"""Package a UI-only preview using the byte-exact catalog of the published 2.0.0.

No private game data regeneration is required. Refuses any engine/data drift.
Usage: python tools/pack_ui_preview.py --out dist/ui-preview
Requires lupa (LuaJIT compile check is mandatory).
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
import pack_addon

ROOT=Path(__file__).resolve().parents[1]


def without_ui(source):
    start=source.index('local MENU_ZH = {')
    end=source.index('local function L(text)',start)
    source=source[:start]+source[end:]
    if 'menu.descriptions = {' in source:
        start=source.index('menu.descriptions = {')
        end=source.index('local function menu_draw(now)',start)
        source=source[:start]+source[end:]
    start=source.index('local function menu_draw(now)')
    end=source.index('local function menu_tick()',start)
    return source[:start]+source[end:]


def package(out):
    with zipfile.ZipFile(ROOT/'dist/BYOG-v2.0.0.zip') as z:
        files={n:z.read(n) for n in z.namelist()}
    resource='Addon/'+pack_addon.ARCHIVE_FILE
    entries=pack_addon.read_archive(files[resource])
    assert len(entries)==1
    baseline=entries[0][1].decode('utf-8')
    data=baseline.split('local DATA = [==[\n',1)[1].split(']==]',1)[0]
    source,version=pack_addon.render('tuner',version='2.0.0',data=data)
    assert without_ui(source)==without_ui(baseline), 'Engine code changed outside permitted UI boundaries'
    pack_addon.check_lua_source(source,'mods/keg/byog')
    compiled=pack_addon.compile_check(source)
    assert compiled=='ok', 'LuaJIT compile required: '+compiled
    archive=pack_addon.make_archive({'mods/keg/byog':source.encode('utf-8')})
    assert pack_addon.read_archive(archive)==[(entries[0][0],source.encode('utf-8'))]
    packaged_data=source.split('local DATA = [==[\n',1)[1].split(']==]',1)[0]
    assert packaged_data.encode()==data.encode()
    files[resource]=archive
    manifest=json.loads(files['manifest.json'])
    has_icons='-- BEGIN UI ICON DATA' in source
    cursor_fix='-- UI POINTER RECENTER FILTER' in source
    wiki_icons='-- WIKI MODEL MAPPING' in source
    type_icons='-- FACTION AND EFFECT ICONS' in source
    manifest['Name']='BYOG - Field Workbench UI Preview' + (' - Icons' if has_icons else '')
    if cursor_fix: manifest['Name']+=' - Cursor Preview'
    if wiki_icons: manifest['Name']='BYOG - Field Workbench - Wiki Icons Preview'
    manifest['Description']='A+C interface preview for BYOG 2.0.0. Same engine, verified game build and catalog. Replaces the original BYOG; enable only one version. Settings remain in LOCALAPPDATA/BYOG.'
    if wiki_icons:
        manifest['Description']+=' Wiki-referenced model silhouettes and equipment badges. Unverified items use generic symbols. See UI-ATTRIBUTION.txt.'
        files['UI-ATTRIBUTION.txt']=(ROOT/'assets/wiki/ATTRIBUTION.txt').read_bytes()
        files['UI-ASSET-SOURCES.json']=(ROOT/'assets/wiki/sources.json').read_bytes()
    elif has_icons: manifest['Description']+=' Original schematic category/weapon-family silhouettes; not extracted game artwork.'
    if type_icons:
        manifest['Name']='BYOG - Field Workbench - Factions and Effects Preview'
        files['UI-TYPE-SOURCES.json']=(ROOT/'assets/ui-types/sources.json').read_bytes()
        files['UI-TYPE-MAPPING.json']=(ROOT/'assets/ui-types/coverage.json').read_bytes()
    if cursor_fix: manifest['Description']+=' Experimental UI-only filter for edge-to-center cursor resets; native input hooks unchanged.'
    for option in manifest.get('Options',[]):
        option['Name']=manifest['Name']
        option['Description']=manifest['Description']
    # Same resource/Guid intentionally: replacement, never a second simultaneously running addon.
    files['manifest.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    out=Path(out)
    out.mkdir(parents=True,exist_ok=True)
    target=out/('BYOG-v2.0.0-AC-UI-Icons-Preview.zip' if has_icons else 'BYOG-v2.0.0-AC-UI-Preview.zip')
    if cursor_fix: target=out/'BYOG-v2.0.0-AC-UI-Icons-Cursor-Preview.zip'
    if wiki_icons: target=out/'BYOG-v2.0.0-AC-UI-Wiki-Preview.zip'
    if type_icons: target=out/'BYOG-v2.0.0-AC-UI-Factions-Effects-Preview.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        for name,body in sorted(files.items()): z.writestr(name,body)
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        assert pack_addon.read_archive(z.read(resource))==pack_addon.read_archive(archive)
    report={'base':'BYOG-v2.0.0.zip','version':version,'ui':'Field Workbench A+C',
            'engine_outside_ui_identical':True,'catalog_identical':True,
            'catalog_sha256':hashlib.sha256(data.encode()).hexdigest(),
            'package_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
            'luajit_compile':compiled,'archive_roundtrip':'ok','zip_integrity':'ok',
            'icons':'wiki-referenced silhouettes and badges' if wiki_icons else ('original schematic silhouettes' if has_icons else 'none'),
            'cursor_filter':'edge-to-center heuristic; UI only' if cursor_fix else 'none',
            'in_game_tested':False}
    (out/'build-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    return target


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',default=str(ROOT/'dist/ui-preview'))
    print(package(parser.parse_args().out))
