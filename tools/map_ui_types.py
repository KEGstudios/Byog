"""Build explicit type mappings from reviewed names; reject catalog drift."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.test_ui_workbench import MenuRig
from ui_type_icons import FACTIONS,EFFECTS
ROOT=Path(__file__).resolve().parents[1]

def main():
    r=MenuRig(); mapping={}; audit=[]
    for category,families in [('enemy_weapon',{'wiki_faction_'+k:v for k,v in FACTIONS.items()}),('status',EFFECTS)]:
        names={}
        for icon,group in families.items():
            for name in group.split('|'):
                assert name not in names,name
                names[name]=icon
        entries=list(r.api.lists()[category].values())
        assert set(names)=={e.name for e in entries},(category,set(names)^{e.name for e in entries})
        for e in entries:
            icon=names[e.name]
            for name in [e.name]+([m.name for m in e.members.values()] if e.members else []):
                key=category+':'+name
                assert key not in mapping or mapping[key]==icon,key
                mapping[key]=icon
            audit.append(dict(category=category,name=e.name,icon=icon))
    dest=ROOT/'assets/ui-types';dest.mkdir(exist_ok=True)
    for name,data in [('mapping',mapping),('coverage',audit)]:
        (dest/(name+'.json')).write_text(json.dumps(data,indent=2),encoding='utf-8')
    print('Mapped',len(audit),'entries;',len(mapping),'explicit names')
if __name__=='__main__':main()
