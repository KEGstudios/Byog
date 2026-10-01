# -*- coding: utf-8 -*-
"""Second, independent source of member names: the game's own field names.

shalzuth/HelldiversData publishes data/components/<Type>.json: the member
names, types, defaults and descriptions of each type, dumped from a game build
whose typelib still carried its string table. Those are the ORIGINAL names
(snake_case), but from an OLDER build, so members added since are missing.

This module aligns such a schema onto the CURRENT typelib layout with a
sequence alignment over member types (Needleman-Wunsch): members inserted by
later builds become gaps instead of shifting every following name.

    python tools/schema_names.py ProjectileInfo ThrowableComponent

`merged_layout()` combines both name sources (FileDiver Go structs and this
schema) and says, per member, whether they agree.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import gostructs  # noqa: E402

SCHEMA_DIR = os.path.join(ROOT, "reference", "HelldiversData", "components")
PRIM = {"float": "FP32", "uint": "UINT32", "int": "INT32", "ulong": "UINT64",
        "long": "INT64", "byte": "UINT8", "ushort": "UINT16", "short": "INT16",
        "double": "FP64"}


def load_schema(type_name):
    """-> [(name, type, description, default)] in declaration order, or None."""
    path = os.path.join(SCHEMA_DIR, type_name + ".json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    fields = d.get(type_name)
    if not isinstance(fields, dict):
        return None
    return [(k, v.get("type", ""), v.get("description", ""), v.get("default"))
            for k, v in fields.items() if isinstance(v, dict)]


def _score(schema_type, m):
    """Type compatibility of a schema field and a typelib member; <0 = incompatible."""
    st = m["storage"].replace("ENUM_", "")
    if schema_type in PRIM:
        if m["storage"].startswith("ENUM_") or m["storage"] == "STRUCT":
            return -9
        if m["atom"] not in ("POD", "BITFIELD"):
            return -9
        if st == PRIM[schema_type]:
            return 2
        # a flag byte may have been repacked into a wider bitfield, and vice versa
        if m["atom"] == "BITFIELD" and schema_type in ("byte", "ushort", "uint"):
            return 1
        return -9
    if schema_type == "array":
        return 2 if m["atom"] in ("ARRAY", "INLINE_ARRAY") else -9
    if schema_type == "string":
        return 2 if st == "STR" else -9
    if m["type"] == schema_type:
        return 3
    if m["type"].startswith("0x") and (m["storage"] == "STRUCT" or m["storage"].startswith("ENUM_")):
        return 1                     # unnamed type hash: cannot confirm, cannot refute
    return -9


def align(type_name):
    """-> {member index: (schema name, schema type, description, default)}, stats dict; or (None, None)."""
    schema = load_schema(type_name)
    t = gostructs.typelib()["types"].get(type_name)
    if schema is None or t is None:
        return None, None
    M = t["members"]
    n, k = len(schema), len(M)
    GAP_M, GAP_S = -1, -2            # typelib member with no schema field / schema field dropped
    NEG = -10 ** 9
    best = [[NEG] * (k + 1) for _ in range(n + 1)]
    back = [[0] * (k + 1) for _ in range(n + 1)]
    best[0][0] = 0
    for j in range(1, k + 1):
        best[0][j], back[0][j] = best[0][j - 1] + GAP_M, 2
    for i in range(1, n + 1):
        best[i][0], back[i][0] = best[i - 1][0] + GAP_S, 3
        for j in range(1, k + 1):
            s = _score(schema[i - 1][1], M[j - 1])
            cands = [(best[i][j - 1] + GAP_M, 2), (best[i - 1][j] + GAP_S, 3)]
            if s >= 0:
                cands.append((best[i - 1][j - 1] + s, 1))
            best[i][j], back[i][j] = max(cands)
    out, i, j = {}, n, k
    dropped = 0
    while i > 0 or j > 0:
        b = back[i][j]
        if b == 1:
            out[j - 1] = schema[i - 1]
            i, j = i - 1, j - 1
        elif b == 2:
            j -= 1
        else:
            dropped += 1
            i -= 1
    stats = {"schema_fields": n, "members": k, "named": len(out),
             "new_members": k - len(out), "dropped_schema_fields": dropped}
    return out, stats


def _norm(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def merged_layout(type_name):
    """gostructs.layout() plus, per member: schema_name, schema_desc, names_agree.

    names_agree: True  both sources name the member and the names match
                 False both name it and they differ
                 None  only one (or neither) source names it
    """
    L = gostructs.layout(type_name)
    if not L:
        return None
    aligned, stats = align(type_name)
    L["schema_stats"] = stats
    for i, m in enumerate(L["members"]):
        s = aligned.get(i) if aligned else None
        m["schema_name"] = s[0] if s else ""
        m["schema_desc"] = s[2] if s else ""
        m["schema_default"] = s[3] if s else None
        if s and m["name_conf"]:
            a, b = _norm(m["name"]), _norm(s[0])
            m["names_agree"] = a == b or a in b or b in a
        else:
            m["names_agree"] = None
        # preferred display name: the game's own name when we have it
        m["best_name"] = m["schema_name"] or (m["name"] if m["name_conf"] else m["name"])
    return L


def print_merged(type_name):
    L = merged_layout(type_name)
    if not L:
        print("## %s: not in typelib" % type_name)
        return
    print("## %s  hash=%s size=%d  go:%s  schema:%s" % (
        L["name"], L["hash"], L["size"], "ok" if L["names_ok"] else (L["why"] or "-"), L["schema_stats"]))
    for m in L["members"]:
        st = m["storage"]
        if m["atom"] == "INLINE_ARRAY":
            st += "[%d]" % m["inline_array_len"]
        elif m["atom"] == "ARRAY":
            st += "[]"
        elif m["atom"] == "BITFIELD":
            st += ":%d@%d" % (m["bits"], m["bit_offset"])
        agree = {True: "==", False: "!=", None: "  "}[m["names_agree"]]
        tn = m["type"] if m["type"] != "(builtin)" else ""
        print("  +%-5d sz=%-4d %-13s %-22s %-34s %s %-36s %s" % (
            m["offset"], m["size"], st, tn[:22], m["schema_name"], agree,
            m["name"] if m["name_conf"] else "", (m["schema_desc"] or m["comment"])[:100]))


if __name__ == "__main__":
    for n in sys.argv[1:]:
        print_merged(n)
        print()
