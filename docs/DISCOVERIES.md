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

The scorebug and other overlays are `.NSW` layout files: a tree of boxes with a position, size, colour and
scale. Moving and scaling them works. The textures each box uses are named by a hash we haven't matched, so the
manager shows the layout as boxes for now.
[Layouts](MODDING_GUIDE.md#ui-layouts-iff0assh)

## The code

The recomp turns the game's code into C when it installs, so gameplay can't be patched in a running exe. Its
builder accepts a table of instruction patches instead, and that's what code mods are.

The game still carries its debug text, which is how the interesting code gets found. So far:

- **Exit velocity** is the hit's power in mph times 1.4667. Changing that one number is the moonshot mods.
- **Air density** is worked out from each park's temperature and altitude. That's the Coors Field effect, and
  the Thin Air mod.
- **The PCI** is compared with where the pitch crosses the plate right before contact. Auto PCI moves it onto
  the ball at that moment.
- **Perfect-Perfect** is two flags set in the hit code.
- **Bat breaks** and **pitcher fatigue** each come down to one number.
- The game tells a human hitter from a CPU one with a single value, which is how a mod can affect only you.

[Code mods and the full map](CODE_MODS.md)

## Still open

- The texture name hash in screen layouts.
- What ties a scanned player to his head folder.
- Head meshes and player body meshes.
- Franchise and Road to the Show saves.
- Runner speed, pitch speed and fielding in the code.
