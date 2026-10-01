# -*- coding: utf-8 -*-
"""Integration test: the recon addon against the REAL Windows API.

The fake-game tests cannot tell whether our FFI signatures and struct layouts are right; a
wrong one would crash the game. Here the addon runs with no test resolver at all, inside this
Python process: it enumerates this process's real memory, reads it with the real
ReadProcessMemory, hashes the real python.exe through bcrypt, and must find a table that the
test planted at the start of a real VirtualAlloc allocation.

    .venv\\Scripts\\python.exe -m unittest tests.test_real_ffi -v     (Windows only)
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

import hd2db  # noqa: E402
import pack_addon  # noqa: E402
from dump_typelib import dlsum  # noqa: E402

MEM_COMMIT, MEM_RESERVE, MEM_RELEASE, PAGE_READWRITE = 0x1000, 0x2000, 0x8000, 0x04


@unittest.skipUnless(sys.platform == "win32", "needs the Windows API")
class RealApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.VirtualAlloc.restype = ctypes.c_void_p
        k32.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32]
        k32.VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32]
        cls.k32 = k32

        # a real allocation that starts like the game's: 4 bytes, then an LDLD block
        t = hd2db.table("ProjectileSettings")
        payload = bytearray(t.data[t.base:t.base + t.size])
        size = 4 + 24 + len(payload)
        cls.region = k32.VirtualAlloc(None, size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
        assert cls.region
        cls.block = cls.region + 4
        struct.pack_into("<Q", payload, 0, cls.block + 24 + 16)          # memory form: absolute pointer
        image = (b"\x11\x22\x33\x44" + b"LDLD" + struct.pack("<III", 1, dlsum("ProjectileSettings"), len(payload))
                 + b"\x01" + b"\0" * 7 + bytes(payload))
        ctypes.memmove(cls.region, image, len(image))

        cls.tmp = tempfile.mkdtemp(prefix="hd2st_real_")
        cls.lua = LuaRuntime(encoding=None, unpack_returned_tuples=True)
        cls.lua.execute(b"""
            local real_getenv = os.getenv
            HD2ST_ENV = {}
            os.getenv = function(name) if HD2ST_ENV[name] ~= nil then return HD2ST_ENV[name] end return real_getenv(name) end
            CowboyBingusModLoader = { api = 1, version = 16, modules = {} }
            HD2ST_UPDATES = 0
            function update(dt) HD2ST_UPDATES = HD2ST_UPDATES + 1; return dt end
        """)
        cls.lua.globals()[b"HD2ST_ENV"][b"LOCALAPPDATA"] = cls.tmp.encode()
        source, _version = pack_addon.render("recon")
        cls.lua.eval(b"function(src) local f, e = loadstring(src, '=addon'); if not f then error(e) end return f() end")(
            source.encode("utf-8"))
        update = cls.lua.globals()[b"update"]
        cls.status = ""
        started = time.time()
        cls.frames = 0
        while time.time() - started < 240:
            for _ in range(200):
                update(0.016)
            cls.frames += 200
            cls.status = cls.read_status()
            if "sha256=" in cls.status:
                break
        cls.seconds = time.time() - started

    @classmethod
    def read_status(cls):
        try:
            with open(os.path.join(cls.tmp, "HD2StatTuner", "STATUS.txt"), "rb") as f:
                return f.read().decode("utf-8", "replace")
        except OSError:
            return ""

    @classmethod
    def tearDownClass(cls):
        cls.k32.VirtualFree(cls.region, 0, MEM_RELEASE)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_the_report_was_written_through_the_real_api(self):
        self.assertIn("sha256=", self.status, "no report after %d frames / %.0f s" % (self.frames, self.seconds))
        self.assertIn("self_read=true", self.status)
        self.assertIn("errors=0", self.status)

    def test_finds_the_planted_table_at_a_real_allocation_start(self):
        lines = [x for x in self.status.split("\r\n") if x.strip().startswith("0x%X size=" % self.block)]
        self.assertEqual(len(lines), 1, self.status[:3000])
        self.assertIn("origin=allocation+4", lines[0])
        self.assertIn("rows=350 ids=350", lines[0])
        self.assertIn("array=absolute pointer, inside the block (+16)", lines[0])
        self.assertRegex(lines[0], r"watch (\d+): match \1, differ 0, key missing 0, unreadable 0")

    def test_hashes_the_real_executable(self):
        # a venv's sys.executable is a launcher; the running image is the base interpreter,
        # which is the path GetModuleFileName must report
        buffer = ctypes.create_unicode_buffer(1024)
        ctypes.windll.kernel32.GetModuleFileNameW(None, buffer, 1024)
        reported = __import__("re").search(r"\(game executable\): path=(.*)", self.status).group(1).strip()
        self.assertEqual(os.path.normcase(reported), os.path.normcase(buffer.value))
        with open(buffer.value, "rb") as f:
            data = f.read()
        self.assertIn("file_size=%d sha256=%s" % (len(data), hashlib.sha256(data).hexdigest().upper()), self.status)
        self.assertRegex(self.status, r"pe_timestamp=0x[0-9A-F]+ image_size=\d+ pe_checksum=0x[0-9A-F]+")

    def test_scan_statistics_are_plausible(self):
        m = __import__("re").search(r"sweep: bytes=(\d+) read_failures=(\d+) pages_not_in_memory=(\d+)", self.status)
        self.assertTrue(m)
        self.assertGreater(int(m.group(1)), 1000000)          # it really swept this process
        m = __import__("re").search(r"regions=(\d+) readable=(\d+)", self.status)
        self.assertGreater(int(m.group(1)), 50)

    def test_update_chain(self):
        self.assertEqual(self.lua.globals()[b"HD2ST_UPDATES"], self.frames)


if __name__ == "__main__":
    unittest.main(verbosity=2)
