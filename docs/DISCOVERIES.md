# What we've found

How MLB The Show 26 (the Switch build the PC recomp runs) is put together, in short. Each part links to the
full details. Everything here was worked out from the game's files and code, on game version 1.0.15.

## The files

The game is about 84,000 loose files under `game/romfs`, listed in `game/romfs_list.tsv`. Switch-specific art
sits under `NSW/`, shared data under `FRONTEND/` and `CROSS/`. Nothing is packed into one big archive, which is
why mods can swap single files.
[Where things are](MODDING_GUIDE.md#where-things-are)

## Textures

`.TEX` files are packs (`TX12NSW`) holding many textures each, LZ4-compressed, in BC1, BC3, BC4 and BC7 with
their mip levels. The manager rebuilds a texture in the same format when you replace it, so the game can't tell
the difference. Alpha in most game textures is a mask (team colour, paint zones), not transparency.
[Format](MODDING_GUIDE.md#tx12nsw-texture-packs-tex)

## Models

A model is two files: `.MOD` describes the meshes and `.0.MOD` holds the geometry. Positions, normals and UVs
are packed (half floats, 10:10:10:2 normals). Bats, balls and props can be exported and replaced. Players use
progressive meshes and cloth data that aren't fully decoded, and heads are built at runtime from a shape plus
the textures in `HEADS`.
[Format](MODDING_GUIDE.md#iff0modl-models-mod--0mod)

## Sound

The crowd, reactions, commentary, PA and music all use Sony's **SADPCM**, a codec we couldn't find documented
anywhere. We
found the game's own decoder in the code and its table of 16 filters, and wrote a decoder and an encoder from
it. That's why every stream plays in the manager and why a replacement WAV goes back in the game's own format.

- A frame is 96 bytes and holds 168 samples of one channel.
- Inside it, four groups of 42 samples are woven together nibble by nibble.
- Commentary archives (`.SKX`) are clips back to back; a `.TBL` file says where each starts and a `.KEY` file
  names them and, for spoken lines, has the script.

[Format](MODDING_GUIDE.md#audio)

## Teams and players

`FRONTEND/STATS/ROSTERS.BIN` and `PLAYERS.BIN` are small databases (`LE90`): a description of every table, then
the rows. Teams, lineups, rotations, ratings, gear, jersey numbers, height and handedness are all in there at
fixed sizes, so they can be edited in place.

- A team's roster is 95 slots: 5 starters, a closer, 24 relievers, 65 position players.
- Each team has five lineups, with and without a DH.
- Ratings are one byte each. The game shows 99 as the top but accepts up to 125.
- A player with a scanned face has `HEAD_SHAPE` 0; everyone else has a built face made from sliders.
- The legends (Ruth, Gehrig, Mays...) are in the database as free agents.

[Roster files](ROSTER_FILES.md) · [Format](MODDING_GUIDE.md#stats-databases-le90)

## Uniforms and schedules

Which uniform a team wears on which day is a JSON file with rules per team: home or away, day of week, day or
night, a date range and a percentage. A second file names the uniforms and decides which show in the picker.
[Uniform schedule](MODDING_GUIDE.md#uniform-schedule)

## Screen layouts

The scorebug and other overlays are `.NSW` layout files: a tree of groups, images, text boxes, switches and
copies of other overlays, each with a position, size, colour and scale. The whole tree reads now, using the same
rule the game uses for where each kind of piece ends, so the manager draws a scorebug with its real art and every
piece can be clicked and changed. Everything in them is named by a hash: rotate left eight bits, XOR the next
lower-case letter in, set the top bit. It names each texture, each overlay and the animations the game plays on
them (`ACT_SCOREBAR_OFF`, `ACT_BATTER_BAR_IN`...).
[Layouts](MODDING_GUIDE.md#ui-layouts-iff0assh)

## How a scorebug moves

Each overlay carries its own animations: which piece, which property (x, y, width, height, alpha) and a few
keyframes. The scorebug has 75, and the game starts them by name: `ACT_BATTER_BAR_IN`, `ACT_PITCHER_BAR_OUT`,
`ACT_EXIT_VELO_ON`. The keyframes store where a piece actually sits, which is why a piece moved by hand used to
snap back the moment it animated. The manager now moves the keyframes with the piece, and can play any of them.
[Animations](MODDING_GUIDE.md#ui-layouts-iff0assh)

## Team logos and the rest of the broadcast

Every team's logos sit in five packs, `NSW/UI/ART/TEXTURES/LOGO1.TEX` to `LOGO5.TEX`: a wordmark, a flat primary,
a tile and two large ones, each named `logoN_<abbreviation>`, with a `_cc` copy for City Connect. The minor
leagues, national teams and colleges are in there too. The starting lineup, matchup and lower-third screens are
layouts in `NSW/UI/GAME/PRES/PRESOSDSn.NSW`, the same format as the scorebug. The transition wipes are not: they
are Bink videos under `CROSS/MOVIES/PRESENTATION`.

## Where team colours come from

Nothing on the scorebug has a team's colour painted in. A group of pieces carries a question, `UI CAP_TEAM_CLR`
with a team, and the game draws the plain art inside it in the answer. The batting team's colour reaches the
batter bar that way and the fielding team's the pitcher bar. A design of your own asks the same question, and can
ask "is this club number ten?" first to swap in a colour of its own. The game does that itself in one place: its
player card asks whether the team is number ten and, if so, takes the second colour.

The colour is the cap's, so it follows the uniform. `UI ACTUAL_TEAM_CLR` is the club's fixed colour and
`TEAM_UI IS_CITY_CONNECT_ACTIVE` says whether a team is in City Connect. No query names any other uniform.

What makes a uniform City Connect is its `unitype` in `MLBUNIS.JSON`: 2 for City Connect, 3 for a throwback. Each
club has one uniform of kind 2, and a club's older City Connect set is filed as a throwback. Change a jersey's
kind to 2 and it should get the City Connect treatment.

## A table row is just a number

The game's lineup screen is a table: one row of text boxes, repeated, each asking for "the batter in this row".
The row is a query of its own, `UI PARENT_TABLE CELL_ROW`. Write a plain number where that query stood and the same
question works outside a table, which is how a card built from nothing lists all nine batters.

## Stadium boards are layouts

Every park's scoreboards sit in `NSW/STADIUMS/<PARK>/SCOREBOARD/` as a layout, a texture pack and a text file, the
same three as a scorebug theme. `SCOREBOARD.SCR` beside them is plain text: each block names a sign in the park's
model, the screen drawn on it and the size of the picture. Boards read the same queries as the scorebug, so the
count, the line score and the batter's stats fill in the same way. Their colours are painted in, not asked.
[Layouts](MODDING_GUIDE.md#ui-layouts-iff0assh)

## How a scorebug knows the score

Overlays read the game through small bracketed queries written in the game's own words: `[ SCOREBAR OUT_TAB ]` picks
the outs lights, `[ IG BALLS ]` and `[ IG STRIKES ]` fill the count, `[ AWAY_TEAM TEAM_PROF SHORT_NAME ]` the
abbreviation, `[ SCOREBAR SPEED ]` the pitch speed. They are stored as hashed words, and nearly all of them could
be named from the game's debug text. That is what lets the manager draw a scorebug for any moment of a game, and
it is the hook for custom pieces that still show live data.
[Queries](MODDING_GUIDE.md#layout-logic-queries)

## Fonts

Game fonts aren't font files. All 38 are drawn on one big sheet as distance fields (which is why text stays sharp at
any size), with a table saying where each letter sits. That makes a custom font possible: draw a font file's letters
the same way into the free part of the sheet and point one of the game's fonts at them. Text boxes pick their font,
size and colour themselves, so each box can be restyled.
[Fonts](MODDING_GUIDE.md#fonts-fontsnsw--fontstex)

## The code

The recomp turns the game's code into C when it installs, so gameplay can't be patched in a running exe. Its
builder accepts a table of instruction patches instead, and that's what code mods are.

The game still carries its debug text, which is how the interesting code gets found. So far:

- **Exit velocity** is the hit's power in mph, kept on the hit, times 1.4667. The number on screen is read from
  the same place, so the Exit Velocity mod raises both.
- **Air density** is worked out from each park's temperature and altitude. That's the Coors Field effect, and
  the Air mod. It slows the ball down; it has no part in how pitches break.
- **Pitch break** is spin crossed with the ball's velocity, times a lift number, over its mass. The Pitch Break
  mod multiplies that push. The game aims every pitch, then lets the forces bend it.
- **Pitch speed** goes into the launch in mph. The Pitch Speed mod multiplies it there.
- **The bounce** is the ball's own bounce times the surface's, and the ground slows a rolling ball by a number
  that depends on the surface.
- **A bunt** is made by its own small function with a direction and a power, and filed as hit type BUNT.
- **The PCI** is compared with where the pitch crosses the plate right before contact. Auto PCI moves it onto
  the ball at that moment. The one you see is a separate thing: a spot the batting interface works out from the
  stick every frame, in zone units (0 is the middle, 1 the edge: 0.75 ft across, half the zone's height up) and in
  feet. Auto PCI Visual writes the pitch's spot there.
- **Perfect-Perfect** is two flags set in the hit code.
- **Bat breaks** and **pitcher fatigue** each come down to one number.
- The game tells a human hitter from a CPU one with a single value, which is how a mod can affect only you.

The game also writes what it is doing into `logs\mlb.log` as you play: each pitch's movement, each swing's aim
error, each hit's type, power, spin and air density. That log is how a code mod gets checked.

[Code mods and the full map](CODE_MODS.md)

## Bodies, bats and mascots

- **Body shapes.** Every player carries ten sizes in the players file (`D_PLAYER_APP`): head, neck, shoulders,
  sleeves, spine, collarbone, hips, thighs, glutes and arms, a byte each with 127 or so as the usual build.
  Arcade Rosters sets them for a whole league.
- **Aluminum bats.** The equipment list (`FRONTEND/EQUIPMENT/MLBEQUIPMENT.JSON`) has ten bats marked `mtl=1`,
  the ones Road to the Show uses in college. A player's bat is a style number in the players file, so anyone can
  be handed one, but the list has them at `"enb": 0`, and outside a college game the code that builds a bat
  swaps a switched-off style for the plain wood one (it lets styles 22, 63, 64, 119 and 120 through by number).
  Setting `"enb": 1` on the ten is enough for all of them to show. They use the `bat_college` and
  `bat_collegeRing` shapes in `NSW/OBJECTS/G4GAMEBAT.MOD` and their own skins in `G4BATTEXTURES.TEX`.
- **The ping is a sound bank, not a bat.** The game asks for the same sounds whatever the bat is (`BAT_HIT`,
  `HIT_BALL_NORM`...). A regular game loads `NSW/AUDIO/GAMEFX_EXTERIOR_STADIUMS.BNK`; a high school or college
  game loads `GAMEFX_AMATEUR.BNK`, where the contact sounds under those names are different recordings. The
  Aluminum Bats sample puts the second file in the first one's place.
- **The body is one model** (`NSW/CHARACTERS/MASTERFILES/BODIES/STANDARDMALE/MALEBODY24.MOD`) on 27 bones:
  hips, waist, back, neck, head, and four or six bones a limb. Caps, helmets, gloves and hands are separate
  models attached to it. `BODYMETA_*.XML` beside it lists the attachments.
- **Mascots** (`AND/CHARACTERS/MASCOTS/<TEAM>/<TEAM>_MASCOT_A.MOD`, textures under `NSW`) are built on those same
  27 bones, in the same order. That is what makes a mascot mode thinkable: a player's animations can drive a
  mascot's body.
- **The game's own fire and fireworks** are not particles. A firework is a model whose vertices are animated by a
  texture (`NSW/STADIUMS/PROPS/FW_*.MOD` with its `.XML` and `.TEX`), set off by a park's plain-text
  `EFFECTS.SCR`, and the only cue those scripts take from play is a home run.
- **Drawing your own over the game.** The recomp's overlay will call a mod back once a frame, the ball and the
  camera can be read while the game runs, and the game's world-to-screen sum is short. That is enough to simulate
  your own particles in the game's space and draw them where they belong. The Effects code mods do it;
  [CODE_MODS.md](CODE_MODS.md) has the addresses.
- **The body file is only skin.** Swapping `MALEBODY24.MOD` for a mascot's body took the players' arms away and
  nothing else: the jersey, pants, head and hands are separate pieces laid over it, and the game shows named
  parts of the body file, which a mascot's doesn't have. Mascots as players will have to come from the code that
  puts a player together.

## What the developers left in

- **Debug screens.** The menu file still has them (stats editor, trade finder, roster export and more). The menus
  ask the game whether to show them and the game always says no: the answer is one byte nothing ever sets. Debug
  Menu in Code Mods sets it. The same goes for a second byte that hides unfinished franchise screens.
- **Start-up switches.** The game reads `BOOT/CONFIG_MAIN.TXT` when it starts, or `BOOT/CONFIG_MAIN_USER.TXT` when
  that exists. One switch name a line, `#` for a comment. The shipped file has every switch commented out, but the
  code still asks for about a hundred of them by a hash of the name. `devswitches.py` has the ones known by name.
  The hash: upper-case the name, run the classic ELF hash over it to get `h`, and the result is
  `h * 0x9E3779B7 + ~h * 0x61C88641`.
  Named so far: FastPlay, AIvAI, NoCrowd, NoTips, NoWarmup, NoIdle, CatcherView, NoDOF, FastLoad,
  UnlockedEquipment, DisableUIElem, DisableJumboBink, Tutorial, Pregame, TestStorylines, GameOnly, HRDerbyOnly,
  TrainOnly, GetStadiumData, OpenBetaDemo, Mobile, No_Trophy, NewDevice, ForcePlayGo, Disable_Compression,
  Savedata_Compression_Test. GameOnly, HRDerbyOnly and TrainOnly start the game straight into a match from a data
  file the shipped game does not have.
- **A second game in the files.** The `AND` folder holds the phone version's art, and the code has a Mobile switch.
- **Retro Mode is "Ken Griffey Jr. Mode"** inside, with its own sound banks.
- **Leagues.** Custom Leagues runs on the old online franchise code. Half of its screens have no menu any more
  (draft, free agents, trades by vote, awards, Hall of Fame), and all of it talks to the game's servers.
- **Raids.** Diamond Quest's name in the code, with invites, teams and captains nobody can reach.
- **Retired numbers** are a table in the code: last name, first name, team, number.

## Road to the Show

- **Tokens** are one 16-bit number in the career data, at 0x12c0, and one small function (`44012c`) hands it to
  every screen that shows or spends it. Unlimited Tokens fills it there.
- **Locked equipment** hangs on a developers' byte, read in two places (`6a038c`, `69b5e8`) for the player being
  dressed. Unlock All Equipment answers yes in both.
- Six screens have their own debug readout behind one byte each (trades, contracts, the free agent board, the
  custom team editor and two career screens). Debug Readouts sets them.

## Colleges

The 19 colleges are teams 135 to 153. A college's short name is the key to everything of its own: its logos are
`logo1uni_`, `logo2uni_` and `logo4uni_` plus that name in the three logo packs, its recruiting numbers are its
line in `FRONTEND/RTTS/COLLEGES.XML`, and `MLBUNIS.JSON` points its team number at a home and a road uniform under
`NSW/UNIFORMS/NCAA`. Its two display names are in the roster file. Swap a University (Teams, Tools) changes the
names, logos and uniforms and leaves the short name and the ballpark alone. The long school names on the
recruiting screens are in `COMMON.NSW_EN`, which the manager cannot write yet.

## Stitching on a jersey

A sewn-on logo is in two textures: its colours in `jersey-color`, and in `jersey-normal` its raised shape plus a
shine mask in the alpha. Change only the colours and the old logo stays behind as a glossy ghost. Apply now takes
that out where the logo is gone from the colours, and leaves it where the logo is still there. A mod that brings
its own `jersey-normal` is left alone.

## Still open

- Layout animations (the rules that pick each look are solved; the keyframes aren't).
- What ties a scanned player to his head folder.
- Head meshes; putting a mascot's head and textures on a player.
- Franchise and Road to the Show saves.
- Runner speed, fielding and the pitch speed shown on screen, in the code.
- Taking caps, helmets and gloves off, and building a player the way the game builds a mascot.
- What pulls the outer PCI in on a swing (see Contact in CODE_MODS.md), and the size of the ball.
