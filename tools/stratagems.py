# -*- coding: utf-8 -*-
"""Stage 0: which settings rows does each stratagem use?

StratagemSettings is NOT in FileDiver's plaintext bundle, so the stratagem
list (ids, debug names, payload entity hashes) is taken from the community
JSON snapshot (shalzuth/HelldiversData, an OLDER build). Everything below the
payload is resolved against the CURRENT entities blob.

The walk is generic and typelib-driven: for every payload entity, every
component record it has is scanned for members whose typelib type is one of
the enums ProjectileType / ExplosionType / DamageInfoType / BeamType / ArcType
(recursing into nested structs and inline arrays), and for u64 members that
are themselves entity hashes (followed up to a small depth: a hellpod carries
a sentry, a sentry carries a gun, ...). No stratagem-specific knowledge.

    python tools/stratagems.py                 # summary + data/stratagems.json
    python tools/stratagems.py "500KG"         # detail for matching debug names
"""
import collections
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import gostructs  # noqa: E402
import hashnames  # noqa: E402
import hd2db  # noqa: E402

JSON_PATH = os.path.join(ROOT, "reference", "HelldiversData", "generated_stratagem_settings.json")
OUT = os.path.join(ROOT, "data", "stratagems.json")
REF_ENUMS = {"ProjectileType": "projectile", "ExplosionType": "explosion",
             "DamageInfoType": "damage", "BeamType": "beam", "ArcType": "arc"}
MAX_DEPTH = 3

_index = None      # entity -> [(wrapper name, record type, record bytes)]
_leafs = {}        # record type -> [(offset, kind, storage_size)]


def entity_index():
    global _index
    if _index is not None:
        return _index
    names = hd2db.type_names()
    data = hd2db.blob("generated_entities.dl_bin")
    _index = collections.defaultdict(list)
    for magic, typ, size in hd2db.instances(data):
        wrapper = names.get(typ)
        if not wrapper:
            continue
        rtype, stride, shape = hd2db.record_type(wrapper)
        if shape != "keyed" or not stride:
            continue
        try:
            t = hd2db.KeyedTable(data, magic, size, rtype, stride)
        except ValueError:
            continue
        for ent in t.index:
            _index[ent].append((wrapper, rtype, t.record(ent)))
    return _index


def leafs(type_name, base=0, depth=0):
    """[(offset, kind)] for enum references and u64 hashes inside `type_name`, recursively."""
    key = (type_name, base)
    if base == 0 and type_name in _leafs:
        return _leafs[type_name]
    tl = gostructs.typelib()["types"]
    t = tl.get(type_name)
    out = []
    if t and depth < 6:
        for m in t["members"]:
            n = m["inline_array_len"] if m["atom"] == "INLINE_ARRAY" else 1
            if m["atom"] not in ("POD", "INLINE_ARRAY") or n == 0:
                continue
            elem = m["size"] // n
            for i in range(n):
                o = base + m["offset"] + i * elem
                if m["type"] in REF_ENUMS and elem == 4:
                    out.append((o, REF_ENUMS[m["type"]]))
                elif m["storage"] == "UINT64":
                    out.append((o, "hash"))
                elif m["storage"] == "STRUCT":
                    out.extend(leafs(m["type"], o, depth + 1))
    if base == 0:
        _leafs[type_name] = out
    return out


def walk(entity, depth=0, seen=None):
    """-> {kind: {id: [where, ...]}} for one entity and the entities it references."""
    seen = seen if seen is not None else set()
    refs = collections.defaultdict(lambda: collections.defaultdict(list))
    if entity in seen:
        return refs
    seen.add(entity)
    idx = entity_index()
    for wrapper, rtype, rec in idx.get(entity, ()):
        for off, kind in leafs(rtype):
            if kind == "hash":
                h = struct.unpack_from("<Q", rec, off)[0]
                if h and h in idx and depth < MAX_DEPTH:
                    sub = walk(h, depth + 1, seen)
                    for k, d in sub.items():
                        for i, w in d.items():
                            refs[k][i].extend(w)
            else:
                v = struct.unpack_from("<I", rec, off)[0]
                if v:
                    refs[kind][v].append("%s+%d@%016X" % (rtype, off, entity))
    return refs


def load_stratagems():
    with open(JSON_PATH, encoding="utf-8") as f:
        groups = json.load(f)
    out = []
    for g in groups:
        for it in g.get("StratagemSettings", {}).get("items", []):
            out.append(it)
    return out


def main(argv):
    strats = load_stratagems()
    idx = entity_index()
    result = []
    for s in strats:
        payload = s.get("payload") or []
        refs = collections.defaultdict(dict)
        present = 0
        for h in payload:
            if h in idx:
                present += 1
            for k, d in walk(h).items():
                refs[k].update(d)
        result.append({
            "id": s.get("id"), "type": s.get("type"), "debug_name": s.get("debug_name"),
            "selectable": s.get("selectable"), "uses": s.get("uses"),
            "cooldown": s.get("cooldown_duration_success"),
            "payload": ["%016X" % h for h in payload],
            "payload_paths": [hashnames.name(h) for h in payload],
            "payload_entities_found": present,
            "rows": {k: {str(i): w for i, w in sorted(d.items())} for k, d in refs.items()},
        })
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)

    if argv:
        for r in result:
            if any(a.lower() in (r["debug_name"] or "").lower() for a in argv):
                print("%s  id=%s uses=%s cooldown=%s" % (r["debug_name"], r["id"], r["uses"], r["cooldown"]))
                for p, path in zip(r["payload"], r["payload_paths"]):
                    print("   payload %s %s" % (p, path))
                for k, d in r["rows"].items():
                    for i, w in d.items():
                        print("   %-10s %-5s via %s" % (k, i, ", ".join(sorted(set(x.split("@")[0] for x in w)))[:150]))
        return 0

    sel = [r for r in result if r["selectable"]]
    with_payload = [r for r in sel if r["payload"]]
    found = [r for r in with_payload if r["payload_entities_found"]]
    with_rows = [r for r in found if any(r["rows"].get(k) for k in ("projectile", "explosion", "damage", "beam", "arc"))]
    print("stratagems in the JSON snapshot: %d  selectable: %d" % (len(result), len(sel)))
    print("selectable with a payload: %d   payload entity present in current data: %d   reaching settings rows: %d"
          % (len(with_payload), len(found), len(with_rows)))
    print("no rows reached (%d):" % (len(found) - len(with_rows)))
    for r in found:
        if r not in with_rows:
            print("    ", r["debug_name"])
    print("payload entity missing from current data (%d):" % (len(with_payload) - len(found)))
    for r in with_payload:
        if r not in found:
            print("    ", r["debug_name"])
    print("-> %s" % os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
