# -*- coding: utf-8 -*-
"""Offline tests for the patch engine (src/tuner/tuner.lua).

    .venv\\Scripts\\python.exe -m unittest tests.test_tuner -v

Every scenario is a plain function `check_*(source)` that raises AssertionError when the
engine misbehaves. The unittest cases call them with the real source; the mutation test calls
them with a deliberately broken source and requires them to fail. A scenario that still
passes on a broken engine does not test what it claims.
"""
import hashlib
import os
import struct
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import gen_tuner_data  # noqa: E402
import harness  # noqa: E402
import hd2db  # noqa: E402
from hashnames import murmur64a  # noqa: E402

BUDGET_US, STEP_SLACK_US = 1000, 250
F10 = 0x79


def entity(short_path):
    return murmur64a(("content/fac_helldivers/equipment/" + short_path).encode())


LIBERATOR = entity("primary_weapons/assault_rifle/assault_rifle")
STALWART_NAME = "lmg_stalwart"


def data_for(info, exe=None, dll=None):
    blob, _stats = gen_tuner_data.generate(builds=[(
        "test build",
        hashlib.sha256(exe if exe is not None else info["exe_bytes"]).hexdigest().upper(),
        hashlib.sha256(dll if dll is not None else info["dll_bytes"]).hexdigest().upper())])
    return blob


_SOURCE_CACHE = {}


def real_source(info):
    key = (info["exe_bytes"][:64], len(info["exe_bytes"]))
    if key not in _SOURCE_CACHE:
        _SOURCE_CACHE[key] = harness.addon_source("tuner", data=data_for(info))
    return _SOURCE_CACHE[key]


class Rig:
    """A fake game with the tuner loaded, plus the addresses the tests care about."""

    def __init__(self, config, mutate=None, world=None, wrong_build=False, **game):
        self.mem, self.info = harness.build_world(second_copy=False, **(world or {}))
        source = real_source(self.info)
        if wrong_build:
            source = harness.addon_source("tuner", data=data_for(self.info, exe=b"another build"))
        if mutate:
            old, new = mutate
            assert source.count(old) == 1, "mutation target not found exactly once: %r" % old[:60]
            source = source.replace(old, new)
        self.game = harness.Game(source, self.mem, self.info, global_name="HD2StatTuner",
                                 log_name="tuner.log", config=config, **game)
        self.blocks = self.info["blocks"]

    def close(self):
        self.game.close()

    # addresses, computed independently of the addon (hd2db) -------------------------------
    def row_field(self, table, row_id, offset, block=None):
        t = hd2db.table(table)
        base = block if block is not None else self.blocks[table][0]
        return base + 24 + t.record_offset(t.by_id()[row_id]) + offset

    def keyed_field(self, table, ent, offset, block=None):
        t = hd2db.table(table)
        base = block if block is not None else self.blocks[table][0]
        return base + 24 + t.record_offset(ent) + offset

    @property
    def damage(self):            # the Liberator's damage: shared DamageSettings row 108, +4
        return self.row_field("DamageSettings", 108, 4)

    @property
    def bonus(self):             # the Liberator's own damage addend
        return self.keyed_field("ProjectileWeaponComponentData", LIBERATOR, 128)

    @property
    def rpm(self):
        return self.keyed_field("ProjectileWeaponComponentData", LIBERATOR, 8)

    def settle(self, frames=600):
        self.game.frames(frames, until=lambda: self.game.status().startswith(
            ("OK", "PARTIAL", "REFUSED", "FAILED", "DISABLED")))
        self.game.frames(20)
        return self.game.status()

    def later(self, seconds, frames=400):
        self.game.skip_time(seconds)
        self.game.frames(frames)
        return self.game.status()

    def reload(self, config):
        self.game.write_config(config)
        self.game.press(F10)
        self.game.frames(300)
        return self.game.status()


def first_line(status):
    return status.split("\r\n", 1)[0]


BASE_CONFIG = "[weapon: assault_rifle]\ndamage = 120\ndamage_bonus = +25\nrpm = 150%\n"


# ------------------------------------------------------------------ scenarios
def check_applies_exactly_what_was_asked(mutate=None):
    rig = Rig(BASE_CONFIG, mutate)
    try:
        status = rig.settle()
        assert first_line(status) == "OK - 3 values applied", first_line(status)
        assert rig.mem.peek(rig.damage, "<I") == 120
        assert rig.mem.peek(rig.bonus, "<f") == 25.0
        assert rig.mem.peek(rig.rpm, "<f") == 960.0
        # nothing else was written: exactly three 4-byte writes, at exactly these addresses
        assert sorted(a for a, _d in rig.mem.writes) == sorted([rig.damage, rig.bonus, rig.rpm]), \
            [hex(a) for a, _d in rig.mem.writes]
        assert all(len(d) == 4 for _a, d in rig.mem.writes)
        assert "damage: 90 -> 120  APPLIED  copies=1" in status
        assert "also affects: " in status and STALWART_NAME + ".damage" in status
        assert "[build] verified: test build" in status
        assert max(rig.game.frame_cost) <= BUDGET_US + STEP_SLACK_US, max(rig.game.frame_cost)
    finally:
        rig.close()


def check_removed_lines_are_restored(mutate=None):
    rig = Rig(BASE_CONFIG, mutate)
    try:
        rig.settle()
        status = rig.reload("[weapon: assault_rifle]\nrpm = 150%\n")
        assert first_line(status) == "OK - 1 values applied", first_line(status)
        assert rig.mem.peek(rig.damage, "<I") == 90
        assert rig.mem.peek(rig.bonus, "<f") == 0.0
        assert rig.mem.peek(rig.rpm, "<f") == 960.0
        status = rig.reload("[settings]\nenabled = false\n[weapon: assault_rifle]\nrpm = 150%\n")
        assert first_line(status).startswith("DISABLED"), first_line(status)
        assert rig.mem.peek(rig.rpm, "<f") == 640.0
    finally:
        rig.close()


def check_rejections_write_nothing(mutate=None):
    config = "\n".join([
        "[weapon: assault_rifle]",
        "damage = 200000",            # out of range
        "nonsense = 5",               # unknown stat
        "magazine = 45",              # set by the default attachment
        "ergonomics = fast",          # not a number
        "[weapon: no_such_gun]",
        "damage = 10",
        "[throwable: he_grenade]",
        "fuse = 61",                  # out of range
        ""])
    rig = Rig(config, mutate)
    try:
        status = rig.settle()
        assert first_line(status).startswith("PARTIAL - 0 values applied, 0 waiting for their table, 0 failed, 6 config lines rejected"), first_line(status)
        assert rig.mem.writes == [], rig.mem.writes
        assert "outside the allowed range 0 .. 100000" in status
        assert 'has no stat "nonsense"' in status
        assert "default attachment" in status
        assert "not a number" in status
        assert "unknown weapon" in status
    finally:
        rig.close()


def check_conflicting_lines_reject_each_other(mutate=None):
    config = "[weapon: assault_rifle]\ndamage = 120\n[weapon: %s]\ndamage = 130\nrpm = 700\n" % STALWART_NAME
    rig = Rig(config, mutate)
    try:
        status = rig.settle()
        assert first_line(status).startswith("PARTIAL - 1 values applied"), first_line(status)
        assert rig.mem.peek(rig.damage, "<I") == 90
        assert status.count("ask for different values of the same shared value") == 2
        assert len(rig.mem.writes) == 1                       # only the Stalwart's own rpm
    finally:
        rig.close()


def check_same_value_twice_is_not_a_conflict(mutate=None):
    config = "[weapon: assault_rifle]\ndamage = 120\n[weapon: %s]\ndamage = 120\n" % STALWART_NAME
    rig = Rig(config, mutate)
    try:
        status = rig.settle()
        assert first_line(status) == "OK - 1 values applied", first_line(status)
        assert rig.mem.peek(rig.damage, "<I") == 120
    finally:
        rig.close()


def check_unknown_build_writes_nothing(mutate=None):
    rig = Rig(BASE_CONFIG, mutate, wrong_build=True)
    try:
        status = rig.settle()
        assert first_line(status).startswith("REFUSED - "), first_line(status)
        rig.later(30)
        rig.game.press(F10)
        rig.later(30)
        assert rig.mem.writes == [], rig.mem.writes
        assert rig.mem.peek(rig.damage, "<I") == 90
        assert "known builds:" in rig.game.status()
    finally:
        rig.close()


def check_tables_that_load_later(mutate=None):
    rig = Rig(BASE_CONFIG, mutate)
    try:
        late = [r for r in rig.mem.regions if r["base"] == 0x1E100000000][0]     # component tables
        rig.mem.regions.remove(late)
        status = rig.settle()
        assert first_line(status).startswith("PARTIAL - 1 values applied, 2 waiting for their table"), first_line(status)
        assert rig.mem.peek(rig.damage, "<I") == 120
        rig.mem.regions.append(late)
        rig.mem.regions.sort(key=lambda r: r["base"])                            # "mission loaded"
        for _ in range(6):
            status = rig.later(31)
            if first_line(status).startswith("OK"):
                break
        assert first_line(status) == "OK - 3 values applied", first_line(status)
        assert rig.mem.peek(rig.rpm, "<f") == 960.0
    finally:
        rig.close()


def check_value_changed_back_is_reapplied(mutate=None):
    rig = Rig(BASE_CONFIG, mutate)
    try:
        rig.settle()
        rig.mem.poke(rig.damage, "<I", 90)                    # the game (or another mod) puts it back
        status = rig.later(6)
        assert rig.mem.peek(rig.damage, "<I") == 120
        assert "rewrites=1" in rig.game.status() or "rewrites=1" in status
    finally:
        rig.close()


def check_table_that_moved_is_found_again(mutate=None):
    rig = Rig("[weapon: assault_rifle]\ndamage = 120\n", mutate)
    try:
        rig.settle()
        old = [r for r in rig.mem.regions if r["base"] == 0x1E000000000][0]
        moved = bytearray(old["data"])
        # stock values again, and pointers that point into the new place
        delta = 0x1EA00000000 - 0x1E000000000
        for name, addresses in rig.blocks.items():
            for address in addresses:
                if 0x1E000000000 <= address < 0x1E000000000 + old["size"]:
                    o = address - 0x1E000000000 + 24
                    pointer = struct.unpack_from("<Q", moved, o)[0]
                    if 0x1E000000000 <= pointer < 0x1E000000000 + old["size"]:
                        struct.pack_into("<Q", moved, o, pointer + delta)
        struct.pack_into("<I", moved, rig.damage - 0x1E000000000, 90)
        rig.mem.regions.remove(old)                           # the old table is freed
        rig.mem.add(0x1EA00000000, bytes(moved))
        for _ in range(4):
            rig.later(6)
        new_address = rig.damage + delta
        assert rig.mem.peek(new_address, "<I") == 120, rig.game.status()[:1500]
        assert first_line(rig.game.status()) == "OK - 1 values applied"
    finally:
        rig.close()


def check_second_copy_is_patched_too(mutate=None):
    rig = Rig("[weapon: assault_rifle]\ndamage = 120\n", mutate)
    try:
        rig.settle()
        t = hd2db.table("DamageSettings")
        payload = bytearray(t.data[t.base:t.base + t.size])
        chain = harness.Chain(0x1EB00000000, prefix=4)
        second = chain.add("DamageSettings", payload, fix=harness.absolute_array)
        rig.mem.add(chain.base, chain.data)                   # a new copy; the old one stays
        for _ in range(8):
            rig.later(31)
        address = rig.row_field("DamageSettings", 108, 4, block=second)
        assert rig.mem.peek(address, "<I") == 120, rig.game.status()[:1500]
        assert rig.mem.peek(rig.damage, "<I") == 120
        assert "damage: 90 -> 120  APPLIED  copies=2" in rig.game.status()
    finally:
        rig.close()


def check_read_only_pages_are_opened_for_one_write_and_closed(mutate=None):
    # in game the component tables (fire rate, handling...) are in read-only pages
    rig = Rig(BASE_CONFIG, mutate)
    try:
        region = [r for r in rig.mem.regions if r["base"] == 0x1E100000000][0]
        region["protect"] = harness.PAGE_READONLY
        status = rig.settle()
        assert first_line(status) == "OK - 3 values applied", first_line(status)
        assert rig.mem.peek(rig.rpm, "<f") == 960.0 and rig.mem.peek(rig.bonus, "<f") == 25.0
        assert region["protect"] == harness.PAGE_READONLY          # closed again
        page = lambda a: a - a % 4096
        assert sorted(rig.mem.protects) == sorted(
            [(page(rig.rpm), harness.PAGE_READWRITE), (page(rig.rpm), harness.PAGE_READONLY),
             (page(rig.bonus), harness.PAGE_READWRITE), (page(rig.bonus), harness.PAGE_READONLY)]), rig.mem.protects
        # every "open" is followed at once by its "close"
        for i in range(0, len(rig.mem.protects), 2):
            assert rig.mem.protects[i][1] == harness.PAGE_READWRITE
            assert rig.mem.protects[i + 1] == (rig.mem.protects[i][0], harness.PAGE_READONLY)
        assert "read-only pages opened for a write=2, not closed again=0" in status
        assert len(rig.mem.writes) == 3
        # the writable settings table never needs it
        assert all(p != page(rig.damage) for p, _prot in rig.mem.protects)
    finally:
        rig.close()


def check_a_write_that_did_not_stick_is_reported(mutate=None):
    rig = Rig("[weapon: assault_rifle]\ndamage = 120\n", mutate)
    try:
        rig.mem.write_ignored = True
        status = rig.settle()
        assert "read-back mismatch: wrote 120, read 90" in status, status[:1200]
        assert first_line(status).startswith("PARTIAL - 0 values applied")
        # a failed value is reported once, not retried every few seconds
        for _ in range(6):
            rig.later(6, frames=120)
        assert "changed back" not in rig.game.log_text(), rig.game.log_text()[-600:]
        assert len(rig.mem.writes) == 1, len(rig.mem.writes)
    finally:
        rig.close()


def check_implausible_current_value_is_not_touched(mutate=None):
    rig = Rig("[weapon: assault_rifle]\ndamage = 120\n", mutate)
    try:
        rig.mem.poke(rig.damage, "<I", 0x7F000000)            # the layout is not what we think
        status = rig.settle()
        assert rig.mem.writes == [], rig.mem.writes
        assert "implausible" in status
    finally:
        rig.close()


def check_value_forms_and_shortcuts(mutate=None):
    config = "\n".join([
        "[weapon: assault_rifle]",
        "ap = 4",                     # every angle that is not 0: three of the four
        "ergonomics = 50%",           # 65 -> 32.5 (a float stat keeps the fraction)
        "durable_damage = 140%",      # 22 -> 30.8 -> 31 (whole number)
        "recoil_v = -2,5",            # decimal comma; drift 10 -> 7.5, climb 20 -> 17.5
        "[throwable: he_grenade]",
        "fuse = 2.0",
        "carried = +1",
        ""])
    rig = Rig(config, mutate)
    try:
        status = rig.settle()
        assert first_line(status) == "OK - 9 values applied", first_line(status)
        ap = [rig.mem.peek(rig.row_field("DamageSettings", 108, 12 + 4 * i), "<I") for i in range(4)]
        assert ap == [4, 4, 4, 0], ap
        wd = lambda off: rig.mem.peek(rig.keyed_field("WeaponDataComponentData", LIBERATOR, off), "<f")
        assert wd(356) == 32.5 and wd(4) == 7.5 and wd(32) == 17.5, (wd(356), wd(4), wd(32))
        assert rig.mem.peek(rig.row_field("DamageSettings", 108, 8), "<I") == 31
        grenade = entity("throwables/he_grenade/he_grenade")
        assert rig.mem.peek(rig.keyed_field("ExplosiveComponentData", grenade, 12), "<f") == 2.0
        assert rig.mem.peek(rig.keyed_field("ThrowableComponentData", grenade, 104), "<I") == 6
    finally:
        rig.close()


def check_reload_key_needs_the_game_in_front(mutate=None):
    rig = Rig("[weapon: assault_rifle]\ndamage = 120\n", mutate)
    try:
        rig.settle()
        rig.game.in_front = False
        rig.game.write_config("[weapon: assault_rifle]\ndamage = 150\n")
        rig.game.press(F10)
        rig.game.frames(300)
        assert rig.mem.peek(rig.damage, "<I") == 120          # another window had the focus
        rig.game.in_front = True
        rig.game.press(F10)
        rig.game.frames(300)
        assert rig.mem.peek(rig.damage, "<I") == 150
    finally:
        rig.close()


def check_auto_reload(mutate=None):
    rig = Rig("[settings]\nauto_reload_seconds = 2\n[weapon: assault_rifle]\ndamage = 120\n", mutate)
    try:
        rig.settle()
        rig.game.write_config("[settings]\nauto_reload_seconds = 2\n[weapon: assault_rifle]\ndamage = 140\n")
        rig.later(3)
        assert rig.mem.peek(rig.damage, "<I") == 140
    finally:
        rig.close()


def check_idle_engine_reads_no_game_memory(mutate=None):
    rig = Rig("", mutate)
    try:
        status = rig.settle()
        assert first_line(status) == "OK - no changes configured", first_line(status)
        rig.later(600, frames=600)
        assert rig.mem.read_log == [], rig.mem.read_log[:5]   # nothing configured: no scanning at all
        assert rig.mem.writes == []
    finally:
        rig.close()


def check_api(mutate=None):
    rig = Rig("", mutate)
    try:
        rig.settle()
        api = rig.game.state()[b"api"]
        assert sorted(x for x in api[b"categories"]().values()) == [b"throwable", b"weapon"]
        stats = {s[b"id"]: s for s in api[b"stats"](b"weapon", b"assault_rifle").values()}
        assert stats[b"damage"][b"game"] == 90 and stats[b"damage"][b"shared_with"] == 3
        assert stats[b"capacity"][b"editable"] is False
        api[b"set"](b"weapon", b"assault_rifle", b"damage", b"150")
        rig.game.frames(300)
        assert rig.mem.peek(rig.damage, "<I") == 150
        api[b"set"](b"weapon", b"assault_rifle", b"damage", None)
        rig.game.frames(300)
        assert rig.mem.peek(rig.damage, "<I") == 90
    finally:
        rig.close()


def check_catalog_and_template(mutate=None):
    rig = Rig(None, mutate)                                   # no config.txt at all
    try:
        rig.settle()
        catalog = rig.game.read_out("catalog.txt")
        assert "[weapon: assault_rifle]" in catalog
        assert "  damage = 90   (0 .. 100000, whole numbers)   # shared with 3 other" in catalog, catalog[:600]
        assert "set by the default attachment" in catalog
        template = rig.game.read_out("config.txt")
        assert "[settings]" in template and "# [weapon: assault_rifle]" in template
        assert rig.mem.writes == []
    finally:
        rig.close()


def check_search_is_spread_over_frames(mutate=None):
    rig = Rig(BASE_CONFIG, mutate, world=dict(filler=4000))   # a pass costs far more than one frame's budget
    try:
        status = rig.settle(frames=3000)
        assert first_line(status) == "OK - 3 values applied", first_line(status)
        assert max(rig.game.frame_cost) <= BUDGET_US + STEP_SLACK_US, max(rig.game.frame_cost)
        assert len([c for c in rig.game.frame_cost if c > 0]) > 10
    finally:
        rig.close()


def check_fallback_enumeration(mutate=None):
    rig = Rig(BASE_CONFIG, mutate, region_info=False)         # NtQueryVirtualMemory class 3 unavailable
    try:
        status = rig.settle()
        assert first_line(status) == "OK - 3 values applied", first_line(status)
    finally:
        rig.close()


CHECKS = [v for k, v in sorted(globals().items()) if k.startswith("check_")]


class Engine(unittest.TestCase):
    pass


def _make(check):
    def test(self):
        check()
    return test


for _check in CHECKS:
    setattr(Engine, "test_" + _check.__name__[6:], _make(_check))


class Startup(unittest.TestCase):
    def test_old_loader_or_missing_hook_never_writes(self):
        for kw, text in ((dict(loader_api=0), "too old"), (dict(has_update=False), "update hook")):
            rig = Rig(BASE_CONFIG, **kw)
            try:
                status = rig.game.status()
                self.assertTrue(status.startswith("FAILED - "), status[:200])
                self.assertIn(text, status)
                if kw.get("has_update", True):
                    rig.game.frames(400)
                self.assertEqual(rig.mem.writes, [])
            finally:
                rig.close()

    def test_first_lines_carry_the_version(self):
        rig = Rig(BASE_CONFIG)
        try:
            status = rig.settle()
            self.assertRegex(status.split("\r\n")[1], r"^HD2 Stat Tuner v\d+\.\d+\.\d+$")
            self.assertRegex(rig.game.log_text().split("\r\n")[0], r"^HD2 Stat Tuner v\d+\.\d+\.\d+$")
        finally:
            rig.close()

    def test_update_chain_is_preserved(self):
        rig = Rig(BASE_CONFIG)
        try:
            rig.settle()
            self.assertEqual(rig.game.lua.globals()[b"HD2ST_UPDATES"], len(rig.game.frame_cost))
            self.assertEqual(rig.game.last_update_result, (b"base", 0.016))
        finally:
            rig.close()


# (name, text to find, replacement, scenario that must fail)
MUTATIONS = [
    ("build gate removed",
     "        if build.state ~= 'verified' then\n            state.phase = 'refused'",
     "        if false then\n            state.phase = 'refused'",
     check_unknown_build_writes_nothing),
    ("build accepted when only the exe matches",
     "if exe.sha256 and dll.sha256 and exe.sha256 == known.exe and dll.sha256 == known.dll then",
     "if exe.sha256 and exe.sha256 ~= known.exe then",
     check_unknown_build_writes_nothing),
    ("range check removed",
     "if value ~= value or value < range.min or value > range.max then",
     "if value ~= value then",
     check_rejections_write_nothing),
    ("attachment-owned stats editable",
     "            if entry.attachment then\n                request.status = 'rejected'",
     "            if false then\n                request.status = 'rejected'",
     check_rejections_write_nothing),
    ("conflict rule removed",
     "if not same_value(target.field.storage, claim.value, target.value) then claim.conflict = true end",
     "",
     check_conflicting_lines_reject_each_other),
    ("read-back removed",
     "    if not same_value(field.storage, back, value) then\n        return false, 'read-back mismatch",
     "    if false then\n        return false, 'read-back mismatch",
     check_a_write_that_did_not_stick_is_reported),
    ("read-only page not opened before the write",
     "        if address % 4096 > 4092 or not A.protect(address, PAGE_READWRITE) then",
     "        if address % 4096 > 4092 then",
     check_read_only_pages_are_opened_for_one_write_and_closed),
    ("read-only page left writable after the write",
     "        local restored = A.protect(address, PAGE_READONLY)\n",
     "        local restored = true\n",
     check_read_only_pages_are_opened_for_one_write_and_closed),
    ("writable pages are 'opened' too",
     "    if protection == PAGE_READONLY then\n        -- In game the component tables",
     "    if true then\n        -- In game the component tables",
     check_read_only_pages_are_opened_for_one_write_and_closed),
    ("a refused write is retried forever",
     "            if entry.value ~= nil and copy.written then",
     "            if entry.value ~= nil then",
     check_a_write_that_did_not_stick_is_reported),
    ("record address forgets the bucket array",
     "block.records_at, block.index, block.count = payload + fit.buckets * 16, index, fit.records",
     "block.records_at, block.index, block.count = payload, index, fit.records",
     check_applies_exactly_what_was_asked),
    ("array pointer in memory treated as a relative offset",
     "    if pointer < size then rows_at = payload + pointer\n    elseif pointer >= payload and pointer < payload + size then rows_at = pointer",
     "    if true then rows_at = payload + pointer\n    elseif pointer >= payload and pointer < payload + size then rows_at = pointer",
     check_applies_exactly_what_was_asked),
    ("write passes a number instead of a pointer",
     "if write_memory(process, ffi.cast(void, address), out, 4, got) == 0 then return false end",
     "if write_memory(process, address, out, 4, got) == 0 then return false end",
     check_applies_exactly_what_was_asked),
    ("removed lines are not restored",
     "            sync_field(entry, nil)\n",
     "",
     check_removed_lines_are_restored),
    ("float written as a truncated integer",
     "        local bits = A.f32_bits(value)\n",
     "        local bits = math.floor(value)\n",
     check_applies_exactly_what_was_asked),
    ("percent taken of the target instead of the game value",
     "        return stock * n / 100",
     "        return n / 100",
     check_applies_exactly_what_was_asked),
    ("recheck never notices a changed value",
     "if not same_value(entry.field.storage, current, entry.value) then result = 'changed' end",
     "",
     check_value_changed_back_is_reapplied),
    ("a vanished table is not noticed",
     "            if not valid_block(copy.block) then\n                return 'lost'\n            end",
     "",
     check_table_that_moved_is_found_again),
    ("no periodic look for new copies",
     "local rescan_due = have_work and config.rescan > 0 and A.now() >= next_rescan",
     "local rescan_due = false",
     check_second_copy_is_patched_too),
    ("reload key works while another window is in front",
     "if down and not key_was_down and A.game_in_front() then",
     "if down and not key_was_down then",
     check_reload_key_needs_the_game_in_front),
    ("implausible values are overwritten",
     "                    elseif range and (current < range.min - 0.5 or current > range.max + 0.5)\n                        and not same_value(field.storage, current, field.stock) then",
     "                    elseif false then",
     check_implausible_current_value_is_not_touched),
    ("'ap' also sets angles that are 0",
     "if entry and range and not (nonzero and entry.field.stock == 0) then",
     "if entry and range then",
     check_value_forms_and_shortcuts),
    ("whole-number stats keep fractions",
     "if range.integer or entry.field.storage ~= 'f32' then value = math.floor(value + 0.5) end",
     "",
     check_value_forms_and_shortcuts),
    ("table search never yields",
     "        if next_cursor <= cursor then next_cursor = cursor + 4096 end\n        cursor = next_cursor\n        pause()",
     "        if next_cursor <= cursor then next_cursor = cursor + 4096 end\n        cursor = next_cursor",
     check_search_is_spread_over_frames),
    ("idle engine scans anyway",
     "            if have_work and (#missing > 0 or state.lost or rescan_due) then",
     "            if true then",
     check_idle_engine_reads_no_game_memory),
    ("disabled config still applies",
     "    if not config.enabled then\n        for _, request in ipairs(config.requests) do",
     "    if false then\n        for _, request in ipairs(config.requests) do",
     check_removed_lines_are_restored),
]


class Mutations(unittest.TestCase):
    def test_every_mutation_is_caught(self):
        survivors = []
        for name, old, new, check in MUTATIONS:
            try:
                check((old, new))
            except Exception:
                continue                      # caught (assertion, or the addon failed to load)
            survivors.append(name)
        self.assertEqual(survivors, [])

    def test_mutation_targets_exist(self):
        mem, info = harness.build_world(second_copy=False)
        source = real_source(info)
        for name, old, _new, _check in MUTATIONS:
            self.assertEqual(source.count(old), 1, name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
