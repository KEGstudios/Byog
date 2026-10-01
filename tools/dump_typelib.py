# -*- coding: utf-8 -*-
"""Dump the game's dl_library.dl_typelib to JSON without needing Go.

This is a Python port of FileDiver's datalibrary.ParseTypeLib (datalib.go).
It replaces reference/hd2-lua-mod-skill/tools/dump_typelib/main.go, which
needs a Go toolchain.

    python tools/dump_typelib.py                # writes data/typelib_all.json

Layout facts (64-bit column of every width-dependent pair is used):

    header            4s + 8*u32                          = 36 bytes
    type hashes       u32 * type_count
    enum hashes       u32 * enum_count
    type descs        36 bytes each
    enum descs        32 bytes each
    member descs      72 bytes each
    enum value descs  16 bytes each
    enum alias descs   8 bytes each
    default data      default_value_size bytes
    strings           typeinfo_strings_size bytes  (0 in shipped builds!)

IMPORTANT: the shipped typelib has NO string table, so it carries layout only
(offset / size / alignment / type hash / atom / storage). Type names come from
FileDiver's hashes/dl_type_names.txt (djb2 of the name == type hash, so they
are self-verifying). MEMBER names are not in the typelib at all; they come
from FileDiver's hand-maintained Go structs (see tools/gostructs.py).
"""
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FD = os.path.join(ROOT, "reference", "filediver")
TYPELIB = os.path.join(FD, "datalibrary", "dl_library.dl_typelib")
TYPE_NAMES = os.path.join(FD, "hashes", "dl_type_names.txt")
OUT = os.path.join(ROOT, "data", "typelib_all.json")

ATOMS = ["POD", "ARRAY", "INLINE_ARRAY", "BITFIELD"]
STORAGES = [
    "INT8", "INT16", "INT32", "INT64", "UINT8", "UINT16", "UINT32", "UINT64",
    "FP32", "FP64",
    "ENUM_INT8", "ENUM_INT16", "ENUM_INT32", "ENUM_INT64",
    "ENUM_UINT8", "ENUM_UINT16", "ENUM_UINT32", "ENUM_UINT64",
    "STR", "PTR", "STRUCT",
]
NONE = 0xFFFFFFFF


def dlsum(name):
    r = 5381
    for ch in name:
        r = (r * 33 + ord(ch)) & 0xFFFFFFFF
    return (r - 5381) & 0xFFFFFFFF


def load_type_names(path=TYPE_NAMES):
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            t = line.strip()
            if not t or t.startswith("//"):
                continue
            out[dlsum(t)] = t
    return out


def parse(data, names):
    magic = data[:4]
    if magic != b"LTLD":
        raise ValueError("not a typelib: magic %r" % magic)
    (version, type_count, enum_count, member_count, enum_value_count,
     enum_alias_count, default_size, strings_size) = struct.unpack_from("<8I", data, 4)
    pos = 36
    type_hashes = struct.unpack_from("<%dI" % type_count, data, pos); pos += 4 * type_count
    enum_hashes = struct.unpack_from("<%dI" % enum_count, data, pos); pos += 4 * enum_count
    type_descs = [struct.unpack_from("<9I", data, pos + 36 * i) for i in range(type_count)]
    pos += 36 * type_count
    enum_descs = [struct.unpack_from("<IIB3xIIIII", data, pos + 32 * i) for i in range(enum_count)]
    pos += 32 * enum_count
    member_descs = [struct.unpack_from("<IIIBBHI6III I16x".replace(" ", ""), data, pos + 72 * i)
                    for i in range(member_count)]
    pos += 72 * member_count
    enum_values = [struct.unpack_from("<IIQ", data, pos + 16 * i) for i in range(enum_value_count)]
    pos += 16 * enum_value_count
    enum_aliases = [struct.unpack_from("<II", data, pos + 8 * i) for i in range(enum_alias_count)]
    pos += 8 * enum_alias_count
    pos += default_size
    strings = data[pos:pos + strings_size]
    pos += strings_size
    if pos != len(data):
        raise ValueError("typelib size mismatch: parsed %d of %d bytes" % (pos, len(data)))

    def tname(h):
        if h == 0:
            return "(builtin)"
        return names.get(h) or ("0x%08X" % h)

    types = {}
    for idx, td in enumerate(type_descs):
        (name_off, flags, size32, size64, align32, align64, mcount, mstart, comment_off) = td
        h = type_hashes[idx]
        members = []
        for i in range(mstart, min(mstart + mcount, member_count)):
            (m_name_off, m_comment_off, m_unknown_off, atom, storage, bf_or_len, type_id,
             s32, s64, a32, a64, o32, o64, def_off, def_size, m_flags) = member_descs[i]
            members.append({
                "index": i - mstart,
                "offset": o64,
                "size": s64,
                "alignment": a64,
                "atom": ATOMS[atom] if atom < len(ATOMS) else "ATOM_%d" % atom,
                "storage": STORAGES[storage] if storage < len(STORAGES) else "STORAGE_%d" % storage,
                "type_hash": "0x%08X" % type_id,
                "type": tname(type_id),
                "inline_array_len": bf_or_len,
                "bits": bf_or_len & 0xFF,
                "bit_offset": bf_or_len >> 8,
                "name_offset": m_name_off,
                "flags": m_flags,
            })
        types[tname(h)] = {
            "name": tname(h),
            "hash": "0x%08X" % h,
            "named": h in names,
            "flags": flags,
            "size": size64,
            "alignment": align64,
            "members": members,
        }

    enums = {}
    for idx, ed in enumerate(enum_descs):
        (name_off, flags, storage, vcount, vstart, acount, astart, comment_off) = ed
        h = enum_hashes[idx]
        values = [enum_values[i][2] for i in range(vstart, min(vstart + vcount, enum_value_count))]
        enums[tname(h)] = {
            "name": tname(h),
            "hash": "0x%08X" % h,
            "named": h in names,
            "storage": STORAGES[storage] if storage < len(STORAGES) else "STORAGE_%d" % storage,
            "value_count": vcount,
            "values": values,
        }

    header = {
        "version": version, "type_count": type_count, "enum_count": enum_count,
        "member_count": member_count, "enum_value_count": enum_value_count,
        "enum_alias_count": enum_alias_count, "default_value_size": default_size,
        "typeinfo_strings_size": strings_size,
    }
    return {"header": header, "types": types, "enums": enums}


def main():
    names = load_type_names()
    with open(TYPELIB, "rb") as f:
        data = f.read()
    tl = parse(data, names)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(tl, f, indent=1)
    named_t = sum(1 for t in tl["types"].values() if t["named"])
    named_e = sum(1 for e in tl["enums"].values() if e["named"])
    print("header:", tl["header"])
    print("types=%d (named %d)  enums=%d (named %d)  -> %s" % (
        len(tl["types"]), named_t, len(tl["enums"]), named_e, os.path.relpath(OUT, ROOT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
