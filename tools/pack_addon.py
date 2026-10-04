# -*- coding: utf-8 -*-
"""Build and package an addon for Bingus Shared Loader.

    python tools/pack_addon.py recon        # -> build/recon.lua, dist/HD2-Stat-Tuner-Recon-v<ver>.zip

Written for this project from the published description of the formats; no third-party code.

Patch archive (`9ba626afa44a3aa3.patch_N`), little-endian:

    +0    72 B  header   u32 magic 0xF0000011, u32 1, u32 resource count, 20 zero bytes,
                         u64 total size, u64 0, 24 zero bytes
    +72   32 B  type row u32 0, u32 0, u64 type id, u32 count, u32 0, u32 16, u32 16
    +104  80 B  per resource: u64 name hash, u64 type id, u64 offset, 4 x u64 0,
                         u32 length, u32 0, u32 0, u32 16, u32 16, u32 index
    data        starts at align16(104 + 80 * count); every resource is padded to 16 bytes
    resource    u32 body length, u32 2, body

A resource's name hash is MurmurHash64A (seed 0) of its name; Lua resources use type id
0xA14E8DFA2CD117E2. The loader discovers an addon by the plaintext first line of its entry
resource:  `-- HD2-Addon: mods/<author>/<name>`.

Mod-manager package (zip): manifest.json + Addon/<archive> (+ two empty companion files).
"""
import argparse
import json
import os
import re
import struct
import sys
import uuid
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from hashnames import murmur64a  # noqa: E402

ARCHIVE_MAGIC = 0xF0000011
LUA_TYPE = 0xA14E8DFA2CD117E2
ARCHIVE_FILE = "9ba626afa44a3aa3.patch_0"
NAME_RE = re.compile(r"mods/[A-Za-z0-9_]+/[A-Za-z0-9_]+")
ILLEGAL_TITLE_CHARS = set('\\/:*?"<>|')
# Lua 5.3+/5.4 syntax and library calls that LuaJIT (the game's runtime) does not have.
FORBIDDEN = [(re.compile(r"[\w\)\]]\s*//\s*[\w\(]"), "integer division '//'"),
             (re.compile(r"\bgoto\s+\w"), "goto"),
             (re.compile(r"\bmath\.type\b"), "math.type"),
             (re.compile(r"\bstring\.pack\b|\bstring\.unpack\b"), "string.pack/unpack"),
             (re.compile(r"\btable\.move\b|\btable\.unpack\b"), "table.move/unpack"),
             (re.compile(r"\butf8\."), "utf8 library"),
             (re.compile(r"[\w\)\]]\s*(<<|>>)\s*[\w\(]"), "bit shift operator")]

ADDONS = {
    "tuner": {
        "source": os.path.join("src", "tuner", "tuner.lua"),
        "version_file": os.path.join("src", "tuner", "version.txt"),
        "data": os.path.join("build", "tuner_data.txt"),
        "resource": "mods/keg/byog",
        "title": "BYOG - Balance Your Own Game",
        "zip": "BYOG-v%s.zip",
        "icon": os.path.join("assets", "logo.png"),
        "description": ("Balance Your Own Game: change the values of weapons, throwables, stratagems, backpacks, "
                        "shields and vehicles from an in-game menu (F9) or a config file in %LOCALAPPDATA%\\BYOG. "
                        "Needs Bingus Shared Loader v15 or newer (the loader is the only requirement)."),
    },
    "recon": {
        "source": os.path.join("src", "recon", "recon.lua"),
        "version_file": os.path.join("src", "recon", "version.txt"),
        "data": os.path.join("build", "recon_data.txt"),
        "resource": "mods/keg/stat_tuner_recon",
        "title": "HD2 Stat Tuner Recon",
        "zip": "HD2-Stat-Tuner-Recon-v%s.zip",
        "description": ("Read-only diagnostic build: finds the game's data tables and writes a report to "
                        "%LOCALAPPDATA%\\HD2StatTuner\\STATUS.txt. It changes nothing in the game. "
                        "Needs Bingus Shared Loader v15 or newer (the loader is the only requirement)."),
    },
}


def make_archive(resources):
    """resources: {resource name: body bytes} -> archive bytes."""
    items = sorted((murmur64a(name.encode("utf-8")), body) for name, body in resources.items())
    count = len(items)
    if count == 0:
        raise ValueError("an archive needs at least one resource")
    offset = (104 + 80 * count + 15) & ~15
    out = bytearray(offset)
    entries = bytearray()
    for index, (name_hash, body) in enumerate(items):
        resource = struct.pack("<II", len(body), 2) + body
        entries += struct.pack("<7Q6I", name_hash, LUA_TYPE, offset, 0, 0, 0, 0,
                               len(resource), 0, 0, 16, 16, index)
        out += resource
        out += b"\0" * (-len(out) % 16)
        offset = len(out)
    header = struct.pack("<III20sQQ24s", ARCHIVE_MAGIC, 1, count, b"", len(out), 0, b"")
    types = struct.pack("<IIQIIII", 0, 0, LUA_TYPE, count, 0, 16, 16)
    out[:104 + len(entries)] = header + types + entries
    return bytes(out)


def read_archive(data):
    """-> [(name hash, body bytes)]; raises on a malformed archive. Used to verify what we wrote."""
    magic, one, count = struct.unpack_from("<III", data, 0)
    total = struct.unpack_from("<Q", data, 32)[0]
    if magic != ARCHIVE_MAGIC or one != 1 or total != len(data):
        raise ValueError("bad archive header")
    out = []
    for i in range(count):
        row = 104 + 80 * i
        name_hash, type_id, offset = struct.unpack_from("<3Q", data, row)
        length = struct.unpack_from("<I", data, row + 56)[0]
        body_len, version = struct.unpack_from("<II", data, offset)
        if type_id != LUA_TYPE or version != 2 or body_len + 8 != length:
            raise ValueError("bad resource entry %d" % i)
        out.append((name_hash, data[offset + 8:offset + 8 + body_len]))
    return out


def check_lua_source(text, resource):
    """Raises ValueError when the source cannot be an addon entry or uses non-LuaJIT syntax."""
    if not NAME_RE.fullmatch(resource):
        raise ValueError("resource name must look like mods/<author>/<name>")
    first = text.split("\n", 1)[0].rstrip("\r")
    if first != "-- HD2-Addon: " + resource:
        raise ValueError("first line must be exactly '-- HD2-Addon: %s'" % resource)
    raw = text.encode("utf-8")
    if raw.startswith(b"\xef\xbb\xbf") or b"\0" in raw:
        raise ValueError("entry must be plain UTF-8 Lua without a BOM")
    # strip long strings, short strings and comments before the token scan
    code = re.sub(r"\[(=*)\[.*?\]\1\]", '""', text, flags=re.S)
    code = re.sub(r"--[^\n]*", "", code)
    code = re.sub(r"'(?:\\.|[^'\\\n])*'|\"(?:\\.|[^\"\\\n])*\"", '""', code)
    for pattern, what in FORBIDDEN:
        m = pattern.search(code)
        if m:
            line = code.count("\n", 0, m.start()) + 1
            raise ValueError("not LuaJIT-compatible: %s (near line %d)" % (what, line))


def compile_check(text):
    """Compile (not run) the source on LuaJIT when lupa is available. -> 'ok' | 'skipped'."""
    try:
        from lupa.luajit21 import LuaRuntime
    except Exception:
        return "skipped (lupa with LuaJIT is not installed)"
    lua = LuaRuntime(encoding=None)
    check = lua.eval("function(src) local f, e = loadstring(src, '=addon'); return e or '' end")
    err = check(text.encode("utf-8"))
    if err:
        raise ValueError("LuaJIT refuses the source: %s" % err.decode("utf-8", "replace"))
    return "ok"


def render(kind, version=None, data=None):
    """Substitute version and generated data into the addon source. -> (text, version).
    `data` replaces the generated blob (tests use it to pin their own fake build)."""
    spec = ADDONS[kind]
    with open(os.path.join(ROOT, spec["source"]), encoding="utf-8", newline="") as f:
        text = f.read().replace("\r\n", "\n")
    if version is None:
        with open(os.path.join(ROOT, spec["version_file"]), encoding="utf-8") as f:
            version = f.read().strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("version must look like 1.2.3")
    if data is None:
        if kind == "tuner":
            # always regenerate: a stale blob once shipped a build without its newest data lines
            import gen_tuner_data
            data, _stats = gen_tuner_data.generate()
            os.makedirs(os.path.dirname(os.path.join(ROOT, spec["data"])), exist_ok=True)
            with open(os.path.join(ROOT, spec["data"]), "w", encoding="utf-8", newline="\n") as f:
                f.write(data)
        else:
            with open(os.path.join(ROOT, spec["data"]), encoding="utf-8") as f:
                data = f.read()
    if "]==]" in data:
        raise ValueError("data blob contains the long-string terminator")
    for token in ("@@VERSION@@", "@@DATA@@"):
        if text.count(token) != 1:
            raise ValueError("expected exactly one %s in the source" % token)
    return text.replace("@@VERSION@@", version).replace("@@DATA@@", data), version


def package(kind, version=None, out_dir=None, flat=False):
    spec = ADDONS[kind]
    text, version = render(kind, version)
    check_lua_source(text, spec["resource"])
    compiled = compile_check(text)
    title = spec["title"]
    if ILLEGAL_TITLE_CHARS.intersection(title) or not title.isascii():
        raise ValueError("package title must be ASCII without \\ / : * ? \" < > |")
    body = text.encode("utf-8")
    archive = make_archive({spec["resource"]: body})
    back = read_archive(archive)
    if back != [(murmur64a(spec["resource"].encode()), body)]:
        raise ValueError("archive round-trip failed")

    build_dir = os.path.join(ROOT, "build")
    os.makedirs(build_dir, exist_ok=True)
    with open(os.path.join(build_dir, kind + ".lua"), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)

    manifest = {
        "Version": 1,
        "Guid": str(uuid.uuid5(uuid.NAMESPACE_URL, "hd2-stat-tuner/" + spec["resource"])),
        "Name": title,
        "Description": spec["description"],
        "Options": [{"Name": title, "Description": spec["description"], "Include": ["Addon"]}],
    }
    icon = None
    if spec.get("icon") and os.path.exists(os.path.join(ROOT, spec["icon"])):
        with open(os.path.join(ROOT, spec["icon"]), "rb") as f:
            icon = f.read()
        manifest["IconPath"] = "icon.png"
    files = {
        "manifest.json": (json.dumps(manifest, indent=2) + "\n").encode("utf-8"),
        "Addon/" + ARCHIVE_FILE: archive,
        "Addon/" + ARCHIVE_FILE + ".stream": b"",
        "Addon/" + ARCHIVE_FILE + ".gpu_resources": b"",
    }
    # Second layout seen in released mods: no options, the archive at the zip root. Only built on
    # request (--flat), as a fallback for a mod manager that refuses the options layout.
    flat_manifest = {k: v for k, v in manifest.items() if k != "Options"}
    flat_files = {
        "manifest.json": (json.dumps(flat_manifest, indent=2) + "\n").encode("utf-8"),
        ARCHIVE_FILE: archive,
        ARCHIVE_FILE + ".stream": b"",
        ARCHIVE_FILE + ".gpu_resources": b"",
    }
    if icon:
        files["icon.png"] = flat_files["icon.png"] = icon
    out_dir = out_dir or os.path.join(ROOT, "dist")
    os.makedirs(out_dir, exist_ok=True)
    zip_path = os.path.join(out_dir, spec["zip"] % version)
    flat_path = zip_path[:-4] + "-flat.zip"
    targets = [(zip_path, files)] + ([(flat_path, flat_files)] if flat else [])
    for target, contents in targets:
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for path, content in sorted(contents.items()):
                info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                z.writestr(info, content)
    return {"zip": zip_path, "flat_zip": flat_path if flat else None, "version": version, "lua_bytes": len(body),
            "archive_bytes": len(archive),
            "compile": compiled, "resource_hash": "0x%016X" % murmur64a(spec["resource"].encode())}


def main():
    ap = argparse.ArgumentParser(description="Build and package an addon.")
    ap.add_argument("kind", choices=sorted(ADDONS))
    ap.add_argument("--version")
    ap.add_argument("--flat", action="store_true", help="also build the flat-layout zip")
    a = ap.parse_args()
    info = package(a.kind, a.version, flat=a.flat)
    print("built %s" % os.path.relpath(info["zip"], ROOT))
    for k in ("version", "lua_bytes", "archive_bytes", "compile", "resource_hash"):
        print("  %-14s %s" % (k, info[k]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
