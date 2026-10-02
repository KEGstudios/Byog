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


BASE_CONFIG = "[weapon: assault_rifle]\ndamage = 120\nap_bonus = +2\nrpm = 150%\n"


# ------------------------------------------------------------------ scenarios
def check_applies_exactly_what_was_asked(mutate=None):
    rig = Rig(BASE_CONFIG, mutate)
    try:
        status = rig.settle()
        assert first_line(status) == "OK - 3 values applied", first_line(status)
        assert rig.mem.peek(rig.damage, "<I") == 120
        assert rig.mem.peek(rig.bonus, "<f") == 2.0
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
        assert rig.mem.peek(rig.rpm, "<f") == 960.0 and rig.mem.peek(rig.bonus, "<f") == 2.0
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
        rig.game.skip_time(2)
        rig.game.press(F10)
        rig.game.frames(300)
        assert rig.mem.peek(rig.damage, "<I") == 150
    finally:
        rig.close()


def check_reload_key_is_debounced(mutate=None):
    rig = Rig("[weapon: assault_rifle]\ndamage = 120\n", mutate)
    try:
        rig.settle()
        before = rig.game.state()[b"reloads"]
        for _ in range(5):                                    # five presses within a quarter of a second
            rig.game.press(F10)
        rig.game.frames(200)
        assert rig.game.state()[b"reloads"] == before + 1, rig.game.state()[b"reloads"] - before
        rig.game.skip_time(2)
        rig.game.press(F10)
        rig.game.frames(200)
        assert rig.game.state()[b"reloads"] == before + 2
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


# ------------------------------------------------------------------ own bullet (row takeover)
OWN_CONFIG = "[weapon: assault_rifle]\nown_bullet = true\ndamage = 5000\nvelocity = 1200\nrpm = 700\n"
SRC_PROJECTILE, NEW_PROJECTILE, SRC_DAMAGE, NEW_DAMAGE = 276, 267, 108, 55


def own_addresses(rig):
    import deltas
    d = deltas._load()
    override = deltas.default_overrides(LIBERATOR)[("ProjectileWeaponComponent", 0)]
    return dict(
        new_projectile=rig.row_field("ProjectileSettings", NEW_PROJECTILE, 0),
        src_projectile=rig.row_field("ProjectileSettings", SRC_PROJECTILE, 0),
        new_damage=rig.row_field("DamageSettings", NEW_DAMAGE, 0),
        src_damage=rig.row_field("DamageSettings", SRC_DAMAGE, 0),
        pointer=rig.keyed_field("ProjectileWeaponComponentData", LIBERATOR, 0),
        ammo=rig.blocks["ComponentEntityDeltaStorage"][0] + 24 + override[1],
        stalwart=rig.keyed_field("ProjectileWeaponComponentData",
                                 entity("primary_weapons/lmg_stalwart/lmg_stalwart"), 0),
    )


def row_bytes(rig, address, size):
    r = rig.mem.find(address)
    o = address - r["base"]
    return bytes(r["data"][o:o + size])


def snapshot(rig):
    return {r["base"]: bytes(r["data"]) for r in rig.mem.regions}


def check_own_bullet_gives_the_weapon_private_rows(mutate=None):
    rig = Rig(OWN_CONFIG, mutate)
    try:
        a = own_addresses(rig)
        before = snapshot(rig)
        stock_projectile = row_bytes(rig, a["src_projectile"], 272)
        stock_damage = row_bytes(rig, a["src_damage"], 76)
        assert rig.mem.peek(a["ammo"], "<I") == SRC_PROJECTILE          # the fixture is what we think it is
        status = rig.settle()
        assert first_line(status) == "OK - 3 values applied, 1 weapons on their own bullet", first_line(status)
        # the spare projectile row is now the Liberator's round, with its own damage row and the new speed
        want = bytearray(stock_projectile)
        struct.pack_into("<I", want, 0, NEW_PROJECTILE)
        struct.pack_into("<I", want, 60, NEW_DAMAGE)
        struct.pack_into("<f", want, 32, 1200.0)
        assert row_bytes(rig, a["new_projectile"], 272) == bytes(want)
        want = bytearray(stock_damage)
        struct.pack_into("<I", want, 0, NEW_DAMAGE)
        struct.pack_into("<i", want, 4, 5000)
        assert row_bytes(rig, a["new_damage"], 76) == bytes(want)
        # the weapon and its ammo attachment point at the new row; nobody else does
        assert rig.mem.peek(a["pointer"], "<I") == NEW_PROJECTILE
        assert rig.mem.peek(a["ammo"], "<I") == NEW_PROJECTILE
        assert rig.mem.peek(a["stalwart"], "<I") == SRC_PROJECTILE
        # the shared rows are untouched: the Stalwart still fires the stock round
        assert row_bytes(rig, a["src_projectile"], 272) == stock_projectile
        assert row_bytes(rig, a["src_damage"], 76) == stock_damage
        # the two switches were thrown last, after every row field was in place
        order = [address for address, _data in rig.mem.writes]
        last_row_write = max(i for i, address in enumerate(order) if address not in (a["pointer"], a["ammo"]))
        first_switch = min(i for i, address in enumerate(order) if address in (a["pointer"], a["ammo"]))
        assert first_switch > last_row_write, (first_switch, last_row_write)
        assert "OWN BULLET ACTIVE: projectile row 276 -> 267, damage row 108 -> 55" in status
        assert "damage: 90 -> 5000 (own row)  APPLIED" in status
        assert "also affects" not in status.split("damage: 90 -> 5000")[1].split("\r\n")[0]
        # take it all back: switches first, then every byte as it was
        writes_before = len(rig.mem.writes)
        status = rig.reload("")
        assert first_line(status) == "OK - no changes configured", first_line(status)
        restore_order = [address for address, _data in rig.mem.writes[writes_before:]]
        assert set(restore_order[:2]) == {a["pointer"], a["ammo"]}, [hex(x) for x in restore_order[:3]]
        assert snapshot(rig) == before
    finally:
        rig.close()


def check_own_bullet_does_not_switch_onto_an_unexpected_row(mutate=None):
    rig = Rig(OWN_CONFIG, mutate)
    try:
        a = own_addresses(rig)
        rig.mem.poke(a["new_projectile"] + 36, "<f", 123.0)   # the "spare" row is not what this build expects
        status = rig.settle()
        assert rig.mem.peek(a["pointer"], "<I") == SRC_PROJECTILE
        assert rig.mem.peek(a["ammo"], "<I") == SRC_PROJECTILE
        assert rig.mem.peek(a["new_projectile"] + 36, "<f") == 123.0
        assert "OWN BULLET FAILED" in status and "unexpected content" in status, status[:1500]
        assert first_line(status).startswith("PARTIAL"), first_line(status)
    finally:
        rig.close()


def check_own_bullet_waits_for_the_weapon_tables(mutate=None):
    rig = Rig(OWN_CONFIG, mutate)
    try:
        a = own_addresses(rig)
        late = [r for r in rig.mem.regions if r["base"] == 0x1E100000000][0]     # component tables
        rig.mem.regions.remove(late)
        status = rig.settle()
        assert "OWN BULLET WAITING" in status, status[:1500]
        # The ammo attachment lives in another table and may already point at the new row: that is
        # safe, because a switch is only thrown once every field of the new rows is in place.
        if rig.mem.peek(a["ammo"], "<I") == NEW_PROJECTILE:
            assert rig.mem.peek(a["new_projectile"] + 60, "<I") == NEW_DAMAGE
            assert rig.mem.peek(a["new_damage"] + 4, "<i") == 5000
        rig.mem.regions.append(late)
        rig.mem.regions.sort(key=lambda r: r["base"])
        for _ in range(6):
            status = rig.later(31)
            if "OWN BULLET ACTIVE" in status:
                break
        assert "OWN BULLET ACTIVE" in status, status[:1500]
        assert rig.mem.peek(a["pointer"], "<I") == NEW_PROJECTILE and rig.mem.peek(a["ammo"], "<I") == NEW_PROJECTILE
    finally:
        rig.close()


def check_own_bullet_only_where_defined(mutate=None):
    rig = Rig("[weapon: lmg_stalwart]\nown_bullet = true\ndamage = 100\n[weapon: assault_rifle]\nown_bullet = maybe\n", mutate)
    try:
        status = rig.settle()
        assert "own_bullet is not available for this weapon yet" in status
        assert "own_bullet takes true, false or new" in status
        assert rig.mem.peek(rig.damage, "<I") == 100              # the plain line still works (shared row)
        assert len(rig.mem.writes) == 1
    finally:
        rig.close()


def check_probe_finds_pointer_arrays_and_writes_nothing(mutate=None):
    rig = Rig("[settings]\nprobe = true\n", mutate)
    try:
        t = hd2db.table("ProjectileSettings")
        rows_at = rig.blocks["ProjectileSettings"][0] + 24 + 16
        ids = sorted(t.by_id())
        # what an engine-side index could look like: one pointer per id, in id order ...
        by_id = bytearray(8 * (max(ids) + 1))
        for row_id, row in t.by_id().items():
            struct.pack_into("<Q", by_id, 8 * row_id, rows_at + row * t.stride)
        # ... plus a lone pointer to one row somewhere else, and noise that must not count
        heap = bytearray(4096 * 4)
        struct.pack_into("<Q", heap, 0x120, rows_at + 5 * t.stride)
        struct.pack_into("<Q", heap, 0x200, 0x1E000000000 - 8)            # just below the block
        struct.pack_into("<Q", heap, 0x1008, rows_at + 9 * t.stride)       # on a page that is not in memory
        rig.mem.add(0x1EC00000000, bytes(by_id))
        rig.mem.add(0x1ED00000000, bytes(heap), absent={1})
        rig.game.frames(4000, until=lambda: "probe: done" in rig.game.status())
        status = rig.game.status()
        assert "probe: done" in status, status[:900]
        report = rig.game.read_out("PROBE.txt")
        section = report.split("[ProjectileSettings]")[1].split("[DamageSettings]")[0]
        present = sum(1 for i in ids)                                      # every id has a pointer in the array
        assert "at 0x1EC00000000:" in section or "at 0x1EC0000" in section, section[:800]
        import re
        m = re.search(r"at (0x1EC[0-9A-F]+): (\d+) pointers, (\d+) to row starts; row id = slot ([+-]\d+) for (\d+) of them", section)
        assert m, section[:800]
        # one pointer per row, and the engine-style index is recognised as "indexed by row id"
        assert int(m.group(2)) == len(ids) == int(m.group(3)), m.groups()
        assert int(m.group(5)) >= 300, m.groups()
        assert "0x1ED00000120->" in section                               # the lone pointer
        assert "0x1ED00001008" not in report                              # absent page: never read
        assert "0x1ED00000200" not in report                              # outside the table: not a hit
        assert rig.mem.writes == [] and rig.mem.protects == []
        assert rig.mem.absent_reads == 0
        assert max(rig.game.frame_cost) <= BUDGET_US + STEP_SLACK_US, max(rig.game.frame_cost)
    finally:
        rig.close()


ENGINE_BASE = 0x7FFD00000000


def add_engine_module(rig):
    """A module image like the game's: code that refers to id-indexed arrays of row pointers in .data.

    -> {table: (array rva, slots)}"""
    header = bytearray(4096)
    header[0:2] = b"MZ"
    struct.pack_into("<I", header, 0x3C, 0x80)
    header[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<H", header, 0x80 + 6, 2)                 # NumberOfSections
    struct.pack_into("<H", header, 0x80 + 20, 240)              # SizeOfOptionalHeader
    struct.pack_into("<H", header, 0x80 + 24, 0x20B)            # PE32+
    struct.pack_into("<I", header, 0x80 + 24 + 56, 0xD000)      # SizeOfImage
    table_at = 0x80 + 24 + 240
    for n, (name, size, rva, flags) in enumerate(((b".text", 0x8000, 0x1000, 0x60000020),
                                                  (b".data", 0x4000, 0x9000, 0xC0000040))):
        o = table_at + n * 40
        header[o:o + len(name)] = name
        struct.pack_into("<II", header, o + 8, size, rva)
        struct.pack_into("<I", header, o + 36, flags)

    data = bytearray(0x4000)
    arrays = {}
    for name, rva in (("ProjectileSettings", 0x9800), ("DamageSettings", 0xA400), ("ExplosionSettings", 0xBC00)):
        t = hd2db.table(name)
        rows_at = rig.blocks[name][0] + 24 + 16
        ids = t.by_id()
        for row_id, row in ids.items():
            struct.pack_into("<Q", data, rva - 0x9000 + 8 * (row_id - 1), rows_at + row * t.stride)
        arrays[name] = (rva, max(ids))
    rva, slots = arrays["ProjectileSettings"]
    assert sorted(hd2db.table("ProjectileSettings").by_id()) == list(range(1, slots + 1))
    struct.pack_into("<Q", data, rva - 0x9000 - 8, slots)                       # a count right before the array
    struct.pack_into("<Q", data, rva - 0x9000 + slots * 8 + 8, ENGINE_BASE + 0x1234)
    struct.pack_into("<I", data, 0x3F00, rva)                                   # data, not code: never a reference

    text = bytearray(b"\xCC" * 0x8000)

    def put(at_rva, code):
        text[at_rva - 0x1000:at_rva - 0x1000 + len(code)] = code
    put(0x1100, b"\x48\x8D\x0D" + struct.pack("<i", rva - (0x1103 + 4)))        # lea rcx, [rip + array]
    put(0x2000, b"\x4A\x8B\x84\xC1" + struct.pack("<I", rva - 8))               # mov rax, [rcx + r8*8 + array - 8]
    put(0x7000, b"\x48\x8D\x05" + struct.pack("<I", 0x9000))                    # names something far from the array
    # a reference whose 4 bytes straddle two 16 KB reads: it names the end of the array
    put(0x1000 + 16382 - 3, b"\x48\x8B\x05" + struct.pack("<i", rva + slots * 8 - (0x1000 + 16382 + 4)))

    rig.mem.add(ENGINE_BASE, bytes(header), protect=harness.PAGE_READONLY, mtype=harness.MEM_IMAGE,
                allocation=ENGINE_BASE)
    rig.mem.add(ENGINE_BASE + 0x1000, bytes(text), protect=harness.PAGE_EXECUTE_READ, mtype=harness.MEM_IMAGE,
                allocation=ENGINE_BASE)
    region = rig.mem.add(ENGINE_BASE + 0x9000, bytes(data), mtype=harness.MEM_IMAGE, allocation=ENGINE_BASE)
    region["written"] = True
    rig.info.setdefault("module_paths", {})[ENGINE_BASE] = "C:\\Games\\Helldivers 2\\bin\\engine.dll"
    return arrays


def check_probe_reads_the_module_that_holds_the_index(mutate=None):
    rig = Rig("[settings]\nprobe = true\n", mutate)
    try:
        arrays = add_engine_module(rig)
        rva, slots = arrays["ProjectileSettings"]
        rig.game.frames(6000, until=lambda: "probe: done" in rig.game.status())
        assert "probe: done" in rig.game.status(), rig.game.status()[:900]
        report = rig.game.read_out("PROBE.txt")
        assert "index analysis failed" not in report, report[-600:]
        assert ("[module engine.dll] base 0x7FFD00000000 image size 0xD000; code read: 32768 bytes, unreadable 0; "
                "candidate references 3") in report, report[report.find("[module"):][:400]
        assert "C:\\Games" not in report                                   # file name only, never the folder
        assert ".text rva 0x1000 size 0x8000 flags 0x60000020; .data rva 0x9000 size 0x4000 flags 0xC0000040" in report
        section = report.split("[index ProjectileSettings]")[1].split("[index DamageSettings]")[0]
        lines = section.split("\r\n")
        assert lines[0] == " at 0x7FFD00009800, %d slots, row id = slot +1" % slots, lines[0]
        assert lines[1].startswith("memory: type 0x1000000 (module image), protection 0x04,"), lines[1]
        assert lines[2].startswith("module: engine.dll, array at rva 0x9800 (section .data, "), lines[2]
        assert lines[3].startswith("64 slots before: ") and lines[3].endswith(" 0x%X" % slots), lines[3][-60:]
        assert lines[4].startswith("64 slots after: 0 img+0x1234 0 "), lines[4][:60]
        assert "code naming array -8: 1\r\n  image at rva 0x2004: " in section, section[:1500]
        assert "code naming array +0: 1\r\n  rip at rva 0x1103: " in section
        assert "code naming array %+d: 1\r\n  rip at rva 0x4FFE: " % (slots * 8) in section
        context = section.split("rip at rva 0x1103: ")[1].split("\r\n")[0]
        assert " 48 8D 0D [" in context and context.count(" ") == 75, context
        assert "[index ExplosionSettings] at 0x7FFD0000BC00, " in report
        assert rig.mem.writes == [] and rig.mem.protects == []
        assert rig.mem.absent_reads == 0
        assert max(rig.game.frame_cost) <= BUDGET_US + STEP_SLACK_US, max(rig.game.frame_cost)
    finally:
        rig.close()


def check_probe_waits_until_every_table_is_loaded(mutate=None):
    rig = Rig("[settings]\nprobe = true\n", mutate)
    try:
        hidden = rig.blocks["DamageSettings"][0] + 8                       # the block's type hash
        real = rig.mem.peek(hidden, "<I")
        rig.mem.poke(hidden, "<I", real ^ 0x5A5A5A5A)                      # "not loaded yet"
        rig.game.frames(1500)
        assert "waiting for DamageSettings" in rig.game.status(), rig.game.status()[:900]
        assert rig.game.read_out("PROBE.txt") == ""
        rig.mem.poke(hidden, "<I", real)                                   # "mission loaded"
        for _ in range(6):
            rig.game.skip_time(16)
            rig.game.frames(6000, until=lambda: "probe: done" in rig.game.status())
        assert "probe: done" in rig.game.status(), rig.game.status()[:900]
        assert "[DamageSettings] block" in rig.game.read_out("PROBE.txt")
        assert rig.mem.writes == []
    finally:
        rig.close()


INDEX_RVA, INDEX_SLOTS = gen_tuner_data.INDEXES["release/01.007.101/19155"]["ProjectileSettings"]
NEW_CONFIG = "[weapon: assault_rifle]\nown_bullet = new\ndamage = 5000\nvelocity = 1200\n"


def add_game_index(rig, wrong_id=None, block=None):
    """game.dll's id-indexed array of projectile row pointers, in image pages the game has written to.

    wrong_id: that id leads to the row of another id (an index this version was not measured on)."""
    t = hd2db.table("ProjectileSettings")
    rows_at = (block if block is not None else rig.blocks["ProjectileSettings"][0]) + 24 + 16
    page = bytearray(0x2000)
    ids = t.by_id()
    assert max(ids) + 1 == INDEX_SLOTS
    for row_id, row in ids.items():
        if row_id == wrong_id:
            row = ids[row_id + 1]
        struct.pack_into("<Q", page, INDEX_RVA % 0x1000 + 8 * row_id, rows_at + row * t.stride)
    base = rig.info["dll_base"] + INDEX_RVA - INDEX_RVA % 0x1000
    region = rig.mem.add(base, bytes(page), mtype=harness.MEM_IMAGE, allocation=rig.info["dll_base"])
    region["written"] = True
    return rig.info["dll_base"] + INDEX_RVA


def in_game_dll(rig, address):
    return rig.info["dll_base"] <= address < rig.info["dll_base"] + INDEX_RVA + 0x1000   # the fake image ends there


def check_new_projectile_id_in_memory_of_our_own(mutate=None):
    rig = Rig(NEW_CONFIG, mutate)
    try:
        a = own_addresses(rig)
        index = add_game_index(rig)
        before = snapshot(rig)
        stock_projectile = row_bytes(rig, a["src_projectile"], 272)
        spare_projectile = row_bytes(rig, a["new_projectile"], 272)
        stock_damage = row_bytes(rig, a["src_damage"], 76)
        status = rig.settle()
        assert first_line(status) == "OK - 2 values applied, 1 weapons on their own bullet", status[:1500]
        # one allocation of our own, above game.dll
        assert len(rig.mem.allocs) == 1, rig.mem.allocs
        own_base, own_size = rig.mem.allocs[0]
        assert own_base > index and own_size == 0x10000
        # the weapon and its ammo attachment carry an id no real row has, and it fits 31 bits
        new_id = rig.mem.peek(a["pointer"], "<I")
        assert INDEX_SLOTS < new_id < 2 ** 31, new_id
        assert rig.mem.peek(a["ammo"], "<I") == new_id
        assert rig.mem.peek(a["stalwart"], "<I") == SRC_PROJECTILE
        # what the game does with that id: [index + id * 8] is a pointer to the row
        row = rig.mem.peek(index + 8 * new_id, "<Q")
        assert own_base <= row and row + 272 <= own_base + own_size, hex(row)
        want = bytearray(stock_projectile)
        struct.pack_into("<I", want, 0, new_id)
        struct.pack_into("<I", want, 60, NEW_DAMAGE)
        struct.pack_into("<f", want, 32, 1200.0)
        assert row_bytes(rig, row, 272) == bytes(want)
        # damage still goes to the spare damage row
        want = bytearray(stock_damage)
        struct.pack_into("<I", want, 0, NEW_DAMAGE)
        struct.pack_into("<i", want, 4, 5000)
        assert row_bytes(rig, a["new_damage"], 76) == bytes(want)
        # no projectile row of the game was touched, and nothing inside game.dll was written
        assert row_bytes(rig, a["src_projectile"], 272) == stock_projectile
        assert row_bytes(rig, a["new_projectile"], 272) == spare_projectile
        assert not [hex(address) for address, _data in rig.mem.writes if in_game_dll(rig, address)]
        # the switches came last
        order = [address for address, _data in rig.mem.writes]
        first_switch = min(i for i, address in enumerate(order) if address in (a["pointer"], a["ammo"]))
        assert all(address in (a["pointer"], a["ammo"]) for address in order[first_switch:]), order[first_switch:]
        assert "OWN BULLET ACTIVE: projectile row 276 -> NEW ID %d, damage row 108 -> 55" % new_id in status, status
        assert "[own rows] ready" in status and "assault_rifle: projectile id %d" % new_id in status
        # take it back: the game's memory is exactly as before (our own block stays, unused)
        status = rig.reload("")
        assert first_line(status) == "OK - no changes configured", first_line(status)
        after = snapshot(rig)
        assert all(after[base] == data for base, data in before.items())
        # asking again reuses the same id: no second allocation, no second row
        rig.reload(NEW_CONFIG)
        assert rig.mem.peek(a["pointer"], "<I") == new_id and len(rig.mem.allocs) == 1
    finally:
        rig.close()


def check_new_projectile_id_needs_a_proven_index(mutate=None):
    for world in ("wrong", "absent", "moved"):
        rig = Rig(NEW_CONFIG, mutate)
        try:
            a = own_addresses(rig)
            if world == "wrong":
                add_game_index(rig, wrong_id=200)                 # one id leads to another row
            elif world == "moved":
                add_game_index(rig, block=0x1EF00000000)          # pointers into a table that is not there
            status = rig.settle()
            assert rig.mem.peek(a["pointer"], "<I") == SRC_PROJECTILE, world
            assert rig.mem.peek(a["ammo"], "<I") == SRC_PROJECTILE, world
            assert "OWN BULLET WAITING" in status, (world, status[:1500])
            reason = "is not in memory yet" if world == "absent" else "does not lead to the rows of the table"
            assert reason in status, (world, status[:1500])
            assert first_line(status).startswith("PARTIAL"), first_line(status)
        finally:
            rig.close()


def check_new_projectile_id_only_on_a_verified_build(mutate=None):
    rig = Rig(NEW_CONFIG, mutate, wrong_build=True)
    try:
        add_game_index(rig)
        rig.settle()
        rig.game.frames(300)
        assert rig.mem.allocs == [] and rig.mem.writes == []
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
     "        sync_field(entry, nil)\n        if not entry.note or copies == 0 then applied[key] = nil",
     "        if not entry.note or copies == 0 then applied[key] = nil",
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
    ("own bullet: stats still go to the shared row",
     "            if own_bullet[item] then\n                local field, redirected = own_row_field(item, entry.field)",
     "            if false then\n                local field, redirected = own_row_field(item, entry.field)",
     check_own_bullet_gives_the_weapon_private_rows),
    ("own bullet: weapon switched although its rows are not in place",
     "            if ready[want.group] == false then\n                want.blocked = true",
     "            if false then\n                want.blocked = true",
     check_own_bullet_does_not_switch_onto_an_unexpected_row),
    ("own bullet: spare row overwritten without checking its content",
     "                    elseif field.exact and not copy.written and not same_value(field.storage, current, field.stock) then",
     "                    elseif false then",
     check_own_bullet_does_not_switch_onto_an_unexpected_row),
    ("own bullet: ammo attachment not redirected",
     "        if item.ammo_delta then\n            want(",
     "        if false then\n            want(",
     check_own_bullet_gives_the_weapon_private_rows),
    ("own bullet: new projectile keeps the shared damage row",
     "                if offset == patch_at then value = patch_value end",
     "",
     check_own_bullet_gives_the_weapon_private_rows),
    ("own bullet: rows restored before the weapon is switched back",
     "        if not desired[key] and entry.order == 2 then restore(key, entry) end",
     "",
     check_own_bullet_gives_the_weapon_private_rows),
    ("probe reads pages that are not in memory",
     "                    if usable[k] then\n                        local last = k",
     "                    if true then\n                        local last = k",
     check_probe_finds_pointer_arrays_and_writes_nothing),
    ("probe: a reference that straddles two reads is missed",
     "                local extra = (at + span < stop) and 3 or 0       -- a value may straddle two chunks",
     "                local extra = 0",
     check_probe_reads_the_module_that_holds_the_index),
    ("probe: relative reference measured from the wrong place",
     "            local target = rva + i + 4 + v",
     "            local target = rva + i + v",
     check_probe_reads_the_module_that_holds_the_index),
    ("probe: data is read as if it were code",
     "        if region.state == MEM_COMMIT and region.type == MEM_IMAGE and EXECUTE[region.protection] then",
     "        if region.state == MEM_COMMIT and region.type == MEM_IMAGE then",
     check_probe_reads_the_module_that_holds_the_index),
    ("probe: runs although a table is missing",
     "            probe.note = 'waiting for ' .. name .. ', which is not loaded yet'\n            return false",
     "            probe.note = 'waiting for ' .. name .. ', which is not loaded yet'",
     check_probe_waits_until_every_table_is_loaded),
    ("new id: weapon switched although the index is not proven",
     "            elseif want.needs_index and not index_ok then",
     "            elseif false then",
     check_new_projectile_id_needs_a_proven_index),
    ("new id: index accepted without comparing it with the table",
     "                    if id < 1 or id >= known.slots or A.words[2 * id + 1] ~= high\n"
     "                        or A.words[2 * id] ~= address - high * 4294967296 then",
     "                    if id < 1 or id >= known.slots then",
     check_new_projectile_id_needs_a_proven_index),
    ("new id: our row keeps the shared damage row",
     "        if offset == 0 then word = id elseif offset == OWN_DAMAGE_AT then word = damage end",
     "        if offset == 0 then word = id end",
     check_new_projectile_id_in_memory_of_our_own),
    ("new id: slot and id do not belong together",
     "    own.index, own.first_id, own.state = index, (address + OWN_SLOTS_AT - index) / 8, 'ready'",
     "    own.index, own.first_id, own.state = index, (address - index) / 8, 'ready'",
     check_new_projectile_id_in_memory_of_our_own),
    ("new id: stats still go to the shared projectile row",
     "        if t.fresh then\n            -- a row of our own starts as a copy of the weapon's round",
     "        if false then\n            -- a row of our own starts as a copy of the weapon's round",
     check_new_projectile_id_in_memory_of_our_own),
    ("reload key not debounced",
     "        if pressed_at - last_key_reload >= RELOAD_DEBOUNCE then",
     "        if true then",
     check_reload_key_is_debounced),
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
