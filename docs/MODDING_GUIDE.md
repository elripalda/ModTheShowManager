# Modding MLB The Show 26 (PC recomp)

How the game's files work, how to find what you want to change, and how to change it with Mod the Show Manager
or by hand. The second half is a format reference for anyone writing their own tools.

## The basics

The recomp reads the game's files loose from `game\romfs`. Nothing is packed, so changing the game means
changing files in there. The manager never edits your mods into the originals blindly: it keeps a backup in
`mod-backup` and puts everything back with **Restore Original Game**.

A mod is a folder in `<game>\mods`:

```
mods/My Mod/
  mod.json                                          name, author, description
  textures/<pack path>/<texture name>.png           replaces one texture inside a .TEX pack
  romfs/<path>                                      replaces a whole file
```

Mods lower in the list win when two touch the same thing. Apply builds the changed files, Restore undoes it.
Share your own work only, never the game's original files.

## Where things are

Everything the Switch build loads is under `romfs/NSW`. The `AND`, `PS4`, `PS5` and `CROSS` folders are other
platforms' leftovers (CROSS/LIVE does hold the card art as WEBP files).

| Folder | What's in it |
| --- | --- |
| `NSW/UNIFORMS/<AL or NL>/<team>/<slot>/` | One team uniform: `UNIFORM.TEX` (jersey, sleeves, letters, numbers), `PANTS.TEX`, `CAPHELMET.TEX`, `DECALS.TEX` |
| `NSW/STADIUMS/<park>/` | `TEXTURES_COLOR.TEX` holds most signs and surfaces; `PROPS/` holds every prop model with its own `.TEX` |
| `NSW/OBJECTS/` | The game bat (`G4GAMEBAT.MOD`), bat finishes (`G4BATTEXTURES.TEX`), bat skins (`BATSKINS.TEX`) |
| `NSW/CHARACTERS/MASTERFILES/` | Bodies, gloves, jerseys, pants and the shared gear texture packs |
| `NSW/CHARACTERS/ACCESSORIES/` | Shoes, elbow guards, eyewear, wristbands |
| `NSW/CHARACTERS/HEADS/<player>/` | Hair (`_G5_H`), eyebrows (`_G5_EB`), facial hair (`_G5_FH`) and the face textures |
| `NSW/UI/GAME/` | Scorebug themes (`THEME1-4`, `THEMEMOMENTS`) and the broadcast graphics (`PRES/`) |
| `NSW/UI/ART/ACTIONSHOTS/` | The player action shots used in menus |
| `NSW/CREATEUNIFORM/` | The uniform creator's fonts, patches and templates |
| `NSW/AUDIO/` | Sound banks (`.BNK`), streams (`BANK_STREAMS`), commentary and music archives (`.SKX`) |

Team codes are the usual three letters (`ARI`, `NYY`, `LAD`...). Uniform slots are `HOME`, `AWAY`, `ALT1`,
`ALT2`, `CC1H` (City Connect) and so on. Park folders use the team code or a short name for other parks.

## Finding things

- **Search Game Files.** Every file in the game is listed and searchable. Texture packs open as a grid.
- **Texture names give it away.** Colour textures end in `-color` or `_basecolor`, glow maps in `_emissive`,
  the rest are normal, roughness and metal maps you can usually leave alone.
- **Ask the model.** Open a model in 3D Models and its material names the textures it uses. The manager finds
  the pack for you and shows the texture on the model.
- **Player gear takes its textures from the uniform.** Jerseys and pants are blank models; the colours come
  from the team's slot folder. That's why the Uniforms page can dress a mannequin in any team.
- **Night games need both.** A sign's colour texture and its `_emissive` partner both need changing, or the
  old ad glows through after dark.

## Textures

Open the texture, **Export PNG**, edit it at the same size, **Replace With PNG**. Mip levels and the loading
preview are rebuilt for you. A few things to know:

- **Uniforms use alpha as a mask**, not transparency. The real colour is in RGB; alpha marks lettering and trim.
  Export gives you the colour PNG plus a `_mask.png`. Bring back an opaque PNG and the game's mask is kept.
- **Higher resolution.** Bring back a PNG that is exactly 2x, 4x or 8x the original (a 2048x1024 jersey as
  4096x2048, up to 8192 on a side) and it goes in at that size, laid out the way the game's own large textures
  are. Any other size is fitted to the original.
- **Bats use alpha as paint zones.** On `bat-color` style textures, alpha 17 is the handle, 51 the barrel and
  0 the logo area. The game paints each player's bat colours into the zones, so a recolour only shows where
  alpha is 0. Clear the alpha if you want your colour everywhere.
- **Formats:** BC1, BC3, BC4, BC7 and RGBA import fine. Stadium props use ASTC 6×6, which the manager can show
  and export but not import yet.

## Models

Models are two files: `NAME.MOD` (the description) and `NAME.0.MOD` (the geometry). Some have more LOD files
(`NAME.1.MOD`, `NAME.2.MOD`).

What you can do today in **3D Models**:

- **View** any bat, ball, prop, shoe, glove, jersey or body with its textures.
- **Export OBJ** for Blender.
- **Replace a mesh** on static models (bats, balls, props) with your own OBJ, of any size.
- **Scale or hide** a mesh.
- **Bat Shapes** reshapes every bat at once (Wiffle, Big Barrel, Fungo) and keeps the textures lined up.

For a custom model: export the original first, build over it in Blender so size and axes match, then export
with the same axis settings and tick **Fit imported OBJ to the original mesh size**.

Skinned models (players, gloves, cloth) open and export but can't be replaced yet. They're tied to the skeleton
and carry progressive LODs and cloth data that a swap has to rebuild.

## Sounds

**Sounds** lists every audio file, and all of it plays and exports as WAV. The crowd and reaction streams
(`.XVAG`) and most of the commentary, PA and music archives (`.SKX`) use Sony's SADPCM, which the manager decodes
itself. Sound banks, AT9 files and the few ATRAC9 clips inside archives go through vgmstream. Pick an archive and
its samples are listed by name; tutorial lines show what is being said.

## The Mods list

Filter the list by kind with the chips on top (Uniforms, Scoreboards, Stadiums, Code…). Right-click a mod, or
double-click it, for **View Changes**: everything it touches, grouped by kind and team. **Remove** takes a mod off the
list and sends its files to the Recycle Bin. **Remove…** at the bottom clears the switched-off ones, or all of them
with the original game put back. Code mods only ever hold code: anything else you edit goes to the mod for its kind.

## Scorebug layout

The editor has three parts. Along the top: which overlay you are working on, the look to start from, and saving.
On the left: the screen, with a pretend game and playback under it. On the right: the settings, grouped by what
they change.

Making a whole look of your own, from the sandbox or from Photoshop: [Designing your own scorebug](SCOREBUG_DESIGN.md).

**Scoreboards › Layout** draws a theme's overlays (the scorebug, the bottom ticker, transitions) the way the game
lays them out, with their real textures. Drag the red box or type X and Y to place one, then save. The layout file
(`NSW/UI/GAME/THEMEn.NSW`) goes into your mod with only what you changed. Scale is there too, but not every theme
honours it yet.

Click any piece on the screen to edit just that piece, or pick a texture under **Its textures** on the right to change every
place the overlay draws it. **Colour** tints, **Opacity** fades, **Move X / Y** shift, **Size** scales, **Hide**
takes it off and **Replace PNG** repaints it. **Back to Default** undoes all of it.

The **Game** row under the screen is a pretend moment of a game: teams, score, inning, count, outs, runners. Change it and the
overlay redraws the way the game would show it, because the manager reads the same rules the game does (below).
**In play / Scene** picks which big piece is up (the scorebug, or the team panels the game shows between innings),
and the pop-up list fades in the panels that come and go: the batter bar, a home run, a strikeout. The switch list
under it still lets you force any single part to any look; **Follow the Game** hands them back.

Type a team's abbreviation (`SD`, `HOU`, `TOR`...) and the preview uses that team's own logo from the game and its
colour. The same sandbox opens the presentation screens under **Broadcast Presentation**: starting lineups, the
matchup, due up, lower thirds.

**Show animation layers** adds the glows the game flashes in. **Zoom in** fills the view with the overlay. Theme 1
is checked against the game; themes 2 to 4 draw but still have rough spots.

The **Animation** row lists the moves the game plays on the overlay: the batter bar sliding in, the bars going
away, a score rolling over. Pick one and drag the slider to step through it, or press **Play**. Moving, resizing or
hiding a piece carries its animation with it, so a piece you moved still slides in at its new spot.

**Import Font…** also lists six open-licence fonts that come with the manager (Bebas Neue, Anton, Oswald,
Graduate, Share Tech Mono, VT323).

**Styles** (top bar) starts you from a whole look. **Classic Line**, **Line Score**, **Team Tiles** and **Glass
Tiles** are scorebugs built from nothing, **New Blank Design** starts your own and **Open a Design File…** loads one
([how they work](SCOREBUG_DESIGN.md#building-one-from-nothing)). **Wide Top Bar** turns Theme 1 into one strip across the top
of the screen. **Split Bar** puts the teams at either end with the game state between them and mirrors the home
side. **Glass Bar** is the same shape as three floating tiles of smoked glass, each team tinted its own colour. **Save as Style…** keeps whatever you have built as its own small mod called `Scorebug: <name>`: it
shows in the Styles list to come back to, and in the Mods list to switch on or share. A style holds only what
differs from the game's layout, plus any pieces you repainted.

Click a text box and **Its text** appears on the right: **Font** (every game font, shown as a sample), **Text size**, **Left /
Centre / Right** and **Outline Colour**. The letters themselves take the normal **Colour** button.

**Import Font…** draws a font file of your own (`.ttf` or `.otf`) into the game in place of the font the clicked
box uses. It takes that font's cap height, so boxes keep their size, and it covers the accented letters. Every
text box that uses the font changes with it, menus included. About five imported fonts fit at once.

The same edits can go in a layout recipe, so a scorebug style can be shared without the layout file:

```json
[{"file": "NSW/UI/GAME/THEME1.NSW", "asset": "Scorebar", "x": 40, "y": 838,
  "pieces": [{"texture": "esl", "opacity": 0},
             {"texture": "circle_32x32", "color": "#ffb000", "size": 1.2, "dx": 2, "dy": 0}]}]
```

A recipe can also recolour an overlay by the colours the game paints it with. `texture` narrows a rule to pieces
drawing that texture (`""` for plain ones) and `kind` to `image` or `text`. It reaches the overlays the scorebug
shows too:

```json
[{"file": "NSW/UI/GAME/THEME1.NSW", "asset": "Scorebar",
  "colours": [{"from": "#cecece", "to": "#18202e"},
              {"from": "#252c34", "kind": "text", "to": "#ffffff"},
              {"from": "#ffffff", "texture": "gradient_vertical", "opacity": 12}]}]
```

The Midnight, Brick & Sand and Flat White samples are built this way.

Text boxes can be restyled the same way, all at once or only the ones using one font:

```json
[{"file": "NSW/UI/GAME/THEME1.NSW", "asset": "Scorebar",
  "text": {"size": "x1.2", "font": 10, "color": "#ffffff", "only_font": 9}}]
```

`use` in a piece draws another texture of the same pack in its place.

A saved style is a recipe too. `runs` are the bytes it changes, `of` the SHA-1 of the layout it was made from, so
it is refused on a game version it doesn't fit. It starts from the game's own layout, not from other scorebug mods:

```json
[{"file": "NSW/UI/GAME/THEME1.NSW", "of": "3f1c…", "runs": [[10468, "0000ae43"], [10484, "0000dc44"]]}]
```

## Jersey builder

**Uniforms › Builder** changes a uniform without an image editor. Pick a part (jersey, sleeves, undershirt, pants,
socks, cap, helmet), click one of its colours to swap it everywhere on that part (trim and piping are colours
too), add pinstripes, and put as many PNG logos on it as you like, each with its own place and size: chest, back,
sleeve. **Sharpness** builds the part at 2x or 4x the game's size so logos and stripes stay crisp up close. **On the Player** shows every part you've touched on the mannequin before you
save. **Save to My Mod** writes them as ordinary PNGs in your mod, so they can still be edited by hand.

It works by colour: the most common colour is the fabric, and trim keeps its soft edges when it changes.

## Uniform schedule

**Uniforms › Schedule** is the game's own list of when a team wears what (`FRONTEND/UNIFORMS/MLBUNIRULES.JSON`):
home or road, jersey, pants and cap, which days, day or night, a date window and a chance. **Uniform List** edits
`MLBUNIS.JSON`: names, and whether a uniform shows up in the picker.

## Teams, players and faces

**Teams & Rosters** reads `FRONTEND/STATS/ROSTERS.BIN` (teams) and `PLAYERS.BIN` (players and ratings). Rename a
team, fix a player's name, position or ratings, or move him to another club. Saves patch the `_LIVE` and `_INJ`
copies too.

**Import / Export** turns a team into a JSON file and reads one back: see [roster files](ROSTER_FILES.md). A name
the game doesn't have takes over a spare player with a built face, so a classic roster never puts a new name on a
real player's scanned head. **Tools › Auto Lineup** fills a team's lineups from whoever is on it.

The **Face** tab shows the player's face texture from `NSW/CHARACTERS/HEADS/<LAST_FIRST>/`. Players with the
same name get a letter on the end (`BELL_JOSHE`). Young players without a scan use the generic creator faces.

Each player also has a **Gear** tab (bat, grip, batting gloves, glove, cleats, guards, sleeve, eyewear, catcher
gear) and his jersey number, height and handedness. Moving a player takes him out of his old team's rotation and
lineups and puts him on the new team's bench or in its bullpen. **Team Builder Names** edits the names and cities
the game's custom team builder offers. **Arcade Rosters** sets ratings for a whole league at once (99 is the normal
top, 125 the boosted one).

## Recipes

A mod can describe a change instead of carrying the changed game file. `rosters/*.json` are
[roster files](ROSTER_FILES.md) and `layouts/*.json` move overlays:

```json
[{"file": "NSW/UI/GAME/THEME1.NSW", "asset": "Scorebar", "x": 40, "y": 838, "scale": 1.0}]
```

They are carried out when you apply. A mod made of PNGs, recipes and code patches has nothing of the game's in
it, which is what [shared mods](../community/README.md) have to be.

## Code mods

**Code Mods** builds instruction patches into `mlb.exe` with the recomp's own tools. A mod carries them in
`code/*.patch`:

```
set  <name> <SWITCH> <default 0/1>
site <set> <main|sdk> <offset hex> <original word hex> <replacement word hex> ...
```

The manager's own code mods are always in the list, and **Make Your Own** writes a commented starter file. Exit
Velocity multiplies a hit's power right before the game turns it into the ball's speed (`main+167d0b8`), and Air
scales the air density the game works out from a park's temperature and altitude (`main+165ac78`).

Rebuild Game runs the recomp's generator and build (about two minutes) and keeps your old exe as
`mlb.original.exe`. After that every code mod can be switched, and its dial turned, in Code Mods or in the game
with F4, without rebuilding. The manager reads the game's own code (`game/exefs/main`) first and leaves out any
set made for a different game version.

[Code mods](CODE_MODS.md) has the full list, how to write your own, and a map of the gameplay code found so far.

## Replacing sounds

Stream files (`.XVAG`) have **Replace With WAV**. Your WAV is resampled to the original's rate, matched to its
channel count and written in SADPCM, the same codec the game's own streams use. Replacing a sample inside an
`.SKX` archive isn't in yet.

## Stadiums in 3D

**Stadiums › 3D View** draws the park's `SCENE.MOD` with its textures. Orbit around it, or switch to Fly Through
and walk around with W A S D (Q and E for down and up). Hide Roof opens up covered parks.

## Not cracked yet

- Layout animations. The tree, the looks, the rules that pick them and the text are read; the keyframes aren't,
  so which pop-up is up at a given moment is picked by hand in the sandbox.
- Head meshes. The `HEADS` folders hold hair and eyebrow models plus the face textures; the head shape is built at
  runtime.
- Saves. A fresh profile only holds settings (`profile/save/<id>/SETT...`) and a marker (`PLYA...`); franchise and
  Road to the Show saves haven't been looked at yet.
- Scanned-head links. A player with a scan has `HEAD_SHAPE` 0 and an empty `APPEAR_VALUES` in `D_PLAYER_APP`;
  what ties him to his `HEADS` folder (the name or `PLAYER_ID`) isn't confirmed, so the manager never renames a
  scanned player into someone new.
- More gameplay. Hit speed, air density, aim error, perfect contact, bat breaks and fatigue are mapped
  ([code mods](CODE_MODS.md)). Runner speed, pitch speed and fielding aren't yet.

---

# Format reference

All values are little-endian.

## TX12NSW texture packs (.TEX)

Header 0x20 bytes: magic `TX12NSW\0`, then sizes. After it, one 0x140-byte entry per texture, then the data.

| Entry offset | Field |
| --- | --- |
| 0x10 | name (64 bytes, NUL padded) |
| 0x60 | total size; 0x64 width (u16); 0x66 height (u16) |
| 0x6C | mip count |
| 0xB0 | preview descriptor (0xC4 width, 0xC6 height) |
| 0xD0 | up to 4 chunk records of 0x14: unpacked size, packed size, offset from payload, unpacked offset, flags (byte 1 first mip, byte 2 mip count) |
| 0x120 | average colour |
| 0x130 | flags; 0x134 payload offset |
| 0x13C | pixel format (u16) |

How the levels are split into chunks: each of the first two levels gets a chunk of its own when it is 64 KiB or
more, and everything smaller shares the last one. A record with a slot above 0 that starts at level 0 is the small
loading preview. Every texture in the game follows this, which is what lets a texture be made larger.

Chunks up to 2 MiB are one LZ4 block. Bigger ones (the font sheet, a few card animations) are 512 KiB blocks in a
row, each led by its packed size and allowed to reach back 64 KiB into the block before it.

Pixel formats: `0x16` BC7, `0x07`/`0x06` BC3, `0x0D` BC1, `0x13` BC4, `0x02` RGBA8, `0x05` BC1 (UI normals),
`0x59` ASTC 6×6. Chunks are LZ4 block compressed and Tegra X1 block-linear swizzled (GOB 64 bytes × 8 rows,
block height from the height in blocks). Big textures split into chunks: mip 0, mip 1, the rest, then a small preview.

## IFF0MODL models (.MOD + .0.MOD)

Both files are chunk lists: 8-byte tag, u32, u32 size; the next chunk starts at offset + 0x10 + size.

`NAME.MOD` (description):

| Chunk | Contents |
| --- | --- |
| `CLAS_VBO` | one 0x40 record per vertex buffer: count, buffer index, stride (high 16 bits = layout index) |
| `CLAS_EBO` | index buffers (16-bit) |
| `STRGINLA` | the vertex layouts as XML (`<InputLayout>`, one per layout) |
| `STRGDGRP` + `INT0DGRP` | mesh names; group records of 0x10 (mesh count, first mesh) |
| `VOIDDNFO` | per mesh: box min, box max, sphere centre, radius (10 floats) |
| `STRGTEXN` | texture names |
| `VOIDPRMS` + `INT0MREF` | material parameters (0x28 each; type 0x12345 = texture, value = index into TEXN); one MREF per mesh (hash, count, first parameter) |
| `INT0DRBL` + `VOIDDRBL` | mesh records |

Mesh record: +0x0C vertex count, +0x28 stream count (u16), +0x2A offset of the stream blocks, +0x2C offset of the
LOD index table. Each stream block is 0x18 bytes with the first vertex at +4. The LOD table holds (index count,
first index) pairs; entry 0 is full detail. Per-stream records start with `0x14` and hold the stride × 8 at +6,
which is how a mesh's layout is found in files with several layouts.

`NAME.0.MOD` (geometry): `VOID_PAD`, `CLAS_VBO`, then `VOID_VBO` per buffer and `VOID_EBO` per layout. Buffer data
starts on a 256-byte boundary. Vertex data is followed by 1-16 zero bytes, index data by 0-15, then `0xAD` up to
the next chunk.

Common attribute formats: `kFloat_16`, `kFloat_32`, `kFP_1_0_9` × 3 + `kFP_0_0_2` (packed 10:10:10:2 normals and
tangents), `kFP_0_0_8` (unorm8), `kUInt_8` (bone indices). The bat stores its length axis in position.w.
`kSInt_Compressed` (progressive mesh tables) isn't decoded.

## Audio

- `.AT9`: RIFF WAVE, ATRAC9 (GUID `d242e147-ba36-8d4d-88fc-61654f8c836c`), 48 kHz.
- `.XVAG`: `XVAG`, u32 offset of the audio, then chunks. `fmat`: channels, codec, samples (twice), a block
  count, sample rate at +0x1C, audio size at +0x20. Codec 0x0E is SADPCM, 0x09 ATRAC9.
- SADPCM: 96-byte frames, 168 samples of one channel each; channels take turns frame by frame. A frame is four
  u32 group headers and 80 bytes of 4-bit codes. A header holds the group's second sample (bits 0–11) and first
  sample (bits 12–23), both signed 12-bit and worth 16x in 16-bit terms, a filter (bits 24–27) and a shift
  (bits 28–31). Codes are read high nibble first; nibble *k* belongs to group *k* mod 4, so the four groups are
  woven together and each gets 40 codes, 42 samples with its header pair. The groups follow each other in time.
  Each new sample is `k0 * s[n-1] + k1 * s[n-2] + (code << shift)` with code a signed nibble. The 16 filters
  (`k0`, `k1`): (0, 0), (0.9375, 0), (1.796875, -0.8125), (1.53125, -0.859375), (1.90625, -0.9375), then those
  four halved, then (0.234375, 0), (0.44921875, -0.203125), (0.3828125, -0.21484375), (0.4765625, -0.234375),
  (0.5, -0.234375), (0.234375, -0.234375), (0.109375, -0.234375). The game's decoder is at `main+1b4ab80`, the
  table at `main+1df27a0`.
- `.SKX` + `.TBL` + `.KEY`: an archive of XVAG clips. `.TBL` (`STBL`): sample count at +8, sector size (u16) at
  +0x18, then 6-byte records from +0x64: u32 sector, u16 kind. Kind 0x0100 is a pause in milliseconds, anything
  else a clip at sector x sector size (some archives count from the end of the first sector). `.KEY` is XML:
  one `SAMPLEFILE` per record with its name and, for spoken lines, the script.
- In `PLAYERS.BIN`, `D_PLAYER_ACC` holds gear as the item's `style` from `FRONTEND/EQUIPMENT/MLBEQUIPMENT.JSON`.
  `UNSIGNED_PACK` bits: height 9–15 (inches), bats 23–24 (R, L, S), jersey number 128–134 and again 135–141.
  `SIGNED_PACK` bit 30 is throws left. `ROSTERS.BIN` `D_ROSTER_HLPR.PLAYER_NUMS` is 95 u32 slots of player
  number + 1 (0–4 rotation, 5 closer, 6–29 bullpen, 30+ position players); `D_LINEUP` maps positions to slots.

## Stats databases (LE90)

`ROSTERS.BIN`, `PLAYERS.BIN`, `STATS.BIN` and friends start with `LE90`, then `[DESC]`: table name (16 bytes),
u32 size, u32 field count, then 32-byte fields (name 22 bytes, id, type, count, byte size, pad). `[DATA]` follows:
table name, u32 record count, records in DESC field order. A record can own child tables (a player owns his
contract, animations, audio, flags, quirks and stance). In `PLAYERS.BIN`, byte 0 of `SIGNED_PACK` is the team
index from `ROSTERS.BIN` (255 = free agent), and `PLR_ATT` holds ratings in the same player order. `STATS.BIN`
keeps 28 career rows per player.

## UI layouts (IFF0ASSH)

One `VOIDASS0` chunk per asset (tag, name hash, size). The body starts with 13 u64 section offsets; section 0 is the
node tree. Every node starts with the same 0x2C bytes:

| Offset | Field |
| --- | --- |
| 0x00 | colour, bytes R G B A; it multiplies down the tree and alpha 0 hides a node and everything under it |
| 0x04 | x, y, z, width, height (floats, 1920×1080, x and y relative to the parent) |
| 0x1C | rotation (s16) |
| 0x1E | anchor flags (0x20 a second set for another screen mode) |
| 0x22 | scale x, scale y (u16, 0x80 = 1.0) |
| 0x26 | kind (low 6 bits; the top two flip the picture) |
| 0x27 | flags: 0x20 additive, 0x80 hidden until an animation shows it |

Where a node ends depends on its kind; the game's own table is at `main+0x7e61d0`. A node that holds others keeps
them packed between the end of its fields and its end, so groups clip what they hold.

| Kind | What | Ends at | Holds nodes from |
| --- | --- | --- | --- |
| 0x0F | group | +[0x48] | +[0x38] |
| 0x18 | image: texture hash at +0x30, a second (mask) at +0x38 | 0x50 | |
| 0x01 | sprite: texture hash at +0x30 | 0x58 | |
| 0x1E | instance of another asset in the file, its hash at +0x30 | +u16[0x50] | |
| 0x1C | switch: look count at +0x70, one u64 offset per look at +0x78 (0 = empty) | +[0x6C] | +[0x48] |
| 0x22 | text box | 0x80 | |
| 0x0C | clip | +[0x48] | +[0x30] |
| 0x19 | flipbook: a list of textures | +u16[0x48] | |
| 0x13, 0x1D, 0x21 | lists and tables | +[0x30] | +[0x38] |
| 0x26, 0x11 | text field, button | +[0x58] | 0x68 |

A group clips what it holds when bit 0x100 of its child count (+0x4C) is set. A switch (0x1C) draws the children
none of its looks name all the time, plus the one look that is picked.

Anchors (+0x1E) say what a piece does when its parent isn't the size it was designed at, which is how one reused
overlay fits Instances of different sizes: bits 0-1 up/down (1 top, 2 bottom, 3 stretch), bits 2-3 across (4 left,
8 right, 0xC stretch), 0xF0 scale in proportion, 0x100 / 0x200 stay centred.

A text box (0x22): the node colour fills the letters and +0x40 is the outline; +0x4C is the id of its words in the
`.LANG` file (0 when code fills it in); +0x58 is its base size and +0x60 the size it is drawn at (u16, 1/16 px,
+0x60 wins when set); +0x70 holds the font number in its low six bits and left / centre / right in bits 18-19. An
image with byte +0x4A set to 1 is a slot the game fills while it runs (a team logo).

The file opens with a directory. At 0x0C is the file's size, at 0x10 the number of tables and at 0x18 where
their headers are. A header is (count u32, type u32, offset u64) and a table is rows of (asset hash u32, 0, chunk
offset u64) sorted by hash. Offsets inside an asset count from its own body, so an asset can be copied to the end
of the file under a new name as long as the directory gets a row for it. A saved style lists such copies as
`"clones": [["dc303b63", "MTS_TeamRow_Mirrored"]]`.

An asset's header continues after the 13 section offsets: at +0x6C the end of its strings, +0x70 how many
children the root has, +0x72 how many animations, +0x7C how many named animations, +0x82 how many triggers, +0x84
the screen it was drawn for (1920, 1080). Section 7 names the animations: rows of (name hash u32, 0, offset of the
animation's entry u64) sorted by hash. Queries need no section of their own. A query is a record (offset of its
token list u64, token count u64) anywhere in the body, and small assets keep them straight after section 7.

An image whose byte +0x4A is 1 keeps a query at +0x30 instead of a texture: `[ UI LOGO [ team , kind ] ]`. A copy
of another asset (0x1E) has the asset's hash at +0x30, its size and argument count as two u16 at +0x50, and one
query pointer per argument from +0x58. A switch (0x1C) has its query at +0x30, its size at +0x6C, its number of
looks at +0x70 and one offset per look from +0x78. `uibuild.py` writes all of these from a design file.

A group can carry a colour query at +0x40. `[ UI CAP_TEAM_CLR [ team ] ]` is a team's colour (add `, 1` for its
second one), and the plain art inside the group is drawn in it. This is how the team rows, the batter bar
(`OFF_TEAM_ID`) and the pitcher bar (`DEF_TEAM_ID`) get their colours. `QCOMP [ a , == , b ]` answers 1 or 0 and
`IF_Q_ELSE_INT [ test , x , y ]` picks between two answers, so a switch can ask anything.

Section 3 holds what an asset does when it appears: records of (commands offset u64, node u64, flags u64), counted
at +0x74, each pointing at 16-byte commands. Command 0x82A with an animation entry's offset plays it.

Animations are section 1 of an asset: 16-byte entries (tracks offset u64, track count u16, length in frames u16).
A track is 24 bytes (channels offset u64, the node's offset in the body u64, 0xFFFF, last frame u16, channel count
u16). A channel is 16 bytes (keys offset u64, last frame u16, key count u8, property u8: 0 x, 1 y, 7 width,
8 height, 11 alpha). A key is 8 bytes: frame u16, then the alpha byte at +2 or a float at +4 (with an easing number at +3: 6 on a
key that eases toward the next, 1 on the last). Keys hold the piece's
real position, not a nudge from it, so a piece moved without its keys jumps back when the animation plays.

Section 8 names them. Its 24-byte entries (pointer u64, name hash u32) lead to a list of 16-byte commands (op u16,
pointer u64 at +8): 0x2A plays an animation, 0x35 stops one, 0x3A sets a value, 0x3B is a conditional.

## Layout logic: queries

What picks a switch's look, what a reused overlay is handed, and what fills a live text are all the same thing: a
list of tokens, each a name hash or a small number, stored last word first. Read backwards they are bracketed
queries in the game's own words:

```
[ SCOREBAR OUT_TAB ]                       outs, picks the look of the outs lights
[ SCOREBAR 1ST_BASE_TAB ]                  runner on first
[ IG BALLS ]  [ IG STRIKES ]  [ IG IS_BOTTOM ]
[ SCORER AWAY_SCORE ]  [ AWAY_TEAM TEAM_PROF SHORT_NAME ]
[ SCOREBAR SPEED ]  [ PITCH_BAT_STATS PITCH_COUNT ]
[ UI TEMPLATE_QUERY_INX [ 2 ] ]            the third thing this copy of the overlay was handed
[ IF_Q_ELSE_INT [ QCOMP [ a , == , 6 ] , x , y ] ]
```

A switch keeps the offset of its query at +0x30; an Instance (0x1E) lists one per argument after +0x58 (count at
+0x52). Both point at (offset, token count) pairs in the asset body. `src/modtheshow/assets/querynames.txt` lists
the 1,500 words layouts use; `uiquery.py` reads, writes and answers them.

## Layout text (.LANG_EN)

Beside each layout. Two tables: fixed words (id, string) and live text (id, string, bindings). Live strings carry
`^d0^ ^d1^` slots, each bound in order to a query, plus marks: `^n^` new line, `^sNN^` size, `^fNN^` font, `^cN^`
colour, `^bN^` a button picture. The count is `^d0^-^d1^` bound to `[ IG BALLS ]` and `[ IG STRIKES ]`.

To add text, a `.LANG_EN` file takes new rows in either table as long as the tables stay sorted by id and every
offset after them moves down. In a live entry each binding's second u64 holds the token count in its low 16 bits
and, above that, how many more bindings follow.

## Fonts (FONTS.NSW + FONTS.TEX)

`NSW/UI/ART/FONTS/FONTS.NSW` is one layout asset holding a font table: 0x30-byte font records from +0x40 of the
body (39 fonts; +0x20 the letter sheet's name hash, +0x28 the glyph table). Each glyph table is 124 records of
0x28 bytes: the character as its UTF-8 bytes (first byte lowest), u0 v0 u1 v1 on the sheet, width and height with
4 px of padding, then bottom (up from the baseline), left and right bearing. The letters live on the 4096×4096
"english" sheet in `FONTS.TEX` as signed distance fields in alpha, edge at 0.5. The bottom quarter of the sheet is
free, which is where imported fonts go.

Names are stored as a 32-bit hash: start at 0; for each character of the lower-cased name, rotate left 8 bits and
XOR the character in; set the top bit at the end. In Python:

```python
def name_hash(name):
    h = 0
    for c in name.lower().encode():
        h = (c ^ ((h << 8) | (h >> 24))) & 0xFFFFFFFF
    return h | 0x80000000
```

An asset's id is the hash of its name (`PBInterface\ScoreBar` is `F3657054`), a texture's is the hash of its name
in the `.TEX` pack beside the layout, and animations are looked up by the hash of an action name
(`ACT_SCOREBAR_OFF`, `ACT_BATTER_BAR_IN`, `ACT_PITCH_CLOCK_ON`...). The game's own function is at `main+0x18a23e0`.
- `.BNK`: Sony Scream bank, `SBlk` at 0x20, bank name at 0x40.
- `.SKX` with `.CTL` (`SCTL`), `.TBL` (`STBL`) and `.KEY` (XML sample list).
