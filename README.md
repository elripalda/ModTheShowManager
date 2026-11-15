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
- Replaced textures keep the game's format: BC1, BC3, BC4 and BC7, with mip levels and loading previews rebuilt.

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
```

Share your own work, not the game's original files.

## Building

```
pip install -r requirements.txt pyinstaller
python src/run.py                       # run from source
pyinstaller ModTheShowManager.spec      # build the exe
```

## Credits

Made by [Ripalda](https://www.elripalda.com). Runs on top of
[mlbts-native](https://github.com/sam110411/mlbts-native). Fonts: Inter, Anton (SIL Open Font License).

Licensed under GPL-3.0.
