# -*- coding: utf-8 -*-
"""Generate the data blob that is embedded into the tuner addon.

The engine knows nothing about the game by itself: every table, item, field,
stock value and allowed range comes from this blob, generated from the Stage 0
artefacts (data/catalog.json, the typelib) and the builds verified in game.

Line format ('|' separated):

  V|label|exe_sha256|game_dll_sha256
      a game build this data was verified on (reports/..., docs/STAT-MAP.md §0).
  T|name|type_hash_hex|shape|stride|id_at          shape: R rows, K keyed
  I|index|category|name|entity16
  F|item_index|stat|table|key|offset|storage|stock|flags
      one memory field of one stat of one item. key: entity16 (K) or row id (R).
      flags: A = the weapon's default attachment sets this value (STAT-MAP §6.2): the field is
      then the attachment's own value inside the delta storage (table ComponentEntityDeltaStorage,
      key "data", offset inside its data array), not the weapon's record, which the game overwrites.
      Every weapon with the same default attachment names the same field, so they show up as sharing it.
  R|stat|min|max|integer
  A|alias|mode|stat,stat,...     mode: all | nonzero (only fields whose stock value is not 0)
  O|item_index|base_projectile|src_projectile|new_projectile|src_damage|new_damage
      "own bullet": rows nothing references that this weapon may take over (see TAKEOVERS).
      base_projectile is the value in the weapon's own record (0 when only an attachment sets it).
  W|table|row_id|hex            stock bytes of a row involved in a takeover
  X|item_index|offset|expected  the default ammo attachment's projectile value: offset inside the
                                delta storage's data array, and the value expected there
  G|item_index|run_at|count|resource
      the weapon's default magazine attachment: where the count of its magazine deltas sits inside the
      delta storage's components array, and that count. Writing 0 there switches the attachment's
      magazine values off for every weapon carrying it; the weapons' own records then count.
  H|item_index|stat|table|key|offset|storage|stock   the same stat in the weapon's own record
  B|item_index|kind|explosion|damage|own|shared_damage|switches
      an explosion of the item (tools/blasts.py). kind P: reached through the weapon's projectile row,
      switches = offsets inside that row; C: through the item's component records, switches =
      table:offset. own = 1: nothing else reaches the explosion row. shared_damage = 1: something else
      uses its damage row.
  S|table|id,id,...              rows that may be borrowed (no table in memory refers to them; census)
  P|table|offset,offset,...      words of a row that hold addresses: copied from memory, never from W
  Y|table|row_id                 the canary's model row: a harmless, very visible explosion
  Q|id type|table                census (read-only research): the table whose row ids are counted
  C|id type|type name|type hash|shape|stride|offline|path;path
      a type that can hold such an id. shape K / R: the table shapes above, paths start at a record;
      O: any other block, paths start at its payload. A path is steps separated by ',': a number adds
      bytes, aN is a dynamic array head (u64 pointer, u64 count, N-byte elements). offline: references
      counted offline, empty when the type is not in the data we have.

    python tools/gen_tuner_data.py        # -> build/tuner_data.txt
"""
import json
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import blasts  # noqa: E402
import deltas  # noqa: E402
import hd2db  # noqa: E402
import references  # noqa: E402
from dump_typelib import dlsum  # noqa: E402

OUT = os.path.join(ROOT, "build", "tuner_data.txt")
STORAGE = {"UINT32": "u32", "INT32": "i32", "FP32": "f32"}

# Builds verified in game (recon v0.1.0, 2026-10-01).
BUILDS = [
    ("release/01.007.101/19155",
     "F5FEE03DCFDB2E553A4752C283590950AC13316B376D8196AA556FF0400D5F06",
     "2E2C3B7C2500646DADD5F2B4C6E0504DBB7E7896139F64CDDC0D1813C718F51E"),
]

# Where game.dll keeps its id-indexed arrays of row pointers, measured in game (probe v0.3.2):
# build label -> table -> (rva of the slot of id 0, number of slots = highest id + 1).
INDEXES = {
    "release/01.007.101/19155": {"ProjectileSettings": (0x37C7670, 351), "DamageSettings": (0x37C60C0, 650)},
}

CATEGORY = {"primary": "weapon", "secondary": "weapon", "support": "weapon", "melee": "weapon",
            "throwable": "throwable", "backpack": "backpack", "shield": "shield", "vehicle": "vehicle",
            "stratagem": "stratagem", "stratagem_weapon": "stratagem_weapon"}
ID_AT = {"StratagemSettings": 4}       # where a row keeps its id (0 unless listed)
SKIP_STATS = {"mode"}          # enum fields are not numbers; id-type stats come in Stage 3

# (regex on the stat id, min, max, integer) -- first match wins. Sanity bounds, not balance advice.
RANGES = [
    (r"(^|_)ap_(direct|slight|large|extreme)$", 0, 10, 1),
    (r"^(durable_)?ap_bonus$", -10, 10, 0),
    (r"^(durable_)?bonus2$", -100000, 100000, 0),      # +136 / +140: effect unknown
    (r"(^|_)(durable_)?damage$", 0, 100000, 1),
    (r"(^|_)(demolition|stagger|push)$", 0, 10000, 1),
    (r"(^|_)status\d_type$", 0, 71, 1),            # a row id of the status table (docs/STATUS-EFFECTS.md)
    (r"(^|_)status\d_value$", 0, 100000, 0),
    (r"^(rpm|rpm_low|rpm_high|arc_rpm)$", 1, 6000, 0),
    (r"^speed_multiplier$", 0.01, 100, 0),
    (r"^pellets$", 1, 100, 1),
    (r"^velocity$", 1, 20000, 0),
    (r"^mass$", 0.001, 100000, 0),
    (r"^calibre$", 0.01, 1000, 0),
    (r"^drag$", 0, 100, 0),
    (r"^gravity$", -100, 100, 0),
    (r"^life_time$", 0, 600, 0),
    (r"^penetration_slowdown$", 0, 1, 0),
    (r"^arming_distance$", 0, 10000, 0),
    (r"^capacity$", 1, 9999, 1),
    (r"^charges$", 1, 9999, 1),
    (r"^charges_start$", -1, 9999, 1),             # -1 = start full
    (r"^charges_refill$", 0, 9999, 1),
    (r"^shield_health$", 1, 1000000, 0),
    (r"^shield_radius$", 0, 500, 0),
    (r"^shield_(recharge|broken)_delay$", 0, 3600, 0),
    (r"^shield_recharge_rate$", 0, 1000000, 0),
    (r"(^|_)durable_resistance$", 0, 1, 0),
    (r"^explosion_damage_multiplier$", 0, 10, 0),
    (r"^constitution$", 0, 1000000, 1),
    (r"^constitution_rate$", -100000, 100000, 0),
    (r"^part_.+_to_main$", 0, 10, 0),
    (r"^part_.+_overflow_cap$", 0, 1, 1),
    (r"^armor$", 0, 10, 1),
    (r"^part_.+_health$", 1, 1000000, 1),
    (r"^part_.+_armor$", 0, 10, 1),
    (r"^call_in_time$", 0, 600, 0),
    (r"^health$", 1, 1000000, 1),
    (r"^cooldown$", 0, 7200, 0),
    (r"^uses$", 1, 4294967295, 1),                 # 4294967295 = unlimited
    (r"^mags_(start|supply|max)$", 0, 999, 1),
    (r"^rounds_(start|supply|max)$", 0, 9999, 1),
    (r"_(inner|outer|stagger)_radius$", 0, 500, 0),
    (r"_shrapnel_count$", 0, 500, 1),
    (r"^(start|max|refill)_amount$", 0, 999, 1),
    (r"^throw_distance_max$", 1, 500, 0),
    (r"^(arming_delay|fuse)$", 0, 60, 0),
    (r"^(overheat_temperature|temp_gain_per_shot|temp_gain_per_second|temp_loss_per_second)$", 0, 100000, 0),
    (r"^recoil_(drift|climb)_[hv]$", 0, 1000, 0),
    (r"^spread_[hv]$", 0, 1000, 0),
    (r"^sway$", 0, 100, 0),
    (r"^ergonomics$", 0, 1000, 0),
    (r"^arc_range$", 0, 1000, 0),
]

# item name -> spare rows it may take over (STAT-MAP §6.5). Spare = referenced by no entity component,
# no attachment delta and no explosion; the damage row belongs to a spare projectile row only.
# 267 is the unused near-twin of the Liberator's round (same calibre, same damage row).
TAKEOVERS = {
    "assault_rifle": {"projectile": 267, "damage": 55},
}

MAGAZINE_STATS = ("capacity", "mags_start", "mags_supply", "mags_max")
CENSUS = [("ExplosionType", "ExplosionSettings")]

ALIASES = [
    ("ap", "nonzero", ["ap_direct", "ap_slight", "ap_large", "ap_extreme"]),
    ("blast_ap", "nonzero", ["blast_ap_direct", "blast_ap_slight", "blast_ap_large", "blast_ap_extreme"]),
    ("recoil", "all", ["recoil_drift_h", "recoil_drift_v", "recoil_climb_h", "recoil_climb_v"]),
    ("recoil_h", "all", ["recoil_drift_h", "recoil_climb_h"]),
    ("recoil_v", "all", ["recoil_drift_v", "recoil_climb_v"]),
    ("spread", "all", ["spread_h", "spread_v"]),
    ("magazine", "all", ["capacity"]),
    ("spare_magazines", "all", ["mags_max"]),
    ("carried", "all", ["max_amount"]),
]


def stat_range(stat):
    for pattern, lo, hi, integer in RANGES:
        if re.search(pattern, stat):
            return lo, hi, integer
    return None


def num(v, storage):
    if storage == "f32":
        return repr(round(float(v), 6))
    return str(int(v))


def generate(builds=None, indexes=None):
    """-> (blob text, stats dict)

    builds   test builds instead of BUILDS: [(label, exe sha256, dll sha256)]
    indexes  {table: (rva, slots)} for those test builds (default: the latest measured ones)"""
    with open(os.path.join(ROOT, "data", "catalog.json"), encoding="utf-8") as f:
        cat = json.load(f)
    lines = []
    for label, exe, dll in (BUILDS if builds is None else builds):
        lines.append("V|%s|%s|%s" % (label, exe, dll))
        known = indexes if indexes is not None else INDEXES.get(label, list(INDEXES.values())[-1])
        for table, (rva, slots) in sorted(known.items()):
            lines.append("N|%s|%s|%X|%d" % (label, table, rva, slots))
    tables, items, fields, stats_seen, unranged = {}, [], [], set(), set()
    data_start = deltas._load()["xo"]
    magazines = {}          # item index -> (catalog item, {stat: (stat entry, attachment entry)})
    for it in cat["items"]:
        category = CATEGORY.get(it["category"])
        if not category:
            continue
        index = len(items)
        items.append("I|%d|%s|%s|%s" % (index, category, it["path"].rsplit("/", 1)[-1], it["entity"]))
        for s in it["stats"]:
            if "error" in s or s["id"] in SKIP_STATS:
                continue
            if stat_range(s["id"]) is None:
                unranged.add(s["id"])
                continue
            storage = STORAGE[s["storage"]]
            stats_seen.add(s["id"])
            attached = s.get("default_attachment")
            if attached:
                tables["ComponentEntityDeltaStorage"] = True
                fields.append("F|%d|%s|ComponentEntityDeltaStorage|data|%d|%s|%s|A" % (
                    index, s["id"], attached["delta_data_offset"] - data_start, storage,
                    num(attached["value"], storage)))
                if s["id"] in MAGAZINE_STATS:
                    magazines.setdefault(index, (it, {}))[1][s["id"]] = (s, attached)
                continue
            flags = ""
            tables[s["table"]] = True
            fields.append("F|%d|%s|%s|%s|%d|%s|%s|%s" % (
                index, s["id"], s["table"], s["key"], s["offset"], storage, num(s["original"], storage), flags))
    if unranged:
        raise ValueError("stats without a range: %s" % sorted(unranged))
    # takeovers
    extra, stock_rows, own_bullets = [], {}, 0
    P, Dm = hd2db.table("ProjectileSettings"), hd2db.table("DamageSettings")
    fire = hd2db.table("ProjectileWeaponComponentData")
    for index, line in enumerate(items):
        _i, _idx, _cat, name, entity_hex = line.split("|")
        # every weapon that fires projectiles can get rows of its own (new ids); the ones listed in
        # TAKEOVERS can also take over spare rows (new_projectile / new_damage, 0 = none assigned)
        spec = TAKEOVERS.get(name)
        ent = int(entity_hex, 16)
        record = fire.record(ent)
        if record is None:
            assert not spec, name
            continue
        base_projectile = struct.unpack_from("<I", record, 0)[0]
        override = deltas.default_overrides(ent).get(("ProjectileWeaponComponent", 0))
        src_projectile = struct.unpack("<I", override[0])[0] if override else base_projectile
        if src_projectile not in P.by_id():
            assert not spec, name
            continue
        src_row = P.record(P.by_id()[src_projectile])
        src_damage = struct.unpack_from("<I", src_row, 60)[0]
        if src_damage not in Dm.by_id():
            assert not spec, name
            continue
        new_projectile, new_damage = (spec["projectile"], spec["damage"]) if spec else (0, 0)
        assert not spec or (new_projectile in P.by_id() and new_damage in Dm.by_id())
        extra.append("O|%d|%d|%d|%d|%d|%d" % (index, base_projectile, src_projectile, new_projectile,
                                              src_damage, new_damage))
        own_bullets += 1
        for pid in (src_projectile, new_projectile):
            if pid:
                stock_rows[("ProjectileSettings", pid)] = P.record(P.by_id()[pid])
        for did in (src_damage, new_damage):
            if did:
                stock_rows[("DamageSettings", did)] = Dm.record(Dm.by_id()[did])
        if override:
            extra.append("X|%d|%d|%d" % (index, override[1] - data_start, src_projectile))
            tables["ComponentEntityDeltaStorage"] = True
        tables["ProjectileSettings"] = tables["DamageSettings"] = True
        tables["ProjectileWeaponComponentData"] = True
    # magazines: a default magazine attachment whose magazine deltas form one run of their own can be
    # switched off, so that each weapon's own record counts
    own_magazines = 0
    for index, (it, stats) in sorted(magazines.items()):
        if set(stats) != set(MAGAZINE_STATS) or len(set(a["item"] for _s, a in stats.values())) != 1:
            continue
        attachment = next(iter(stats.values()))[1]["item"]
        resource = next(int(a["delta_resource"], 16) for a in it["default_attachments"] if a["item"] == attachment)
        wanted = sorted((s["offset"], 4) for s, _a in stats.values())
        runs = [(run, entries) for run, _ci, entries in deltas.component_runs(resource) if sorted(entries) == wanted]
        if len(runs) != 1:
            continue                  # the run also carries other deltas: it cannot be switched off as a whole
        extra.append("G|%d|%d|%d|%016X" % (index, runs[0][0] * 12 + 8, len(wanted), resource))
        for stat in MAGAZINE_STATS:
            s = stats[stat][0]
            storage = STORAGE[s["storage"]]
            extra.append("H|%d|%s|%s|%s|%d|%s|%s" % (index, stat, s["table"], s["key"], s["offset"], storage,
                                                    num(s["original"], storage)))
            tables[s["table"]] = True
        own_magazines += 1
    # explosions: which items need a row of their own, and the rows that may be borrowed for it
    index_of = dict((line.split("|")[3], int(line.split("|")[1])) for line in items
                    if line.split("|")[2] in ("weapon", "throwable", "stratagem_weapon"))
    with_rows = set(int(x.split("|")[1]) for x in extra if x.startswith("O|"))
    Xp = hd2db.table("ExplosionSettings")
    found, own_blasts = blasts.item_blasts(cat), 0
    for name, item_blasts in sorted(found.items()):
        index = index_of.get(name)
        # the explosion on impact first: it is the one `blast_from` hands to another item
        item_blasts.sort(key=lambda b: (b["kind"] == "P" and 144 not in b["switches"], b["explosion"]))
        for b in item_blasts if index is not None else []:
            if b["kind"] == "P":
                if index not in with_rows:
                    continue
                switches = ",".join(str(o) for o in b["switches"])
            else:
                switches = ",".join("%s:%d" % s for s in b["switches"])
                for wrapper, _offset in b["switches"]:
                    tables[wrapper] = True
            damage = b["damage"] if b["damage"] in Dm.by_id() else 0
            extra.append("B|%d|%s|%d|%d|%d|%d|%s" % (index, b["kind"], b["explosion"], damage, int(b["own"]),
                                                    int(b["shared_damage"] and bool(damage)), switches))
            if not b["own"]:
                stock_rows[("ExplosionSettings", b["explosion"])] = Xp.record(Xp.by_id()[b["explosion"]])
            if damage:
                stock_rows[("DamageSettings", damage)] = Dm.record(Dm.by_id()[damage])
            own_blasts += 1
    spare = [row for row, _score, _why in blasts.pool()]
    marker = found["smoke_grenade"][0]["explosion"]
    extra.append("S|ExplosionSettings|" + ",".join(str(row) for row in spare))
    extra.append("P|ExplosionSettings|" + ",".join(str(o) for o in references.pointer_words("ExplosionInfo")))
    extra.append("Y|ExplosionSettings|%d" % marker)
    for row in spare + [marker]:
        stock_rows[("ExplosionSettings", row)] = Xp.record(Xp.by_id()[row])
    tables["ExplosionSettings"] = tables["DamageSettings"] = True
    # census: every type that can hold a row id of the tables in CENSUS
    for target, own_table in CENSUS:
        extra.append("Q|%s|%s" % (target, own_table))
        offline = {}
        for users in references.users(target, own_table).values():
            for wrapper, _key, _offset in users:
                offline[wrapper] = offline.get(wrapper, 0) + 1
        for name, shape, stride, paths, present in references.census_types(target, own_table):
            extra.append("C|%s|%s|%08X|%s|%d|%s|%s" % (
                target, name, dlsum(name), shape, stride, offline.get(name, 0) if present else "",
                ";".join(",".join(p) for p in paths)))
    for (table, row_id), raw in sorted(stock_rows.items()):
        extra.append("W|%s|%d|%s" % (table, row_id, raw.hex().upper()))
    for name in sorted(tables):
        if name == "ComponentEntityDeltaStorage":
            lines.append("T|%s|%08X|D|0|0" % (name, dlsum(name)))
            continue
        _rt, stride, shape = hd2db.record_type(name)
        lines.append("T|%s|%08X|%s|%d|%d" % (name, dlsum(name), "R" if shape == "rows" else "K", stride,
                                             ID_AT.get(name, 0)))
    lines += items + fields + extra
    for stat in sorted(stats_seen):
        lo, hi, integer = stat_range(stat)
        lines.append("R|%s|%s|%s|%d" % (stat, repr(lo), repr(hi), integer))
    for alias, mode, targets in ALIASES:
        lines.append("A|%s|%s|%s" % (alias, mode, ",".join(targets)))
    # all_health: the main health and every part's health of a vehicle together. With a percentage the
    # relations between them stay as the game has them (a part still breaks before the vehicle is gone).
    parts = sorted(s for s in stats_seen if re.search(r"^part_.+_health$", s))
    lines.append("A|all_health|all|%s" % ",".join(["health"] + parts))
    blob = "\n".join(lines) + "\n"
    assert "]==]" not in blob
    return blob, {"tables": len(tables), "items": len(items), "fields": len(fields), "stats": len(stats_seen),
                  "own_bullets": own_bullets, "stock_rows": len(stock_rows), "own_magazines": own_magazines,
                  "blasts": own_blasts, "spare": len(spare)}


def main():
    blob, st = generate()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(blob)
    print("tuner data: %(tables)d tables, %(items)d items, %(fields)d fields, %(stats)d stats" % st
          + ", %d bytes -> %s" % (len(blob), os.path.relpath(OUT, ROOT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
