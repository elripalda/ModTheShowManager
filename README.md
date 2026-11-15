<p align="center"><img src="src/modtheshow/assets/logo.png" width="360" alt="Mod the Show Manager"></p>

A mod manager for the MLB The Show 26 PC recomp. Browse every file in the game, preview any texture, export it,
drop in your own art and switch mods on and off.

## What it does

- **Game Files** – all 84,634 files in the game, searchable. Texture packs open as a grid you can preview,
  export or replace. Images and text files preview too.
- **Uniforms, Bats, Stadiums, Scoreboards, Menus & Loading Screens** – the same textures, sorted the way you think
  about them: by team and uniform, by ballpark, by scorebug theme.
- **Mods** – each mod is a folder in `<game>\mods`. Turn them on and off, set the order, Apply. Restore puts the
  original files back.
- **3D Models** – bats, balls, stadium props, players' gear, gloves, jerseys and bodies, drawn with their game
  textures. Export OBJ for Blender, bring an OBJ back in to replace a mesh on bats, balls and props, scale or
  hide meshes. Bat Shapes turns every bat in the game into a wiffle bat, a big barrel toy bat or a fungo.
- **Uniforms on a player** – flip the Uniforms page to *On a Player* and see the uniform you're editing on a
  mannequin, your replaced PNGs included.
- **Sounds** – every sound file in the game. Sound banks and AT9 clips play and export as WAV.
- Replaced textures keep the game's format: BC1, BC3, BC4 and BC7, with mip levels and loading previews rebuilt.

See the **[modding guide](docs/MODDING_GUIDE.md)** for where everything lives, how to find what you want and how
the file formats work.

## Get it

Download `ModTheShowManager.exe` from Releases and run it. It looks for the game in `C:\Games\MLB The Show 26`
and asks if it isn't there.

## Making a mod

1. Pick the mod your changes go into from **Saving To** at the top (or make a new one).
2. Find a texture, export it, edit it, then **Replace With PNG** (or drop the PNG on the preview).
3. Go to **Mods** and press **Apply**. Close the game first.

A mod folder looks like this, so mods can be zipped and shared:

```
mods/My Mod/
  mod.json
  textures/NSW/STADIUMS/ARZ/TEXTURES_COLOR.TEX/rolling_sign_basecolor.png
  romfs/NSW/STADIUMS/ARZ/PROPS.XML
  romfs/NSW/OBJECTS/G4GAMEBAT.MOD        (models are two files:
  romfs/NSW/OBJECTS/G4GAMEBAT.0.MOD       the description and the geometry)
```

For a custom model, export the original OBJ first and build over it in Blender so the size and axes match,
then export with the same axis settings.

Share your own work, not the game's original files.

## Building

```
pip install -r requirements.txt pyinstaller
python src/run.py                       # run from source
pyinstaller ModTheShowManager.spec      # build the exe
```

## Credits

Made by [Ripalda](https://www.elripalda.com). Runs on top of
[mlbts-native](https://github.com/sam110411/mlbts-native). Audio decoding by [vgmstream](https://vgmstream.org).
Fonts: Inter, Anton (SIL Open Font License).

Licensed under GPL-3.0.
