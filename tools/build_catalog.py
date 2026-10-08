# -*- coding: utf-8 -*-
"""Stage 0: resolve every stat chain offline and write data/catalog.json.

For each helldiver weapon / throwable / armor passive this walks the same
chain the game does (entity -> component record -> settings row) using only
the typelib layout and the plaintext datalibrary, and records for every stat:
table, record key, field offset, storage and the game's ORIGINAL value.

    python tools/build_catalog.py            # writes data/catalog.json, prints a summary

Field offsets are looked up BY NAME through tools/schema_names.py /
tools/gostructs.py; nothing below is a literal offset.
"""
import collections
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import deltas  # noqa: E402
import gostructs  # noqa: E402
import hashnames  # noqa: E402
import hd2db  # noqa: E402
import schema_names  # noqa: E402

OUT = os.path.join(ROOT, "data", "catalog.json")
_FMT = {"UINT32": "<I", "INT32": "<i", "FP32": "<f", "UINT8": "<B", "UINT64": "<Q"}
CATEGORIES = [("primary", "/equipment/primary_weapons/"), ("secondary", "/equipment/sidearm_weapons/"),
              ("support", "/equipment/support_weapons/"), ("melee", "/equipment/melee_weapons/"),
              ("throwable", "/equipment/throwables/")]

_layouts = {}


def off(type_name, path):
    """Byte offset + storage of a (possibly nested) field: 'recoil_info.drift.vertical_recoil',
    'damage[1]', 'rounds_per_minute[1]'. Names are the game's own (schema) names, falling
    back to FileDiver's Go names. Raises KeyError when the field cannot be found."""
    total, cur, storage = 0, type_name, None
    for part in path.split("."):
        idx = None
        if part.endswith("]"):
            part, idx = part[:-1].split("[")
            idx = int(idx)
        L = _layouts.setdefault(cur, schema_names.merged_layout(cur))
        if L is None:
            raise KeyError("%s: not in typelib" % cur)
        hit = None
        want = schema_names._norm(part)
        for m in L["members"]:
            if schema_names._norm(m["schema_name"]) == want or \
                    (m["name_conf"] and schema_names._norm(m["name"]) == want):
                hit = m
                break
        if hit is None:
            raise KeyError("%s.%s: no such field" % (cur, part))
        total += hit["offset"]
        storage = hit["storage"].replace("ENUM_", "")
        if idx is not None:
            if hit["atom"] == "INLINE_ARRAY":
                elem = hit["size"] // hit["inline_array_len"]
            elif hit["type"].startswith("CApiVector"):
                elem, storage = 4, "FP32"
            else:
                raise KeyError("%s.%s is not indexable" % (cur, part))
            total += idx * elem
        cur = hit["type"]
    return total, storage


def rd(rec, type_name, path):
    o, st = off(type_name, path)
    return struct.unpack_from(_FMT[st], rec, o)[0]


class Tables:
    def __init__(self):
        g = hd2db.table
        self.weapon = g("WeaponDataComponentData")
        self.fire = g("ProjectileWeaponComponentData")
        self.magazine = g("WeaponMagazineComponentData")
        self.rounds = g("WeaponRoundsComponentData")
        self.heat = g("WeaponHeatComponentData")
        self.beam_weapon = g("BeamWeaponComponentData")
        self.arc_weapon = g("ArcWeaponComponentData")
        self.spray = g("SprayWeaponComponentData")
        self.melee = g("MeleeWeaponComponentData")
        self.throwable = g("ThrowableComponentData")
        self.explosive = g("ExplosiveComponentData")
        self.avatar = g("AvatarComponentData")
        self.projectile = g("ProjectileSettings")
        self.damage = g("DamageSettings")
        self.explosion = g("ExplosionSettings")
        self.beam = g("BeamSettings")
        self.arc = g("ArcSettings")
        self.proj_ix = self.projectile.by_id()
        self.dmg_ix = self.damage.by_id()
        self.exp_ix = self.explosion.by_id()
        self.beam_ix = self.beam.by_id()
        self.arc_ix = self.arc.by_id()


def stat(stats, sid, table, key, rtype, path, rec):
    """Append one stat description (and its original value) to `stats`."""
    try:
        o, st = off(rtype, path)
    except KeyError as e:
        stats.append({"id": sid, "error": str(e)})
        return None
    v = struct.unpack_from(_FMT[st], rec, o)[0]
    if st == "FP32":
        v = round(v, 6)
    stats.append({"id": sid, "table": table, "key": key, "record": rtype, "field": path,
                  "offset": o, "storage": st, "original": v})
    return v


def word_stat(stats, sid, table, key, rtype, path, rec):
    """A choice or a yes / no of a record (an enum, a flag byte), offered as the whole 32-bit word it sits in.
    A flag byte is only offered when the three bytes behind it are unused."""
    try:
        o, st = off(rtype, path)
    except KeyError:
        return
    if st in ("UINT8", "ENUM_UINT8") and rec[o + 1:o + 4] != b"\0\0\0":
        return
    stats.append({"id": sid, "table": table, "key": key, "record": rtype, "field": path, "offset": o,
                  "storage": "UINT32", "original": struct.unpack_from("<I", rec, o)[0]})


def damage_stats(T, stats, prefix, dmg_id):
    row = T.dmg_ix.get(dmg_id)
    if not dmg_id or row is None:
        return
    rec = T.damage.record(row)
    for sid, path in (("damage", "damage[0]"), ("durable_damage", "damage[1]"),
                      ("ap_direct", "armor_penetration_per_angle[0]"),
                      ("ap_slight", "armor_penetration_per_angle[1]"),
                      ("ap_large", "armor_penetration_per_angle[2]"),
                      ("ap_extreme", "armor_penetration_per_angle[3]"),
                      ("demolition", "demolition_strength"), ("stagger", "force_strength"),
                      ("push", "force_impulse")):
        stat(stats, prefix + sid, "DamageSettings", dmg_id, "DamageInfo", path, rec)
    # what a hit applies: four slots of (status effect id, strength). The ids are the rows of the game's
    # status table (docs/STATUS-EFFECTS.md, read in game); 0 = empty slot.
    for i in range(4):
        stat(stats, "%sstatus%d_type" % (prefix, i + 1), "DamageSettings", dmg_id, "DamageInfo",
             "status_effects[%d].type" % i, rec)
        stat(stats, "%sstatus%d_value" % (prefix, i + 1), "DamageSettings", dmg_id, "DamageInfo",
             "status_effects[%d].value" % i, rec)


def explosion_stats(T, stats, prefix, exp_id):
    row = T.exp_ix.get(exp_id)
    if not exp_id or row is None:
        return
    rec = T.explosion.record(row)
    for sid, path in (("inner_radius", "inner_radius"), ("outer_radius", "outer_radius"),
                      ("stagger_radius", "stagger_radius")):
        stat(stats, prefix + sid, "ExplosionSettings", exp_id, "ExplosionInfo", path, rec)
    damage_stats(T, stats, prefix, rd(rec, "ExplosionInfo", "damage_type"))
    # what the explosion leaves behind: fire on the ground, and a volume that keeps applying a status
    word_stat(stats, prefix + "fire_type", "ExplosionSettings", exp_id, "ExplosionInfo", "fire_template", rec)
    word_stat(stats, prefix + "lingering_status", "ExplosionSettings", exp_id, "ExplosionInfo", "persistent_status_volume", rec)
    stat(stats, prefix + "lingering_seconds", "ExplosionSettings", exp_id, "ExplosionInfo", "status_volume_effect_time", rec)
    n = rd(rec, "ExplosionInfo", "num_shrapnel_projectiles")
    if n:
        stat(stats, prefix + "shrapnel_count", "ExplosionSettings", exp_id, "ExplosionInfo",
             "num_shrapnel_projectiles", rec)
        # the pieces themselves: a projectile row of their own, and the damage row that one names
        piece = rd(rec, "ExplosionInfo", "shrapnel_projectile_type")
        piece_row = T.proj_ix.get(piece)
        if piece and piece_row is not None:
            piece_rec = T.projectile.record(piece_row)
            stat(stats, prefix + "shrapnel_velocity", "ProjectileSettings", piece, "ProjectileInfo", "speed", piece_rec)
            damage_stats(T, stats, prefix + "shrapnel_", rd(piece_rec, "ProjectileInfo", "damage_info_type"))


def projectile_stats(T, stats, proj_id):
    row = T.proj_ix.get(proj_id)
    if not proj_id or row is None:
        return None
    rec = T.projectile.record(row)
    for sid, path in (("pellets", "num_projectiles"), ("velocity", "speed"), ("mass", "mass"),
                      ("calibre", "calibre"), ("drag", "drag"), ("gravity", "gravity_multiplier"),
                      ("life_time", "life_time"), ("penetration_slowdown", "penetration_slowdown"),
                      ("arming_distance", "arming_distance")):
        stat(stats, sid, "ProjectileSettings", proj_id, "ProjectileInfo", path, rec)
    if rd(rec, "ProjectileInfo", "explosion_type_on_impact") or rd(rec, "ProjectileInfo", "explosion_type_expire"):
        # a round that explodes: how long after the hit, and how near a target sets it off
        stat(stats, "explosion_delay", "ProjectileSettings", proj_id, "ProjectileInfo", "explosion_delay", rec)
        stat(stats, "explosion_proximity", "ProjectileSettings", proj_id, "ProjectileInfo", "explosion_proximity", rec)
        # what counts as "near": 960337176 on most rounds; the ones that burst beside an enemy (Airburst
        # rocket, plasma Punisher) have 2878794200
        stat(stats, "explosion_proximity_filter", "ProjectileSettings", proj_id, "ProjectileInfo",
             "proximity_explosion_collision_filter", rec)
    damage_stats(T, stats, "", rd(rec, "ProjectileInfo", "damage_info_type"))
    explosion_stats(T, stats, "blast_", rd(rec, "ProjectileInfo", "explosion_type_on_impact"))
    exp2 = rd(rec, "ProjectileInfo", "explosion_type_expire")
    if exp2 and exp2 != rd(rec, "ProjectileInfo", "explosion_type_on_impact"):
        explosion_stats(T, stats, "expiry_", exp2)
    return row


def apply_overrides(stats, overrides):
    """Mark stats whose live value comes from a default attachment's delta, not the base record."""
    n = 0
    for s in stats:
        o = overrides.get((s.get("record"), s.get("offset")))
        if o is None or s.get("table", "").endswith("Settings"):
            continue
        data, doff, slot, item = o
        v = struct.unpack_from(_FMT[s["storage"]], data, 0)[0]
        s["default_attachment"] = {"value": round(v, 6) if s["storage"] == "FP32" else v,
                                   "delta_data_offset": doff, "slot": slot, "item": item}
        n += 1
    return n


def resolve_weapon(T, ent):
    key = "%016X" % ent
    stats, source = [], []
    fire, rounds = T.fire.record(ent), T.rounds.record(ent)
    overrides = deltas.default_overrides(ent)
    proj = 0
    if fire:
        proj = rd(fire, "ProjectileWeaponComponent", "projectile_type")
        o = overrides.get(("ProjectileWeaponComponent", off("ProjectileWeaponComponent", "projectile_type")[0]))
        if o is not None:
            proj = struct.unpack_from("<I", o[0], 0)[0]
            source.append("projectile-from-attachment")
    if rounds:
        rp = struct.unpack_from("<I", rounds, off("WeaponRoundsComponent", "ammo_types")[0])[0]
        # A weapon loaded round by round fires what its rounds record names (seen in game: the Senator,
        # v1.1.17). Where that differs from the weapon record / the attachment, the rounds record counts.
        if rp and rp != proj:
            proj = rp
            source.append("projectile-from-rounds")
    if fire:
        for i, sid in enumerate(("rpm_low", "rpm", "rpm_high")):
            v = rd(fire, "ProjectileWeaponComponent", "rounds_per_minute[%d]" % i)
            if v > 0:
                stat(stats, sid, "ProjectileWeaponComponentData", key, "ProjectileWeaponComponent",
                     "rounds_per_minute[%d]" % i, fire)
    if fire:
        # a burst weapon fires at its own rate ("if above 0, the fire rate will be changed to this, when the
        # weapon is set to Burst"), and the weapon's own sound flag for a suppressor
        stat(stats, "rpm_burst", "ProjectileWeaponComponentData", key, "ProjectileWeaponComponent", "burst_fire_rate", fire)
        word_stat(stats, "silenced_sound", "ProjectileWeaponComponentData", key, "ProjectileWeaponComponent", "silenced", fire)
        data = T.weapon.record(ent)
        if data is not None:
            stat(stats, "burst_rounds", "WeaponDataComponentData", key, "WeaponDataComponent", "num_burst_rounds", data)
            for n, path in enumerate(("primary_fire_mode", "secondary_fire_mode", "tertiary_fire_mode",
                                      "QuaternaryFireMode")):
                word_stat(stats, "fire_mode_%d" % (n + 1), "WeaponDataComponentData", key, "WeaponDataComponent", path, data)
            word_stat(stats, "suppressed", "WeaponDataComponentData", key, "WeaponDataComponent", "is_suppressed", data)
    if fire:
        # Per-weapon addends. Both name sources call +128 "damage_addends" and +136 "ap_addends", but
        # in game (tuner v0.2.1 / v0.2.2) +128 / +132 changed armor penetration and never damage. The
        # stat ids follow what the game does; +136 / +140 keep a neutral name until their effect is known.
        for sid, path in (("ap_bonus", "damage_addends.normal"),
                          ("durable_ap_bonus", "damage_addends.durable"),
                          ("bonus2", "ap_addends.normal"), ("durable_bonus2", "ap_addends.durable"),
                          ("speed_multiplier", "speed_multiplier")):
            stat(stats, sid, "ProjectileWeaponComponentData", key, "ProjectileWeaponComponent", path, fire)
    if proj and projectile_stats(T, stats, proj) is not None:
        source.append("projectile:%d" % proj)
    bw = T.beam_weapon.record(ent)
    if bw:
        bt = rd(bw, "BeamWeaponComponent", "beam_type")
        row = T.beam_ix.get(bt)
        if row is not None:
            source.append("beam:%d" % bt)
            brec = T.beam.record(row)
            damage_stats(T, stats, "", rd(brec, "BeamInfo", "damage_info_type"))
            # the beam itself (a row of BeamSettings, shared by the weapons that fire this beam)
            stat(stats, "beam_range", "BeamSettings", bt, "BeamInfo", "length", brec)
            stat(stats, "beam_radius", "BeamSettings", bt, "BeamInfo", "radius", brec)
    aw = T.arc_weapon.record(ent)
    if aw:
        at = rd(aw, "ArcWeaponComponent", "arc_type")
        row = T.arc_ix.get(at)
        if row is not None:
            source.append("arc:%d" % at)
            arec = T.arc.record(row)
            stat(stats, "arc_rpm", "ArcWeaponComponentData", key, "ArcWeaponComponent", "rounds_per_minute", aw)
            stat(stats, "arc_range", "ArcSettings", at, "ArcInfo", "distance", arec)
            stat(stats, "arc_speed", "ArcSettings", at, "ArcInfo", "speed", arec)
            stat(stats, "arc_chain_length", "ArcSettings", at, "ArcInfo", "max_chain_length", arec)
            stat(stats, "arc_chain_split", "ArcSettings", at, "ArcInfo", "max_chain_split", arec)
            damage_stats(T, stats, "", rd(arec, "ArcInfo", "damage_info_type"))
    sp = T.spray.record(ent)
    if sp:
        source.append("spray")
        damage_stats(T, stats, "", rd(sp, "SprayWeaponComponent", "damage_info_type"))
    ml = T.melee.record(ent)
    if ml:
        source.append("melee")
        # MeleeWeaponComponent has no field names in either source; the only member typed
        # DamageInfoType is the strike's damage row (typelib-confirmed type, SHODAN-confirmed use).
        L = gostructs.typelib()["types"]["MeleeWeaponComponent"]
        dm = [m for m in L["members"] if m["type"] == "DamageInfoType"]
        if len(dm) == 1:
            damage_stats(T, stats, "", struct.unpack_from("<I", ml, dm[0]["offset"])[0])
    if rounds:
        source.append("rounds")
        for sid, path in (("rounds_max", "ammo_capacity"), ("rounds_supply", "ammo_refill"),
                          ("rounds_start", "ammo")):
            stat(stats, sid, "WeaponRoundsComponentData", key, "WeaponRoundsComponent", path, rounds)
    # Weapons that spin up before they fire, and weapons that are charged. Field names and what they mean
    # are the game's own, as FileDiver's structures record them ("Time until the weapon fully winds up",
    # "Min-, Full-, and Over-Charged states", "The value to multiply the projectile damage with when at
    # the smallest charge amount" ...).
    wind = hd2db.table("WeaponWindUpComponentData").record(ent)
    if wind:
        for sid, path in (("windup_seconds", "wind_up_time"), ("winddown_seconds", "wind_down_time")):
            stat(stats, sid, "WeaponWindUpComponentData", key, "WeaponWindUpComponent", path, wind)
    charge = hd2db.table("WeaponChargeComponentData").record(ent)
    if charge:
        source.append("charge")
        for n, state in enumerate(("min", "full", "over")):
            stat(stats, "charge_time_" + state, "WeaponChargeComponentData", key, "WeaponChargeComponent",
                 "charge_state_settings[%d].charge_time" % n, charge)
        for sid, path in (("charge_speed_min", "speed_multiplier_min"), ("charge_speed_over", "speed_multiplier_overcharge"),
                          ("charge_damage_min", "damage_multiplier_min"), ("charge_damage_over", "damage_multiplier_overcharge"),
                          ("charge_penetration_min", "penetration_multiplier_min"),
                          ("charge_penetration_over", "penetration_multiplier_overcharge")):
            stat(stats, sid, "WeaponChargeComponentData", key, "WeaponChargeComponent", "proj_multipliers." + path, charge)
    # reload time: the typelib has an f32 at +56 of WeaponReloadComponent, and FileDiver's structure names it
    # Duration ("We scale the reload ability to match this duration. If 0, use the default ability duration")
    reload_record = hd2db.table("WeaponReloadComponentData").record(ent)
    if reload_record:
        stats.append({"id": "reload_seconds", "table": "WeaponReloadComponentData", "key": key,
                      "record": "WeaponReloadComponent", "field": "duration", "offset": 56, "storage": "FP32",
                      "original": round(struct.unpack_from("<f", reload_record, 56)[0], 6)})
    mag = T.magazine.record(ent)
    if mag:
        for sid, path in (("capacity", "magazine_capacity"), ("mags_start", "magazines"),
                          ("mags_supply", "magazines_refill"), ("mags_max", "magazines_max")):
            stat(stats, sid, "WeaponMagazineComponentData", key, "WeaponMagazineComponent", path, mag)
    heat = T.heat.record(ent)
    if heat:
        source.append("heat")
        for sid, path in (("overheat_temperature", "overheat_temperature"),
                          ("temp_gain_per_shot", "temp_gain_per_shot"),
                          ("temp_gain_per_second", "temp_gain_per_second"),
                          ("temp_loss_per_second", "temp_loss_per_second"),
                          # a weapon that charges through its heat (the Quasar): the charge a shot needs,
                          # and how fast it builds and drains
                          ("heat_charge_needed", "firing_charge"),
                          ("heat_charge_per_second", "charge_gain_per_second"),
                          ("heat_charge_loss_per_second", "charge_loss_per_second")):
            stat(stats, sid, "WeaponHeatComponentData", key, "WeaponHeatComponent", path, heat)
    wd = T.weapon.record(ent)
    if wd:
        for sid, path in (("recoil_drift_h", "recoil_info.drift.horizontal_recoil"),
                          ("recoil_drift_v", "recoil_info.drift.vertical_recoil"),
                          ("recoil_climb_h", "recoil_info.climb.horizontal_recoil"),
                          ("recoil_climb_v", "recoil_info.climb.vertical_recoil"),
                          ("spread_h", "spread_info.horizontal"), ("spread_v", "spread_info.vertical"),
                          ("sway", "sway_multiplier"), ("ergonomics", "ergonomics")):
            stat(stats, sid, "WeaponDataComponentData", key, "WeaponDataComponent", path, wd)
    n = apply_overrides(stats, overrides)
    return {"sources": source, "stats": stats, "default_attachment_overrides": n,
            "default_attachments": [{"slot": a, "item": b, "delta_resource": "%016X" % c}
                                    for a, b, c in deltas.default_attachments(ent)]}


def resolve_throwable(T, ent):
    key = "%016X" % ent
    stats = []
    th, ex = T.throwable.record(ent), T.explosive.record(ent)
    if th:
        for sid, path in (("start_amount", "start_amount"), ("max_amount", "max_amount"),
                          ("refill_amount", "refill_amount"), ("throw_distance_max", "throw_distance_max")):
            stat(stats, sid, "ThrowableComponentData", key, "ThrowableComponent", path, th)
    if ex:
        stat(stats, "mode", "ExplosiveComponentData", key, "ExplosiveComponent", "mode", ex)
        stat(stats, "arming_delay", "ExplosiveComponentData", key, "ExplosiveComponent", "arming_delay", ex)
        stat(stats, "fuse", "ExplosiveComponentData", key, "ExplosiveComponent", "explosion_delay", ex)
        explosion_stats(T, stats, "blast_", rd(ex, "ExplosiveComponent", "explosion_type"))
    return {"sources": ["throwable"] if th else [], "stats": stats}


# Settled in game (tuner v0.11.0, one tester, Shield Generator Pack): +88 is the delay before an unbroken
# shield starts to recharge, +92 the delay after it broke, +96 the recharge per second. This is the
# reading of the second name source; the type library's own names sit one slot earlier. +80 and +100
# showed no effect and are not offered.
SHIELD_RECHARGE = (("shield_recharge_delay", 88), ("shield_broken_delay", 92), ("shield_recharge_rate", 96))
ZONE_NAMES = {}
with open(os.path.join(HERE, "zone_names.txt"), encoding="utf-8") as _f:
    for _line in _f:
        if not _line.startswith("#") and "|" in _line:
            ZONE_NAMES[int(_line.split("|")[0], 16)] = _line.split("|")[1].strip()


def raw_stat(stats, sid, table, key, offset, rec):
    """A float of a record whose members the type library does not name: by its offset alone."""
    record = table[:-4]
    members = dict((m["offset"], m["storage"]) for m in gostructs.typelib()["types"][record]["members"])
    assert members.get(offset) == "FP32", (table, offset, members.get(offset))
    stats.append({"id": sid, "table": table, "key": key, "record": record, "field": "+%d" % offset,
                  "offset": offset, "storage": "FP32", "original": round(struct.unpack_from("<f", rec, offset)[0], 6)})


# JumppackComponent (Jump Pack, Hover Pack), RechargeComponent, DisplacementComponent (Warp Pack)
JUMP_PACK = (("pack_launch_force", 0), ("pack_takeoff_seconds", 24), ("pack_forward_share", 32),
             ("pack_landing_force", 36), ("pack_landing_seconds", 40), ("pack_steering", 60))
WARP_PACK = (("warp_distance", 120), ("warp_reach_up", 128), ("warp_reach_down", 132), ("warp_heat_safe", 140),
             ("warp_heat_unsafe", 144), ("warp_heat_per_warp", 148), ("warp_cooling", 152))


def packs(T):
    out = []
    jump, recharge = hd2db.table("JumppackComponentData"), hd2db.table("RechargeComponentData")
    warp = hd2db.table("DisplacementComponentData")
    for ent in sorted(set(jump.index) | set(warp.index)):
        path = hashnames.name(ent)
        stats, key = [], "%016X" % ent
        rec = jump.record(ent)
        if rec is not None:
            if recharge.record(ent) is not None:
                raw_stat(stats, "pack_recharge_seconds", "RechargeComponentData", key, 0, recharge.record(ent))
            for sid, offset in JUMP_PACK:
                raw_stat(stats, sid, "JumppackComponentData", key, offset, rec)
            if struct.unpack_from("<f", rec, 156)[0] > 0:             # -1: this pack does not hover
                raw_stat(stats, "pack_hover_seconds", "JumppackComponentData", key, 156, rec)
        rec = warp.record(ent)
        if rec is not None:
            for sid, offset in WARP_PACK:
                raw_stat(stats, sid, "DisplacementComponentData", key, offset, rec)
        name = path.rsplit("/", 1)[-1] if path else "pack_%08x" % (ent >> 32)
        out.append({"category": "backpack", "entity": key, "path": "backpacks/" + name, "full_path": path,
                    "sources": ["pack"], "stats": stats})
    return out


def turret_stats(items):
    """How fast a turret turns (TurretComponent +12 sideways, +8 up and down, degrees a second) and how
    often it looks for a target (DetectorComponent +0 / +4, seconds), for every listed thing that has them."""
    turret, detector = hd2db.table("TurretComponentData"), hd2db.table("DetectorComponentData")
    for it in items:
        if it["category"] not in ("stratagem_weapon", "enemy_weapon", "unknown_weapon"):
            continue
        ent = int(it["entity"], 16)
        rec = turret.record(ent)
        if rec is not None:
            raw_stat(it["stats"], "turn_speed_h", "TurretComponentData", it["entity"], 12, rec)
            raw_stat(it["stats"], "turn_speed_v", "TurretComponentData", it["entity"], 8, rec)
        rec = detector.record(ent)
        if rec is not None:
            raw_stat(it["stats"], "search_seconds_min", "DetectorComponentData", it["entity"], 0, rec)
            raw_stat(it["stats"], "search_seconds_max", "DetectorComponentData", it["entity"], 4, rec)


def resolve_equipment(T):
    """Backpacks, shields and vehicles: one component record per entity, nothing shared."""
    out = []

    def add(category, ent, path, stats):
        if stats and not any("error" in s for s in stats):
            out.append({"category": category, "entity": "%016X" % ent, "path": path, "sources": [category],
                        "stats": stats})

    deposit, shield = hd2db.table("DepositComponentData"), hd2db.table("ShieldComponentData")
    health, vehicle = hd2db.table("HealthComponentData"), hd2db.table("VehicleComponentData")
    for ent in sorted(deposit.index):
        path = hashnames.name(ent)
        if path and "/fac_helldivers/equipment/backpacks/" in path:
            stats, key, rec = [], "%016X" % ent, deposit.record(ent)
            for sid, field in (("charges", "capacity"), ("charges_start", "start_amount"),
                               ("charges_refill", "refill_amount")):
                stat(stats, sid, "DepositComponentData", key, "DepositComponent", field, rec)
            add("backpack", ent, path, stats)
    for ent in sorted(shield.index):
        path = hashnames.name(ent)
        if path and "/fac_helldivers/" in path:
            stats, key, rec = [], "%016X" % ent, shield.record(ent)
            stat(stats, "shield_health", "ShieldComponentData", key, "ShieldComponent", "charge", rec)
            stat(stats, "shield_radius", "ShieldComponentData", key, "ShieldComponent", "radius", rec)
            for sid, o in SHIELD_RECHARGE:
                stats.append({"id": sid, "table": "ShieldComponentData", "key": key,
                              "record": "ShieldComponent", "field": "+%d" % o, "offset": o, "storage": "FP32",
                              "original": round(struct.unpack_from("<f", rec, o)[0], 6)})
            add("shield", ent, path, stats)
    for ent in sorted(vehicle.index):
        path = hashnames.name(ent)
        rec = health.record(ent)
        if path and "/fac_helldivers/vehicles/" in path and rec is not None:
            stats, key = [], "%016X" % ent
            stat(stats, "health", "HealthComponentData", key, "HealthComponent", "health", rec)
            # armor of the main body: both name sources and the values (FRV 3, exosuits and tanks 4) agree
            stat(stats, "armor", "HealthComponentData", key, "HealthComponent", "default_damageable_zone_info.armor", rec)
            # How the main body takes damage. The Patriot's values equal the community wiki's table
            # (durable 100 %, explosion damage 50 %, constitution 2000 at -400 / s), which confirms the offsets.
            for sid, field in (("durable_resistance", "default_damageable_zone_info.projectile_durable_resistance"),
                               ("explosion_damage_multiplier", "default_damageable_zone_info.explosion_damage_multiplier"),
                               ("constitution", "constitution"), ("constitution_rate", "constitution_changerate")):
                stat(stats, sid, "HealthComponentData", key, "HealthComponent", field, rec)
            # the parts: each damageable zone has its own health and armor (a part can break on its own)
            zones_at, zones_size = off("HealthComponent", "damageable_zones")[0], _layouts["HealthComponent"]
            zone = next(m for m in zones_size["members"] if m["offset"] == zones_at)
            step = zone["size"] // zone["inline_array_len"]
            name_at = off("DamageableZoneInfo", "zone_name")[0]
            for z in range(zone["inline_array_len"]):
                name_hash = struct.unpack_from("<I", rec, zones_at + z * step + name_at)[0]
                if not name_hash:
                    continue
                part = ZONE_NAMES.get(name_hash, "%08x" % name_hash)
                # to_main: the share of the damage to this part that also goes to the main health;
                # overflow_cap: 1 = that share stops once the part's own health is gone
                for sid, field in (("health", "health"), ("armor", "armor"),
                                   ("durable_resistance", "projectile_durable_resistance"),
                                   ("to_main", "affects_main_health"),
                                   ("overflow_cap", "main_health_affect_capped_by_zone_health")):
                    o, st = off("DamageableZoneInfo", field)
                    if st == "UINT8":
                        # a flag byte followed by three unused bytes: written as one whole word
                        if rec[zones_at + z * step + o + 1:zones_at + z * step + o + 4] != b"\0\0\0":
                            continue
                        st = "UINT32"
                    v = struct.unpack_from(_FMT[st], rec, zones_at + z * step + o)[0]
                    if st == "FP32":
                        v = round(v, 6)
                    stats.append({"id": "part_%s_%s" % (part, sid), "table": "HealthComponentData", "key": key,
                                  "record": "HealthComponent", "field": "damageable_zones[%d].%s" % (z, field),
                                  "offset": zones_at + z * step + o, "storage": st, "original": v})
            add("vehicle", ent, path, stats)
    return out


def slug(name):
    return "_".join("".join(c.lower() if c.isalnum() else " " for c in name).split())


def stratagem_weapons(T, seen):
    """What stratagems shoot: the guns of sentries, emplacements, drones, vehicles and the Eagle (entities
    with a weapon component, resolved exactly like a hand weapon), and the shells of orbital and Eagle
    strikes (a projectile id inside a Bombardment / Eagle / OrbitalAbility component).
    The links come from tools/stratagems.py (data/stratagems.json)."""
    path = os.path.join(ROOT, "data", "stratagems.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        stratagems = json.load(f)
    out, names, done = [], {}, set(seen)

    def unique(name):
        names[name] = names.get(name, 0) + 1
        return name if names[name] == 1 else "%s_%d" % (name, names[name])

    for s in stratagems:
        base = slug(s["debug_name"])
        shells, guns, damage = [], [], []
        for kind, rows in s.get("rows", {}).items():
            for row_id, links in rows.items():
                for link in links:
                    component, rest = link.split("+")
                    offset, ent = rest.split("@")
                    if component in ("ProjectileWeaponComponent", "BeamWeaponComponent", "ArcWeaponComponent",
                                     "SprayWeaponComponent"):
                        guns.append(int(ent, 16))
                    elif component in ("BombardmentComponent", "EagleComponent", "OrbitalAbilityComponent"):
                        (shells if kind == "projectile" else damage if kind == "damage" else []).append(
                            (int(offset), int(row_id), ent))
        for ent in guns:
            if ent in done:
                continue
            done.add(ent)
            r = resolve_weapon(T, ent)
            if not r["stats"]:
                continue
            path_name = hashnames.name(ent)
            name = unique(path_name.rsplit("/", 1)[-1] if path_name else base + "_weapon")
            out.append({"category": "stratagem_weapon", "entity": "%016X" % ent,
                        "path": "stratagem_weapons/" + name, "stratagem": s["debug_name"], **r})
        rounds = []
        for offset, row_id, ent in sorted(shells):
            if row_id not in [r[1] for r in rounds]:
                rounds.append((offset, row_id, ent))
        for n, (offset, row_id, ent) in enumerate(rounds):
            if ("shell", ent, row_id) in done:
                continue
            done.add(("shell", ent, row_id))
            stats = []
            if projectile_stats(T, stats, row_id) is None:
                continue
            name = unique(base if len(rounds) == 1 else "%s_shell%d" % (base, n + 1))
            places = sorted(set((link.split("+")[0], int(link.split("+")[1].split("@")[0]))
                                for link in s["rows"]["projectile"][str(row_id)] if link.endswith("@" + ent)))
            out.append({"category": "stratagem_weapon", "entity": ent, "path": "stratagem_weapons/" + name,
                        "stratagem": s["debug_name"], "sources": ["shell:%d" % row_id], "stats": stats,
                        "shell": {"projectile": row_id, "switches": places}})
        for offset, row_id, ent in sorted(damage):
            if ("damage", ent, row_id) in done:
                continue
            done.add(("damage", ent, row_id))
            stats = []
            damage_stats(T, stats, "", row_id)
            if stats:
                out.append({"category": "stratagem_weapon", "entity": ent, "path": "stratagem_weapons/" + unique(base),
                            "stratagem": s["debug_name"], "sources": ["damage:%d" % row_id], "stats": stats})
    return out


def body_stats(items):
    """Health, armor and the parts of every listed thing that has a HealthComponent and is not a vehicle
    (those have theirs already): sentries, emplacements, guard dogs, and the enemy units that carry their
    weapon component themselves. The same fields as for vehicles, whose offsets were confirmed in game."""
    health = hd2db.table("HealthComponentData")
    zones_at = off("HealthComponent", "damageable_zones")[0]
    zone = next(m for m in _layouts["HealthComponent"]["members"] if m["offset"] == zones_at)
    step = zone["size"] // zone["inline_array_len"]
    name_at = off("DamageableZoneInfo", "zone_name")[0]
    for it in items:
        if it["category"] not in ("stratagem_weapon", "enemy_weapon", "unknown_weapon") and not it.get("body"):
            continue
        if any(s.get("id") == "health" for s in it["stats"]):
            continue
        rec = health.record(int(it["entity"], 16))
        if rec is None:
            continue
        stats, key = it["stats"], it["entity"]
        stat(stats, "health", "HealthComponentData", key, "HealthComponent", "health", rec)
        stat(stats, "armor", "HealthComponentData", key, "HealthComponent", "default_damageable_zone_info.armor", rec)
        for sid, field in (("durable_resistance", "default_damageable_zone_info.projectile_durable_resistance"),
                           ("explosion_damage_multiplier", "default_damageable_zone_info.explosion_damage_multiplier")):
            stat(stats, sid, "HealthComponentData", key, "HealthComponent", field, rec)
            # (a sentry's explosion multiplier is the largest float there is: "not set". Not offered.)
            if abs(stats[-1].get("original", 0)) > 1e30:
                stats.pop()
        for z in range(zone["inline_array_len"]):
            name_hash = struct.unpack_from("<I", rec, zones_at + z * step + name_at)[0]
            if not name_hash:
                continue
            part = ZONE_NAMES.get(name_hash, "%08x" % name_hash)
            for sid, field in (("health", "health"), ("armor", "armor"),
                               ("durable_resistance", "projectile_durable_resistance"),
                               ("to_main", "affects_main_health"),
                               ("overflow_cap", "main_health_affect_capped_by_zone_health")):
                o, st = off("DamageableZoneInfo", field)
                if st == "UINT8":
                    # a flag byte followed by three unused bytes: written as one whole word
                    if rec[zones_at + z * step + o + 1:zones_at + z * step + o + 4] != b"\0\0\0":
                        continue
                    st = "UINT32"
                v = struct.unpack_from(_FMT[st], rec, zones_at + z * step + o)[0]
                stats.append({"id": "part_%s_%s" % (part, sid), "table": "HealthComponentData", "key": key,
                              "record": "HealthComponent", "field": "damageable_zones[%d].%s" % (z, field),
                              "offset": zones_at + z * step + o, "storage": st,
                              "original": round(v, 6) if st == "FP32" else v})


def other_weapons(T, items):
    """Every entity with a ProjectileWeaponComponent that the lists above did not reach.

    The stratagem snapshot is older than the game, so the weapons of newer stratagems have no link from a
    stratagem; and the enemies' weapons were never asked for by a list. An entity whose path is in the
    community's name list is filed by that path; one without a name is offered as weapon_<8 hex digits>."""
    have = set()
    for it in items:
        try:
            have.add(int(it["entity"], 16))
        except (TypeError, ValueError):
            pass
    taken = collections.Counter(it["path"].rsplit("/", 1)[-1] for it in items)
    out = []
    # (flame weapons have none of the first three: a SprayWeaponComponent is what makes them weapons)
    pool = set(T.fire.index) | set(T.beam_weapon.index) | set(T.arc_weapon.index) | set(T.spray.index)
    for ent in sorted(pool):
        if ent in have:
            continue
        path = hashnames.name(ent)
        if path is None:
            category, name = "unknown_weapon", "weapon_%08x" % (ent >> 32)
        elif "/tutorial/" in path or path.endswith("tutorial_turret"):
            continue
        elif "/fac_helldivers/" in path or "/fac_super_earth/" in path or "/obj_common/" in path:
            category, name = "stratagem_weapon", path.rsplit("/", 1)[-1]
        else:
            category, name = "enemy_weapon", path.rsplit("/", 1)[-1]
        r = resolve_weapon(T, ent)
        if not any("error" not in s for s in r["stats"]):
            continue
        taken[name] += 1
        if taken[name] > 1:
            name += "_%d" % taken[name]
        out.append({"category": category, "entity": "%016X" % ent, "path": category + "s/" + name,
                    "full_path": path, **r})
    return out


# Damage rows of the enemies' melee hits, by the numbers the wiki gives for the attack (see MELEE below):
# row id -> (internal name, what it is). "full": all six numbers are the wiki's; "near": its place among
# the rows of the same enemy settled it where two rows carry the same numbers, or one number differs.
MELEE = {
    565: ("melee_brood_commander_bull_rush", "Brood Commander: Bull Rush"),
    568: ("melee_charger_heavy_ram", "Charger: Heavy Ram"),
    570: ("melee_charger_heavy_crush", "Charger: Heavy Crush"),
    574: ("melee_hunter_serrated_slash", "Hunter: Serrated Slash"),
    575: ("melee_hunter_acidic_lash", "Hunter: Acidic Lash"),
    576: ("melee_hunter_leap", "Hunter: Leap"),
    578: ("melee_impaler_momentous_slam", "Impaler: Momentous Slam"),
    582: ("melee_warrior_claws", "Warrior / Brood Commander / Hive Guard: claws"),
    585: ("melee_scavenger_tearing_pincers", "Scavenger: Tearing Pincers"),
    588: ("melee_stalker_impaling_strike", "Stalker: Impaling Strike"),
    589: ("melee_stalker_barbed_laceration", "Stalker: Barbed Laceration"),
    591: ("melee_bile_titan_cataclysmic_slam", "Bile Titan: Cataclysmic Slam"),
    593: ("melee_trooper_steel_fist", "Trooper: Steel Fist"),
    594: ("melee_heat_blade", "Commissar / Brawler: Heat Blade"),
    596: ("melee_hulk_heavy_rotary_saw", "Hulk: Heavy Rotary Saw"),
    599: ("melee_heat_blade_2", "Commissar / Brawler: Heat Blade (second row)"),
    601: ("melee_berserker_meatsaw_slash", "Berserker: Meatsaw Slash"),
    602: ("melee_berserker_stomp", "Berserker: Stomp"),
    609: ("melee_voteless_swipe_and_claw", "Voteless: Swipe and Claw"),
    612: ("melee_overseer_bludgeon", "Overseer: Pathfinder Lightspear (bludgeon)"),
    621: ("melee_fleshmob_swing_and_bludgeon", "Fleshmob: Swing and Bludgeon"),
}


def other_damage(T, items):
    """Every damage row no listed item uses: the enemies' melee hits by name, the rest by number."""
    used = set()
    for it in items:
        for s in it["stats"]:
            if s.get("table") == "DamageSettings":
                used.add(int(s["key"]))
    out = []
    for row_id in sorted(T.dmg_ix):
        if not row_id or row_id in used:
            continue
        stats = []
        damage_stats(T, stats, "", row_id)
        if not any("error" not in s for s in stats):
            continue
        v = dict((s["id"], s.get("original")) for s in stats if "error" not in s)
        if row_id in MELEE:
            category, name, shown = "enemy_weapon", MELEE[row_id][0], MELEE[row_id][1] + " (melee)"
        else:
            category, name = "unknown_weapon", "damage_row_%d" % row_id
            shown = "Damage row %d: %d / %d, AP %d" % (row_id, v.get("damage", 0), v.get("durable_damage", 0),
                                                       v.get("ap_direct", 0))
        out.append({"category": category, "entity": "%016X" % row_id, "path": category + "s/" + name,
                    "sources": ["damage row"], "shown": shown, "stats": stats})
    return out


def live_stratagems():
    """Stratagem rows as read in game (tools/live_stratagems.txt): the table is not in the offline data.
    Offsets: uses +80, call-in time +84 and cooldown +104 of StratagemInfo, settled by comparing the rows
    read in game with a community snapshot (STAT-MAP 4.9)."""
    out, seen = [], {}
    with open(os.path.join(HERE, "live_stratagems.txt"), encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            row_id, name, uses, cooldown, call_in = line.rstrip("\n").split("|")
            slug = "_".join("".join(c.lower() if c.isalnum() else " " for c in name).split())
            seen[slug] = seen.get(slug, 0) + 1
            if seen[slug] > 1:
                slug += "_%d" % seen[slug]
            row = {"table": "StratagemSettings", "key": int(row_id), "record": "StratagemInfo"}
            out.append({"category": "stratagem", "entity": "%016X" % int(row_id), "path": "stratagems/" + slug,
                        "sources": ["live:" + name], "stats": [
                            dict(row, id="cooldown", field="cooldown_duration_success", offset=104, storage="FP32",
                                 original=float(cooldown)),
                            dict(row, id="uses", field="uses", offset=80, storage="UINT32", original=int(uses))]})
            # spawn_time (+84, here `call_in`) is not offered: set to 20 s on the Recoilless Rifle it changed
            # nothing in game (tuner v0.11.0 and v0.12.0, also when set before the mission).
    return out


def live_statuses(T=None):
    """Status effect rows as read in game (tools/live_statuses.txt): the table is not in the offline data."""
    out, seen = [], {}
    with open(os.path.join(HERE, "live_statuses.txt"), encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            row_id, name, _a, _b, duration, damage_row = line.rstrip("\n").split("|")
            slug = "_".join("".join(c.lower() if c.isalnum() else " " for c in name).split())
            seen[slug] = seen.get(slug, 0) + 1
            if seen[slug] > 1:
                slug += "_%d" % seen[slug]
            out.append({"category": "status", "entity": "%016X" % int(row_id), "path": "statuses/" + slug,
                        "sources": ["live:" + name], "stats": [
                            {"table": "StatusEffectSettings", "key": int(row_id), "record": "StatusEffectInfo",
                             "id": "duration", "field": "+40", "offset": 40, "storage": "FP32",
                             "original": float(duration)}]})
            # what the effect does each time it ticks: its damage row (shared by everything that causes
            # this effect, the enemies included)
            if int(damage_row) and T is not None:
                damage_stats(T, out[-1]["stats"], "", int(damage_row))
    return out


def armor(T):
    """Armor kits (weight class per piece), passives (modifier lists) and the avatar's movement block."""
    out = {"kits": [], "passives": [], "avatar": []}
    data = hd2db.blob("generated_customization_armor_sets.dl_bin")
    KIT, BODY, PIECE = "HelldiverCustomizationKit", "HelldiverBodyTypePieces", "HelldiverCustomizationPieceInfo"
    body_size = gostructs.typelib()["types"][BODY]["size"]
    piece_size = gostructs.typelib()["types"][PIECE]["size"]
    for magic, _typ, size in hd2db.instances(data):
        base = magic + hd2db.HEADER
        rec = data[base:base + size]
        bo, _ = off(KIT, "body_types")
        boff, bcount = struct.unpack_from("<QQ", rec, bo)
        weights = collections.Counter()
        piece_fields = []
        for b in range(bcount):
            brec_at = boff + b * body_size
            po, _ = off(BODY, "pieces")
            poff, pcount = struct.unpack_from("<QQ", rec, brec_at + po)
            for p in range(pcount):
                at = poff + p * piece_size
                wo, _ = off(PIECE, "weight")
                weights[struct.unpack_from("<I", rec, at + wo)[0]] += 1
                piece_fields.append(at + wo)
        out["kits"].append({
            "id": rd(rec, KIT, "id"), "type": rd(rec, KIT, "type"),
            "passive": rd(rec, KIT, "passive_bonus"), "name_cased": rd(rec, KIT, "name_cased"),
            "payload_size": size, "weights": dict(weights), "weight_field_offsets": piece_fields})
    data = hd2db.blob("generated_customization_passive_bonuses.dl_bin")
    P, MOD, SMOD = ("HelldiverCustomizationPassiveBonusSettings", "HelldiverCustomizationPassiveBonusModifier",
                    "HelldiverCustomizationStatModifier")
    for magic, _typ, size in hd2db.instances(data):
        base = magic + hd2db.HEADER
        rec = data[base:base + size]
        mo, mc = struct.unpack_from("<QQ", rec, off(P, "modifiers")[0])
        so, sc = struct.unpack_from("<QQ", rec, off(P, "stat_modifiers")[0])
        mods = []
        for i in range(mc):
            at = mo + i * 16
            mods.append({"modifier_id": "0x%08X" % rd(rec[at:], MOD, "modifier_id"),
                         "modifier_type": rd(rec[at:], MOD, "modifier_type"),
                         "value": round(rd(rec[at:], MOD, "value"), 6),
                         "value_offset": at + off(MOD, "value")[0]})
        smods = []
        for i in range(sc):
            at = so + i * 12
            t, add, mul = struct.unpack_from("<Iff", rec, at)
            smods.append({"stat": t, "add_value": round(add, 6), "mul_value": round(mul, 6), "offset": at})
        out["passives"].append({"passive_bonus": rd(rec, P, "passive_bonus"), "payload_size": size,
                                "modifiers": mods, "stat_modifiers": smods})
    for ent in T.avatar.index:
        rec = T.avatar.record(ent)
        stats = []
        key = "%016X" % ent
        for name in ("walk", "jog", "sprint", "sprint_exerted", "crouch_walk", "crouch_sprint", "prone"):
            stat(stats, "speed_" + name, "AvatarComponentData", key, "AvatarComponent",
                 "movement_info.speeds." + name, rec)
        for name in ("sprint_stamina_decay_duration", "jog_stamina_decay_duration",
                     "stamina_recover_time_stand", "stamina_recover_time_crouch",
                     "stamina_recover_time_prone", "stamina_recover_delay"):
            stat(stats, name, "AvatarComponentData", key, "AvatarComponent", "movement_info." + name, rec)
        out["avatar"].append({"entity": key, "path": hashnames.name(ent), "stats": stats})
    return out


def main():
    T = Tables()
    items = []
    seen = set()
    for cat, needle in CATEGORIES:
        pool = T.throwable.index if cat == "throwable" else T.weapon.index
        for ent in sorted(pool):
            path = hashnames.name(ent)
            if not path or needle not in path or "/fac_helldivers/" not in path:
                continue
            seen.add(ent)
            r = resolve_throwable(T, ent) if cat == "throwable" else resolve_weapon(T, ent)
            items.append({"category": cat, "entity": "%016X" % ent, "path": path, **r})
    items += stratagem_weapons(T, seen) + resolve_equipment(T)
    # the charge of the C4 pack: a throwable like the others, but its entity is filed with the backpacks
    for ent in sorted(T.throwable.index):
        path = hashnames.name(ent)
        if path and path.endswith("/c4_charge_backpack/c4_charge") and ent not in seen:
            seen.add(ent)
            items.append({"category": "throwable", "entity": "%016X" % ent, "path": path, **resolve_throwable(T, ent)})
    # the missile of the Solo Silo: no weapon fires it, it is the thing itself (an explosive)
    for ent in sorted(hd2db.table("SeekingMissileComponentData").index):
        path = hashnames.name(ent)
        if path and path.endswith("/mini_missile_silo/mini_missile_silo") and ent not in seen:
            seen.add(ent)
            r = resolve_throwable(T, ent)
            items.append({"category": "stratagem_weapon", "entity": "%016X" % ent,
                          "path": "stratagem_weapons/mini_missile_silo", "full_path": path, **r})
    items += other_weapons(T, items)
    # what the enemies throw or carry that explodes: an explosive of its own, with a fuse
    for ent in sorted(T.explosive.index):
        path = hashnames.name(ent)
        if path and ("/fac_cyborgs/" in path or "/fac_illuminate/" in path or "/fac_bugs/" in path) \
                and not any(it["entity"] == "%016X" % ent for it in items):
            r = resolve_throwable(T, ent)
            if any("error" not in s for s in r["stats"]):
                items.append({"category": "enemy_weapon", "entity": "%016X" % ent,
                              "path": "enemy_weapons/" + path.rsplit("/", 1)[-1], "full_path": path, **r})
    # every other enemy: the ones without a weapon record (they bite), and the bodies of the ones whose
    # gun is an entity of its own. Health, armor and parts come from body_stats below.
    listed = set(it["path"].rsplit("/", 1)[-1] for it in items)
    for ent in sorted(hd2db.table("HealthComponentData").index):
        path = hashnames.name(ent)
        if path and ("/fac_cyborgs/" in path or "/fac_illuminate/" in path or "/fac_bugs/" in path) \
                and not any(it["entity"] == "%016X" % ent for it in items):
            name = path.rsplit("/", 1)[-1]
            if name in listed:
                name += "_%08x" % (ent >> 32)
            listed.add(name)
            items.append({"category": "enemy_weapon", "entity": "%016X" % ent, "path": "enemy_weapons/" + name,
                          "full_path": path, "sources": ["unit"], "stats": []})
    # everything else that has health and a name: the helldiver's own body, what a hellpod brings, equipment,
    # SEAF troops, mission objects, what stands in the enemies' bases
    for ent in sorted(hd2db.table("HealthComponentData").index):
        path = hashnames.name(ent)
        if not path or any(it["entity"] == "%016X" % ent for it in items) or "/tutorial/" in path:
            continue
        short = path.replace("content/", "")
        if short.startswith("fac_helldivers/cha_avatar/"):
            category = "armor"
        elif short.startswith("fac_helldivers/hellpod/") or short.startswith("fac_helldivers/equipment/"):
            category = "stratagem_weapon"
        elif any(short.startswith(p) for p in ("objectives/obj_cyborgs", "objectives/obj_bugs", "objectives/obj_illuminate",
                                               "env_cyborg", "env_bugs", "env_illuminate")):
            category = "enemy_weapon"
        else:
            category = "vehicle"            # the helldivers' side: vehicle pieces, SEAF troops, mission objects
        name = path.rsplit("/", 1)[-1]
        if name in listed:
            name += "_%08x" % (ent >> 32)
        listed.add(name)
        items.append({"category": category, "entity": "%016X" % ent, "path": category + "s/" + name,
                      "full_path": path, "sources": ["health"], "body": True, "stats": []})
    # and the records of the health table whose name nobody knows (the community's list of names does not
    # have their path): listed by what they are made of, so that they can be recognised
    for ent in sorted(hd2db.table("HealthComponentData").index):
        if hashnames.name(ent) is None and not any(it["entity"] == "%016X" % ent for it in items):
            items.append({"category": "unknown_weapon", "entity": "%016X" % ent,
                          "path": "unknown_weapons/body_%08x" % (ent >> 32), "sources": ["health"], "body": True,
                          "stats": []})
    items += packs(T)
    body_stats(items)
    items[:] = [it for it in items if not it.get("body") or any("error" not in s for s in it["stats"])]
    for it in items:
        if it.get("body") and it["category"] == "unknown_weapon":
            v = dict((s["id"], s.get("original")) for s in it["stats"] if "error" not in s)
            parts = sum(1 for k in v if k.startswith("part_") and k.endswith("_health"))
            it["shown"] = "Body without a name: health %d, armor %d, %d parts" % (v.get("health", 0), v.get("armor", 0), parts)
    turret_stats(items)
    # How long a deployed thing stays before it removes itself: HellpodPayloadComponent.life_time, by the
    # game's own field name. Sentries 150 s, mortar sentries 180 s, Tesla tower 150 s, shield relay 40 s;
    # 0 on things that stay (emplacements, mine deployers).
    payload = hd2db.table("HellpodPayloadComponentData")
    for it in items:
        rec = payload.record(int(it["entity"], 16))
        if rec is not None and it["category"] in ("stratagem_weapon", "shield"):
            if not any(s.get("id") == "lifetime_seconds" for s in it["stats"]):
                stat(it["stats"], "lifetime_seconds", "HellpodPayloadComponentData", it["entity"],
                     "HellpodPayloadComponent", "life_time", rec)
    # How far a sentry sees. The type library has no names for the members of these two components, so
    # this rests on the values alone: the first float of SensorEyeComponent is 75 for the machine gun and
    # Gatling sentries, 100 for the rocket and autocannon sentries, 125 for the mortar sentries, 25 for
    # the Tesla tower; SensorProximityComponent (mortar sentries only) holds the same 125.
    # NOT confirmed by a name source: to be checked in game (docs/STAT-MAP.md 4.9).
    eye, near = hd2db.table("SensorEyeComponentData"), hd2db.table("SensorProximityComponentData")
    for it in items:
        if it["category"] != "stratagem_weapon":
            continue
        for sid, t, record in (("sight_range", eye, "SensorEyeComponent"),
                               ("proximity_range", near, "SensorProximityComponent")):
            rec = t.record(int(it["entity"], 16))
            if rec is not None and not any(s.get("id") == sid for s in it["stats"]):
                it["stats"].append({"id": sid, "table": record + "Data", "key": it["entity"], "record": record,
                                    "field": "+0", "offset": 0, "storage": "FP32",
                                    "original": round(struct.unpack_from("<f", rec, 0)[0], 6)})
    items += live_stratagems()
    items += live_statuses(T)
    items += other_damage(T, items)
    unnamed = sorted("%016X" % e for e in T.weapon.index if hashnames.name(e) is None)
    cat = {"snapshot": {"source": "FileDiver datalibrary mirror", "projectile_rows": T.projectile.count,
                        "damage_rows": T.damage.count, "explosion_rows": T.explosion.count},
           "items": items, "unnamed_weapon_entities": unnamed, "armor": armor(T)}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(cat, f, indent=1)

    by_cat = collections.Counter(i["category"] for i in items)
    errors = [(i["path"], s) for i in items for s in i["stats"] if "error" in s]
    print("catalog -> %s" % os.path.relpath(OUT, ROOT))
    print("items:", dict(by_cat), " unnamed weapon entities (no path in FileDiver's hash list):", len(unnamed))
    print("stat lookups that failed:", len(errors))
    for e in errors[:10]:
        print("   ", e)
    src = collections.Counter(tuple(s.split(":")[0] for s in i["sources"]) for i in items)
    print("damage sources:", dict(src))
    nostat = [i["path"] for i in items if not any(s.get("id") == "damage" for s in i["stats"])
              and i["category"] in ("primary", "secondary", "support", "melee")]
    print("weapons with no damage row resolved: %d" % len(nostat))
    for p in nostat:
        print("    ", p)
    ov = collections.Counter(s["id"] for i in items for s in i["stats"] if "default_attachment" in s)
    print("stats whose live value comes from a DEFAULT ATTACHMENT delta:", dict(ov))
    print("weapons with at least one such stat:", sum(1 for i in items if i.get("default_attachment_overrides")))
    share = collections.defaultdict(set)
    for i in items:
        for s in i["stats"]:
            if s.get("table") in ("ProjectileSettings", "DamageSettings", "ExplosionSettings"):
                share[(s["table"], s["key"])].add(i["path"].rsplit("/", 1)[-1])
    shared = {k: v for k, v in share.items() if len(v) > 1}
    print("settings rows shared by more than one listed item: %d of %d" % (len(shared), len(share)))
    a = cat["armor"]
    kt = collections.Counter(k["type"] for k in a["kits"])
    wt = collections.Counter(w for k in a["kits"] if k["type"] == 0 for w in k["weights"])
    print("armor kits by type (0 armor,1 helmet,2 cape):", dict(kt), " body-armor weight classes:", dict(wt))
    print("passives:", len(a["passives"]), " distinct modifier ids:",
          len({m["modifier_id"] for p in a["passives"] for m in p["modifiers"]}))
    for av in a["avatar"]:
        print("avatar", av["entity"], av["path"], {s["id"]: s.get("original") for s in av["stats"]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
