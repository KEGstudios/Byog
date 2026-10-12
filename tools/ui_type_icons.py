"""Original, code-native status pictograms and reviewed faction assignments.

Status pictograms denote a family, not an assertion about undocumented behavior.
Enemy membership reference: https://helldivers.wiki.gg/wiki/Factions (2026-10-08).
"""
from PIL import Image,ImageDraw

FACTIONS={
 'terminid': '''cha_warrior_big_tier2|Bile Spewer|cha_scavenger_spitter|Bile Titan|cha_warrior_acid|Brood Commander|Charger|Charger Behemoth|cha_dragon|cha_warrior_plus|cha_hive_lord|Hunter|Impaler|Nursing Spewer|cha_charger_burrower|cha_boomer_burrower|cha_warrior_burrower|Scavenger|Shrieker|bug_spawner_shrieker|cha_charger_acid|Spore Spewer|Stalker|Terminid: not identified|Warrior''',
 'automaton': '''Agitator|Annihilator Tank|cyborg_turret_autocannons|Automaton Fabricator|cyborg_tank_base|Automaton: not identified|Barrager Tank|Berserker|cha_conscript_melee|Cannon Turret|Command Bunker|Commissar|soldier_flamer|Devastator|Dropship|Factory Strider|cyborg_gunship|Heavy Devastator|Hulk|soldier_machinegun_flm|MG Emplacement|MG Raider|cyborg_turret_mortar|Pyro Trooper|Radical|Rocket Devastator|conscript_cannon|cyborg_walker_scout|Shredder Tank|Trooper|cyborg_siege_engine|cyborg_assault_walker''',
 'illuminate': '''Crescent Overseer|cha_bodyhorror_helmetguy|Elevated Overseer|Fleshmob|cha_exomech_ranged|Gazer|Harvester|Illuminate Overship|Illuminate: not identified|illuminate_war_machine|Overseer|illuminate_attack_ship|cha_exomech_melee|Voteless|illuminate_dropship|cha_observer|cha_bodyhorror_bladed'''
}
EFFECTS={
 'wiki_effect_acid':'Acid',
 'wiki_effect_gas':'Gas|backpack_chemicals',
 'wiki_effect_bleed':'bleed',
 'wiki_effect_fire':'Burning|Fire|cyborg_fire|flamerslowed|lava|thermite',
 'effect_thorns':'barbwire|cactus|thornbush',
 'effect_blind':'blind',
 'effect_cold':'blizzard|extreme_cold|snow',
 'effect_plant':'Bush',
 'effect_breath':'choked',
 'effect_confusion':'confusion',
 'effect_shield':'Constitution|weather_insulated',
 'effect_void':'Dark|gloom',
 'effect_deaf':'deaf',
 'effect_march':'death_march',
 'effect_electric':'electric',
 'effect_light':'flashlighted',
 'effect_hidden':'hidden',
 'effect_heat':'Hotshot|intense_heat',
 'effect_scramble':'illuminate_scrambler',
 'effect_aim':'inverted_aim_assist',
 'effect_mud':'mud',
 'effect_poison':'Poison',
 'effect_explosion':'post_mortem_explosion',
 'effect_damage':'pure_damage',
 'effect_radiation':'Radiation',
 'effect_root':'rooted',
 'effect_sand':'sand|sandstorm',
 'effect_slow':'slowed',
 'effect_smoke':'smoke_covered',
 'effect_heal':'Stim',
 'effect_stun':'Stun',
 'effect_water':'submerged',
 'effect_tornado':'tornadostun',
 'effect_tremor':'tremor',
}

def artwork():
    art={}
    def start(name):
        im=Image.new('1',(32,32));art['effect_'+name]=im
        return ImageDraw.Draw(im)
    def eye(d):
        d.polygon([(2,16),(9,8),(23,8),(30,16),(23,24),(9,24)],outline=1,width=2)
        d.ellipse((12,12,20,20),fill=1)
    d=start('electric');d.polygon([(18,1),(5,19),(14,19),(11,31),(28,11),(19,11)],fill=1)
    d=start('stun');d.ellipse((10,12,22,26),outline=1,width=2)
    for x,y in [(5,7),(25,7),(16,3)]:d.line((x-3,y,x+3,y),fill=1,width=2);d.line((x,y-3,x,y+3),fill=1,width=2)
    d=start('heal');d.rounded_rectangle((2,2,29,29),radius=5,outline=1,width=2);d.rectangle((13,7,18,24),fill=1);d.rectangle((7,13,24,18),fill=1)
    d=start('cold')
    for line in [(16,2,16,30),(3,8,29,24),(3,24,29,8),(11,4,16,8,21,4),(11,28,16,24,21,28)]:d.line(line,fill=1,width=2)
    d=start('thorns');d.line((2,22,29,9),fill=1,width=3)
    for x,y in [(8,19),(16,15),(24,11)]:d.line((x-2,y-5,x+2,y+5),fill=1,width=2)
    d=start('blind');eye(d);d.rectangle((2,13,29,18),fill=1)
    d=start('hidden');eye(d);d.line((3,2,29,30),fill=0,width=6);d.line((3,2,29,30),fill=1,width=2)
    d=start('plant');d.line((16,30,16,9),fill=1,width=2);d.polygon([(16,19),(4,15),(2,5),(12,8)],fill=1);d.polygon([(17,24),(28,19),(30,9),(21,12)],fill=1)
    d=start('breath');d.line((16,3,16,12,9,17),fill=1,width=2);d.line((16,12,23,17),fill=1,width=2)
    d.ellipse((3,11,13,28),outline=1,width=2);d.ellipse((19,11,29,28),outline=1,width=2)
    d=start('confusion');d.arc((6,2,26,19),175,470,fill=1,width=3);d.line((17,18,16,23),fill=1,width=3);d.rectangle((14,27,18,30),fill=1)
    d=start('shield');d.polygon([(4,5),(16,1),(28,5),(26,21),(16,30),(6,21)],outline=1,width=2);d.line((10,15,15,20,23,10),fill=1,width=3)
    d=start('void');d.ellipse((2,2,30,30),outline=1,width=2);d.arc((7,7,25,25),20,300,fill=1,width=3);d.ellipse((13,13,19,19),fill=1)
    d=start('deaf');d.arc((8,2,26,23),160,395,fill=1,width=3);d.line((12,19,12,25,8,28),fill=1,width=3);d.line((3,4,29,29),fill=1,width=2)
    d=start('march');d.polygon([(6,4),(16,4),(16,17),(28,20),(28,27),(4,27),(4,20),(6,18)],outline=1,width=2);d.line((7,23,25,23),fill=1,width=2)
    d=start('light');d.polygon([(2,12),(14,12),(14,20),(2,20)],fill=1);d.polygon([(16,11),(29,4),(29,28),(16,21)],outline=1,width=2)
    d=start('heat');d.rounded_rectangle((12,2,20,24),radius=4,outline=1,width=2);d.ellipse((9,19,23,31),fill=1);d.line((16,8,16,24),fill=1,width=2)
    d=start('scramble')
    for points in [(3,7,12,7,12,13,27,13),(4,25,20,25,20,18,28,18)]:d.line(points,fill=1,width=3)
    d.rectangle((20,3,25,7),fill=1);d.rectangle((7,16,11,20),fill=1)
    d=start('aim');d.arc((4,4,28,28),20,165,fill=1,width=2);d.arc((4,4,28,28),200,345,fill=1,width=2);d.polygon([(3,12),(10,15),(2,20)],fill=1);d.polygon([(29,20),(22,17),(30,12)],fill=1);d.ellipse((13,13,19,19),fill=1)
    d=start('mud');d.polygon([(10,3),(18,3),(19,17),(25,21),(25,25),(7,25),(8,17)],fill=1);d.line((2,29,30,29),fill=1,width=2);d.line((2,21,5,19),fill=1,width=2)
    d=start('poison');d.ellipse((6,3,26,23),fill=1);d.rectangle((11,19,21,28),fill=1);d.ellipse((9,10,14,15),fill=0);d.ellipse((18,10,23,15),fill=0);d.line((16,24,16,28),fill=0,width=2)
    d=start('explosion');d.polygon([(16,1),(19,10),(29,4),(24,15),(31,20),(21,22),(23,31),(15,25),(7,30),(9,21),(1,17),(10,13),(6,3)],fill=1)
    d=start('damage');d.ellipse((6,6,26,26),outline=1,width=2);d.ellipse((13,13,19,19),fill=1)
    for line in [(16,1,16,9),(16,23,16,31),(1,16,9,16),(23,16,31,16)]:d.line(line,fill=1,width=2)
    d=start('radiation');d.ellipse((13,13,19,19),fill=1)
    for a in (30,150,270):d.pieslice((2,2,30,30),a,a+60,fill=1)
    d.ellipse((10,10,22,22),fill=0);d.ellipse((13,13,19,19),fill=1)
    d=start('root');d.line((16,2,16,21),fill=1,width=3);d.line((3,22,29,22),fill=1,width=2)
    for points in [(16,17,8,26,4,29),(16,21,16,30),(16,17,24,25,28,28)]:d.line(points,fill=1,width=2)
    d=start('sand')
    for y in (7,15,23):d.line((3,y,26,y),fill=1,width=2)
    for x,y in [(5,3),(13,11),(23,19),(8,27),(28,28)]:d.rectangle((x,y,x+2,y+2),fill=1)
    d=start('slow');d.line((6,3,26,3),fill=1,width=2);d.line((6,29,26,29),fill=1,width=2);d.polygon([(9,4),(23,4),(23,9),(17,16),(23,23),(23,28),(9,28),(9,23),(15,16),(9,9)],outline=1,width=2);d.polygon([(11,26),(21,26),(16,20)],fill=1)
    d=start('smoke')
    for b in [(2,15,17,28),(10,5,25,23),(18,14,30,28)]:d.ellipse(b,fill=1)
    d.rectangle((7,23,25,28),fill=1)
    d=start('water')
    for y in (9,18,27):d.line((2,y,8,y-3,16,y+1,24,y-3,30,y),fill=1,width=2)
    d=start('tornado')
    for y,x0,x1 in [(4,2,29),(10,6,26),(16,9,23),(22,12,20),(28,15,18)]:d.line((x0,y,x1,y),fill=1,width=2)
    d=start('tremor');d.line((1,17,7,17,11,6,16,28,21,11,25,17,31,17),fill=1,width=2)
    return art
