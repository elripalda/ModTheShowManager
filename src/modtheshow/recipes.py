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


def lang_of(rel):
    """The text file beside a layout."""
    return rel[:-4] + '.LANG_EN'


def layout_targets(mods):
    out = []
    for m in mods:
        for path in files(m.path, 'layouts'):
            try:
                for e in _load(path):
                    rel = str(e.get('file', '')).strip('/').upper()
                    if rel and rel not in out:
                        out.append(rel)
                    if rel and e.get('designs') and lang_of(rel) not in out:      # a design brings words with it
                        out.append(lang_of(rel))
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


def _original(game, rel, live):
    try:
        return game.original(rel)
    except Exception:
        return live


def _sha1(path):
    import hashlib
    with open(path, 'rb') as f:
        return hashlib.sha1(f.read()).hexdigest()


def style_recipe(rel, layout, original_path, original=None):
    """The recipe entry that turns the original layout into this one: the assets it copied, then the bytes that
    differ. original: the original file's bytes, when they are in hand."""
    orig = original
    if orig is None:
        with open(original_path, 'rb') as f:
            orig = f.read()
    import hashlib
    entry = {'file': rel, 'of': hashlib.sha1(orig).hexdigest()}
    ref = uilayout.Layout(orig)
    if layout.clones:
        entry['clones'] = [[f'{src:08x}', name] for src, name in layout.clones]
        for src, name in layout.clones:
            ref.clone(ref.by_hash[src], name)
    if layout.designs:
        from . import uibuild
        entry['designs'] = list(layout.designs)
        from .samples import CARRIERS
        carriers = getattr(layout, 'carriers', None) or list(CARRIERS)
        if carriers != list(CARRIERS):                 # a theme whose pictures ride in other textures
            entry['carriers'] = carriers
        for design in layout.designs:
            uibuild.install(ref, design, carriers)
    entry['runs'] = layout.runs(ref.bytes())
    return entry


def apply_style(lay, entry):
    """Carry a saved style out on the game's own layout: the assets it copies, the designs it builds, then the
    bytes it changes. The designs' words are left on lay.words for the text file."""
    for src, name in entry.get('clones') or []:
        a = lay.by_hash.get(int(str(src), 16))
        if a is None:
            raise ValueError('this style copies an asset the layout does not have')
        lay.clone(a, str(name))
    if entry.get('designs'):
        from . import uibuild
        from .samples import CARRIERS
        for design in entry['designs']:
            uibuild.install(lay, design, entry.get('carriers') or CARRIERS)
    lay.apply_runs(entry.get('runs') or [])


def lang_bytes(game, rel, lay):
    """The text file that goes with a layout: the game's own plus the words of the designs built into it."""
    from . import uilang
    p = game.path(lang_of(rel))
    with open(_original(game, lang_of(rel), p), 'rb') as f:
        return uilang.add(f.read(), *lay.words)


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
                    if e.get('runs'):                   # a saved style: the game's own layout plus what it changed
                        orig = _original(game, rel, p)
                        if e.get('of') and e['of'] != _sha1(orig):
                            raise ValueError(f'this style was made for a different version of {rel}')
                        lay = uilayout.Layout.open(orig)
                        apply_style(lay, e)
                        done[rel] = lay
                        if not e.get('asset'):
                            continue
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
                    if e.get('text'):
                        for spec in (e['text'] if isinstance(e['text'], list) else [e['text']]):
                            lay.retext(asset, spec)
                    if e.get('colours'):
                        table = _texture_table(game, rel)
                        if not lay.repaint(asset, e['colours'], table):
                            raise ValueError(f'none of the colours named for {e["asset"]} are in {rel}')
                    done[rel] = lay
                except Exception as x:
                    problems.append(f'{m.name}: {os.path.basename(path)}: {x}')
    out = list(done)
    for rel, lay in done.items():
        p = game.path(rel)
        os.chmod(p, 0o666)
        with open(p, 'wb') as f:
            f.write(lay.bytes())
        if lay.words[0] or lay.words[1]:
            try:
                data = lang_bytes(game, rel, lay)
                p = game.path(lang_of(rel))
                os.chmod(p, 0o666)
                with open(p, 'wb') as f:
                    f.write(data)
                out.append(lang_of(rel))
            except (OSError, ValueError) as x:
                problems.append(f'{lang_of(rel)}: {x}')
    return out
