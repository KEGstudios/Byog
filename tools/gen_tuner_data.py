# -*- coding: utf-8 -*-
"""Generate the data blob that is embedded into the tuner addon.

The engine knows nothing about the game by itself: every table, item, field,
stock value and allowed range comes from this blob, generated from the Stage 0
artefacts (data/catalog.json, the typelib) and the builds verified in game.

Line format ('|' separated):

  V|label|exe_sha256|game_dll_sha256
      a game build this data was verified on (reports/..., docs/STAT-MAP.md §0).
  K|item|stat|text                                 shown beside the game's value of that stat
  J|item|group|section|order                       the menu shows the items of a group as one row, in sections
  T|name|type_hash_hex|shape|stride|id_at          shape: R rows, K keyed, S one record per block
  I|index|category|name|entity16|display name
      display name: the game's own name of the item (tools/display_names.txt), empty when not known.
      Shown in the menu and in catalog.txt; config.txt uses `name`.
  F|item_index|stat|table|key|offset|storage|stock|flags
      one memory field of one stat of one item. key: entity16 (K) or row id (R).
      flags: A = the weapon's default attachment sets this value (STAT-MAP §6.2): the field is
      then the attachment's own value inside the delta storage (table ComponentEntityDeltaStorage,
      key "data", offset inside its data array), not the weapon's record, which the game overwrites.
      Every weapon with the same default attachment names the same field, so they show up as sharing it.
  R|stat|min|max|integer
  A|alias|mode|stat,stat,...     mode: all | nonzero (only fields whose stock value is not 0)
  O|item_index|base_projectile|src_projectile|new_projectile|src_damage|new_damage
      "own bullet": rows nothing references that this weapon may take over (see TAKEOVERS).
      base_projectile is the value in the weapon's own record (0 when only an attachment sets it).
  W|table|row_id|hex            stock bytes of a row involved in a takeover
      base_projectile "-": the item is not a weapon entity (a shell of an orbital / Eagle strike).
  U|item_index|table|offset|projectile
      another place in the item's own records that names a round: an entry of the magazine's belt
      pattern (WeaponMagazineComponent; seen in game: the sentry's gun takes its rounds from there, not
      from the weapon record) or the projectile field of a Bombardment / Eagle / OrbitalAbility
      component. A round other than the weapon's own (a tracer) gets a row of its own as well when it
      uses the same damage row.
  X|item_index|offset|expected  the default ammo attachment's projectile value: offset inside the
                                delta storage's data array, and the value expected there
  G|item_index|run_at|count|resource
      the weapon's default magazine attachment: where the count of its magazine deltas sits inside the
      delta storage's components array, and that count. Writing 0 there switches the attachment's
      magazine values off for every weapon carrying it; the weapons' own records then count.
  H|item_index|stat|table|key|offset|storage|stock   the same stat in the weapon's own record
  B|item_index|kind|explosion|damage|own|shared_damage|switches
      an explosion of the item (tools/blasts.py). kind P: reached through the weapon's projectile row,
      switches = offsets inside that row; C: through the item's component records, switches =
      table:offset. own = 1: nothing else reaches the explosion row. shared_damage = 1: something else
      uses its damage row.
  S|table|id,id,...              rows that may be borrowed (no table in memory refers to them; census)
  P|table|offset,offset,...      words of a row that hold addresses: copied from memory, never from W

    python tools/gen_tuner_data.py        # -> build/tuner_data.txt
"""
import json
import collections
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import blasts  # noqa: E402
import deltas  # noqa: E402
import hd2db  # noqa: E402
import references  # noqa: E402
from dump_typelib import dlsum  # noqa: E402

OUT = os.path.join(ROOT, "build", "tuner_data.txt")
STORAGE = {"UINT32": "u32", "INT32": "i32", "FP32": "f32"}

# Builds verified in game (recon v0.1.0, 2026-10-01).
BUILDS = [
    ("release/01.007.101/19155",
     "F5FEE03DCFDB2E553A4752C283590950AC13316B376D8196AA556FF0400D5F06",
     "2E2C3B7C2500646DADD5F2B4C6E0504DBB7E7896139F64CDDC0D1813C718F51E"),
]

# Where game.dll keeps its id-indexed arrays of row pointers, measured in game (probe v0.3.2):
# build label -> table -> (rva of the slot of id 0, number of slots = highest id + 1).
INDEXES = {
    "release/01.007.101/19155": {"ProjectileSettings": (0x37C7670, 351), "DamageSettings": (0x37C60C0, 650)},
}

CATEGORY = {"primary": "weapon", "secondary": "weapon", "support": "weapon", "melee": "weapon",
            "throwable": "throwable", "backpack": "backpack", "shield": "shield", "vehicle": "vehicle",
            "stratagem": "stratagem", "stratagem_weapon": "stratagem_weapon", "status": "status",
            "enemy_weapon": "enemy_weapon", "unknown_weapon": "unknown_weapon",
            "armor": "armor", "armor_passive": "armor_passive", "attachment": "attachment"}
# WeaponStatModifierType, as far as attachments use it. 0 is added to the weapon's ergonomics, the others
# multiply; each has a twin (the next number) for the weapon's alternate hold. 18 is an empty slot.
# (The enum's member names are not in the type library: read from the values - an "Explosive" load has
# 14 and 16 at 6, a vertical grip lowers 2..5 - and the same as the SHODAN Stat Editor labels them.)
MODIFIERS = {0: "ergonomics", 1: "sway", 2: "recoil_h", 3: "recoil_h_alt", 4: "recoil_v", 5: "recoil_v_alt",
             10: "recoil_climb_h", 11: "recoil_climb_h_alt", 12: "recoil_climb_v", 13: "recoil_climb_v_alt",
             14: "spread_h", 15: "spread_h_alt", 16: "spread_v", 17: "spread_v_alt"}
MODIFIERS_AT, MODIFIER_SLOTS, WEAPON_DATA = 956, 8, 236     # weapon_stat_modifiers; the component's delta index


def attachment_items():
    """Every attachment that changes a weapon's handling, with the numbers it changes."""
    import build_catalog
    assert build_catalog.off("WeaponDataComponent", "weapon_stat_modifiers")[0] == MODIFIERS_AT
    assert deltas.COMPONENT_INDEX[WEAPON_DATA] == "WeaponDataComponent"
    data_start = deltas._load()["xo"]
    out, shown, used = [], {}, set()
    for t in hd2db.table("WeaponCustomizationSettings"):
        data, base = t.data, t.base
        rows, count = struct.unpack_from("<QQ", data, base)
        for i in range(count):
            at = base + rows + i * 88
            name_at, = struct.unpack_from("<Q", data, at)
            name = data[base + name_at:data.index(b"\0", base + name_at)].decode("ascii", "replace").strip()
            item_id, = struct.unpack_from("<I", data, at + 8)
            resource, = struct.unpack_from("<Q", data, at + 32)
            words = {}
            for component, offset, size, raw, where in (deltas.resource_deltas(resource) or []) if resource else []:
                if component == WEAPON_DATA:
                    for k in range(0, size - size % 4, 4):
                        words[offset + k] = (raw[k:k + 4], where + k)
            stats = []
            for slot in range(MODIFIER_SLOTS):
                o = MODIFIERS_AT + slot * 8
                if o in words and o + 4 in words:
                    kind = struct.unpack("<I", words[o][0])[0]
                    if kind in MODIFIERS:
                        sid = "mod_" + MODIFIERS[kind]
                        if sid in [s["id"] for s in stats]:
                            continue                                  # the same value twice: the first counts
                        stats.append({"id": sid, "table": "ComponentEntityDeltaStorage", "key": "data",
                                      "offset": words[o + 4][1] - data_start, "storage": "FP32",
                                      "original": round(struct.unpack("<f", words[o + 4][0])[0], 6)})
            if not stats:
                continue
            short = slug(name) or "item_%08x" % item_id
            if ("attachment", short) in used:
                short = "%s_%08x" % (short, item_id)
            used.add(("attachment", short))
            shown[("attachment", short)] = " ".join(w.title() if w.isupper() and len(w) > 3 else w for w in name.split())
            out.append({"category": "attachment", "path": "attachment/" + short, "entity": "%016X" % item_id,
                        "stats": stats})
    return out, shown
# Tables that are one record per block (an armor kit, an armor passive): wrapper -> where the record's id is.
SINGLE = {"HelldiverCustomizationKit": 0, "HelldiverCustomizationPassiveBonusSettings": 0}
# What an effect of an armor passive does, by the id the game gives the effect. The game stores a hash
# and no name: these are our reading of the game's own description of each passive beside its numbers
# (Med-Kit: "+2 stims, +2 s" = add 2, time 2). An effect that is not listed is shown by its id.
EFFECTS = {0xAFAE3B47: "armor_rating", 0xC36935A9: "recoil_crouched", 0xF6FA9626: "extra_grenades",
           0x2875F44A: "extra_stims", 0x93EB16A7: "stim_seconds", 0x1F98D152: "explosive_damage_taken",
           0x4DF29271: "fire_damage_taken", 0x6E99CCE5: "gas_damage_taken", 0x4BDF39C4: "arc_damage_taken",
           0xB5A50096: "elemental_damage_taken", 0x21A7BA64: "scan_seconds", 0x14ECCE15: "detection_range",
           0x2559B40D: "melee_damage", 0x2CFAECA3: "chest_damage_taken", 0xA68930C2: "chest_bleed",
           0xCB814D05: "death_save", 0x26C969A1: "throw_range", 0x86A99BB9: "limb_health", 0xAF8B7112: "noise",
           0xC8CCB6FA: "ergonomics_bonus"}
# The weapon values a passive scales (the game's ModifiableStatType; 11 is named in its enum, the others
# are read the same way as the effects above).
GUN_STATS = {11: "flinch", 12: "ammo_capacity", 13: "primary_reload", 15: "sidearm_reload", 16: "sidearm_draw",
             17: "sidearm_recoil"}


STRATAGEM_FAMILIES = ("team_weapons", "president_rewards", "backpack", "consumables", "eagle", "emplacements",
                      "missions", "orbital", "sentrys", "vehicles")


def group_of(category, internal, shown):
    """-> (group, section, order) of an item in the menu, or None: it is a row of its own.
    The group is what the row of the item list says, the section what the value list says above its values."""
    if category == "stratagem":
        for family in STRATAGEM_FAMILIES:
            if internal.startswith(family + "_"):
                return family.replace("_", " ").capitalize(), internal[len(family) + 1:].replace("_", " "), 1
        return None
    if category == "attachment" and ". " in shown:
        family, load = shown.split(". ", 1)
        return family, load.strip(), 1
    if category == "status":
        words = re.sub(r"([a-z])([A-Z])", r"\1 \2", re.sub(r" \(.*\)$", "", shown)).split()
        if words:
            return words[0], " ".join(words[1:]) or "(plain)", (1 if len(words) > 1 else 0)
    if not shown and category in ("stratagem_weapon", "vehicle"):
        # what a hellpod brings and who fights beside the helldivers: families by their internal names
        for prefix, family in (("weapon_rack", "Hellpod weapon racks"), ("drone_", "Guard Dog drones (bodies)"),
                               ("mine_launcher", "Mine launchers"), ("expandable_cover", "Expandable cover"),
                               ("ballistic_shield_backpack", "Ballistic shields (bodies)"), ("sos_beacon", "SOS beacon"),
                               ("cha_battlefront_seaf", "SEAF troops"), ("cha_seaf", "SEAF civilians")):
            if internal.startswith(prefix) and not re.search(r"_(mount|weapon)$", internal):
                return family, internal[len(prefix):].strip("_").replace("_", " ") or "(plain)", 1
    if not shown:
        # no name of the game's: the shells and guns of one stratagem are numbered copies of one internal name
        m = re.match(r"^(.+?)(?:_(shell\d|weapon(?:_\d)?|left|right|\d))$", internal)
        if category == "stratagem_weapon":
            return (m.group(1) if m else internal), (m.group(2).replace("_", " ") if m else "(plain)"), (1 if m else 0)
        return None
    m = re.match(r"^(Damage row) (\d+: .+)$", shown)
    if m:
        return "Damage rows no item uses", m.group(2), 1
    m = re.match(r"^([^:(]+?)(?: \(([^)]*)\))?(?:: (.+))?$", shown)
    if not m:
        return None
    if m.group(1) in ("Automaton", "Illuminate", "Terminid") and category == "enemy_weapon":
        return m.group(1) + ": not identified", m.group(3) or internal, 1
    names = [n.strip() for n in m.group(1).split(" / ")]
    variant, part = m.group(2), m.group(3)
    if part:
        section, order = part + (" (%s)" % variant if variant else ""), 2
    else:
        words = [w.strip() for w in (variant or "").split(",") if w.strip() and w.strip() != "unit"]
        if category == "enemy_weapon":
            section = "Body: " + ", ".join(words) if words else "Body"
        else:
            section = ", ".join(words) if words else internal
        order = 1 if words else 0
    if len(names) > 1:
        section += " (also %s)" % ", ".join(names[1:])
    return names[0], section, order


def menu_groups(items):
    """Items of one category that are one thing, or one family: one row of the menu's item list.
    -> ["J|item index|group|section|order"]"""
    found = {}
    for line in items:
        _i, index, category, internal, _entity, shown = line.split("|", 5)
        g = group_of(category, internal, shown)
        if g:
            found.setdefault((category, g[0]), []).append((g[2], g[1].lower(), g[1], int(index), internal))
    out = []
    for (category, group), members in sorted(found.items()):
        if len(members) < 2:
            continue
        twice = collections.Counter(m[2] for m in members)
        for n, (_order, _key, section, index, internal) in enumerate(sorted(members)):
            if twice[section] > 1:
                section = "%s [%s]" % (section, internal)      # two members under one word: the internal name tells
            assert "|" not in group + section
            out.append("J|%d|%s|%s|%d" % (index, group, section, n))
    return out


def slug(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def armor_items(cat):
    """Armors, armor passives and the helldiver's own movement as items like the others.
    -> [catalog-like item], {(category, short name): shown name}"""
    names = {"passive": {}, "kit": {}}
    with open(os.path.join(HERE, "armor_names.txt"), encoding="utf-8") as f:
        for line in f:
            if not line.startswith("#") and line.count("|") == 2:
                kind, key, shown = line.rstrip("\n").split("|")
                names[kind][int(key, 16) if kind == "kit" else int(key)] = shown
    import build_catalog
    KIT, PASSIVE = "HelldiverCustomizationKit", "HelldiverCustomizationPassiveBonusSettings"
    assert build_catalog.off(KIT, "id")[0] == SINGLE[KIT] and build_catalog.off(PASSIVE, "passive_bonus")[0] == SINGLE[PASSIVE]
    passive_at = build_catalog.off(KIT, "passive_bonus")[0]
    out, shown, used = [], {}, set()

    def stat(sid, table, key, offset, storage, original, more=()):
        return {"id": sid, "table": table, "key": key, "offset": offset, "storage": storage, "original": original,
                "more": list(more)}

    def add(category, short, display, entity, stats):
        assert (category, short) not in used, short
        used.add((category, short))
        shown[(category, short)] = display
        out.append({"category": category, "path": category + "/" + short, "entity": "%016X" % entity, "stats": stats})

    # the helldiver: one record for every armor (walking, running, stamina)
    for av in cat["armor"]["avatar"]:
        if av["path"].endswith("avatar_helldiver"):
            add("armor", "helldiver", "* Helldiver: movement, stamina", int(av["entity"], 16),
                [s for s in av["stats"] if "error" not in s])
    # body armors: the weight class (kept once per piece of the armor) and the passive
    data = hd2db.blob("generated_customization_armor_sets.dl_bin")
    payload_of = {}
    for magic, _typ, size in hd2db.instances(data):
        rec = data[magic + hd2db.HEADER:magic + hd2db.HEADER + size]
        payload_of[struct.unpack_from("<I", rec, SINGLE[KIT])[0]] = rec
    for kit in cat["armor"]["kits"]:
        if kit["type"] != 0 or not kit["weight_field_offsets"]:
            continue
        rec = payload_of[kit["id"]]
        pieces = [(o, struct.unpack_from("<I", rec, o)[0]) for o in kit["weight_field_offsets"]]
        most = collections.Counter(w for _o, w in pieces).most_common(1)[0][0]
        pieces.sort(key=lambda p: (p[1] != most, p[0]))               # the armor's own class first
        assert struct.unpack_from("<I", rec, passive_at)[0] == kit["passive"]
        name = names["kit"].get(kit["id"])
        short = slug(name) if name else "armor_%08x" % kit["id"]
        if ("armor", short) in used:
            short = "%s_%08x" % (short, kit["id"])
        key = str(kit["id"])
        add("armor", short, name or short, kit["id"], [
            stat("weight", KIT, key, pieces[0][0], "UINT32", pieces[0][1], pieces[1:]),
            stat("passive", KIT, key, passive_at, "UINT32", kit["passive"])])
    # passives: every number of every effect
    for p in cat["armor"]["passives"]:
        number = p["passive_bonus"]
        if number == 0:
            continue                                                  # "no passive": nothing in it
        name = names["passive"].get(number) or "passive %d" % number
        stats, key = [], str(number)
        for m in p["modifiers"]:
            hashed = int(m["modifier_id"], 16)
            if hashed == 0:
                continue
            sid = "effect_" + EFFECTS.get(hashed, "%08x" % hashed)
            assert sid not in [s["id"] for s in stats], (name, sid)
            stats.append(stat(sid, PASSIVE, key, m["value_offset"], "FP32", m["value"]))
        for m in p["stat_modifiers"]:
            sid = "gun_" + GUN_STATS.get(m["stat"], "stat%d" % m["stat"])
            assert sid not in [s["id"] for s in stats], (name, sid)
            stats.append(stat(sid, PASSIVE, key, m["offset"] + 8, "FP32", m["mul_value"]))
        add("armor_passive", slug(name), "%s  (%d)" % (name, number), number, stats)
    return out, shown
# things a stratagem brings that are carried and fired like any weapon: listed with the weapons
HAND_WEAPONS = {("stratagem_weapon", "team_weapons_chem_gun_weapon"): "weapon",
                ("stratagem_weapon", "shotgun_doublebarrel"): "weapon"}
ID_AT = {"StratagemSettings": 4}       # where a row keeps its id (0 unless listed)
SKIP_STATS = {"mode"}          # enum fields are not numbers; id-type stats come in Stage 3

# (regex on the stat id, min, max, integer) -- first match wins. Sanity bounds, not balance advice.
RANGES = [
    (r"(^|_)ap_(direct|slight|large|extreme)$", 0, 10, 1),
    (r"^(durable_)?ap_bonus$", -10, 10, 0),
    (r"^(durable_)?bonus2$", -100000, 100000, 0),      # +136 / +140: effect unknown
    (r"(^|_)(durable_)?damage$", 0, 100000, 1),
    (r"(^|_)(demolition|stagger|push)$", 0, 10000, 1),
    (r"(^|_)status\d_type$", 0, 71, 1),            # a row id of the status table (docs/STATUS-EFFECTS.md)
    (r"(^|_)status\d_value$", 0, 100000, 0),
    (r"^(rpm|rpm_low|rpm_high|arc_rpm)$", 1, 6000, 0),
    (r"^speed_multiplier$", 0.01, 100, 0),
    (r"^pellets$", 1, 100, 1),
    (r"^velocity$", 1, 20000, 0),
    (r"^mass$", 0.001, 100000, 0),
    (r"^calibre$", 0.01, 1000, 0),
    (r"^drag$", 0, 100, 0),
    (r"^gravity$", -100, 100, 0),
    (r"^life_time$", 0, 600, 0),
    (r"^penetration_slowdown$", 0, 1, 0),
    (r"^arming_distance$", 0, 10000, 0),
    (r"^capacity$", 1, 9999, 1),
    (r"^beam_(range|radius)$", 0, 5000, 0),
    (r"^arc_speed$", 0, 100000, 0),
    (r"^arc_chain_(length|split)$", 0, 100, 1),
    (r"^wind(up|down)_seconds$", 0, 60, 0),
    (r"^charge_time_(min|full|over)$", 0, 60, 0),
    (r"^charge_(speed|damage|penetration)_(min|over)$", 0, 100, 0),
    (r"^reload_seconds$", 0, 60, 0),               # 0 = the length of the reload animation as it is
    (r"shrapnel_velocity$", 0, 20000, 0),
    (r"^pack_(recharge|takeoff|landing|hover)_seconds$", 0, 600, 0),
    (r"^pack_(launch|landing)_force$", 0, 1000, 0),
    (r"^pack_forward_share$", 0, 1, 0),
    (r"^pack_steering$", 0, 100, 0),
    (r"^warp_(distance|reach_up|reach_down)$", 0, 1000, 0),
    (r"^warp_(heat_safe|heat_unsafe|heat_per_warp|cooling)$", 0, 1000, 0),
    (r"^turn_speed_[hv]$", 0, 3600, 0),
    (r"^search_seconds_(min|max)$", 0, 60, 0),
    (r"^mod_ergonomics$", -100, 100, 0),
    (r"^mod_", 0, 100, 0),
    (r"^explosion_delay$", 0, 60, 0),
    (r"^explosion_proximity$", 0, 500, 0),
    (r"^rpm_burst$", 0, 6000, 0),                  # 0 = the weapon's ordinary rate
    (r"^burst_rounds$", 0, 100, 1),
    (r"^fire_mode_\d$", 0, 9, 1),                  # 0 none, 1 auto, 2 single, 3 burst, 4 / 5 charge
    (r"^(suppressed|silenced_sound)$", 0, 1, 1),
    (r"_fire_type$", 0, 6, 1),
    (r"_lingering_status$", 0, 30, 1),
    (r"_lingering_seconds$", 0, 3600, 0),
    (r"^heat_charge_", 0, 100000, 0),
    (r"^explosion_proximity_filter$", 0, 4294967295, 1),
    (r"^weight$", 0, 2, 1),                        # an armor's class: 0 light, 1 medium, 2 heavy
    (r"^passive$", 0, 41, 1),                      # the number of an armor passive (the Passives list)
    (r"^(effect|gun)_", -100000, 100000, 0),
    (r"^speed_(walk|jog|sprint|sprint_exerted|crouch_walk|crouch_sprint|prone)$", 0, 100, 0),
    (r"stamina", 0, 3600, 0),
    (r"^charges$", 1, 9999, 1),
    (r"^charges_start$", -1, 9999, 1),             # -1 = start full
    (r"^charges_refill$", 0, 9999, 1),
    (r"^shield_health$", 1, 1000000, 0),
    (r"^shield_radius$", 0, 500, 0),
    (r"^shield_(recharge|broken)_delay$", 0, 3600, 0),
    (r"^shield_recharge_rate$", 0, 1000000, 0),
    (r"(^|_)durable_resistance$", 0, 1, 0),
    (r"^explosion_damage_multiplier$", 0, 10, 0),
    (r"^constitution$", 0, 1000000, 1),
    (r"^constitution_rate$", -100000, 100000, 0),
    (r"^part_.+_to_main$", 0, 10, 0),
    (r"^part_.+_overflow_cap$", 0, 1, 1),
    (r"^armor$", 0, 10, 1),
    (r"^part_.+_health$", 1, 1000000, 1),
    (r"^part_.+_armor$", 0, 10, 1),
    (r"^call_in_time$", 0, 600, 0),
    (r"^health$", 1, 1000000, 1),
    (r"^cooldown$", 0, 7200, 0),
    (r"^duration$", 0, 1000000, 0),                # a status effect's own length, seconds (the game: up to 999999)
    (r"^lifetime_seconds$", 0, 36000, 0),          # 0 = stays until destroyed
    (r"^(sight|proximity)_range$", 0, 2000, 0),
    (r"^uses$", 1, 4294967295, 1),                 # 4294967295 = unlimited
    (r"^mags_(start|supply|max)$", 0, 999, 1),
    (r"^rounds_(start|supply|max)$", 0, 9999, 1),
    (r"_(inner|outer|stagger)_radius$", 0, 500, 0),
    (r"_shrapnel_count$", 0, 500, 1),
    (r"^(start|max|refill)_amount$", 0, 999, 1),
    (r"^throw_distance_max$", 1, 500, 0),
    (r"^(arming_delay|fuse)$", 0, 60, 0),
    (r"^(overheat_temperature|temp_gain_per_shot|temp_gain_per_second|temp_loss_per_second)$", 0, 100000, 0),
    (r"^recoil_(drift|climb)_[hv]$", 0, 1000, 0),
    (r"^spread_[hv]$", 0, 1000, 0),
    (r"^sway$", 0, 100, 0),
    (r"^ergonomics$", 0, 1000, 0),
    (r"^arc_range$", 0, 1000, 0),
]

# item name -> spare rows it may take over (STAT-MAP §6.5). Spare = referenced by no entity component,
# no attachment delta and no explosion; the damage row belongs to a spare projectile row only.
# 267 is the unused near-twin of the Liberator's round (same calibre, same damage row).
TAKEOVERS = {
    "assault_rifle": {"projectile": 267, "damage": 55},
}

MAGAZINE_STATS = ("capacity", "mags_start", "mags_supply", "mags_max")

ALIASES = [
    ("ap", "nonzero", ["ap_direct", "ap_slight", "ap_large", "ap_extreme"]),
    ("blast_ap", "nonzero", ["blast_ap_direct", "blast_ap_slight", "blast_ap_large", "blast_ap_extreme"]),
    ("recoil", "all", ["recoil_drift_h", "recoil_drift_v", "recoil_climb_h", "recoil_climb_v"]),
    ("recoil_h", "all", ["recoil_drift_h", "recoil_climb_h"]),
    ("recoil_v", "all", ["recoil_drift_v", "recoil_climb_v"]),
    ("spread", "all", ["spread_h", "spread_v"]),
    ("magazine", "all", ["capacity"]),
    ("spare_magazines", "all", ["mags_max"]),
    ("carried", "all", ["max_amount"]),
]


def stat_range(stat):
    for pattern, lo, hi, integer in RANGES:
        if re.search(pattern, stat):
            return lo, hi, integer
    return None


def num(v, storage):
    if storage == "f32":
        return repr(round(float(v), 6))
    return str(int(v))


def generate(builds=None, indexes=None):
    """-> (blob text, stats dict)

    builds   test builds instead of BUILDS: [(label, exe sha256, dll sha256)]
    indexes  {table: (rva, slots)} for those test builds (default: the latest measured ones)"""
    with open(os.path.join(ROOT, "data", "catalog.json"), encoding="utf-8") as f:
        cat = json.load(f)
    lines = []
    for label, exe, dll in (BUILDS if builds is None else builds):
        lines.append("V|%s|%s|%s" % (label, exe, dll))
        known = indexes if indexes is not None else INDEXES.get(label, list(INDEXES.values())[-1])
        for table, (rva, slots) in sorted(known.items()):
            lines.append("N|%s|%s|%X|%d" % (label, table, rva, slots))
    tables, items, fields, stats_seen, unranged = {}, [], [], set(), set()
    cat_of = {}             # item index -> catalog item
    display = {}
    with open(os.path.join(HERE, "display_names.txt"), encoding="utf-8") as f:
        for line in f:
            if not line.startswith("#") and line.count("|") == 2:
                c, n, shown = line.rstrip("\n").split("|")
                display[(c, n)] = shown
    hidden = set()
    with open(os.path.join(HERE, "hidden_items.txt"), encoding="utf-8") as f:
        for line in f:
            if not line.startswith("#") and line.count("|") == 2:
                c, n, _why = line.rstrip("\n").split("|")
                hidden.add((c, n))
    # two items of a category under one name (the testers found two "SG-8 Punisher"): the internal name
    # is added, so that they can be told apart
    shown_count = collections.Counter((c, shown) for (c, n), shown in display.items() if (c, n) not in hidden)
    for (c, n), shown in list(display.items()):
        if shown_count[(c, shown)] > 1:
            display[(c, n)] = "%s (%s)" % (shown, n)
    data_start = deltas._load()["xo"]
    magazines = {}          # item index -> (catalog item, {stat: (stat entry, attachment entry)})
    armors, armor_shown = armor_items(cat)
    display.update(armor_shown)
    attached, attached_shown = attachment_items()
    display.update(attached_shown)
    for it in cat["items"] + armors + attached:
        category = CATEGORY.get(it["category"])
        if not category:
            continue
        index = len(items)
        short = it["path"].rsplit("/", 1)[-1]
        category = HAND_WEAPONS.get((category, short), category)
        if (category, short) in hidden:
            continue
        if short.startswith("damage_row_") and int(short[11:]) in [spec["damage"] for spec in TAKEOVERS.values()]:
            continue                 # a row the mod borrows for a weapon's own bullet is not offered as an item
        if it.get("shown") and (category, short) not in display:
            display[(category, short)] = it["shown"]                   # (a damage row: named where it is listed)
        if category == "enemy_weapon" and (category, short) not in display:
            # the faction, from the entity's path (fac_cyborgs are the Automatons): a name of the game's own
            # for the unit or its weapon is not known to us
            full = it.get("full_path") or ""
            faction = ("Automaton" if "cyborg" in full else "Illuminate" if "illuminate" in full or "/il_" in full
                       else "Terminid" if "fac_bugs" in full or "obj_bugs" in full or "env_bugs" in full else "")
            if faction:
                display[(category, short)] = "%s: %s%s" % (faction, short.replace("cha_", "").replace("_", " "),
                                                         " (unit)" if "/cha_" in full else "")
        items.append("I|%d|%s|%s|%s|%s" % (index, category, short, it["entity"], display.get((category, short), "")))
        cat_of[index] = it
        for s in it["stats"]:
            if "error" in s or s["id"] in SKIP_STATS:
                continue
            if stat_range(s["id"]) is None:
                unranged.add(s["id"])
                continue
            storage = STORAGE[s["storage"]]
            stats_seen.add(s["id"])
            attached = s.get("default_attachment")
            if attached:
                tables["ComponentEntityDeltaStorage"] = True
                fields.append("F|%d|%s|ComponentEntityDeltaStorage|data|%d|%s|%s|A" % (
                    index, s["id"], attached["delta_data_offset"] - data_start, storage,
                    num(attached["value"], storage)))
                if s["id"] in MAGAZINE_STATS:
                    magazines.setdefault(index, (it, {}))[1][s["id"]] = (s, attached)
                continue
            flags = ""
            tables[s["table"]] = True
            fields.append("F|%d|%s|%s|%s|%d|%s|%s|%s" % (
                index, s["id"], s["table"], s["key"], s["offset"], storage, num(s["original"], storage), flags))
            # the same value kept in further places (an armor's weight class: once per piece)
            for offset, original in s.get("more", ()):
                fields.append("F|%d|%s|%s|%s|%d|%s|%s|M" % (
                    index, s["id"], s["table"], s["key"], offset, storage, num(original, storage)))
    if unranged:
        raise ValueError("stats without a range: %s" % sorted(unranged))
    # takeovers
    extra, stock_rows, own_bullets = [], {}, 0
    P, Dm = hd2db.table("ProjectileSettings"), hd2db.table("DamageSettings")
    fire = hd2db.table("ProjectileWeaponComponentData")
    magazine_table = hd2db.table("WeaponMagazineComponentData")
    rounds_table = hd2db.table("WeaponRoundsComponentData")
    ROUNDS_AT = (64, 68)            # WeaponRoundsComponent: the two ammo types (u32 projectile ids)
    pattern_at = references.member_offsets("ProjectileType", "WeaponMagazineComponent")
    for index, line in enumerate(items):
        _i, _idx, _cat, name, entity_hex, _shown = line.split("|")
        # every weapon that fires projectiles can get rows of its own (new ids); the ones listed in
        # TAKEOVERS can also take over spare rows (new_projectile / new_damage, 0 = none assigned)
        spec = TAKEOVERS.get(name)
        ent = int(entity_hex, 16)
        record = fire.record(ent)
        shell = cat_of[index].get("shell")
        if record is None and not shell:
            assert not spec, name
            continue
        if record is not None:
            base_projectile = struct.unpack_from("<I", record, 0)[0]
            override = deltas.default_overrides(ent).get(("ProjectileWeaponComponent", 0))
            src_projectile = struct.unpack("<I", override[0])[0] if override else base_projectile
            # loaded round by round: the round that is fired is the one the rounds record names
            loaded = rounds_table.record(ent)
            first_round = struct.unpack_from("<I", loaded, ROUNDS_AT[0])[0] if loaded is not None else 0
            if src_projectile in P.by_id() and first_round and first_round != src_projectile:
                src_projectile = first_round
                if override and struct.unpack("<I", override[0])[0] != src_projectile:
                    override = None                       # the attachment names another round: left alone
        else:
            base_projectile, override, src_projectile = "-", None, shell["projectile"]
        if src_projectile not in P.by_id():
            assert not spec, name
            continue
        src_row = P.record(P.by_id()[src_projectile])
        src_damage = struct.unpack_from("<I", src_row, 60)[0]
        if src_damage not in Dm.by_id():
            assert not spec, name
            continue
        new_projectile, new_damage = (spec["projectile"], spec["damage"]) if spec else (0, 0)
        assert not spec or (new_projectile in P.by_id() and new_damage in Dm.by_id())
        extra.append("O|%d|%s|%d|%d|%d|%d" % (index, base_projectile, src_projectile, new_projectile,
                                              src_damage, new_damage))
        own_bullets += 1
        places = []
        if record is not None:
            belt = magazine_table.record(ent)
            for o in pattern_at if belt is not None else []:
                pid = struct.unpack_from("<I", belt, o)[0]
                if pid:
                    places.append(("WeaponMagazineComponentData", o, pid))
            for o in ROUNDS_AT if loaded is not None else []:
                pid = struct.unpack_from("<I", loaded, o)[0]
                if pid:
                    places.append(("WeaponRoundsComponentData", o, pid))
        else:
            places = [(component + "Data", o, src_projectile) for component, o in shell["switches"]]
        for table, o, pid in places:
            extra.append("U|%d|%s|%d|%d" % (index, table, o, pid))
            tables[table] = True
            if pid != src_projectile and pid in P.by_id():
                row = P.record(P.by_id()[pid])
                if struct.unpack_from("<I", row, 60)[0] == src_damage:
                    stock_rows[("ProjectileSettings", pid)] = row
        for pid in (src_projectile, new_projectile):
            if pid:
                stock_rows[("ProjectileSettings", pid)] = P.record(P.by_id()[pid])
        for did in (src_damage, new_damage):
            if did:
                stock_rows[("DamageSettings", did)] = Dm.record(Dm.by_id()[did])
        if override:
            extra.append("X|%d|%d|%d" % (index, override[1] - data_start, src_projectile))
            tables["ComponentEntityDeltaStorage"] = True
        tables["ProjectileSettings"] = tables["DamageSettings"] = True
        if record is not None:
            tables["ProjectileWeaponComponentData"] = True
    # magazines: a default magazine attachment whose magazine deltas form one run of their own can be
    # switched off, so that each weapon's own record counts
    own_magazines = 0
    for index, (it, stats) in sorted(magazines.items()):
        if set(stats) != set(MAGAZINE_STATS) or len(set(a["item"] for _s, a in stats.values())) != 1:
            continue
        attachment = next(iter(stats.values()))[1]["item"]
        resource = next(int(a["delta_resource"], 16) for a in it["default_attachments"] if a["item"] == attachment)
        wanted = sorted((s["offset"], 4) for s, _a in stats.values())
        runs = [(run, entries) for run, _ci, entries in deltas.component_runs(resource) if sorted(entries) == wanted]
        if len(runs) != 1:
            continue                  # the run also carries other deltas: it cannot be switched off as a whole
        extra.append("G|%d|%d|%d|%016X" % (index, runs[0][0] * 12 + 8, len(wanted), resource))
        for stat in MAGAZINE_STATS:
            s = stats[stat][0]
            storage = STORAGE[s["storage"]]
            extra.append("H|%d|%s|%s|%s|%d|%s|%s" % (index, stat, s["table"], s["key"], s["offset"], storage,
                                                    num(s["original"], storage)))
            tables[s["table"]] = True
        own_magazines += 1
    # explosions: which items need a row of their own, and the rows that may be borrowed for it
    index_of = dict((line.split("|")[3], int(line.split("|")[1])) for line in items
                    if line.split("|")[2] in ("weapon", "throwable", "stratagem_weapon", "enemy_weapon",
                                              "unknown_weapon"))
    with_rows = set(int(x.split("|")[1]) for x in extra if x.startswith("O|"))
    Xp = hd2db.table("ExplosionSettings")
    found, own_blasts = blasts.item_blasts(cat), 0
    for name, item_blasts in sorted(found.items()):
        index = index_of.get(name)
        # the explosion on impact first: it is the one `blast_from` hands to another item
        item_blasts.sort(key=lambda b: (b["kind"] == "P" and 144 not in b["switches"], b["explosion"]))
        for b in item_blasts if index is not None else []:
            if b["kind"] == "P":
                if index not in with_rows:
                    continue
                switches = ",".join(str(o) for o in b["switches"])
            else:
                switches = ",".join("%s:%d" % s for s in b["switches"])
                for wrapper, _offset in b["switches"]:
                    tables[wrapper] = True
            damage = b["damage"] if b["damage"] in Dm.by_id() else 0
            extra.append("B|%d|%s|%d|%d|%d|%d|%s" % (index, b["kind"], b["explosion"], damage, int(b["own"]),
                                                    int(b["shared_damage"] and bool(damage)), switches))
            if not b["own"]:
                stock_rows[("ExplosionSettings", b["explosion"])] = Xp.record(Xp.by_id()[b["explosion"]])
            if damage:
                stock_rows[("DamageSettings", damage)] = Dm.record(Dm.by_id()[damage])
            own_blasts += 1
    spare = [row for row, _score, _why in blasts.pool()]
    extra.append("S|ExplosionSettings|" + ",".join(str(row) for row in spare))
    extra.append("P|ExplosionSettings|" + ",".join(str(o) for o in references.pointer_words("ExplosionInfo")))
    for row in spare:
        stock_rows[("ExplosionSettings", row)] = Xp.record(Xp.by_id()[row])
    tables["ExplosionSettings"] = tables["DamageSettings"] = True
    for (table, row_id), raw in sorted(stock_rows.items()):
        extra.append("W|%s|%d|%s" % (table, row_id, raw.hex().upper()))
    for name in sorted(tables):
        if name == "ComponentEntityDeltaStorage":
            lines.append("T|%s|%08X|D|0|0" % (name, dlsum(name)))
            continue
        if name in SINGLE:
            lines.append("T|%s|%08X|S|0|%d" % (name, dlsum(name), SINGLE[name]))
            continue
        _rt, stride, shape = hd2db.record_type(name)
        lines.append("T|%s|%08X|%s|%d|%d" % (name, dlsum(name), "R" if shape == "rows" else "K", stride,
                                             ID_AT.get(name, 0)))
    # what the tables do not hold and the wiki does: shown in the menu beside the game's own number
    hints = {}
    with open(os.path.join(HERE, "reload_times.txt"), encoding="utf-8") as f:
        for line in f:
            if not line.startswith("#") and line.count("|") == 1:
                hints[line.split("|")[0]] = line.rstrip("\n").split("|")[1]
    notes = []
    for line in items:
        _i, index, _category, _name, _entity, shown = line.split("|", 5)
        if shown in hints and any(x.startswith("F|%s|reload_seconds|WeaponReloadComponentData|" % index)
                                  and x.rstrip("|").endswith("|0.0") for x in fields):
            notes.append("K|%s|reload_seconds|wiki %s" % (index, hints[shown]))
    lines += items + menu_groups(items) + notes + fields + extra
    for stat in sorted(stats_seen):
        lo, hi, integer = stat_range(stat)
        lines.append("R|%s|%s|%s|%d" % (stat, repr(lo), repr(hi), integer))
    for alias, mode, targets in ALIASES:
        lines.append("A|%s|%s|%s" % (alias, mode, ",".join(targets)))
    # all_health: the main health and every part's health of a vehicle together. With a percentage the
    # relations between them stay as the game has them (a part still breaks before the vehicle is gone).
    parts = sorted(s for s in stats_seen if re.search(r"^part_.+_health$", s))
    lines.append("A|all_health|all|%s" % ",".join(["health"] + parts))
    blob = "\n".join(lines) + "\n"
    assert "]==]" not in blob
    return blob, {"tables": len(tables), "items": len(items), "fields": len(fields), "stats": len(stats_seen),
                  "own_bullets": own_bullets, "stock_rows": len(stock_rows), "own_magazines": own_magazines,
                  "blasts": own_blasts, "spare": len(spare)}


def main():
    blob, st = generate()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(blob)
    print("tuner data: %(tables)d tables, %(items)d items, %(fields)d fields, %(stats)d stats" % st
          + ", %d bytes -> %s" % (len(blob), os.path.relpath(OUT, ROOT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
