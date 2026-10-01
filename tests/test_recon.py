# -*- coding: utf-8 -*-
"""Offline tests for the read-only recon addon.

    .venv\\Scripts\\python.exe -m unittest tests.test_recon -v

Three groups:
  * behaviour against the fake game (tests/harness.py),
  * packaging / syntax gates,
  * mutation tests: each known-dangerous edit of the addon must make the baseline fail.
    A mutation that survives means the tests do not actually check that property.
"""
import hashlib
import os
import re
import struct
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import harness  # noqa: E402
import hd2db  # noqa: E402
import pack_addon  # noqa: E402

SOURCE = harness.addon_source("recon")
BUDGET_US = 1500
STEP_SLACK_US = 250          # one unit of work may finish after the deadline


def projectile_field(row_id, field_offset):
    t = hd2db.table("ProjectileSettings")
    return t.record_offset(t.by_id()[row_id]) + field_offset


def run_baseline(source=SOURCE, **world):
    mem, info = harness.build_world(**world)
    game = harness.Game(source, mem, info)
    game.run_until_status("sha256=", max_frames=3000)
    return game


def first_line(status):
    return status.split("\r\n", 1)[0]


def table_line(status, name):
    m = re.search(r"^%s [0-9A-F]{8} shape=\w stride=\d+ copies=(\d+)\r?$" % re.escape(name), status, re.M)
    return int(m.group(1)) if m else None


def baseline_ok(game):
    """Everything the baseline promises, as one boolean (used by the mutation tests)."""
    status = game.status()
    return (first_line(status).startswith("OK - all 28 tables found, all ")
            and table_line(status, "ProjectileSettings") == 2
            and game.memory.absent_reads == 0
            and max(game.frame_cost) <= BUDGET_US + STEP_SLACK_US
            and "sha256=" + hashlib.sha256(game.info["exe_bytes"]).hexdigest().upper() in status
            and "start_amount" not in status.split("[differences]")[1].split("[stratagems]")[0])


class Baseline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game = run_baseline()
        cls.status = cls.game.status()

    @classmethod
    def tearDownClass(cls):
        cls.game.close()

    def test_verdict_is_ok_and_first(self):
        with open(os.path.join(ROOT, "build", "recon_data.txt")) as f:
            watch = len([1 for line in f if line.startswith("W|")])
        self.assertEqual(first_line(self.status),
                         "OK - all 28 tables found, all %d watched values match the offline data" % watch)

    def test_states_read_only_and_version(self):
        lines = self.status.split("\r\n")
        self.assertEqual(lines[1], "read-only build: nothing was written to game memory")
        self.assertRegex(lines[2], r"^HD2 Stat Tuner recon v\d+\.\d+\.\d+$")
        self.assertRegex(self.game.log_text().split("\r\n")[0], r"^HD2 Stat Tuner recon v\d+\.\d+\.\d+$")

    def test_never_resolves_a_write_api(self):
        for name in self.game.resolved:
            self.assertNotRegex(name, r"(?i)write|protect|alloc|free|createremotethread")
        self.assertNotRegex(SOURCE.split("local DATA")[0] + SOURCE.split("]==]")[1],
                            r"WriteProcessMemory|VirtualProtect|NtWriteVirtualMemory|VirtualAlloc")

    def test_finds_the_copy_that_is_not_at_an_allocation_start(self):
        self.assertEqual(table_line(self.status, "ProjectileSettings"), 2)
        self.assertIn("%s size=" % ("0x%X" % self.game.info["second_copy"]), self.status)
        self.assertRegex(self.status, r"0x%X size=\d+ origin=sweep" % self.game.info["second_copy"])

    def test_ignores_mapped_memory_absurd_sizes_and_absent_pages(self):
        self.assertNotIn("0x1E500000000", self.status)      # file mapping
        self.assertNotIn("0x1E400000000", self.status)      # payload size 0xFFFFFFF0
        self.assertNotIn("12345678", self.status)           # header on a page that is not in memory
        self.assertNotIn("0BADF00D", self.status)           # allocation whose first page is not in memory
        self.assertEqual(self.game.memory.absent_reads, 0)

    def test_reports_array_form(self):
        self.assertRegex(self.status, r"rows=350 ids=350 duplicates=0 tail=0 array=absolute pointer, inside the block \(\+16\)")

    def test_keyed_tables_are_parsed(self):
        t = hd2db.table("WeaponDataComponentData")
        self.assertIn("records=%d entities=%d buckets=%d slack=0" % (t.count, len(t.index), t.buckets), self.status)
        h = hd2db.table("HealthComponentData")
        self.assertIn("records=%d entities=%d buckets=%d" % (h.count, len(h.index), h.buckets), self.status)

    def test_stays_inside_the_frame_budget(self):
        self.assertLessEqual(max(self.game.frame_cost), BUDGET_US + STEP_SLACK_US)
        worked = [c for c in self.game.frame_cost if c > 0]
        self.assertGreater(len(worked), 20)                  # the work really was spread over frames
        # nothing happens before START_FRAME, and only on every 2nd frame after it
        self.assertEqual(sum(self.game.frame_cost[:118]), 0)

    def test_build_identity(self):
        digest = hashlib.sha256(self.game.info["exe_bytes"]).hexdigest().upper()
        self.assertIn("file_size=%d sha256=%s" % (len(self.game.info["exe_bytes"]), digest), self.status)
        self.assertIn("pe_timestamp=0x66AABBCC image_size=%d pe_checksum=0x4D2F1" % 0x123000, self.status)
        self.assertIn("game.dll: path=nil", self.status)

    def test_stratagem_cooldown_votes(self):
        groups = re.findall(r"known (\d+), uses@80 match (\d+), cooldown votes (.*)", self.status)
        self.assertTrue(groups)
        known = sum(int(g[0]) for g in groups)
        self.assertEqual(known, self.game.info["stratagems"])
        at104 = sum(int(re.search(r"\+104:(\d+)", g[2]).group(1)) for g in groups)
        at100 = sum(int(re.search(r"\+100:(\d+)", g[2]).group(1)) for g in groups)
        self.assertEqual(at104, known)
        self.assertLess(at100, known // 4)
        self.assertIn('"ORBITAL. LASER" uses@80=3', self.status)

    def test_status_effects_are_listed_by_name(self):
        section = self.status.split("[status effects]")[1].split("[attachment deltas]")[0]
        self.assertIn("=Acid Storm", section)
        self.assertRegex(section, r"raw \d+ Acid Storm: [0-9A-F]{304}")
        names = section.split("\r\n")[1]
        self.assertEqual(names.count("="), len(self.game.info["status_names"]))

    def test_attachment_deltas(self):
        section = self.status.split("[attachment deltas]")[1].split("[census]")[0]
        self.assertIn("absolute", self.status.split("ComponentEntityDeltaStorage")[1].split("\r\n")[1])
        self.assertRegex(section, r"component 5: 327 deltas, top offsets .*\+136x80")
        self.assertRegex(section, r"component 236: 1916 deltas, top offsets \+956x204")

    def test_update_chain_is_preserved(self):
        self.assertEqual(self.game.lua.globals()[b"HD2ST_UPDATES"], len(self.game.frame_cost))
        self.assertEqual(self.game.last_update_result, (b"base", 0.016))

    def test_large_addresses_are_printed_in_full(self):
        self.assertIn("0x1E000000004 size=", self.status)


class Variants(unittest.TestCase):
    def run_world(self, **kw):
        game = run_baseline(**kw)
        self.addCleanup(game.close)
        return game, game.status()

    def test_a_changed_value_is_reported_with_both_numbers(self):
        offset = projectile_field(276, 32)                       # the Liberator's projectile speed
        game, status = self.run_world(corrupt=("ProjectileSettings", offset, struct.pack("<f", 1234.5)))
        self.assertTrue(first_line(status).startswith("PARTIAL - 28 of 28 tables found"))
        self.assertRegex(status, r"ProjectileSettings: \S+\.velocity  key 276 \+32 f32  offline 900  live 1234\.5")

    def test_a_difference_in_the_second_copy_shows_on_its_own_line(self):
        game, status = self.run_world(corrupt_copy=(projectile_field(276, 32), struct.pack("<f", 1.0)))
        self.assertTrue(first_line(status).startswith("OK - "))
        line = [x for x in status.split("\r\n") if x.strip().startswith("0x%X " % game.info["second_copy"])][0]
        self.assertIn("differ 1,", line)

    def test_calibration_follows_the_data_not_an_assumption(self):
        game, status = self.run_world(cooldown_at=100)
        groups = re.findall(r"known (\d+), uses@80 match \d+, cooldown votes (.*)", status)
        known = sum(int(g[0]) for g in groups)
        self.assertEqual(sum(int(re.search(r"\+100:(\d+)", g[1]).group(1)) for g in groups), known)

    def test_negative_i32_values(self):
        game, status = self.run_world()
        with open(os.path.join(ROOT, "build", "recon_data.txt")) as f:
            self.assertRegex(f.read(), r"W\|DepositComponentData\|[0-9A-F]{16}\|4\|i32\|-1\|")
        self.assertNotIn("start_amount", status.split("[differences]")[1].split("[stratagems]")[0])


class Startup(unittest.TestCase):
    def start(self, **kw):
        mem, info = harness.build_world()
        game = harness.Game(SOURCE, mem, info, **kw)
        self.addCleanup(game.close)
        return game

    def test_old_loader_stops_before_doing_anything(self):
        game = self.start(loader_api=0)
        self.assertTrue(game.status().startswith("FAILED - "))
        self.assertIn("too old", game.status())
        self.assertTrue(game.same(game.lua.globals()[b"update"], game.base_update))     # no hook installed
        game.frames(300)
        self.assertEqual(game.memory.read_log, [])

    def test_missing_update_hook(self):
        mem, info = harness.build_world()
        game = harness.Game(SOURCE, mem, info, has_update=False)
        self.addCleanup(game.close)
        self.assertIn("FAILED - ", game.status())
        self.assertIn("update hook", game.status())

    def test_unknown_loader_is_not_refused(self):
        game = self.start(loader_api=None)
        self.assertTrue(game.status().startswith("WAITING"))

    def test_waiting_status_exists_before_the_scan(self):
        game = self.start()
        self.assertTrue(game.status().startswith("WAITING - "))
        self.assertIn("HD2 Stat Tuner recon v", game.status())

    def test_second_load_is_a_no_op(self):
        game = self.start()
        hooked = game.lua.globals()[b"update"]
        game.lua.eval(b"function(src) return loadstring(src, '=addon')() end")(SOURCE.encode())
        self.assertTrue(game.same(game.lua.globals()[b"update"], hooked))

    def test_without_presence_information_nothing_is_read(self):
        game = self.start(working_set_fails=True)
        game.frames(1500)
        self.assertIn("0 of 28 tables found", first_line(game.status()))
        self.assertEqual(game.memory.absent_reads, 0)


class Lifecycle(unittest.TestCase):
    def test_tables_that_appear_later_are_found_and_trigger_a_new_sweep(self):
        mem, info = harness.build_world()
        late = [r for r in mem.regions if r["base"] == 0x1E100000000][0]     # the component tables
        mem.regions.remove(late)
        game = harness.Game(SOURCE, mem, info)
        self.addCleanup(game.close)
        status = game.run_until_status("sha256=", max_frames=3000)
        self.assertTrue(first_line(status).startswith("PARTIAL - 11 of 28 tables found"))
        mem.regions.append(late)
        mem.regions.sort(key=lambda r: r["base"])                            # "mission loaded"
        for _ in range(12):
            game.skip_time(25)
            game.frames(400)
            if first_line(game.status()).startswith("OK - ") and "sweeps=2" in game.status():
                break
        status = game.status()
        self.assertTrue(first_line(status).startswith("OK - all 28 tables found"), first_line(status))
        self.assertIn("copies changed", status.split("[history]")[1])
        self.assertRegex(status, r"sweeps=[23]")

    def test_retires_after_the_last_round_and_unhooks(self):
        mem, info = harness.build_world(second_copy=False)
        game = harness.Game(SOURCE, mem, info)
        self.addCleanup(game.close)
        for _ in range(300):
            game.skip_time(25)
            game.frames(60)
            if game.state()[b"retired"]:
                break
        self.assertTrue(game.state()[b"retired"])
        self.assertEqual(game.state()[b"phase"], b"done")
        self.assertTrue(game.same(game.lua.globals()[b"update"], game.base_update))
        reads = len(game.memory.read_log)
        game.frames(500)
        self.assertEqual(len(game.memory.read_log), reads)                   # truly asleep
        self.assertEqual(game.last_update_result, (b"base", 0.016))

    def test_retiring_keeps_a_later_wrapper_intact(self):
        mem, info = harness.build_world(second_copy=False)
        game = harness.Game(SOURCE, mem, info)
        self.addCleanup(game.close)
        game.lua.execute(b"""
            local inner = update
            OUTER_CALLS = 0
            function update(...) OUTER_CALLS = OUTER_CALLS + 1; return inner(...) end
        """)
        outer = game.lua.globals()[b"update"]
        for _ in range(300):
            game.skip_time(25)
            game.frames(60)
            if game.state()[b"retired"]:
                break
        self.assertTrue(game.state()[b"retired"])
        self.assertTrue(game.same(game.lua.globals()[b"update"], outer))    # chain not cut
        game.frames(10)
        self.assertEqual(game.last_update_result, (b"base", 0.016))


class Packaging(unittest.TestCase):
    def test_entry_line_and_names(self):
        self.assertTrue(SOURCE.startswith("-- HD2-Addon: mods/keg/stat_tuner_recon\n"))
        pack_addon.check_lua_source(SOURCE, "mods/keg/stat_tuner_recon")
        with self.assertRaises(ValueError):
            pack_addon.check_lua_source(SOURCE, "mods/keg/other_name")
        with self.assertRaises(ValueError):
            pack_addon.check_lua_source("﻿" + SOURCE, "mods/keg/stat_tuner_recon")

    def test_gate_rejects_syntax_luajit_does_not_have(self):
        head = "-- HD2-Addon: mods/keg/x\n"
        for bad in ("local a = 7 // 2", "goto done", "local t = math.type(1)", "local s = string.pack('<I', 1)",
                    "local b = 1 << 3", "table.move(a, 1, 2, 3)"):
            with self.assertRaises(ValueError, msg=bad):
                pack_addon.check_lua_source(head + bad + "\n", "mods/keg/x")
        # the same text inside a comment or a string is fine
        pack_addon.check_lua_source(head + "-- a // b\nlocal s = 'x // y'\n", "mods/keg/x")

    def test_compile_gate_catches_a_syntax_error(self):
        self.assertEqual(pack_addon.compile_check(SOURCE), "ok")
        with self.assertRaises(ValueError):
            pack_addon.compile_check(SOURCE.replace("local function pause()", "local function pause(", 1))
        with self.assertRaises(ValueError):                 # accepted by Lua 5.3+, refused by LuaJIT
            pack_addon.compile_check("local a = 7 // 2")

    def test_archive_round_trip(self):
        body = SOURCE.encode("utf-8")
        archive = pack_addon.make_archive({"mods/keg/stat_tuner_recon": body})
        self.assertEqual(len(archive) % 16, 0)
        self.assertEqual(pack_addon.read_archive(archive)[0][1], body)
        first = archive[104 + 80 + (-(104 + 80) % 16) + 8:][:40]
        self.assertEqual(first, b"-- HD2-Addon: mods/keg/stat_tuner_recon\n")
        with self.assertRaises(ValueError):
            pack_addon.read_archive(archive[:-16])


# (name, text to find, replacement) -- each must break the baseline
MUTATIONS = [
    ("address passed as a number, not a pointer",
     "if read_memory(process, ffi.cast(cvoid, address), a.buffer, size, got) == 0 then return false end",
     "if read_memory(process, address, a.buffer, size, got) == 0 then return false end"),
    ("u32 read passes a number",
     "if read_memory(process, ffi.cast(cvoid, address), cell, 4, got) == 0 then return nil end",
     "if read_memory(process, address, cell, 4, got) == 0 then return nil end"),
    ("array pointer always treated as a relative offset",
     "    if pointer < size then\n        rows_at, form = payload + pointer",
     "    if true then\n        rows_at, form = payload + pointer"),
    ("records start forgets the bucket array",
     "records_at = payload + fit.buckets * 16, stride = stride, index = index,",
     "records_at = payload, stride = stride, index = index,"),
    ("i32 read as unsigned",
     "if storage == 'i32' and bits >= 2147483648 then return bits - 4294967296 end",
     ""),
    ("sweep reads pages that are not in memory",
     "                if present[k] then\n                    local last = k",
     "                if true then\n                    local last = k"),
    ("fast pass reads allocations whose first page is not in memory",
     "            if base == allocation and (A.present(base, 1) or {})[1] then",
     "            if base == allocation then"),
    ("mapped memory is scanned too",
     "if mem_state == MEM_COMMIT and mem_type == MEM_PRIVATE\n",
     "if mem_state == MEM_COMMIT\n"),
    ("float decoder off by one exponent",
     "return sign * (1 + mantissa / 8388608) * 2 ^ (exponent - 127)",
     "return sign * (1 + mantissa / 8388608) * 2 ^ (exponent - 126)"),
    ("sweep never yields",
     "        offset = offset + CHUNK\n        pause()\n    end\nend",
     "        offset = offset + CHUNK\n    end\nend"),
    ("chunk boundary overlap dropped",
     "if last + 1 <= count + extra and present[last + 1] then bytes = bytes + 4 end",
     ""),
    ("absurd block sizes accepted",
     "if not kind or kind == 0 or not size or size == 0 or size > MAX_BLOCK then return nil end",
     "if not kind or kind == 0 or not size or size == 0 then return nil end"),
    ("file hash skips the last partial chunk",
     "                    if n == 0 then break end\n",
     "                    if n == 0 or n < CHUNK then break end\n"),
    ("row id read from the wrong column",
     "local at = k * stride + spec.id_at",
     "local at = k * stride + spec.id_at + 4"),
    ("header search misses the version word",
     "if words[i] == LDLD and words[i + 1] == 1 then",
     "if words[i] == LDLD and words[i + 1] == 2 then"),
]


class Mutations(unittest.TestCase):
    """Each mutation re-introduces a bug this project (or the skill's case studies) has seen."""

    def test_baseline_is_ok_without_mutation(self):
        game = run_baseline()
        self.addCleanup(game.close)
        self.assertTrue(baseline_ok(game))

    def test_every_mutation_is_caught(self):
        survivors = []
        for name, old, new in MUTATIONS:
            self.assertEqual(SOURCE.count(old), 1, "mutation target not found exactly once: " + name)
            mutated = SOURCE.replace(old, new)
            try:
                game = run_baseline(source=mutated)
            except Exception:
                continue                      # the addon blew up while loading: caught
            try:
                if baseline_ok(game):
                    survivors.append(name)
            finally:
                game.close()
        self.assertEqual(survivors, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
