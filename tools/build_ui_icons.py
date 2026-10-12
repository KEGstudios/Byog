"""Compile category vectors and attributed wiki masks to merged Gui.rect spans.

Wiki masks and exact mappings live in assets/wiki; provenance and licensing are
kept alongside them. No PNG/material loader is needed at runtime. Pillow runs
only at build time. Generated Lua stays embedded in tuner.lua.
"""
from pathlib import Path
import json,re
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
ART={}


def shape(name,w=64,h=24):
    im=Image.new('1',(w,h))
    ART[name]=im
    return ImageDraw.Draw(im)


d=shape('rifle')
d.polygon([(2,9),(12,10),(16,7),(43,7),(43,9),(61,9),(61,12),(40,12),(36,15),(25,15),(22,22),(17,21),(19,14),(13,14),(8,18),(2,17)],fill=1)
d.rectangle((23,15,29,21),fill=1); d.rectangle((28,4,33,6),fill=1)
d.rectangle((33,9,39,10),fill=0)
d=shape('sniper')
d.polygon([(1,11),(11,10),(15,8),(35,8),(35,10),(62,10),(62,12),(34,12),(28,15),(21,15),(18,21),(14,20),(16,14),(10,14),(4,18),(1,18)],fill=1)
d.rectangle((17,3,33,5),fill=1); d.rectangle((20,6,22,8),fill=1); d.rectangle((29,6,31,8),fill=1)
d.polygon([(43,12),(45,12),(48,21),(46,21)],fill=1)
d=shape('autocannon')
d.polygon([(1,9),(11,10),(14,6),(39,6),(44,9),(62,9),(62,13),(40,13),(33,17),(18,17),(12,14),(8,18),(1,17)],fill=1)
d.rectangle((21,3,31,5),fill=1); d.ellipse((20,12,32,23),fill=1)
d.rectangle((42,8,47,14),fill=1); d.rectangle((55,8,58,14),fill=1)
d.rectangle((17,8,27,9),fill=0)
d=shape('shotgun')
d.polygon([(1,10),(12,11),(16,8),(61,8),(61,11),(40,11),(40,15),(24,15),(22,12),(14,14),(7,19),(1,17)],fill=1)
d.rectangle((32,12,49,14),fill=1)
for x in (34,38,42,46): d.line((x,12,x,14),fill=0)
d=shape('pistol')
d.polygon([(12,5),(50,5),(50,10),(37,10),(32,14),(29,22),(20,22),(23,11),(12,11)],fill=1)
d.rectangle((27,11,36,15),fill=1); d.rectangle((29,11,34,13),fill=0)
d=shape('revolver')
d.polygon([(13,7),(23,6),(26,4),(36,4),(37,7),(55,7),(55,11),(36,11),(32,16),(29,22),(20,22),(23,13),(15,12)],fill=1)
d.rectangle((26,6,34,12),fill=1); d.line((28,7,28,11),fill=0); d.line((31,7,31,11),fill=0)
d=shape('smg')
d.polygon([(4,9),(16,9),(16,6),(43,6),(43,9),(56,9),(56,12),(41,12),(36,15),(30,15),(30,23),(25,23),(25,14),(20,14),(17,21),(12,20),(15,13),(4,13)],fill=1)
d.rectangle((21,3,25,5),fill=1)
d=shape('machinegun')
d.polygon([(1,9),(12,10),(16,6),(43,6),(43,9),(62,9),(62,12),(43,12),(39,15),(26,15),(24,22),(18,21),(20,14),(12,14),(7,18),(1,17)],fill=1)
d.rectangle((28,13,38,22),fill=1)
d.polygon([(48,12),(50,12),(54,22),(52,22)],fill=1)
d.rectangle((26,3,36,5),fill=1)
d=shape('minigun')
d.rectangle((7,7,27,17),fill=1); d.ellipse((14,11,29,23),fill=1)
for y in (6,10,14): d.rectangle((26,y,61,y+2),fill=1)
d.rectangle((55,5,58,17),fill=1); d.rectangle((28,5,31,17),fill=1)
d.rectangle((11,3,21,4),fill=1); d.rectangle((11,3,13,8),fill=1)
d=shape('launcher')
d.polygon([(2,6),(11,4),(54,4),(60,7),(60,13),(55,16),(12,16),(2,14)],fill=1)
d.rectangle((17,16,21,22),fill=1); d.rectangle((39,16,43,21),fill=1)
d.rectangle((28,1,35,3),fill=1); d.rectangle((6,7,8,13),fill=0); d.rectangle((54,7,56,13),fill=0)
d=shape('grenade_launcher')
d.polygon([(2,10),(14,10),(18,6),(40,6),(40,8),(60,8),(60,13),(38,13),(28,17),(22,16),(19,22),(14,21),(16,14),(8,18),(2,17)],fill=1)
d.ellipse((26,11,40,22),fill=1); d.ellipse((30,14,35,19),fill=0)
d=shape('laser')
d.polygon([(2,9),(14,10),(18,5),(40,5),(44,8),(59,8),(62,10),(59,14),(42,14),(37,18),(27,18),(24,22),(18,21),(20,14),(11,15),(3,18)],fill=1)
for x in (24,29,34): d.rectangle((x,7,x+1,11),fill=0)
d.rectangle((44,5,50,6),fill=1)
d=shape('plasma')
d.polygon([(3,10),(14,10),(19,4),(37,4),(42,7),(59,7),(61,12),(56,16),(35,16),(31,20),(23,20),(20,16),(13,14),(6,19),(3,18)],fill=1)
d.rectangle((26,7,36,10),fill=0); d.rectangle((47,10,56,12),fill=0)
d=shape('flamer')
d.polygon([(2,10),(13,10),(17,7),(38,7),(38,10),(59,10),(59,13),(37,13),(30,17),(23,16),(20,22),(15,21),(17,14),(7,17),(2,17)],fill=1)
d.ellipse((27,13,39,23),fill=1); d.rectangle((51,8,54,15),fill=1)
d.polygon([(59,9),(63,6),(62,10),(63,13),(59,14)],fill=1)
d=shape('crossbow')
d.polygon([(4,10),(23,10),(34,7),(51,7),(51,11),(34,13),(26,15),(23,22),(18,21),(20,14),(5,15)],fill=1)
d.line((44,2,52,11,44,22),fill=1,width=3); d.line((44,2,44,22),fill=1)
d.line((31,10,61,10),fill=1,width=2)
d=shape('spear')
d.polygon([(3,15),(47,7),(47,4),(62,5),(50,12),(49,10),(4,18)],fill=1)
d=shape('blade')
d.polygon([(3,19),(15,13),(17,15),(48,2),(62,2),(54,9),(20,18),(19,21),(15,18),(5,23)],fill=1)
d=shape('axe')
d.polygon([(18,22),(22,23),(41,3),(38,1)],fill=1)
d.polygon([(30,4),(34,1),(51,2),(58,11),(43,14),(41,8)],fill=1)
d=shape('hammer')
d.polygon([(17,22),(21,23),(39,7),(35,4)],fill=1)
d.polygon([(29,3),(34,0),(52,10),(49,16)],fill=1)
d=shape('shovel')
d.polygon([(13,20),(16,23),(42,8),(39,5)],fill=1)
d.polygon([(38,5),(43,0),(56,2),(55,12),(47,15),(40,11)],fill=1)
d=shape('throwable',32,32)
d.ellipse((7,9,25,29),fill=1); d.rectangle((12,5,19,10),fill=1)
d.line((15,4,25,4,28,17),fill=1,width=2)
d.rectangle((10,16,22,17),fill=0); d.rectangle((15,11,16,27),fill=0)
d=shape('stratagem_weapon',32,32)
d.rectangle((4,8,21,15),fill=1); d.rectangle((21,10,30,12),fill=1)
d.rectangle((13,15,17,21),fill=1)
d.line((15,20,4,29),fill=1,width=3); d.line((15,20,27,29),fill=1,width=3)
d=shape('stratagem',32,32)
d.ellipse((5,5,26,26),outline=1,width=2); d.ellipse((12,12,19,19),fill=1)
d.line((15,1,15,9),fill=1,width=2); d.line((15,22,15,30),fill=1,width=2)
d.line((1,15,9,15),fill=1,width=2); d.line((22,15,30,15),fill=1,width=2)
d=shape('backpack',32,32)
d.rounded_rectangle((6,7,26,29),radius=3,fill=1)
d.rectangle((11,3,21,9),outline=1,width=2)
d.rectangle((9,18,23,19),fill=0); d.rectangle((14,12,18,14),fill=0)
d=shape('shield',32,32)
d.polygon([(5,4),(16,1),(27,4),(26,20),(16,30),(6,20)],fill=1)
d.polygon([(8,7),(16,4),(24,7),(23,19),(16,26),(9,19)],fill=0)
d=shape('vehicle',32,32)
d.polygon([(2,15),(8,12),(12,5),(22,5),(27,12),(30,14),(30,23),(2,23)],fill=1)
d.polygon([(13,8),(20,8),(23,13),(10,13)],fill=0)
d.ellipse((4,21,11,28),fill=1); d.ellipse((22,21,29,28),fill=1)
d=shape('armor',32,32)
d.polygon([(5,3),(11,1),(13,7),(19,7),(21,1),(27,3),(25,13),(28,28),(4,28),(7,13)],fill=1)
d.rectangle((10,13,21,14),fill=0); d.rectangle((15,15,16,25),fill=0)
d=shape('armor_passive',32,32)
d.polygon([(16,1),(22,10),(31,12),(24,21),(25,30),(16,25),(7,30),(8,21),(1,12),(10,10)],fill=1)
d.rectangle((14,10,18,23),fill=0); d.rectangle((10,14,22,18),fill=0)
d=shape('attachment',32,32)
d.ellipse((6,6,25,25),fill=1)
for b in [(13,1,18,7),(13,24,18,30),(1,13,7,18),(24,13,30,18),(4,4,9,9),(22,22,27,27),(4,22,9,27),(22,4,27,9)]: d.rectangle(b,fill=1)
d.ellipse((11,11,20,20),fill=0)
d=shape('enemy_weapon',32,32)
d.ellipse((4,2,27,24),fill=1); d.rectangle((9,19,22,29),fill=1)
d.rectangle((7,11,12,16),fill=0); d.rectangle((19,11,24,16),fill=0)
d.polygon([(16,16),(13,21),(18,21)],fill=0)
for x in (12,16,20): d.line((x,25,x,30),fill=0)
d=shape('unknown_weapon',32,32)
d.line((7,9,7,6,12,3,22,3,26,7,26,12,16,19,16,23),fill=1,width=4)
d.rectangle((14,27,18,30),fill=1)
d=shape('status',32,32)
d.polygon([(18,1),(6,18),(14,18),(11,31),(27,12),(18,12)],fill=1)
d=shape('baton')
d.polygon([(7,20),(10,23),(53,7),(54,3),(49,2)],fill=1)
for x,y in [(13,18),(17,16),(21,14)]: d.line((x,y,x+2,y+4),fill=0)
d=shape('flag')
d.polygon([(18,23),(21,23),(24,2),(21,1)],fill=1)
d.polygon([(25,2),(39,5),(55,2),(54,14),(39,17),(24,13)],fill=1)
d.polygon([(31,7),(43,10),(31,11)],fill=0)
ART['weapon']=ART['rifle']


def spans(im):
    """Merge identical horizontal runs on adjacent scanlines into rectangles."""
    done=[]; active={}
    for y in range(im.height+1):
        runs=[]; x=0
        while y<im.height and x<im.width:
            if not im.getpixel((x,y)): x+=1; continue
            start=x
            while x<im.width and im.getpixel((x,y)): x+=1
            runs.append((start,x-start))
        following={}
        for run in runs:
            r=active.pop(run,None)
            if r: r[3]+=1
            else: r=[run[0],y,run[1],1]
            following[run]=r
        done.extend(active.values()); active=following
    return done


def generate():
    wiki=ROOT/'assets/wiki'
    mapping=json.loads((wiki/'mapping.json').read_text(encoding='utf-8')) if wiki.exists() else {}
    sources=json.loads((wiki/'sources.json').read_text(encoding='utf-8')) if wiki.exists() else []
    icon_ids={name:'wiki_'+re.sub('[^a-z0-9]','_',name.lower()) for name in set(mapping.values())}
    assert len(set(icon_ids.values()))==len(icon_ids), 'wiki icon key collision'
    for ref in sources:
        if ref['key'] in icon_ids:
            ART[icon_ids[ref['key']]]=Image.open(wiki/ref['bitmap']).convert('1')
    from ui_type_icons import artwork
    ART.update(artwork())
    types=ROOT/'assets/ui-types'
    type_mapping=json.loads((types/'mapping.json').read_text())
    for ref in json.loads((types/'sources.json').read_text()):
        ART[ref['key']]=Image.open(types/ref['bitmap']).convert('1')
    lines=['-- BEGIN UI ICON DATA (generated by tools/build_ui_icons.py)',
           '-- Wiki reference silhouettes plus original category symbols. x,y,w,h spans.',
           '-- Sources and attribution: assets/wiki/sources.json and ATTRIBUTION.txt.',
           'menu.icons = {']
    for name,im in sorted(ART.items()):
        rs=spans(im)
        assert len(rs)<=90,(name,len(rs))
        lines.append('    '+name+' = { w='+str(im.width)+', h='+str(im.height)+',')
        for i in range(0,len(rs),6):
            lines.append('        '+','.join('{'+','.join(map(str,r))+'}' for r in rs[i:i+6])+',')
        lines.append('    },')
    lines+=['}', '-- WIKI MODEL MAPPING', 'menu.wiki_icons = {']
    for key,name in sorted(mapping.items()):
        lines.append('    ['+json.dumps(key)+'] = '+json.dumps(icon_ids[name])+',')
    lines+=['}', '-- FACTION AND EFFECT ICONS', 'menu.type_icons = {']
    for key,name in sorted(type_mapping.items()):
        assert name in ART,name
        lines.append('    ['+json.dumps(key)+'] = '+json.dumps(name)+',')
    lines+=['}', '-- END UI ICON DATA']
    return '\n'.join(lines)


if __name__=='__main__':
    p=ROOT/'src/tuner/tuner.lua'
    source=p.read_text(encoding='utf-8')
    if '-- BEGIN UI ICON DATA' in source:
        a=source.index('-- BEGIN UI ICON DATA')
        b=source.index('-- END UI ICON DATA',a)+len('-- END UI ICON DATA')
        source=source[:a]+generate()+source[b:]
    else:
        source=source.replace('local function menu_draw(now)',generate()+'\n\nlocal function menu_draw(now)',1)
    p.write_text(source,encoding='utf-8',newline='\n')
    print('Generated',len(ART),'UI silhouettes and symbols;',sum(len(spans(i)) for i in ART.values()),'rectangles total')
