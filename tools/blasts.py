# -*- coding: utf-8 -*-
"""Explosion rows of the catalog items: who else reaches them, and which rows can be borrowed.

Explosion row ids are bounds-checked by the game (probe v0.3.2), so an item cannot get a brand-new
explosion id the way it gets projectile and damage ids. To give an item an explosion row of its own
when it shares one, an existing row has to be borrowed. FREE_IN_MEMORY lists, per verified build, the
rows that no table in the game's memory refers to (census v0.8.0, reports/v0.8.0-tester1/CENSUS.txt).
That is NOT proof that a row is unused: an id that only code knows is invisible to the census. The
pool below is therefore a ranked guess, and the tuner has a canary mode to test it in game.

    python tools/blasts.py
"""
import collections
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import deltas  # noqa: E402
import hd2db  # noqa: E402
import references  # noqa: E402

TARGET, TABLE = "ExplosionType", "ExplosionSettings"
POOL_SIZE = 24

FREE_IN_MEMORY = {
    "release/01.007.101/19155": [
        3, 10, 12, 13, 18, 19, 22, 29, 30, 31, 37, 38, 39, 40, 43, 49, 51, 53, 54, 57, 60, 61, 65, 66, 68, 71, 76,
        78, 83, 85, 88, 89, 90, 95, 98, 101, 103, 105, 111, 113, 114, 120, 121, 123, 124, 125, 129, 130, 134, 136,
        137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 149, 151, 152, 153, 156, 160, 163, 165, 168, 172,
        173, 183, 186, 189, 190, 198, 200, 203, 205, 207, 208, 209, 211, 214, 215, 216, 217, 218, 219, 221, 223,
        225, 226, 231, 233, 238, 239, 240, 242, 243, 245, 246, 247, 250, 253, 255, 256, 258, 259, 260, 262, 265,
        272, 273, 274, 275, 276, 281, 284, 286, 289, 293, 295, 296, 297, 298, 299, 305, 308, 309, 310, 311, 312,
        313, 317, 320, 322, 323, 324, 328, 333, 335, 336, 337, 338, 340, 350, 353, 362, 364, 367, 370, 371, 375,
        378, 383, 384, 394, 395, 396, 399, 400, 401, 403, 405, 406, 412, 415, 418, 419],
}


def _body(table, row):
    """A row without its id and without the array head, for comparing content."""
    r = bytearray(table.record(row))
    r[0:4] = b"\0\0\0\0"
    for o in references.pointer_words(hd2db.record_type(TABLE)[0]):
        r[o:o + 4] = b"\0\0\0\0"
    return bytes(r)


def pool(label=None):
    """Rows to borrow, best first: [(row id, score, why)].

    Preferred: rows that look like the explosion of a weapon that no longer exists - small, with an
    effect, a sound and a damage row that only unreferenced explosions use - and rows that are a
    byte-for-byte twin of a row in use. Avoided: large or silent rows (damage volumes that code is
    likely to spawn by id)."""
    free = FREE_IN_MEMORY[label] if label else list(FREE_IN_MEMORY.values())[-1]
    E = hd2db.table(TABLE)
    ids = E.by_id()
    damage_users = references.users("DamageInfoType", "DamageSettings")
    bodies = collections.defaultdict(list)
    for i, row in ids.items():
        if i:
            bodies[_body(E, row)].append(i)
    ranked = []
    for i in free:
        r = E.record(ids[i])
        damage = struct.unpack_from("<I", r, 4)[0]
        outer = struct.unpack_from("<f", r, 20)[0]
        particle = struct.unpack_from("<Q", r, 56)[0]
        audio = struct.unpack_from("<I", r, 64)[0]
        private = bool(damage) and all(w == TABLE and k in free for w, k, _o in damage_users.get(damage, []))
        twins = [j for j in bodies[_body(E, ids[i])] if j not in free]
        weapon_like = bool(particle) and bool(audio) and bool(damage) and outer <= 12
        score = (3 if twins else 0) + (2 if weapon_like else 0) + (1 if private else 0) \
            - (2 if outer > 15 else 0) - (1 if not particle else 0)
        why = []
        if twins:
            why.append("twin of %s" % twins)
        if weapon_like:
            why.append("weapon-like")
        if private:
            why.append("damage row used by free explosions only")
        ranked.append((i, score, ", ".join(why)))
    ranked.sort(key=lambda x: (-x[1], x[0]))
    return ranked[:POOL_SIZE]


def item_blasts(cat):
    """{item name: [blast]} for the catalog. A blast is a dict:
       kind       P: reached through the weapon's projectile row; C: through the item's own component records
       explosion  the explosion row, damage: its damage row (0 = none)
       own        nothing else reaches the explosion row
       shared_damage  something else uses the damage row
       switches   P: offsets inside the projectile row; C: [(table wrapper, offset)]
       others     who else reaches the row (for reports)"""
    explosion_users = references.users(TARGET, TABLE)
    projectile_users = references.users("ProjectileType", "ProjectileSettings")
    damage_users = references.users("DamageInfoType", "DamageSettings")
    E, P = hd2db.table(TABLE), hd2db.table("ProjectileSettings")
    entity_name = {it["entity"].upper(): it["path"].rsplit("/", 1)[-1] for it in cat["items"]}
    state = deltas._load()
    fired_by_attachment = collections.defaultdict(list)       # projectile id -> delta resources that set it
    for resource in state["hm"]:
        for ci, off, size, data, _doff in deltas.resource_deltas(resource):
            if deltas.COMPONENT_INDEX.get(ci) == "ProjectileWeaponComponent" and off == 0 and size == 4:
                fired_by_attachment[struct.unpack("<I", data)[0]].append(resource)
    default_of = collections.defaultdict(set)
    for it in cat["items"]:
        for a in it.get("default_attachments", []):
            default_of[int(a["delta_resource"], 16)].add(it["path"].rsplit("/", 1)[-1])

    def owner(user):
        wrapper, key, _offset = user
        return entity_name.get(key, "entity " + key) if isinstance(key, str) else "%s row %s" % (wrapper, key)

    def firing(projectile):
        out = set()
        for user in projectile_users.get(projectile, []):
            out.add("shrapnel of explosion %s" % user[1] if user[0] == TABLE else owner(user))
        for resource in fired_by_attachment.get(projectile, []):
            names = default_of.get(resource)
            out.add("ammo attachment of " + ",".join(sorted(names)) if names
                    else "ammo attachment %016X" % resource)
        return out

    keyed = [(name, hd2db.record_type(name)[0]) for name, shape, _s, _p, present
             in references.census_types(TARGET, TABLE) if shape == "K" and present]
    in_row = references.member_offsets(TARGET, "ProjectileInfo")
    out = {}
    for it in cat["items"]:
        name = it["path"].rsplit("/", 1)[-1]
        entity = int(it["entity"], 16)
        mine = sorted(set(s["key"] for s in it["stats"] if s.get("table") == "ProjectileSettings"))
        for explosion in sorted(set(s["key"] for s in it["stats"] if s.get("table") == TABLE)):
            others, switches, kind = set(), [], "C"
            for projectile in mine:
                row = P.record(P.by_id()[projectile])
                offsets = [o for o in in_row if struct.unpack_from("<I", row, o)[0] == explosion]
                if offsets:
                    kind, switches = "P", offsets
            if kind == "C":
                for wrapper, _rtype in keyed:
                    record = hd2db.table(wrapper).record(entity)
                    if record is None:
                        continue
                    for o in references.member_offsets(TARGET, hd2db.record_type(wrapper)[0]):
                        if struct.unpack_from("<I", record, o)[0] == explosion:
                            switches.append((wrapper, o))
            for user in explosion_users.get(explosion, []):
                if user[0] == "ProjectileSettings":
                    who = firing(user[1])
                    for w in who:
                        if w not in (name, "ammo attachment of " + name):
                            others.add("%s (projectile %s)" % (w, user[1]))
                    if not who and user[1] not in mine:
                        others.add("projectile %s, which nothing in our data fires" % user[1])
                elif owner(user) != name:
                    others.add("%s [%s]" % (owner(user), user[0].replace("ComponentData", "")))
            damage = struct.unpack_from("<I", E.record(E.by_id()[explosion]), 4)[0]
            shared = [u for u in damage_users.get(damage, []) if not (u[0] == TABLE and u[1] == explosion)]
            if switches:
                out.setdefault(name, []).append(dict(
                    kind=kind, explosion=explosion, damage=damage, own=not others, shared_damage=bool(shared),
                    switches=switches, others=sorted(others)))
    return out


if __name__ == "__main__":
    import json
    with open(os.path.join(os.path.dirname(HERE), "data", "catalog.json"), encoding="utf-8") as f:
        catalog = json.load(f)
    print("pool:")
    for row, score, why in pool():
        print("   %-4d score %d  %s" % (row, score, why))
    found = item_blasts(catalog)
    kinds = collections.Counter()
    for name, blasts in sorted(found.items()):
        for b in blasts:
            need = "row of its own needed" if not b["own"] else ("new damage id" if b["shared_damage"] else "already its own")
            kinds[need] += 1
            if need != "already its own":
                print("%-34s %s explosion %-4d damage %-4d %-22s %s" % (
                    name, b["kind"], b["explosion"], b["damage"], need, "; ".join(b["others"])))
    print(dict(kinds))
