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


def asset(name, root, moves=()):
    """moves: one animation, as [(node offset in the body, property, [(frame, value)])]."""
    body = bytearray(0x68 + 0x28)               # 13 section offsets, then padding up to the tree
    struct.pack_into('<Q', body, 0, len(body))
    s1 = len(body) + len(root)
    struct.pack_into('<Q', body, 8, s1)
    body += root
    if moves:
        tracks = s1 + 16
        chans = tracks + 24 * len(moves)
        keys = chans + 16 * len(moves)
        last = max(f for _, _, ks in moves for f, _ in ks)
        body += struct.pack('<QHHI', tracks, len(moves), last, 0)
        tail = bytearray()
        for i, (at, _prop, ks) in enumerate(moves):
            body += struct.pack('<QQHHHH', chans + 16 * i, at, 0xFFFF, last, 1, 0)
        for at, prop, ks in moves:
            body += struct.pack('<QHBB', keys + len(tail), last, len(ks), prop) + bytes(4)
            for f, v in ks:
                k = bytearray(8)
                struct.pack_into('<H', k, 0, f)
                uilayout.write_key(k, 0, prop, v)
                tail += k
        body += tail
    body += bytes(-len(body) % 16)
    return b'VOIDASS0' + struct.pack('<II', H(name), len(body)) + bytes(body)


def build(moves=()):
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
    main = asset('PBInterface\\ScoreBar', group(0, 0, 1920, 1080, [frame]), moves)
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


def test_animation():
    """A piece that slides in: its keys hold where it sits, so moving, resizing or hiding it rewrites them too."""
    plain = uilayout.Layout(build())
    a = plain.by_hash[H('PBInterface\\ScoreBar')]
    logo = next(n for n in a.nodes() if n.ref == H('logo'))
    at = logo.off - a.body
    moves = [(at, uilayout.P_X, [(0, 150.0), (10, 200.0)]), (at, uilayout.P_ALPHA, [(0, 0), (10, 255)])]
    data = build(moves)
    L = uilayout.Layout(data)
    a = L.by_hash[a.hash]
    an = a.animations()
    assert len(an) == 1 and an[0].frames == 10 and len(an[0].tracks) == 2
    logo = L.node_at(a, at, 0x18)
    assert a.pose(0, 0)[logo.off] == {uilayout.P_X: 150.0, uilayout.P_ALPHA: 0}
    assert a.pose(0, 5)[logo.off][uilayout.P_X] == 175.0 and a.pose(0, 99)[logo.off][uilayout.P_X] == 200.0
    img0, _ = uirender.render(L, a, lambda n: Image.new('RGBA', (8, 8), (255, 255, 255, 255)),
                              {H('logo'): 'logo', H('bar'): 'bar', H('dot'): 'dot'}, pose=a.pose(0, 0))
    img1, _ = uirender.render(L, a, lambda n: Image.new('RGBA', (8, 8), (255, 255, 255, 255)),
                              {H('logo'): 'logo', H('bar'): 'bar', H('dot'): 'dot'}, pose=a.pose(0, 10))
    assert img0.getpixel((1390 + 232, 838 + 42)) != img1.getpixel((1390 + 232, 838 + 42))
    L.move(logo, 260, 10)                                        # 60 to the right: so do the keys
    assert [k[uilayout.P_X] for k in (a.pose(0, 0)[logo.off], a.pose(0, 10)[logo.off])] == [210.0, 260.0]
    L.recolor(logo, alpha=0)                                     # hidden stays hidden while it plays
    assert a.pose(0, 10)[logo.off][uilayout.P_ALPHA] == 0
    # a style is the bytes that changed, and puts them back on the game's own file
    runs = L.runs(data)
    assert runs and sum(len(h) // 2 for _, h in runs) < 64
    again = uilayout.Layout(data)
    again.apply_runs(runs)
    assert again.bytes() == L.bytes()
    assert again.by_hash[a.hash].pose(0, 10)[logo.off][uilayout.P_X] == 260.0
    L.restore(a)
    assert L.bytes() == data


def test_repaint():
    L = uilayout.Layout(build())
    a = L.by_hash[H('PBInterface\\ScoreBar')]
    names = {H(n): n for n in ('bar', 'logo', 'glow', 'dot')}
    n = L.repaint(a, [{'from': '#252c34', 'to': '#102030'}, {'from': '#ffffff', 'texture': 'dot', 'opacity': 0}], names)
    assert n == 2
    frame = next(x for x in a.nodes() if x.kind == 0x18 and x.ref == uilayout.NONE)
    assert frame.rgba() == (16, 32, 48, 255)
    dot = next(x for x in L.by_hash[H('Badge')].nodes() if x.ref == H('dot'))
    assert dot.rgba()[3] == 0


def test_text():
    from modtheshow import fontlib
    import numpy as np
    L = uilayout.Layout(build())
    # a text box is 0x80 bytes; give the asset one by reusing an image record's space is not possible, so build one
    t = bytearray(node(0x22, 5, 5, 100, 30, size=0x80))
    struct.pack_into('<H', t, 0x58, 14 * 16)
    struct.pack_into('<H', t, 0x60, 24 * 16)
    struct.pack_into('<I', t, 0x70, 0x00148000 | 0x40 | 10)
    L2 = uilayout.Layout(bytes(L.d[:0x30]) + asset('T', group(0, 0, 1920, 1080, [bytes(t)])))
    a = L2.assets[0]
    n = next(x for x in a.nodes() if x.kind == 0x22)
    assert L2.text_size(n) == 24 and L2.text_font(n) == 10
    assert L2.retext(a, {'size': 'x1.5', 'font': 2, 'color': '#ff0000'}) == 1
    assert L2.text_size(n) == 36 and L2.text_font(n) == 2 and L2.d[n.off + 0x70] & 0xC0 == 0x40
    assert L2.text_align(n) == 1
    L2.set_text_align(n, 2)
    assert L2.text_align(n) == 2 and L2.text_font(n) == 2
    assert n.rgba()[:3] == (255, 0, 0)
    assert fontlib.char_of(fontlib.code_of('Ñ')) == 'Ñ' and fontlib.char_of(0x41) == 'A'
    m = np.zeros((20, 20), bool)
    m[5:15, 5:15] = True
    f = fontlib.distance_field(m, 4)
    assert f[10, 10] == 255 and f[0, 0] == 0 and 100 < f[10, 5] < 160


def test_queries():
    from modtheshow import uiquery as Q
    t = Q.tokens('[ IF_Q_ELSE_INT [ QCOMP [ UI TEMPLATE_QUERY_INX [ 3 ] , <= , 5 ] , UI TEMPLATE_QUERY_INX [ 3 ] , 9 ] ]')
    assert Q.text(t).startswith('[ IF_Q_ELSE_INT [ QCOMP')
    c = Q.Context(Q.Situation(outs=2, bottom=True), [0, 0, 0, 4])
    assert c.number(t) == 4 and Q.Context(Q.Situation(), [0, 0, 0, 7]).number(t) == 9
    assert c.number(Q.tokens('[ SCOREBAR OUT_TAB ]')) == 2
    assert c.value(Q.parse(Q.tokens('[ TEAM_UI SHORT_NAME [ OFF_TEAM_ID ] ]'))) == 'AZ'
    assert Q.word(Q.tokens('[ -1 ]')[1]) == -1


def test_lang_and_place():
    from modtheshow import uilang, uiquery as Q
    words = b'OUT\0' + b'^d0^-^d1^\0'
    q1, q2 = Q.tokens('[ IG BALLS ]'), Q.tokens('[ IG STRIKES ]')
    head = 0x20
    t1 = head                       # one fixed word
    t2 = t1 + 16                    # one live text
    binds = t2 + 24
    toks = binds + 32
    strs = toks + 4 * (len(q1) + len(q2))
    b = bytearray(strs + len(words))
    struct.pack_into('<8I', b, 0, t1, 0, t2, 0, 1, 1, len(b), 2)
    struct.pack_into('<QQ', b, t1, 0x11, strs)
    struct.pack_into('<QQQ', b, t2, 0x22, strs + 4, binds)
    struct.pack_into('<QQQQ', b, binds, toks, 0x10000 | len(q1), toks + 4 * len(q1), len(q2))
    struct.pack_into(f'<{len(q1) + len(q2)}I', b, toks, *(q1 + q2))
    b[strs:] = words
    lg = uilang.Lang(b)
    assert lg.static[0x11] == 'OUT'
    fmt, bd = lg.live[0x22]
    ctx = Q.Context(Q.Situation(balls=3, strikes=2))
    assert fmt == '^d0^-^d1^' and [ctx.value(Q.parse(bd[i])) for i in (0, 1)] == [3, 2]
    assert uilang.plain('P: ^f21^^s20^^c3^^d0^') == 'P: ^d0^'

    class N:
        x, y, w, h = 10.0, 5.0, 100.0, 20.0
    # parent grew 50 x 10: 0x5 top-left stays, 0xF stretches, 0x6 bottom-left drops, 0xE bottom + stretch across,
    # 0x300 stays centred
    for anchor, want in ((0x5, (10, 5, 100, 20)), (0xF, (10, 5, 150, 30)), (0x6, (10, 15, 100, 20)),
                         (0xE, (10, 15, 150, 20)), (0x300, (35, 10, 100, 20))):
        N.anchor = anchor
        assert uilayout.place(N, 50, 10, 200, 40) == want, hex(anchor)


def directory(assets):
    """A layout file's opening: one table of (hash, 0, offset) rows sorted by hash, then the chunks."""
    assets = sorted(assets, key=lambda c: struct.unpack_from('<I', c, 8)[0])
    first = 0x30 + 16 * len(assets)
    rows, at = b'', first
    for c in assets:
        rows += struct.pack('<IIQ', struct.unpack_from('<I', c, 8)[0], 0, at)
        at += len(c)
    head = b'IFF0ASSH' + struct.pack('<IIIIII', 0, at, 1, 0, 0x20, 0) + struct.pack('<IIQ', len(assets), 7, 0x30)
    return head + rows + b''.join(assets)


def test_clone_and_mirror():
    """One template drawn twice can be given a second shape: copy it, flip the copy, point one user at it."""
    row = asset('Row', group(0, 0, 100, 40, [
        bytes(node(0x18, 0, 0, 30, 40, ref=H('logo'))),
        bytes(node(0x18, 70, 0, 30, 40, color=(255, 0, 0, 255))),
    ]), [(0x90 + 0x50, uilayout.P_X, [(0, -30.0), (10, 0.0)])])
    use = [bytes(node(0x1E, 0, i * 50, 100, 40, ref=H('Row'), size=0x58, extra=struct.pack('<HH', 0x58, 0)))
           for i in (0, 1)]
    main = asset('PBInterface\\ScoreBar', group(0, 0, 1920, 1080, [group(10, 10, 200, 100, use)]))
    data = directory([main, row])
    L = uilayout.Layout(data)
    assert len(L.assets) == 2 and sum(a.problems for a in L.assets) == 0
    twin = L.clone(L.by_hash[H('Row')], 'Row_Mirrored')
    L.mirror(twin)
    bar = L.by_hash[H('PBInterface\\ScoreBar')]
    L.retarget(bar.container().children[1], twin)
    L2 = uilayout.Layout(L.bytes())
    assert len(L2.assets) == 3 and len(L2.bytes()) == len(data) + 16 + len(row)
    d = L2.bytes()
    assert struct.unpack_from('<I', d, 0x0C)[0] == len(d) and struct.unpack_from('<I', d, 0x20)[0] == 3
    rows = [struct.unpack_from('<IIQ', d, 0x30 + 16 * i) for i in range(3)]
    assert [r[0] for r in rows] == sorted(r[0] for r in rows)
    assert all(d[r[2]:r[2] + 8] == b'VOIDASS0' and struct.unpack_from('<I', d, r[2] + 8)[0] == r[0] for r in rows)
    a, b = L2.by_hash[H('Row')], L2.by_hash[H('Row_Mirrored')]
    assert [n.x for n in a.nodes()[1:]] == [0, 70] and [n.x for n in b.nodes()[1:]] == [70, 0]
    assert a.pose(0, 0)[a.nodes()[1].off][uilayout.P_X] == -30 and b.pose(0, 0)[b.nodes()[1].off][uilayout.P_X] == 100
    assert b.nodes()[1].kflip == 1 and a.nodes()[1].kflip == 0
    assert L2.by_hash[bar.hash].container().children[1].ref == H('Row_Mirrored')
    # and it travels as a recipe: the copy by name, then the bytes that differ
    import tempfile
    from modtheshow import recipes
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(data)
    entry = recipes.style_recipe('T.NSW', L, f.name)
    assert entry['clones'] == [[f'{H("Row"):08x}', 'Row_Mirrored']]
    again = uilayout.Layout(data)
    recipes.apply_style(again, entry)
    assert again.bytes() == L.bytes()


def test_build_a_design():
    """A piece of UI written as data compiles into an asset the reader takes like the game's own, and its words go
    into the text file."""
    from modtheshow import recipes, uibuild, uilang, uiquery
    design = {'name': 'MTS_Test', 'size': [300, 40], 'pieces': [
        {'box': [0, 0, 300, 40], 'color': '#101010', 'opacity': 80},
        {'text': '^d0^ OUT', 'data': ['SCORER OUTS'], 'at': [200, 4, 96, 32], 'size': 24, 'align': 'right'},
        {'text': 'TOP', 'at': [4, 4, 60, 32], 'font': 23},
        {'logo': 'home', 'kind': 2, 'at': [70, 0, 40, 40]},
        {'team': 'away', 'at': [110, 0, 40, 40]},
        {'switch': 'IG IS_BOTTOM', 'at': [150, 0, 40, 40], 'looks': [
            [{'box': [0, 0, 40, 40], 'color': '#ff0000'}], [{'box': [0, 0, 40, 40], 'color': '#0000ff'}]]}]}
    row = asset('Row', group(0, 0, 100, 40, [bytes(node(0x18, 0, 0, 30, 40))]))
    use = bytes(node(0x1E, 0, 0, 100, 40, ref=H('Row'), size=0x58, extra=struct.pack('<HH', 0x58, 0)))
    main = asset('PBInterface\\ScoreBar', group(0, 0, 1920, 1080, [group(10, 10, 200, 100, [use])]))
    data = directory([main, row])
    L = uilayout.Layout(data)
    made = uibuild.install(L, design)
    L.retarget(L.by_hash[H('PBInterface\\ScoreBar')].container().children[0], made)
    L2 = uilayout.Layout(L.bytes())
    a = L2.by_hash[H('MTS_Test')]
    assert a.problems == 0 and a.name == 'MTS_Test'
    kinds = [n.kind for n in a.nodes()]
    assert kinds.count(0x22) == 2 and kinds.count(0x1C) == 1 and kinds.count(0x1E) == 1 and kinds[0] == 0x0F
    sw = next(n for n in a.nodes() if n.kind == 0x1C)
    assert uiquery.text(L2.selector(sw)) == '[ IG IS_BOTTOM ]' and len(sw.state_children()) == 2
    assert all(c is not None and c.children[0].kind == 0x18 for c in sw.state_children())
    slot = next(n for n in a.nodes() if L2.is_slot(n))
    assert uiquery.text(L2._query_at(a, struct.unpack_from('<Q', L2.d, slot.off + 0x30)[0])) == \
        '[ UI LOGO [ HOME_TEAM_ID , 2 ] ]'
    wash = next(n for n in a.nodes() if n.kind == 0x1E)
    assert [uiquery.text(q) for q in L2.instance_args(wash)] == ['[ AWAY_TEAM_ID ]'] and wash.parent.clips
    txt = next(n for n in a.nodes() if n.kind == 0x22)
    assert L2.text_size(txt) == 24 and L2.text_align(txt) == 2 and L2.text_font(txt) == 25
    # the words: a text file with nothing but a header takes them, sorted, and reads them back
    static, live = L.words
    assert list(static.values()) == ['TOP'] and [v[0] for v in live.values()] == ['^d0^ OUT']
    empty = struct.pack('<8I', 0x20, 0, 0x20, 0, 0, 0, 0x20, 2)
    assert uilang.add(empty) == empty
    lang = uilang.Lang(uilang.add(uilang.add(empty, {5: 'five'}, {}), static, live))
    assert lang.static[5] == 'five' and lang.static[L2.text_label(next(n for n in a.nodes() if n.kind == 0x22 and
                                                                       L2.text_font(n) == 23))] == 'TOP'
    words, binds = lang.live[L2.text_label(txt)]
    assert words == '^d0^ OUT' and uiquery.text(binds[0]) == '[ SCORER OUTS ]'
    img, _ = uirender.render(L2, L2.by_hash[H('PBInterface\\ScoreBar')], lambda n: None, {},
                             situation=uiquery.Situation(bottom=True), lang=lang)
    assert img.getpixel((10 + 150 + 20, 10 + 20))[:3] == (0, 0, 255)                # the second look is the one drawn
    # and a style carries the design as data, not as bytes
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(data)
    entry = recipes.style_recipe('T.NSW', L, f.name)
    assert entry['designs'] == [design]
    again = uilayout.Layout(data)
    recipes.apply_style(again, entry)
    assert again.bytes() == L.bytes() and again.words == L.words


def test_team_art():
    from modtheshow import teamart
    assert teamart.color('sd') == (0x2F, 0x24, 0x1D) and teamart.color('SD_CC') == teamart.color('SD')
    assert teamart.color('???', (1, 2, 3)) == (1, 2, 3)
    assert teamart.logo_name('HOU') == ('NSW/UI/ART/TEXTURES/LOGO2.TEX', 'logo2_hou')
    assert teamart.logo_name('sd', 'tile', True) == ('NSW/UI/ART/TEXTURES/LOGO4.TEX', 'logo4_sd_cc')


def test_hash():
    assert H('PBInterface\\ScoreBar') == 0xF3657054
    assert H('') == uilayout.NONE


if __name__ == '__main__':
    test_hash()
    test_parse()
    test_draw()
    test_edit()
    test_animation()
    test_repaint()
    test_text()
    test_queries()
    test_lang_and_place()
    test_clone_and_mirror()
    test_build_a_design()
    test_team_art()
    print('ui layout ok')
