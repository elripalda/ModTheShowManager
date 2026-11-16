# Quick start

## 1. Set up

1. Install the MLB The Show 26 PC recomp and make sure the game starts.
2. Run `ModTheShowManager-Setup.exe`.
3. Open the manager. If your game isn't in `C:\Games\MLB The Show 26`, point it at the folder that has `mlb.exe`.

Home shows the state of your game: stock or modded files, which build of `mlb.exe` you have, and a Play button.

## 2. Try a sample

1. Go to **Mods** and press **Sample Mods**. Leave them all ticked and press **Add Samples**.
2. Switch on **Sample: Scorebug Bottom Left**.
3. Close the game if it's open, then press **Apply Changes**.
4. Press **Play** and start a game. The scorebug is in the bottom left corner.

Switch it off and Apply again and the scorebug goes home.

## 3. Make your own

1. Press **New Mod** and give it a name. It becomes the mod in **Saving To** at the top.
2. Open **Stadiums**, pick a park, click a sign.
3. **Export PNG**, edit it in any image editor, then **Replace With PNG** (or drop the PNG on the preview).
4. **Mods › Apply Changes**.

The same steps work everywhere else: uniforms, bats, menus, scorebugs.

## 4. Try a gameplay mod

Code mods need the recomp's own folder, the one with `MLBTS-Setup.exe` in it.

1. Go to **Code Plugins**. If it says the recomp folder wasn't found, press **Find Recomp Folder**.
2. Tick **Moonshot** (or **Auto PCI**).
3. Press **Rebuild Game** and wait about two minutes.
4. Launch from the manager.

After the first rebuild you can tick and untick without rebuilding. It takes effect the next time you launch
from the manager.

## 5. Go back to stock

**Mods › Restore Original Game** puts every original file back, brings back the standard `mlb.exe` and switches
all mods off. Your mods stay in the list for later.

## Where things are

| | |
| --- | --- |
| Your mods | `<game>\mods` |
| Original files a mod replaced | `<game>\mod-backup` |
| The exe from before code mods | `<game>\mlb.original.exe` |
| The manager's log | Settings › Open Log |
