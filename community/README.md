# Sharing mods

The **Discover** tab in the manager lists the mods in [index.json](index.json). Anyone can add one.

## What a shared mod can hold

Only things you made:

- `textures/**.png` — your art.
- `rosters/*.json` — [roster files](../docs/ROSTER_FILES.md).
- `layouts/*.json` — overlay moves.
- `code/*.patch` — [code mods](../docs/CODE_MODS.md).
- `mod.json`, a readme, a `preview.png`.

No changed game files (`romfs/`), no programs. The manager refuses a zip that has them, so a shared mod never
carries the game's own data. Don't share other people's work or logos you don't have the right to use.

## Sharing yours

1. In the manager, pick your mod in **Saving To**, open **Discover** and press **Share a Mod**. It packs the zip
   and tells you if anything had to be left out.
2. The form that opens asks for the zip, a name and a line about what it does.
3. Once it's looked over, it goes in the list.

## A league pack

A league is just a mod with more than one of those in it:

```
mods/Liga Mexicana/
  mod.json
  rosters/01 teams.json          names and rosters for each club
  textures/NSW/UNIFORMS/...      uniforms and logos
  layouts/scorebug.json          optional
```

Roster files are applied in name order, and two packs that change different teams both work at once.
