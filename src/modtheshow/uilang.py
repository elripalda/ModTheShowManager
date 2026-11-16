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
