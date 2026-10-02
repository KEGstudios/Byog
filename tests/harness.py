# -*- coding: utf-8 -*-
"""Offline harness: runs an addon on LuaJIT (lupa) against a fake process.

What is real and what is fake:

* The Lua runtime is LuaJIT with its REAL ffi library, so buffers, casts and integer
  conversions behave exactly as in the game.
* The Windows API is fake. The addon fetches every function through a resolver; the test
  resolver (`HD2ST_TEST_RESOLVER`) returns Lua functions that are type-strict (a number where
  a pointer is expected is an error, as with real FFI) and that forward to this module.
* Memory is a FakeMemory: regions with state / protection / type / allocation base and a set
  of pages that are "not present". Every read is recorded, so tests can assert what the addon
  touched (for example: never a page that is not in memory, never more than the frame budget).

The fake clock only advances when the addon works: each API call costs a little, each byte
read costs a little more. That makes "work per frame" measurable and deterministic.
"""
import hashlib
import json
import os
import shutil
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from lupa.luajit21 import LuaRuntime  # noqa: E402

import hd2db  # noqa: E402
import pack_addon  # noqa: E402
from dump_typelib import dlsum  # noqa: E402

MEM_COMMIT, MEM_RESERVE, MEM_FREE = 0x1000, 0x2000, 0x10000
MEM_PRIVATE, MEM_MAPPED, MEM_IMAGE = 0x20000, 0x40000, 0x1000000
PAGE_NOACCESS, PAGE_READONLY, PAGE_READWRITE, PAGE_GUARD = 0x01, 0x02, 0x04, 0x100
PAGE_EXECUTE_READ = 0x20
ADDRESS_END = 0x7FFFFFFF0000
PAGE = 4096


def page_up(n):
    return (n + PAGE - 1) & ~(PAGE - 1)


class FakeMemory:
    def __init__(self):
        self.regions = []          # sorted by base
        self.read_log = []         # (address, size, ok)
        self.absent_reads = 0      # reads that touched a page marked as not present
        self.bytes_read = 0
        self.writes = []           # (address, bytes) accepted by the fake WriteProcessMemory
        self.protects = []         # (page address, new protection) accepted by the fake VirtualProtect
        self.write_ignored = False # True: writes "succeed" but change nothing (read-back must notice)

    def add(self, base, data, protect=PAGE_READWRITE, mtype=MEM_PRIVATE, state=MEM_COMMIT,
            allocation=None, absent=()):
        size = page_up(len(data))
        region = dict(base=base, size=size, protect=protect, type=mtype, state=state,
                      allocation=base if allocation is None else allocation,
                      data=bytearray(data) + bytearray(size - len(data)), absent=set(absent))
        for r in self.regions:
            if base < r["base"] + r["size"] and r["base"] < base + size:
                raise ValueError("overlapping fake regions")
        self.regions.append(region)
        self.regions.sort(key=lambda r: r["base"])
        return region

    def find(self, address):
        # regions are kept sorted by base; tests may also edit the list directly
        lo, hi = 0, len(self.regions)
        while lo < hi:
            mid = (lo + hi) // 2
            if self.regions[mid]["base"] <= address:
                lo = mid + 1
            else:
                hi = mid
        if lo:
            r = self.regions[lo - 1]
            if r["base"] <= address < r["base"] + r["size"]:
                return r
        return None

    def query(self, address):
        """MEMORY_BASIC_INFORMATION (48 bytes) for the region holding `address`, or None."""
        address = int(address)
        if address >= ADDRESS_END:
            return None
        r = self.find(address)
        if r:
            return struct.pack("<QQIHHQIII4x", r["base"], r["allocation"], r["protect"], 0, 0,
                               r["size"], r["state"], r["protect"], r["type"])
        base = address & ~(PAGE - 1)
        end = ADDRESS_END
        for x in self.regions:
            if x["base"] > address:
                end = x["base"]
                break
        return struct.pack("<QQIHHQIII4x", base, 0, 0, 0, 0, end - base, MEM_FREE, PAGE_NOACCESS, 0)

    def read(self, address, size):
        address, size = int(address), int(size)
        r = self.find(address)
        ok = bool(r and r["state"] == MEM_COMMIT
                  and r["protect"] in (PAGE_READONLY, PAGE_READWRITE, PAGE_EXECUTE_READ)
                  and address + size <= r["base"] + r["size"])
        self.read_log.append((address, size, ok))
        if not ok:
            return None
        first = (address - r["base"]) // PAGE
        last = (address + size - 1 - r["base"]) // PAGE
        if any(p in r["absent"] for p in range(first, last + 1)):
            self.absent_reads += 1
        self.bytes_read += size
        o = address - r["base"]
        return bytes(r["data"][o:o + size])

    def present(self, address):
        r = self.find(int(address))
        if not r or r["state"] != MEM_COMMIT:
            return False
        return ((int(address) - r["base"]) // PAGE) not in r["absent"]

    def attributes(self, address):
        """PSAPI_WORKING_SET_EX_BLOCK bits: valid, Win32 protection (bits 4..14), shared (bit 15)."""
        if not self.present(address):
            return 0
        r = self.find(int(address))
        # "written" marks image pages the process has written to: copy-on-write made them private
        shared = r["type"] != MEM_PRIVATE and not r.get("written")
        return 1 | ((r["protect"] & 0x7FF) << 4) | (0x8000 if shared else 0)

    def allocation(self, address):
        """MEMORY_REGION_INFORMATION (48 bytes) of the allocation holding `address`, or None when free."""
        r = self.find(int(address))
        if not r:
            return None
        same = [x for x in self.regions if x["allocation"] == r["allocation"]]
        size = max(x["base"] + x["size"] for x in same) - r["allocation"]
        return struct.pack("<QIIQQ16x", r["allocation"], r["protect"], 0, size, size)

    def protect(self, address, size, protection):
        """Like VirtualProtect, at region granularity. -> old protection, or None."""
        r = self.find(int(address))
        if not r or r["state"] != MEM_COMMIT:
            return None
        old = r["protect"]
        r["protect"] = int(protection)
        self.protects.append((int(address), int(protection)))
        return old

    def write(self, address, data):
        """Like WriteProcessMemory: fails on read-only and no-access pages (it only forces
        execute-read ones, which tables never are)."""
        address = int(address)
        r = self.find(address)
        if not r or r["state"] != MEM_COMMIT or address + len(data) > r["base"] + r["size"]:
            return False
        if r["protect"] != PAGE_READWRITE:
            return False
        self.writes.append((address, bytes(data)))
        if not self.write_ignored:
            o = address - r["base"]
            r["data"][o:o + len(data)] = data
        return True

    def peek(self, address, fmt):
        r = self.find(int(address))
        return struct.unpack_from(fmt, r["data"], int(address) - r["base"])[0]

    def poke(self, address, fmt, value):
        r = self.find(int(address))
        struct.pack_into(fmt, r["data"], int(address) - r["base"], value)


# ------------------------------------------------------------------ world building
class Chain:
    """Lays LDLD blocks back to back inside one allocation and fixes their pointers."""

    def __init__(self, base, prefix=4):
        self.base = base
        self.data = bytearray(prefix)
        self.addresses = {}        # wrapper name -> [block address]

    def add(self, name, payload, gap=4, fix=None):
        """payload: bytes of the block's payload. fix(payload_bytearray, payload_address) patches pointers."""
        address = self.base + len(self.data)
        body = bytearray(payload)
        if fix:
            fix(body, address + 24)
        self.data += b"LDLD" + struct.pack("<III", 1, dlsum(name), len(body)) + b"\x01" + b"\0" * 7
        self.data += body
        self.data += b"\0" * gap
        self.addresses.setdefault(name, []).append(address)
        return address


def file_block(wrapper, filename=None):
    """Payload bytes of a table exactly as FileDiver's plaintext mirror has it."""
    t = hd2db.table(wrapper, filename)
    if isinstance(t, list):
        return [bytes(x.data[x.base:x.base + x.size]) for x in t]
    return bytes(t.data[t.base:t.base + t.size])


def absolute_array(payload, address):
    """Row table in memory form: the array's first u64 becomes an absolute pointer."""
    off = struct.unpack_from("<Q", payload, 0)[0]
    struct.pack_into("<Q", payload, 0, address + off)


def absolute_deltas(payload, address):
    for k in range(5):
        off = struct.unpack_from("<Q", payload, k * 16)[0]
        struct.pack_into("<Q", payload, k * 16, address + off)


def synth_rows(stride, rows, strings, memory_form=True):
    """Row table whose rows may point at C strings stored after the rows.

    rows: list of (dict offset -> (fmt, value), name bytes or None, name offset)
    -> (payload bytes, fix function)"""
    count = len(rows)
    body = bytearray(16 + count * stride)
    struct.pack_into("<QQ", body, 0, 16, count)
    name_slots = []
    for i, (fields, name, name_at) in enumerate(rows):
        base = 16 + i * stride
        for off, (fmt, value) in fields.items():
            struct.pack_into(fmt, body, base + off, value)
        if name is not None:
            name_slots.append((base + name_at, len(body)))
            body += name + b"\0"
    body += b"\0" * (-len(body) % 8)

    def fix(payload, address):
        if memory_form:
            struct.pack_into("<Q", payload, 0, address + 16)
        for slot, where in name_slots:
            struct.pack_into("<Q", payload, slot, (address + where) if memory_form else where)
    return bytes(body), fix


def load_json(name):
    with open(os.path.join(ROOT, "reference", "HelldiversData", name), encoding="utf-8") as f:
        return json.load(f)


ROW_TABLES = ["ProjectileSettings", "DamageSettings", "ExplosionSettings", "BeamSettings", "ArcSettings"]
KEYED_TABLES = ["WeaponDataComponentData", "ProjectileWeaponComponentData", "WeaponMagazineComponentData",
                "WeaponRoundsComponentData", "WeaponHeatComponentData", "BeamWeaponComponentData",
                "ArcWeaponComponentData", "SprayWeaponComponentData", "MeleeWeaponComponentData",
                "ThrowableComponentData", "ExplosiveComponentData", "DepositComponentData",
                "ShieldComponentData", "HealthComponentData", "VehicleComponentData",
                "WeaponCustomizationComponentData", "AvatarComponentData"]

_cache = {}


def _payloads():
    """File payloads of every bundled table the fixtures use (cached: the entities blob is 46 MB)."""
    if not _cache:
        for name in ROW_TABLES + KEYED_TABLES:
            _cache[name] = file_block(name)
        _cache["WeaponCustomizationSettings"] = file_block("WeaponCustomizationSettings")
        _cache["ComponentEntityDeltaStorage"] = None
        d = hd2db.blob("generated_entity_deltas.dl_bin")
        magic, _typ, size = hd2db.instances(d)[0]
        _cache["ComponentEntityDeltaStorage"] = bytes(d[magic + 24:magic + 24 + size])
        for key, fn in (("kits", "generated_customization_armor_sets.dl_bin"),
                        ("passives", "generated_customization_passive_bonuses.dl_bin")):
            d = hd2db.blob(fn)
            _cache[key] = [bytes(d[m + 24:m + 24 + s]) for m, _t, s in hd2db.instances(d)]
    return _cache


def build_world(cooldown_at=104, second_copy=True, corrupt=None, corrupt_copy=None, exe_bytes=None,
                filler=0):
    """A fake process that looks like the game after its tables are loaded.

    cooldown_at    where the synthetic stratagem rows keep their cooldown (the real offset is unknown)
    second_copy    put a second ProjectileSettings copy in the middle of a heap region (sweep only)
    corrupt        (wrapper name, payload offset, bytes) applied to the primary copy
    corrupt_copy   (payload offset, bytes) applied to the second ProjectileSettings copy
    """
    P = _payloads()
    mem = FakeMemory()
    info = {"blocks": {}}

    def patched(name, payload):
        if corrupt and corrupt[0] == name:
            b = bytearray(payload)
            b[corrupt[1]:corrupt[1] + len(corrupt[2])] = corrupt[2]
            return bytes(b)
        return payload

    # 1. settings chain: row tables, absolute array pointers, mixed gaps
    c = Chain(0x1E000000000, prefix=4)
    for i, name in enumerate(ROW_TABLES):
        c.add(name, patched(name, P[name]), gap=(0, 4, 8, 12, 16)[i % 5], fix=absolute_array)
    for payload in P["WeaponCustomizationSettings"]:
        c.add("WeaponCustomizationSettings", payload, gap=4, fix=absolute_array)
    c.add("ComponentEntityDeltaStorage", P["ComponentEntityDeltaStorage"], fix=absolute_deltas)
    # synthetic tables that are not in the plaintext mirror
    status = load_json("generated_status_effect_settings.json")[0]["StatusEffectSettings"]["items"]
    rows = [({0: ("<I", i), 40: ("<f", float(it.get("duration", 0)))},
             str(it.get("debug_name", "")).encode("ascii", "replace"), 8) for i, it in enumerate(status)]
    payload, fix = synth_rows(152, rows, None)
    c.add("StatusEffectSettings", payload, fix=fix)
    info["status_names"] = [str(it.get("debug_name", "")) for it in status]
    groups = load_json("generated_stratagem_settings.json")
    info["stratagems"] = 0
    for g in groups:
        items = g.get("StratagemSettings", {}).get("items", [])
        rows = []
        for it in items:
            fields = {4: ("<I", it["id"]), 80: ("<I", it.get("uses", 0)),
                      84: ("<f", float(it.get("spawn_time", 0))),
                      cooldown_at: ("<f", float(it.get("cooldown_duration_success", 0)))}
            rows.append((fields, str(it.get("debug_name", "")).encode("ascii", "replace"), 16))
        if rows:
            payload, fix = synth_rows(400, rows, None)
            c.add("StratagemSettings", payload, fix=fix)
            info["stratagems"] += len(rows)
    mem.add(c.base, c.data)
    info["blocks"].update(c.addresses)

    # 2. component tables: one allocation, block at allocation+0
    k = Chain(0x1E100000000, prefix=0)
    for i, name in enumerate(KEYED_TABLES):
        k.add(name, patched(name, P[name]), gap=(4, 8)[i % 2])
    mem.add(k.base, k.data)
    info["blocks"].update(k.addresses)

    # 3. customization kits and passives (single-record blocks, file form)
    s = Chain(0x1E200000000, prefix=4)
    for payload in P["kits"]:
        s.add("HelldiverCustomizationKit", payload, gap=4)
    for payload in P["passives"]:
        s.add("HelldiverCustomizationPassiveBonusSettings", payload, gap=4)
    mem.add(s.base, s.data)
    info["blocks"].update(s.addresses)

    # 4. a heap region with a second ProjectileSettings copy away from the allocation start
    heap = bytearray(os.urandom(64) * (0x200000 // 64))
    info["second_copy"] = None
    if second_copy:
        # 'LDLD' is the last word of the first 256 KB chunk, the version word starts the next one
        at = 0x1E300000000 + 0x40000 - 4
        body = bytearray(P["ProjectileSettings"])
        struct.pack_into("<Q", body, 0, at + 24 + 16)
        if corrupt_copy:
            body[corrupt_copy[0]:corrupt_copy[0] + len(corrupt_copy[1])] = corrupt_copy[1]
        block = b"LDLD" + struct.pack("<III", 1, dlsum("ProjectileSettings"), len(body)) + b"\x01" + b"\0" * 7 + body
        o = at - 0x1E300000000
        heap[o:o + len(block)] = block
        info["second_copy"] = at
    mem.add(0x1E300000000, heap)

    # 5. decoys
    decoy = b"LDLD" + struct.pack("<III", 1, dlsum("ProjectileSettings"), 0xFFFFFFF0) + b"\0" * 64
    mem.add(0x1E400000000, decoy)                                   # absurd size: must be rejected
    mapped = bytearray(P["ProjectileSettings"])
    struct.pack_into("<Q", mapped, 0, 0x1E500000000 + 24 + 16)
    mem.add(0x1E500000000, b"LDLD" + struct.pack("<III", 1, dlsum("ProjectileSettings"), len(mapped))
            + b"\x01" + b"\0" * 7 + mapped, mtype=MEM_MAPPED)       # file mapping: must be ignored
    absent = bytearray(PAGE * 8)
    absent[3 * PAGE:3 * PAGE + 16] = b"LDLD" + struct.pack("<III", 1, 0x12345678, 64)
    mem.add(0x1E600000000, absent, absent={3})                      # page not in memory: never read
    mem.add(0x1E700000000, b"\0" * PAGE * 4, state=MEM_RESERVE, protect=0)
    mem.add(0x1E800000000, b"\0" * PAGE * 2, protect=PAGE_READWRITE | PAGE_GUARD)
    info["absent_first_page"] = 0x1E900000000
    mem.add(0x1E900000000, b"LDLD" + struct.pack("<III", 1, 0x0BADF00D, 32) + b"\0" * 64, absent={0})

    # 6. the game executable: an image region with a PE header, and its file on disk
    exe = bytearray(exe_bytes if exe_bytes is not None else (b"MZ" + bytes(range(256)) * 1400))
    exe[0:2] = b"MZ"
    struct.pack_into("<I", exe, 0x3C, 0x80)
    exe[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<I", exe, 0x80 + 8, 0x66AABBCC)       # TimeDateStamp
    struct.pack_into("<I", exe, 0x80 + 80, 0x00123000)      # SizeOfImage
    struct.pack_into("<I", exe, 0x80 + 88, 0x0004D2F1)      # CheckSum
    info["exe_base"] = 0x7FF600000000
    info["exe_bytes"] = bytes(exe)
    mem.add(info["exe_base"], exe[:PAGE * 4], protect=PAGE_READONLY, mtype=MEM_IMAGE)
    # many small unrelated allocations, like a real process has
    for i in range(filler):
        mem.regions.append(dict(base=0x20000000000 + i * 0x10000, size=PAGE, protect=PAGE_READWRITE,
                                type=MEM_PRIVATE, state=MEM_COMMIT, allocation=0x20000000000 + i * 0x10000,
                                data=bytearray(PAGE), absent=set()))
    mem.regions.sort(key=lambda r: r["base"])
    info["dll_base"] = 0x7FF700000000
    info["dll_bytes"] = b"MZ" + bytes(range(255, -1, -1)) * 700
    mem.add(info["dll_base"], info["dll_bytes"][:PAGE * 2], protect=PAGE_READONLY, mtype=MEM_IMAGE)
    return mem, info


# ------------------------------------------------------------------ the fake game
RESOLVER_LUA = r"""
local ffi = require('ffi')
local py = HD2ST_PY
local function pointer(value, what)
    if type(value) ~= 'cdata' then
        error('bad argument: cannot convert ' .. type(value) .. ' to a pointer (' .. what .. ')', 3)
    end
    return value
end
local function address_of(p) return tonumber(ffi.cast('uintptr_t', p)) end
local function text(value, what)
    if value == nil then return nil end
    if type(value) == 'string' then return value end
    if type(value) == 'cdata' then return ffi.string(value) end
    error('bad argument: cannot convert ' .. type(value) .. ' to a string (' .. what .. ')', 3)
end
local F = {}
F['kernel32.dll'] = {
    GetCurrentProcess = function() return ffi.cast('void *', 0x1234) end,
    ReadProcessMemory = function(process, address, buffer, size, got)
        pointer(process, 'process'); pointer(address, 'address'); pointer(buffer, 'buffer'); pointer(got, 'got')
        local data = py.read(address_of(address), tonumber(size))
        if data == nil then got[0] = 0; return 0 end
        ffi.copy(buffer, data, #data)
        got[0] = #data
        return 1
    end,
    VirtualQuery = function(address, info, size)
        pointer(address, 'address'); pointer(info, 'info')
        local data = py.query(address_of(address))
        if data == nil then return 0 end
        ffi.copy(info, data, 48)
        return 48
    end,
    K32QueryWorkingSetEx = function(process, pages, bytes)
        pointer(process, 'process'); pointer(pages, 'pages')
        if py.working_set_fails() then return 0 end
        local entries = ffi.cast('uint64_t *', pages)
        for k = 0, tonumber(bytes) / 16 - 1 do
            entries[2 * k + 1] = py.attributes(tonumber(entries[2 * k]))
        end
        return 1
    end,
    GetCurrentProcessId = function() return 4242 end,
    VirtualProtect = function(address, size, protection, old)
        pointer(address, 'address'); pointer(old, 'old')
        local previous = py.protect(address_of(address), tonumber(size), protection)
        if previous == nil then return 0 end
        old[0] = previous
        return 1
    end,
    WriteProcessMemory = function(process, address, buffer, size, got)
        pointer(process, 'process'); pointer(address, 'address'); pointer(buffer, 'buffer'); pointer(got, 'got')
        if not py.write(address_of(address), ffi.string(buffer, size)) then got[0] = 0; return 0 end
        got[0] = size
        return 1
    end,
    CreateDirectoryA = function(path, security) py.mkdir(text(path, 'path')); return 1 end,
    GetLastError = function() return 0 end,
    QueryPerformanceCounter = function(ticks) pointer(ticks, 'ticks'); ticks[0] = py.clock(); return 1 end,
    QueryPerformanceFrequency = function(f) pointer(f, 'frequency'); f[0] = 1000000; return 1 end,
    GetModuleHandleA = function(name)
        local base = py.module(text(name, 'name'))
        return ffi.cast('void *', base or 0)
    end,
    GetModuleFileNameA = function(module, buffer, size)
        pointer(module, 'module'); pointer(buffer, 'buffer')
        local path = py.module_path(address_of(module))
        if path == nil then return 0 end
        ffi.copy(buffer, path, #path)
        return #path
    end,
    CreateFileA = function(path, access, share, security, disposition, flags, template)
        local id = py.file_open(text(path, 'path'))
        return ffi.cast('void *', id or -1)
    end,
    GetFileSizeEx = function(handle, size)
        pointer(handle, 'handle'); pointer(size, 'size')
        size[0] = py.file_size(address_of(handle)); return 1
    end,
    ReadFile = function(handle, buffer, count, got, overlapped)
        pointer(handle, 'handle'); pointer(buffer, 'buffer'); pointer(got, 'got')
        local data = py.file_read(address_of(handle), tonumber(count))
        ffi.copy(buffer, data, #data)
        got[0] = #data
        return 1
    end,
    CloseHandle = function(handle) pointer(handle, 'handle'); py.file_close(address_of(handle)); return 1 end,
}
F['ntdll.dll'] = {
    NtQueryVirtualMemory = function(process, address, class, info, size, returned)
        pointer(process, 'process'); pointer(address, 'address'); pointer(info, 'info'); pointer(returned, 'returned')
        if class ~= 3 or py.region_info_unsupported() then return -1073741821 end   -- STATUS_INVALID_INFO_CLASS
        local data = py.allocation(address_of(address))
        if data == nil then return -1073741503 end                                 -- STATUS_INVALID_ADDRESS
        if tonumber(size) < 32 then return -1073741820 end
        ffi.copy(info, data, math.min(tonumber(size), 48))
        return 0
    end,
}
F['user32.dll'] = {
    GetAsyncKeyState = function(vk) return py.key(vk) and -32768 or 0 end,
    GetForegroundWindow = function() return ffi.cast('void *', py.foreground() and 0x777 or 0x888) end,
    GetWindowThreadProcessId = function(window, id)
        pointer(window, 'window'); pointer(id, 'id')
        id[0] = address_of(window) == 0x777 and 4242 or 1
        return 1
    end,
}
F['bcrypt.dll'] = {
    BCryptOpenAlgorithmProvider = function(algorithm, name, implementation, flags)
        pointer(algorithm, 'algorithm'); pointer(name, 'name')
        local id = ffi.cast('const uint16_t *', name)
        local chars = {}
        for i = 0, 5 do chars[i + 1] = string.char(id[i]) end
        if table.concat(chars) ~= 'SHA256' or id[6] ~= 0 then return -1 end
        algorithm[0] = ffi.cast('void *', 0x5A)
        return 0
    end,
    BCryptCloseAlgorithmProvider = function(algorithm, flags) pointer(algorithm, 'algorithm'); return 0 end,
    BCryptCreateHash = function(algorithm, hash, object, object_size, secret, secret_size, flags)
        pointer(algorithm, 'algorithm'); pointer(hash, 'hash')
        hash[0] = ffi.cast('void *', py.sha_new())
        return 0
    end,
    BCryptHashData = function(hash, data, size, flags)
        pointer(hash, 'hash'); pointer(data, 'data')
        py.sha_update(address_of(hash), ffi.string(data, size))
        return 0
    end,
    BCryptFinishHash = function(hash, digest, size, flags)
        pointer(hash, 'hash'); pointer(digest, 'digest')
        ffi.copy(digest, py.sha_digest(address_of(hash)), 32)
        return 0
    end,
    BCryptDestroyHash = function(hash) pointer(hash, 'hash'); return 0 end,
}
HD2ST_TEST_RESOLVER = function(dll, name, signature)
    local module = F[dll]
    local fn = module and module[name]
    if not fn then error('test resolver: ' .. tostring(dll) .. '!' .. tostring(name) .. ' is not available') end
    py.resolved(dll .. '!' .. name)
    return fn
end
"""


class Game:
    """One fake game session with one addon loaded."""

    FRAME_US = 16667

    def __init__(self, source, memory, info, loader_api=1, has_update=True, working_set_fails=False,
                 global_name="HD2StatTunerRecon", log_name="recon.log", config=None, region_info=True):
        self.memory, self.info = memory, info
        self.global_name, self.log_name = global_name, log_name
        self.keys, self.in_front, self.region_info = set(), True, region_info
        self.clock_us = 1000000
        self.frame_cost = []           # fake microseconds the addon spent in each frame
        self.resolved = []
        self.tmp = tempfile.mkdtemp(prefix="hd2st_")
        self.files, self.hashes = {}, {}
        self.exe_path = os.path.join(self.tmp, "helldivers2.exe")
        with open(self.exe_path, "wb") as f:
            f.write(info["exe_bytes"])
        self.dll_path = os.path.join(self.tmp, "game.dll")
        with open(self.dll_path, "wb") as f:
            f.write(info.get("dll_bytes", b""))
        if config is not None:
            self.write_config(config)
        self.working_set_fails = working_set_fails
        self.lua = LuaRuntime(encoding=None, unpack_returned_tuples=True)
        g = self.lua.globals()
        g[b"HD2ST_PY"] = self.lua.table_from({
            b"read": self._read, b"query": self._query, b"present": self.memory.present,
            b"attributes": self.memory.attributes, b"allocation": self._allocation,
            b"write": self.memory.write, b"protect": self.memory.protect,
            b"key": lambda vk: int(vk) in self.keys,
            b"foreground": lambda: self.in_front,
            b"region_info_unsupported": lambda: not self.region_info,
            b"working_set_fails": lambda: self.working_set_fails,
            b"mkdir": self._mkdir, b"clock": self._clock, b"module": self._module,
            b"module_path": self._module_path, b"file_open": self._file_open,
            b"file_size": self._file_size, b"file_read": self._file_read, b"file_close": self._file_close,
            b"sha_new": self._sha_new, b"sha_update": self._sha_update, b"sha_digest": self._sha_digest,
            b"resolved": lambda name: self.resolved.append(name.decode()),
        })
        self.lua.execute(RESOLVER_LUA.encode())
        self.lua.execute(b"""
            local real_getenv = os.getenv
            HD2ST_ENV = {}
            os.getenv = function(name) if HD2ST_ENV[name] ~= nil then return HD2ST_ENV[name] end return real_getenv(name) end
            HD2ST_UPDATES = 0
        """)
        g[b"HD2ST_ENV"][b"LOCALAPPDATA"] = self.tmp.encode()
        if loader_api is not None:
            self.lua.execute(("CowboyBingusModLoader = { api = %d, version = 16, modules = {} }" % loader_api).encode())
        if has_update:
            self.lua.execute(b"function update(dt) HD2ST_UPDATES = HD2ST_UPDATES + 1; return 'base', dt end")
        self.base_update = g[b"update"]
        loader = self.lua.eval(b"function(src) local f, e = loadstring(src, '=addon'); if not f then error(e) end return f() end")
        loader(source.encode("utf-8"))

    # ---- python side of the fake API
    def _clock(self):
        self.clock_us += 2
        return self.clock_us

    def _read(self, address, size):
        self.clock_us += 2 + int(size) // 4000         # 256 KB costs about 65 fake microseconds
        return self.memory.read(address, size)

    def _query(self, address):
        self.clock_us += 2
        return self.memory.query(address)

    def _allocation(self, address):
        self.clock_us += 2
        return self.memory.allocation(address)

    def write_config(self, text):
        folder = os.path.join(self.tmp, "HD2StatTuner")
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "config.txt"), "wb") as f:
            f.write(text.replace("\n", "\r\n").encode("utf-8"))

    def read_out(self, name):
        try:
            with open(self.out_path(name), "rb") as f:
                return f.read().decode("utf-8", "replace")
        except OSError:
            return ""

    def press(self, vk=0x79):
        """Holds a key for two frames (F10 by default)."""
        self.keys.add(vk)
        self.frames(2)
        self.keys.discard(vk)
        self.frames(1)

    def _mkdir(self, path):
        os.makedirs(path.decode(), exist_ok=True)

    def _module(self, name):
        if name is None:
            return self.info["exe_base"]
        if name == b"game.dll" and self.global_name != "HD2StatTunerRecon":
            return self.info.get("dll_base")
        return None                                      # the recon tests run without game.dll

    def _module_path(self, base):
        if int(base) == self.info["exe_base"]:
            return self.exe_path.encode()
        if int(base) == self.info.get("dll_base"):
            return self.dll_path.encode()
        extra = self.info.get("module_paths", {}).get(int(base))
        return extra.encode() if extra else None

    def _file_open(self, path):
        try:
            f = open(path.decode(), "rb")
        except OSError:
            return None
        handle = 0x7000 + len(self.files)
        self.files[handle] = f
        return handle

    def _file_size(self, handle):
        return os.fstat(self.files[int(handle)].fileno()).st_size

    def _file_read(self, handle, count):
        self.clock_us += 50
        return self.files[int(handle)].read(int(count))

    def _file_close(self, handle):
        self.files.pop(int(handle)).close()

    def _sha_new(self):
        handle = 0x9000 + len(self.hashes)
        self.hashes[handle] = hashlib.sha256()
        return handle

    def _sha_update(self, handle, data):
        self.hashes[int(handle)].update(data)

    def _sha_digest(self, handle):
        return self.hashes[int(handle)].digest()

    # ---- driving the game
    def frames(self, count, until=None):
        """Runs `count` frames; stops early when `until()` is true. -> frames run."""
        update = self.lua.globals()[b"update"]
        for n in range(count):
            self.clock_us += self.FRAME_US
            before = self.clock_us
            result = update(0.016)
            self.frame_cost.append(self.clock_us - before)
            self.last_update_result = result
            if until and until():
                return n + 1
        return count

    def same(self, a, b):
        """Lua identity of two Lua values (lupa wrappers do not compare equal)."""
        return bool(self.lua.eval(b"function(a, b) return rawequal(a, b) end")(a, b))

    def skip_time(self, seconds):
        self.clock_us += int(seconds * 1000000)

    def state(self):
        return self.lua.globals()[self.global_name.encode()]

    def out_path(self, name):
        return os.path.join(self.tmp, "HD2StatTuner", name)

    def status(self):
        try:
            with open(self.out_path("STATUS.txt"), "rb") as f:
                return f.read().decode("utf-8", "replace")
        except OSError:
            return ""

    def log_text(self):
        try:
            with open(self.out_path(self.log_name), "rb") as f:
                return f.read().decode("utf-8", "replace")
        except OSError:
            return ""

    def run_until_status(self, text, max_frames=4000):
        self.frames(max_frames, until=lambda: text in self.status())
        return self.status()

    def close(self):
        for f in list(self.files.values()):
            f.close()
        shutil.rmtree(self.tmp, ignore_errors=True)


def addon_source(kind="recon", data=None):
    text, _version = pack_addon.render(kind, data=data)
    return text
