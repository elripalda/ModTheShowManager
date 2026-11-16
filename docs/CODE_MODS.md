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

| Key | What it does |
| --- | --- |
| F4 | Open and close the list |
| Up, Down | Move |
| Enter | Switch the mod on or off |
| Left, Right | Turn its dial (on a mod without one: off and on) |
| F6 | Fireworks, when that mod is on |

The game draws the list itself, the way it draws its own F1 menu, so it shows in fullscreen too. Changes take
effect at once and are remembered. While the list is open the game ignores the controller, the same
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
| Power Bunts (dial) | A bunt comes off the bat like a real swing. Experimental. |
| Air (dial) | How much air the ball flies through. Low and fly balls carry forever; high and they die early. |
| Bouncy Ball (dial) | How much the ball bounces off the ground and the walls. Experimental. |
| Gravity (dial) | How hard the ball is pulled down while it flies. Low is moon ball. Experimental. |
| Rocket Arms | Thrown balls travel 1.25x faster. Experimental. |
| Pitch Speed (dial) | How fast every pitch gets to the plate. Experimental. |
| Pitch Break (dial) | How hard spin bends the ball. Turn it up for wiffle ball. Experimental. |
| Iron Arms | Pitchers tire four times slower. Experimental. |
| Fireball (dial) | A pitch thrown hard enough catches fire: flames, a glow, embers and smoke. Experimental. |
| On Fire | Streaks. Three whiffs in a row heat up the pitcher; three hard-hit balls in a row heat up the lineup. Experimental. |
| Fireworks (dial) | Fireworks over the field on F6, and for a rocket off the bat. Experimental. |

Experimental means it is built from reading the code and hasn't been confirmed in a game yet. These are for
offline play.

The last three are **Effects**. Nothing in them is the game's art: the manager simulates its own particles in the
game's space and draws them over the picture every frame. They are drawn on the frames the game's overlay lays
out, so they show while its fps readout is on. The manager switches that on for them; F10 is the readout's own
key, and switching it off there puts the effects out too.

## Checking that one works

Code Mods shows it for you after a game:

- Under each mod: how many times its code ran in your last game. A mod that was on and ran zero times never got
  its turn, which is worth reporting.
- **Last game**: what the game itself recorded. The hardest ball hit (with Exit Velocity on it goes well past
  120 mph), the hardest bunt, the air density (about 0.075 untouched), how far pitches broke, and how far off the
  PCI was on the last swing (0.00 with Auto PCI).

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
- `#turns <set> <dial>` gives a set a dial that no site loads. The Effects use it for numbers their own code reads,
  like the speed a pitch has to reach before it burns.

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

A site can also just watch. One whose replacement is the original word changes nothing, and its counter still
goes up each time the game gets there: On Fire counts swings that way. And one whose replacement starts with
`mov x16, xN` (`aa0003f0` for `x0`) hands that register to the manager's own code each time it runs, which is how
Fireball gets hold of the ball. `x16` is only free to use like that on the first instruction of a function.

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
| `16767d0` | Makes a bunt: direction and power in (power capped at 130 mph), hit type 18 out. Power is stored at `1676838`. |
| `167880c` | Where every hit starts. A hit that was worked out beforehand goes to `1678848`; everything else to `167a6ac`. |
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
| `1655ad4` | Launches a pitch: speed in mph in, times 1.4667 at `1655b18`, then a plain arc to the aim point. |
| `1665460` | Pitch or throw: a pitch (`+0x482` set) takes its speed from the ball's `+0x454` or `+0x458` and goes to `1655ad4`; a throw goes to `1688000`. |
| `1656f78` | The forces on a ball in the air. Spin crossed with velocity at `16570b4`, times a lift number, times 71.86 at `1657168`: that is what makes a pitch break. Drag (0.31) at `165733c`. Rolling friction (-0.8 or -1.2 by surface) at `16573bc`. |
| `1658dbc` | The ball hitting something. `1659528` multiplies the ball's own bounce (`+0x24`) by the surface's. |
| `1665f68` | Prints `Actual Pitch Movement`: where the pitch ends (`+0x420`) minus where it was aimed (`+0x42c`). |
| `165ac78` | Last multiply of the air density function (temperature and altitude in, density out). |
| `1688088` | 1.4667 again, for a thrown ball's speed. |
| `166a6e4` | 1.4667 in the release setup shared by pitches and throws (speed and distance in, flight time out). |
| `24ada4`, `24adb0` | The low and high ends of a pitch speed multiplier (about 0.95 and 1.05). Not confirmed in a game. |

**Where things are, for drawing over the game**

| Where | What |
| --- | --- |
| `166a2a4` | Releases the ball (it prints `ACTUAL RELEASE MAT`). The ball is in `x0`. |
| ball `+0x560` | The ball's object on the field. Its place in the world is three floats at `+0xe0`, in feet. |
| ball `+0x454`, `+0x458` | The pitch's speed in mph; the first wins when it is set. |
| `28f51f8` | A pointer to the camera. Its matrix is at `+0x110` (rows: right, up, forward, where it stands), its two projection scales at `+0x500`. |
| `119e918` | The game's world-to-screen routine: take the point relative to the camera, dot it with the three rows for x, y and z, and the spot on screen is `0.5 - 0.5 * scale * x / z` across and the same with y down, from the top left. It is in front of the camera when z is above 0. |

The field is measured from the pitching rubber. Towards the plate is +z (the plate is at 60.5), up is +y, and a
pitch is let go around z = 9.

**Gravity** is not a setting: it is a flat 32 added to the ball's fall at `16571c0`, in the forces function.

**Contact** (function at `358744`, read from the code, not tried in a game)

| Where | What |
| --- | --- |
| swing `+0x60`, `+0x64` | The inner and outer PCI sizes for this swing, set at `3568f4`. |
| `358744` | The chance of contact: the aim error against those two sizes. Inside the inner one is 1 to 2, between them 1 down to 0. The game logs it as `Hitchance`. |
| `356a18` | Pulls the outer size in towards the inner one, by an amount that depends on the swing and, for one kind of swing, on Competitive. What drives it is not traced yet. |
| `1680bcc` to `1680c30` | In Competitive, contact on a pitch outside the zone loses up to 10% of its power, by how far outside. One game mode takes it off a second time. The game logs it as `Outside SZ`. |
| `aa760`, `aa7f0`, `aa7c0` | Competitive, Simulation, Casual. The flags the hitting code reads are copied at `abb2c` (`+0x2b` and `+0x35` Competitive, `+0x22` Simulation, `+0x23` Casual). |

**Stamina**

| Where | What |
| --- | --- |
| `3c56fc`, `3c5710` | The 2.1 that fatigue per pitch starts from, before the fatigue slider scales it. |

Hit types, in the game's order: 0 MISSED_EARLY, 1 MISSED_INSIDE, 2 MISSED_BELOW, 3 TIP_BACKSTOP, 4 POPUP_BACKWARD,
5 POPUP_FORWARD, 6 HIGH_FLY, 7 MEDIUM FLYBALL, 8 LINE_DRIVE, 9 HARD_GROUNDER, 10 EASY_GROUNDER, 11 CHOPPER,
12 DRIBBLER, 13 TIP_CATCHER, 14 MISSED_OVER, 15 MISSED_OUTSIDE, 16 MISSED_LATE, 17 CORKSCREW, 18 BUNT.

Not found yet: runner speed (the top speed readout is at `2e85b0`, the code that uses it isn't traced), fielder
reactions, the strike zone, the pitch speed shown on screen, Road to the Show tokens (the names are there:
`AVAILABLE_TOKENS`, `tokens_remaining`, `num_tokens_earned`; the sum behind them isn't traced).

## From an idea to a code mod

How Power Bunts was made, as a pattern to follow. You need a disassembler that reads ARM64 (Ghidra is free) with
`game/exefs/main` loaded in it.

1. **Find the words.** The game keeps its debug text, so search the strings for what you're after. "BUNT" turns
   up in a list of hit types (`MISSED_EARLY`, `TIP_BACKSTOP`, ... `BUNT`), and BUNT is number 18 in it.
2. **Find the code that uses them.** Look for the code that writes 18 into a hit. One small function does
   (`16767d0`): it takes a direction and a power, caps the power at 130 mph and stores it.
3. **Pick the instruction.** The store is at `1676838`: `str s1, [x19, #0x48]`, word `bd004a61`. Multiplying
   `s1` just before it makes every bunt harder.
4. **Check what you may use.** The patch needs a spare register for the multiplier. `s2` was only holding a zero
   at that point and is written again before it is next read, so it is free.
5. **Write it.**

   ```
   #dial power_bunts 4 1 8 0.5 Bunt power x
   set  power_bunts MLB_MOD_POWERBUNTS 0
   site power_bunts main 1676838 bd004a61 $power_bunts:s2 1e220821 bd004a61
   ```

   `$power_bunts:s2` loads the dial into `s2`, `1e220821` is `fmul s1, s1, s2`, and the original store comes last.
6. **Prove it.** Rebuild, bunt, and read `logs\mlb.log`: `Hit Type: BUNT` followed by
   `AutoHit::m_fPowerMPH`. Code Mods shows the same thing under Last game, and counts how often your code ran.

A patch that only swaps a number needs no dial: give the new instruction word in place of the old one.

## Finding more

The game writes a running commentary into `<game>\logs\mlb.log` while you play: every pitch's movement, every
swing's aim error, every hit's type, power, spin and the air density it flew through. That log is the quickest
way to prove a code mod did what it was meant to, and Code Mods reads it for you after a game.

The game still has its debug text, and that is the way in. Search the strings in `main` for something that
describes what you're after ("Broken Bat Chance", "Slider settings adjust fatigue"), find the code that prints it,
and the numbers being printed are being computed a few instructions earlier. Numbers aren't stored as data: the
game builds them with `movz`/`movk` and `fmov`, so a constant like 1.4667 can be searched for as the instruction
that makes it.
