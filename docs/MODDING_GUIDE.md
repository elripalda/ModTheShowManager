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

## Scorebug layout

**Scoreboards › Layout** shows a theme's overlays (the scorebug, the bottom ticker, transitions) on a 1080p
screen. Drag the box or type X and Y, then save. The layout file (`NSW/UI/GAME/THEMEn.NSW`) goes into your mod
with only those numbers changed. Scale is there too, but not every theme honours it yet.

Under the screen is a strip of every texture that overlay draws: the frame, the base diamonds, the sponsor logo.
Pick one and the row below it changes that piece everywhere the overlay draws it: **Colour** tints it, **Opacity**
fades it (0 hides it), **Move X / Y** shift it, **Size** scales it and **Replace PNG** repaints it. **Back to
Default** undoes all of it.

The same edits can go in a layout recipe, so a scorebug style can be shared without the layout file:

```json
[{"file": "NSW/UI/GAME/THEME1.NSW", "asset": "Scorebar", "x": 40, "y": 838,
  "pieces": [{"texture": "esl", "opacity": 0},
             {"texture": "circle_32x32", "color": "#ffb000", "size": 1.2, "dx": 2, "dy": 0}]}]
```

`use` in a piece draws another texture of the same pack in its place.

## Jersey builder

**Uniforms › Builder** changes a uniform without an image editor. Pick a part (jersey, sleeves, undershirt, pants,
socks, cap, helmet), click one of its colours to swap it everywhere on that part, add pinstripes, and put a PNG
logo on it with the three sliders. **On the Player** shows every part you've touched on the mannequin before you
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

**Code Plugins** builds instruction patches into `mlb.exe` with the recomp's own tools. A mod carries them in
`code/*.patch`:

```
set  <name> <SWITCH> <default 0/1>
site <set> <main|sdk> <offset hex> <original word hex> <replacement word hex> ...
```

**Add Arcade Samples** gives you working examples: the hit ones change the number the game uses to turn a hit's
power (mph) into the ball's speed off the bat (`main+167d0b4`), and Thin Air scales the air density the game works
out from a park's temperature and altitude (`main+165ac78`). The file is commented; read it before writing your own.

Rebuild Game runs the recomp's generator and build (about two minutes) and keeps your old exe as
`mlb.original.exe`. Each set can still be switched on and off afterwards without rebuilding. The manager reads the game's own
code (`game/exefs/main`) first and leaves out any set made for a different game version.

[Code mods](CODE_MODS.md) has the samples, how to write your own, and a map of the gameplay code found so far.

## Replacing sounds

Stream files (`.XVAG`) have **Replace With WAV**. Your WAV is resampled to the original's rate, matched to its
channel count and written in SADPCM, the same codec the game's own streams use. Replacing a sample inside an
`.SKX` archive isn't in yet.

## Stadiums in 3D

**Stadiums › 3D View** draws the park's `SCENE.MOD` with its textures. Orbit around it, or switch to Fly Through
and walk around with W A S D (Q and E for down and up). Hide Roof opens up covered parks.

## Not cracked yet

- The full node tree of UI layouts. Names are solved (below), but how every node nests isn't, so the Layout view
  can list an overlay's pieces and not yet draw the whole thing as the game does.
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

A table of (hash, offset) pairs, then one `VOIDASS0` chunk per asset. Nodes nest by subtree size. Node fields: +0
size, +4 type, +8 ARGB colour, +0xC x, y, z, width, height (floats, 1920×1080 space), +0x2A scale x/y (0x80 = 1.0),
+0x38 the hash of the texture or sub-layout it draws (a second one at +0x40).

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
