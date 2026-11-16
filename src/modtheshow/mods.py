"""Mods: folders in <game>/mods, switched on and off, ordered, and installed into the game.

A mod folder:
  mod.json                                   name, author, version, description
  textures/<pack path>/<texture name>.png    replaces one texture inside a .TEX pack
  romfs/<path>                               replaces a whole game file
The library state (order, which mods are off) is in mods/modtheshow.json, so mod folders stay clean to share.
Mods lower in the list win when two touch the same thing. Originals are kept in <game>/mod-backup.
"""
import hashlib
import json
import os
import re
import shutil
import time
import zipfile

from .texlib import Tex

STATE = 'modtheshow.json'
APPLIED = 'applied.json'


def norm(rel):
    return rel.replace('\\', '/').strip('/').upper()


# what a game file is, by where it lives (first match wins)
CATEGORIES = [('NSW/UI/ART/FONTS', 'Fonts'), ('NSW/UI/GAME', 'Scoreboards'), ('CROSS/MOVIES/SCOREBAR', 'Scoreboards'),
              ('NSW/UNIFORMS', 'Uniforms'), ('NSW/CREATEUNIFORM', 'Uniforms'), ('NSW/STADIUMS', 'Stadiums'),
              ('NSW/OBJECTS', 'Bats & Gear'), ('NSW/CHARACTERS', 'Bats & Gear'), ('NSW/AUDIO', 'Sounds'),
              ('FRONTEND/STATS', 'Rosters'), ('NSW/LOADINGSCREEN', 'Menus'), ('NSW/UI', 'Menus'),
              ('CROSS/LIVE', 'Card Art')]
ORDER = ['Uniforms', 'Scoreboards', 'Stadiums', 'Bats & Gear', 'Rosters', 'Sounds', 'Fonts', 'Menus', 'Card Art',
         'Code', 'Other']


def category_of(rel):
    r = norm(rel)
    for prefix, name in CATEGORIES:
        if r.startswith(prefix):
            return name
    return 'Other'


def trash(path):
    """Send a folder to the Recycle Bin when the system has one, else delete it."""
    try:
        from PySide6.QtCore import QFile
        if QFile.moveToTrash(path):
            return
    except Exception:
        pass
    shutil.rmtree(path, ignore_errors=True)


def _put(src, dst):
    if os.path.exists(dst):
        os.chmod(dst, 0o666)
    shutil.copy2(src, dst)
    os.chmod(dst, 0o666)


class Mod:
    def __init__(self, folder, path):
        self.folder, self.path = folder, path
        self.meta = {}
        try:
            with open(os.path.join(path, 'mod.json'), encoding='utf-8') as f:
                self.meta = json.load(f)
        except (OSError, ValueError):
            pass
        self.enabled = True

    @property
    def name(self):
        return self.meta.get('name') or self.folder.lstrip('_')

    def save_meta(self):
        with open(os.path.join(self.path, 'mod.json'), 'w', encoding='utf-8') as f:
            json.dump(self.meta, f, indent=2)

    def textures(self):
        """{pack rel (upper): {texture name: png path}}"""
        out = {}
        root = os.path.join(self.path, 'textures')
        for dp, _, fs in os.walk(root):
            pngs = [f for f in fs if f.lower().endswith('.png')]
            if pngs:
                rel = norm(os.path.relpath(dp, root))
                for f in pngs:
                    out.setdefault(rel, {})[f[:-4]] = os.path.join(dp, f)
        return out

    def files(self):
        """{romfs rel (upper): source path}"""
        out = {}
        root = os.path.join(self.path, 'romfs')
        for dp, _, fs in os.walk(root):
            for f in fs:
                src = os.path.join(dp, f)
                out[norm(os.path.relpath(src, root))] = src
        return out

    def counts(self):
        t = self.textures()
        return sum(len(v) for v in t.values()), len(self.files())

    def has(self, sub):
        d = os.path.join(self.path, sub)
        return os.path.isdir(d) and any(fs for _, _, fs in os.walk(d))

    def categories(self):
        """What kinds of thing this mod changes, in the usual order."""
        cats = {category_of(r) for r in list(self.textures()) + list(self.files())}
        if self.has('rosters'):
            cats.add('Rosters')
        if self.has('layouts'):
            cats.add('Scoreboards')
        if self.has('code'):
            cats.add('Code')
        return [c for c in ORDER if c in cats]

    def changes(self):
        """{category: [what changes]} for the View Changes list."""
        out = {}
        for pack, names in sorted(self.textures().items()):
            for n in sorted(names):
                out.setdefault(category_of(pack), []).append(f'{pack} › {n}')
        for rel in sorted(self.files()):
            out.setdefault(category_of(rel), []).append(rel)
        for sub, cat in (('rosters', 'Rosters'), ('layouts', 'Scoreboards'), ('code', 'Code')):
            d = os.path.join(self.path, sub)
            if os.path.isdir(d):
                for f in sorted(os.listdir(d)):
                    out.setdefault(cat, []).append(f'{sub}/{f}')
        return {c: out[c] for c in ORDER if c in out}

    def signature(self, legacy=False):
        """A fingerprint of what Apply installs from this mod: its textures and romfs files. '' when it has neither
        (a code-only or empty mod has nothing to apply). legacy: the fingerprint builds before 0.10 wrote, which
        covered every file in the folder."""
        h = hashlib.sha1()
        any_ = False
        for dp, _, fs in sorted(os.walk(self.path)):
            rel_dir = os.path.relpath(dp, self.path).replace('\\', '/')
            if not legacy and rel_dir.split('/')[0] not in ('textures', 'romfs', 'rosters', 'layouts'):
                continue
            for f in sorted(fs):
                p = os.path.join(dp, f)
                st = os.stat(p)
                h.update(f'{os.path.relpath(p, self.path)}|{st.st_size}|{int(st.st_mtime)}'.encode())
                any_ = True
        return h.hexdigest() if any_ or legacy else ''


class Library:
    def __init__(self, game):
        self.game = game
        self.root = game.mods
        os.makedirs(self.root, exist_ok=True)

    # ---- state
    def _state(self):
        try:
            with open(os.path.join(self.root, STATE), encoding='utf-8') as f:
                return json.load(f)
        except (OSError, ValueError):
            return {'order': [], 'disabled': []}

    def _save_state(self, st):
        from .game import write_json
        write_json(os.path.join(self.root, STATE), st)

    def list(self):
        st = self._state()
        folders = [d for d in os.listdir(self.root) if os.path.isdir(os.path.join(self.root, d))]
        order = [f for f in st.get('order', []) if f in folders]
        order += sorted(f for f in folders if f not in order)
        mods = []
        for f in order:
            m = Mod(f, os.path.join(self.root, f))
            m.enabled = f not in st.get('disabled', []) and not f.startswith('_')
            mods.append(m)
        return mods

    def save_order(self, mods):
        st = self._state()
        st['order'] = [m.folder for m in mods]
        st['disabled'] = [m.folder for m in mods if not m.enabled]
        self._save_state(st)

    def set_enabled(self, mod, on):
        mods = self.list()
        for m in mods:
            if m.folder == mod.folder:
                m.enabled = on
        self.save_order(mods)

    def move(self, mod, delta):
        mods = self.list()
        i = next(i for i, m in enumerate(mods) if m.folder == mod.folder)
        j = max(0, min(len(mods) - 1, i + delta))
        mods.insert(j, mods.pop(i))
        self.save_order(mods)

    # ---- editing
    def create(self, name, author='', description=''):
        slug = re.sub(r'[<>:"/\\|?*]+', '', name).strip() or 'New Mod'
        folder, n = slug, 2
        while os.path.exists(os.path.join(self.root, folder)):
            folder, n = f'{slug} {n}', n + 1
        path = os.path.join(self.root, folder)
        os.makedirs(path)
        m = Mod(folder, path)
        m.meta = {'name': name, 'author': author, 'version': '1.0', 'description': description}
        m.save_meta()
        mods = self.list()
        self.save_order(mods)
        return m

    def delete(self, mod):
        trash(mod.path)
        self.save_order(self.list())

    def workspace(self, category, create=False, author=''):
        """The mod your own edits of one kind go into ("My Uniforms"), made on first use."""
        for m in self.list():
            if m.meta.get('workspace') == category:
                return m
        if not create:
            return None
        name = 'My Code Mods' if category == 'Code' else 'My Other Changes' if category == 'Other' else f'My {category}'
        m = next((x for x in self.list() if x.name == name), None) or self.create(
            name, author, f'Your own {category.lower()} changes, saved here as you make them.')
        m.meta['workspace'] = category
        m.save_meta()
        return m

    def tidy(self):
        """Code mods that picked up other edits (uniforms, layouts) hand them to the mod for that kind of change.
        Returns [(from mod, category, how many files)]."""
        moved = []
        for m in self.list():
            if not m.has('code') or m.meta.get('workspace'):
                continue
            jobs = []
            for sub in ('textures', 'romfs'):
                root = os.path.join(m.path, sub)
                for dp, _, fs in os.walk(root):
                    for f in fs:
                        src = os.path.join(dp, f)
                        rel = os.path.relpath(src, root)
                        jobs.append((category_of(rel), sub, rel, src))
            for sub, cat in (('rosters', 'Rosters'), ('layouts', 'Scoreboards')):
                root = os.path.join(m.path, sub)
                if os.path.isdir(root):
                    for f in os.listdir(root):
                        jobs.append((cat, sub, f, os.path.join(root, f)))
            counts = {}
            for cat, sub, rel, src in jobs:
                new = self.workspace(cat) is None
                w = self.workspace(cat, create=True, author=m.meta.get('author', ''))
                if new and not m.enabled:
                    self.set_enabled(w, False)
                dst = os.path.join(w.path, sub, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                if os.path.exists(dst):
                    os.remove(src)                      # the newer edit is already there
                else:
                    shutil.move(src, dst)
                counts[cat] = counts.get(cat, 0) + 1
            for sub in ('textures', 'romfs', 'rosters', 'layouts'):
                root = os.path.join(m.path, sub)
                if os.path.isdir(root) and not any(fs for _, _, fs in os.walk(root)):
                    shutil.rmtree(root, ignore_errors=True)
            moved += [(m.name, c, n) for c, n in counts.items()]
        return moved

    def texture_path(self, mod, pack_rel, tex_name):
        return os.path.join(mod.path, 'textures', *norm(pack_rel).split('/'), tex_name + '.png')

    def add_texture(self, mod, pack_rel, tex_name, image):
        """image: a PIL image or a path to a PNG."""
        from PIL import Image
        dst = self.texture_path(mod, pack_rel, tex_name)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        img = Image.open(image) if isinstance(image, str) else image
        img.convert('RGBA').save(dst)
        return dst

    def remove_texture(self, mod, pack_rel, tex_name):
        p = self.texture_path(mod, pack_rel, tex_name)
        if os.path.exists(p):
            os.remove(p)

    def add_file(self, mod, rel, src):
        dst = os.path.join(mod.path, 'romfs', *norm(rel).split('/'))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        return dst

    def export_zip(self, mod, out):
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
            for dp, _, fs in os.walk(mod.path):
                for f in fs:
                    p = os.path.join(dp, f)
                    z.write(p, os.path.join(mod.folder, os.path.relpath(p, mod.path)))

    def import_zip(self, path):
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if not n.endswith('/')]
            tops = {n.split('/')[0] for n in names}
            single = len(tops) == 1 and any('/' in n for n in names)
            base = os.path.splitext(os.path.basename(path))[0]
            folder = tops.pop() if single else base
            target, n = folder, 2
            while os.path.exists(os.path.join(self.root, target)):
                target, n = f'{folder} {n}', n + 1
            dest = os.path.join(self.root, target)
            for name in names:
                rel = name.split('/', 1)[1] if single else name
                if not rel or '..' in rel.split('/'):
                    continue
                out = os.path.join(dest, *rel.split('/'))
                os.makedirs(os.path.dirname(out), exist_ok=True)
                with z.open(name) as src, open(out, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
        self.save_order(self.list())
        return Mod(target, dest)

    # ---- what wins
    def winners(self):
        """Final texture and file sources from enabled mods, in order (later wins)."""
        tex, files = {}, {}
        for m in self.list():
            if not m.enabled:
                continue
            for pack, names in m.textures().items():
                for n, png in names.items():
                    tex.setdefault(pack, {})[n] = (m, png)
            for rel, src in m.files().items():
                files[rel] = (m, src)
        return tex, files

    def conflicts(self):
        seen, out = {}, {}
        for m in self.list():
            if not m.enabled:
                continue
            keys = [(p, n) for p, ns in m.textures().items() for n in ns] + [(r, None) for r in m.files()]
            for k in keys:
                if k in seen:
                    out.setdefault(k, [seen[k]]).append(m.name)
                seen[k] = m.name
        return out

    # ---- install
    def _signature(self, legacy=False):
        if legacy:
            return [[m.folder, m.signature(True)] for m in self.list() if m.enabled]
        return [[f, sig] for f, sig in ((m.folder, m.signature()) for m in self.list() if m.enabled) if sig]

    def _applied(self):
        """What the last Apply recorded: [[mod folder, fingerprint]]. A record from an older build is brought up to
        date when nothing has changed since."""
        path = os.path.join(self.game.backup, APPLIED)
        try:
            with open(path, encoding='utf-8') as f:
                doc = json.load(f)
            done = doc.get('mods', [])
        except (OSError, ValueError, AttributeError):
            return []
        if done and done != self._signature() and done == self._signature(legacy=True):
            done = self._signature()
            try:
                from .game import write_json
                write_json(path, dict(doc, mods=done))
            except OSError:
                pass
        return done

    def pending_count(self):
        """How many mods differ from what is in the game (turned on, off or edited since the last apply)."""
        done = dict(map(tuple, self._applied()))
        now = dict(map(tuple, self._signature()))
        return sum(1 for k in set(done) | set(now) if done.get(k) != now.get(k))

    def pending(self):
        return self._applied() != self._signature()

    def _backed_up(self):
        out = []
        for dp, _, fs in os.walk(self.game.backup):
            for f in fs:
                if f == APPLIED and dp == self.game.backup:
                    continue
                out.append(os.path.relpath(os.path.join(dp, f), self.game.backup).replace('\\', '/'))
        return out

    def _back_up(self, rel):
        b = os.path.join(self.game.backup, *rel.split('/'))
        if not os.path.exists(b):
            os.makedirs(os.path.dirname(b), exist_ok=True)
            shutil.copy2(self.game.path(rel), b)

    def _fix_sizes(self, rels):
        tsv = self.game.tsv
        if not rels or not os.path.exists(tsv):
            return
        want = {'/' + norm(r): os.path.getsize(self.game.path(r)) for r in rels if os.path.exists(self.game.path(r))}
        with open(tsv, encoding='utf-8', newline='') as f:
            lines = f.read().split('\n')
        for i, line in enumerate(lines):
            p = line.split('\t')
            key = p[-1].rstrip('\r').upper()
            if len(p) == 3 and key in want:
                p[0] = str(want[key])
                lines[i] = '\t'.join(p)
        with open(tsv, 'w', encoding='utf-8', newline='') as f:
            f.write('\n'.join(lines))

    def restore(self, log=print):
        rels = self._backed_up()
        for rel in rels:
            _put(os.path.join(self.game.backup, *rel.split('/')), self.game.path(rel))
        self._fix_sizes(rels)
        try:
            os.remove(os.path.join(self.game.backup, APPLIED))
        except OSError:
            pass
        log(f'Restored {len(rels)} original file(s)')
        return rels

    def apply(self, log=print, progress=lambda done, total: None):
        """Install every enabled mod. Returns (files changed, problems)."""
        from PIL import Image
        t0 = time.time()
        self.restore(log=lambda *_: None)
        tex, files = self.winners()
        total = len(files) + sum(len(v) for v in tex.values())
        done, problems, changed = 0, [], []
        for rel, (m, src) in files.items():
            if not os.path.exists(self.game.path(rel)):
                problems.append(f'{m.name}: {rel} is not a game file')
                continue
            self._back_up(rel)
            _put(src, self.game.path(rel))
            changed.append(rel)
            done += 1
            progress(done, total)
            log(f'{rel}  ({m.name})')
        for rel, names in tex.items():
            if not os.path.exists(self.game.path(rel)):
                problems.append(f'{rel} is not a game file')
                continue
            self._back_up(rel)
            t = Tex(self.game.path(rel) if rel in files else self.game.original(rel))
            n = 0
            for name, (m, png) in sorted(names.items()):
                hits = t.find(name.split('__')[0])
                try:
                    if not hits:
                        raise ValueError(f'no texture named {name} in {rel}')
                    for e in hits:
                        t.replace(e, Image.open(png))
                    n += 1
                except Exception as x:
                    problems.append(f'{m.name}: {name}: {x}')
                done += 1
                progress(done, total)
            os.chmod(self.game.path(rel), 0o666)
            t.save(self.game.path(rel))
            changed.append(rel)
            log(f'{rel}  ({n} texture(s))')
        # recipes last: they work on the files as the mods above left them
        from . import recipes
        on = [m for m in self.list() if m.enabled]
        if any(recipes.files(m.path, 'rosters') for m in on):
            for rel in recipes.roster_targets(self.game):
                self._back_up(rel)
            done = recipes.apply_rosters(self.game, on, problems)
            changed += done
            for rel in done:
                log(f'{rel}  (roster recipes)')
        for rel in recipes.layout_targets(on):
            if os.path.exists(self.game.path(rel)):
                self._back_up(rel)
        done = recipes.apply_layouts(self.game, on, problems)
        changed += done
        for rel in done:
            log(f'{rel}  (layout recipes)')
        self._fix_sizes(changed)
        os.makedirs(self.game.backup, exist_ok=True)
        with open(os.path.join(self.game.backup, APPLIED), 'w', encoding='utf-8') as f:
            json.dump({'mods': self._signature(), 'when': time.time()}, f)
        log(f'Done in {time.time() - t0:.1f}s: {len(set(changed))} game file(s) changed')
        return changed, problems
