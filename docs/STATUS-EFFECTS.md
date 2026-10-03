# Status effect ids

The values of `status1_type` .. `status4_type` (and `blast_status1_type` ...). Read from the game's
memory by the recon build (v0.1.0, 2026-10-01) on build `release/01.007.101/19155`; the table is not in
the offline data, and the ids can change with a game update. `0` = empty slot.

A weapon applies a status through its damage row: up to four slots of (type, value). Whether a target
takes it depends on the target and on the status itself; an id that exists is not a promise that it does
anything on that weapon. Untested in game as of tuner v0.13.0.

| id | name | id | name | id | name |
|---|---|---|---|---|---|
| 1 | Blind | 25 | Stim Fx | 49 | Backpack Chemicals |
| 2 | Bleed | 26 | Stim Stamina | 50 | Intense Heat |
| 3 | Deaf | 27 | Stim Heal | 51 | Extreme Cold |
| 4 | Confusion | 28 | Stim Pistol Heal | 52 | Tremor |
| 5 | Fire | 29 | Stim Combat Drugs | 53 | Sandstorm |
| 6 | Fire_Panic | 30 | Stim Cooldown | 54 | Blizzard |
| 7 | Lava | 31 | BurningLight | 55 | Acid Storm |
| 8 | Slowed | 32 | BurningHeavy | 56 | Weather Insulated |
| 9 | Rooted | 33 | RadiationLight | 57 | TornadoStun |
| 10 | Acid Splash | 34 | RadiationHeavy | 58 | Dark Fluid |
| 11 | Acid Stream | 35 | Electric | 59 | Death March |
| 12 | Thermite | 36 | Hidden | 60 | Hotshot Laser Rifle |
| 13 | Cyborg Fire | 37 | Stun Small | 61 | Hotshot Laser Rifle |
| 14 | Choked | 38 | Stun Medium | 62 | Hotshot Laser Rifle |
| 15 | Sand | 39 | Stun Large | 63 | Illuminate Scrambler |
| 16 | Mud | 40 | Stun Massive | 64 | Constitution |
| 17 | Snow | 41 | Stun Illuminate | 65 | Constitution Booster Armor Resistance |
| 18 | Submerged | 42 | Gas | 66 | Post Mortem Explosion |
| 19 | Thornbush | 43 | Gas | 67 | FlamerSlowed |
| 20 | Cactus | 44 | Gas_Confusion | 68 | Gloom |
| 21 | Barbwire | 45 | Gas_Confusion | 69 | Dark Fluid |
| 22 | BushSmall | 46 | Inverted_Aim_Assist | 70 | Poison |
| 23 | BushLarge | 47 | Flashlighted | 71 | PoisonVulnerability |
| 24 | Pure Damage | 48 | Smoke_Covered | | |
