"""UI layouts (.NSW, IFF0ASSH): the scorebug, transitions, tickers and menus.

A layout file holds one VOIDASS0 chunk per asset. An asset body starts with 13 section offsets; the first section
is the asset's node tree. Every node starts with the same 0x2C bytes:

  +0x00 u8[4] colour, R G B A (multiplies down the tree; alpha 0 hides a node and everything under it)
  +0x04 f32   x, relative to the parent        +0x08 f32 y        +0x0C f32 z
  +0x10 f32   width                            +0x14 f32 height   (1920x1080 space)
  +0x1C s16   rotation
  +0x1E u16   anchors, for when the parent is a different size than it was designed at (a reused overlay is
              stretched to the size of the Instance that shows it): bits 0-1 up/down (1 top, 2 bottom, 3 stretch),
              bits 2-3 across (4 left, 8 right, 0xC stretch), 0xF0 scale in proportion, 0x100 / 0x200 keep centred.
              +0x20 holds a second set used in another screen mode
  +0x22 u16   scale x, 0x80 = 1.0              +0x24 u16 scale y
  +0x26 u8    kind (low 6 bits; the top two are flip flags)
  +0x27 u8    flags (0x20 additive, 0x80 starts hidden and is shown by an animation)

What follows depends on the kind. Where a node ends is fixed per kind, the same rule the game uses
(KIND_END); a node that holds other nodes keeps them packed between the end of its own fields and its end.
Kinds that matter most:

  0x0F group       children from +[0x38] to +[0x48]; +0x4C child count | 0x8000, | 0x100 when it clips them
  0x18 image       texture hash at +0x30, a second texture (mask) at +0x38
  0x01 sprite      texture hash at +0x30
  0x1E instance    draws another asset of the same file, its hash at +0x30
  0x1C states      a switch: +0x70 state count, +0x78 one u64 offset per state (0 = empty), children from +[0x48];
                   +0x30 points at the query that picks the look; children no state names are always drawn
  0x22 text        a text box
  0x0C clip        children from +[0x30] to +[0x48]

Animations are section 1 of the asset body: 16-byte entries (offset of its tracks u64, track count u16, length in
frames u16). A track is 24 bytes (offset of its channels u64, the node it moves as an offset in the body u64, 0xFFFF,
last frame u16, channel count u16); a channel 16 (offset of its keys u64, last frame u16, key count u8, property u8:
0 x, 1 y, 7 width, 8 height, 11 opacity); a key 8 (frame u16, then a float at +4, or for opacity a byte at +2).
Keys hold where the piece is, not how far it moves, so moving a piece means moving its keys with it: move, resize
and recolor here do. Section 8 lists the actions the game fires (ACT_BATTER_BAR_IN): command lists where 0x2A plays
an animation and 0x35 stops one.

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


def place(node, dw, dh, pw, ph):
    """Where a node sits when its parent is dw x dh bigger than designed (pw x ph): (x, y, w, h)."""
    a = node.anchor
    x, y, w, h = node.x, node.y, node.w, node.h
    if dw:
        mode = (a >> 2) & 3
        if a & 0x100:
            x += dw / 2
        elif mode == 2:
            x += dw
        elif mode == 3:
            w += dw
        elif mode == 0 and a & 0xC0 and pw > 0:
            k = (pw + dw) / pw
            x, w = x * k, w * k
    if dh:
        mode = a & 3
        if a & 0x200:
            y += dh / 2
        elif mode == 2:
            y += dh
        elif mode == 3:
            h += dh
        elif mode == 0 and a & 0x30 and ph > 0:
            k = (ph + dh) / ph
            y, h = y * k, h * k
    return x, y, max(0.0, w), max(0.0, h)


def rgba(v):
    """A node colour (u32 as stored) as (r, g, b, a)."""
    return v & 255, (v >> 8) & 255, (v >> 16) & 255, (v >> 24) & 255


def pack_rgba(r, g, b, a):
    return (int(r) & 255) | (int(g) & 255) << 8 | (int(b) & 255) << 16 | (int(a) & 255) << 24


class Node:
    __slots__ = ('off', 'size', 'kind', 'kflip', 'flags', 'color', 'x', 'y', 'z', 'w', 'h', 'sx', 'sy', 'rot',
                 'anchor', 'ref', 'ref2', 'children', 'parent', 'states', 'asset', 'clips')

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


P_X, P_Y, P_W, P_H, P_ALPHA = 0, 1, 7, 8, 11


def read_key(d, at, prop):
    """(frame, value) of one animation key."""
    frame = struct.unpack_from('<H', d, at)[0]
    return frame, (d[at + 2] if prop == P_ALPHA else struct.unpack_from('<f', d, at + 4)[0])


def write_key(d, at, prop, value):
    if prop == P_ALPHA:
        d[at + 2] = max(0, min(255, int(round(value))))
    else:
        struct.pack_into('<f', d, at + 4, float(value))


class Anim:
    def __init__(self, index, frames):
        self.index, self.frames, self.name, self.tracks = index, frames, '', []

    @property
    def label(self):
        n = self.name.replace('ACT_', '').replace('_', ' ').title() if self.name else f'Animation {self.index + 1}'
        return f'{n}  ·  {self.frames} frames'


class Asset:
    def __init__(self, layout, off, hash_, size):
        self.layout, self.off, self.hash, self.size = layout, off, hash_, size
        self.body = off + 0x10
        self.name = self._name()
        self._root = None
        self._nodes = None
        self._anims = None
        self._chan_index = None
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

    def animations(self):
        """[Anim] for this asset, in file order."""
        if getattr(self, '_anims', None) is not None:
            return self._anims
        d, b = self.layout.d, self.body
        out = []
        sec = self.sections()
        if sec and sec[1] and sec[1] + 16 <= self.size:
            s1 = sec[1]
            first = struct.unpack_from('<Q', d, b + s1)[0]
            n = (first - s1) // 16 if s1 < first <= self.size else 0
            for i in range(min(n, 4096)):
                off, cnt, dur, _x = struct.unpack_from('<QHHI', d, b + s1 + 16 * i)
                an = Anim(i, dur)
                if not off or off + 24 * cnt > self.size:
                    out.append(an)
                    continue
                for j in range(cnt):
                    ca, node, _ff, _last, nch, _z = struct.unpack_from('<QQHHHH', d, b + off + 24 * j)
                    chans = []
                    for c in range(nch):
                        if ca + 16 * c + 16 > self.size:
                            break
                        ko, _lf, kc, prop = struct.unpack_from('<QHBB', d, b + ca + 16 * c)
                        if ko + 8 * kc <= self.size:
                            chans.append((prop, b + ko, kc))
                    an.tracks.append((b + node, chans))
                out.append(an)
            self._name_anims(out, sec)
        self._anims = out
        return out

    def _name_anims(self, anims, sec):
        """Name each animation after the first game action that plays it."""
        d, b = self.layout.d, self.body
        s8 = sec[8]
        if not s8 or s8 + 24 > self.size:
            return
        first = struct.unpack_from('<Q', d, b + s8)[0]
        n = (first - s8) // 24 if s8 < first <= self.size else 0
        acts = sorted(struct.unpack_from('<QI', d, b + s8 + 24 * i) for i in range(min(n, 2048)))
        lo, hi = sec[1], struct.unpack_from('<Q', d, b + sec[1])[0]
        from . import uiquery
        for off, h in acts:
            if off + 16 > self.size:
                continue
            head = struct.unpack_from('<Q', d, b + off + 8)[0]       # entry -> (0x3E, header) -> (list, size, count)
            if not head or head + 16 > self.size:
                continue
            lst, size, _count = struct.unpack_from('<QII', d, b + head)
            end = min(self.size, max(lst, head) + size)
            q = lst
            while lst and q + 16 <= end:
                op, ptr = struct.unpack_from('<H6xQ', d, b + q)
                if op & 0xFF == 0x2A and lo <= ptr < hi and (ptr - lo) % 16 == 0:
                    a = anims[(ptr - lo) // 16]
                    if not a.name:
                        a.name = str(uiquery.word(h))
                q += 16

    def channels(self, node):
        """[(property, address of its keys, key count)] for every animation channel that drives a node."""
        idx = getattr(self, '_chan_index', None)
        if idx is None:
            idx = {}
            for an in self.animations():
                for off, chans in an.tracks:
                    idx.setdefault(off, []).extend(chans)
            self._chan_index = idx
        return idx.get(node.off, [])

    def pose(self, index, frame):
        """{node offset: {property: value}} at one frame of an animation."""
        d = self.layout.d
        out = {}
        for off, chans in self.animations()[index].tracks:
            for prop, ka, kc in chans:
                keys = [read_key(d, ka + 8 * i, prop) for i in range(kc)]
                if not keys:
                    continue
                v = keys[0][1]
                for (f0, v0), (f1, v1) in zip(keys, keys[1:]):
                    if frame >= f1:
                        v = v1
                    elif frame > f0:
                        v = v0 + (v1 - v0) * (frame - f0) / max(1, f1 - f0)
                        break
                    else:
                        break
                out.setdefault(off, {})[prop] = v
        return out

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
        self.base = bytearray(self.d)          # as opened: edits to animated pieces are worked out from here

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
        # a group hides what falls outside it when bit 0x100 of its child count is set; a Clip node always does
        n.clips = n.kind == 0x0C or (n.kind == 0x0F and p + 0x50 <= len(d) and bool(d[p + 0x4D] & 1))
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
        if alpha is not None:                      # animations that fade it keep fading it, to the new strength
            base_a = self.base[node.off + 3]
            if a == 0:
                self._keys(node, P_ALPHA, lambda v: 0)
            elif base_a:
                self._keys(node, P_ALPHA, lambda v: v * a / base_a)
            else:
                self._keys(node, P_ALPHA, lambda v: v)

    def _keys(self, node, prop, fn):
        """Rewrite a node's animation keys for one property: each becomes fn(its value when the file was opened)."""
        for p, ka, kc in node.asset.channels(node):
            if p == prop:
                for i in range(kc):
                    write_key(self.d, ka + 8 * i, p, fn(read_key(self.base, ka + 8 * i, p)[1]))

    def resize(self, node, w, h):
        """Set a node's size; its size keys in animations scale with it."""
        bw, bh = struct.unpack_from('<ff', self.base, node.off + 0x10)
        struct.pack_into('<ff', self.d, node.off + 0x10, float(w), float(h))
        node.w, node.h = float(w), float(h)
        if bw > 0:
            self._keys(node, P_W, lambda v: v * w / bw)
        if bh > 0:
            self._keys(node, P_H, lambda v: v * h / bh)

    def move(self, node, x, y):
        """Set a node's position; animations that slide it keep sliding it, from the new spot."""
        bx, by = struct.unpack_from('<ff', self.base, node.off + 4)
        struct.pack_into('<ff', self.d, node.off + 4, float(x), float(y))
        node.x, node.y = float(x), float(y)
        self._keys(node, P_X, lambda v: v + (x - bx))
        self._keys(node, P_Y, lambda v: v + (y - by))

    def scale_tree(self, node, k, text=True):
        """Shrink or grow a piece and everything in it by k, keys included. The piece keeps its own position."""
        for m in node.walk():
            bx, by, _z, bw, bh = struct.unpack_from('<5f', self.base, m.off + 4)
            if m is not node:
                struct.pack_into('<ff', self.d, m.off + 4, bx * k, by * k)
                m.x, m.y = bx * k, by * k
                self._keys(m, P_X, lambda v: v * k)
                self._keys(m, P_Y, lambda v: v * k)
            struct.pack_into('<ff', self.d, m.off + 0x10, bw * k, bh * k)
            m.w, m.h = bw * k, bh * k
            self._keys(m, P_W, lambda v: v * k)
            self._keys(m, P_H, lambda v: v * k)
            if text and m.kind == 0x22:
                for o in (0x58, 0x60):
                    v = struct.unpack_from('<H', self.base, m.off + o)[0]
                    struct.pack_into('<H', self.d, m.off + o, min(0xFFFF, int(round(v * k))))

    def restore(self, asset, family=True, source=None):
        """Put an overlay (and the overlays it shows) back the way the file was opened, or the way another copy of
        the same file (source, its bytes) has it."""
        src = self.base if source is None else source
        if len(src) != len(self.d):
            raise ValueError('the other copy of the layout is a different size')
        for a in (self.family(asset) if family else [asset]):
            self.d[a.off:a.off + 0x10 + a.size] = src[a.off:a.off + 0x10 + a.size]
            if source is not None:
                self.base[a.off:a.off + 0x10 + a.size] = src[a.off:a.off + 0x10 + a.size]
            a._root = a._nodes = a._anims = a._chan_index = None

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

    # ---- text boxes (kind 0x22): the node colour fills the letters; +0x40 outline colour, +0x44 / +0x48 second and
    #      highlight colours, +0x4C the id of
    #      its words in the .LANG file (0 when code fills it in), +0x58 base size and +0x60 the size it is drawn at
    #      (both u16 in 1/16 px; +0x60 wins when set), +0x70 flags: the font number in the low six bits, bits 18-19
    #      left / centre / right
    def text_size(self, node):
        base, _a, _b, _c, size = struct.unpack_from('<5H', self.d, node.off + 0x58)
        return (size or base) / 16

    def set_text_size(self, node, px):
        v = max(16, min(0xFFFF, int(round(px * 16))))
        base, _a, _b, _c, size = struct.unpack_from('<5H', self.d, node.off + 0x58)
        struct.pack_into('<H', self.d, node.off + (0x60 if size else 0x58), v)

    def text_font(self, node):
        return self.d[node.off + 0x70] & 0x3F

    def set_text_font(self, node, number):
        self.d[node.off + 0x70] = (self.d[node.off + 0x70] & 0xC0) | (int(number) & 0x3F)

    def text_align(self, node):
        """0 left, 1 centre, 2 right."""
        return (self.d[node.off + 0x72] >> 2) & 3

    def set_text_align(self, node, align):
        self.d[node.off + 0x72] = (self.d[node.off + 0x72] & ~0x0C) | ((int(align) & 3) << 2)

    def is_slot(self, node):
        """An image the game fills in while it runs (a team logo)."""
        return node.kind == 0x18 and self.d[node.off + 0x4A] == 1

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
        """Restyle every text box an overlay draws. spec: size (px, or 'x1.5' to scale), font (number), color and
        outline ('#rrggbb'), align (left / centre / right); 'only_font' narrows it to boxes using that font now.
        Returns how many changed."""
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
                    self.recolor(t, rgb=((v >> 16) & 255, (v >> 8) & 255, v & 255))
                if spec.get('outline'):
                    v = int(str(spec['outline']).lstrip('#'), 16)
                    self.set_text_color(t, rgb=((v >> 16) & 255, (v >> 8) & 255, v & 255))
                if spec.get('align') in ('left', 'centre', 'center', 'right'):
                    self.set_text_align(t, {'left': 0, 'right': 2}.get(spec['align'], 1))
                n += 1
        return n

    # ---- queries: what picks a States node's look, and what a copy of an overlay is handed (see uiquery)
    def _query_at(self, asset, v):
        d = self.d
        if not v or asset.body + v + 16 > len(d):
            return []
        off, cnt = struct.unpack_from('<QQ', d, asset.body + v)
        if cnt > 256 or asset.body + off + 4 * cnt > len(d):
            return []
        return list(struct.unpack_from(f'<{cnt}I', d, asset.body + off))

    def selector(self, node):
        """The query that picks a States node's look, as tokens ([] when the game's code picks it)."""
        return self._query_at(node.asset, struct.unpack_from('<I', self.d, node.off + 0x30)[0])

    def instance_args(self, node):
        """The queries an Instance node hands to the overlay it shows, one token list per argument."""
        size, cnt = struct.unpack_from('<HH', self.d, node.off + 0x50)
        if not cnt or 0x58 + 8 * cnt > size:
            return []
        return [self._query_at(node.asset, struct.unpack_from('<Q', self.d, node.off + 0x58 + 8 * i)[0])
                for i in range(cnt)]

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

    def node_at(self, asset, rel, kind=None):
        """The node at an offset inside an asset's body (None when there is none, or it is another kind)."""
        for n in asset.nodes():
            if n.off - asset.body == rel:
                return n if kind is None or n.kind == kind else None
        return None

    def runs(self, original):
        """What differs from the original file, as [[offset, hex of the new bytes]]: a whole style in a few lines,
        with nothing of the game's in it."""
        a, b = self.d, original
        if len(a) != len(b):
            raise ValueError('the layout is not the size of the original')
        out, i, n = [], 0, len(a)
        while i < n:
            if a[i] == b[i]:
                i += 1
                continue
            j, last = i, i
            while j < n and j - last <= 4:              # runs a few bytes apart are saved as one
                if a[j] != b[j]:
                    last = j
                j += 1
            out.append([i, bytes(a[i:last + 1]).hex()])
            i = last + 1
        return out

    def apply_runs(self, runs):
        for off, hx in runs:
            data = bytes.fromhex(hx)
            if int(off) + len(data) > len(self.d):
                raise ValueError('this style is for a different version of the layout')
            self.d[int(off):int(off) + len(data)] = data
        for a in self.assets:
            a._root = a._nodes = a._anims = a._chan_index = None

    def bytes(self):
        return bytes(self.d)
