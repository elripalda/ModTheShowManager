"""Find the texture pack that holds a texture a model asks for, and load it for previews.

Models name their textures but not the pack. The game keeps them close by: a pack next to the model with the same
name, other packs in the same folder, the park's shared packs one or two folders up, or a pack named after the
texture itself (crowd chairs). Shared props and the bat look in their own common packs.
"""
import os
import threading

from PIL import Image

from . import texlib

SHARED = ['NSW/STADIUMS/PROPS', 'NSW/STADIUMS/SHARED', 'NSW/OBJECTS', 'NSW/STADIUMS']


class TextureFinder:
    def __init__(self, game, override=None):
        """override(pack_rel, name) -> path of a PNG that replaces this texture, or None."""
        self.game = game
        self.override = override
        self._folders = None
        self._names = {}
        self._lock = threading.Lock()

    def _index(self):
        if self._folders is None:
            if not self.game.files:
                self.game.index()
            self._set = set(self.game.files)
            folders = {}
            for f in self.game.files:
                if f.endswith('.TEX'):
                    d, _, n = f.rpartition('/')
                    folders.setdefault(d, []).append(f)
            self._folders = folders
        return self._folders

    def names(self, pack):
        with self._lock:
            if pack not in self._names:
                try:
                    self._names[pack] = {n.lower(): n for n in texlib.names(self.game.original(pack))}
                except OSError:
                    self._names[pack] = {}
            return self._names[pack]

    def candidates(self, model_rel, texname):
        folders = self._index()
        d = model_rel.rpartition('/')[0]
        out = []
        def add(p):
            if p in self._set and p not in out:
                out.append(p)
        add(model_rel[:-4] + '.TEX')
        add(f'{d}/{texname.upper()}.TEX')
        parts = d.split('/')
        for k in range(len(parts), max(1, len(parts) - 3), -1):
            folder = '/'.join(parts[:k])
            add(f'{folder}/{texname.upper()}.TEX')
            for p in sorted(folders.get(folder, []), key=lambda p: ('COLOR' not in p, p)):
                add(p)
        for folder in SHARED:
            for p in sorted(folders.get(folder, [])):
                add(p)
        return out

    def find(self, model_rel, texname):
        """(pack rel, exact texture name) or None."""
        if not texname:
            return None
        key = texname.lower()
        for pack in self.candidates(model_rel, texname)[:400]:
            if 'LIGHTMAP' in pack or 'NORMAL' in pack.rsplit('/', 1)[-1]:
                continue
            hit = self.names(pack).get(key)
            if hit:
                return pack, hit
        return None

    def image(self, model_rel, texname, max_size=1024):
        """PIL RGBA image of the texture (the active mod's version when there is one), or None."""
        found = self.find(model_rel, texname)
        if not found:
            return None
        pack, name = found
        png = self.override(pack, name) if self.override else None
        try:
            if png and os.path.exists(png):
                img = Image.open(png).convert('RGBA')
            else:
                with texlib.Tex(self.game.original(pack), readonly=True) as t:
                    e = t.find(name)
                    if not e or not t.readable(e[0]):
                        return None
                    img = t.image(e[0]).convert('RGBA')
        except Exception:
            return None
        if max(img.size) > max_size:
            img.thumbnail((max_size, max_size), Image.LANCZOS)
        return img
