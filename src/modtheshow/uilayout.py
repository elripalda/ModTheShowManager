"""UI layouts (.NSW, IFF0ASSH): the scorebug, transitions, tickers and menus.

A layout file is a header table of (asset hash, offset) followed by one VOIDASS0 chunk per asset. Each asset is a
tree of nodes on a 1920x1080 canvas. A node record holds:

  +0x00 u32   size of the node and everything under it (bytes) - this is what nests the tree
  +0x04 u16   node type (0x8001 image, 0x8002/0x8003 groups, 0x81xx text and effects, 0 = a modifier/keyframe)
  +0x08 u32   colour, ARGB
  +0x0C f32   x, relative to the parent
  +0x10 f32   y
  +0x14 f32   z
  +0x18 f32   width
  +0x1C f32   height
  +0x2A u16   scale x, 0x80 = 1.0      (marker 80 00 80 00 .. .. 84 01 at +0x2A)
  +0x2C u16   scale y

Names are a 32-bit hash: for every character of the lower-cased name, rotate the hash left 8 bits and XOR the
character in; then set the top bit (name_hash). An asset's id is the hash of its name ("PBInterface\\ScoreBar"), a
texture's the hash of its name in the .TEX pack next to the layout, and an animation's the hash of its action name
("ACT_SCOREBAR_OFF"). A node draws the texture or sub-layout whose hash sits at +0x38 (a second one at +0x40).
"""
import re
import struct



def name_hash(name):
    """The game's name hash, as used for layout assets, textures and animation actions."""
    h = 0
    for c in name.lower().encode('latin1', 'replace'):
        if c >= 0x80:
            c |= 0xFFFFFF00
        h = (c ^ ((h << 8) | (h >> 24))) & 0xFFFFFFFF
    return h | 0x80000000


class Node:
    __slots__ = ('off', 'size', 'type', 'color', 'x', 'y', 'w', 'h', 'sx', 'sy', 'children', 'parent', 'ref', 'ref2')

    def abs_rect(self):
        x, y, n = self.x, self.y, self.parent
        while n is not None and n.parent is not None:     # the asset root sits at the canvas origin
            x += n.x
            y += n.y
            n = n.parent
        return x, y, self.w, self.h


class Asset:
    def __init__(self, layout, off, hash_, size):
        self.layout, self.off, self.hash, self.size = layout, off, hash_, size
        self.name = self._name()
        self._nodes = None

    def _name(self):
        d = self.layout.d
        body = d[self.off + 0x10:self.off + 0x10 + self.size]
        strs = [s.decode('latin1') for s in re.findall(rb'[A-Za-z][A-Za-z0-9_]{3,}', body)]
        good = [s for s in strs if s[0].isupper() and not s.isupper() and len(s) <= 40]
        return good[0] if good else f'asset_{self.hash:08x}'

    def nodes(self):
        """Flat list of nodes in file order, with parent/children filled in."""
        if self._nodes is not None:
            return self._nodes
        d = self.layout.d
        start, end = self.off + 0x10, self.off + 0x10 + self.size
        out = []
        for m in re.finditer(rb'[\x01-\xff][\x00-\x03][\x01-\xff][\x00-\x03]..\x84\x01', d[start:end], re.S):
            p = start + m.start() - 0x2A
            if p < start or d[p + 0x2A:p + 0x2C] == b'':
                continue
            size, typ, _flags, color = struct.unpack_from('<IHHI', d, p)
            x, y, _z, w, h = struct.unpack_from('<5f', d, p + 0x0C)
            sx, sy = struct.unpack_from('<HH', d, p + 0x2A)
            if not (-10000 < x < 10000 and -10000 < y < 10000 and 0 <= w < 10000 and 0 <= h < 10000):
                continue
            n = Node()
            n.off, n.size, n.type, n.color = p, size, typ, color
            n.x, n.y, n.w, n.h, n.sx, n.sy = x, y, w, h, sx, sy
            n.children, n.parent = [], None
            n.ref, n.ref2 = struct.unpack_from('<I4xI', d, p + 0x38) if p + 0x44 <= end else (0, 0)
            out.append(n)
        # nest by subtree size: a node contains the nodes that start inside its byte span
        stack = []
        for n in out:
            while stack and not (stack[-1].off < n.off < stack[-1].off + max(stack[-1].size, 0x50)):
                stack.pop()
            if stack and stack[-1].size >= 0x50:
                n.parent = stack[-1]
                stack[-1].children.append(n)
            if n.size >= 0x50:
                stack.append(n)
        self._nodes = out
        return out

    def container(self):
        """The asset's top visual node (the scorebug's frame), or None."""
        for n in self.nodes():
            if n.type & 0x8000 and n.w > 0 and n.h > 0 and (n.w, n.h) != (1920, 1080):
                return n
        return None


class Layout:
    def __init__(self, data):
        self.d = bytearray(data)
        if self.d[:8] != b'IFF0ASSH':
            raise ValueError('not a UI layout (IFF0ASSH)')
        self.assets = []
        for m in re.finditer(rb'VOIDASS0', self.d):
            o = m.start()
            if o % 16:
                continue
            h, size = struct.unpack_from('<II', self.d, o + 8)
            self.assets.append(Asset(self, o, h, size))

    @classmethod
    def open(cls, path):
        with open(path, 'rb') as f:
            return cls(f.read())

    def find(self, name):
        for a in self.assets:
            if a.name.lower() == name.lower():
                return a
        return None

    @staticmethod
    def texture_table(names):
        """{hash: texture name} for the names of the texture pack that goes with a layout."""
        return {name_hash(n): n for n in names}

    def true_names(self, extra=()):
        """{asset hash: its real name} for the assets whose name can be found: any text in the file, or in extra."""
        ids = {a.hash for a in self.assets}
        out = {}
        for s in list(extra) + [m.decode('latin1') for m in re.findall(rb'[ -~]{2,64}', bytes(self.d))]:
            h = name_hash(s)
            if h in ids:
                out.setdefault(h, s)
        return out

    def retexture(self, node, name):
        """Point a node at another texture of the pack (by name)."""
        struct.pack_into('<I', self.d, node.off + 0x38, name_hash(name))
        node.ref = name_hash(name)

    def move(self, node, x, y):
        struct.pack_into('<ff', self.d, node.off + 0x0C, float(x), float(y))
        node.x, node.y = float(x), float(y)

    def scale(self, node, s):
        v = max(16, min(1024, int(round(0x80 * s))))
        struct.pack_into('<HH', self.d, node.off + 0x2A, v, v)
        node.sx = node.sy = v

    def bytes(self):
        return bytes(self.d)
