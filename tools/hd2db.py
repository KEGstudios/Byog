# -*- coding: utf-8 -*-
"""Offline reader for FileDiver's plaintext datalibrary mirror.

Two container shapes exist (both start with a 24-byte LDLD instance header:
'LDLD', u32 version=1, u32 type hash, u32 payload size, u8 is64, 7 pad):

  row table   (generated_*_settings.dl_bin)
      payload = DLArray{u64 offset, u64 count} + count * record
      In the FILE the first u64 is an offset relative to the payload start
      (normally 16); IN MEMORY it is an absolute pointer.

  keyed table (component tables inside generated_entities.dl_bin)
      payload = buckets * {u64 entity hash, u32 record index, u32 0}
                + records * stride
      buckets == 2 * live entities; the record stride comes from the typelib
      (second member of the XxxComponentData wrapper type).

Nothing here hard-codes a table size or a record count: both are derived from
the payload size and the typelib stride, then checked against the content.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import gostructs  # noqa: E402
from dump_typelib import dlsum, load_type_names  # noqa: E402

DL_DIR = os.path.join(ROOT, "reference", "filediver", "datalibrary")
HEADER = 24
_FMT = {"INT8": "<b", "UINT8": "<B", "INT16": "<h", "UINT16": "<H", "INT32": "<i",
        "UINT32": "<I", "INT64": "<q", "UINT64": "<Q", "FP32": "<f", "FP64": "<d"}

_files = {}
_names = None


def type_names():
    global _names
    if _names is None:
        _names = load_type_names()
    return _names


def blob(filename):
    if filename not in _files:
        with open(os.path.join(DL_DIR, filename), "rb") as f:
            _files[filename] = f.read()
    return _files[filename]


def instances(data):
    """-> [(magic_offset, type_hash, payload_size)] for every LDLD v1 block."""
    out, i = [], data.find(b"LDLD")
    while i >= 0:
        if i + 16 <= len(data):
            ver, typ, size = struct.unpack_from("<III", data, i + 4)
            if ver == 1 and typ != 0 and i + HEADER + size <= len(data):
                out.append((i, typ, size))
        i = data.find(b"LDLD", i + 1)
    return out


def record_type(wrapper_name):
    """XxxComponentData / XxxSettings -> (record type name, stride, 'keyed'|'rows'|None)."""
    tl = gostructs.typelib()["types"]
    t = tl.get(wrapper_name)
    if not t:
        return None, None, None
    ms = t["members"]
    if len(ms) >= 2 and ms[0]["type"] == "ComponentIndexData":
        rt = ms[1]["type"]
        return rt, tl[rt]["size"] if rt in tl else None, "keyed"
    if len(ms) == 1 and ms[0]["atom"] == "ARRAY":
        rt = ms[0]["type"]
        return rt, tl[rt]["size"] if rt in tl else None, "rows"
    return None, None, None


class RowTable:
    def __init__(self, data, magic, size, rtype, stride):
        self.data, self.magic, self.size, self.rtype, self.stride = data, magic, size, rtype, stride
        self.base = magic + HEADER
        off, count = struct.unpack_from("<QQ", data, self.base)
        if off != 16 or 16 + count * stride > size:
            raise ValueError("%s: unexpected row layout (offset=%d count=%d stride=%d size=%d)"
                             % (rtype, off, count, stride, size))
        self.count = count
        self.first = self.base + off
        self.tail = size - 16 - count * stride   # strings / arrays the rows point to

    def record_offset(self, i):
        """Payload-relative offset of row i (what an in-memory patcher adds to payload start)."""
        return 16 + i * self.stride

    def record(self, i):
        o = self.first + i * self.stride
        return self.data[o:o + self.stride]

    def rows(self):
        return [self.record(i) for i in range(self.count)]

    def by_id(self, id_at=0):
        out = {}
        for i in range(self.count):
            out.setdefault(struct.unpack_from("<I", self.data, self.first + i * self.stride + id_at)[0], i)
        return out


class KeyedTable:
    def __init__(self, data, magic, size, rtype, stride):
        self.data, self.magic, self.size, self.rtype, self.stride = data, magic, size, rtype, stride
        self.base = magic + HEADER
        fits = []
        count = live = 0
        top = -1
        off = 0
        while off + 16 <= size:
            hv, ix, pad = struct.unpack_from("<QII", data, self.base + off)
            if pad != 0 or ix > 1000000:
                break
            count += 1
            if hv:
                live += 1
                top = max(top, ix)
            off += 16
            rest = size - count * 16
            if count == 2 * live and rest > 0 and rest % stride < 8:
                n = rest // stride
                if top < n <= live + 2:
                    fits.append((count, n, rest % stride))
        if len(fits) != 1:
            raise ValueError("%s: %d bucket layouts fit (need exactly 1)" % (rtype, len(fits)))
        self.buckets, self.count, self.slack = fits[0]
        self.index = {}
        for k in range(self.buckets):
            hv, ix, _ = struct.unpack_from("<QII", data, self.base + k * 16)
            if hv and hv not in self.index:
                self.index[hv] = ix

    def record_offset(self, entity):
        ix = self.index.get(entity)
        return None if ix is None else self.buckets * 16 + ix * self.stride

    def record(self, entity):
        o = self.record_offset(entity)
        return None if o is None else self.data[self.base + o:self.base + o + self.stride]


_tables = {}


def table(wrapper_name, filename=None):
    """Find a table by its wrapper type name. Searches every bundled .dl_bin unless told one."""
    key = (wrapper_name, filename)
    if key in _tables:
        return _tables[key]
    rtype, stride, shape = record_type(wrapper_name)
    if not shape:
        raise KeyError("%s is not a known table wrapper" % wrapper_name)
    want = dlsum(wrapper_name)
    files = [filename] if filename else sorted(
        f for f in os.listdir(DL_DIR) if f.startswith("generated_") and f.endswith(".dl_bin"))
    found = []
    for fn in files:
        data = blob(fn)
        sig = b"LDLD" + struct.pack("<II", 1, want)
        i = data.find(sig)
        while i >= 0:
            size = struct.unpack_from("<I", data, i + 12)[0]
            found.append((fn, i, size))
            i = data.find(sig, i + 1)
    if not found:
        raise KeyError("%s (0x%08X) not found in the bundled datalibrary" % (wrapper_name, want))
    out = []
    for fn, magic, size in found:
        cls = RowTable if shape == "rows" else KeyedTable
        t = cls(blob(fn), magic, size, rtype, stride)
        t.file, t.wrapper, t.shape = fn, wrapper_name, shape
        out.append(t)
    _tables[key] = out[0] if len(out) == 1 else out
    return _tables[key]


def decode(rec, type_name, base=0, depth=0):
    """Record bytes -> ordered [(offset, name, value, member)] using the joined layout."""
    L = gostructs.layout(type_name)
    out = []
    for m in L["members"]:
        o = base + m["offset"]
        st = m["storage"].replace("ENUM_", "")
        if m["atom"] == "POD" and st in _FMT:
            v = struct.unpack_from(_FMT[st], rec, o)[0]
        elif m["atom"] == "INLINE_ARRAY" and st in _FMT:
            n = m["inline_array_len"]
            v = list(struct.unpack_from("<%d%s" % (n, _FMT[st][1]), rec, o))
        elif m["atom"] == "BITFIELD" and st in _FMT:
            raw = struct.unpack_from(_FMT[st], rec, o)[0]
            v = (raw >> m["bit_offset"]) & ((1 << m["bits"]) - 1)
        elif m["atom"] == "POD" and m["type"] in ("CApiVector3", "CApiVector2", "CApiVector4"):
            n = m["size"] // 4
            v = [round(x, 6) for x in struct.unpack_from("<%df" % n, rec, o)]
        else:
            v = rec[o:o + min(m["size"], 32)].hex() + ("..." if m["size"] > 32 else "")
        out.append((m["offset"], m["name"], v, m))
    return out


def show(rec, type_name, only=None):
    for off, name, v, m in decode(rec, type_name):
        if only and name not in only:
            continue
        if isinstance(v, float):
            v = round(v, 6)
        print("  +%-5d %-8s %-34s = %s" % (off, m["name_conf"], name, v))


if __name__ == "__main__":
    for fn in sorted(os.listdir(DL_DIR)):
        if fn.startswith("generated_") and fn.endswith(".dl_bin"):
            inst = instances(blob(fn))
            print("%-52s %9d bytes  %d LDLD blocks" % (fn, len(blob(fn)), len(inst)))
            if len(inst) <= 3:
                for magic, typ, size in inst:
                    print("    +%-8d %-48s size=%d" % (magic, type_names().get(typ, "0x%08X" % typ), size))
