# HD2 Stat Tuner (work in progress)

A Bingus Shared Loader addon that changes existing weapon / throwable / stratagem values in
memory, for private lobbies with friends. No in-game UI yet; the engine will read a config file.

| Stage | State |
|---|---|
| 0 Offline research | done — `docs/STAT-MAP.md` |
| 1 Read-only recon addon | done — first in-game round OK: 28 of 28 tables, 4074 of 4074 values (`docs/STAT-MAP.md` §0) |
| 2 Patch engine + config format | **v0.3.1: damage, fire rate, recoil and per-weapon armor penetration write-verified in game; per-weapon damage through a row takeover ("own bullet") under test** (`TEST-v0.3.1.md`, `docs/CONFIG-FORMAT.md`) |
| 3 All categories | not started |
| 4 Multiplayer presets | not started |

## Layout

| Path | What |
|---|---|
| `docs/STAT-MAP.md` | every stat: table, field, offset, type, source, confidence |
| `docs/LAYOUTS.txt` | generated record layouts |
| `src/tuner/tuner.lua` | the patch engine (config-driven; version in `src/tuner/version.txt`) |
| `src/recon/recon.lua` | the recon addon (read-only; version in `src/recon/version.txt`) |
| `docs/CONFIG-FORMAT.md` | the config file format |
| `tools/` | offline analysis and build tooling (Python 3.10+, standard library only) |
| `tests/` | offline tests: fake game (`harness.py`), mutation tests, real-Windows-API test |
| `TEST-v0.1.md` | tester checklist for the current build (Turkish) |
| `data/`, `build/`, `dist/` | generated, not committed |
| `reference/` | third-party repositories, pinned in `reference/SOURCES.txt` — read only, not committed |

## Building and testing

```
python tools/dump_typelib.py          # typelib -> data/typelib_all.json
python tools/build_catalog.py         # every stat chain resolved -> data/catalog.json
python tools/gen_recon_data.py        # what the recon addon looks for -> build/recon_data.txt
python tools/pack_addon.py recon      # -> build/recon.lua, dist/HD2-Stat-Tuner-Recon-v<ver>.zip
python tools/gen_tuner_data.py        # items, fields, ranges, verified builds -> build/tuner_data.txt
python tools/pack_addon.py tuner      # -> build/tuner.lua, dist/HD2-Stat-Tuner-v<ver>.zip
python -m unittest tests.test_tuner tests.test_real_tuner tests.test_recon tests.test_real_ffi
```

The tests need `lupa` (LuaJIT runtime for Python): `python -m venv .venv`, then
`.venv\Scripts\python -m pip install lupa` and run the commands with that interpreter.

## Rules this project follows

* Game memory is only touched from inside the game, through the loader. Never from another process.
* The recon build cannot write: it does not even look up a memory-writing function (tested).
* Table sizes, record counts and enum ids are never hard-coded as gates; they drift with game updates.
* Third-party policy: no code is copied from SHODAN Stat Editor or Super-Earth-Armory-Forge;
  they were read for ideas only. The packaging tool is our own implementation of the published
  archive format. `tools/dump_typelib.py` is a Python re-implementation of FileDiver's typelib
  parser (BSD-3-Clause) and is offline tooling only; nothing of it ships in the addon.
