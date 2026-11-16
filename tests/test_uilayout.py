"""Read, draw and edit a UI layout without game files: a small layout built here with a group, an image, a states
switch and an instance of a second asset."""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from PIL import Image  # noqa: E402

from modtheshow import uilayout, uirender  # noqa: E402

H = uilayout.name_hash


def node(kind, x, y, w, h, color=(255, 255, 255, 255), size=0x50, flags=1, ref=uilayout.NONE, extra=b''):
    b = bytearray(size)
    b[0:4] = bytes(color)
    struct.pack_into('<5f', b, 4, x, y, 0, w, h)
    struct.pack_into('<HHHH', b, 0x1E, 5, 5, 0x80, 0x80)
    b[0x26], b[0x27] = kind, flags
    struct.pack_into('<H', b, 0x28, 0x184)
    struct.pack_into('<I', b, 0x30, ref)
    b[0x50:0x50 + len(extra)] = extra
    return b


def group(x, y, w, h, kids, color=(255, 255, 255, 255)):
    g = node(0x0F, x, y, w, h, color)
    body = b''.join(kids)
    struct.pack_into('<I', g, 0x38, 0x50)
    struct.pack_into('<I', g, 0x48, 0x50 + len(body))
    struct.pack_into('<I', g, 0x4C, 0x8000 | len(kids))
    return bytes(g + body)


def states(x, y, w, h, looks):
    """A States node: a hidden label group, then one group per look."""
    head = 0x90
    s = bytearray(node(0x1C, x, y, w, h, size=head))
    label = group(0, 0, w, h, [], color=(255, 255, 255, 0))
    body = bytearray(label)
    offs = []
    for look in looks:
        offs.append(head + len(body))
        body += look
    struct.pack_into('<I', s, 0x48, head)
    struct.pack_into('<I', s, 0x6C, head + len(body))
    s[0x70] = len(looks)
    for i, o in enumerate(offs):
        struct.pack_into('<Q', s, 0x78 + 8 * i, o)
    return bytes(s + body)


def asset(name, root):
    body = bytearray(0x68 + 0x28)               # 13 section offsets, then padding up to the tree
    struct.pack_into('<Q', body, 0, len(body))
    struct.pack_into('<Q', body, 8, len(body) + len(root))
    body += root
    body += bytes(-len(body) % 16)
    return b'VOIDASS0' + struct.pack('<II', H(name), len(body)) + bytes(body)


def build():
    sub = asset('Badge', group(0, 0, 1920, 1080, [bytes(node(0x18, 0, 0, 20, 20, ref=H('dot')))]))
    look1 = group(0, 0, 100, 40, [bytes(node(0x18, 0, 0, 100, 40, color=(255, 0, 0, 255), ref=H('bar')))])
    look2 = group(0, 0, 100, 40, [bytes(node(0x18, 0, 0, 100, 40, color=(0, 0, 255, 255), ref=H('bar')))])
    frame = group(1390, 838, 473, 192, [
        bytes(node(0x18, 0, 0, 473, 192, color=(37, 44, 52, 255))),
        states(10, 10, 100, 40, [look1, look2]),
        bytes(node(0x18, 200, 10, 64, 64, ref=H('logo'))),
        bytes(node(0x18, 300, 10, 64, 64, ref=H('glow'), flags=0x21)),
        bytes(node(0x1E, 400, 100, 20, 20, ref=H('Badge'), size=0x58, extra=struct.pack('<HH', 0x58, 0))),
    ])
    main = asset('PBInterface\\ScoreBar', group(0, 0, 1920, 1080, [frame]))
    head = bytearray(0x30)
    head[:8] = b'IFF0ASSH'
    data = bytes(head) + main + sub
    return data


def test_parse():
    L = uilayout.Layout(build())
    a = L.by_hash[H('PBInterface\\ScoreBar')]
    assert a.problems == 0
    kinds = [n.kind for n in a.nodes()]
    assert kinds.count(0x18) == 5 and kinds.count(0x1C) == 1 and kinds.count(0x1E) == 1, kinds
    c = a.container()
    assert (c.x, c.y, c.w, c.h) == (1390, 838, 473, 192)
    s = next(n for n in a.nodes() if n.kind == 0x1C)
    looks = s.state_children()
    assert len(looks) == 2 and all(looks)
    img = next(n for n in a.nodes() if n.ref == H('logo'))
    assert img.abs_rect()[:2] == (1590, 848)
    assert img.parent is c


def test_draw():
    L = uilayout.Layout(build())
    a = L.by_hash[H('PBInterface\\ScoreBar')]
    names = {H(n): n for n in ('bar', 'logo', 'glow', 'dot')}
    white = Image.new('RGBA', (8, 8), (255, 255, 255, 255))
    img, hits = uirender.render(L, a, lambda n: white, names)
    assert img.getpixel((1400, 1000))[:3] == (37, 44, 52)
    assert img.getpixel((1420, 868))[:3] == (255, 0, 0)          # the first look
    s = next(n for n in a.nodes() if n.kind == 0x1C)
    img, _ = uirender.render(L, a, lambda n: white, names, states={s.off: 1})
    assert img.getpixel((1420, 868))[:3] == (0, 0, 255)          # the second look
    drawn = {h.texture for h in hits}
    assert 'glow' not in drawn and 'dot' in drawn                 # glows wait for effects; instances draw
    _, hits = uirender.render(L, a, lambda n: white, names, effects=True)
    assert 'glow' in {h.texture for h in hits}


def test_edit():
    data = build()
    L = uilayout.Layout(data)
    assert L.bytes() == data
    a = L.by_hash[H('PBInterface\\ScoreBar')]
    c = a.container()
    L.move(c, 40, 838)
    logo = next(n for n in a.nodes() if n.ref == H('logo'))
    L.recolor(logo, rgb=(10, 20, 30), alpha=128)
    L.resize(logo, 32, 32)
    L.retexture(logo, 'bar')
    L2 = uilayout.Layout(L.bytes())
    a2 = L2.by_hash[a.hash]
    assert a2.container().x == 40
    n = next(n for n in a2.nodes() if n.off == logo.off)
    assert n.rgba() == (10, 20, 30, 128) and (n.w, n.h) == (32, 32) and n.ref == H('bar')
    assert len(a2.nodes()) == len(a.nodes())


def test_hash():
    assert H('PBInterface\\ScoreBar') == 0xF3657054
    assert H('') == uilayout.NONE


if __name__ == '__main__':
    test_hash()
    test_parse()
    test_draw()
    test_edit()
    print('ui layout ok')
