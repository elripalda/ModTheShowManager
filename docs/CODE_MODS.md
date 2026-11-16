# Code mods

The recomp turns the game's code into C when it installs, so `mlb.exe` can't be patched afterwards the way a
normal PC game can. Its builder takes a patch table instead and bakes the changes in. **Code Plugins** drives that:
it joins the patch tables of the mods that are switched on, runs the recomp's generator and build, and swaps
`mlb.exe` (the one it replaced is kept as `mlb.original.exe`).

You need the recomp folder for this, the one `MLBTS-Setup.exe` is in. A rebuild takes about two minutes.

One thing the manager does on top: the runtime library the recomp ships was built with no patch sets, so its
switches are never filled in and a baked-in patch would stay off for good. The manager adds a small file of its
own to the build that holds the switches and fills them in when the game starts.

## The samples

**Add Arcade Samples** puts these in a mod called Arcade Code Mods. Tick what you want, **Rebuild Game** once, then
start the game. After that, ticking and unticking takes effect the next time the game starts, with no rebuild.

| Sample | What it does |
| --- | --- |
| Auto PCI | Your PCI snaps onto the ball on every swing. You still have to time it. |
| Auto PCI Everyone | The same for every hitter, CPU included. |
| Perfect Perfect | Every ball you put in play counts as perfect PCI and perfect timing. Experimental. |
| Orbit Shots, God Power, Moonshot, Juiced Ball | Balls leave the bat 3x, 2x, 1.5x and 1.25x faster. |
| Dead Ball | Balls leave the bat 20% slower. |
| Thin Air | A quarter of the air density everywhere. Fly balls carry. |
| Rocket Arms | Thrown balls travel 1.25x faster. Experimental. |
| Unbreakable Bats | Bats never break. |
| Iron Arms | Pitchers tire four times slower. Experimental. |

These are for offline play. None of them have been through a full season, so try one at a time first.

## Checking that one is on

- **Code Plugins** says what the game had on the last time it started, and what its log recorded about your
  last swing.
- `<game>\logs\mts-code.log` is written every time the game starts: one line per code mod, `1` for on, and
  where the answer came from.
- `<game>\logs\mlb.log` has the game's own notes. After a swing with Auto PCI on, the `ErrorXY` in
  `BATTER SWING DIAGNOSTICS` reads `0.00, 0.00`. With Perfect Perfect on, the `PERFECT PERFECT` line reads `1 1`.

Your ticks are saved in `<game>\mts-code.cfg`, which the game reads when it starts, so they hold whether you
launch from the manager or not.

## Writing one

A mod carries its patches in `code/*.patch`. **New Code Mod** makes a starter file with the format explained.

```
set  moonshot MLB_MOD_MOONSHOT 0
site moonshot main 167d0b4 72a7f769 72a80189
```

- `set <name> <SWITCH> <default>` is one switchable group. The switch is an environment variable the manager sets
  when it launches the game.
- `site <set> <module> <offset> <original> <replacement> ...` replaces one instruction. `<module>` is `main` or
  `sdk`, `<offset>` is where the instruction sits in that module, `<original>` is the ARM64 word that is there
  now, and the replacement is one or more ARM64 words that run in its place.
- A line starting with `#: name: text` is the description the manager shows next to the tick box.

The rules the recomp's builder enforces: the original word must match, a replacement may only branch in its last
word, and it must write the same flags the original did. That last one matters: a replacement for a plain
`fsub` can't use `cmp`. The Auto PCI sample shows how to pick between two values without touching the flags.

The manager reads `game/exefs/main` before a build and leaves out any set whose original words don't match your
game version, instead of letting the build fail.

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
