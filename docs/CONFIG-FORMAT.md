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
* **Shared values.** Damage, projectile and explosion rows are shared between weapons (and with
  stratagems and enemies). Setting one changes every user; STATUS.txt lists them under "also affects".
  If two lines ask for different values of the same shared value, **both are rejected**.
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
* **`own_bullet = new`** (more experimental; solo play only): the same, but the projectile row is a
  brand-new one in memory the mod allocates, reached through a projectile id the game does not have.
  No spare projectile row is used up. The game is never switched to the new id unless its row index
  was first checked against the table. Other players without the mod do not have this id: do not use
  it in multiplayer until that has been tested.
* Stats whose live value comes from a default attachment (magazine size on some weapons, see
  STAT-MAP §6.2) are refused in this version with a clear reason; they are Stage 3 work.
* The mod writes nothing unless the game's executable and game.dll match a build it was verified on.

## What the mod writes back

`%LOCALAPPDATA%\HD2StatTuner\STATUS.txt` — first line is the verdict; then build check, tables found,
every config line as applied / rejected (with the reason) / waiting (its table is not loaded yet; some
tables only load with a mission), read-back results and errors.
