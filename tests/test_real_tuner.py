# -*- coding: utf-8 -*-
"""Integration test: the patch engine against the REAL Windows API.

No test resolver: the engine enumerates this Python process's real allocations
(NtQueryVirtualMemory), checks real page attributes (QueryWorkingSetEx), hashes the real
executable and a real loaded DLL named game.dll (bcrypt), and writes with the real
WriteProcessMemory into tables the test planted in real VirtualAlloc allocations.

    .venv\\Scripts\\python.exe -m unittest tests.test_real_tuner -v     (Windows only)
"""
import ctypes
import hashlib
import os
import shutil
import struct
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from lupa.luajit21 import LuaRuntime  # noqa: E402

import gen_tuner_data  # noqa: E402
import hd2db  # noqa: E402
import pack_addon  # noqa: E402
from dump_typelib import dlsum  # noqa: E402
from hashnames import murmur64a  # noqa: E402

MEM_COMMIT, MEM_RESERVE, MEM_RELEASE = 0x1000, 0x2000, 0x8000
PAGE_READONLY, PAGE_READWRITE = 0x02, 0x04
LIBERATOR = murmur64a(b"content/fac_helldivers/equipment/primary_weapons/assault_rifle/assault_rifle")


@unittest.skipUnless(sys.platform == "win32", "needs the Windows API")
class RealApi(unittest.TestCase):
    @classmethod
    def plant(cls, wrapper, protect=PAGE_READWRITE):
        """A real allocation that starts like the game's: 4 bytes, then the LDLD block."""
        t = hd2db.table(wrapper)
        payload = bytearray(t.data[t.base:t.base + t.size])
        region = cls.k32.VirtualAlloc(None, 4 + 24 + len(payload), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
        assert region
        block = region + 4
        if t.shape == "rows":
            struct.pack_into("<Q", payload, 0, block + 24 + 16)      # memory form: absolute pointer
        image = (b"\0\0\0\0" + b"LDLD" + struct.pack("<III", 1, dlsum(wrapper), len(payload))
                 + b"\x01" + b"\0" * 7 + bytes(payload))
        ctypes.memmove(region, image, len(image))
        if protect != PAGE_READWRITE:
            old = ctypes.c_uint32(0)
            assert cls.k32.VirtualProtect(ctypes.c_void_p(region), len(image), protect, ctypes.byref(old))
        cls.regions.append(region)
        return block, t

    @classmethod
    def setUpClass(cls):
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.VirtualAlloc.restype = ctypes.c_void_p
        k32.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32]
        k32.VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32]
        k32.VirtualProtect.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_void_p]
        cls.k32, cls.regions = k32, []
        cls.tmp = tempfile.mkdtemp(prefix="hd2st_realtuner_")

        # a real module called game.dll, so the build gate has two real files to hash
        exe = ctypes.create_unicode_buffer(1024)
        ctypes.windll.kernel32.GetModuleFileNameW(None, exe, 1024)
        dll_source = os.path.join(os.path.dirname(exe.value), "python3.dll")
        cls.dll_path = os.path.join(cls.tmp, "game.dll")
        shutil.copyfile(dll_source, cls.dll_path)
        cls.dll = ctypes.WinDLL(cls.dll_path)
        with open(exe.value, "rb") as f:
            exe_hash = hashlib.sha256(f.read()).hexdigest().upper()
        with open(cls.dll_path, "rb") as f:
            dll_hash = hashlib.sha256(f.read()).hexdigest().upper()

        cls.damage_block, cls.damage_table = cls.plant("DamageSettings")
        cls.fire_block, cls.fire_table = cls.plant("ProjectileWeaponComponentData")
        cls.readonly_block, cls.projectile_table = cls.plant("ProjectileSettings", protect=PAGE_READONLY)
        cls.plant("ExplosionSettings")

        folder = os.path.join(cls.tmp, "HD2StatTuner")
        os.makedirs(folder)
        cls.config_path = os.path.join(folder, "config.txt")
        with open(cls.config_path, "w") as f:
            f.write("[settings]\nauto_reload_seconds = 1\n[weapon: assault_rifle]\n"
                    "damage = 120\nrpm = 150%\nvelocity = 1000\n")

        # test_5 plants an id-indexed array of row pointers at rva 0x3100 of game.dll (the slot of id 1)
        blob, _stats = gen_tuner_data.generate(builds=[("this python", exe_hash, dll_hash)],
                                               indexes={"ProjectileSettings": (0x30F8, 351)})
        source, _version = pack_addon.render("tuner", data=blob)
        cls.lua = LuaRuntime(encoding=None, unpack_returned_tuples=True)
        cls.lua.execute(b"""
            local real_getenv = os.getenv
            HD2ST_ENV = {}
            os.getenv = function(name) if HD2ST_ENV[name] ~= nil then return HD2ST_ENV[name] end return real_getenv(name) end
            CowboyBingusModLoader = { api = 1, version = 16, modules = {} }
            function update(dt) return dt end
        """)
        cls.lua.globals()[b"HD2ST_ENV"][b"LOCALAPPDATA"] = cls.tmp.encode()
        cls.lua.eval(b"function(src) local f, e = loadstring(src, '=addon'); if not f then error(e) end return f() end")(
            source.encode("utf-8"))
        cls.update = cls.lua.globals()[b"update"]
        cls.status = cls.run_until(lambda s: s.startswith(("OK", "PARTIAL", "REFUSED", "FAILED")))

    @classmethod
    def read_status(cls):
        try:
            with open(os.path.join(cls.tmp, "HD2StatTuner", "STATUS.txt"), "rb") as f:
                return f.read().decode("utf-8", "replace")
        except OSError:
            return ""

    @classmethod
    def run_until(cls, done, seconds=120):
        started = time.time()
        while time.time() - started < seconds:
            for _ in range(100):
                cls.update(0.016)
            status = cls.read_status()
            if done(status):
                return status
        return cls.read_status()

    @classmethod
    def tearDownClass(cls):
        for region in cls.regions:
            cls.k32.VirtualFree(region, 0, MEM_RELEASE)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def peek(self, address, fmt):
        return struct.unpack(fmt, ctypes.string_at(address, struct.calcsize(fmt)))[0]

    def damage_address(self):
        t = self.damage_table
        return self.damage_block + 24 + t.record_offset(t.by_id()[108]) + 4

    def rpm_address(self):
        return self.fire_block + 24 + self.fire_table.record_offset(LIBERATOR) + 8

    def velocity_address(self):
        t = self.projectile_table
        return self.readonly_block + 24 + t.record_offset(t.by_id()[276]) + 32

    def test_1_build_gate_and_real_writes(self):
        self.assertIn("[build] verified: this python", self.status, self.status[:1500])
        self.assertEqual(self.peek(self.damage_address(), "<I"), 120)
        self.assertEqual(self.peek(self.rpm_address(), "<f"), 960.0)
        self.assertIn("damage: 90 -> 120  APPLIED  copies=1", self.status)
        self.assertIn("rpm: 640 -> 960  APPLIED  copies=1", self.status)
        self.assertIn("origin=allocation+4", self.status)

    def page_protection(self, address):
        class MBI(ctypes.Structure):
            _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                        ("AllocationProtect", ctypes.c_uint32), ("PartitionId", ctypes.c_uint16),
                        ("RegionSize", ctypes.c_size_t), ("State", ctypes.c_uint32),
                        ("Protect", ctypes.c_uint32), ("Type", ctypes.c_uint32)]
        mbi = MBI()
        self.k32.VirtualQuery.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
        self.k32.VirtualQuery.restype = ctypes.c_size_t
        self.assertTrue(self.k32.VirtualQuery(ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)))
        return mbi.Protect

    def test_2_read_only_table_is_written_and_left_read_only(self):
        # the table was planted in a real read-only allocation, like the game's component tables
        self.assertTrue(self.status.startswith("OK - 3 values applied"), self.status[:300])
        self.assertEqual(self.peek(self.velocity_address(), "<f"), 1000.0)
        self.assertEqual(self.page_protection(self.velocity_address()), PAGE_READONLY)
        self.assertIn("read-only pages opened for a write=1, not closed again=0", self.status)

    def test_3_cost_is_inside_the_budget(self):
        import re
        # Single frames are noisy in a test process (the garbage collector and the OS scheduler bill
        # their pauses to whoever is running), so the budget is judged by the average working frame
        # and the worst one only has to stay far below a game frame.
        worst = float(re.search(r"worst_frame_ms=([\d.]+)", self.status).group(1))
        frames = int(re.search(r"busy_frames=(\d+)", self.status).group(1))
        seconds = float(re.search(r"busy_seconds=([\d.]+)", self.status).group(1))
        self.assertLess(seconds / frames * 1000, 2.5, "average working frame %.2f ms" % (seconds / frames * 1000))
        self.assertLess(worst, 16.0, "a frame took %.2f ms" % worst)
        passes = int(re.search(r"search: passes=(\d+) allocations=(\d+)", self.status).group(1))
        allocations = int(re.search(r"search: passes=(\d+) allocations=(\d+)", self.status).group(2))
        self.assertGreaterEqual(passes, 1)
        self.assertGreater(allocations, 50)                                # it really walked this process

    def test_4_restore_through_auto_reload(self):
        with open(self.config_path, "w") as f:
            f.write("[settings]\nauto_reload_seconds = 1\n")
        status = type(self).run_until(lambda s: s.startswith("OK - no changes configured"), seconds=60)
        self.assertTrue(status.startswith("OK - no changes configured"), status[:300])
        self.assertEqual(self.peek(self.damage_address(), "<I"), 90)
        self.assertEqual(self.peek(self.rpm_address(), "<f"), 640.0)
        self.assertEqual(self.peek(self.velocity_address(), "<f"), 900.0)
        self.assertEqual(self.page_protection(self.velocity_address()), PAGE_READONLY)

    def test_5_probe_reads_a_real_module(self):
        # An id-indexed array of row pointers inside the real module game.dll (pages of an image that
        # were written to, like the game's), and one instruction in executable memory that names it.
        base = self.dll._handle
        t = self.projectile_table
        rows_at = self.readonly_block + 24 + 16
        ids = t.by_id()
        array_rva, code_rva = 0x3100, 0x8100
        array = bytearray(8 * len(ids))
        for row_id, row in ids.items():
            struct.pack_into("<Q", array, 8 * (row_id - 1), rows_at + row * t.stride)
        old = ctypes.c_uint32(0)
        self.assertTrue(self.k32.VirtualProtect(ctypes.c_void_p(base + 0x3000), 0x2000, PAGE_READWRITE, ctypes.byref(old)))
        ctypes.memmove(base + array_rva - 8, struct.pack("<Q", len(ids)) + bytes(array), 8 + len(array))
        code = b"\x48\x8D\x0D" + struct.pack("<i", array_rva - (code_rva + 3 + 4))
        self.assertTrue(self.k32.VirtualProtect(ctypes.c_void_p(base + 0x8000), 0x1000, PAGE_READWRITE, ctypes.byref(old)))
        ctypes.memmove(base + code_rva, code, len(code))
        self.assertTrue(self.k32.VirtualProtect(ctypes.c_void_p(base + 0x8000), 0x1000, 0x20, ctypes.byref(old)))

        with open(self.config_path, "w") as f:
            f.write("[settings]\nauto_reload_seconds = 1\nprobe = true\n")
        status = type(self).run_until(lambda s: "probe: done" in s or "probe: failed" in s, seconds=300)
        self.assertIn("probe: done", status, status[:1500])
        with open(os.path.join(self.tmp, "HD2StatTuner", "PROBE.txt"), "rb") as f:
            report = f.read().decode("utf-8", "replace")
        self.assertNotIn("index analysis failed", report)
        self.assertIn("[module game.dll] base 0x%X image size 0x10000; code read: 4096 bytes, unreadable 0;" % base, report)
        self.assertIn(".rdata rva 0x1000 size 0xD51C flags 0x40000040", report)
        section = [x for x in report.split("[index ProjectileSettings]")[1:] if "module image" in x.split("[index")[0]][0]
        self.assertTrue(section.startswith(" at 0x%X, %d slots, row id = slot +1" % (base + array_rva, len(ids))),
                        section[:200])
        self.assertIn("memory: type 0x1000000 (module image), protection 0x04,", section)
        self.assertIn("allocation base 0x%X" % base, section)
        self.assertIn("module: game.dll, array at rva 0x3100 (section .rdata,", section)
        self.assertIn("code naming array +0: 1\r\n  rip at rva 0x%X: " % (code_rva + 3), section)
        self.assertRegex(section, r"64 slots before: .* 0x%X\r\n" % len(ids))

    def test_6_new_projectile_id_through_real_memory(self):
        import re
        base = self.dll._handle
        ctypes.memmove(base + 0x30F8, bytes(8), 8)                      # the slot of id 0 is empty in the game
        with open(self.config_path, "w") as f:
            f.write("[settings]\nauto_reload_seconds = 1\n[weapon: assault_rifle]\nown_bullet = new\nvelocity = 1200\n")
        status = type(self).run_until(lambda s: "velocity: 900 -> 1200 (own row)  APPLIED" in s, seconds=120)
        self.assertIn("[own rows] ready", status, status[:2500])
        m = re.search(r"block (0x[0-9A-F]+), game index (0x[0-9A-F]+), first new id (\d+)", status)
        self.assertTrue(m, status[:2500])
        block, index, new_id = int(m.group(1), 16), int(m.group(2), 16), int(m.group(3))
        self.assertEqual(index, base + 0x30F8)
        self.assertGreater(block, index)
        self.assertLess(new_id, 2 ** 31)
        # the block is real, private, writable memory that Windows gave us at the address we asked for
        self.assertEqual(self.page_protection(block), PAGE_READWRITE)
        # what the game would do with the new id: [index + id * 8] -> the row
        row = self.peek(index + 8 * new_id, "<Q")
        self.assertTrue(block <= row < block + 0x10000, hex(row))
        self.assertEqual(self.peek(row, "<I"), new_id)
        self.assertEqual(self.peek(row + 32, "<f"), 1200.0)
        self.assertEqual(self.peek(row + 60, "<I"), 55)
        # the weapon was switched to it; the shared row of the game is untouched
        deadline = time.time() + 60
        while time.time() < deadline and self.peek(self.fire_block + 24 + self.fire_table.record_offset(LIBERATOR), "<I") != new_id:
            type(self).run_until(lambda s: False, seconds=1)
        self.assertEqual(self.peek(self.fire_block + 24 + self.fire_table.record_offset(LIBERATOR), "<I"), new_id)
        self.assertEqual(self.peek(self.velocity_address(), "<f"), 900.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
