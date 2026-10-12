"""Build explicit UI mappings from the published catalog and reviewed wiki assets."""
from pathlib import Path
import json,re,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tests.test_ui_workbench import MenuRig

def norm(s): return re.sub('[^a-z0-9]','',s.lower())

def main():
    dest=ROOT/'assets/wiki'
    refs=json.loads((dest/'sources.json').read_text(encoding='utf-8'))
    by_title={}
    for ref in refs: by_title.setdefault(norm(ref['title']),ref)
    aliases={
      'G-89 Smokescreen':'G-89_Smokescreen',
      'B-01 Tactical':'B-01_Tactical_v1',
      'M-102 Gunner FRV':'stratagem_Fast_Recon_Vehicle',
      'sentries_laser_cannon_sentry':'stratagem_Laser_Sentry',
      'eagle_airstrike_smoke':'stratagem_Eagle_Smoke_Strike',
      'eagle_clusterbombs':'stratagem_Eagle_Cluster_Bomb',
      'orbital_120mm_he_strike':'stratagem_Orbital_120mm_HE_Barrage',
      'orbital_railcannon':'stratagem_Orbital_Railcannon_Strike',
      'Concussive Padding, Grenadier':'passive_Concussive_Padding',
      'Concussive Padding, Hazmat':'passive_Concussive_Padding',
      'Concussive Padding, Reinforced':'passive_Concussive_Padding',
    }
    by_key={r['key']:r for r in refs}
    for title,key in aliases.items():
        assert key in by_key,(title,key)
        by_title[norm(title)]=by_key[key]
    r=MenuRig(); mapping={}; audit=[]
    for category,items in r.api.lists().items():
        for e in items.values():
            title=e.display or e.name
            lookup=re.sub(r'\s*\(\d+\)$','',title) if category=='armor_passive' else title
            ref=by_title.get(norm(lookup))
            if not ref and category in ('stratagem_weapon','backpack','shield','vehicle'):
                lookup=re.sub(r'\s*\([^)]*\)$','',title)
                lookup=re.sub(r'^[A-Z0-9/]+-[A-Z0-9]+\s+','',lookup)
                ref=by_title.get(norm(lookup)) or by_title.get(norm(e.name))
            if category in ('enemy_weapon','unknown_weapon','status','attachment'): ref=None
            key=category+':'+e.name
            if ref: mapping[key]=ref['key']
            members=[]
            if e.members:
                for m in e.members.values():
                    mt=m.display or m.name
                    mr=by_title.get(norm(mt))
                    if mr and ref: mapping[category+':'+m.name]=mr['key']
                    members.append({'name':m.name,'display':m.display})
            audit.append({'category':category,'name':e.name,'display':e.display,
              'wiki_asset':ref['key'] if ref else None,
              'kind':('wiki badge' if ref['key'].startswith(('stratagem_','passive_')) else 'wiki model silhouette') if ref else 'generic category symbol: no verified model mapping',
              'members':members})
    (dest/'mapping.json').write_text(json.dumps(mapping,indent=2),encoding='utf-8')
    (dest/'coverage.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    from collections import Counter
    print('Matched entries:',dict(Counter(e['category'] for e in audit if e['wiki_asset'])))
    print('Explicit mapping keys:',len(mapping))

if __name__=='__main__': main()
