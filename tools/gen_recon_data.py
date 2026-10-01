# -*- coding: utf-8 -*-
"""Generate the data blob that is embedded into the recon addon.

The recon addon knows nothing about the game by itself; everything it looks
for comes from this blob, which is generated from the Stage 0 artefacts
(data/catalog.json, the typelib, the community stratagem snapshot).

Line format (one record per line, '|' separated):

  T|name|type_hash_hex|shape|stride|id_at
      a table to look for. shape: R rows, K keyed, S single-record blocks,
      D delta storage. stride = record size from the typelib (0 for S/D).
  W|table|key|offset|storage|expected|label
      a value to read and compare with the offline value.
      key: 16 hex digits (entity hash) for K tables, decimal row id for R.
      storage: u32 | i32 | f32 | u8
  C|stratagem_id|uses|cooldown
      community-snapshot values used to calibrate StratagemInfo offsets.
  N|table|name_offset
      R table whose rows carry a debug-name string pointer at name_offset.

    python tools/gen_recon_data.py        # -> build/recon_data.txt
"""
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import build_catalog as B  # noqa: E402
import gostructs  # noqa: E402
import hashnames  # noqa: E402
import hd2db  # noqa: E402
from dump_typelib import dlsum  # noqa: E402

OUT = os.path.join(ROOT, "build", "recon_data.txt")
STORAGE = {"UINT32": "u32", "INT32": "i32", "FP32": "f32", "UINT8": "u8"}

# wrapper type name -> (shape, id_at)
TABLES = [
    ("ProjectileSettings", "R", 0), ("DamageSettings", "R", 0), ("ExplosionSettings", "R", 0),
    ("BeamSettings", "R", 0), ("ArcSettings", "R", 0),
    ("StatusEffectSettings", "R", 0), ("StratagemSettings", "R", 4),
    ("WeaponDataComponentData", "K", 0), ("ProjectileWeaponComponentData", "K", 0),
    ("WeaponMagazineComponentData", "K", 0), ("WeaponRoundsComponentData", "K", 0),
    ("WeaponHeatComponentData", "K", 0), ("BeamWeaponComponentData", "K", 0),
    ("ArcWeaponComponentData", "K", 0), ("SprayWeaponComponentData", "K", 0),
    ("MeleeWeaponComponentData", "K", 0), ("ThrowableComponentData", "K", 0),
    ("ExplosiveComponentData", "K", 0), ("DepositComponentData", "K", 0),
    ("ShieldComponentData", "K", 0), ("HealthComponentData", "K", 0),
    ("VehicleComponentData", "K", 0), ("WeaponCustomizationComponentData", "K", 0),
    ("AvatarComponentData", "K", 0),
    ("WeaponCustomizationSettings", "R", 8),
    ("HelldiverCustomizationKit", "S", 0), ("HelldiverCustomizationPassiveBonusSettings", "S", 0),
    ("ComponentEntityDeltaStorage", "D", 0),
]


def fmt(v, st):
    if st == "f32":
        return repr(round(float(v), 6))
    return str(int(v))


def main():
    lines = []
    tl = gostructs.typelib()["types"]
    for name, shape, id_at in TABLES:
        stride = 0
        if shape in ("R", "K"):
            _rt, stride, _shape = hd2db.record_type(name)
        lines.append("T|%s|%08X|%s|%d|%d" % (name, dlsum(name), shape, stride or 0, id_at))

    with open(os.path.join(ROOT, "data", "catalog.json"), encoding="utf-8") as f:
        cat = json.load(f)
    seen = set()
    n_watch = 0

    def watch(table, key, offset, storage, expected, label):
        nonlocal n_watch
        k = (table, str(key), offset)
        if k in seen:
            return
        seen.add(k)
        lines.append("W|%s|%s|%d|%s|%s|%s" % (table, key, offset, storage, fmt(expected, storage), label))
        n_watch += 1

    for it in cat["items"]:
        short = it["path"].rsplit("/", 1)[-1]
        for s in it["stats"]:
            if "error" in s:
                continue
            watch(s["table"], s["key"], s["offset"], STORAGE[s["storage"]], s["original"],
                  "%s.%s" % (short, s["id"]))
    for av in cat["armor"]["avatar"]:
        for s in av["stats"]:
            watch(s["table"], s["key"], s["offset"], STORAGE[s["storage"]], s["original"], "avatar." + s["id"])

    # extras resolved here: backpacks, shields, vehicles (helldiver entities with a known path)
    def keyed_extra(wrapper, rtype, fields, want):
        t = hd2db.table(wrapper)
        for ent in sorted(t.index):
            path = hashnames.name(ent)
            if not path or not want(path):
                continue
            rec = t.record(ent)
            short = path.rsplit("/", 1)[-1]
            for label, off, st in fields:
                v = struct.unpack_from({"u32": "<I", "i32": "<i", "f32": "<f"}[st], rec, off)[0]
                watch(wrapper, "%016X" % ent, off, st, v, "%s.%s" % (short, label))

    o = B.off
    keyed_extra("DepositComponentData", "DepositComponent",
                [("capacity", o("DepositComponent", "capacity")[0], "u32"),
                 ("start_amount", o("DepositComponent", "start_amount")[0], "i32"),
                 ("refill_amount", o("DepositComponent", "refill_amount")[0], "u32")],
                lambda p: "/fac_helldivers/" in p)
    keyed_extra("ShieldComponentData", "ShieldComponent",
                [("radius", 0, "f32"), ("charge", o("ShieldComponent", "charge")[0], "f32")]
                + [("f%d" % off, off, "f32") for off in (80, 88, 92, 96, 100, 104)],
                lambda p: "/fac_helldivers/" in p)
    vehicles = set(hd2db.table("VehicleComponentData").index)
    armor_off = o("HealthComponent", "default_damageable_zone_info")[0] + 216
    t = hd2db.table("HealthComponentData")
    for ent in sorted(vehicles):
        path = hashnames.name(ent)
        rec = t.record(ent)
        if not path or rec is None or "/fac_helldivers/vehicles/" not in path:
            continue
        short = path.rsplit("/", 1)[-1]
        watch("HealthComponentData", "%016X" % ent, 0, "i32", struct.unpack_from("<i", rec, 0)[0], short + ".health")
        watch("HealthComponentData", "%016X" % ent, armor_off, "u32",
              struct.unpack_from("<I", rec, armor_off)[0], short + ".armor")

    with open(os.path.join(ROOT, "reference", "HelldiversData", "generated_stratagem_settings.json"),
              encoding="utf-8") as f:
        groups = json.load(f)
    n_cal = 0
    for g in groups:
        for it in g.get("StratagemSettings", {}).get("items", []):
            lines.append("C|%d|%d|%s" % (it["id"], it.get("uses", 0), repr(float(it.get("cooldown_duration_success", 0)))))
            n_cal += 1

    name_off = {m["offset"] for m in tl["StatusEffectInfo"]["members"] if m["storage"] == "STR"}
    lines.append("N|StatusEffectSettings|%d" % min(name_off))
    lines.append("N|StratagemSettings|16")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    blob = "\n".join(lines) + "\n"
    assert "]==]" not in blob
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(blob)
    print("recon data: %d tables, %d watch values, %d stratagem calibration rows, %d bytes -> %s" % (
        len(TABLES), n_watch, n_cal, len(blob), os.path.relpath(OUT, ROOT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
