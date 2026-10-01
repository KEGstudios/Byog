# -*- coding: utf-8 -*-
"""Weapon attachments and the component deltas they apply.

A weapon's base component records are NOT always what the game uses: each
equipped attachment (the defaults included) names a "delta" resource in
ComponentEntityDeltaStorage, a list of (component index, byte offset, bytes)
patches the game lays over the weapon's component records. Example: the P-2
Peacemaker's ProjectileWeaponComponent has projectile_type 0; its default
ammunition attachment writes the real projectile type at +0.

    ComponentEntityDeltaStorage payload (file form; in memory the five array
    heads are absolute pointers):
      +0   DLArray  hashmap    16 B: u64 resource, u32 settings index, u32 pad
      +16  DLArray  settings    8 B: u32 component count, u32 first component
      +32  DLArray  components 12 B: u32 component index, u32 first delta, u32 count
      +48  DLArray  deltas     12 B: u32 offset in component, u32 size, u32 data offset
      +64  DLArray  data       bytes

COMPONENT_INDEX maps the storage's component index to a component type. The
index is a runtime id that is NOT recorded anywhere in the offline data, so
this table is INFERRED from which offsets the deltas touch; treat it as
"offline, inferred" until an in-game recon confirms it.
"""
import collections
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import hd2db  # noqa: E402

COMPONENT_INDEX = {
    5: "WeaponMagazineComponent",
    236: "WeaponDataComponent",
    266: "WeaponHeatComponent",
    271: "WeaponCustomizationComponent",
    321: "ProjectileWeaponComponent",
}

_state = None


def _load():
    global _state
    if _state is not None:
        return _state
    d = hd2db.blob("generated_entity_deltas.dl_bin")
    inst = hd2db.instances(d)
    base = inst[0][0] + hd2db.HEADER
    ho, hc, so, sc, co, cc, do, dc, xo, xc = struct.unpack_from("<10Q", d, base)
    hm = {}
    for i in range(hc):
        h, ix, _pad = struct.unpack_from("<QII", d, base + ho + i * 16)
        if h:
            hm[h] = ix
    cs = hd2db.blob("generated_weapon_customization_settings.dl_bin")
    items = {}
    for magic, _typ, _size in hd2db.instances(cs):
        b = magic + hd2db.HEADER
        aoff, cnt = struct.unpack_from("<QQ", cs, b)
        for i in range(cnt):
            at = b + aoff + i * 88
            items[struct.unpack_from("<I", cs, at + 8)[0]] = struct.unpack_from("<Q", cs, at + 32)[0]
    _state = dict(d=d, base=base, so=so, co=co, do=do, xo=xo, hm=hm, items=items)
    return _state


def resource_deltas(resource):
    """-> [(component index, offset, size, bytes, data_offset_in_payload)] or None."""
    s = _load()
    ix = s["hm"].get(resource)
    if ix is None:
        return None
    d, base = s["d"], s["base"]
    out = []
    n, first = struct.unpack_from("<II", d, base + s["so"] + ix * 8)
    for c in range(first, first + n):
        ci, fd, cnt = struct.unpack_from("<III", d, base + s["co"] + c * 12)
        for k in range(fd, fd + cnt):
            off, size, doff = struct.unpack_from("<III", d, base + s["do"] + k * 12)
            at = base + s["xo"] + doff
            out.append((ci, off, size, d[at:at + size], s["xo"] + doff))
    return out


def default_attachments(entity):
    """-> [(slot, item id, delta resource hash or 0)] for a weapon entity."""
    t = hd2db.table("WeaponCustomizationComponentData")
    rec = t.record(entity)
    if rec is None:
        return []
    out = []
    for s in range(10):
        slot, item = struct.unpack_from("<II", rec, s * 8)
        if item:
            out.append((slot, item, _load()["items"].get(item, 0)))
    return out


def default_overrides(entity):
    """{(component type, offset): (bytes, delta data offset, slot, item)} from the weapon's DEFAULT attachments."""
    out = {}
    for slot, item, res in default_attachments(entity):
        for ci, off, size, data, doff in (resource_deltas(res) or []) if res else []:
            ct = COMPONENT_INDEX.get(ci)
            if ct:
                out[(ct, off)] = (data, doff, slot, item)
    return out


if __name__ == "__main__":
    s = _load()
    hist = collections.defaultdict(collections.Counter)
    for res in s["hm"]:
        for ci, off, size, data, _doff in resource_deltas(res):
            hist[ci][(off, size)] += 1
    print("delta resources: %d   attachment items: %d" % (len(s["hm"]), len(s["items"])))
    for ci, c in sorted(hist.items(), key=lambda kv: -sum(kv[1].values()))[:10]:
        print("component %-4d %-30s deltas=%-5d top (offset,size): %s" % (
            ci, COMPONENT_INDEX.get(ci, "?"), sum(c.values()), c.most_common(8)))
