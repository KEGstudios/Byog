# -*- coding: utf-8 -*-
"""Field names for typelib types, taken from FileDiver's Go structs.

The shipped typelib has no string table (see tools/dump_typelib.py), so member
NAMES and COMMENTS only exist in FileDiver's datalibrary/*.go. Those structs
are read with encoding/binary, i.e. they are PACKED and carry explicit `_`
padding, so every Go field has a computable byte offset.

This module computes those offsets and joins the Go names onto the typelib
layout BY OFFSET. A join is only trusted (`names_ok`) when

  * every Go type in the struct could be sized,
  * the Go struct's total size equals the typelib size, and
  * every named Go field starts exactly on a typelib member offset.

Typelib members with no Go field at their offset (extra bitfield bits, tail of
a merged array) are reported with the generated name `m<index>`.

    python tools/gostructs.py ProjectileInfo DamageInfo      # print layouts
    python tools/gostructs.py --audit                        # join statistics
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GO_DIR = os.path.join(ROOT, "reference", "filediver", "datalibrary")
TYPELIB_JSON = os.path.join(ROOT, "data", "typelib_all.json")

PRIMS = {
    "uint8": 1, "int8": 1, "bool": 1, "byte": 1,
    "uint16": 2, "int16": 2,
    "uint32": 4, "int32": 4, "float32": 4,
    "uint64": 8, "int64": 8, "float64": 8,
    "stingray.Hash": 8, "stingray.ThinHash": 4,
    "mgl32.Vec2": 8, "mgl32.Vec3": 12, "mgl32.Vec4": 16, "mgl32.Quat": 16,
    "mgl32.Mat4": 64, "mgl32.Mat3": 36,
    "DLArray": 16, "DLString": 8, "DLPtr": 8, "DLHash": 4,
}

_STRUCT_RE = re.compile(r"^type\s+(\w+)\s+struct\s*\{\s*$")
_ALIAS_RE = re.compile(r"^type\s+(\w+)\s+([\w.\[\]]+)\s*(?://.*)?$")
_FIELD_RE = re.compile(r"^\s*(\w+)\s+([^\s/`][^/`]*?)\s*(?:`[^`]*`)?\s*(?://\s*(.*))?$")
_ARRAY_RE = re.compile(r"^\[(\d+)\](.+)$")


def _parse_dir(go_dir, prefix=""):
    """-> (structs {name: [(field, gotype, comment)]}, aliases {name: gotype})"""
    structs, aliases = {}, {}
    for path in sorted(glob.glob(os.path.join(go_dir, "*.go"))):
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
        cur, fields = None, None
        for line in lines:
            if cur is None:
                m = _STRUCT_RE.match(line)
                if m:
                    cur, fields = m.group(1), []
                    continue
                m = _ALIAS_RE.match(line)
                if m and m.group(2) != "struct":
                    aliases.setdefault(prefix + m.group(1), m.group(2))
                continue
            if line.startswith("}"):
                structs.setdefault(prefix + cur, fields)   # first definition wins
                cur = None
                continue
            s = line.strip()
            if not s or s.startswith("//"):
                continue
            m = _FIELD_RE.match(line)
            if m:
                fields.append((m.group(1), m.group(2).strip(), (m.group(3) or "").strip()))
    return structs, aliases


class GoLayouts:
    def __init__(self, go_dir=GO_DIR):
        self.structs, self.aliases = _parse_dir(go_dir)
        _, enum_aliases = _parse_dir(os.path.join(go_dir, "enum"), prefix="enum.")
        self.aliases.update(enum_aliases)
        self._size = {}

    def sizeof(self, gotype, _stack=()):
        """Byte size of a Go type as encoding/binary reads it, or None if unknown."""
        if gotype in self._size:
            return self._size[gotype]
        size = None
        m = _ARRAY_RE.match(gotype)
        if gotype in PRIMS:
            size = PRIMS[gotype]
        elif m:
            inner = self.sizeof(m.group(2), _stack)
            size = None if inner is None else int(m.group(1)) * inner
        elif gotype in typelib()["types"]:
            # nested typelib type: the typelib's own size is authoritative
            size = typelib()["types"][gotype]["size"]
        elif gotype in self.aliases:
            size = self.sizeof(self.aliases[gotype], _stack)
        elif gotype in self.structs and gotype not in _stack:
            total = 0
            for _, ft, _c in self.structs[gotype]:
                s = self.sizeof(ft, _stack + (gotype,))
                if s is None:
                    total = None
                    break
                total += s
            size = total
        self._size[gotype] = size
        return size

    def fields(self, struct_name):
        """-> ([(offset, size, name, gotype, comment)], total_size) or (None, None)."""
        if struct_name not in self.structs:
            return None, None
        out, off = [], 0
        for name, gotype, comment in self.structs[struct_name]:
            s = self.sizeof(gotype)
            if s is None:
                return None, None
            if name != "_":
                out.append((off, s, name, gotype, comment))
            off += s
        return out, off


_TL = None
_GO = None


def typelib():
    global _TL
    if _TL is None:
        with open(TYPELIB_JSON, encoding="utf-8") as f:
            _TL = json.load(f)
    return _TL


def go_layouts():
    global _GO
    if _GO is None:
        _GO = GoLayouts()
    return _GO


STORAGE_SIZE = {"INT8": 1, "UINT8": 1, "INT16": 2, "UINT16": 2, "INT32": 4, "UINT32": 4,
                "INT64": 8, "UINT64": 8}


def _fits(members_by_off, members, target, size):
    """Can a Go field of `size` bytes start at typelib offset `target`?"""
    def plain_array(x):
        return x["atom"] == "INLINE_ARRAY" and x["storage"] != "STRUCT"

    m = members_by_off.get(target)
    if m is not None:
        if m["size"] == size or m["atom"] == "BITFIELD":
            return True
        if m["size"] > size:
            return plain_array(m)            # Go names the elements one by one
        # Go field is wider: it may swallow padding, or span whole members
        end = target + size
        nxt = min([x["offset"] for x in members if x["offset"] > target] or [end])
        return end <= nxt or any(x["offset"] == end for x in members)             or end == max(x["offset"] + x["size"] for x in members)
    for x in members:                        # a later element of a plain inline array
        if x["offset"] < target < x["offset"] + x["size"] and plain_array(x):
            return True
    return False


def layout(type_name):
    """Typelib layout of `type_name` with Go names joined on.

    FileDiver's Go structs are sometimes OLDER than the typelib it embeds (the
    game inserted members since). The join therefore walks the Go fields with
    a running byte `delta`; when a field stops landing on a typelib member the
    smallest shift that makes the next few fields fit again is adopted.

    Per-member `name_conf`:
      "exact"    Go offset == typelib offset, sizes agree (delta 0)
      "shifted"  matched after a non-zero delta (Go struct is stale before it)
      ""         no Go name (generated `m<index>`)

    -> {"name","hash","size","names_ok","why","members":[...]}; `names_ok`
       is True only when the whole struct joined at delta 0.
    """
    t = typelib()["types"].get(type_name)
    if not t:
        return None
    go = go_layouts()
    members = [dict(m, name="m%d" % i, go_type="", comment="", name_conf="")
               for i, m in enumerate(t["members"])]
    by_off = {}
    for m in members:
        by_off.setdefault(m["offset"], m)
    why, shifted, unmatched = "no Go struct", 0, 0
    for candidate in ("raw" + type_name, type_name):
        gfields, gsize = go.fields(candidate)
        if gfields is None:
            if candidate in go.structs:
                why = "Go struct has a type of unknown size"
            continue
        why, delta = "", 0
        for i, (o, sz, name, gotype, comment) in enumerate(gfields):
            if not _fits(by_off, members, o + delta, sz):
                found = None
                window = gfields[i:i + 5]
                for step in range(1, 1024):
                    for d in (delta + step, delta - step):
                        if all(_fits(by_off, members, fo + d, fs) for fo, fs, _n, _t, _c in window):
                            found = d
                            break
                    if found is not None:
                        break
                if found is None:
                    unmatched += 1
                    continue
                delta = found
            m = by_off.get(o + delta)
            if m is None or m["name_conf"]:
                continue                     # sub-field of an array/struct, or already named
            m["name"], m["go_type"], m["comment"] = name, gotype, comment
            m["name_conf"] = "exact" if delta == 0 else "shifted"
            shifted += delta != 0
        if gsize != t["size"] and not why:
            why = "Go size %d != typelib size %d" % (gsize, t["size"])
        if shifted:
            why += "; %d fields matched after a shift" % shifted
        if unmatched:
            why += "; %d Go fields unmatched" % unmatched
        break
    return {"name": type_name, "hash": t["hash"], "size": t["size"],
            "names_ok": not why, "why": why.strip("; "), "members": members}


def field(type_name, field_name):
    """The typelib member that FileDiver calls `field_name`, or None."""
    L = layout(type_name)
    if not L:
        return None
    for m in L["members"]:
        if m["name"] == field_name and m["name_conf"]:
            return m
    return None


def print_layout(type_name):
    L = layout(type_name)
    if not L:
        print("## %s: not in typelib" % type_name)
        return
    print("## %s  hash=%s size=%d members=%d names_ok=%s %s" % (
        L["name"], L["hash"], L["size"], len(L["members"]), L["names_ok"], L["why"]))
    for m in L["members"]:
        st = m["storage"]
        if m["atom"] == "INLINE_ARRAY":
            st += "[%d]" % m["inline_array_len"]
        elif m["atom"] == "ARRAY":
            st += "[]"
        elif m["atom"] == "BITFIELD":
            st += ":%d@%d" % (m["bits"], m["bit_offset"])
        tn = m["type"] if m["type"] != "(builtin)" else ""
        print("  +%-5d sz=%-5d %-14s %-28s %-8s %-34s %s" % (
            m["offset"], m["size"], st, tn, m["name_conf"], m["name"], m["comment"][:120]))


def audit():
    tl = typelib()["types"]
    go = go_layouts()
    ok = bad = 0
    for name in sorted(tl):
        if name not in go.structs and "raw" + name not in go.structs:
            continue
        L = layout(name)
        if L["names_ok"]:
            ok += 1
        else:
            bad += 1
            print("  MISMATCH %-44s %s" % (name, L["why"]))
    print("typelib types with a Go struct: %d joined cleanly, %d mismatched" % (ok, bad))


if __name__ == "__main__":
    if sys.argv[1:] == ["--audit"]:
        audit()
    else:
        for n in sys.argv[1:]:
            print_layout(n)
            print()
