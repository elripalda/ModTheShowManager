"""Recipes: changes a mod describes instead of carrying a changed game file.

A mod made only of PNGs, patch files and recipes holds none of the game's own data, so it can be shared freely, and
two mods that touch different teams or overlays both apply.

    <mod>/rosters/*.json     roster files (see rosterjson.py), applied in name order
    <mod>/layouts/*.json     overlay moves: [{"file": "NSW/UI/GAME/THEME1.NSW", "asset": "Scorebar",
                                              "x": 40, "y": 838, "scale": 1.0}]

They are carried out when mods are applied, on top of the game's files as the enabled mods' own files left them.
"""
import json
import os

from . import rosterjson, rosters as R, uilayout

KINDS = ('rosters', 'layouts')


def files(mod_path, kind):
    folder = os.path.join(mod_path, kind)
    if not os.path.isdir(folder):
        return []
    return [os.path.join(folder, f) for f in sorted(os.listdir(folder)) if f.lower().endswith('.json')]


def has_any(mod_path):
    return any(files(mod_path, k) for k in KINDS)


def count(mod_path):
    return sum(len(files(mod_path, k)) for k in KINDS)


def _load(path):
    with open(path, encoding='utf-8-sig') as f:
        return json.load(f)


def roster_targets(game):
    """romfs paths of the roster database files this install has."""
    fs = game.file_set()
    return [rel for base in (R.ROSTERS, R.PLAYERS) for rel in R.variants(base)
            if rel in fs and os.path.exists(game.path(rel))]


def layout_targets(mods):
    out = []
    for m in mods:
        for path in files(m.path, 'layouts'):
            try:
                for e in _load(path):
                    rel = str(e.get('file', '')).strip('/').upper()
                    if rel and rel not in out:
                        out.append(rel)
            except (OSError, ValueError, AttributeError, TypeError):
                pass
    return out


def apply_rosters(game, mods, problems):
    """Carries out every roster recipe of mods (in order) on the game's current roster files. Returns the romfs
    paths written."""
    docs = []
    for m in mods:
        for path in files(m.path, 'rosters'):
            try:
                docs.append((m.name, os.path.basename(path), _load(path)))
            except (OSError, ValueError) as x:
                problems.append(f'{m.name}: {os.path.basename(path)}: {x}')
    if not docs:
        return []
    targets = roster_targets(game)
    if R.ROSTERS not in targets or R.PLAYERS not in targets:
        problems.append('Roster recipes skipped: this install has no roster files.')
        return []
    db = R.Database(game.path(R.ROSTERS), game.path(R.PLAYERS))
    for mod_name, fname, doc in docs:
        try:
            rep = rosterjson.apply(db, doc)
            problems += [f'{mod_name}: {fname}: {p}' for p in rep.problems[:12]]
        except Exception as x:
            problems.append(f'{mod_name}: {fname}: {x}')
    if not db.dirty():
        return []
    out = {}
    db.write({rel: game.path(rel) for rel in targets}, lambda rel, data: out.__setitem__(rel, data))
    for rel, data in out.items():
        p = game.path(rel)
        os.chmod(p, 0o666)
        with open(p, 'wb') as f:
            f.write(data)
    return list(out)


def _texture_table(game, rel):
    """{hash: name} for the texture pack beside a layout, or {} when there is none."""
    from . import texlib
    p = game.path(rel[:-4] + '.TEX')
    if not os.path.exists(p):
        return {}
    with texlib.Tex(p, readonly=True) as t:
        return uilayout.Layout.texture_table([e['name'] for e in t.entries])


def apply_layouts(game, mods, problems):
    done = {}
    for m in mods:
        for path in files(m.path, 'layouts'):
            try:
                entries = _load(path)
            except (OSError, ValueError) as x:
                problems.append(f'{m.name}: {os.path.basename(path)}: {x}')
                continue
            for e in entries if isinstance(entries, list) else []:
                try:
                    rel = str(e['file']).strip('/').upper()
                    p = game.path(rel)
                    if not os.path.exists(p):
                        raise ValueError(f'{rel} is not a game file')
                    lay = done.get(rel) or uilayout.Layout.open(p)
                    asset = lay.find(str(e['asset']))
                    node = asset.container() if asset else None
                    if node is None:
                        raise ValueError(f'no overlay called {e["asset"]} in {rel}')
                    if 'x' in e or 'y' in e:
                        lay.move(node, float(e.get('x', node.x)), float(e.get('y', node.y)))
                    if 'scale' in e:
                        lay.scale(node, float(e['scale']))
                    if e.get('pieces'):
                        if not lay.restyle(asset, e['pieces']):
                            raise ValueError(f'none of the pieces named for {e["asset"]} are in {rel}')
                    if e.get('colours'):
                        table = _texture_table(game, rel)
                        if not lay.repaint(asset, e['colours'], table):
                            raise ValueError(f'none of the colours named for {e["asset"]} are in {rel}')
                    done[rel] = lay
                except Exception as x:
                    problems.append(f'{m.name}: {os.path.basename(path)}: {x}')
    for rel, lay in done.items():
        p = game.path(rel)
        os.chmod(p, 0o666)
        with open(p, 'wb') as f:
            f.write(lay.bytes())
    return list(done)
