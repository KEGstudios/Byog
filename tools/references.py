# -*- coding: utf-8 -*-
"""Which records refer to a row of a settings table?

Row ids are typed in the typelib (ExplosionType, DamageInfoType, ProjectileType...), so every
4-byte member of that type, in every table of the bundled datalibrary we can read, is a reference.
Limits, stated because "nothing refers to this row" is only as good as the scan:
  * only members stored inline in a record are followed (nested structs and inline arrays are;
    dynamic arrays inside records are not),
  * only tables present in the FileDiver mirror are seen (it covers part of the game's data),
  * ids built by code are invisible.

    python tools/references.py ExplosionType ExplosionSettings
"""
import collections
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import gostructs  # noqa: E402
import hd2db  # noqa: E402

_cache = {}


def member_offsets(target, type_name, base=0, seen=()):
    """Offsets of the inline 4-byte members typed `target` in a record of `type_name`."""
    types = gostructs.typelib()["types"]
    out = []
    t = types.get(type_name)
    if not t or type_name in seen:
        return out
    for m in t["members"]:
        o = base + m["offset"]
        n = m.get("inline_array_len") or 1
        if m["atom"] not in ("POD", "INLINE_ARRAY"):
            continue
        if m["type"] == target:
            out += [o + 4 * k for k in range(n)]
        elif m["type"] in types and m["type"] != type_name:
            for k in range(n):
                out += member_offsets(target, m["type"], o + k * types[m["type"]]["size"], seen + (type_name,))
    return out


def users(target, own_table):
    """{row id: [(table wrapper, record key, offset)]}; the id field of `own_table`'s rows is not a reference."""
    key = (target, own_table)
    if key in _cache:
        return _cache[key]
    found = collections.defaultdict(list)
    names = hd2db.type_names()
    for fn in sorted(os.listdir(hd2db.DL_DIR)):
        if not (fn.startswith("generated_") and fn.endswith(".dl_bin")):
            continue
        data = hd2db.blob(fn)
        for magic, typ, size in hd2db.instances(data):
            wrapper = names.get(typ)
            rtype, stride, shape = hd2db.record_type(wrapper) if wrapper else (None, None, None)
            if not shape or not stride:
                continue
            offsets = member_offsets(target, rtype)
            if not offsets:
                continue
            try:
                t = (hd2db.RowTable if shape == "rows" else hd2db.KeyedTable)(data, magic, size, rtype, stride)
            except ValueError:
                continue
            if shape == "rows":
                records = [(struct.unpack_from("<I", t.record(i), 0)[0], t.record(i)) for i in range(t.count)]
            else:
                records = [("%016X" % e, t.record(e)) for e in t.index]
            for record_key, rec in records:
                for o in offsets:
                    if wrapper == own_table and o == 0:
                        continue
                    v = struct.unpack_from("<I", rec, o)[0]
                    if v:
                        found[v].append((wrapper, record_key, o))
    _cache[key] = found
    return found


def spare_rows(target, own_table):
    """Ids of `own_table` rows that nothing we can read refers to, ascending."""
    u = users(target, own_table)
    return sorted(i for i in hd2db.table(own_table).by_id() if i and not u.get(i))


def pointer_words(record_type):
    """Offsets of the 4-byte words of a record that hold pointers or array heads (absolute in memory)."""
    out = []
    for m in gostructs.typelib()["types"][record_type]["members"]:
        if m["atom"] in ("POD", "INLINE_ARRAY", "BITFIELD"):
            continue
        out += list(range(m["offset"], m["offset"] + m["size"], 4))
    return out


if __name__ == "__main__":
    target, table = sys.argv[1], sys.argv[2]
    u = users(target, table)
    spare = spare_rows(target, table)
    print("%s: %d rows, %d with no referrer in the tables we read" % (table, len(hd2db.table(table).by_id()), len(spare)))
    print("referrers by table:", dict(collections.Counter(w for v in u.values() for w, _k, _o in v)))
    rtype = hd2db.record_type(table)[0]
    print("pointer words of %s: %s" % (rtype, pointer_words(rtype)))
    print("members that are not plain:", [(m.get("name"), m["atom"], m["offset"], m["size"])
                                          for m in gostructs.typelib()["types"][rtype]["members"]
                                          if m["atom"] not in ("POD", "INLINE_ARRAY", "BITFIELD")])
