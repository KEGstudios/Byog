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
      flags: A = the live value comes from a default attachment's delta, not from
      this field (STAT-MAP §6.2): the engine refuses to edit it.
  R|stat|min|max|integer
  A|alias|mode|stat,stat,...     mode: all | nonzero (only fields whose stock value is not 0)

    python tools/gen_tuner_data.py        # -> build/tuner_data.txt
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import hd2db  # noqa: E402
from dump_typelib import dlsum  # noqa: E402

OUT = os.path.join(ROOT, "build", "tuner_data.txt")
STORAGE = {"UINT32": "u32", "INT32": "i32", "FP32": "f32"}

# Builds verified in game (recon v0.1.0, 2026-10-01).
BUILDS = [
    ("release/01.007.101/19155",
     "F5FEE03DCFDB2E553A4752C283590950AC13316B376D8196AA556FF0400D5F06",
     "2E2C3B7C2500646DADD5F2B4C6E0504DBB7E7896139F64CDDC0D1813C718F51E"),
]

CATEGORY = {"primary": "weapon", "secondary": "weapon", "support": "weapon", "melee": "weapon",
            "throwable": "throwable"}
SKIP_STATS = {"mode"}          # enum fields are not numbers; id-type stats come in Stage 3

# (regex on the stat id, min, max, integer) -- first match wins. Sanity bounds, not balance advice.
RANGES = [
    (r"(^|_)ap_(direct|slight|large|extreme)$", 0, 10, 1),
    # The second addend pair (+136 / +140). Both name sources call it "ap_addends", but the game's own
    # barrel attachments write +10 / -5 there, which looks like damage. Wide range until tested in game.
    (r"^(durable_)?ap_bonus$", -100000, 100000, 0),
    (r"(^|_)(durable_)?damage$", 0, 100000, 1),
    (r"^(durable_)?damage_bonus$", -100000, 100000, 0),
    (r"(^|_)(demolition|stagger|push)$", 0, 10000, 1),
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


def generate(builds=None):
    """-> (blob text, stats dict)"""
    with open(os.path.join(ROOT, "data", "catalog.json"), encoding="utf-8") as f:
        cat = json.load(f)
    lines = []
    for label, exe, dll in (BUILDS if builds is None else builds):
        lines.append("V|%s|%s|%s" % (label, exe, dll))
    tables, items, fields, stats_seen, unranged = {}, [], [], set(), set()
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
            flags = "A" if "default_attachment" in s else ""
            tables[s["table"]] = True
            stats_seen.add(s["id"])
            fields.append("F|%d|%s|%s|%s|%d|%s|%s|%s" % (
                index, s["id"], s["table"], s["key"], s["offset"], storage, num(s["original"], storage), flags))
    if unranged:
        raise ValueError("stats without a range: %s" % sorted(unranged))
    for name in sorted(tables):
        _rt, stride, shape = hd2db.record_type(name)
        lines.append("T|%s|%08X|%s|%d|0" % (name, dlsum(name), "R" if shape == "rows" else "K", stride))
    lines += items + fields
    for stat in sorted(stats_seen):
        lo, hi, integer = stat_range(stat)
        lines.append("R|%s|%s|%s|%d" % (stat, repr(lo), repr(hi), integer))
    for alias, mode, targets in ALIASES:
        lines.append("A|%s|%s|%s" % (alias, mode, ",".join(targets)))
    blob = "\n".join(lines) + "\n"
    assert "]==]" not in blob
    return blob, {"tables": len(tables), "items": len(items), "fields": len(fields), "stats": len(stats_seen)}


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
