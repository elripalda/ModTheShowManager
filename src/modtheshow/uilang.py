"""Layout text (.LANG_EN beside a .NSW): what every text box says.

Header: eight u32 (offset and count of two tables among them). Table one is fixed words: (id u64, offset u64 of a
NUL-ended string). Table two is live text: (id u64, string offset u64, bindings offset u64); the string holds
^d0^ ^d1^ placeholders and each binding, in ^d0^ ^d1^ order, is (offset u64 of a token list, u64 with the token count in its low 16 bits). Token lists
are game queries (see uiquery). A text box names its entry by the id at +0x4C.

Markup inside strings: ^n^ new line, ^dN^ a value, ^sNN^ size, ^fNN^ font, ^cN^ colour, ^bN^ a button picture.
"""
import re
import struct


class Lang:
    def __init__(self, data):
        self.d = bytes(data)
        b = self.d
        o1, _, o2, _, n1, n2, _size, _ = struct.unpack_from('<8I', b, 0)
        self.static, self.live = {}, {}
        for i in range(n1):
            k, o = struct.unpack_from('<QQ', b, o1 + i * 16)
            self.static[k & 0xFFFFFFFF] = self._s(o)
        for i in range(n2):
            k, so, do = struct.unpack_from('<QQQ', b, o2 + i * 24)
            s = self._s(so)
            binds = {}
            for j in range(len(set(re.findall(r'\^d(\d+)\^', s)))):
                off, c = struct.unpack_from('<QQ', b, do + 16 * j)
                binds[j] = list(struct.unpack_from(f'<{c & 0xFFFF}I', b, off))     # in order: ^d0^ first
            self.live[k & 0xFFFFFFFF] = (s, binds)

    def _s(self, o):
        return self.d[o:self.d.index(b'\0', o)].decode('utf-8', 'replace')

    @classmethod
    def open(cls, path):
        with open(path, 'rb') as f:
            return cls(f.read())

    def token_lists(self):
        for _s, binds in self.live.values():
            yield from binds.values()


MARK = re.compile(r'\^(?:[sfcb]\d+)\^')


def plain(s):
    """A string without its size, font and colour marks; ^n^ becomes a line break."""
    return MARK.sub('', s).replace('^n^', '\n')


def add(data, static=None, live=None):
    """A .LANG file with entries added: static {id: words}, live {id: (words, [token lists])}. Both tables stay
    sorted by id, which is how the game finds an entry; an id already there is replaced."""
    b = bytes(data)
    o1, z1, o2, z2, n1, n2, _size, tail = struct.unpack_from('<8I', b, 0)
    t1 = [list(struct.unpack_from('<QQ', b, o1 + 16 * i)) for i in range(n1)]
    t2 = [list(struct.unpack_from('<QQQ', b, o2 + 24 * i)) for i in range(n2)]
    static, live = dict(static or {}), dict(live or {})
    t1 = [r for r in t1 if r[0] not in static]
    t2 = [r for r in t2 if r[0] not in live]
    body_at = o2 + 24 * n2
    if o1 != 0x20 or o2 != o1 + 16 * n1 or body_at > len(b):
        raise ValueError('this text file is not laid out the way the manager expects')
    body = bytearray(b[body_at:])
    new_at = 0x20 + 16 * (len(t1) + len(static)) + 24 * (len(t2) + len(live))
    shift = new_at - body_at
    seen = set()
    for _k, _so, do in t2:                                   # the bindings hold file offsets too
        s = b[_so:b.index(b'\0', _so)].decode('utf-8', 'replace')
        for j in range(len(set(re.findall(r'\^d(\d+)\^', s)))):
            at = do + 16 * j
            if at in seen:
                continue
            seen.add(at)
            off = struct.unpack_from('<Q', b, at)[0]
            struct.pack_into('<Q', body, at - body_at, off + shift)
    for r in t1:
        r[1] += shift
    for r in t2:
        r[1] += shift
        r[2] += shift

    def put(raw, align=1):
        body.extend(bytes(-len(body) % align))
        at = new_at + len(body)
        body.extend(raw)
        return at
    for k, words in static.items():
        t1.append([k, put(words.encode('utf-8') + b'\0')])
    for k, (words, lists) in live.items():
        if len(set(re.findall(r'\^d(\d+)\^', words))) != len(lists):
            raise ValueError(f'"{words}" needs one query for each ^dN^ in it')
        so = put(words.encode('utf-8') + b'\0')
        offs = [put(struct.pack(f'<{len(t)}I', *t), 8) for t in lists]
        binds = b''.join(struct.pack('<QQ', o, len(t) | ((len(lists) - 1 - j) << 16))
                         for j, (o, t) in enumerate(zip(offs, lists)))
        t2.append([k, so, put(binds, 8) if binds else new_at])
    t1.sort()
    t2.sort()
    out = bytearray(struct.pack('<8I', 0x20, z1, 0x20 + 16 * len(t1), z2, len(t1), len(t2), 0, tail))
    for r in t1:
        out += struct.pack('<QQ', *r)
    for r in t2:
        out += struct.pack('<QQQ', *r)
    out += body
    struct.pack_into('<I', out, 0x18, len(out))
    return bytes(out)
