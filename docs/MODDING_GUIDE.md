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

**Sounds** lists every audio file. Sound banks and AT9 files play and export as WAV through vgmstream. The
crowd and reaction streams (`.XVAG`) use a Switch-only codec (0x0E) nobody decodes yet, and the commentary,
PA and music `.SKX` archives are listed by name only (their `.KEY` files name every sample).

## Not cracked yet

- The `.XVAG` 0x0E codec and the `.SKX` archive layout. Cracking these comes before sound replacement.
- UI layouts (`.NSW` files, `IFF0ASSH`). These decide where scorebug pieces sit. Retexturing works now; moving
  pieces needs this.
- Player heads. The Switch build has no head meshes in `HEADS`; faces are built at runtime.
- Gameplay. The recomp's build can bake instruction patches into `mlb.exe` (`recomp/patches.py` in mlbts-native),
  each switchable at run time. That's the road to gameplay mods like metal-bat exit velocity. The work left is
  finding the right code.

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
- `.XVAG`: `XVAG` header with an `fmat` chunk: channels, codec, samples, …, sample rate at +0x1C. Codec 0x0E on Switch.
- `.BNK`: Sony Scream bank, `SBlk` at 0x20, bank name at 0x40.
- `.SKX` with `.CTL` (`SCTL`), `.TBL` (`STBL`) and `.KEY` (XML sample list).
