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

## Sections

`[<category>: <item>]`. Categories in this version: `weapon`, `throwable`.
Planned (Stage 3): `stratagem`, `backpack`, `shield`, `vehicle`.

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
