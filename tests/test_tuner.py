# -*- coding: utf-8 -*-
"""Offline tests for the patch engine (src/tuner/tuner.lua).

    .venv\\Scripts\\python.exe -m unittest tests.test_tuner -v

Every scenario is a plain function `check_*(source)` that raises AssertionError when the
engine misbehaves. The unittest cases call them with the real source; the mutation test calls
them with a deliberately broken source and requires them to fail. A scenario that still
passes on a broken engine does not test what it claims.
"""
import hashlib
import json
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
SHARED_ROWS = "\n[settings]\nown_rows = off\nmenu_sections = open\n"   # (and the menu's headings start open)
OPEN_SECTIONS = "\n[settings]\nmenu_sections = open\n"
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

    def __init__(self, config, mutate=None, world=None, wrong_build=False, auto=False, closed=False, **game):
        """auto=False: the config gets `own_rows = off` appended, so that values go to the rows the weapons
        share (what the engine tests are about). auto=True: the config is used as written."""
        self.mem, self.info = harness.build_world(second_copy=False, **(world or {}))
        source = real_source(self.info)
        if wrong_build:
            source = harness.addon_source("tuner", data=data_for(self.info, exe=b"another build"))
        if mutate:
            old, new = mutate
            assert source.count(old) == 1, "mutation target not found exactly once: %r" % old[:60]
            source = source.replace(old, new)
        self.game = harness.Game(source, self.mem, self.info, global_name="BYOG",
                                 log_name="byog.log", config=config,
                                 config_suffix=("" if closed else OPEN_SECTIONS) if auto else SHARED_ROWS, **game)
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
        "ergonomics = fast",          # not a number
        "[weapon: no_such_gun]",
        "damage = 10",
        "[throwable: he_grenade]",
        "fuse = 61",                  # out of range
        ""])
    rig = Rig(config, mutate)
    try:
        status = rig.settle()
        assert first_line(status).startswith("PARTIAL - 0 values applied, 0 waiting for their table, 0 failed, 5 config lines rejected"), first_line(status)
        assert rig.mem.writes == [], rig.mem.writes
        assert "outside the allowed range 0 .. 100000" in status
        assert 'has no stat "nonsense"' in status
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
        assert sorted(x for x in api[b"categories"]().values()) == [b"armor", b"armor_passive", b"attachment", b"backpack", b"enemy_weapon", b"shield", b"status", b"stratagem", b"stratagem_weapon", b"throwable", b"unknown_weapon", b"vehicle", b"weapon"]
        stats = {s[b"id"]: s for s in api[b"stats"](b"weapon", b"assault_rifle").values()}
        assert stats[b"damage"][b"game"] == 90 and stats[b"damage"][b"shared_with"] == 6
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
        assert "  damage = 90   (0 .. 100000, whole numbers)   # shared with 6 other" in catalog, catalog[:600]
        assert "  capacity = 45   (1 .. 9999, whole numbers)   # value of the default attachment: another " \
               "attachment on the weapon replaces it; shared with 2 other" in catalog
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
    rig = Rig("[weapon: lmg_stalwart]\nown_bullet = true\ndamage = 100\n[weapon: assault_rifle]\nown_bullet = maybe\n"
                  "[weapon: laser_cannon]\nown_bullet = new\n", mutate)
    try:
        status = rig.settle()
        assert "own_bullet is not available for this weapon yet" in status      # a beam weapon: no projectile
        assert "own_bullet = true needs a spare row" in status                  # the Stalwart has none assigned
        assert "own_bullet takes true, false or new" in status
        assert rig.mem.peek(rig.damage, "<I") == 100              # the plain line still works (shared row)
        assert len(rig.mem.writes) == 1
    finally:
        rig.close()


ENGINE_BASE = 0x7FFD00000000


KNOWN_INDEXES = gen_tuner_data.INDEXES["release/01.007.101/19155"]
INDEX_RVA, INDEX_SLOTS = KNOWN_INDEXES["ProjectileSettings"]
NEW_CONFIG = "[weapon: assault_rifle]\nown_bullet = new\ndamage = 5000\nvelocity = 1200\n"
IMAGE_FROM, IMAGE_SIZE = 0x37C6000, 0x3000          # the pages of the fake game.dll that hold both indexes


def add_game_index(rig, wrong=None, block=None):
    """game.dll's id-indexed arrays of row pointers, in image pages the game has written to.

    wrong: (table, id): that id leads to the row of the next id (an index this version was not measured on).
    block: {table: block address} instead of the real ones (pointers into a table that is not there).
    -> {table: address of the slot of id 0}"""
    page = bytearray(IMAGE_SIZE)
    out = {}
    for name, (rva, slots) in KNOWN_INDEXES.items():
        t = hd2db.table(name)
        rows_at = ((block or {}).get(name) or rig.blocks[name][0]) + 24 + 16
        ids = t.by_id()
        assert max(ids) + 1 == slots and IMAGE_FROM <= rva and rva + slots * 8 <= IMAGE_FROM + IMAGE_SIZE
        for row_id, row in ids.items():
            if wrong == (name, row_id):
                row = ids[row_id + 1]
            struct.pack_into("<Q", page, rva - IMAGE_FROM + 8 * row_id, rows_at + row * t.stride)
        out[name] = rig.info["dll_base"] + rva
    region = rig.mem.add(rig.info["dll_base"] + IMAGE_FROM, bytes(page), mtype=harness.MEM_IMAGE,
                         allocation=rig.info["dll_base"])
    region["written"] = True
    return out


def in_game_dll(rig, address):
    return rig.info["dll_base"] <= address < rig.info["dll_base"] + IMAGE_FROM + IMAGE_SIZE


def check_new_row_ids_in_memory_of_our_own(mutate=None):
    rig = Rig(NEW_CONFIG, mutate)
    try:
        a = own_addresses(rig)
        index = add_game_index(rig)
        before = snapshot(rig)
        stock_projectile = row_bytes(rig, a["src_projectile"], 272)
        stock_damage = row_bytes(rig, a["src_damage"], 76)
        status = rig.settle()
        assert first_line(status) == "OK - 2 values applied, 1 weapons on their own bullet", status[:1500]
        # one allocation of our own, above game.dll
        assert len(rig.mem.allocs) == 1, rig.mem.allocs
        own_base, own_size = rig.mem.allocs[0]
        assert own_base > max(index.values()) and own_size == 0x20000
        # the weapon and its ammo attachment carry an id no real row has, and it fits 31 bits
        new_id = rig.mem.peek(a["pointer"], "<I")
        assert INDEX_SLOTS < new_id < 2 ** 31, new_id
        assert rig.mem.peek(a["ammo"], "<I") == new_id
        assert rig.mem.peek(a["stalwart"], "<I") == SRC_PROJECTILE
        # what the game does with that id: [index + id * 8] is a pointer to the row
        row = rig.mem.peek(index["ProjectileSettings"] + 8 * new_id, "<Q")
        assert own_base <= row and row + 272 <= own_base + own_size, hex(row)
        new_damage = rig.mem.peek(row + 60, "<I")
        assert KNOWN_INDEXES["DamageSettings"][1] < new_damage < 2 ** 31 and new_damage != new_id
        want = bytearray(stock_projectile)
        struct.pack_into("<I", want, 0, new_id)
        struct.pack_into("<I", want, 60, new_damage)
        struct.pack_into("<f", want, 32, 1200.0)
        assert row_bytes(rig, row, 272) == bytes(want)
        # and with the damage id of that row: [damage index + id * 8] is a pointer to a damage row of our own
        damage_row = rig.mem.peek(index["DamageSettings"] + 8 * new_damage, "<Q")
        assert own_base <= damage_row and damage_row + 76 <= own_base + own_size, hex(damage_row)
        assert not (row <= damage_row < row + 272)
        want = bytearray(stock_damage)
        struct.pack_into("<I", want, 0, new_damage)
        struct.pack_into("<i", want, 4, 5000)
        assert row_bytes(rig, damage_row, 76) == bytes(want)
        # no row of the game was touched (not even a spare one), and nothing inside game.dll was written
        game_writes = [address for address, _data in rig.mem.writes if not own_base <= address < own_base + own_size]
        assert sorted(set(game_writes)) == sorted({a["pointer"], a["ammo"]}), [hex(x) for x in game_writes]
        assert not [hex(address) for address in game_writes if in_game_dll(rig, address)]
        # the switches came last
        order = [address for address, _data in rig.mem.writes]
        first_switch = min(i for i, address in enumerate(order) if address in (a["pointer"], a["ammo"]))
        assert all(address in (a["pointer"], a["ammo"]) for address in order[first_switch:]), order[first_switch:]
        assert ("OWN BULLET ACTIVE: projectile row 276 -> NEW ID %d, damage row 108 -> NEW ID %d"
                % (new_id, new_damage)) in status, status
        assert "[own rows] ready" in status and "assault_rifle: ProjectileSettings id %d" % new_id in status
        assert "assault_rifle: DamageSettings id %d" % new_damage in status
        # take it back: the game's memory is exactly as before (our own block stays, unused)
        status = rig.reload("")
        assert first_line(status) == "OK - no changes configured", first_line(status)
        after = snapshot(rig)
        assert all(after[base] == data for base, data in before.items())
        # asking again reuses the same ids: no second allocation, no second row
        rig.reload(NEW_CONFIG)
        assert rig.mem.peek(a["pointer"], "<I") == new_id and len(rig.mem.allocs) == 1
    finally:
        rig.close()


def check_new_row_ids_for_several_weapons(mutate=None):
    stalwart = entity("primary_weapons/lmg_stalwart/lmg_stalwart")
    rig = Rig("[weapon: assault_rifle]\nown_bullet = new\ndamage = 150\n"
              "[weapon: lmg_stalwart]\nown_bullet = new\ndamage = 60\n"
              "[weapon: machinegun]\nown_bullet = true\n", mutate)
    try:
        index = add_game_index(rig)
        status = rig.settle()
        assert first_line(status) == ("PARTIAL - 2 values applied, 0 waiting for their table, 0 failed, "
                                      "1 config lines rejected"), status[:1500]
        assert "own_bullet = true needs a spare row" in status
        seen = {}
        for name, ent, damage in (("assault_rifle", LIBERATOR, 150), ("lmg_stalwart", stalwart, 60)):
            new_id = rig.mem.peek(rig.keyed_field("ProjectileWeaponComponentData", ent, 0), "<I")
            assert new_id > INDEX_SLOTS, (name, new_id)
            row = rig.mem.peek(index["ProjectileSettings"] + 8 * new_id, "<Q")
            damage_row = rig.mem.peek(index["DamageSettings"] + 8 * rig.mem.peek(row + 60, "<I"), "<Q")
            assert rig.mem.peek(damage_row + 4, "<i") == damage, (name, rig.mem.peek(damage_row + 4, "<i"))
            seen[name] = (new_id, row, damage_row)
        # two weapons that shared one round now have different rounds and different damage rows
        assert len({v[0] for v in seen.values()}) == 2 and len({v[2] for v in seen.values()}) == 2
        assert rig.mem.peek(rig.damage, "<I") == 90                    # the shared row of the game: untouched
    finally:
        rig.close()


def check_new_projectile_id_needs_a_proven_index(mutate=None):
    for world in ("wrong", "absent", "moved"):   # each breaks a different index, or both
        rig = Rig(NEW_CONFIG, mutate)
        try:
            a = own_addresses(rig)
            if world == "wrong":
                add_game_index(rig, wrong=("DamageSettings", 200))               # one id leads to another row
            elif world == "moved":
                add_game_index(rig, block={"ProjectileSettings": 0x1EF00000000})  # a table that is not there
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


def check_a_round_loaded_weapon_is_switched_where_it_takes_its_round_from(mutate=None):
    # seen in game (v1.1.17): the P-4 Senator got rows of its own, the status said so, and nothing changed. A
    # weapon that is loaded round by round fires what its ROUNDS record names; that still named the old row.
    senator = int(catalog_stat("revolver_pistol", "damage")[0]["entity"], 16)
    veto = int(catalog_stat("pistol_broomhandle", "damage")[0]["entity"], 16)
    rig = Rig("[weapon: revolver_pistol]\ndamage = 230\n[weapon: pistol_broomhandle]\ndamage = 110\n", mutate, auto=True)
    try:
        index = add_game_index(rig)
        status = rig.settle()
        assert first_line(status) == "OK - 2 values applied, 2 weapons on their own bullet", status[:1800]
        for ent, stock, wanted in ((senator, 309, 230), (veto, 237, 110)):
            in_rounds = rig.mem.peek(rig.keyed_field("WeaponRoundsComponentData", ent, 64), "<I")
            in_weapon = rig.mem.peek(rig.keyed_field("ProjectileWeaponComponentData", ent, 0), "<I")
            assert in_rounds == in_weapon and in_rounds > INDEX_SLOTS and in_rounds != stock, (in_rounds, in_weapon)
            row = rig.mem.peek(index["ProjectileSettings"] + 8 * in_rounds, "<Q")
            damage_row = rig.mem.peek(index["DamageSettings"] + 8 * rig.mem.peek(row + 60, "<I"), "<Q")
            assert rig.mem.peek(damage_row + 4, "<i") == wanted
        # and taken back: the rounds record names the game's row again
        status = rig.reload("")
        assert rig.mem.peek(rig.keyed_field("WeaponRoundsComponentData", senator, 64), "<I") == 309, status[:900]
        assert rig.mem.peek(rig.keyed_field("WeaponRoundsComponentData", veto, 64), "<I") == 237
    finally:
        rig.close()


def check_a_changed_weapon_gets_rows_of_its_own_by_itself(mutate=None):
    stalwart = entity("primary_weapons/lmg_stalwart/lmg_stalwart")
    rig = Rig(BASE_CONFIG, mutate, auto=True)                  # damage = 120, ap_bonus = +2, rpm = 150%
    try:
        a = own_addresses(rig)
        index = add_game_index(rig)
        status = rig.settle()
        assert first_line(status) == "OK - 3 values applied, 1 weapons on their own bullet", status[:1800]
        assert "rows of its own (automatic) -> OWN BULLET ACTIVE" in status

        def damage_of(ent):
            new_id = rig.mem.peek(rig.keyed_field("ProjectileWeaponComponentData", ent, 0), "<I")
            if new_id <= INDEX_SLOTS:
                return None
            row = rig.mem.peek(index["ProjectileSettings"] + 8 * new_id, "<Q")
            return rig.mem.peek(rig.mem.peek(index["DamageSettings"] + 8 * rig.mem.peek(row + 60, "<I"), "<Q") + 4, "<i")
        assert damage_of(LIBERATOR) == 120
        assert rig.mem.peek(rig.damage, "<I") == 90                # the row the Stalwart still uses
        assert damage_of(stalwart) is None
        assert rig.mem.peek(rig.rpm, "<f") == 960.0                # a value of the weapon itself: as before
        # two weapons that share a round may now have different values: no conflict any more
        status = rig.reload("[weapon: assault_rifle]\ndamage = 150\n[weapon: lmg_stalwart]\ndamage = 60\n")
        assert first_line(status) == "OK - 2 values applied, 2 weapons on their own bullet", status[:1800]
        assert damage_of(LIBERATOR) == 150 and damage_of(stalwart) == 60
        assert rig.mem.peek(rig.damage, "<I") == 90
        # own_bullet = false: this weapon keeps the shared row, as in the first versions
        status = rig.reload("[weapon: assault_rifle]\nown_bullet = false\ndamage = 150\n")
        assert rig.mem.peek(rig.damage, "<I") == 150, status[:1800]
        assert rig.mem.peek(a["pointer"], "<I") == SRC_PROJECTILE and rig.mem.peek(a["ammo"], "<I") == SRC_PROJECTILE
        assert "also affects" in status
        # a value that is not in the shared rows does not cost a row
        rows_before = status.count("ProjectileSettings id")
        status = rig.reload("[weapon: machinegun]\nrpm = 150%\n")
        assert "automatic" not in status and status.count("ProjectileSettings id") == rows_before, status[:1800]
    finally:
        rig.close()


_CATALOG = {}


def catalog_stat(weapon, stat):
    """-> (catalog item, stat entry) from the offline catalog, which the addon never sees."""
    if not _CATALOG:
        with open(os.path.join(ROOT, "data", "catalog.json"), encoding="utf-8") as f:
            for it in json.load(f)["items"]:
                _CATALOG.setdefault(it["path"].rsplit("/", 1)[-1], it)      # weapons and throwables come first
    it = _CATALOG[weapon]
    return it, next(s for s in it["stats"] if s.get("id") == stat)


def attachment_value(rig, weapon, stat):
    """-> (address of the value in the default attachment's delta, address in the weapon's own record)"""
    it, s = catalog_stat(weapon, stat)
    delta = rig.blocks["ComponentEntityDeltaStorage"][0] + 24 + s["default_attachment"]["delta_data_offset"]
    return delta, rig.keyed_field(s["table"], int(it["entity"], 16), s["offset"])


def check_magazine_values_live_in_the_default_attachment(mutate=None):
    config = "[weapon: assault_rifle]\ncapacity = 60\nmags_max = +2\n[weapon: standard_pistol]\nmagazine = 150%\n"
    rig = Rig(config, mutate)
    try:
        capacity, base_capacity = attachment_value(rig, "assault_rifle", "capacity")
        spare, base_spare = attachment_value(rig, "assault_rifle", "mags_max")
        pistol, base_pistol = attachment_value(rig, "standard_pistol", "capacity")
        before = [rig.mem.peek(a, "<I") for a in (capacity, spare, pistol, base_capacity, base_spare, base_pistol)]
        assert before == [45, 8, 15, 30, 12, 30], before
        status = rig.settle()
        assert first_line(status) == "OK - 3 values applied", status[:1500]
        # the attachment's values changed (percent and +N count from the value the game really uses) ...
        assert [rig.mem.peek(a, "<I") for a in (capacity, spare, pistol)] == [60, 10, 23]
        # ... and nothing else: not the weapons' own records, which the game overwrites anyway
        assert sorted(a for a, _d in rig.mem.writes) == sorted([capacity, spare, pistol]), \
            [hex(a) for a, _d in rig.mem.writes]
        assert [rig.mem.peek(a, "<I") for a in (base_capacity, base_spare, base_pistol)] == [30, 12, 30]
        line = next(x for x in status.split("\r\n") if x.startswith("  capacity: 45 -> 60"))
        assert "APPLIED" in line and "(value of the default attachment)" in line, line
        # the Liberator's magazine is also the default of two other rifles; the pistol's is its own
        assert "also affects: assault_rifle_ap.capacity, assault_rifle_whisper.capacity" in line, line
        line = next(x for x in status.split("\r\n") if x.startswith("  capacity: 15 -> 23"))
        assert "also affects" not in line, line
        # two weapons with the same magazine cannot ask for different values
        status = rig.reload("[weapon: assault_rifle]\ncapacity = 60\n[weapon: assault_rifle_ap]\ncapacity = 50\n")
        assert status.count("ask for different values of the same shared value") == 2, status[:1500]
        assert [rig.mem.peek(a, "<I") for a in (capacity, spare, pistol)] == [45, 8, 15]
        status = rig.reload("")
        assert [rig.mem.peek(a, "<I") for a in (capacity, spare, pistol)] == [45, 8, 15]
    finally:
        rig.close()


MAGAZINE_STATS = ("capacity", "mags_start", "mags_supply", "mags_max")


def magazine_addresses(rig, weapon):
    """-> ({stat: address in the weapon's own record}, {stat: address in the attachment's delta data},
    address of the count of the attachment's magazine deltas)"""
    import deltas
    it, capacity = catalog_stat(weapon, "capacity")
    own, attached = {}, {}
    for stat in MAGAZINE_STATS:
        attached[stat], own[stat] = attachment_value(rig, weapon, stat)
    attachment = capacity["default_attachment"]["item"]
    resource = next(int(a["delta_resource"], 16) for a in it["default_attachments"] if a["item"] == attachment)
    run = next(r for r, ci, _e in deltas.component_runs(resource) if ci == 5)
    count = rig.blocks["ComponentEntityDeltaStorage"][0] + 24 + deltas._load()["co"] + run * 12 + 8
    return own, attached, count


def values(rig, addresses):
    return [rig.mem.peek(addresses[stat], "<I") for stat in MAGAZINE_STATS]


def check_magazine_values_of_the_weapons_own(mutate=None):
    config = "[weapon: assault_rifle]\ncapacity = 100\nmags_max = 12\n[weapon: standard_pistol]\ncapacity = 150%\n"
    rig = Rig(config, mutate, auto=True)
    try:
        rifle, rifle_mag, rifle_switch = magazine_addresses(rig, "assault_rifle")
        other, other_mag, other_switch = magazine_addresses(rig, "assault_rifle_ap")
        third, _mag, _switch = magazine_addresses(rig, "assault_rifle_whisper")
        pistol, pistol_mag, pistol_switch = magazine_addresses(rig, "standard_pistol")
        assert other_switch == rifle_switch and pistol_switch != rifle_switch          # one magazine, three rifles
        before = snapshot(rig)
        assert values(rig, rifle) == [30, 6, 6, 12] and values(rig, rifle_mag) == [45, 6, 8, 8]
        assert rig.mem.peek(rifle_switch, "<I") == 4 and rig.mem.peek(pistol_switch, "<I") == 4
        status = rig.settle()
        assert first_line(status) == ("OK - 3 values applied, 2 magazines switched to the weapons' own values"), \
            status[:1500]
        # the Liberator's own record: the config's values, and the attachment's for what was not set
        assert values(rig, rifle) == [100, 6, 8, 12], values(rig, rifle)
        # the two other rifles with this magazine keep what the attachment gave them, now in their own records
        assert values(rig, other) == [45, 6, 8, 8] and values(rig, third) == [45, 6, 8, 8]
        assert values(rig, pistol) == [23, 5, 8, 8], values(rig, pistol)
        # the attachments' values are untouched, and their magazine deltas are switched off
        assert values(rig, rifle_mag) == [45, 6, 8, 8] and values(rig, pistol_mag) == [15, 5, 8, 8]
        assert rig.mem.peek(rifle_switch, "<I") == 0 and rig.mem.peek(pistol_switch, "<I") == 0
        # a switch is thrown only when every record of its magazine is in place
        order = [address for address, _data in rig.mem.writes]
        records = set(list(rifle.values()) + list(other.values()) + list(third.values()))
        assert order.index(rifle_switch) > max(i for i, a in enumerate(order) if a in records)
        line = next(x for x in status.split("\r\n") if x.startswith("  capacity: 45 -> 100"))
        assert "APPLIED" in line and "the magazine attachment's values are switched off)" in line, line
        assert "also affects" not in line, line
        # two rifles with the same magazine can now have different values
        status = rig.reload("[weapon: assault_rifle]\ncapacity = 60\nmags_start = 10\n"
                            "[weapon: assault_rifle_ap]\ncapacity = 50\nmags_start = 7\n")
        assert "REJECTED" not in status, status[:1500]
        assert values(rig, rifle) == [60, 10, 8, 8] and values(rig, other) == [50, 7, 8, 8]
        # seen in game: more magazines at the start than the maximum are capped by the game. Said, not "fixed".
        assert status.count("WARNING: mags_start") == 1, status[:2000]
        assert "WARNING: mags_start 10 is above mags_max 8: the game starts with 8. Set mags_max as well" in status
        assert values(rig, third) == [45, 6, 8, 8]
        assert rig.mem.peek(rifle_switch, "<I") == 0 and rig.mem.peek(pistol_switch, "<I") == 4
        assert values(rig, pistol) == [30, 6, 6, 12]
        # take it all back: the switch first, then the records
        writes_before = len(rig.mem.writes)
        status = rig.reload("")
        assert first_line(status) == "OK - no changes configured", first_line(status)
        assert rig.mem.writes[writes_before][0] == rifle_switch
        assert snapshot(rig) == before
    finally:
        rig.close()


BLAST_CONFIG = ("[weapon: grenade_launcher]\nblast_damage = 5000\nblast_inner_radius = 9\n"
                "[throwable: frag_grenade]\nblast_outer_radius = 30\n"
                "[throwable: arc_grenade]\nblast_damage = 7\n")
LIVE_WORDS = (40, 44, 48, 52)                # the array head inside an explosion row: addresses, only known in memory


def item_entity(name):
    return int(catalog_stat(name, "blast_inner_radius")[0]["entity"], 16)


def explosion_row(rig, row):
    return rig.row_field("ExplosionSettings", row, 0)


def check_explosions_of_their_own(mutate=None):
    import blasts
    pool = [row for row, _score, _why in blasts.pool()]
    rig = Rig(BLAST_CONFIG, mutate, auto=True)
    try:
        index = add_game_index(rig)
        launcher = rig.keyed_field("ProjectileWeaponComponentData", item_entity("grenade_launcher"), 0)
        frag = rig.keyed_field("ExplosiveComponentData", item_entity("frag_grenade"), 36)
        antitank = rig.keyed_field("ExplosiveComponentData", item_entity("antitank_grenade"), 36)
        # in memory the array heads are addresses that no offline data knows: make them differ from the file
        for n, row in enumerate((361, 257, pool[0], pool[1])):
            rig.mem.poke(explosion_row(rig, row) + 40, "<Q", 0x1E0AAAA0000 + n * 0x100)
        before = snapshot(rig)
        stock = {row: row_bytes(rig, explosion_row(rig, row), 152) for row in (361, 257, 157, pool[0], pool[1])}
        stock_damage = {row: row_bytes(rig, rig.row_field("DamageSettings", row, 0), 76) for row in (375, 335, 364)}
        assert rig.mem.peek(frag, "<I") == 257 and rig.mem.peek(antitank, "<I") == 257
        status = rig.settle()
        assert first_line(status) == ("OK - 4 values applied, 1 weapons on their own bullet, "
                                      "3 explosions of their own"), status[:2500]

        def own_damage(damage_id, source, value):
            assert KNOWN_INDEXES["DamageSettings"][1] < damage_id < 2 ** 31, damage_id
            at = rig.mem.peek(index["DamageSettings"] + 8 * damage_id, "<Q")
            want = bytearray(stock_damage[source])
            struct.pack_into("<I", want, 0, damage_id)
            if value is not None:
                struct.pack_into("<i", want, 4, value)
            assert row_bytes(rig, at, 76) == bytes(want), (source, damage_id)

        def borrowed(row, source, patches):
            """the borrowed row: the source row as it is in memory, with its own id, damage row and the new values"""
            got = row_bytes(rig, explosion_row(rig, row), 152)
            want = bytearray(stock[source])
            struct.pack_into("<I", want, 0, row)
            struct.pack_into("<I", want, 4, struct.unpack_from("<I", got, 4)[0])
            for offset, value in patches.items():
                struct.pack_into("<f", want, offset, value)
            assert got == bytes(want), (row, source)
            return struct.unpack_from("<I", got, 4)[0]

        # the launcher: a projectile row of its own, whose explosion is the first borrowed row
        new_projectile = rig.mem.peek(launcher, "<I")
        assert new_projectile > INDEX_SLOTS
        own_projectile = rig.mem.peek(index["ProjectileSettings"] + 8 * new_projectile, "<Q")
        assert rig.mem.peek(own_projectile + 144, "<I") == pool[0] and rig.mem.peek(own_projectile + 156, "<I") == pool[0]
        own_damage(borrowed(pool[0], 361, {16: 9.0}), 375, 5000)
        # the grenade: its component points at the second borrowed row; the other grenade with that explosion does not
        assert rig.mem.peek(frag, "<I") == pool[1] and rig.mem.peek(antitank, "<I") == 257
        own_damage(borrowed(pool[1], 257, {20: 30.0}), 335, None)
        # the arc grenade's explosion row is its own: only its damage row id changes
        arc = bytearray(stock[157])
        arc_damage = rig.mem.peek(explosion_row(rig, 157) + 4, "<I")
        struct.pack_into("<I", arc, 4, arc_damage)
        assert row_bytes(rig, explosion_row(rig, 157), 152) == bytes(arc)
        own_damage(arc_damage, 364, 7)
        assert len({arc_damage, rig.mem.peek(explosion_row(rig, pool[0]) + 4, "<I"),
                    rig.mem.peek(explosion_row(rig, pool[1]) + 4, "<I")}) == 3
        # what the other users of these explosions see is untouched
        for row in (361, 257):
            assert row_bytes(rig, explosion_row(rig, row), 152) == stock[row], row
        for row in (375, 335, 364):
            assert row_bytes(rig, rig.row_field("DamageSettings", row, 0), 76) == stock_damage[row], row
        # a switch is thrown only when its borrowed row is complete
        order = [address for address, _data in rig.mem.writes]
        last_copy = max(i for i, a in enumerate(order) if explosion_row(rig, pool[1]) <= a < explosion_row(rig, pool[1]) + 152)
        assert order.index(frag) > last_copy
        assert "OWN EXPLOSION ACTIVE: explosion row 361 -> borrowed row %d, damage row 375 -> NEW ID" % pool[0] in status
        assert "OWN EXPLOSION ACTIVE: explosion row 157 is its own, damage row 364 -> NEW ID %d" % arc_damage in status
        assert "blast_damage: 400 -> 5000 (own row)  APPLIED" in status, status[:2500]
        assert "frag_grenade:257: ExplosionSettings row %d (as a copy of row 257)" % pool[1] in status
        # take it all back: the game's memory is exactly as before
        writes_before = len(rig.mem.writes)
        status = rig.reload("")
        assert first_line(status) == "OK - no changes configured", first_line(status)
        restore = [address for address, _data in rig.mem.writes[writes_before:]]
        assert restore.index(frag) < min(i for i, a in enumerate(restore)
                                         if explosion_row(rig, pool[1]) <= a < explosion_row(rig, pool[1]) + 152)
        after = snapshot(rig)
        assert all(after[base] == data for base, data in before.items())
    finally:
        rig.close()


def check_explosion_of_its_own_waits_for_a_proven_index(mutate=None):
    rig = Rig("[throwable: arc_grenade]\nblast_damage = 7\n", mutate, auto=True)
    try:
        status = rig.settle()                               # no index in this world: a new damage id must not be used
        assert rig.mem.peek(explosion_row(rig, 157) + 4, "<I") == 364
        assert "OWN EXPLOSION WAITING" in status and "is not in memory yet" in status, status[:2000]
        assert rig.mem.peek(rig.row_field("DamageSettings", 364, 4), "<i") != 7
    finally:
        rig.close()


def stratagem_in_the_fake_world(rig):
    """A stratagem that is both in the list read in game and in the synthetic tables of the fake world.
    -> (config name, address of its row, cooldown, uses)"""
    import build_catalog
    rows = {}
    for block in rig.blocks["StratagemSettings"]:
        count = rig.mem.peek(block + 24 + 8, "<Q")
        for n in range(count):
            at = block + 24 + 16 + n * 400
            rows[rig.mem.peek(at + 4, "<I")] = at
    assert len(rig.blocks["StratagemSettings"]) > 1                    # the table is split into groups
    for item in build_catalog.live_stratagems():
        row_id = int(item["entity"], 16)
        cooldown = next(s["original"] for s in item["stats"] if s["id"] == "cooldown")
        uses = next(s["original"] for s in item["stats"] if s["id"] == "uses")
        at = rows.get(row_id)
        # not in the first group, with a cooldown the fixture agrees on
        if at and at > rig.blocks["StratagemSettings"][1] and cooldown >= 60 and rig.mem.peek(at + 104, "<f") == cooldown \
                and rig.mem.peek(at + 80, "<I") == uses:
            return item["path"].rsplit("/", 1)[-1], at, cooldown, uses
    raise AssertionError("no common stratagem")


def check_stratagems_backpacks_shields_and_vehicles(mutate=None):
    probe = Rig("", None)
    name, _at, cooldown, _uses = stratagem_in_the_fake_world(probe)
    probe.close()
    config = ("[stratagem: %s]\ncooldown = 50%%\nuses = 5\n"
              "[backpack: recoilless_rifle_backpack]\ncharges = 10\ncharges_start = 4\n"
              "[shield: energy_shield_backpack]\nshield_health = 300\nshield_broken_delay = 1\n"
              "[vehicle: combat_walker]\nhealth = 200%%\narmor = 6\npart_leg_left_health = 2000\n"
              "part_leg_left_armor = 5\n") % name
    rig = Rig(config, mutate)
    try:
        _name, row, cooldown, uses = stratagem_in_the_fake_world(rig)
        backpack = rig.keyed_field("DepositComponentData",
                                   entity("backpacks/recoilless_rifle_backpack/recoilless_rifle_backpack"), 0)
        shield = rig.keyed_field("ShieldComponentData",
                                 entity("backpacks/energy_shield_backpack/energy_shield_backpack"), 76)
        walker = rig.keyed_field("HealthComponentData",
                                 murmur64a(b"content/fac_helldivers/vehicles/combat_walker/combat_walker"), 0)
        before = snapshot(rig)
        assert rig.mem.peek(backpack, "<I") == 5 and rig.mem.peek(backpack + 4, "<i") == -1
        assert rig.mem.peek(shield, "<f") == 150.0 and rig.mem.peek(walker, "<i") == 1800
        assert rig.mem.peek(shield + 16, "<f") == 12.0 and rig.mem.peek(walker + 280, "<I") == 4
        status = rig.settle()
        assert first_line(status) == "OK - 10 values applied", status[:2000]
        # a part of the vehicle: its own health and armor, somewhere inside the 22 KB health record
        leg = walker + catalog_stat("combat_walker", "part_leg_left_health")[1]["offset"]
        leg_armor = walker + catalog_stat("combat_walker", "part_leg_left_armor")[1]["offset"]
        assert leg - walker > 520 and leg_armor == leg - 16
        assert rig.mem.peek(leg, "<i") == 2000 and rig.mem.peek(leg_armor, "<I") == 5
        other_leg = walker + catalog_stat("combat_walker", "part_leg_right_health")[1]["offset"]
        assert rig.mem.peek(other_leg, "<i") == 550
        assert rig.mem.peek(row + 104, "<f") == cooldown / 2 and rig.mem.peek(row + 80, "<I") == 5
        assert rig.mem.peek(shield + 16, "<f") == 1.0 and rig.mem.peek(walker + 280, "<I") == 6
        assert rig.mem.peek(backpack, "<I") == 10 and rig.mem.peek(backpack + 4, "<i") == 4
        assert rig.mem.peek(shield, "<f") == 300.0 and rig.mem.peek(walker, "<i") == 3600
        assert sorted(a for a, _d in rig.mem.writes) == sorted([row + 104, row + 80, backpack, backpack + 4,
                                                                shield, shield + 16, walker, walker + 280,
                                                                leg, leg_armor])
        assert "also affects" not in status and "WARNING" not in status
        # seen in game: a part with more health than the main health can pay for never breaks. Said, not "fixed".
        status = rig.reload("[vehicle: combat_walker]\npart_leg_right_health = 100000\n")
        assert ("WARNING: part leg_right has 100000 health and passes 100% of its damage on, the main health is 1800"
                in status), status[:2000]
        assert rig.mem.peek(other_leg, "<i") == 100000 and rig.mem.peek(walker, "<i") == 1800
        # a line that names one value wins over the shortcut that also covers it (in game the two rejected each other)
        status = rig.reload("[vehicle: combat_walker]\nall_health = 300%\npart_leg_left_health = 10\n"
                            "part_leg_right_health = 100000\n")
        assert "REJECTED" not in status, status[:2000]
        assert rig.mem.peek(walker, "<i") == 5400 and rig.mem.peek(leg, "<i") == 10
        assert rig.mem.peek(other_leg, "<i") == 100000
        assert "(set by their own lines instead: " in status and "part_leg_left_health (line 3)" in status
        assert "WARNING: part leg_right has 100000 health and passes 100% of its damage on, the main health is 5400" in status
        assert "call_in_time" not in rig.game.read_out("catalog.txt")
        status = rig.reload("[vehicle: combat_walker]\nhealth = 500\n")
        assert "WARNING: part leg_right has 550 health" in status or "WARNING: part leg_left has 550 health" in status
        # everything together keeps the game's relations; and the share a part passes on is a value of its own
        share = walker + catalog_stat("combat_walker", "part_leg_left_to_main")[1]["offset"]
        status = rig.reload("[vehicle: combat_walker]\nall_health = 200%\npart_leg_left_to_main = 0.5\n"
                            "durable_resistance = 0.5\n")
        assert "WARNING" not in status and "REJECTED" not in status, status[:2000]
        assert rig.mem.peek(walker, "<i") == 3600 and rig.mem.peek(leg, "<i") == 1100
        assert rig.mem.peek(other_leg, "<i") == 1100 and rig.mem.peek(share, "<f") == 0.5
        assert rig.mem.peek(walker + 268, "<f") == 0.5
        status = rig.reload("")
        assert snapshot(rig) == before
        catalog = rig.game.read_out("catalog.txt")
        assert "  shield_recharge_rate = 150   (0 .. 1000000)" in catalog and "shield_value_" not in catalog
        assert "  part_leg_left_to_main = 1   (0 .. 10)" in catalog and "  constitution = 2000   (" in catalog
        for header in ("[stratagem: %s]" % name, "[backpack: recoilless_rifle_backpack]",
                       "[shield: energy_shield_backpack]", "[vehicle: combat_walker]"):
            assert header in catalog, header
        assert "  charges_start = -1   (-1 .. 9999, whole numbers)" in catalog
    finally:
        rig.close()


SENTRY_GUN = 0x37CDE43876BA26BB              # the machine gun sentry's gun: fires the MG-43's round (148)


def check_stratagem_weapons_and_blast_from(mutate=None):
    gas = catalog_stat("gas_grenade", "blast_inner_radius")[1]["key"]
    config = ("[stratagem_weapon: orbital_precision_strike]\ndamage = 5000\n"
              "[stratagem_weapon: turret_machinegun_gpmg]\ndamage = 200\n"
              "[weapon: grenade_launcher]\nblast_from = gas_grenade\n"
              "[throwable: frag_grenade]\nblast_from = gas_grenade\n")
    rig = Rig(config, mutate, auto=True)
    try:
        index = add_game_index(rig)
        P = hd2db.table("ProjectileSettings")
        shell_damage = struct.unpack_from("<I", P.record(P.by_id()[100]), 60)[0]
        orbital = rig.row_field("DamageSettings", shell_damage, 4)
        sentry = rig.keyed_field("ProjectileWeaponComponentData", SENTRY_GUN, 0)
        hand_gun = rig.keyed_field("ProjectileWeaponComponentData", item_entity_of("machinegun"), 0)
        launcher = rig.keyed_field("ProjectileWeaponComponentData", item_entity("grenade_launcher"), 0)
        frag = rig.keyed_field("ExplosiveComponentData", item_entity("frag_grenade"), 36)
        before = snapshot(rig)
        assert rig.mem.peek(sentry, "<I") == 148 and rig.mem.peek(hand_gun, "<I") == 148 and rig.mem.peek(frag, "<I") == 257
        status = rig.settle()
        assert first_line(status) == "OK - 4 values applied, 3 weapons on their own bullet", status[:2500]
        # an orbital shell: the strike's own component names a new round, whose damage row is its own
        strike = rig.keyed_field("BombardmentComponentData",
                                 int(catalog_stat("orbital_precision_strike", "damage")[0]["entity"], 16), 64)
        shell = rig.mem.peek(strike, "<I")
        assert shell > INDEX_SLOTS and rig.mem.peek(orbital, "<i") == 4000          # the shared row: untouched
        shell_row = rig.mem.peek(index["ProjectileSettings"] + 8 * shell, "<Q")
        shell_damage_row = rig.mem.peek(index["DamageSettings"] + 8 * rig.mem.peek(shell_row + 60, "<I"), "<Q")
        assert rig.mem.peek(shell_damage_row + 4, "<i") == 5000
        # the sentry's gun gets rows of its own: the MG-43 in a diver's hands keeps the stock round
        new_id = rig.mem.peek(sentry, "<I")
        assert new_id > INDEX_SLOTS and rig.mem.peek(hand_gun, "<I") == 148
        row = rig.mem.peek(index["ProjectileSettings"] + 8 * new_id, "<Q")
        damage_row = rig.mem.peek(index["DamageSettings"] + 8 * rig.mem.peek(row + 60, "<I"), "<Q")
        assert rig.mem.peek(damage_row + 4, "<i") == 200 and rig.mem.peek(rig.row_field("DamageSettings", 125, 4), "<i") == 90
        # seen in game (v0.13.0): the sentry takes its rounds from the magazine's belt pattern, not from the
        # weapon record. Every entry of the pattern is switched; the tracer gets a row of its own on the
        # same damage row, so every round of the belt does the new damage.
        belt = rig.keyed_field("WeaponMagazineComponentData", SENTRY_GUN, 0)
        assert [rig.mem.peek(belt + o, "<I") for o in (4, 8, 12, 16)] == [new_id] * 4
        tracer = rig.mem.peek(belt + 20, "<I")
        assert tracer > INDEX_SLOTS and tracer != new_id
        tracer_row = rig.mem.peek(index["ProjectileSettings"] + 8 * tracer, "<Q")
        assert rig.mem.peek(tracer_row + 60, "<I") == rig.mem.peek(row + 60, "<I")
        stock_tracer = bytearray(row_bytes(rig, rig.row_field("ProjectileSettings", 242, 0), 272))
        struct.pack_into("<I", stock_tracer, 0, tracer)
        struct.pack_into("<I", stock_tracer, 60, rig.mem.peek(row + 60, "<I"))
        assert row_bytes(rig, tracer_row, 272) == bytes(stock_tracer)
        hand_belt = rig.keyed_field("WeaponMagazineComponentData", item_entity_of("machinegun"), 0)
        assert [rig.mem.peek(hand_belt + o, "<I") for o in (4, 8, 12, 16, 20)] == [148, 148, 148, 148, 242]
        # the launcher explodes like a gas grenade: the id is in ITS projectile row, on impact only
        own = rig.mem.peek(index["ProjectileSettings"] + 8 * rig.mem.peek(launcher, "<I"), "<Q")
        assert rig.mem.peek(own + 144, "<I") == gas and rig.mem.peek(own + 156, "<I") == 361
        assert rig.mem.peek(rig.row_field("ProjectileSettings", 280, 144), "<I") == 361      # the shared round: untouched
        assert rig.mem.peek(frag, "<I") == gas
        assert "blast_from: explosion row 361 -> gas_grenade (explosion row %d)" % gas in status, status[:2500]
        status = rig.reload("[weapon: grenade_launcher]\nblast_from = assault_rifle\n")
        assert "blast_from takes the name of an item that explodes" in status
        status = rig.reload("")
        after = snapshot(rig)
        assert all(after[base] == data for base, data in before.items())
        catalog = rig.game.read_out("catalog.txt")
        assert "[stratagem_weapon: turret_machinegun_gpmg]" in catalog and "  blast_from = <item>" in catalog
    finally:
        rig.close()


def item_entity_of(name):
    return int(catalog_stat(name, "damage")[0]["entity"], 16)


def check_research_settings_of_the_test_builds_do_nothing(mutate=None):
    # the probe, census, canary and globals dump of the test builds are gone; a config that still names them
    # is not a problem and nothing of theirs happens
    rig = Rig("[settings]\nui_probe = text\nprobe = true\ncensus = true\ncanary = true\ndump_globals = true\n"
              "[weapon: assault_rifle]\nrpm = 150%\n", mutate)
    try:
        rig.game.lua.execute(FAKE_ENGINE)
        status = rig.settle()
        rig.game.frames(50)
        assert first_line(status) == "OK - 1 values applied" and "config problem" not in status, status[:600]
        assert drawn(rig) == ("", 0)
        for name in ("UIPROBE.txt", "PROBE.txt", "CENSUS.txt", "GLOBALS.txt"):
            assert rig.game.read_out(name) == "", name
        assert rig.mem.peek(explosion_row(rig, 258) + 16, "<f") != rig.mem.peek(explosion_row(rig, 28) + 16, "<f")
    finally:
        rig.close()


# a stand-in for the engine's Gui: records what the menu draws
FAKE_ENGINE = b"""
stingray = { drawn = { rects = 0, texts = {} },
  Application = { main_world = function() return 'world' end,
                  back_buffer_size = function(...) if select('#', ...) > 0 then stingray.drawn.crashed = true end
                                                   return 2560, 1440 end },
  World = { create_screen_gui = function(world, mode) return 'gui' end,
            destroy_gui = function(world, gui) stingray.drawn.destroyed = true end },
  Vector2 = function(x, y) return { x, y } end,
  Vector3 = function(x, y, z) return { x, y, z } end,
  Color = function(a, r, g, b) return { a, r, g, b } end }
stingray.Gui = {
  -- the real one takes a viewport and a window: handed a gui it closed the game (v0.15.0)
  resolution = function(gui) stingray.drawn.crashed = true return 1920, 1080 end,
  rect = function(gui, position, size, color)
    stingray.drawn.rects = stingray.drawn.rects + 1
    if size[1] > (stingray.drawn.panel and stingray.drawn.panel[3] or 0) then
      stingray.drawn.panel = { position[1], position[2], size[1], size[2] }
    end
    stingray.drawn.top_rect = math.max(stingray.drawn.top_rect or 0, position[3] or 0)
  end,
  text = function(gui, str, font, size, material, position, color)
    stingray.drawn.texts[#stingray.drawn.texts + 1] = str
    if str ~= ' ' then stingray.drawn.font, stingray.drawn.material = font, material end
    if str ~= ' ' then          -- (a single blank is the menu trying out a font)
      stingray.drawn.low_text = math.min(stingray.drawn.low_text or 1e9, position[3] or 0)
    end
  end }
"""
F9, UP, DOWN, LEFT, RIGHT, TAB, DELETE = 0x78, 0x26, 0x28, 0x25, 0x27, 0x09, 0x2E


def menu_order(*categories):
    """The items of a menu tab in the order the menu shows them: by the game's name where one is known."""
    shown = {}
    with open(os.path.join(ROOT, "tools", "display_names.txt"), encoding="utf-8") as f:
        for line in f:
            if not line.startswith("#") and line.count("|") == 2:
                _c, name, label = line.rstrip("\n").split("|")
                shown[name] = label
    hidden = set()
    with open(os.path.join(ROOT, "tools", "hidden_items.txt"), encoding="utf-8") as f:
        for line in f:
            if not line.startswith("#") and line.count("|") == 2:
                hidden.add(line.split("|")[1])
    names = [it["path"].rsplit("/", 1)[-1] for it in _CATALOG.values() if it["category"] in categories]
    names = [n for n in names if n not in hidden]
    return sorted(names, key=lambda n: shown.get(n, n).lower())


def drawn(rig):
    """-> (text drawn since the last call, rectangles since the last call)"""
    text = rig.game.lua.eval(b"table.concat(stingray.drawn.texts, '\\n')").decode()
    rects = rig.game.lua.eval(b"stingray.drawn.rects")
    rig.game.lua.execute(b"stingray.drawn.texts = {}; stingray.drawn.rects = 0")
    return text, rects


def check_menu_changes_a_value_and_remembers_it(mutate=None):
    rig = Rig("", mutate)
    try:
        rig.settle()
        rig.game.lua.execute(FAKE_ENGINE)
        rig.game.frames(5)
        assert drawn(rig) == ("", 0)                                   # closed: nothing is drawn
        rig.game.press(F9)
        text, rects = drawn(rig)
        assert "BALANCE YOUR OWN GAME" in text and "AR-23 Liberator" in text and rects > 0, text[:300]
        # seen in game (v0.15.1): drawn without layers, the panel and the bars covered the text
        assert rig.game.lua.eval(b"stingray.drawn.low_text") > rig.game.lua.eval(b"stingray.drawn.top_rect") >= 901
        # in the middle of a 1920 x 1080 screen (the Gui's origin is the bottom left corner)
        panel = [rig.game.lua.eval(b"stingray.drawn.panel[%d]" % n) for n in (1, 2, 3, 4)]
        scale = 1440 / 1080                                            # the fake screen is 2560 x 1440
        want = [(2560 - 1180 * scale) / 2, (1440 - 726 * scale) / 2, 1180 * scale, 726 * scale]
        assert all(abs(a - b) < 0.01 for a, b in zip(panel, want)), (panel, want)
        assert rig.game.lua.eval(b"stingray.drawn.crashed") is None    # no engine call with arguments it does not take
        log = rig.game.read_out("byog.log")
        assert "menu: about to use World.create_screen_gui" in log and "menu: first frame drawn" in log
        assert "menu: screen 2560 x 1440" in log
        # walk to the Liberator, then to its values
        names = menu_order("primary", "secondary", "support", "melee")
        for _ in range(names.index("assault_rifle")):
            rig.game.press(DOWN)
        rig.game.press(TAB)
        # the values come in groups under headings: damage first, then what the hit applies, then the round ...
        text, _rects = drawn(rig)
        order = [text.index("\n[-] " + heading + "\n") for heading in ("DAMAGE", "STATUS EFFECTS")]
        assert order == sorted(order) and text.index("\nDamage\n") < text.index("\nStatus effect 1: type\n"), text[:900]
        assert "\nArmor penetration, direct hit\n" in text and "\nap_direct\n" not in text   # by a readable name
        assert "ap_bonus   (name in config.txt)" in text               # and the name config.txt takes, under the list
        assert "\nFire rate (rpm)\n" not in text                      # further down: the list scrolls
        stats = [s["id"] for s in catalog_stat("assault_rifle", "rpm")[0]["stats"] if s["id"] != "mode"]
        ahead = [s for s in stats if s in ("damage", "durable_damage", "ap_direct", "ap_slight", "ap_large", "ap_extreme",
                                           "demolition", "stagger", "push", "ap_bonus", "durable_ap_bonus", "bonus2",
                                           "durable_bonus2", "pellets", "velocity", "mass", "calibre", "drag", "gravity",
                                           "life_time", "penetration_slowdown", "arming_distance", "speed_multiplier")
                 or s.startswith("status")]
        for _ in ahead:                                                # walk down to the first value under FIRE
            rig.game.press(DOWN)
        text = shown(rig)                                              # (the row before it: what the weapon explodes like)
        assert "\n[-] EXPLOSION\n" in text and "\nExplodes like\n" in text and "\nits own\n" in text, text[:900]
        rig.game.press(DOWN)
        drawn(rig)
        rig.game.frames(2)
        text, _rects = drawn(rig)
        assert "\n[-] FIRE\n" in text and "\nFire rate (rpm)\n" in text and "\n[-] AMMO\n" in text, text[:900]
        assert "rpm   (name in config.txt)" in text
        rig.game.press(RIGHT)
        rig.game.frames(40)                                            # quiet for a moment: handed to the engine
        assert rig.mem.peek(rig.rpm, "<f") == 650.0
        saved = rig.game.read_out("presets/Default.txt")
        assert "[weapon: assault_rifle]" in saved and "rpm = 650" in saved, saved
        assert 'preset "Default": 1 values set through the in-game menu' in rig.game.status()
        text = shown(rig)
        assert 'Saved to "Default"' in text
        assert "650" in text and "640" in text                        # the new value and the game's
        assert "assault_rifle   (name in config.txt)" in text
        rig.game.press(DELETE)
        rig.game.frames(40)
        assert rig.mem.peek(rig.rpm, "<f") == 640.0 and "rpm" not in rig.game.read_out("presets/Default.txt")
        # another category, and closing
        rig.game.press(TAB)
        rig.game.press(RIGHT)
        assert "G-4 Gas" in drawn(rig)[0]
        rig.game.press(F9)
        rig.game.frames(5)
        drawn(rig)
        rig.game.frames(5)
        assert drawn(rig) == ("", 0) and rig.game.lua.eval(b"stingray.drawn.destroyed") is True
    finally:
        rig.close()


def check_menu_values_are_read_at_start(mutate=None):
    rig = Rig("[weapon: assault_rifle]\nrpm = 150%\n", mutate)
    try:
        with open(rig.game.out_path("menu.txt"), "wb") as f:
            f.write(b"# Written by the in-game menu.\r\n\r\n[weapon: assault_rifle]\r\nrpm = 700\r\n")
        status = rig.settle()
        assert rig.mem.peek(rig.rpm, "<f") == 700.0, status[:900]      # the menu's value wins over config.txt
    finally:
        rig.close()


def check_tables_are_found_when_their_first_page_is_not_in_memory(mutate=None):
    # seen in game: the system takes pages the game has not touched out of the working set; when that
    # was the first page of a chain of tables, the engine waited for those tables for a whole mission
    rig = Rig(BASE_CONFIG, mutate)
    try:
        for base in (0x1E000000000, 0x1E100000000):
            rig.mem.find(base)["absent"].add(0)
        status = rig.settle()
        assert first_line(status) == "OK - 3 values applied", status[:900]
        assert rig.mem.peek(rig.damage, "<I") == 120 and rig.mem.peek(rig.rpm, "<f") == 960.0
    finally:
        rig.close()


MENU_BEFORE_FIRE = ("damage", "durable_damage", "ap_direct", "ap_slight", "ap_large", "ap_extreme", "demolition",
                    "stagger", "push", "ap_bonus", "durable_ap_bonus", "bonus2", "durable_bonus2", "pellets", "velocity",
                    "mass", "calibre", "drag", "gravity", "life_time", "penetration_slowdown", "arming_distance",
                    "speed_multiplier")


def check_menu_stays_inside_the_range(mutate=None):
    rig = Rig("", mutate)
    try:
        with open(rig.game.out_path("menu.txt"), "wb") as f:
            f.write(b"[weapon: assault_rifle]\r\nrpm = 5999\r\n")
        rig.settle()
        rig.game.lua.execute(FAKE_ENGINE)
        rig.game.press(F9)
        names = menu_order("primary", "secondary", "support", "melee")
        for _ in range(names.index("assault_rifle")):
            rig.game.press(DOWN)
        rig.game.press(TAB)
        stats = [s["id"] for s in catalog_stat("assault_rifle", "rpm")[0]["stats"] if s["id"] != "mode"]
        for _ in range(sum(1 for s in stats if s != "rpm" and (s.startswith("status") or s in MENU_BEFORE_FIRE))):
            rig.game.press(DOWN)
        rig.game.press(DOWN)                                           # (the row "explodes like")
        rig.game.press(RIGHT)                                          # 5999 + 10 would leave 1 .. 6000
        rig.game.frames(40)
        assert rig.mem.peek(rig.rpm, "<f") == 6000.0 and "REJECTED" not in rig.game.status()
    finally:
        rig.close()


def check_menu_search_finds_items_of_every_category(mutate=None):
    rig = Rig("", mutate)
    try:
        rig.settle()
        rig.game.lua.execute(FAKE_ENGINE)
        rig.game.press(F9)
        drawn(rig)
        rig.game.press(F3)
        for key in b"SENTRY":                                          # typed on the keyboard
            rig.game.press(key)
        rig.game.frames(3)
        drawn(rig)
        rig.game.frames(2)
        text, _rects = drawn(rig)
        assert "search: sentry_" in text, text[:400]
        assert "A/G-16 Gatling Sentry  [strat. weapon]" in text and "A/MG-43 Machine Gun Sent" in text, text[:900]
        assert "AR-23 Liberator" not in text                           # the weapon tab is no longer what is listed
        rig.game.press(BACKSPACE)
        assert "search: sentr_" in shown(rig)
        rig.game.press(INSERT)                                         # out of the box, the hits stay
        # the first hit is selected: its values are on the right, and can be changed
        rig.game.press(TAB)
        rig.game.frames(2)
        assert "(name in config.txt)" in drawn(rig)[0]
        rig.game.press(TAB)
        rig.game.press(END)                                            # drops the search
        text = shown(rig)
        assert "press ENTER / F3 to search" in text and "AR-23 Liberator" in text
    finally:
        rig.close()


def check_more_ammunition_than_a_resupply_fills_is_said(mutate=None):
    # seen in game: the minigun started with 1500 rounds, a resupply filled it to 1023 only
    rig = Rig("[backpack: minigun_backpack]\ncharges = 150%\ncharges_start = 150%\n"
              "[backpack: recoilless_rifle_backpack]\ncharges = 150%\n", mutate)
    try:
        status = rig.settle()
        assert first_line(status) == "OK - 3 values applied", status[:900]
        pack = rig.keyed_field("DepositComponentData", entity("backpacks/minigun_backpack/minigun_backpack"), 0)
        assert rig.mem.peek(pack, "<I") == 1500 and rig.mem.peek(pack + 4, "<i") == 1500      # written as asked
        assert status.count("WARNING") == 1, status[:1500]
        assert ("WARNING: charges 1500 is above 1023: the game starts with 1500, but a resupply fills up to 1023 at most"
                in status)
        # and the menu says it where the value is
        rig.game.lua.execute(FAKE_ENGINE)
        rig.game.press(F9)
        rig.game.press(F3)
        for key in b"MINIGUN B":                                       # a space where the internal name has '_'
            rig.game.press(key)
        rig.game.press(INSERT)
        rig.game.press(TAB)
        drawn(rig)
        rig.game.frames(2)
        assert "! charges 1500 is above 1023" in drawn(rig)[0]
    finally:
        rig.close()


F3, F6, F7, INSERT, END, BACKSPACE, ENTER, ESCAPE = 0x72, 0x75, 0x76, 0x2D, 0x23, 0x08, 0x0D, 0x1B


def typed(rig, keys):
    for key in keys:
        rig.game.press(key)


def shown(rig):
    """What the menu draws now (the frames before are dropped)."""
    drawn(rig)
    rig.game.frames(2)
    return drawn(rig)[0]


def check_keys_go_to_the_box_only(mutate=None):
    rig = Rig("", mutate)
    try:
        rig.settle()
        rig.game.lua.execute(FAKE_ENGINE)
        rig.game.press(F9)
        typed(rig, b"S")                                               # a letter alone does nothing any more
        text = shown(rig)
        assert "search: " not in text and "press ENTER / F3 to search" in text, text[:400]
        rig.game.press(INSERT)                                         # seen in game: this is what testers press
        typed(rig, b"S")
        assert "search: s_" in shown(rig)
        rig.game.press(END)
        assert "search: " not in shown(rig)
        rig.game.press(ENTER)                                          # the same with the keys every keyboard has
        typed(rig, b"S")
        assert "search: s_" in shown(rig)
        rig.game.press(ESCAPE)
        assert "search: " not in shown(rig)
        rig.game.press(F3)                                             # and the search key itself
        typed(rig, b"S")
        assert "search: s_" in shown(rig)
        rig.game.press(TAB)                                            # in the box these are not the menu's keys
        rig.game.press(DOWN)
        rig.game.press(END)                                            # leaves the box and drops the search
        text = shown(rig)
        assert "search: " not in text and "AR-23 Liberator" in text
        rig.game.press(RIGHT)                                          # still in the item list: the next category
        text = shown(rig)
        assert "G-4 Gas" in text, text[:1500]
        assert not os.path.exists(rig.game.out_path("presets/Default.txt")) or \
            "=" not in rig.game.read_out("presets/Default.txt")        # and no value was changed on the way
    finally:
        rig.close()


def check_explodes_like_is_a_row_of_the_menu(mutate=None):
    rig = Rig("", mutate, auto=True)
    try:
        index = add_game_index(rig)
        rig.settle()
        rig.game.lua.execute(FAKE_ENGINE)
        rig.game.press(F9)
        catalog_stat("assault_rifle", "rpm")
        for _ in range(menu_order("primary", "secondary", "support", "melee").index("assault_rifle")):
            rig.game.press(DOWN)
        rig.game.press(TAB)
        stats = [s["id"] for s in catalog_stat("assault_rifle", "rpm")[0]["stats"] if s["id"] != "mode"]
        for _ in range(sum(1 for s in stats if s.startswith("status") or s in MENU_BEFORE_FIRE)):
            rig.game.press(DOWN)                                       # the row after damage, status and projectile
        text = shown(rig)
        assert "blast_from   (name in config.txt)" in text and "\nits own\n" in text, text[:900]
        rig.game.press(RIGHT)                                          # the first item that explodes, by name
        rig.game.frames(60)
        saved = rig.game.read_out("presets/Default.txt")
        donor = saved.split("blast_from = ")[1].split()[0]
        status = rig.game.status()
        assert "blast_from = " + donor in status and "REJECTED" not in status, status[:1500]
        # the Liberator's own projectile row now names the explosion of that item
        donor_blast = next(int(line.split("|")[3]) for line in gen_tuner_data.generate()[0].split("\n")
                           if line.startswith("B|") and line.split("|")[1] == next(
                               l.split("|")[1] for l in gen_tuner_data.generate()[0].split("\n")
                               if l.startswith("I|") and l.split("|")[3] == donor))
        new_id = rig.mem.peek(rig.keyed_field("ProjectileWeaponComponentData", LIBERATOR, 0), "<I")
        row = rig.mem.peek(index["ProjectileSettings"] + 8 * new_id, "<Q")
        assert rig.mem.peek(row + 144, "<I") == donor_blast
        text = shown(rig)
        assert "\nits own\n" not in text                              # the menu shows the donor's name instead
        rig.game.press(LEFT)                                           # back to its own
        rig.game.frames(60)
        assert "blast_from" not in rig.game.read_out("presets/Default.txt")
        rig.game.press(ENTER)                                          # no number can be typed here
        assert "= _" not in shown(rig)
    finally:
        rig.close()


def check_the_mouse(mutate=None):
    rig = Rig("", mutate)
    try:
        rig.settle()
        rig.game.lua.execute(FAKE_ENGINE)
        rig.game.press(F9)
        rig.game.frames(2)
        rig.game.press(0x01)                                           # a click of a mouse that has never moved
        assert "press ENTER / F3 to search" in shown(rig)              # is nothing: nobody is using it
        assert rig.game.lua.eval(b"stingray.drawn.top_rect") < 903     # and no pointer is drawn
        # the pages at the top: Presets is the second one
        rig.game.click(110, 60)
        text = shown(rig)
        assert "+ New preset (empty)" in text, text[:500]
        assert rig.game.lua.eval(b"stingray.drawn.top_rect") == 904    # and now there is a pointer, above everything
        rig.game.click(40, 60)                                         # Items
        assert "press ENTER / F3 to search" in shown(rig)
        # an item of the list, by clicking it: the fourth row
        catalog_stat("assault_rifle", "rpm")
        names = menu_order("primary", "secondary", "support", "melee")
        rig.game.click(100, 150 + 3 * 26 + 10)
        text = shown(rig)
        assert names[3] + "   (name in config.txt)" in text, (names[:5], text[:700])
        # a value, by clicking its number: the box opens, and what is typed is set
        rig.game.click(820, 150 + 1 * 26 + 10)                         # (row 0 is the heading, row 1 the first value)
        assert "\n= _\n" in shown(rig)
        typed(rig, b"3")
        rig.game.press(ENTER)
        rig.game.frames(40)
        assert " = 3" in rig.game.read_out("presets/Default.txt")
        # while a box is open a click does nothing
        rig.game.press(ENTER)
        rig.game.click(110, 60)
        assert "+ New preset (empty)" not in shown(rig)
        rig.game.press(ESCAPE)
        # another category, by its tab; the search, by its box
        rig.game.click(170, 100)
        assert "G-4 Gas" in shown(rig)
        rig.game.click(100, 130)
        assert "search: _" in shown(rig)
        rig.game.press(ESCAPE)
        # a list page: a click selects a row, a click on the selected row confirms it
        rig.game.click(300, 60)                                        # Language
        rig.game.click(100, 150 + 26 + 10)                             # Chinese: selected
        assert "! no font of the game can draw Chinese" not in shown(rig)   # selected only: not confirmed yet
        rig.game.click(100, 150 + 26 + 10)                             # and confirmed: this engine has no font for it
        assert "! no font of the game can draw Chinese" in shown(rig)
    finally:
        rig.close()


def check_a_value_can_be_typed(mutate=None):
    rig = Rig("", mutate)
    try:
        rig.settle()
        rig.game.lua.execute(FAKE_ENGINE)
        rig.game.press(F9)
        catalog_stat("assault_rifle", "rpm")                           # (reads the catalog the order comes from)
        names = menu_order("primary", "secondary", "support", "melee")
        for _ in range(names.index("assault_rifle")):
            rig.game.press(DOWN)
        rig.game.press(TAB)                                            # the first value of the Liberator: ap_bonus
        rig.game.press(INSERT)
        text = shown(rig)
        assert "\n= _\n" in text and "\n_\n" not in text              # seen in game: a text of "_" alone, and a hang
        typed(rig, b"3")
        assert "= 3_" in shown(rig)
        log = rig.game.read_out("byog.log")
        assert "menu: the value box opens" in log and "menu: the value box: first frame drawn" in log
        rig.game.press(INSERT)
        rig.game.frames(40)
        assert "ap_bonus = 3" in rig.game.read_out("presets/Default.txt")
        rig.game.press(INSERT)
        typed(rig, b"99")                                              # the range is -10 .. 10
        rig.game.press(INSERT)
        rig.game.frames(40)
        assert "ap_bonus = 10" in rig.game.read_out("presets/Default.txt") and "REJECTED" not in rig.game.status()
        rig.game.press(INSERT)
        typed(rig, b"5")
        rig.game.press(END)                                            # given up: nothing changes
        rig.game.frames(40)
        assert "ap_bonus = 10" in rig.game.read_out("presets/Default.txt")
    finally:
        rig.close()


def check_presets(mutate=None):
    rig = Rig("", mutate)
    try:
        with open(rig.game.out_path("menu.txt"), "wb") as f:           # what v1.0 kept: it becomes "Default"
            f.write(b"[weapon: assault_rifle]\r\nrpm = 700\r\n")
        rig.settle()
        assert rig.mem.peek(rig.rpm, "<f") == 700.0
        assert "rpm = 700" in rig.game.read_out("presets/Default.txt")
        assert 'preset "Default": 1 values set through the in-game menu' in rig.game.status()
        rig.game.lua.execute(FAKE_ENGINE)
        rig.game.press(F9)
        assert "Preset: Default" in shown(rig)
        rig.game.press(F7)
        text = shown(rig)
        assert "Default   (active, 1 values)" in text and "+ New preset (empty)" in text, text[:600]
        rig.game.press(DOWN)                                           # + New preset (empty)
        rig.game.press(INSERT)
        typed(rig, b"FUN")
        assert "Name: fun_" in shown(rig)
        rig.game.press(INSERT)
        rig.game.frames(60)
        assert rig.mem.peek(rig.rpm, "<f") == 640.0                    # the old preset's value is gone from the game
        assert os.path.exists(rig.game.out_path("presets/fun.txt"))
        assert "rpm = 700" in rig.game.read_out("presets/Default.txt")  # and still in its own file
        assert "preset = fun" in rig.game.read_out("settings.txt")
        text = shown(rig)
        assert "fun   (active, 0 values)" in text and "Preset: fun" in text, text[:600]
        # a name that is taken, whatever the case
        rig.game.press(DOWN); rig.game.press(DOWN)
        rig.game.press(INSERT)
        typed(rig, b"DEFAULT")
        rig.game.press(INSERT)
        assert "That name is taken" in shown(rig)
        # back to the first one
        rig.game.press(UP); rig.game.press(UP); rig.game.press(UP)
        rig.game.press(INSERT)                                         # [Activate] on "Default"
        rig.game.frames(60)
        assert rig.mem.peek(rig.rpm, "<f") == 700.0
        # delete the other one: asked first
        rig.game.press(DOWN)
        for _ in range(3):
            rig.game.press(RIGHT)
        rig.game.press(INSERT)
        assert 'Delete the preset "fun"?' in shown(rig)
        rig.game.press(END)                                            # no
        assert os.path.exists(rig.game.out_path("presets/fun.txt"))
        rig.game.press(INSERT)
        rig.game.press(INSERT)                                         # yes
        assert not os.path.exists(rig.game.out_path("presets/fun.txt"))
        assert rig.mem.peek(rig.rpm, "<f") == 700.0
    finally:
        rig.close()


def check_keys_can_be_changed(mutate=None):
    rig = Rig("", mutate)
    try:
        rig.settle()
        rig.game.lua.execute(FAKE_ENGINE)
        rig.game.press(F9)
        rig.game.press(F7); rig.game.press(F7)                         # Keys
        text = shown(rig)
        assert "Search" in text and "F3" in text and "Reset the keys" in text, text[:900]
        for _ in range(12):
            rig.game.press(DOWN)                                       # the 13th action: search
        rig.game.press(INSERT)
        assert "Press the key for: Search" in shown(rig)
        rig.game.press(0x4B)                                           # K
        assert "key.search = K" in rig.game.read_out("settings.txt")
        rig.game.press(F6); rig.game.press(F6)                         # Items
        rig.game.press(F3)
        assert "search: _" not in shown(rig)
        rig.game.press(0x4B)
        assert "search: _" in shown(rig)
        rig.game.press(END)
        # two actions on one key are named
        rig.game.press(F7); rig.game.press(F7)
        rig.game.press(INSERT)                                         # search again
        rig.game.press(TAB)
        assert "Two actions share the key TAB" in shown(rig)
    finally:
        rig.close()


def expected_filter(flag, next_hook):
    """The message filter, written out here independently of the addon (see a.hook_code for the listing)."""
    return (bytes.fromhex("85C9" "7829" "48B8") + struct.pack("<Q", flag) + bytes.fromhex("803800" "741A" "418B4008"
            "3D00010000" "7407" "3D02010000" "7508" "41C7400800000000" "4D89C1" "4989D0" "4863D1" "31C9" "48B8")
            + struct.pack("<Q", next_hook) + bytes.fromhex("FFE0"))


def check_the_game_input_can_be_blocked(mutate=None):
    rig = Rig("", mutate)
    try:
        # seen in game (v1.1.3): the file v1.1.2 left behind said "off", and nobody had chosen that
        os.makedirs(os.path.dirname(rig.game.out_path("settings.txt")), exist_ok=True)
        with open(rig.game.out_path("settings.txt"), "wb") as f:
            f.write(b"preset = Default\r\nlanguage = en\r\nblock_game_input = false\r\n")
        rig.game.window_thread = 5                                     # as in the game: not the mod's thread
        rig.settle()
        rig.game.lua.execute(FAKE_ENGINE)
        start = list(rig.game.raw)
        assert rig.game.game_gets_keys() and not rig.game.hooks
        rig.game.press(F9)
        assert rig.game.raw == [(1, 5, 0x0, 0x777)]                    # open: the pad is left, the mouse is gone
        # a "get message" hook on the game's window thread, and it is switched on
        assert len(rig.game.hooks) == 1 and rig.game.hooks[0][0] == 3 and rig.game.hooks[0][2] == 5
        assert not rig.game.game_gets_keys()
        code_at, flag_at = rig.game.hooks[0][1], rig.game.filter_flag()
        region = rig.mem.find(code_at)
        code = bytes(region["data"][:68])
        assert code == expected_filter(flag_at, 0x7FFB12345678), code.hex()
        assert region["protect"] == 0x20 and rig.mem.find(flag_at)["protect"] == 0x04   # runs, cannot be written; the flag can
        assert rig.mem.find(flag_at) is not region
        assert rig.game.focus == 0x777 and rig.game.focus_calls == 0 and rig.game.attach_calls == 0   # the focus is left alone
        log = rig.game.read_out("byog.log")
        assert "menu: raw input registered by the game: 1/2 flags 100 window 0x777" in log
        assert "menu: the game window 0x777 belongs to another thread" in log
        assert "menu: about to use SetWindowsHookExA" in log and "menu: message filter installed, code at" in log
        assert "menu: game input blocked (keyboard: message filter, mouse: raw input)" in log
        settings = rig.game.read_out("settings.txt")
        assert "block_input = true" in settings and "trying" not in settings
        typed(rig, b"S")                                               # the menu still sees the keys
        rig.game.frames(70)
        assert "filter on" in rig.game.read_out("watch.txt")
        rig.game.press(F9)                                             # closed: as it was
        assert sorted(rig.game.raw) == sorted(start) and rig.game.game_gets_keys()
        assert "menu: game input given back" in rig.game.read_out("byog.log")
        rig.game.press(F9)                                             # open again: the same filter, not a second one
        assert not rig.game.game_gets_keys() and len(rig.game.hooks) == 1
        rig.game.press(F7); rig.game.press(F7)
        for _ in range(15):
            rig.game.press(DOWN)
        assert "Block game input while the menu is open" in shown(rig)
        rig.game.press(INSERT)                                         # switched off, at once
        assert sorted(rig.game.raw) == sorted(start) and rig.game.game_gets_keys()
        assert "block_input = false" in rig.game.read_out("settings.txt")
        rig.game.press(F9)
        rig.game.press(F9)
        assert sorted(rig.game.raw) == sorted(start) and rig.game.game_gets_keys()   # and it stays off
        assert rig.game.focus_calls == 0 and rig.game.attach_calls == 0
    finally:
        rig.close()


def check_the_filter_does_what_its_listing_says(mutate=None):
    """The 68 bytes run for real, in this process: called like Windows calls a hook."""
    if sys.platform != "win32":
        return
    import ctypes
    rig = Rig("", mutate)
    try:
        rig.settle()
        k32 = ctypes.WinDLL("kernel32")
        k32.VirtualAlloc.restype = ctypes.c_void_p
        k32.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32]
        k32.VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32]
        seen = []
        NEXT = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t, ctypes.c_void_p)

        def next_hook(hook, code, wparam, lparam):
            seen.append((hook, code, wparam, lparam))
            return 1234

        keep = NEXT(next_hook)
        flag = ctypes.c_uint8(0)
        api = rig.game.state()[b"api"]
        code = bytes(api[b"hook_code"](ctypes.addressof(flag), ctypes.cast(keep, ctypes.c_void_p).value))
        assert len(code) == 68
        page = k32.VirtualAlloc(None, 4096, 0x3000, 0x40)
        try:
            ctypes.memmove(page, code, len(code))
            proc = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, ctypes.c_size_t, ctypes.c_void_p)(page)
            msg = (ctypes.c_uint8 * 48)()

            def call(on, code_value, message):
                flag.value = on
                struct.pack_into("<QI", msg, 0, 0x777, message)
                result = proc(code_value, 1, ctypes.addressof(msg))
                assert result == 1234                                          # what the next hook answered
                assert seen[-1] == (None, code_value, 1, ctypes.addressof(msg)), seen[-1]   # and it got all three
                assert struct.unpack_from("<Q", msg, 0)[0] == 0x777            # nothing else of the MSG is touched
                return struct.unpack_from("<I", msg, 8)[0]

            assert call(0, 0, 0x100) == 0x100 and call(0, 0, 0x102) == 0x102   # menu closed: everything passes
            assert call(1, 0, 0x100) == 0 and call(1, 0, 0x102) == 0           # open: key down and character are dropped
            assert call(1, 0, 0x101) == 0x101                                  # a released key passes
            assert call(1, 0, 0x104) == 0x104 and call(1, 0, 0x105) == 0x105   # Alt combinations (Alt+F4) pass
            assert call(1, 0, 0x0FF) == 0x0FF and call(1, 0, 0x103) == 0x103   # raw input, and the neighbours
            assert call(1, 0, 0x200) == 0x200 and call(1, 0, 0x0F) == 0x0F     # mouse, paint
            assert call(1, -1, 0x100) == 0x100                                 # code < 0: hands off, by the rules of a hook
            assert call(7, 3, 0x100) == 0                                      # any value but 0 is "on"
        finally:
            k32.VirtualFree(page, 0, 0x8000)
    finally:
        rig.close()


def check_nothing_of_ours_is_in_the_way_when_the_game_is_switched_away_from(mutate=None):
    # seen in game (v1.1.13, v1.1.16): moving the keyboard focus made the game stop answering, on Alt+Tab
    # or at once. The focus is not touched at all any more, whatever the game's window does.
    rig = Rig("", mutate)
    try:
        rig.game.window_thread = 5
        rig.settle()
        rig.game.lua.execute(FAKE_ENGINE)
        rig.game.press(F9)
        assert not rig.game.game_gets_keys()
        rig.game.in_front = False                                      # another window is in front
        rig.game.frames(120)
        rig.game.in_front = True
        rig.game.frames(60)
        assert not rig.game.game_gets_keys()                           # still open, still ours
        rig.game.in_front = False
        rig.game.lua.execute(b"BYOG.api.close_menu()")                 # closed while the game is behind
        assert rig.game.game_gets_keys()
        assert rig.game.focus_calls == 0 and rig.game.attach_calls == 0 and rig.game.focus == 0x777
    finally:
        rig.close()


def check_without_the_filter_the_keys_are_left_alone(mutate=None):
    rig = Rig("", mutate)
    try:
        rig.game.window_thread = 5
        rig.game.hook_refused = True                                   # Windows says no
        rig.settle()
        rig.game.lua.execute(FAKE_ENGINE)
        rig.game.press(F9)
        assert rig.game.game_gets_keys() and rig.game.focus_calls == 0
        assert rig.game.raw == [(1, 5, 0x0, 0x777)]                    # the mouse is still taken care of
        log = rig.game.read_out("byog.log")
        assert "the message filter could not be installed: Windows refused the hook" in log
        assert "game input blocked (keyboard: no, mouse: raw input)" in log
    finally:
        rig.close()


def check_a_settings_file_that_cannot_be_written_is_written_later(mutate=None):
    # seen in game (v1.1.15): the mark of the first try stayed in the file, and the next start took it for a crash
    rig = Rig("", mutate)
    try:
        rig.game.window_thread = 5
        rig.settle()
        rig.game.lua.execute(FAKE_ENGINE)
        path = rig.game.out_path("settings.txt")
        os.remove(path)
        os.mkdir(path)                                                 # nothing can be written there now
        rig.game.press(F9)
        assert not rig.game.game_gets_keys()                           # the menu works all the same
        rig.game.frames(60)
        os.rmdir(path)                                                 # and now it can
        rig.game.frames(60)
        settings = rig.game.read_out("settings.txt")
        assert "block_input = true" in settings and "trying" not in settings, settings
    finally:
        rig.close()


def check_a_block_that_closed_the_game_is_not_tried_again(mutate=None):
    rig = Rig("", mutate)
    try:
        # what the file looks like when the game closed inside the first try
        os.makedirs(os.path.dirname(rig.game.out_path("settings.txt")), exist_ok=True)
        with open(rig.game.out_path("settings.txt"), "wb") as f:
            f.write(b"preset = Default\r\nblock_input = true\r\nblock_input_trying = true\r\n")
        rig.settle()
        rig.game.lua.execute(FAKE_ENGINE)
        rig.game.press(F9)
        assert len(rig.game.raw) == 2 and rig.game.raw_calls == 0 and rig.game.game_gets_keys()
        assert rig.game.focus_calls == 0
        assert "block_input = false" in rig.game.read_out("settings.txt")
        assert "switched off" in rig.game.read_out("byog.log")
        rig.game.press(F7); rig.game.press(F7)
        assert "switched off: the game closed when this was tried" in shown(rig)
    finally:
        rig.close()


FAKE_FONTS = b"""
stingray.Application.can_get = function(kind, name)
  -- as the game answers when it is set to Chinese (research file of v1.1.9)
  return (kind == 'runtime_font' and name == 'content/fonts/fallback')
      or (kind == 'material' and name == 'content/fonts/runtime_font')
end
"""


def check_chinese(mutate=None):
    rig = Rig("", mutate)
    try:
        rig.settle()
        rig.game.lua.execute(FAKE_ENGINE)
        rig.game.lua.execute(FAKE_FONTS)
        rig.game.press(F9)
        rig.game.press(F6)                                             # Language is the last page
        text = shown(rig)
        assert "English   *" in text and "Chinese (Simplified)" in text, text[:600]
        rig.game.press(DOWN)
        rig.game.press(INSERT)
        text = shown(rig)
        assert "物品" in text and "预设" in text and "Items" not in text, text[:600]
        assert rig.game.lua.eval(b"stingray.drawn.font") == b"content/fonts/fallback"
        assert rig.game.lua.eval(b"stingray.drawn.material") == b"content/fonts/runtime_font"
        # while it is being tried the file says so, and not yet "Chinese"
        settings = rig.game.read_out("settings.txt")
        assert "chinese_trying = true" in settings and "language = en" in settings, settings
        rig.game.frames(70)
        settings = rig.game.read_out("settings.txt")
        assert "language = zh" in settings and "chinese_trying" not in settings, settings
        rig.game.press(F7)                                             # Items: headings and values in Chinese
        catalog_stat("assault_rifle", "rpm")
        for _ in range(menu_order("primary", "secondary", "support", "melee").index("assault_rifle")):
            rig.game.press(DOWN)
        rig.game.press(TAB)
        text = shown(rig)
        assert "伤害" in text and "穿甲加成" in text and "AR-23 Liberator" in text, text[:900]
        assert "ap_bonus   (config.txt" in text                        # the name config.txt takes stays as it is
        rig.game.press(F6)
        rig.game.press(UP)
        rig.game.press(INSERT)                                         # and back
        text = shown(rig)
        assert "Items" in text and "language = en" in rig.game.read_out("settings.txt")
    finally:
        rig.close()


def check_chinese_needs_a_font_of_the_game(mutate=None):
    rig = Rig("", mutate)
    try:
        rig.settle()
        rig.game.lua.execute(FAKE_ENGINE)                              # this engine has none of the fonts
        rig.game.lua.execute(b"stingray.Application.can_get = function(kind, name) return false end")
        rig.game.press(F9)
        rig.game.press(F6)
        rig.game.press(DOWN)
        rig.game.press(INSERT)
        text = shown(rig)
        assert "no font of the game can draw Chinese" in text and "Items" in text, text[:600]
        assert "language = en" in rig.game.read_out("settings.txt")
        assert "menu: font content/fonts/fallback (runtime_font): not there" in rig.game.read_out("byog.log")
    finally:
        rig.close()


def check_chinese_is_not_tried_again_after_the_game_stopped(mutate=None):
    # seen in game (v1.1.7, with a font of symbols): the game stopped answering, and the file still said "Chinese"
    rig = Rig("", mutate)
    try:
        os.makedirs(os.path.dirname(rig.game.out_path("settings.txt")), exist_ok=True)
        with open(rig.game.out_path("settings.txt"), "wb") as f:
            f.write(b"preset = Default\r\nlanguage = en\r\nchinese_trying = true\r\n")
        rig.settle()
        rig.game.lua.execute(FAKE_ENGINE)
        rig.game.lua.execute(FAKE_FONTS)
        rig.game.press(F9)
        rig.game.press(F6)
        rig.game.press(DOWN)
        rig.game.press(INSERT)
        text = shown(rig)
        assert "Chinese is switched off: the game stopped when it was drawn" in text and "Items" in text, text[:600]
        assert rig.game.lua.eval(b"stingray.drawn.font") != b"content/fonts/fallback"
        settings = rig.game.read_out("settings.txt")
        assert "chinese_failed = true" in settings and "language = en" in settings, settings
    finally:
        rig.close()


def check_status_effects_have_a_length(mutate=None):
    rig = Rig("[status: acid_storm]\nduration = 10\n[status: gas]\nduration = 150%\n", mutate)
    try:
        status = rig.settle()
        assert first_line(status) == "OK - 2 values applied", status[:900]
        # the rows of the table follow its 16-byte array head, 152 bytes each, in the order of their ids
        row = lambda row_id: rig.blocks["StatusEffectSettings"][0] + 24 + 16 + row_id * 152 + 40
        assert rig.mem.peek(row(55), "<f") == 10.0 and rig.mem.peek(row(42), "<f") == 9.0
        assert rig.mem.peek(row(43), "<f") == 10.0                     # the other gas is another status: untouched
        rig.game.lua.execute(FAKE_ENGINE)
        rig.game.press(F9)
        rig.game.press(LEFT)                                           # the last category
        text = shown(rig)
        assert "Status 48" in text and "Acid" in text and "Acid Storm" not in text, text[:900]
        rig.game.press(TAB)                                            # the three acids are one row: three drop-downs
        text = shown(rig)
        assert "[+] SPLASH" in text and "[+] STORM" in text and "Duration (s)" not in text, text[:900]
        rig.game.press(DOWN)
        rig.game.press(ENTER)                                          # the second one opens
        text = shown(rig)
        assert "[-] STORM" in text and "Duration (s)" in text and "[acid_storm] duration" in text, text[:900]
        assert "A status effect has one length" in text
    finally:
        rig.close()


def check_armor(mutate=None):
    # FS-37 Ravager is the first kit of the game's file: 23 pieces light (0), two of them heavy (2); its
    # passive is Engineering Kit (6). Med-Kit is the fourth passive block: +2 stims at +64, 2 s at +80.
    rig = Rig("[armor: fs_37_ravager]\nweight = 1\npassive = 7\n[armor_passive: med_kit]\neffect_extra_stims = 6\n"
              "[armor: helldiver]\nspeed_sprint = 7\n", mutate)
    try:
        status = rig.settle()
        assert first_line(status) == "OK - 28 values applied", status[:1200]   # the weight: once per piece
        kit = rig.blocks["HelldiverCustomizationKit"][0] + 24
        pieces = [152 + 96 * n for n in range(25)]
        assert [rig.mem.peek(kit + at, "<I") for at in pieces] == [1] * 25      # every piece, the heavy ones too
        assert rig.mem.peek(kit + 28, "<I") == 7
        other = rig.blocks["HelldiverCustomizationKit"][2] + 24                 # another armor: untouched
        assert rig.mem.peek(other + 152, "<I") == 2 and rig.mem.peek(other + 28, "<I") == 3
        med = rig.blocks["HelldiverCustomizationPassiveBonusSettings"][3] + 24
        assert rig.mem.peek(med + 64, "<f") == 6.0 and rig.mem.peek(med + 80, "<f") == 2.0
        assert rig.mem.peek(rig.keyed_field("AvatarComponentData", 0x4D1C334D294DFA97, 20), "<f") == 7.0
        # taken out of the file: every piece gets its own class back, not all the same one
        rig.game.write_config("")
        rig.game.press(F10)
        rig.game.frames(300)
        back = [rig.mem.peek(kit + at, "<I") for at in pieces]
        assert back.count(0) == 23 and back.count(2) == 2 and back[14] == 2, back
        assert rig.mem.peek(kit + 28, "<I") == 6 and rig.mem.peek(med + 64, "<f") == 2.0
        # what another mod has changed is left alone
        rig.mem.poke(med + 80, "<f", 9.0)
        rig.game.write_config("[armor_passive: med_kit]\neffect_stim_seconds = 4\neffect_extra_stims = 3\n")
        rig.game.press(F10)
        rig.game.frames(300)
        assert rig.mem.peek(med + 80, "<f") == 9.0 and rig.mem.peek(med + 64, "<f") == 3.0
        assert "unexpected content" in rig.game.status()
        # the menu: two lists of their own
        rig.game.lua.execute(FAKE_ENGINE)
        rig.game.press(F9)
        for _ in range(7):
            rig.game.press(RIGHT)
        text = shown(rig)
        assert "Armor 122" in text and "* Helldiver\n" in text and "A-9 Helljumper" in text, text[:900]
        assert "[+] MOVEMENT, STAMINA" in text and "[+] BODY" in text   # the helldiver: how it moves, and its own body
        rig.game.press(RIGHT)
        text = shown(rig)
        assert "Passives 31" in text and "Engineering Kit  (6)" in text, text[:900]
    finally:
        rig.close()


def check_packs_turrets_attachments(mutate=None):
    JUMP, GATLING = 0x59C5CA839449B379, int(catalog_stat("gatling_turret", "turn_speed_h")[0]["entity"], 16)
    rig = Rig("[backpack: jumppack_backpack]\npack_recharge_seconds = 2\npack_launch_force = 80\n"
              "[backpack: hover_backpack]\npack_hover_seconds = 30\n"
              "[backpack: displacement_backpack]\nwarp_distance = 40\n"
              "[stratagem_weapon: gatling_turret]\nturn_speed_h = 360\nsearch_seconds_min = 0.1\n"
              "[attachment: vertical_grip]\nmod_recoil_v = 0.1\n"
              "[throwable: frag_grenade]\nblast_shrapnel_velocity = 90\n"
              "[stratagem_weapon: eagle_500kg_bomb]\nexplosion_delay = 3\n"
              "[weapon: assault_rifle]\nreload_seconds = 1\n", mutate)
    try:
        status = rig.settle()
        assert first_line(status) == "OK - 10 values applied", status[:1500]
        # the Liberator reloads in the 3 s its magazine says (its own record says 0): the magazine's number is set
        _rifle, reload = catalog_stat("assault_rifle", "reload_seconds")
        assert reload["original"] == 0.0 and reload["default_attachment"]["value"] == 3.0, reload
        assert rig.mem.peek(rig.blocks["ComponentEntityDeltaStorage"][0] + 24
                            + reload["default_attachment"]["delta_data_offset"], "<f") == 1.0
        # the 500 kg bomb goes off 0.8 s after it lands: now 3 s
        _bomb, fuse = catalog_stat("eagle_500kg_bomb", "explosion_delay")
        assert fuse["original"] == 0.8
        assert rig.mem.peek(rig.row_field("ProjectileSettings", int(fuse["key"]), fuse["offset"]), "<f") == 3.0
        assert rig.mem.peek(rig.keyed_field("RechargeComponentData", JUMP, 0), "<f") == 2.0
        assert rig.mem.peek(rig.keyed_field("JumppackComponentData", JUMP, 0), "<f") == 80.0
        assert rig.mem.peek(rig.keyed_field("JumppackComponentData", JUMP, 24), "<f") == 0.5        # takeoff: as it was
        assert rig.mem.peek(rig.keyed_field("JumppackComponentData", 0x5EC80F4F1CDB66CF, 156), "<f") == 30.0
        assert rig.mem.peek(rig.keyed_field("DisplacementComponentData", 0xB49756795D9B0E68, 120), "<f") == 40.0
        assert rig.mem.peek(rig.keyed_field("TurretComponentData", GATLING, 12), "<f") == 360.0
        assert rig.mem.peek(rig.keyed_field("TurretComponentData", GATLING, 8), "<f") == 50.0       # up and down: as it was
        assert abs(rig.mem.peek(rig.keyed_field("DetectorComponentData", GATLING, 0), "<f") - 0.1) < 1e-6
        # the grip's number is in the delta storage's data, at the place the generator names
        import gen_tuner_data
        grip = next(s["offset"] for it in gen_tuner_data.attachment_items()[0] if it["path"].endswith("/vertical_grip")
                    for s in it["stats"] if s["id"] == "mod_recoil_v")
        storage = rig.blocks["ComponentEntityDeltaStorage"][0] + 24
        data_at = rig.mem.peek(storage + 64, "<Q")
        assert abs(rig.mem.peek(data_at + grip, "<f") - 0.1) < 1e-6
        # the pieces of a frag grenade: their speed is in their own projectile row
        assert rig.mem.peek(rig.row_field("ProjectileSettings", 201, 32), "<f") == 90.0
        # the Jump Pack has no hovering to set
        rig.game.write_config("[backpack: jumppack_backpack]\npack_hover_seconds = 5\n")
        rig.game.press(F10)
        rig.game.frames(300)
        assert 'has no stat "pack_hover_seconds"' in rig.game.status()
        assert rig.mem.peek(rig.keyed_field("TurretComponentData", GATLING, 12), "<f") == 80.0      # and all is back
        rig.game.lua.execute(FAKE_ENGINE)
        rig.game.press(F9)
        for _ in range(9):
            rig.game.press(RIGHT)
        text = shown(rig)
        assert "Attach. 46" in text and "items, one section each" in text and "[+] " in text, text[:900]   # families
        rig.game.press(TAB)
        rig.game.press(ENTER)                                          # the first load of the first family
        assert "[-] ON THE WEAPON IT IS FITTED TO" in shown(rig)
    finally:
        rig.close()


def check_one_row_for_one_thing(mutate=None):
    rig = Rig("", mutate)
    try:
        rig.settle()
        rig.game.lua.execute(FAKE_ENGINE)
        rig.game.press(F9)
        rig.game.press(F3)
        typed(rig, b"VOTELESS")
        rig.game.press(ENTER)
        text = shown(rig)
        # three bodies and the claws: one row of the list, and the value list says which is which
        assert "Voteless  [enemy]" in text and "1 of 1" in text and "Voteless (unit" not in text, text[:900]
        assert "4 items, one section each" in text and "[+] BODY: HEAVY" in text and "[+] BODY: LIGHT" in text, text[:1500]
        assert "Health" not in text                                    # every member is a closed drop-down at first
        rig.game.press(TAB)
        rig.game.press(ENTER)                                          # the first one opens: its values, under its headings
        text = shown(rig)
        assert "[-] BODY: HEAVY" in text and "[-] BODY\n" in text, text[:1500]
        assert "[cha_corrupted_v3] health" in text                     # whose value it is, by its own name
        rig.game.press(ESCAPE)                                         # the back key closes the heading one is in,
        text = shown(rig)
        assert "[+] BODY\n" in text and "[cha_corrupted_v3] health" not in text, text[:1500]
        rig.game.press(ESCAPE)                                         # then the member it belongs to,
        assert "[+] BODY: HEAVY" in shown(rig)
        rig.game.press(RIGHT)                                          # and Right opens a closed one like Enter does
        rig.game.press(RIGHT)
        assert "[cha_corrupted_v3] health" in shown(rig)
        rig.game.press(ENTER)
        typed(rig, b"7")
        rig.game.press(ENTER)
        rig.game.frames(40)
        saved = rig.game.read_out("presets/Default.txt")
        assert "cha_corrupted_v3" in saved and "cha_corrupted_v2" not in saved, saved   # the heavy one only
        heavy = rig.keyed_field("HealthComponentData", int(catalog_stat("cha_corrupted_v3", "health")[0]["entity"], 16),
                                catalog_stat("cha_corrupted_v3", "health")[1]["offset"])
        medium = rig.keyed_field("HealthComponentData", int(catalog_stat("cha_corrupted_v2", "health")[0]["entity"], 16),
                                 catalog_stat("cha_corrupted_v2", "health")[1]["offset"])
        rig.game.frames(300)
        assert rig.mem.peek(heavy, "<I") == 7 and rig.mem.peek(medium, "<I") == 130
        # the last value of the list is the claws': another item of the same row
        for _ in range(12):
            rig.game.press(0x22)                                       # Page Down
        rig.game.press(ENTER)
        text = shown(rig)
        assert "[-] SWIPE AND CLAW (MELEE)" in text and "[melee_voteless_swipe_and_claw] " in text, text[-900:]
        rig.game.press(DELETE)                                         # resets that value, not the body's
        rig.game.frames(40)
        assert "cha_corrupted_v3" in rig.game.read_out("presets/Default.txt")
    finally:
        rig.close()


def check_sections_start_closed(mutate=None):
    rig = Rig("", mutate, auto=True, closed=True)                      # (the other menu checks ask for them open)

    def last(text):
        return text.rsplit("BALANCE YOUR OWN GAME", 1)[1]

    def find(name):
        rig.game.press(F3)
        for _ in range(12):
            rig.game.press(BACKSPACE)
        typed(rig, name)
        rig.game.press(ENTER)
        rig.game.press(TAB)
        return last(shown(rig))
    try:
        rig.settle()
        rig.game.lua.execute(FAKE_ENGINE)
        rig.game.press(F9)
        text = find(b"SCORCHER")
        assert "[+] DAMAGE" in text and "[+] AMMO" in text and "[-] " not in text, text[:900]
        assert "\nDamage\n" not in text                               # nothing but headings until one is opened
        # the reload: the Scorcher's record says 0, and the wiki's time stands beside it
        closed = [line for line in text.split("\n") if line.startswith("[+] ")]
        for _ in range(closed.index("[+] AMMO")):
            rig.game.press(DOWN)
        rig.game.press(ENTER)
        text = last(shown(rig))
        assert "[-] AMMO" in text and "0 (wiki 2.5)" in text and "[+] DAMAGE" in text, text[:1500]
        # a heading that has been opened is open on the next item too
        rig.game.press(TAB)
        text = find(b"PURIFIER")
        assert "[-] AMMO" in text and "[+] DAMAGE" in text, text[:900]
    finally:
        rig.close()


def check_research_file(mutate=None):
    rig = Rig("[settings]\nresearch = true\n", mutate)
    try:
        rig.settle()
        rig.game.frames(400)
        text = rig.game.read_out("RESEARCH.txt")
        assert "[status effects] " in text and " rows of 152 bytes" in text, text[:400]
        rows = [line.split("|") for line in text.splitlines() if line[:1].isdigit()]
        by_id = {int(r[0]): r for r in rows}
        assert len(rows) >= 56 and by_id[55][1] == "Acid Storm" and by_id[55][4] == "1", rows[55:56]
        assert by_id[42][1] == "Gas" and by_id[42][4] == "6" and by_id[43][4] == "10"
        assert all(len(r[5]) == 304 for r in rows)                     # the whole row, for what is not known yet
        assert "[engine] no stingray table here" in text               # (this fake game has no engine)
        assert "research: RESEARCH.txt written" in rig.game.read_out("byog.log")
        assert first_line(rig.game.status()) == "OK - no changes configured"   # reading is not a change
    finally:
        rig.close()


def check_research_asks_for_fonts_of_other_kinds(mutate=None):
    rig = Rig("[settings]\nresearch = true\n", mutate)
    try:
        rig.game.lua.execute(b"""
            stingray = { Application = { can_get = function(kind, name)
                return kind == 'runtime_font' and name == 'content/fonts/runtime_font' end } }""")
        rig.settle()
        rig.game.frames(400)
        text = rig.game.read_out("RESEARCH.txt")
        assert "runtime_font: content/fonts/runtime_font\r\n" in text, text[-700:]
        assert "runtime_font_atlas: none" in text and "texture: none" in text
        assert not os.path.exists(rig.game.out_path("RESEARCH-running.txt"))   # the mark is gone when it went well
    finally:
        rig.close()


def check_research_does_not_ask_again_after_the_game_closed_there(mutate=None):
    rig = Rig("[settings]\nresearch = true\n", mutate)
    try:
        os.makedirs(os.path.dirname(rig.game.out_path("RESEARCH-running.txt")), exist_ok=True)
        with open(rig.game.out_path("RESEARCH-running.txt"), "wb") as f:
            f.write(b"font_material\r\n")
        rig.game.lua.execute(b"""
            ASKED = {}
            stingray = { Application = { can_get = function(kind, name) ASKED[kind] = true return false end } }""")
        rig.settle()
        rig.game.frames(400)
        text = rig.game.read_out("RESEARCH.txt")
        assert "left out: the game closed the last time this was asked (font_material)" in text, text[-700:]
        assert rig.game.lua.eval(b"ASKED.font") is True and rig.game.lua.eval(b"ASKED.runtime_font") is None
    finally:
        rig.close()


def check_research_can_be_switched_off(mutate=None):
    rig = Rig("[settings]\nresearch = false\n", mutate)
    try:
        rig.settle()
        rig.game.frames(200)
        assert rig.game.read_out("RESEARCH.txt") == ""
    finally:
        rig.close()


def check_sentry_lifetime(mutate=None):
    rig = Rig("[stratagem_weapon: turret_machinegun_gpmg]\nlifetime_seconds = 600\nsight_range = 150\n"
              "[stratagem_weapon: mortar_turret]\nproximity_range = 50%\n"
              "[shield: energy_shield]\nlifetime_seconds = 200%\n", mutate)
    try:
        sentry = rig.keyed_field("HellpodPayloadComponentData", SENTRY_GUN, 4)
        relay = rig.keyed_field("HellpodPayloadComponentData",
                                murmur64a(b"content/fac_helldivers/hellpod/energy_shield/energy_shield"), 4)
        assert rig.mem.peek(sentry, "<f") == 150.0 and rig.mem.peek(relay, "<f") == 40.0
        status = rig.settle()
        assert first_line(status) == "OK - 4 values applied", status[:900]
        assert rig.mem.peek(sentry, "<f") == 600.0 and rig.mem.peek(relay, "<f") == 80.0
        sight = rig.keyed_field("SensorEyeComponentData", SENTRY_GUN, 0)
        mortar = rig.keyed_field("SensorProximityComponentData",
                                 murmur64a(b"content/fac_helldivers/hellpod/mortar_turret/mortar_turret"), 0)
        assert rig.mem.peek(sight, "<f") == 150.0 and rig.mem.peek(mortar, "<f") == 62.5       # 75 and 125 in the game
        assert sorted(a for a, _d in rig.mem.writes) == sorted([sentry, relay, sight, mortar])
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
            self.assertRegex(status.split("\r\n")[1], r"^BYOG v\d+\.\d+\.\d+$")
            self.assertRegex(rig.game.log_text().split("\r\n")[0], r"^BYOG v\d+\.\d+\.\d+$")
        finally:
            rig.close()

    def test_shipped_data_is_generated_fresh(self):
        # what pack_addon puts into the zip, not what a test passes in
        text = harness.addon_source("tuner")
        for label, _exe, _dll in gen_tuner_data.BUILDS:
            for table, (rva, slots) in gen_tuner_data.INDEXES[label].items():
                self.assertIn("\nN|%s|%s|%X|%d\n" % (label, table, rva, slots), text)
            self.assertIn("\nV|%s|" % label, text)

    def test_attachment_values_point_into_the_delta_storage(self):
        blob, _stats = gen_tuner_data.generate()
        flagged = [x.split("|") for x in blob.splitlines() if x.startswith("F|") and x.endswith("|A")]
        self.assertEqual(len(flagged), 107)       # 18: the reload set by the magazine; 3: what a suppressor sets
        self.assertTrue(all(f[3] == "ComponentEntityDeltaStorage" and f[4] == "data" for f in flagged))
        data_start = __import__("deltas")._load()["xo"]
        _it, s = catalog_stat("assault_rifle", "capacity")
        self.assertIn("|capacity|ComponentEntityDeltaStorage|data|%d|u32|45|A"
                      % (s["default_attachment"]["delta_data_offset"] - data_start), blob)

    def test_magazine_and_census_data(self):
        blob, stats = gen_tuner_data.generate()
        lines = blob.splitlines()
        self.assertEqual(stats["own_magazines"], 19)
        self.assertEqual(len([x for x in lines if x.startswith("H|")]), 76)
        # one magazine is the default of three rifles: the same run for all three
        self.assertEqual(len([x for x in lines if x.startswith("G|") and x.endswith("|7BE1E04A7738E673")]), 3)
        self.assertFalse([x for x in lines if x[:2] in ("C|", "Q|", "Y|")])      # research lines: gone

    def test_explosion_data(self):
        blob, stats = gen_tuner_data.generate()
        lines = blob.splitlines()
        self.assertEqual(stats["spare"], 24)
        self.assertEqual(len([x for x in lines if x.endswith("|C|257|335|0|1|ExplosiveComponentData:36")]), 2)
        self.assertTrue([x for x in lines if x.startswith("S|ExplosionSettings|258,371,")])
        self.assertIn("P|ExplosionSettings|40,44,48,52", lines)
        own = [x for x in lines if x.startswith("B|") and x.split("|")[5] == "1"]
        borrow = [x for x in lines if x.startswith("B|") and x.split("|")[5] == "0"]
        self.assertEqual((len(own), len(borrow)), (80, 112))       # hand weapons, throwables, stratagem weapons
        # every row that may be borrowed, and every row copied into one, ships with its stock bytes
        for row in [x for x in lines if x.startswith("S|")][0].split("|")[2].split(","):
            self.assertTrue([x for x in lines if x.startswith("W|ExplosionSettings|%s|" % row)], row)

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
    ("magazine of its own: attachment used although own_rows is on",
     "local base = entry.attachment and config.own_rows and item.magazine and item.magazine.base[stat]",
     "local base = nil",
     check_magazine_values_of_the_weapons_own),
    ("magazine of its own: taken although own_rows is off",
     "local base = entry.attachment and config.own_rows and item.magazine and item.magazine.base[stat]",
     "local base = entry.attachment and item.magazine and item.magazine.base[stat]",
     check_magazine_values_live_in_the_default_attachment),
    ("magazine of its own: the other weapons with this magazine are forgotten",
     "        for _, item in ipairs(MAGAZINES[resource]) do",
     "        for _, item in ipairs({}) do",
     check_magazine_values_of_the_weapons_own),
    ("magazine of its own: the attachment is not switched off",
     "        desired[switch.key] = { field = switch, value = 0, sources = {}, base = true, group = group, order = 2 }",
     "",
     check_magazine_values_of_the_weapons_own),
    ("magazine of its own: switched off before the records are in place",
     "        desired[switch.key] = { field = switch, value = 0, sources = {}, base = true, group = group, order = 2 }",
     "        desired[switch.key] = { field = switch, value = 0, sources = {}, base = true, group = group, order = 1 }",
     check_magazine_values_of_the_weapons_own),
    ("magazine of its own: other weapons get their unused record values",
     "entry = { field = field, value = item.stats[stat].field.stock, sources = {}, base = true }",
     "entry = { field = field, value = base.stock, sources = {}, base = true }",
     check_magazine_values_of_the_weapons_own),
    ("explosion of its own: the borrowed row keeps the shared damage row",
     "                if offset == 4 and damage then value = damage end",
     "",
     check_explosions_of_their_own),
    ("explosion of its own: array heads taken from the offline data",
     "field.exact, field.live = nil, get_field('ExplosionSettings', tostring(source), offset, 'u32', value)",
     "field.exact, field.live = nil, nil",
     check_explosions_of_their_own),
    ("explosion of its own: switched before the borrowed row is complete",
     "order = 2, needs_index = (a.new_damage ~= nil or b.kind == 'P') or nil }",
     "order = 1, needs_index = (a.new_damage ~= nil or b.kind == 'P') or nil }",
     check_explosions_of_their_own),
    ("explosion of its own: new ids used without a proven index",
     "order = 2, needs_index = (a.new_damage ~= nil or b.kind == 'P') or nil }",
     "order = 2 }",
     check_explosion_of_its_own_waits_for_a_proven_index),
    ("explosion of its own: blast values still written to the shared rows",
     "            if not target.own then\n                local field, group = own_blast_field(item, entry.field)",
     "            if false then\n                local field, group = own_blast_field(item, entry.field)",
     check_explosions_of_their_own),
    ("explosion of its own: one borrowed row given to two items",
     "    spare.next[table_name] = n\n",
     "",
     check_explosions_of_their_own),
    ("more magazines at the start than the maximum is not reported",
     "            if limit and start and start > limit then",
     "            if false then",
     check_magazine_values_of_the_weapons_own),
    ("a row in another group of its table counts as missing",
     "                absent = absent + 1\n",
     "                entry.note = 'record not found in the table'\n",
     check_stratagems_backpacks_shields_and_vehicles),
    ("row ids always read at the start of the row",
     "stride = tonumber(f[5]), id_at = tonumber(f[6]), blocks = {} }",
     "stride = tonumber(f[5]), id_at = 0, blocks = {} }",
     check_stratagems_backpacks_shields_and_vehicles),
    ("a vehicle part that outlasts its vehicle is not reported",
     "            if health and not w.request.warning then",
     "            if false then",
     check_stratagems_backpacks_shields_and_vehicles),
    ("a shortcut and a line for one of its values reject each other",
     "                local line = direct[request.category .. ':' .. request.item:lower() .. ':' .. target.stat]",
     "                local line = nil",
     check_stratagems_backpacks_shields_and_vehicles),
    ("blast_from: the id goes to the explosion on expiry",
     "local BLAST_ON_IMPACT = 144      -- ProjectileInfo.explosion_type_on_impact",
     "local BLAST_ON_IMPACT = 156      -- ProjectileInfo.explosion_type_on_impact",
     check_stratagem_weapons_and_blast_from),
    ("blast_from: not possible for a throwable",
     "    elseif item.blasts and item.blasts[1].kind == 'C' then\n        for _, s in ipairs(item.blasts[1].switches) do",
     "    elseif false then\n        for _, s in ipairs(item.blasts[1].switches) do",
     check_stratagem_weapons_and_blast_from),
    ("blast_from: any item accepted as the source",
     "    if not source or not source.blasts then\n",
     "    if not source then\n",
     check_stratagem_weapons_and_blast_from),
    ("blast_from: written although the weapon has no row of its own",
     "    if stat == 'blast_from' then return true end        -- written into the weapon's own projectile row\n",
     "",
     check_stratagem_weapons_and_blast_from),
    ("own bullet: the belt pattern of the magazine still names the shared round",
     "        for _, s in ipairs(t.fresh and item.switches or {}) do",
     "        for _, s in ipairs({}) do",
     check_stratagem_weapons_and_blast_from),
    ("own bullet: the tracer of a belt keeps the shared row",
     "            if s.projectile ~= t.src_projectile and rounds[s.projectile] == nil and stock",
     "            if false and stock",
     check_stratagem_weapons_and_blast_from),
    ("tables behind a first page that is not in memory are not found",
     "            if A.readable_start(base, size) then",
     "            if A.readable_private(base) then",
     check_tables_are_found_when_their_first_page_is_not_in_memory),
    ("menu: the panel is not in the middle of the screen",
     "    local left, bottom = (width - PANEL_W * scale) / 2, (height - PANEL_H * scale) / 2",
     "    local left, bottom = 0, 0",
     check_menu_changes_a_value_and_remembers_it),
    ("menu: what is typed does not filter the list",
     "    if menu.filter == '' then\n        local category = MENU_CATEGORIES[menu.tab]",
     "    if true then\n        local category = MENU_CATEGORIES[menu.tab]",
     check_menu_search_finds_items_of_every_category),
    ("menu: search looks at the internal names only",
     "                    or (item.display or ''):lower():find(menu.filter, 1, true) or internal:find(menu.filter, 1, true)\n",
     "                    or internal:find(menu.filter, 1, true)\n",
     check_menu_search_finds_items_of_every_category),
    ("more ammunition than a resupply fills is not reported",
     "    local RESUPPLY_LIMIT = 1023\n",
     "    local RESUPPLY_LIMIT = 99999\n",
     check_more_ammunition_than_a_resupply_fills_is_said),
    ("menu: the warning of the selected value is not shown",
     "            if warning and not menu.note then yellow('! '",
     "            if false then yellow('! '",
     check_more_ammunition_than_a_resupply_fills_is_said),
    ("menu: a value is shown by its short name",
     "                    row(menu_label(stat), 460, y, 728 - 16, here, focused, 34, function()\n",
     "                    row(stat, 460, y, 728 - 16, here, focused, 34, function()\n",
     check_menu_changes_a_value_and_remembers_it),
    ("menu: the name config.txt takes is not shown",
     "                gray(menu_clip((item.members and ('[' .. owner.name .. '] ') or '') .. stats[at], 60) .. '   ('",
     "                gray(menu_clip((item.members and ('[' .. owner.name .. '] ') or '') .. menu_label(stats[at]), 60) .. '   ('",
     check_menu_changes_a_value_and_remembers_it),
    ("menu: the menu's keys also work while a box is typed into",
     "    if menu.mode == 'text' then\n        menu_box_input(now)\n    elseif menu.mode == 'capture' then",
     "    if menu.mode == 'text' then\n        menu_box_input(now)\n    end\n    if menu.mode == 'capture' then",
     check_keys_go_to_the_box_only),
    ("menu: the select key does not open the search from the item list",
     "    elseif menu.focus == 'items' and menu_act('accept', now, true) then\n",
     "    elseif false then\n",
     check_keys_go_to_the_box_only),
    ("menu: a letter searches without the search key",
     "    if menu_act('search', now, true) then\n",
     "    if menu_act('search', now, true) or A.key_down(0x53) then\n",
     check_keys_go_to_the_box_only),
    ("menu: the value box is drawn as a bare underscore",
     "                        text('= ' .. menu.box.text .. '_', 800, y + 3, 17, 255, c, c, c)\n",
     "                        text(menu.box.text .. '_', 800, y + 3, 17, 255, c, c, c)\n",
     check_a_value_can_be_typed),
    ("menu: the row \"explodes like\" is missing",
     "    if menu.takes_blast(item) then\n        local label, rank = menu_group('blast_from')",
     "    if false then\n        local label, rank = menu_group('blast_from')",
     check_explodes_like_is_a_row_of_the_menu),
    ("menu: a number can be typed where the name of an item belongs",
     "        if stat and stat ~= 'blast_from' and menu_act('accept', now, true) then",
     "        if stat and menu_act('accept', now, true) then",
     check_explodes_like_is_a_row_of_the_menu),
    ("keys: Insert and End are gone (the keys the testers and the notes of v1.1 know)",
     "            if a[1] == action and a[4] and menu_key_pressed(a[4], now, no_repeat) then pressed = true end\n",
     "",
     check_keys_go_to_the_box_only),
    ("attachments: their numbers are filed as an effect of a passive",
     "    if stat:sub(1, 4) == 'mod_' then return 'ON THE WEAPON IT IS FITTED TO', 720 end\n",
     "",
     check_packs_turrets_attachments),
    ("drop-downs: the headings start open",
     "                closed = menu.is_closed(heading_key, not config.sections_open)\n",
     "                closed = menu.is_closed(heading_key, false)\n",
     check_sections_start_closed),
    ("drop-downs: a heading opened on one item is closed on the next",
     "        values(item, 'every item', 1)\n",
     "        values(item, item.category .. '|' .. item.name, 1)\n",
     check_sections_start_closed),
    ("menu: what the wiki says about a reload is not shown",
     "                    if owner.hints and owner.hints[stat] then stock = stock .. ' (' .. owner.hints[stat] .. ')' end\n",
     "",
     check_sections_start_closed),
    ("drop-downs: the members of a group are open from the start",
     "            local closed = menu.is_closed(key, true)\n",
     "            local closed = menu.is_closed(key, false)\n",
     check_one_row_for_one_thing),
    ("drop-downs: the back key does not close the heading one is in",
     "                menu.toggle(item, row.parent, true)\n",
     "                menu.toggle(item, row.parent, false)\n",
     check_one_row_for_one_thing),
    ("drop-downs: Right does not open a closed heading",
     "            elseif stats[at] == false and side > 0 then\n",
     "            elseif false then\n",
     check_one_row_for_one_thing),
    ("groups: a value of a group is set on the group's first member",
     "    return item.menu_owners and item.menu_owners[n] or item\n",
     "    return item.members and item.members[1] or item\n",
     check_one_row_for_one_thing),
    ("groups: the members of a group are rows of their own as well",
     "            if item.group then\n",
     "            if item.group and false then\n",
     check_one_row_for_one_thing),
    ("armor: a value kept once per piece is set for the first piece only",
     "            for _, extra in ipairs(entry.more or {}) do\n",
     "            for _, extra in ipairs({}) do\n",
     check_armor),
    ("armor: a number another mod has changed is overwritten",
     "            if SPECS[f[4]] and SPECS[f[4]].shape == 'S' then field.exact = true end\n",
     "",
     check_armor),
    ("armor: the record of a block is not asked for by its id",
     "            block.records_at, block.index, block.count, block.limit = payload, { [id] = 0 }, 1, payload + block.size\n",
     "            block.records_at, block.index, block.count, block.limit = payload, { [0] = 0, [id + 1] = 0 }, 1, payload + block.size\n",
     check_armor),
    ("mouse: a click is taken although the mouse never moved",
     "    if mouse and menu.mouse_used then\n",
     "    if mouse then\n",
     check_the_mouse),
    ("mouse: a click is taken while a box is typed into",
     "        if button and not menu.mouse_down and menu.mode == 'list' then\n",
     "        if button and not menu.mouse_down then\n",
     check_the_mouse),
    ("mouse: a held button clicks every frame",
     "        if button and not menu.mouse_down and menu.mode == 'list' then\n",
     "        if button and menu.mode == 'list' then\n",
     check_the_mouse),
    ("mouse: a click on a number does not open the box",
     "                        if mouse and mouse.x >= 790 and stat ~= 'blast_from' then\n",
     "                        if false then\n",
     check_the_mouse),
    ("mouse: a click on a list page confirms at once",
     "            if current == n then menu.click_accept = true else set(n) end\n",
     "            menu.click_accept = true\n            set(n)\n",
     check_the_mouse),
    ("menu: a typed value may leave the range",
     "    value = math.max(range.min, math.min(range.max, value))\n",
     "",
     check_a_value_can_be_typed),
    ("menu: a box that is given up still counts",
     "    elseif menu_act('back', now, true) then\n        menu.mode, menu.box = 'list', nil\n        if box.kind == 'search'",
     "    elseif menu_act('back', now, true) then\n        menu.mode, menu.box = 'list', nil\n        if box.done then box.done(box.text, now) end\n        if box.kind == 'search'",
     check_a_value_can_be_typed),
    ("presets: the values of the old preset stay",
     "    for key in pairs(overrides) do overrides[key] = nil end\n    for key, value in pairs(values or {})",
     "    for key, value in pairs(values or {})",
     check_presets),
    ("presets: a name can be used twice",
     "            if preset_known(new) then return menu_say(L('That name is taken'), at) end\n",
     "",
     check_presets),
    ("presets: deleted without asking",
     "        menu.mode, menu.ask = 'confirm', { name = name }\n",
     "        os.remove(dir .. '\\\\' .. preset_file(name))\n",
     check_presets),
    ("presets: menu.txt of v1.0 is forgotten",
     "        for key, value in pairs(preset_parse(read_file(OLD_MENU_FILE))) do overrides[key] = value end\n",
     "",
     check_presets),
    ("keys: the chosen key is not kept",
     "                menu.bind[capture.action] = key\n",
     "",
     check_keys_can_be_changed),
    ("keys: two actions on one key are not named",
     "                if clash then menu_say(L('Two actions share the key %s'):format(clash), now) end\n",
     "",
     check_keys_can_be_changed),
    ("game input: not given back when the menu closes",
     "    pcall(menu_block_game, false)\n",
     "    if menu.mode == 'x' then pcall(menu_block_game, false) end\n",
     check_the_game_input_can_be_blocked),
    ("game input: blocked although it is switched off",
     "    if menu.block then\n        if not menu.block_tried then",
     "    if true then\n        if not menu.block_tried then",
     check_the_game_input_can_be_blocked),
    ("game input: the default of an older version switches it off",
     "            elseif key == 'block_input' then\n",
     "            elseif key == 'block_input' or key == 'block_game_input' then\n",
     check_the_game_input_can_be_blocked),
    ("game input: the keys still go to the game's window",
     "        local keys = menu.block_keys(true)\n",
     "        local keys = false\n",
     check_the_game_input_can_be_blocked),
    ("game input: the filter stays on when the menu is closed",
     "        menu.keys_blocked = nil\n        A.hook_on(false)\n",
     "        menu.keys_blocked = nil\n",
     check_the_game_input_can_be_blocked),
    ("game input: a second filter with every opening",
     "            if hook.thread == thread then return true end\n",
     "            hook = nil\n",
     check_the_game_input_can_be_blocked),
    ("game input: the filter's code stays writable",
     "        if not a.protect(code_at, 0x20) then return nil, 'the code could not be made executable' end",
     "        if false then return nil end",
     check_the_game_input_can_be_blocked),
    ("game input: the flag is in the page of the code",
     "        local code_at, flag_at = own_memory(), own_memory()\n",
     "        local code_at = own_memory()\n        local flag_at = code_at + 2048\n",
     check_the_game_input_can_be_blocked),
    ("filter: a released key is dropped as well (a key held when the menu opens stays down for the game)",
     "'\\x3D\\x02\\x01\\x00\\x00' .. '\\x75\\x08'",
     "'\\x3D\\x01\\x01\\x00\\x00' .. '\\x75\\x08'",
     check_the_filter_does_what_its_listing_says),
    ("filter: it also drops while the menu is closed",
     "'\\x80\\x38\\x00' .. '\\x74\\x1A'",
     "'\\x80\\x38\\x00' .. '\\x90\\x90'",
     check_the_filter_does_what_its_listing_says),
    ("filter: the next hook gets the arguments in the wrong places",
     "'\\x4D\\x89\\xC1' .. '\\x49\\x89\\xD0'",
     "'\\x49\\x89\\xD0' .. '\\x4D\\x89\\xC1'",
     check_the_filter_does_what_its_listing_says),
    ("filter: it acts on a call it has to keep its hands off (code < 0)",
     "'\\x85\\xC9' .. '\\x78\\x29'",
     "'\\x85\\xC9' .. '\\x90\\x90'",
     check_the_filter_does_what_its_listing_says),
    ("game input: when Windows refuses the filter the menu says the keys are blocked",
     "        local ok, where = A.hook_install(thread)\n        if not ok then\n",
     "        local ok, where = A.hook_install(thread)\n        if false then\n",
     check_without_the_filter_the_keys_are_left_alone),
    ("game input: the pad is taken away as well",
     "            if d.page == 1 and (d.usage == 2 or d.usage == 6) then mine[#mine + 1] = d end\n",
     "            if d.page == 1 then mine[#mine + 1] = d end\n",
     check_the_game_input_can_be_blocked),
    ("game input: put back with other flags than it had",
     "        if not A.raw_register(menu.raw_saved) then log(",
     "        for _, d in ipairs(menu.raw_saved) do d.flags = 0 end\n        if not A.raw_register(menu.raw_saved) then log(",
     check_the_game_input_can_be_blocked),
    ("settings: a write that failed is never made up for",
     "    if menu.settings_unsaved and now - (menu.settings_tried or 0) > 0.5 then\n",
     "    if false then\n",
     check_a_settings_file_that_cannot_be_written_is_written_later),
    ("game input: a try that closed the game is tried again",
     "            elseif key == 'block_input_trying' and value == 'true' then\n                tried = true\n",
     "",
     check_a_block_that_closed_the_game_is_not_tried_again),
    ("chinese: a font the engine does not have is used",
     "                if usable then menu.zh_fonts[#menu.zh_fonts + 1] = { font = c[2], material = c[3] } end\n",
     "                menu.zh_fonts[#menu.zh_fonts + 1] = { font = c[2], material = c[3] }\n",
     check_chinese_needs_a_font_of_the_game),
    ("chinese: drawn with the font that has no Chinese",
     "    if menu.lang == 'zh' and menu.zh_font then\n        font, material = menu.zh_font.font",
     "    if false then\n        font, material = menu.zh_font.font",
     check_chinese),
    ("chinese: tried again although the game stopped there",
     "            elseif (key == 'chinese_trying' or key == 'chinese_failed') and value == 'true' then\n",
     "            elseif false then\n",
     check_chinese_is_not_tried_again_after_the_game_stopped),
    ("chinese: the file says Chinese before it has been drawn for a while",
     "        if menu.lang_saved ~= 'zh' then\n            menu.zh_trying = true\n",
     "        if menu.lang_saved ~= 'zh' then\n            menu.lang_saved = 'zh'\n",
     check_chinese),
    ("chinese: drawn with the debug font's material",
     "        S.Gui.text(gui, str, font, size * scale, material,\n",
     "        S.Gui.text(gui, str, font, size * scale, menu.font,\n",
     check_chinese),
    ("chinese: the values keep their English names",
     "    local label = MENU_LABEL[rest]\n    return label and L(label) or stat\n",
     "    local label = MENU_LABEL[rest]\n    return label or stat\n",
     check_chinese),
    ("research: asked again although the game closed there the last time",
     "        elseif read_file('RESEARCH-running.txt') then\n",
     "        elseif false then\n",
     check_research_does_not_ask_again_after_the_game_closed_there),
    ("research: the mark of a try stays behind",
     "            if dir then os.remove(dir .. '\\\\RESEARCH-running.txt') end\n",
     "",
     check_research_asks_for_fonts_of_other_kinds),
    ("research: the names of the status rows are not read",
     "                if pointer and pointer > 0x10000 and A.read(pointer, 64) then\n",
     "                if false then\n",
     check_research_file),
    ("research: written although it is switched off",
     "            if config.research and research.pending then\n",
     "            if research.pending then\n",
     check_research_can_be_switched_off),
    ("own bullet: the other places that name the round are left as they were",
     "        for _, s in ipairs(t.fresh and item.switches or {}) do\n",
     "        for _, s in ipairs({}) do\n",
     check_a_round_loaded_weapon_is_switched_where_it_takes_its_round_from),
    ("menu: the values of an item are not grouped",
     "        if x.rank ~= y.rank then return x.rank < y.rank end\n        if x.first ~= y.first",
     "        if x.first ~= y.first",
     check_menu_changes_a_value_and_remembers_it),
    ("menu: text drawn without a layer, under the panel",
     "                   layers and S.Vector3(px, py, 902) or S.Vector2(px, py), S.Color(a, r, g, b))",
     "                   S.Vector2(px, py), S.Color(a, r, g, b))",
     check_menu_changes_a_value_and_remembers_it),
    ("menu: the gui is handed to a function that takes none",
     "        local ok, w, h = pcall(S.Application.back_buffer_size)",
     "        local ok, w, h = pcall(S.Application.back_buffer_size, gui)",
     check_menu_changes_a_value_and_remembers_it),
    ("menu: nothing in the log before an engine call",
     "    log('menu: about to use ' .. name)\n    flush_log()",
     "",
     check_menu_changes_a_value_and_remembers_it),
    ("menu: a change never reaches the engine",
     "        menu.dirty_at = nil\n        request_reload()\n        pcall(menu_save)",
     "        menu.dirty_at = nil\n        pcall(menu_save)",
     check_menu_changes_a_value_and_remembers_it),
    ("menu: drawn although it is closed",
     "    if not menu.open then return end\n    local ok, why = pcall(function()",
     "    if not menu.S then return end\n    local ok, why = pcall(function()",
     check_menu_changes_a_value_and_remembers_it),
    ("menu: menu.txt is not read at start",
     "    if not menu.loaded then pcall(menu_load) end",
     "    menu.loaded = true",
     check_menu_values_are_read_at_start),
    ("menu: a value outside the allowed range",
     "    if value > range.max then value = range.max end\n    if same_value",
     "    if same_value",
     check_menu_stays_inside_the_range),
    ("attachment values written 4 bytes off",
     "        local address = block.records_at + field.offset\n",
     "        local address = block.records_at + field.offset + 4\n",
     check_magazine_values_live_in_the_default_attachment),
    ("attachment value not marked in STATUS",
     "target.attachment and '  (value of the default attachment)' or ''",
     "''",
     check_magazine_values_live_in_the_default_attachment),
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
     "if not same_value(entry.field.storage, current, expected) then result = 'changed' end",
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
     "        if offset == 0 then word = id elseif damage and offset == OWN_DAMAGE_AT then word = damage end",
     "        if offset == 0 then word = id end",
     check_new_row_ids_in_memory_of_our_own),
    ("new id: slot and id do not belong together",
     "        t.first_id, t.count, t.users = (address + t.slots_at - t.index) / 8, 0, {}",
     "        t.first_id, t.count, t.users = (address - t.index) / 8, 0, {}",
     check_new_row_ids_in_memory_of_our_own),
    ("new id: two weapons get the same row",
     "    local user = t.users[key]\n    if user then return user.id end",
     "    local user = t.users[next(t.users) or key]\n    if user then return user.id end",
     check_new_row_ids_for_several_weapons),
    ("new id: only one of the two indexes is checked",
     "                    if not ok then\n                        index_ok, own.index_note = ok, why\n                        break",
     "                    if not ok and name == 'ProjectileSettings' then\n                        index_ok, own.index_note = ok, why\n                        break",
     check_new_projectile_id_needs_a_proven_index),
    ("new id: stats still go to the shared projectile row",
     "    if t.fresh then\n        -- a row of our own starts as a copy of the weapon's row",
     "    if false then\n        -- a row of our own starts as a copy of the weapon's row",
     check_new_row_ids_in_memory_of_our_own),
    ("automatic own rows although own_rows = off",
     "    if config.own_rows then\n        local automatic = {}",
     "    if true then\n        local automatic = {}",
     check_applies_exactly_what_was_asked),
    ("automatic own rows for a weapon that said own_bullet = false",
     "            if item and request.status ~= 'accepted' then declined[item] = true end",
     "",
     check_a_changed_weapon_gets_rows_of_its_own_by_itself),
    ("automatic own rows for values that are not in the shared rows",
     "                and touches_shared_rows(item, request.stat) then",
     "                then",
     check_a_changed_weapon_gets_rows_of_its_own_by_itself),
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
            # A few mutations only change the ORDER of writes, which then follows Lua's table order
            # (random per run) and can come out right by chance: such a mutant must survive three runs.
            for _attempt in range(3):
                try:
                    check((old, new))
                except Exception:
                    break                     # caught (assertion, or the addon failed to load)
            else:
                survivors.append(name)
        self.assertEqual(survivors, [])

    def test_mutation_targets_exist(self):
        mem, info = harness.build_world(second_copy=False)
        source = real_source(info)
        for name, old, _new, _check in MUTATIONS:
            self.assertEqual(source.count(old), 1, name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
