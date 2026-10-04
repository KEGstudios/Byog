# Config format (approved 2026-10-01)

File: `%LOCALAPPDATA%\HD2StatTuner\config.txt` — plain text, edited by hand. The mod creates a
commented template on first run. `#` starts a comment. Names are case-insensitive.

```ini
[settings]
enabled = true            # false: every value goes back to the game's own
reload_key = F10          # press in game to read this file again and apply it (F1..F12)
auto_reload_seconds = 0   # 0 = off; N = re-read every N seconds and apply when the text changed

[weapon: assault_rifle]
damage = 120              # absolute value
rpm = 150%                # percent of the game's value
magazine = +15            # the game's value plus 15
recoil_v = -20            # the game's value minus 20
```

## The in-game menu (works in game since v0.15.2)

`[settings] menu_key = F9` (F1..F12) opens a panel in the middle of the screen: categories, items, and the
values of the selected item. Up / Down and PageUp / PageDown move, Tab switches between the item list and
the value list, Left / Right changes the category or the value (Shift: ten times the step), Delete puts a
value back to the game's own. A change is applied by the engine like a config line. The menu's values
are kept in `menu.txt` next to config.txt, are read again at the next start, and **win over config.txt**
for the same value. Deleting menu.txt forgets them. The menu shows the game's own names where they are known
(`tools/display_names.txt`, written by hand: AR-23 Liberator, MG-43 Machine Gun...) and the internal name
otherwise; config.txt and menu.txt always use the internal names, which catalog.txt lists side by side. While the menu is open the game still receives the keys.

Search (v0.16.0, not yet tested in game): in the item list, typing letters or digits lists every item of
every category whose name, the game's or the internal one, contains what was typed. Backspace removes a
letter, Delete clears the search.

## Sections

`[<category>: <item>]`. Categories: `weapon`, `throwable`, and since v0.10.0 (works in game: cooldown,
uses, backpack charges, shield health, vehicle health; the stats added in v0.11.0 are not yet tested):

| Category | Items | Stats |
|---|---|---|
| `stratagem` | 149 rows of the game's stratagem table, named after the game's own debug names (`eagle_500kg_bomb`, `orbital_laser`, `sentrys_machinegun`...) | `cooldown` (seconds), `uses` (4294967295 = unlimited) |
| `backpack` | 18 backpacks (`recoilless_rifle_backpack`, `ammo_backpack`...) | `charges`, `charges_start` (-1 = start full), `charges_refill` |
| `shield` | 4 (`energy_shield_backpack`, `directional_energy_shield`, `energy_shield` = the relay, `energy_shield_grenade`) | `shield_health`, `shield_radius`, `shield_recharge_delay` (before an unbroken shield refills), `shield_broken_delay` (after it broke), `shield_recharge_rate` (per second) - settled in game |
| `vehicle` | 14 (`combat_walker` = Patriot, `frv`, `tank`...) | `health`, `armor`, `durable_resistance`, `explosion_damage_multiplier`, `constitution`, `constitution_rate`; per part `part_<name>_health`, `_armor`, `_durable_resistance`, `_to_main`, `_overflow_cap`; `all_health` |

| `stratagem_weapon` (v0.13.0) | 53: the guns of sentries, emplacements, drones, exosuits and the Eagle (`turret_machinegun_gpmg`, `gatling_turret`, `mortar_turret`, `combat_walker_autocannon_left`...), and the shells of orbital and Eagle strikes (`orbital_precision_strike`, `orbital_380mm_he_barrage_shell1`...) | the same stats as a hand weapon: damage, armor penetration, blast, fire rate... |

`lifetime_seconds` (v0.16.0, not yet tested in game), on sentry guns, the Tesla tower and the shield
relay: how long the deployed thing stays before it removes itself (sentries 150, mortar sentries 180,
shield relay 40; 0 = stays).

Each of the first four is one record per item: nothing is shared, nothing else changes. A stratagem's gun
is treated like a hand weapon: when a projectile or damage stat is set it gets rows of its own, so the
sentry's machine gun and the MG-43 in a diver's hands, which fire the same round, can differ. Since v0.14.0 the
shells of orbital and Eagle strikes get rows of their own in the same way.

In game (v0.13.0): an orbital shell's blast radius, `blast_from` and the status slots work. The sentry's
gun did not change: it takes its rounds from the belt pattern of its magazine, which v0.14.0 switches
as well (in game: the machine gun sentry then one-shots; the MG-43 in the same test stayed unchanged
because the engine had lost sight of the tables, fixed in v0.15.0). A stratagem value changed
during a mission takes effect after the stratagem's next use (seen in game).

**Vehicle parts.** A vehicle's parts (legs, cockpit, doors, tracks...) have their own health and armor.
The game stores a part's name as a hash; 35 of the 88 names were recovered (`part_leg_left_health`,
`part_cockpit_rear_armor`, `part_left_track_health`...), the others appear with their hash
(`part_fed0a478_health`). The Patriot exosuit's eight parts are all named.

Damage to a part also goes to the main health, by the part's `to_main` share (1 = all of it). So a part
whose health is more than the main health can pay for never breaks: the vehicle is destroyed first
(seen in game, v0.11.0). STATUS.txt puts a WARNING on such a line; it does not change the main health
by itself. `all_health = 150%` scales the main health and every part's health together, which keeps
the game's relations. `part_<name>_overflow_cap = 1`: the share stops once the part's own health is gone.

A line that names one value wins over a shortcut that also covers it: with `all_health = 300%` and
`part_leg_left_health = 10` the leg gets 10 and STATUS.txt says so on the shortcut's line (v0.12.1; in
v0.12.0 the two lines rejected each other). This holds for every shortcut (`recoil`, `ap`, `spread`...).

`part_<name>_to_main = 0` stops a part from passing damage on (works in game: shooting the bonnet of the
FRV no longer lowered its health). A fraction did not scale it in the one test made (0.5 behaved like 1).

**`blast_from = <item>`** (v0.13.0, works in game: a grenade launcher with `gas_grenade` leaves gas and
does no blast damage, a frag grenade with `incendiary_grenade` leaves fire), for weapons that fire projectiles and for
throwables: the item explodes like the named item (`blast_from = gas_grenade`). The value is an item
name of `catalog.txt`, never a number: row ids change with game updates. A weapon gets the explosion in
its own projectile row (on impact), a throwable in its own component record. The explosion itself stays
the source item's: changing the source's blast values changes both.

**Status effects** (v0.13.0, works in game: `status1_type = 5`, `status1_value = 50` on the Liberator sets enemies on fire): `status1_type` .. `status4_type` and
`status1_value` .. `status4_value` (and `blast_status...` for an explosion): what a hit applies. The
types are numbers of `docs/STATUS-EFFECTS.md` (5 = Fire, 42 = Gas, 37 = Stun Small...).

**`[settings] dump_globals = true`** (research, read-only): writes the names of the game's Lua globals
to `GLOBALS.txt`, for building the in-game menu.

`[settings] ui_probe` (research, v0.14.0 only) drew a test rectangle; it showed that an addon can draw.
The setting is still accepted and does nothing since v0.15.1.

A stratagem's call-in time is not offered: the field the data calls `spawn_time` changed nothing in game.

`<item>` is the game's internal name (for example `assault_rifle` is the AR-23 Liberator). Every item
and stat the mod knows, with the game's value and the allowed range, is listed in
`%LOCALAPPDATA%\HD2StatTuner\catalog.txt`, which the mod writes itself. In-game display names come
with the UI (Stage 3).

## Values

| Form | Meaning |
|---|---|
| `120` | set to 120 |
| `150%` | 150 % of the game's own value |
| `+15`, `-5` | the game's own value plus / minus |

Whole-number stats are rounded to the nearest whole number. A result outside the stat's allowed range
is **rejected** (never clamped) and reported in STATUS.txt with the range.

## Rules

* Removing a line (or a section) and reloading puts that value back to the game's own.
* **One weapon at a time (v0.6.0).** In the game's data many weapons share one projectile row and one
  damage row. When a line sets a projectile or damage stat of a weapon that fires projectiles, the mod
  gives that weapon rows of its own first (brand-new row ids in memory the mod allocates), so the change
  reaches this weapon only. STATUS.txt shows it as `rows of its own (automatic)`. Tested in game
  (v0.6.0): two weapons that share a round got different damage without any `own_bullet` line.
* **Shared values that remain.** Explosion rows, and everything of items that do not fire projectiles,
  are still shared: setting one changes every user; STATUS.txt lists them under "also affects". If two
  lines ask for different values of the same shared value, **both are rejected**.
* `[settings] own_rows = off` turns the automatic rows off for the whole config, and
  `own_bullet = false` in a weapon's section does it for that weapon: its projectile and damage stats
  are then written to the shared rows, as in the first versions.
* **Values of the default attachment (v0.7.0, works in game).** For 21 weapons the magazine
  values (`capacity`, `mags_start`, `mags_supply`, `mags_max`) or heat values are not read from the
  weapon: the attachment the weapon carries by default (its magazine, its heat sink) lays its own values
  over them. The mod writes those attachment values; catalog.txt marks them `value of the default
  attachment`, and `150%` / `+5` count from the value the game really uses. Two limits:
  * an attachment can be the default of several weapons (one magazine is shared by `assault_rifle`,
    `assault_rifle_ap` and `assault_rifle_whisper`): the change reaches all of them, STATUS.txt lists
    them under "also affects", and different values for the same attachment reject each other;
  * a different attachment put on the weapon in the armory brings its own values, which this version
    does not touch.

  The game reads these values when the weapon is created: a change made during a mission shows on the
  next weapon (seen in game: after dying and coming back), not on the one already in hand.
* **Magazine values of a weapon's own (v0.8.0, works in game).** With `own_rows = auto` (the
  default) a magazine stat of one of the 18 weapons whose default magazine attachment sets it no longer
  goes into the attachment. The mod switches that attachment's magazine values off (one count in the
  delta storage is set to 0) and writes the values into the weapons' own records: the config's for the
  weapon being changed, the attachment's stock values for every other weapon that carries this
  magazine by default. Two weapons with the same magazine can then have different values, and nothing is
  listed under "also affects". Known limit: a weapon on which the player has fitted that magazine as a
  non-default choice reads its own record, which the mod has not filled. `own_rows = off` keeps the
  v0.7.0 behaviour.
* `mags_start` above `mags_max` is capped by the game (seen in game: 10 with a maximum of 8 started
  with 8). STATUS.txt puts a WARNING on the line; the mod does not raise the maximum by itself.
* **Explosions of an item's own (v0.9.0, works in game).** With `own_rows = auto` a `blast_*`
  or `expiry_*` stat reaches the item it is written for only:
  * 31 of the 57 explosions behind catalog items already belong to one item; their values are written
    in place.
  * 11 belong to one item but share their damage row: a blast damage stat gives the explosion a new
    damage id (as projectiles get theirs).
  * 15 are reached by something else as well (another grenade, a turret or vehicle firing the same
    round...). Explosion ids cannot be new (the game checks them), so the item gets a **borrowed**
    explosion row: one of 24 rows that no table in the game's memory refers to is overwritten with a
    copy of the item's row and put back when the line is removed. STATUS.txt lists them under
    `[borrowed rows]`. A row that only game code uses would be invisible to that check: if some other
    explosion in the game suddenly looks like the edited weapon's, that row was not free.
  In game (v0.9.0, one tester): GL-21 and the frag grenade got explosions of their own, everything
  else stayed normal. The canary ran for two missions without unexpected smoke; not every exploding
  thing in the game was tried, so an odd explosion later is to be reported.
* **`[settings] canary = true`** (research): turns all 24 rows of the borrowing list into copies of
  the smoke grenade's explosion. Anything in the game that uses one of them then shows smoke instead
  of its own explosion. While it is on, no row is borrowed.
* **`[settings] census = true`** (research, read-only): once per session, in a mission, counts in every
  table in memory the references to each explosion row and writes `CENSUS.txt`. Nothing is written to
  the game; config values are applied after the census has finished.
* **Fire rate.** A weapon with a fire-rate selector has three rates. `rpm` is the default one (the
  middle setting); `rpm_low` and `rpm_high` are the other two and are set on their own lines. Seen in
  game (v0.6.0): `rpm = 200%` on the MG-43 changed the middle setting only.
* `ap = N` sets every armor-penetration angle that is not 0 in the game's data; `ap_direct`,
  `ap_slight`, `ap_large`, `ap_extreme` set a single angle.
* Per-weapon values that are never shared: `ap_bonus`, `durable_ap_bonus` (armor penetration added for
  this weapon only; tested in game: works) and `speed_multiplier` (untested). `bonus2` /
  `durable_bonus2` are the second addend pair of the weapon record; their effect is unknown.
  There is **no per-weapon damage addend** in the game data that works.
* **`own_bullet = true`** (experimental, only for weapons listed with it in catalog.txt): the weapon
  gets a projectile row and a damage row of its own, copied from the ones it shares. After that,
  `damage`, `ap`, `velocity` and the other projectile / damage stats of this weapon change this weapon
  only. The rows it takes over are rows nothing in the game data refers to; if the game uses them after
  all, whatever uses them fires this weapon's round while the mod is active. Removing the line puts the
  weapon and both rows back exactly as they were.
* **`own_bullet = new`**: gives a weapon rows of its own even when no stat of it is set (what the
  automatic rule does by itself). The game is never switched to the new ids unless its row indexes were
  first checked against the tables. Tested in game solo and as a client in another player's lobby; a
  lobby hosted by the modded player with players who do not have the mod has not been tested.
* Stats whose live value comes from a default attachment (magazine size on some weapons, see
  STAT-MAP §6.2) are refused in this version with a clear reason; they are Stage 3 work.
* The mod writes nothing unless the game's executable and game.dll match a build it was verified on.

## What the mod writes back

`%LOCALAPPDATA%\HD2StatTuner\STATUS.txt` — first line is the verdict; then build check, tables found,
every config line as applied / rejected (with the reason) / waiting (its table is not loaded yet; some
tables only load with a mission), read-back results and errors.
