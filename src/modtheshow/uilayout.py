"""UI layouts (.NSW, IFF0ASSH): the scorebug, transitions, tickers and menus.

A layout file holds one VOIDASS0 chunk per asset. An asset body starts with 13 section offsets; the first section
is the asset's node tree. Every node starts with the same 0x2C bytes:

  +0x00 u8[4] colour, R G B A (multiplies down the tree; alpha 0 hides a node and everything under it)
  +0x04 f32   x, relative to the parent        +0x08 f32 y        +0x0C f32 z
  +0x10 f32   width                            +0x14 f32 height   (1920x1080 space)
  +0x1C s16   rotation
  +0x1E u16   anchor flags (+0x20 a second set used in another screen mode)
  +0x22 u16   scale x, 0x80 = 1.0              +0x24 u16 scale y
  +0x26 u8    kind (low 6 bits; the top two are flip flags)
  +0x27 u8    flags (0x20 additive, 0x80 starts hidden and is shown by an animation)

What follows depends on the kind. Where a node ends is fixed per kind, the same rule the game uses
(KIND_END); a node that holds other nodes keeps them packed between the end of its own fields and its end.
Kinds that matter most:

  0x0F group       children from +[0x38] to +[0x48]
  0x18 image       texture hash at +0x30, a second texture (mask) at +0x38
  0x01 sprite      texture hash at +0x30
  0x1E instance    draws another asset of the same file, its hash at +0x30
  0x1C states      a switch: +0x70 state count, +0x78 one u64 offset per state (0 = empty), children from +[0x48]
  0x22 text        a text box
  0x0C clip        children from +[0x30] to +[0x48]

Names are a 32-bit hash: for every character of the lower-cased name, rotate the hash left 8 bits and XOR the
character in; then set the top bit (name_hash). An asset's id is the hash of its name ("PBInterface\\ScoreBar"), a
texture's the hash of its name in the .TEX pack next to the layout, and an animation's the hash of its action name
("ACT_SCOREBAR_OFF").
"""
import re
import struct

# where each kind of node ends: ('u32'|'u16', field) read from the node, or a fixed size
KIND_END = {
    0x01: 0x58, 0x02: ('I', 0x48), 0x03: ('I', 0x48), 0x04: 0x90, 0x05: ('I', 0x48), 0x06: 0x50,
    0x07: ('I', 0x30), 0x08: ('I', 0x50), 0x09: ('I', 0x30), 0x0A: ('I', 0x78), 0x0B: ('I', 0x78),
    0x0C: ('I', 0x48), 0x0D: 0x40, 0x0E: ('I', 0x30), 0x0F: ('I', 0x48), 0x10: ('I', 0x30),
    0x11: ('I', 0x58), 0x12: 0x40, 0x13: ('I', 0x30), 0x14: ('I', 0x48), 0x15: ('I', 0x30),
    0x16: ('I', 0xA0), 0x17: ('I', 0x48), 0x18: 0x50, 0x19: ('H', 0x48), 0x1A: ('I', 0x38),
    0x1B: 0x78, 0x1C: ('I', 0x6C), 0x1D: ('I', 0x30), 0x1E: ('H', 0x50), 0x1F: ('I', 0x30),
    0x20: ('I', 0x30), 0x21: ('I', 0x30), 0x22: 0x80, 0x23: 0x88, 0x24: ('I', 0x30), 0x25: 0x98,
    0x26: ('I', 0x58),
}
# where the nodes a node holds start: a field holding the offset, for the kinds that hold nodes
KIND_KIDS = {0x02: 0x38, 0x03: 0x38, 0x05: 0x38, 0x0F: 0x38, 0x14: 0x38, 0x17: 0x38, 0x0C: 0x30, 0x1C: 0x48,
             0x13: 0x38, 0x21: 0x38, 0x10: 0x38, 0x1D: 0x38, 0x1F: 0x38, 0x20: 0x38, 0x24: 0x38,
             0x26: ('at', 0x68), 0x11: ('at', 0x68)}
KIND_NAMES = {0x0F: 'Group', 0x18: 'Image', 0x01: 'Sprite', 0x1E: 'Instance', 0x1C: 'States', 0x22: 'Text',
              0x0C: 'Clip', 0x19: 'Flipbook', 0x05: 'Colour set', 0x13: 'List', 0x1D: 'Table', 0x26: 'Text field',
              0x11: 'Button', 0x04: 'Image (two)', 0x21: 'Scroller'}
NONE = 0x80000000           # the hash of an empty name


def name_hash(name):
    """The game's name hash, as used for layout assets, textures and animation actions."""
    h = 0
    for c in name.lower().encode('latin1', 'replace'):
        if c >= 0x80:
            c |= 0xFFFFFF00
        h = (c ^ ((h << 8) | (h >> 24))) & 0xFFFFFFFF
    return h | 0x80000000


def rgba(v):
    """A node colour (u32 as stored) as (r, g, b, a)."""
    return v & 255, (v >> 8) & 255, (v >> 16) & 255, (v >> 24) & 255


def pack_rgba(r, g, b, a):
    return (int(r) & 255) | (int(g) & 255) << 8 | (int(b) & 255) << 16 | (int(a) & 255) << 24


class Node:
    __slots__ = ('off', 'size', 'kind', 'kflip', 'flags', 'color', 'x', 'y', 'z', 'w', 'h', 'sx', 'sy', 'rot',
                 'anchor', 'ref', 'ref2', 'children', 'parent', 'states', 'asset')

    @property
    def type(self):                      # older name for kind
        return self.kind

    @property
    def kind_name(self):
        return KIND_NAMES.get(self.kind, f'Kind {self.kind:02X}')

    def abs_rect(self):
        x, y, n = self.x, self.y, self.parent
        while n is not None:
            x += n.x
            y += n.y
            n = n.parent
        return x, y, self.w, self.h

    def rgba(self):
        return rgba(self.color)

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()

    def state_children(self):
        """For a States node: [child node or None] per state, in state order."""
        if self.states is None:
            return []
        by_off = {c.off - self.off: c for c in self.children}
        return [by_off.get(o) if o else None for o in self.states]


class Asset:
    def __init__(self, layout, off, hash_, size):
        self.layout, self.off, self.hash, self.size = layout, off, hash_, size
        self.body = off + 0x10
        self.name = self._name()
        self._root = None
        self._nodes = None
        self.problems = 0

    def _name(self):
        d = self.layout.d
        body = d[self.body:self.body + self.size]
        strs = [s.decode('latin1') for s in re.findall(rb'[A-Za-z][A-Za-z0-9_]{3,}', body)]
        good = [s for s in strs if s[0].isupper() and not s.isupper() and len(s) <= 40]
        return good[0] if good else f'asset_{self.hash:08x}'

    def sections(self):
        if self.size < 0x68:
            return None
        return struct.unpack_from('<13Q', self.layout.d, self.body)

    def root(self):
        if self._root is None and self.size >= 0x68:
            sec = self.sections()
            start = self.body + sec[0]
            end = self.body + (sec[1] if sec[1] else self.size)
            if sec[0] and start + 0x2C <= end <= self.body + self.size and self.layout._valid(start, end):
                self._root = self.layout._parse(start, end, None, self)
        return self._root

    def nodes(self):
        """Every node in file order, with parent and children filled in."""
        if self._nodes is None:
            r = self.root()
            self._nodes = list(r.walk()) if r else []
        return self._nodes

    def container(self):
        """The asset's top visual node (the scorebug's frame), or None."""
        for n in self.nodes():
            if n.parent is not None and n.w > 0 and n.h > 0 and (n.w, n.h) != (1920, 1080):
                return n
        return None

    def instances(self):
        """Hashes of the other assets this one draws."""
        return {n.ref for n in self.nodes() if n.kind == 0x1E}


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
        self.by_hash = {a.hash: a for a in self.assets}

    @classmethod
    def open(cls, path):
        with open(path, 'rb') as f:
            return cls(f.read())

    # ------------------------------------------------------------------ reading
    def _valid(self, p, end):
        d = self.d
        if p + 0x2C > end:
            return False
        x, y, z, w, h = struct.unpack_from('<5f', d, p + 4)
        if not all(abs(v) < 20000 for v in (x, y, z, w, h)):
            return False
        sx, sy = struct.unpack_from('<HH', d, p + 0x22)
        return d[p + 0x29] <= 1 and (d[p + 0x26] & 0x3F) in KIND_END and 0 < sx <= 0x800 and 0 < sy <= 0x800

    def _end(self, p, kind):
        rule = KIND_END.get(kind)
        if rule is None:
            return None
        if isinstance(rule, int):
            return rule
        fmt, field = rule
        return struct.unpack_from('<' + fmt, self.d, p + field)[0]

    def _parse(self, p, end, parent, asset, depth=0):
        d = self.d
        n = Node()
        n.off, n.parent, n.asset, n.children, n.states = p, parent, asset, [], None
        n.color = struct.unpack_from('<I', d, p)[0]
        n.x, n.y, n.z, n.w, n.h = struct.unpack_from('<5f', d, p + 4)
        n.rot, n.anchor, _a2, n.sx, n.sy = struct.unpack_from('<hHHHH', d, p + 0x1C)
        n.kind, n.kflip, n.flags = d[p + 0x26] & 0x3F, d[p + 0x26] >> 6, d[p + 0x27]
        n.ref, n.ref2 = struct.unpack_from('<I4xI', d, p + 0x30) if p + 0x3C <= len(d) else (NONE, NONE)
        size = self._end(p, n.kind)
        if not size or size < 0x40 or p + size > end:
            # an unknown or damaged node: it runs to the next node that looks right
            q = p + 0x50
            while q < end and not self._valid(q, end):
                q += 4
            size = q - p
            asset.problems += 1
        n.size = size
        kids = KIND_KIDS.get(n.kind)
        if kids is not None and depth < 64:
            first = kids[1] if isinstance(kids, tuple) else struct.unpack_from('<I', d, p + kids)[0]
            e = p + size
            if 0x2C <= first < size:
                q = p + first
                if not self._valid(q, e) and q + 0x10 <= e:      # a table keeps a small header before its rows
                    v = struct.unpack_from('<I', d, q + 8)[0]
                    if first < v < size and self._valid(p + v, e):
                        q = p + v
                while q < e:
                    if not self._valid(q, e):
                        # a few kinds keep extra data after their own end (a button's string list): skip it
                        q += 4
                        while q < e and not self._valid(q, e):
                            q += 4
                        if q >= e:
                            break
                    c = self._parse(q, e, n, asset, depth + 1)
                    n.children.append(c)
                    q += c.size
        if n.kind == 0x1C:
            cnt = d[p + 0x70]
            n.states = [struct.unpack_from('<I', d, p + 0x78 + 8 * i)[0] for i in range(cnt)]
        return n

    def find(self, name):
        for a in self.assets:
            if a.name.lower() == name.lower():
                return a
        h = name_hash(name)
        return self.by_hash.get(h)

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

    def pieces(self, asset, table):
        """{texture name: [nodes that draw it]} for one asset, in the order they first appear."""
        out = {}
        for n in asset.nodes():
            name = table.get(n.ref)
            if name:
                out.setdefault(name, []).append(n)
        return out

    # ------------------------------------------------------------------ editing
    def retexture(self, node, name):
        """Point a node at another texture of the pack (by name)."""
        struct.pack_into('<I', self.d, node.off + 0x30, name_hash(name))
        node.ref = name_hash(name)

    def recolor(self, node, rgb=None, alpha=None):
        """Set a node's tint (r, g, b) and/or its opacity (0-255)."""
        r, g, b, a = rgba(node.color)
        if rgb is not None:
            r, g, b = rgb
        if alpha is not None:
            a = max(0, min(255, int(alpha)))
        node.color = pack_rgba(r, g, b, a)
        struct.pack_into('<I', self.d, node.off, node.color)

    def resize(self, node, w, h):
        struct.pack_into('<ff', self.d, node.off + 0x10, float(w), float(h))
        node.w, node.h = float(w), float(h)

    def move(self, node, x, y):
        struct.pack_into('<ff', self.d, node.off + 4, float(x), float(y))
        node.x, node.y = float(x), float(y)

    def scale(self, node, s):
        v = max(16, min(1024, int(round(0x80 * s))))
        struct.pack_into('<HH', self.d, node.off + 0x22, v, v)
        node.sx = node.sy = v

    def restyle(self, asset, edits):
        """Carry out piece edits on an asset. Each edit names a texture and may give color '#rrggbb', opacity 0-100,
        dx / dy (pixels to shift every use of it), size (1.0 = as is) and use (another texture of the pack to draw
        instead). Returns how many nodes changed."""
        changed = 0
        for e in edits:
            h = name_hash(str(e['texture']))
            for n in asset.nodes():
                if n.ref != h:
                    continue
                if e.get('color'):
                    v = int(str(e['color']).lstrip('#'), 16)
                    self.recolor(n, rgb=((v >> 16) & 255, (v >> 8) & 255, v & 255))
                if e.get('opacity') is not None:
                    self.recolor(n, alpha=round(float(e['opacity']) * 2.55))
                if e.get('dx') or e.get('dy'):
                    self.move(n, n.x + float(e.get('dx', 0)), n.y + float(e.get('dy', 0)))
                if e.get('size'):
                    self.resize(n, n.w * float(e['size']), n.h * float(e['size']))
                if e.get('use'):
                    self.retexture(n, str(e['use']))
                changed += 1
        return changed

    # ---- text boxes (kind 0x22): +0x40 text colour, +0x44 / +0x48 second and highlight colours, +0x4C the label
    #      it shows (0 for live text the game fills in), +0x58 size in 1/16 px, +0x70 layout flags, +0x74 font
    #      (font number in the top six bits)
    def text_size(self, node):
        return struct.unpack_from('<H', self.d, node.off + 0x58)[0] / 16

    def set_text_size(self, node, px):
        struct.pack_into('<H', self.d, node.off + 0x58, max(16, min(0xFFFF, int(round(px * 16)))))

    def text_font(self, node):
        return self.d[node.off + 0x74] >> 2

    def set_text_font(self, node, number):
        self.d[node.off + 0x74] = ((int(number) & 0x3F) << 2) | (self.d[node.off + 0x74] & 3)

    def text_color(self, node):
        return rgba(struct.unpack_from('<I', self.d, node.off + 0x40)[0])

    def set_text_color(self, node, rgb=None, alpha=None):
        r, g, b, a = self.text_color(node)
        if rgb is not None:
            r, g, b = rgb
        if alpha is not None:
            a = alpha
        struct.pack_into('<I', self.d, node.off + 0x40, pack_rgba(r, g, b, a))

    def text_label(self, node):
        return struct.unpack_from('<I', self.d, node.off + 0x4C)[0]

    def retext(self, asset, spec):
        """Restyle every text box an overlay draws. spec: size (px, or 'x1.5' to scale), font (number), color
        ('#rrggbb'); 'only_font' narrows it to boxes using that font now. Returns how many changed."""
        n = 0
        for a in self.family(asset):
            for t in a.nodes():
                if t.kind != 0x22:
                    continue
                if spec.get('only_font') is not None and self.text_font(t) != int(spec['only_font']):
                    continue
                size = spec.get('size')
                if size is not None:
                    if isinstance(size, str) and size.lower().startswith('x'):
                        self.set_text_size(t, self.text_size(t) * float(size[1:]))
                    else:
                        self.set_text_size(t, float(size))
                if spec.get('font') is not None:
                    self.set_text_font(t, spec['font'])
                if spec.get('color'):
                    v = int(str(spec['color']).lstrip('#'), 16)
                    self.set_text_color(t, rgb=((v >> 16) & 255, (v >> 8) & 255, v & 255))
                n += 1
        return n

    def family(self, asset):
        """The asset and every asset it draws, nearest first."""
        out, todo = [], [asset]
        while todo:
            a = todo.pop(0)
            if a in out:
                continue
            out.append(a)
            todo += [self.by_hash[h] for h in sorted(a.instances()) if h in self.by_hash]
        return out

    def repaint(self, asset, rules, table=None):
        """Recolour an overlay by colour: each rule names a colour the game uses ('from': '#cecece') and gives
        'to' ('#rrggbb') and/or 'opacity' (0-100). 'texture' narrows a rule to pieces drawing that texture ('' for
        plain pieces), 'kind' to 'image' or 'text'. Covers the overlays it draws too. Returns how many changed."""
        table = table or {}
        kinds = {'image': (0x18, 0x01, 0x04), 'text': (0x22,)}
        done = set()
        for rule in rules:
            want = int(str(rule['from']).lstrip('#'), 16)
            want = ((want >> 16) & 255, (want >> 8) & 255, want & 255)
            tex = rule.get('texture')
            ks = kinds.get(rule.get('kind'), (0x18, 0x01, 0x04, 0x22))
            for a in self.family(asset):
                for n in a.nodes():
                    if n.off in done or n.kind not in ks or n.rgba()[:3] != want:
                        continue
                    if tex is not None:
                        name = '' if n.ref == NONE else table.get(n.ref, '?')
                        if name.lower() != str(tex).lower():
                            continue
                    rgb = None
                    if rule.get('to'):
                        v = int(str(rule['to']).lstrip('#'), 16)
                        rgb = ((v >> 16) & 255, (v >> 8) & 255, v & 255)
                    alpha = round(float(rule['opacity']) * 2.55) if rule.get('opacity') is not None else None
                    self.recolor(n, rgb=rgb, alpha=alpha)
                    done.add(n.off)
        return len(done)

    def bytes(self):
        return bytes(self.d)
