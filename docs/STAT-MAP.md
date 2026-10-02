# STAT-MAP — Stage 0 (offline research)

Status: **read-verified in game** (recon v0.1.0, 2026-10-01, see §0). Writing is verified for one stat so far;
what a write does in game is still untested for every other stat.
Every offset below is derived, not guessed; the derivation is reproducible with `tools/` (see §9).

## 0. In-game verification (recon v0.1.0, one tester, ship + one mission)

Result line: `OK - all 28 tables found, all 4074 watched values match the offline data`.

| Question | Answer from the live game |
|---|---|
| Is the offline snapshot the live build? | Yes: 4074 of 4074 values read at the mapped offsets equal the offline values (weapons, throwables, backpacks, shields, vehicles, avatar). Every stat rated O / O- below is therefore **read-verified (G-read)**. |
| Game version | Main menu shows `release/01.007.101/19155 live.prod`. FileDiver labels its data `01.007.100`; the tables are nevertheless identical (all 4074 values, all sizes). Other mods active: Bingus Shared Loader and HD2 Runtime only. |
| Build identity | `helldivers2.exe` 14,957,160 B, SHA-256 `F5FEE03DCFDB2E553A4752C283590950AC13316B376D8196AA556FF0400D5F06`, PE timestamp 0x6AB382E4. `game.dll` 15,522,408 B, SHA-256 `2E2C3B7C2500646DADD5F2B4C6E0504DBB7E7896139F64CDDC0D1813C718F51E`, PE timestamp 0x6AB3B43F. |
| Copies | Exactly **one** copy of every table, before and during the mission. |
| Where | Every wanted table sits at the start of an allocation (+4) or in the chain behind one. The full sweep (5.07 GB) found nothing the cheap allocation-start pass does not find. |
| Array form in memory | Absolute pointers, inside the block (+16), for every row table and for the delta storage. |
| When | 10 of 28 tables at frame 254 (title screen), 23 on the ship, all 28 only after the mission loaded (frame ~11400). The engine must keep looking until a mission. |
| Table sizes | Identical to the offline snapshot (350 projectile rows, 649 damage rows, 422 explosion rows, 366 weapon records...). |
| Stratagem cooldown offset | **+104** (90 of the 100 live rows that are also in the snapshot vote for +104, at most 2 for any other offset; the other 10 changed cooldown since the snapshot). The type-alignment guess of +100 was wrong; SHODAN's +104 is right. |
| Status effects | 71 rows. "Acid Storm" is id 55; its live record has no damage row and no stat multipliers (see §4.8). |
| Attachment deltas | Same component-index histogram as offline (5 / 236 / 266 / 271 / 321 at the expected offsets). |
| Cost | Worst frame 9.9 ms, caused by a single VirtualQuery call on a very large region (9.9 ms); average busy frame 1.6 ms; allocation-start pass 4.0 s over 23,524 regions. The patch engine must not query whole regions this way. |

**First write test (tuner v0.2.0, same tester, same build):**

| Question | Answer from the live game |
|---|---|
| Does a written value take effect? | Yes for `DamageSettings` (`damage`, `durable_damage` set to 5000: confirmed in play by the tester, and restoring them brought the weapon back to normal). This is the first **write-verified** stat. |
| Are all tables writable? | No. The settings row tables are in read-write pages; the **entity component tables are in read-only pages** (`ProjectileWeaponComponentData`: protection PAGE_READONLY). v0.2.0 refused them, so `rpm` and the per-weapon `damage_bonus` were never written and remain untested. v0.2.1 opens the page for the single write and closes it again. |
| Build gate, config template, reload key | Work in game. |
| Table search without VirtualQuery | 16,365 allocations in 1.5 s per pass; average working frame 1.0 ms. |

**Second write test (tuner v0.2.1, same tester, same build):**

| Stat | Written and read back | Effect in game (tester's report) |
|---|---|---|
| `rpm` 200 % and 400 % (`ProjectileWeaponComponent.rounds_per_minute`, read-only page) | yes | **works** |
| `recoil = 0` (`WeaponDataComponent.recoil_info`, four fields, read-only page) | yes | **works** |
| restore (empty config) | yes | **works** |
| `damage_bonus`, `durable_damage_bonus` (`ProjectileWeaponComponent.damage_addends`), tried with +5000, +500, +50 | yes | **no effect** |

Read-only pages were opened for a write 18 times and closed again every time; errors 0. So writing to
the component tables is verified. The per-weapon damage addend is NOT a usable knob as tested: the
value is in memory but the weapon's damage did not change. The tester wrote it on the ship, saw no
change on the weapon's stat card, then dropped into a mission and still saw none, so "only read when the
weapon is created" is ruled out too. Damage can only be changed through the shared rows (§6.1).

Side observation from the same tester: for the stats that work (damage, fire rate, recoil) the
weapon's stat card in the armory already shows the changed numbers before the mission.

**Open issue from the recon round:** the tester's game closed (process left hanging) at the moment he threw
the tank stratagem call-in during the mission. The recon log shows no error and the build is read-only,
but the cause is NOT established. A/B follow-up by the same tester: same tank call-in with the recon
disabled: no crash; with the recon enabled again: no crash. The crash did not reproduce in either
configuration, so it is not attributed to the recon, and it remains a single unexplained event.

Not answered by this round: anything about writing; whether other machines / language versions load
the tables the same way (one tester so far); which five tables arrive only with the mission.

## 1. Sources and data snapshot

| Source | Used for | Pinned at |
|---|---|---|
| FileDiver `datalibrary/dl_library.dl_typelib` | **Layout authority**: every type's size, member offsets, storage, member type hash | `xypwn/filediver@6d66a9c` |
| FileDiver `datalibrary/generated_*.dl_bin` | Plaintext mirror of the game's data tables (values, record counts) | same; upstream labels it game update `01.007.100` |
| FileDiver `datalibrary/*.go` | Field names + comments (name source A) | same |
| shalzuth/HelldiversData `data/components/*.json` | The game's **own** field names/descriptions from an older build (name source B) | `0d18368` |
| FileDiver `hashes/hashes.txt`, `cracked.txt` | Entity hash -> resource path | same |
| SHODAN Stat Editor (read only, **no code reused**) | Which tables/offsets a shipped in-game editor actually writes | v2.1.0 and v2.2.0 |
| Super-Earth-Armory-Forge (read only, **no code reused**) | Armor weight finding, STATUS-file/test-harness ideas | `461b42e` |

Three facts about the sources that shaped the method:

1. **The shipped typelib has no string table** (`typeinfo_strings_size = 0`). It gives layout only.
   Type names are recovered from a name list (self-verifying: `djb2(name) == type hash`). Member
   names are *not* in the typelib; they come from sources A and B.
2. **FileDiver's Go structs are partly older than the typelib it embeds** (e.g. `ProjectileWeaponComponent`:
   Go 388 bytes vs typelib 616 — a 224-byte array was inserted at +304). Names are therefore joined to
   the typelib by a drift-tolerant alignment, and each name carries `exact` / `shifted`.
3. Source B is older too (members added since are missing), so it is joined by sequence alignment over
   member types. **A field is called "name-confirmed" only when A and B agree at the same typelib offset.**
   Known limit: when a later build inserted a member inside a run of same-typed members (several f32 in a
   row), source B alone cannot say where; such fields are marked and need recon (see §4.9, §4.10).

Snapshot sizes (will drift with game updates — never use these as gates, see §7):
350 projectile rows, 649 damage rows, 422 explosion rows, 30 beam rows, 16 arc rows,
366 weapon-data records, 272 projectile-weapon records, 271 magazine records, 46 throwables,
411 customization kits (135 body armors), 32 armor passives.

## 2. Confidence levels

| Level | Meaning |
|---|---|
| **O** offline | typelib offset + storage; name-confirmed by A and B; offline value is plausible/known (e.g. Liberator 90/22 dmg, 640 RPM, 30 rounds) |
| **O-** offline, weaker | typelib offset + storage, but only one name source, or name inferred |
| **S** SHODAN-confirmed | additionally, SHODAN writes exactly this table/offset in a released in-game editor |
| **F** SEAF-confirmed | additionally, Super-Earth-Armory-Forge reports an in-mission confirmation |
| **G** in-game verified | verified by our own recon/patch build — **none yet** |

All 75 SHODAN field claims that overlap our scope were checked against the typelib: every one lands on a
member of the right storage type, and every table stride SHODAN hard-codes equals the typelib record size.

## 3. Containers (how a field address is formed)

Every table is an `LDLD` block: `'LDLD'`, u32 version = 1, u32 type hash, u32 payload size, 8 more
header bytes; payload starts at +24.

| Shape | Payload layout | Field address |
|---|---|---|
| **rows** (`*Settings`) | `DLArray{u64 ptr, u64 count}` then `count * stride` rows; row id is a u32 inside the row | `rows + row_index*stride + field` |
| **keyed** (`*ComponentData`) | `buckets * {u64 entity hash, u32 record index, u32 0}` (buckets = 2 x entities), then records | `payload + buckets*16 + index*stride + field` |
| **single** (kit, passive) | one record, then the arrays it points to | `payload + field`, arrays via pointer |

In the file a `DLArray`'s first u64 is an offset relative to the payload; **in memory it is an absolute
pointer** (per the skill's case studies and SHODAN). Stage 1 must report which form it sees.

Row ids are **enum values, not row indices**, and enum values are recycled between builds. Rows must be
found by scanning the id column, and identity must be checked by content, never by id alone.

## 4. Stat map

Offsets are relative to the record start. `T` = storage. Table type hash in parentheses.

### 4.1 Damage — `DamageSettings` (0xE0A72CF0), rows of `DamageInfo` (76 B)

| Stat | Field (game name) | Off | T | Meaning | Conf |
|---|---|---|---|---|---|
| Damage | `damage[0]` | +4 | i32 | standard damage | O, S |
| Durable damage | `damage[1]` | +8 | i32 | damage vs durable parts | O, S |
| Armor penetration | `armor_penetration_per_angle[0..3]` | +12/+16/+20/+24 | u32 | AP at direct / slight / large / extreme angle | O, S |
| Demolition | `demolition_strength` | +28 | u32 | | O, S |
| Stagger | `force_strength` | +32 | u32 | | O, S |
| Push | `force_impulse` | +36 | u32 | | O, S |
| Status effects | `status_effects[4]` | +44 | 4 x {u32 type, f32 value} | burn/gas etc. applied per hit | O, S |

A weapon reaches its damage row through one of these chains (all resolved offline for 114 of 114 named
helldiver weapons that deal damage):

| Weapon kind | Chain |
|---|---|
| Ballistic | `ProjectileWeaponComponent.projectile_type` (+0) -> `ProjectileInfo.damage_info_type` (+60) |
| Round-loaded (shotguns, bolt action, Senator) | `WeaponRoundsComponent.ammo_types.primary` (+64) -> projectile -> damage |
| Projectile set by ammo attachment (pistols, Liberator...) | default attachment delta writes `projectile_type` (§6.2) |
| Beam | `BeamWeaponComponent.beam_type` (+0) -> `BeamInfo.damage_info_type` (+12) |
| Arc | `ArcWeaponComponent.arc_type` (+0) -> `ArcInfo.damage_info_type` (+36) |
| Flame / gas | `SprayWeaponComponent.damage_info_type` (+200) |
| Melee | `MeleeWeaponComponent` +12 (only member typed `DamageInfoType`; **no field name in either source**) — O-, S |
| Explosive rounds | `ProjectileInfo.explosion_type_on_impact` (+144) / `explosion_type_expire` (+156) -> `ExplosionInfo.damage_type` (+4) |

### 4.2 Projectile — `ProjectileSettings` (0xBD4042C2), rows of `ProjectileInfo` (272 B)

| Stat | Field | Off | T | Meaning | Conf |
|---|---|---|---|---|---|
| Projectile speed | `speed` | +32 | f32 | muzzle velocity m/s | O, S |
| Drag | `drag` | +40 | f32 | drag coefficient | O, S |
| Pellets | `num_projectiles` | +28 | u32 | projectiles per shot | O, S |
| Mass | `mass` | +36 | f32 | | O |
| Calibre | `calibre` | +24 | f32 | | O |
| Gravity | `gravity_multiplier` | +44 | f32 | | O |
| Lifetime | `life_time` | +52 | f32 | seconds before the projectile expires; 0 for most bullets | O- (B names it; A calls it `UnkFloat`) |
| Lifetime randomness | `life_time_randomness` | +56 | f32 | | O- (A mislabels this one `LifeTime`) |
| Penetration slowdown | `penetration_slowdown` | +64 | f32 | speed lost when passing through a target | O, S |
| Arming distance | `arming_distance` | +160 | f32 | | O |
| Explosion proximity / delay | `explosion_proximity`, `explosion_delay` | +148 / +152 | f32 | | O |

Also in the weapon's own record: `ProjectileWeaponComponent.speed_multiplier` (+124, f32) scales the
projectile's speed per weapon, and `damage_addends` / `ap_addends` (+128 / +136, 2 x f32 each) add
damage / AP per weapon ("used by weapon customizations"). These are the only **per-weapon** damage and
speed knobs; everything in §4.1 and §4.2 is per *row* and shared (§6.1). Conf O (names agree), not used by SHODAN.
**In-game result (v0.2.1): writing `damage_addends` (+128 / +132) had no effect on the weapon's damage** (§0);
`ap_addends` and `speed_multiplier` are untested.

Offline evidence about the two addend pairs (attachment deltas, `tools/deltas.py`): no shipped attachment
writes +128 / +132 at all. The Senator's barrel attachments write +136 and +140: long barrel +10 / +10
with speed x1.2, short barrel -5 / -5 with speed x0.8. On a 0..10 armor-penetration scale "+10" makes no
sense, as damage it does. **Hypothesis under test (v0.2.2): +136 / +140 is what actually changes a
weapon's damage; +128 / +132 may be the armor-penetration pair or unused.** Not established.

How much sharing there is (offline, all 1899 entities): of the 92 projectile weapons, **56 have a
projectile row and a damage row nobody else uses**, so for them `damage` already is per-weapon. The
rest share with family members (Liberator / Stalwart / Patriot ...), sentries, vehicles or drones.
146 of the 350 projectile rows are not referenced by any entity component; whether those are free to
borrow is unknown (code can reference rows by enum).

### 4.3 Explosion — `ExplosionSettings` (0x2AEA2592), rows of `ExplosionInfo` (152 B)

| Stat | Field | Off | T | Conf |
|---|---|---|---|---|
| Inner radius (full damage) | `inner_radius` | +16 | f32 | O, S |
| Outer radius (damage falls to 0) | `outer_radius` | +20 | f32 | O, S |
| Stagger radius | `stagger_radius` | +24 | f32 | O, S (SHODAN labels it "shockwave") |
| Explosion damage row | `damage_type` | +4 | u32 enum | O, S |
| Shrapnel count / projectile | `num_shrapnel_projectiles` / `shrapnel_projectile_type` | +80 / +84 | u32 | O, S |

### 4.4 Fire rate, ammo, handling (keyed by weapon entity hash)

| Stat | Table (hash) / record | Field | Off | T | Conf |
|---|---|---|---|---|---|
| Fire rate | `ProjectileWeaponComponentData` (0x45171B68) / 616 B | `rounds_per_minute` x,y,z (y = default) | +4/+8/+12 | f32 | O, S |
| Arc fire rate | `ArcWeaponComponentData` (0xB87BA9ED) / 80 B | `rounds_per_minute` | +4 | f32 | O, S |
| Magazine size | `WeaponMagazineComponentData` (0xFB8D88A3) / 160 B | `magazine_capacity` | +136 | u32 | O, S |
| Starting magazines | same | `magazines` | +140 | u32 | O, S |
| Magazines per resupply | same | `magazines_refill` | +144 | u32 | O, S |
| Max spare magazines | same | `magazines_max` | +148 | u32 | O, S |
| Rounds loaded (round-reload weapons) | `WeaponRoundsComponentData` (0x66081072) / 136 B | `magazine_capacity` (vec2) | +72 | f32 | O, S |
| Max / resupply / starting rounds | same | `ammo_capacity` / `ammo_refill` / `ammo` | +80/+84/+88 | u32 | O, S |
| Heat capacity etc. | `WeaponHeatComponentData` (0x4C981CD9) / 592 B | `overheat_temperature`, `temp_gain_per_shot`, `temp_gain_per_second`, `temp_loss_per_second` | +96/+116/+120/+128 | f32 | O, S |
| Heatsinks | same | `magazines` / `_refill` / `_max` | +84/+88/+92 | u32 | O, S |
| Recoil (weapon drift) | `WeaponDataComponentData` (0x88E4DBB1) / 1232 B | `recoil_info.drift.horizontal_recoil` / `.vertical_recoil` | +0 / +4 | f32 | O, S |
| Recoil (camera climb) | same | `recoil_info.climb.horizontal_recoil` / `.vertical_recoil` | +28 / +32 | f32 | O, S |
| Spread | same | `spread_info.horizontal` / `.vertical` (MRAD) | +84 / +88 | f32 | O, S |
| Sway | same | `sway_multiplier` | +104 | f32 | O, S |
| Ergonomics | same | `ergonomics` | +356 | f32 | O, S |

### 4.5 Throwables (keyed by throwable entity hash)

| Stat | Table (hash) / record | Field | Off | T | Conf |
|---|---|---|---|---|---|
| Carried at start | `ThrowableComponentData` (0xAF16BCB5) / 360 B | `start_amount` | +100 | u32 | O-, S (name source B only) |
| Max carried | same | `max_amount` | +104 | u32 | O-, S |
| Per resupply | same | `refill_amount` | +108 | u32 | O-, S |
| Throw distance | same | `throw_distance_min` / `_max` | +12 / +16 | f32 | O-, S (max) |
| Fuse time | `ExplosiveComponentData` (0xF5CF9B8C) / 360 B | `explosion_delay` ("time from armed to explosion; for impact, the minimum timer") | +12 | f32 | O, S |
| Arming delay | same | `arming_delay` | +8 | f32 | O |
| Mode | same | `mode` (0 = timed; the impact grenade has 2) | +0 | i32 enum | O, S |
| Explosion | same | `explosion_type` -> §4.3 -> §4.1 | +36 | u32 enum | O, S |

Checked offline: G-12 HE = 800 dmg, 3.5 s fuse, 4 start / 5 max; G-6 Frag = 500 dmg, 2.4 s.

### 4.6 Armor (out of scope since the 2026-10-01 review: an existing mod covers armor; kept for reference)

There is **no per-armor numeric armor / speed / stamina field**. What exists:

| What | Where | Field | Off | T | Conf |
|---|---|---|---|---|---|
| Weight class of each armor piece (0 light, 1 medium, 2 heavy) | `HelldiverCustomizationKit` (0xD9A55AA0), one LDLD block per kit -> `body_types[]` -> `pieces[]` (`HelldiverCustomizationPieceInfo`, 96 B) | `weight` | piece +16 | u32 enum | O, **F** (SEAF: setting a heavy armor to light shows 50/550/125 and "runs like light", confirmed in a mission) |
| Which passive an armor has | same kit record | `passive_bonus` | +28 | u32 enum | O |
| Passive modifier values | `HelldiverCustomizationPassiveBonusSettings` (0x63CE0FEB), one block per passive -> `modifiers[]` (16 B: `modifier_id`, `modifier_type` 0 set/1 add/2 multiply/3 seconds, `value`, `desc_loc`) | `value` | modifier +8 | f32 | O, S |
| Passive weapon-stat modifiers | same -> `stat_modifiers[]` (12 B: `type`, `add_value`, `mul_value`) | `add_value` / `mul_value` | +4 / +8 | f32 | O, S |
| Base movement speeds (all helldivers) | `AvatarComponentData` (0x40EF204C) / 852 B, entity `avatar_helldiver` | `movement_info.speeds.walk/jog/sprint/sprint_exerted` | +12/+16/+20/+24 | f32 | O (offline 2.0 / 3.2 / 5.5 / 4.25 m/s) |
| Stamina (all helldivers) | same | `movement_info.sprint_stamina_decay_duration`, `stamina_recover_time_stand/crouch/prone`, `stamina_recover_delay` | +52, +60/+64/+68, +72 | f32 | O |

Passive modifier ids relevant to the request (labels are SHODAN's/SEAF's, matched by them against the wiki;
we have only confirmed the ids and values exist offline):
`0xAFAE3B47` armor rating, additive, in class steps (Extra Padding = 1.0, four passives = 0.5/0.6);
`0xCD79A687` walk/run speed multiplier (only one passive has it: 1.1).

### 4.7 Backpack capacity — `DepositComponentData` (0xC435BA85), keyed by the BACKPACK entity, `DepositComponent` (152 B)

| Stat | Field | Off | T | Meaning | Conf |
|---|---|---|---|---|---|
| Capacity | `capacity` | +0 | u32 | total charges / rounds the backpack holds | O, S |
| Starting amount | `start_amount` | +4 | i32 | -1 = start full | O, S |
| Per resupply | `refill_amount` | +8 | u32 | | O, S |

30 records offline. Backpack-fed weapons: Recoilless 5 / -1 / 3, Autocannon 10 / -1 / 5, Airburst 5,
Spear 4, belt-fed grenade launcher 120, minigun 1000, heavy flamethrower 500. Also Supply Pack 4,
Guard Dogs, C4, Portable Hellbomb. The key is the backpack entity, not the weapon; the weapon side is
`WeaponAssistedReloadComponent` (team-reload launchers) or `WeaponLinkedAmmoComponent` (belt / hose fed).
SHODAN notes a backpack reads its values when it is called in, so an edit applies to the next call-in.

### 4.8 What a weapon fires and applies (id fields, not numbers)

These fields hold a **row id of another table**. They make "grenade launcher that fires gas / fire",
programmable-ammo changes and "add an effect to a weapon" possible without adding content, but they are
a different kind of stat: the valid range is "an id that exists in the target table of this build", and
ids are recycled between builds, so a config must name the SOURCE by item ("the explosion of the gas
grenade"), never by number.

| What | Table / record | Field | Off | T | Conf |
|---|---|---|---|---|---|
| Projectile a weapon fires | `ProjectileWeaponComponent` | `projectile_type` | +0 | u32 enum | O, S (read) |
| Programmable-ammo alternate projectile | same | `weapon_function_projectile_type` | +576 | u32 enum | O- (name source A only, in the shifted part of the struct; data fits: Autocannon, Recoilless, Airburst and the smart pistols have one, all others 0) |
| Programmable muzzle velocity | same | `weapon_function_muzzle_velocity` | +572 | f32 | O- (150 on every weapon offline: looks like an unused default) |
| Primary / alternate round type (round-loaded weapons) | `WeaponRoundsComponent` | `ammo_types.primary` / `.alternate` | +64 / +68 | u32 enum | O (the Halt has two different types) |
| Explosion of a projectile | `ProjectileInfo` | `explosion_type_on_impact` / `explosion_type_expire` | +144 / +156 | u32 enum | O, S (read) |
| Gas / status cloud left by an explosion | `ExplosionInfo` | `persistent_status_volume`, `status_volume_effect_time` | +100, +104 | u32 enum, f32 | O (gas grenade: template 16 for 15 s) |
| Fire left by an explosion | `ExplosionInfo` | `fire_template` | +96 | u32 enum | O (incendiary grenade: 4) |
| Status applied per hit (burn, gas, ...) | `DamageInfo` | `status_effects[i].type` / `.value`, i = 0..3 | +44 + 8*i / +48 + 8*i | u32 enum, f32 | O, S |

**Grenade launcher with gas / fire.** Offline, a launcher grenade is projectile row -> explosion row (GL:
280 -> 361), and a gas grenade's whole effect lives in its explosion row (177). So it is either one id
write (`explosion_type_on_impact` of the GL projectile := the gas grenade's explosion id) or two or three
writes that add the gas / fire templates to the GL's own explosion. **Untested in game**; the open risk
is whether the borrowed row's effect assets are loaded when the grenade itself is not equipped.

**Programmable ammo.** Editing the alternate round's *numbers* needs nothing new: it is an ordinary
projectile row (§4.2) reached through `weapon_function_projectile_type`.

**Sterilizer + acid rain.** How acid rain is wired, as far as data shows (older community snapshot for
the weather / status tables, current data for weapons):

1. A weather record carries `environment_effect_tag = Acidstorm`.
2. An `EnvironmentalEffectTagComponent` maps that tag to `status_effect_to_apply` — described by the
   game itself as "the status effect to apply to **players**".
3. That status is "Acid Storm". Its record has **no damage row and no stat multipliers**: strength 1,
   duration 1, a screen/shading effect, nothing else. The list of stats a status CAN scale
   (`ModifiableStatType`) has damage dealt / damage taken / explosion radius / reload time — **no armor**.

So the armor loss players associate with acid rain is not expressed in any record we can see; it is
either code keyed on this status / weather, or lives in a newer version of the record than the snapshot.
A weapon applies statuses through its damage row's `status_effects` (4 slots of type + strength; the gas
sprayers use 2), so writing "Acid Storm" into a free slot of the Sterilizer's row is mechanically one
write. Whether it then does anything to an enemy is open on three counts:

* the status id in the current build is unknown offline (the enum went from 61 names in the snapshot to
  73 values now; `StatusEffectSettings`, 0xC63E0B22, is not in the plaintext bundle) — recon can read
  the live table, whose rows carry a debug name;
* a target only takes a status it is susceptible to (`no_susceptibility_required` is 0 for Acid Storm),
  and the tag component speaks of players, not enemies;
* even when applied, the effect itself may be nothing but the screen tint.

Live result (recon v0.1.0): the status exists as id 55 "Acid Storm" in the current build, and its
record is as empty as the snapshot's: strength 1, duration 1, a shading environment, no damage row, no
multiplier array. So the armor loss is NOT data in this record; it is done by game code. Whether that
code looks at "this unit has status 55" (then a weapon-applied status would work) or at "the weather is
an acid storm" (then it would not) can only be found by trying it in Stage 2. The gas statuses are ids
42/43 ("Gas", 6 s and 10 s) and 44/45 ("Gas_Confusion").

Alternatives that stay inside known mechanics, for the same "acid" idea: (a) the bile acid statuses
"Acid Splash" / "Acid Stream" — real damage-over-time rows plus a slow, already applied by enemies to
players; (b) raising the armor penetration of the gas damage-over-time row, which is what "eats armor"
means in damage terms; (c) a larger "damage taken" effect is NOT available: the gas status has an empty
multiplier list and we do not add array elements. The Sterilizer's entity is among the 133 unnamed
ones (§6.4).

### 4.9 Stratagems

`StratagemSettings` (0x30EB6399, rows of `StratagemInfo`, 400 B, several group tables, row id at +4) is
**not in FileDiver's plaintext bundle**, so this part rests on an older community JSON snapshot for the
stratagem list and on SHODAN for the record offsets. Everything below the payload was resolved against
the current data with a generic, typelib-driven walk (`tools/stratagems.py`): payload entity -> every
component record it has -> members typed ProjectileType / ExplosionType / DamageInfoType / BeamType /
ArcType, following entity hashes (hellpod -> sentry -> gun).

Result: of 59 selectable stratagems in the snapshot, 58 have their payload entity in the current data
and **53 reach projectile / explosion / damage rows**; from there damage, AP, radii and shrapnel are the
same fields as §4.1-§4.3. The 5 that reach none are backpacks and shields (§4.7, §4.10). Links found:

| Stratagem kind | Link to its rows |
|---|---|
| Sentries, emplacements, support weapons, vehicle guns | `ProjectileWeaponComponent.projectile_type` of the gun entity (30 stratagems) |
| Orbital barrages / strikes | `BombardmentComponent` (0xCDBC43D8, 192 B) projectile types (10) |
| Eagle strikes | `EagleComponent` (0x556FF68B, 152 B) projectile type (6), plus the Eagle's own guns |
| Orbital laser / railcannon | `OrbitalAbilityComponent` (0x936A9C08, 552 B): damage row, projectile type |
| Mines, hellbomb | `MinefieldComponent`, `ExplosiveComponent.explosion_type` |

| Stat | Field | Off | T | Conf |
|---|---|---|---|---|
| Uses per mission | `uses` (0xFFFFFFFF = unlimited) | +80 | u32 | O-, S |
| Cooldown | `cooldown_duration_success` | +104 | f32 | G-read (whole-table vote in game, §0), S |
| Payload entities | `payload` (array) | +152 | u64[] | O-, S |

**Resolved in game:** the current record has one more f32 in the run +84..+108 than the old field list.
Aligning by type put the cooldown at +100; the recon build compared every live row with the community
snapshot and +104 won clearly (§0). Lesson kept: a name source that is older than the build cannot place
a field inside a run of same-typed members; such fields need a whole-table check against known values.
The live table has 149 rows in 11 groups, including stratagems that are not in the snapshot.

### 4.10 Energy shields — `ShieldComponentData` (0x5154DB66), keyed, `ShieldComponent` (344 B)

16 records offline: Shield Generator Pack (charge 150), directional shield (1000), Shield Generator Relay
(4000), shield grenade (1000), plus enemy shields in the same table.

| Stat | Field | Off | T | Conf |
|---|---|---|---|---|
| Shield health | `charge` | +76 | f32 | O-, S (both readings agree on this one) |
| Radius | `radius` | +0 | f32 | O-, S |
| Recharge delay / delay once broken / recharge rate / charge when it comes back | `recharge_delay`, `broken_recharge_delay`, `recharge_rate`, `starter_charge_on_recharge` | **+80..+100, one slot uncertain** | f32 | type alignment says +80/+88/+92/+96, SHODAN says +88/+92/+96/+100 |

Same ambiguity as the stratagem cooldown (new members inside a run of floats). Shield health itself is
not affected. To be settled in recon / Stage 2.

### 4.11 Vehicles (exosuits, FRVs, tanks) — `HealthComponentData` (0xB3915DE3), keyed, `HealthComponent` (22096 B)

Which entities are vehicles: `VehicleComponentData` (0xEAEB2B0D), 21 records offline. Their health
record is in the same table as every other unit's (502 records, enemies included).

| Stat | Field | Off | T | Conf |
|---|---|---|---|---|
| Health | `health` ("Max health") | +0 | i32 | O, S |
| Armor (main body) | `default_damageable_zone_info.armor` | +64 + 216 = +280 | u32 | O-, S (the zone struct gained members since both name sources; the value fits: FRV 3, exosuits 4, tanks 4) |
| Per-part health / armor (legs, cockpit, tracks...) | `damageable_zones[38]` from +520, 552 B each: zone `armor` +216, zone health +232, `zone_name` +96 | | u32 / i32 | S only for the two offsets inside the zone; O for the array itself |

Offline values: exosuits (Patriot, Emancipator, Lumberer, Breacher) 1800 health / armor 4; FRVs 2400 / 3
(flamer FRV 2900); tanks 8000 / 4. The unit sits in the shared health table, so an edit is per vehicle
entity and does not touch other units.

## 5. Requested stats that do not exist as data, or exist only indirectly

| Requested | Finding |
|---|---|
| **Damage falloff over distance** | **No dedicated field.** Neither `DamageInfo`, `ProjectileInfo`, any weapon component, nor any of the game's own field names contains a falloff/range-damage value (the only "falloff" in all sources is `BeamInfo.falloff_effect_path`, a particle effect). For bullets it can only be indirect, through the projectile's flight model: `drag` (+40), `mass` (+36), `calibre` (+24), `speed` (+32). **That drag drives damage loss is a community claim we could not confirm offline** (the wiki is behind bot protection); it needs one in-game test in Stage 2 (set drag to 0, compare damage at 10 m and 100 m). For explosions, falloff over distance *is* data: `inner_radius` -> `outer_radius`. |
| **Range** | No "range" field for bullets. Indirect: `life_time` (+52; 0 = engine default for most bullets) x `speed`, plus `gravity_multiplier`/`drag`. Beams have a real range: `BeamInfo.length` (+8, O). Arcs: `ArcInfo.distance` (+8, O, S). |
| **Weight** (weapon) | No weight field. `ergonomics` is the handling stat. `RecoilInfo` +56 is an unnamed float FileDiver guesses "might be a weight" — not usable. |
| **Armor value** | Not a number per armor. Set by the piece's `weight` class (50/100/150 per SEAF) plus the passive's armor-rating modifier. Arbitrary values are only reachable on armors whose passive already has that modifier. |
| **Armor speed** | Not per armor. Weight class (550/500/450 per SEAF), or the global avatar speeds (affects every armor), or the one passive with a speed multiplier. |
| **Stamina regeneration** | Not per armor. Weight class (125/100/50 per SEAF), or the global avatar `stamina_recover_time_*`. |
| Where the class numbers 50/550/125 etc. live | **Not found** in any table we have (FileDiver covers ~20 of the game's 57 `generated_*` files; none of the community-decoded settings is an armor-class table). Likely code-side or an uncovered table. |

## 5b. Testers' wish list (2026-10-01) against this map

| Wanted | Status |
|---|---|
| Damage, armor penetration for weapons and stratagems | §4.1; stratagems via §4.9 |
| Spare magazine count, magazine capacity | §4.4 (mind attachment deltas, §6.2) |
| Projectile AP, explosion AP; normal and durable damage of both | §4.1 — a projectile and its explosion have separate damage rows |
| Demolition force, stagger force, push force | §4.1 `demolition_strength`, `force_strength`, `force_impulse` |
| Recoil | §4.4 (weapon drift and camera climb, horizontal / vertical) |
| Ergonomics, sway | §4.4 |
| Explosion inner / outer / shockwave radius | §4.3 (`stagger_radius` is the "shockwave") |
| Shrapnel count | §4.3 `num_shrapnel_projectiles` |
| Projectile speed | §4.2 `speed` |
| Fire rate for weapons with no fire-rate selector | §4.4: `rounds_per_minute` exists for every projectile weapon; beam and spray weapons have no rate |
| Backpack capacity of backpack-fed weapons | §4.7 (new) |
| Programmable ammo; grenade launcher firing gas / fire | §4.8 (new; id fields, untested in game) |
| Acid rain effect on the Sterilizer | §4.8 (new; feasibility unknown until tested) |
| Energy shield health | §4.10 (new) |
| Vehicle health, armor | §4.11 (new) |
| Damage falloff | §5: no such field; only indirect |
| Armor | dropped from scope |

## 6. Structural risks the engine must handle

### 6.1 Shared rows
Damage/projectile/explosion rows are shared. Offline, 17 of 294 rows used by the named player weapons
are shared by more than one of them (e.g. several Liberator-family weapons), and rows are also shared
with stratagems, sentries and **enemies**. Editing a row edits every user. The engine API must expose
"also affects: ...". The only strictly per-weapon damage/speed knobs are the addends/multiplier in §4.2.

### 6.2 Attachment deltas override base records
`ComponentEntityDeltaStorage` (0x683E604F) holds, per attachment, byte patches the game lays over a
weapon's component records. Offline, **25 of 114** named weapons are affected by a *default attachment*:
for 21 a requested stat's live value comes from the attachment's delta and not from the base record
(magazine size/counts on 19 weapons, heat values on others; 55 of those 79 delta values differ from the
base record), and for 9 the projectile type itself is set by the ammo attachment (e.g. the Peacemaker's
base `projectile_type` is 0). Writing only the base record would silently do nothing for those. The
component-index -> component-type mapping inside the delta storage is **inferred** offline from the
offsets the deltas touch (5 = magazine, 236 = weapon data, 266 = heat, 271 = customization,
321 = projectile weapon); recon must confirm it. Non-default attachments carry their own copies.

### 6.2b Per-weapon damage: addends do not work, row takeover is under test

In-game results (tuner v0.2.1 / v0.2.2, one tester): the pair both name sources call `damage_addends`
(+128 / +132) does not change damage even on a weapon created after the write; writing 10 there made
the Liberator hurt heavily armored targets, so **+128 / +132 are armor-penetration addends** (per
weapon, working). The pair at +136 / +140 was set to +5000 and, per the tester's summary, did not act
as damage either (logs for that round were not returned). No per-weapon damage knob exists.

Row takeover ("own bullet", tuner v0.3.0): a weapon is given a projectile row and a damage row that
nothing in the offline data refers to. The engine copies the shared rows into them word by word
(stock values, generated offline), points the new projectile row at the new damage row, and only when
every field is in place switches the weapon's `projectile_type` (+0 of its ProjectileWeaponComponent)
and, where a default ammo attachment sets the projectile, that attachment's delta value. Each field is
only overwritten if it holds exactly the expected stock value. Restore is the reverse, switches first.

Spare rows (offline): 80 projectile rows are referenced by no entity component, attachment delta or
explosion; 32 of them have a damage row nothing else references. For the Liberator: projectile 267 (an
unused near-twin of its round 276: same calibre and damage row, 12 words differ) and damage row 55
(owned by the equally unreferenced projectile 221). **"Unreferenced" is not proof of "unused"**: game
code, or tables outside the plaintext bundle, may refer to a row by enum value.

**In-game result (tuner v0.3.1, one tester): the takeover works.** With the Liberator on rows 267 / 55
and `damage = 5000` on its own rows, only the Liberator changed; restoring worked; no oddity reported.
So a weapon's `projectile_type` is read live enough for this, and rows 267 / 55 were safe in that session.

**How the game finds a row (probe, v0.3.1):** game.dll holds a static array of row pointers per table,
indexed by row id: 350 pointers for ProjectileSettings, 422 for ExplosionSettings, each pointing at a row
start, slot + 1 = row id for every one. The table's own row order is irrelevant. Consequences:
ids are fixed at build time (an id without a slot cannot be looked up, so tables cannot simply be
extended with new ids), and the number of things that can have a projectile of their own is bounded by
the number of unused ids: 80 projectile, 164 damage, 225 explosion rows offline.

**Second probe (v0.3.2): the lookups, decoded from the code that uses the arrays.** game.dll keeps the
arrays in its writable data section (rva: damage 0x37C60C8, projectile 0x37C7678, explosion 0x37CC928 for
the slot of id 1; the code addresses `array - 8`, the slot of id 0). A lookup is
`id == 0 ? &default_row : index[id]`, inlined in 64 (projectile), 487 (damage) and 46 (explosion) places.
ProjectileSettings and DamageSettings ids are NOT compared with a row count (8 projectile sites and the
stand-alone damage accessor at rva 0x11F8EA7 were read); ExplosionSettings ids are (`cmp eax, 423`), with
the default row as fallback. The table loader clears slots 0..N and refills them on every load.

**New ids without touching game code (tuner v0.4.1, `own_bullet = new`): works in game, solo** (one tester:
Liberator on projectile id 14569810, damage 5000 on it alone, second mission, restore; errors 0). How it works:
because the projectile id is unchecked and 32 bits wide, an id far above 350 reads its slot from memory
above game.dll. The mod allocates a block there, puts a copy of the weapon's row and a pointer to it
inside, and gives the weapon the id that lands on that pointer. As a client in an unmodded host's
lobby it also worked (host unaffected, the client's damage values counted). v0.5.0 does the same for the
damage row (index rva 0x37C60C0, 650 slots) and offers it for all 83 projectile weapons of the catalog.
**In game (v0.5.0, one tester): works** with six weapons at once (Liberator, Stalwart, Peacemaker, MG-43,
GL-21, Recoilless), different damage on weapons that share a round, errors 0. v0.6.0 makes it automatic. Open questions only the game can
answer: other per-projectile-id arrays, narrower copies of the id (network packing), the 56 sites not
read. Explosion rows cannot get new ids (bounds check); 225 spare rows exist there.

### 6.3 Copies, reloads, drift
Per the skill's case studies: several copies of a table can exist in memory, new copies appear on
mission load, table sizes / record counts / enum ids change with game updates. Hence: locate by
`LDLD + version + type hash` only, derive counts from sizes, identify rows by content, patch every
copy, re-verify cheaply, never gate on a hard-coded size.

### 6.4 Entity names
FileDiver's hash list names 232 of 365 weapon entities (114 are player weapons under
`content/fac_helldivers/equipment/...`); 133 are unnamed, which includes newer weapons. A complete
player-facing catalog (display names) needs another source — to be solved in Stage 3 (localization ids
are in the records; a recon dump can list what the build actually has).

## 7. What Stage 1 (read-only recon) must answer

1. Game build identity (exe/dll hashes, version string) on the testers' machines.
2. For each table in §4: found? how many copies? payload size, derived record count, stride check.
3. DLArray form in memory (absolute pointer vs offset) for `ProjectileSettings`, kit and passive blocks.
4. Do the offline values match live values for a fixed watch-list (e.g. Liberator fire/projectile/damage,
   HE grenade, one armor kit, avatar speeds)? This is what turns "O" into "G".
5. Which tables are present on the ship vs only in a mission.
6. Delta storage: present? component indices as inferred?

## 8. Recommendation on SHODAN

Per the project decision (no licensed code, avoid any license question): **reference only, zero code
reuse** — for both the GPL-3.0 v2.2.0 and the earlier Unlicense releases, and likewise for
Super-Earth-Armory-Forge (no license at all).

What we take from SHODAN is *facts*, each re-derived here from the typelib and data: which tables matter,
the chains in §4.1, that attachment deltas exist, and the evidence that these offsets work in a live game.
What we deliberately do not take: its scanner, its Windows API layer, its field/row model, its catalogs,
its UI. Our engine will be written from the layouts in this document with its own design (config-driven,
STATUS file, build gate, range checks, per-copy backup/read-back).

Other third-party material: FileDiver (BSD-3-Clause) is used only as offline *data* and as the reference
for `tools/dump_typelib.py` (a Python re-implementation of its typelib parser, for our offline tooling
only; nothing of it ships in the mod). hd2-lua-mod-skill (MIT) provides the workflow and packaging tools;
whether its `build_addon.py` / `hd2_archive.py` are used as-is is an open decision.

## 9. Reproducing this document

```
python tools/dump_typelib.py          # typelib -> data/typelib_all.json (no Go needed)
python tools/gostructs.py --audit     # name source A join statistics
python tools/schema_names.py <Type>   # merged layout of one type (A + B)
python tools/deltas.py                # attachment delta histogram
python tools/build_catalog.py         # every chain resolved -> data/catalog.json
```

`docs/LAYOUTS.txt` is the full generated layout of every record type referenced above.
`data/catalog.json` holds, per item and stat: table, key, record type, field path, offset, storage and
the original value — the seed for the engine's stat list and for the recon watch-list.
