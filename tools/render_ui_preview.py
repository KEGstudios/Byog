"""Offline preview of actual Gui calls (approximate game font, not an in-game capture)."""
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.test_ui_workbench import MenuRig

out=Path(sys.argv[1])
out.mkdir(parents=True,exist_ok=True)
r=MenuRig()
r.api.overrides['weapon:automatic_cannon:damage']='400'
r.api.overrides['weapon:automatic_cannon:durable_damage']='300'
r.menu.saved_at=9
_,stats=r.api.rows(r.item)
for n,s in stats.items():
    if s=='damage': r.menu.stat[r.item]=n
if len(sys.argv)>2:
    category=sys.argv[2]
    r.item=r.api.use(category,sys.argv[3])
for page in range(1,5):
    r.menu.page=page
    r.draw()
    scale=3  # Preserve fractional icon spans, then downsample for antialiasing.
    im=Image.new('RGB',(r.ui.width*scale,r.ui.height*scale),(17,22,28))
    d=ImageDraw.Draw(im)
    for x in sorted(r.ui.rects.values(),key=lambda x:x.p[3]):
        px,py,w,h=x.p[1],r.ui.height-x.p[2]-x.s[2],x.s[1],x.s[2]
        d.rectangle((px*scale,py*scale,max(px*scale,(px+w)*scale-1),max(py*scale,(py+h)*scale-1)),fill=tuple(int(x.c[i]) for i in [2,3,4]))
    for x in r.ui.texts.values():
        font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',max(8,round(x.s*scale)))
        d.text((x.p[1]*scale,(r.ui.height-x.p[2]-x.s)*scale),x.t,font=font,fill=tuple(int(x.c[i]) for i in [2,3,4]),anchor='lt')
    im=im.resize((r.ui.width,r.ui.height),Image.Resampling.LANCZOS)
    im.save(out/('preview-%d.png'%page))
print(out)
