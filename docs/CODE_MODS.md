# Code mods

The recomp turns the game's code into C when it installs, so `mlb.exe` can't be patched afterwards the way a
normal PC game can. Its builder takes a patch table instead and bakes the changes in. **Code Mods** drives that:
it joins every code mod into one table, runs the recomp's generator and build, and swaps `mlb.exe` (the one it
replaced is kept as `mlb.original.exe`).

You need the recomp folder for this, the one `MLBTS-Setup.exe` is in. A rebuild takes about two minutes.

## Using them

Everything is on one page. The manager's own code mods are always in the list, and so is the code of any mod you
have, whether that mod is on or off in Mods. Each code mod has one switch.

1. Press **Rebuild Game** once. Every code mod in the list is built in, switched off.
2. Switch on what you want and play.

After that first rebuild nothing needs rebuilding again until the list itself changes (you import a code mod, or
the manager updates its own).

Some code mods have a **dial**: a number you can turn. Exit Velocity's dial is how many times harder the ball
comes off the bat; Air's is how much air it flies through.

## In the game

**F4** opens the same list over the game.

| Key | Controller | What it does |
| --- | --- | --- |
| F4 | Options closes | Open and close the list |
| Up, Down | D-pad | Move |
| Enter | Any face button | Switch the mod on or off |
| Left, Right | D-pad | Turn its dial (on a mod without one: off and on) |

Changes take effect at once and are remembered. While the list is open the game ignores the controller, the same
as with its own F1 menu. **F2** and **F3** still work with the list closed: F2 steps through the mods, F3 switches
the one shown.

## What comes with the manager

| Code mod | What it does |
| --- | --- |
| Exit Velocity (dial) | Every ball comes off the bat harder, and the exit velocity on screen shows it. |
| Auto PCI | Your PCI snaps onto the ball on every swing. You still have to time it. |
| Auto PCI Everyone | The same for every hitter, CPU included. |
| Auto PCI Visual | The PCI on screen moves onto the pitch by itself. Experimental. |
| Perfect Perfect | Every ball you put in play counts as perfect PCI and perfect timing. Experimental. |
| Unbreakable Bats | Bats never break. |
| Air (dial) | How much air the ball flies through. Low and fly balls carry forever; high and they die early. |
| Rocket Arms | Thrown balls travel 1.25x faster. Experimental. |
| Heat, Soft Toss | Every pitch comes in about 15% faster, or 15% slower. Experimental. |
| Iron Arms | Pitchers tire four times slower. Experimental. |

Experimental means it is built from reading the code and hasn't been confirmed in a game yet. These are for
offline play.

## Checking that one works

Code Mods shows it for you after a game:

- Under each mod: how many times its code ran in your last game. A mod that was on and ran zero times never got
  its turn, which is worth reporting.
- **Last game**: what the game itself recorded. The hardest ball hit (with Exit Velocity on it goes well past
  120 mph), the air density (about 0.075 untouched), the biggest pitch break, and how far off the PCI was on the
  last swing (0.00 with Auto PCI).

The files behind that, if you want to look yourself: `<game>\logs\mts-code.log` (what was on, each dial, how
often each mod ran) and `<game>\logs\mlb.log` (the game's own notes: `AutoHit::m_fPowerMPH`,
`AutoHit::m_fAirDensity`, `Actual Pitch Movement`, `BATTER SWING DIAGNOSTICS`). Your switches and dials are saved
in `<game>\mts-code.cfg`, which the game reads when it starts, so they hold whether you launch from the manager
or not.

## Getting more

- **Get More** opens Discover, where shared mods can carry code.
- **Import** takes a `.patch` file someone sent you, or a shared mod's `.zip`.

Either way the code mods show up in the list switched off, and the next Rebuild Game builds them in.

## Making your own

**Make Your Own** puts a starter file in your mod's `code` folder with the format explained in it.

```
#group Hitting
#: big_fly: Balls come off the bat harder.
#dial big_fly 1.5 0.5 4 0.25 Power x
set  big_fly MLB_MOD_BIGFLY 0
site big_fly main 167d0b8 bd404a60 bd404a60 $big_fly:s1 1e210800 bd004a60
```

- `set <name> <SWITCH> <default>` is one switchable code mod. The switch is an environment variable that also
  works at launch.
- `site <set> <module> <offset> <original> <replacement> ...` replaces one instruction. `<module>` is `main` or
  `sdk`, `<offset>` is where the instruction sits in that module, `<original>` is the ARM64 word that is there
  now, and the replacement is one or more ARM64 words that run in its place.
- `#: name: text` is the description. `#group Heading` puts the sets under it beneath that heading. `#tag name:
  Experimental` adds a mark beside the name.
- `#dial <name> <start> <lowest> <highest> <step> <label>` makes a dial, and `$name:s1` in a site loads its number
  into float register `s1` (any `s` register the code isn't using at that point).

The rules the recomp's builder enforces: the original word must match, a replacement may only branch in its last
word, and it must write the same flags the original did. That last one matters: a replacement for a plain
`fsub` can't use `cmp`. Auto PCI shows how to pick between two values without touching the flags.

The manager reads `game/exefs/main` before a build and leaves out any set whose original words don't match your
game version, instead of letting the build fail.

## How it is built

For the curious. The runtime library the recomp ships was built with no patch sets, so its switches are never
filled in and a baked-in patch would stay off for good. The manager adds one C file of its own to the build
(`mts_switches.c`) that holds the switches, the dials, a counter per mod and the F4 menu, and points the patched
code at it. A dial is written into the table as an instruction no real patch uses; after the recomp translates
it, the manager swaps that number for the live one. If that ever fails, the dials are built in at their current
numbers instead and the build still works.

## The map so far

Offsets in `main` for game version 1.0.15, read off the code. Not every one has been tried in a game yet. The code
is ARM64; `x19` and friends are registers.

**The hit** (function at `167a6ac`). The hit record is in `x19`.

| Where | What |
| --- | --- |
| `167d0b4` | `movk w9, #0x3fbb, lsl #16` finishes the constant 1.4667 (mph to feet per second). Power in mph times this is the ball's speed off the bat. |
| `167a8cc` | Stores the perfect PCI flag (hit record `+0x4c`). |
| `167a8d8` | Result of the perfect timing check (function `1678010`), stored at `+0x4e`. |
| `167bd4c` | Human or CPU: the word at `+0xbc` of the settings block (`[context + 0x40]`) is 9 for a CPU hitter. Picks the human or CPU contact slider. |
| `16808d4` to `1680c70` | The power penalties (jammed, off the end, and so on). |
| `167d0b8` | `ldr s0, [x19, #0x48]` loads the hit's power in mph. The exit velocity shown after the play is read from the same place (`f4f2e8`), so a change written back here shows on screen. |
| `167d828` | Broken bat power multiplier. |
| `16785f8` | Check swing power multiplier. |

Hit record: `+0x1c` late/inside rating, `+0x20` early/outside rating, `+0x28` to `+0x30` direction then velocity,
`+0x48` power in mph, `+0x4c` perfect PCI, `+0x4e` perfect timing.

**The swing** (function at `3560d0`). The swing record is in `x19`, the pitch in `x21`.

| Where | What |
| --- | --- |
| `356718` to `35673c` | Aim error: PCI position (`x19 + 8`, `+ 0xc`) minus where the pitch crosses the plate (`x21 + 0x148`, `+ 0x14c`), stored at `x19 + 0x10` and its length at `+ 0x118`. |
| `35acdc` | Broken bat chance, from bat speed, location and timing. |

**The ball**

| Where | What |
| --- | --- |
| `165ac78` | Last multiply of the air density function (temperature and altitude in, density out). |
| `1688088` | 1.4667 again, for a thrown ball's speed. |
| `166a6e4` | 1.4667 in the release setup shared by pitches and throws (speed and distance in, flight time out). |
| `24ada4`, `24adb0` | The low and high ends of a pitch speed multiplier (about 0.95 and 1.05). Not confirmed in a game. |

**Stamina**

| Where | What |
| --- | --- |
| `3c56fc`, `3c5710` | The 2.1 that fatigue per pitch starts from, before the fatigue slider scales it. |

Not found yet: runner speed (the top speed readout is at `2e85b0`, the code that uses it isn't traced), pitch
speed on its own, fielder reactions, the strike zone.

## Finding more

The game still has its debug text, and that is the way in. Search the strings in `main` for something that
describes what you're after ("Broken Bat Chance", "Slider settings adjust fatigue"), find the code that prints it,
and the numbers being printed are being computed a few instructions earlier. Numbers aren't stored as data: the
game builds them with `movz`/`movk` and `fmov`, so a constant like 1.4667 can be searched for as the instruction
that makes it.
