"""Apply, switch off and restore must leave the game exactly as it was."""
import hashlib
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from modtheshow import codemods, game as G, mods as M, rosterjson  # noqa: E402


def _game(root):
    files = {'A/ONE.BIN': b'one' * 100, 'A/TWO.BIN': b'two' * 50, 'B/THREE.BIN': b'three'}
    for rel, data in files.items():
        p = os.path.join(root, 'game', 'romfs', *rel.split('/'))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'wb') as f:
            f.write(data)
    with open(os.path.join(root, 'game', 'romfs_list.tsv'), 'w', newline='') as f:
        f.write(''.join(f'{len(d)}\t0\t/{rel}\n' for rel, d in files.items()))
    with open(os.path.join(root, 'mlb.exe'), 'wb') as f:
        f.write(b'exe')
    return files


def _digest(root):
    out = {}
    for dp, _, fs in os.walk(os.path.join(root, 'game')):
        for fn in fs:
            with open(os.path.join(dp, fn), 'rb') as f:
                out[os.path.relpath(os.path.join(dp, fn), root)] = hashlib.md5(f.read()).hexdigest()
    return out


def test_apply_disable_restore():
    root = tempfile.mkdtemp()
    _game(root)
    g = G.Game(root)
    g.index()
    lib = M.Library(g)
    stock = _digest(root)
    src = os.path.join(root, 'new.bin')
    a, b = lib.create('First'), lib.create('Second')
    for mod, data in ((a, b'AAAA'), (b, b'BBBBBBBB')):
        with open(src, 'wb') as f:
            f.write(data)
        lib.add_file(mod, 'A/ONE.BIN', src)
    assert lib.pending()
    changed, problems = lib.apply(log=lambda *_: None)
    assert not problems and set(changed) == {'A/ONE.BIN'}
    with open(g.path('A/ONE.BIN'), 'rb') as f:
        assert f.read() == b'BBBBBBBB'          # the lower mod wins
    with open(g.tsv) as f:
        assert f.readline().split('\t')[0] == '8'
    lib.move(b, -1)                              # now First is lower
    lib.apply(log=lambda *_: None)
    with open(g.path('A/ONE.BIN'), 'rb') as f:
        assert f.read() == b'AAAA'
    for m in lib.list():
        lib.set_enabled(m, False)
    lib.apply(log=lambda *_: None)
    assert _digest(root) == stock                # everything off and applied is stock
    lib.set_enabled(lib.list()[0], True)
    lib.apply(log=lambda *_: None)
    assert _digest(root) != stock
    lib.restore(log=lambda *_: None)
    assert _digest(root) == stock                # and so is Restore Original Game


def test_restore_exe():
    root = tempfile.mkdtemp()
    with open(os.path.join(root, 'mlb.exe'), 'wb') as f:
        f.write(b'modded')
    assert not codemods.restore_exe(root)
    with open(os.path.join(root, 'mlb.original.exe'), 'wb') as f:
        f.write(b'stock')
    assert codemods.restore_exe(root)
    with open(os.path.join(root, 'mlb.exe'), 'rb') as f:
        assert f.read() == b'stock'
    assert not os.path.exists(os.path.join(root, 'mlb.original.exe'))


def test_drop_sets():
    text = 'set a A 0\nsite a main 10 1 2\nset b B 0\nsite b main 20 3 4\n'
    assert codemods.drop_sets(text, {'a'}) == 'set b B 0\nsite b main 20 3 4\n'
    sets, _, bad = codemods.parse(codemods.ARCADE)
    assert not bad and {'auto_pci', 'moonshot', 'perfect_perfect'} <= {s[0] for s in sets}


def test_switch_wiring():
    gen = tempfile.mkdtemp()
    os.makedirs(os.path.join(gen, 'main'))
    os.makedirs(os.path.join(gen, 'sdk'))
    with open(os.path.join(gen, 'main', 'main_0001.c'), 'w') as f:
        f.write('extern uint8_t rt_patch_on[];\nvoid f(void) { if (rt_patch_on[1]) {} else {} }\n')
    with open(os.path.join(gen, 'main', 'main_0002.c'), 'w') as f:
        f.write('void g(void) {}\n')
    table = 'set a MLB_A 0\nsite a main 10 1 2\nset b MLB_B 1\nsite b main 20 3 4\n'
    assert codemods.wire_switches(gen, table) == 1
    with open(os.path.join(gen, 'main', 'main_0001.c')) as f:
        text = f.read()
    assert 'rt_patch_on' not in text and 'mts_patch_on[1]' in text
    with open(os.path.join(gen, 'main', 'mts_switches.c')) as f:
        src = f.read()
    assert '{"a", "MLB_A", 0, "A"}' in src and '{"b", "MLB_B", 1, "B"}' in src and '#define MTS_SETS 2' in src
    assert 'VK_F2' in src and 'VK_F2' not in codemods.switch_source([('a', 'MLB_A', 0)], hotkeys=False)
    assert codemods.wire_switches(gen, '') == 0 and not os.path.exists(os.path.join(gen, 'main', 'mts_switches.c'))
    root = tempfile.mkdtemp()
    os.makedirs(os.path.join(root, 'logs'))
    codemods.write_switches(root, {'a': True, 'b': False})
    with open(os.path.join(root, codemods.SWITCH_FILE)) as f:
        assert 'a=1' in f.read()
    with open(os.path.join(root, 'logs', codemods.SWITCH_LOG), 'w') as f:
        f.write('Code mods built into this mlb.exe: 2\na=1 (launch switch)\nb=0 (default)\n')
    assert codemods.last_launch(root) == {'a': (True, 'launch switch'), 'b': (False, 'default')}
    with open(os.path.join(root, 'logs', 'mlb.log'), 'w') as f:
        f.write('[lm 0] {CrossXY: 1, 2, AimXY: 1, 2, ErrorXY: 0.16, -0.35, ErrorMag: 0.37}\n[lm 0] PERFECT PERFECT 0 1\n')
    assert codemods.last_swing(root) == {'error': 0.37, 'perfect': (0, 1)}


def test_shared_zip_rules():
    import zipfile
    from modtheshow import community
    d = tempfile.mkdtemp()
    good, bad = os.path.join(d, 'good.zip'), os.path.join(d, 'bad.zip')
    with zipfile.ZipFile(good, 'w') as z:
        z.writestr('Pack/mod.json', '{}')
        z.writestr('Pack/rosters/a.json', '{"teams": []}')
        z.writestr('Pack/textures/NSW/X.TEX/logo.png', b'png')
        z.writestr('Pack/code/x.patch', 'set a A 0\n')
    with zipfile.ZipFile(bad, 'w') as z:
        z.writestr('Pack/romfs/FRONTEND/STATS/ROSTERS.BIN', b'x')
        z.writestr('Pack/tool.exe', b'x')
        z.writestr('Pack/textures/../../evil.png', b'x')
    assert community.check_zip(good) == [] and len(community.check_zip(bad)) == 3


def test_layout_recipe_targets():
    from modtheshow import recipes
    root = tempfile.mkdtemp()
    os.makedirs(os.path.join(root, 'layouts'))
    with open(os.path.join(root, 'layouts', 'a.json'), 'w') as f:
        f.write('[{"file": "nsw/ui/game/theme1.nsw", "asset": "Scorebar", "x": 1, "y": 2}]')

    class M:
        path, name = root, 'm'
    assert recipes.layout_targets([M]) == ['NSW/UI/GAME/THEME1.NSW'] and recipes.count(root) == 1


def test_roster_keys():
    assert rosterjson._height('6\'2"') == 74 and rosterjson._height(74) == 74 and rosterjson._height('6-0') == 72
    assert rosterjson.RATING_KEYS['power_vs_r'] == 'POWER_RIGHT' and rosterjson._pos('SP') == 0
    import json
    assert json.loads(rosterjson.dump(rosterjson.SAMPLE))['teams'][0]['players'][0]['last'] == 'Ruth'

def test_uniform_builder():
    from PIL import Image
    from modtheshow import uniformbuilder as UB
    img = Image.new('RGBA', (256, 128), (240, 240, 225, 200))
    for x in range(100, 110):
        for y in range(128):
            img.putpixel((x, y), (170, 30, 50, 200))
    pal = UB.palette(img)
    assert max(abs(a - b) for a, b in zip(pal[0][0], (240, 240, 225))) < 6 and len(pal) == 2, pal
    logo = Image.new('RGBA', (20, 20), (0, 0, 255, 255))
    out = UB.apply(img, [(pal[0][0], (10, 20, 120))], dict(color=(255, 255, 255), spacing=16, width=2),
                   dict(image=logo, x=0.75, y=0.5, width=0.1))
    assert out.size == img.size and out.getpixel((5, 5))[3] == 200            # the mask is kept
    assert max(abs(a - b) for a, b in zip(out.getpixel((5, 5))[:3], (10, 20, 120))) < 8      # fabric recoloured
    assert out.getpixel((105, 60))[:3] == (170, 30, 50)                       # trim untouched, no stripe over it
    assert out.getpixel((32, 60))[:3] == (255, 255, 255)                      # a pinstripe on the fabric
    assert out.getpixel((192, 64))[:3] == (0, 0, 255)                         # the logo


def test_name_hash():
    from modtheshow import uilayout
    assert uilayout.name_hash('PBInterface\\ScoreBar') == 0xF3657054          # a layout asset
    assert uilayout.name_hash('ACT_SCOREBAR_OFF') == 0xA80D1C39                # an animation action
    assert uilayout.name_hash('circle_32x32') == uilayout.name_hash('CIRCLE_32X32') == 0xBD741E62   # a texture
    assert uilayout.name_hash('') == 0x80000000


def test_layout_restyle():
    import struct
    from modtheshow import uilayout
    # one asset: a frame group holding a piece that draws the texture "logo"

    def node(kind, x, y, w, h, ref=0x80000000):
        b = bytearray(0x50)
        b[0:4] = b'\xff\xff\xff\xff'
        struct.pack_into('<5f', b, 4, x, y, 0, w, h)
        struct.pack_into('<HHHH', b, 0x1E, 5, 5, 0x80, 0x80)
        b[0x26], b[0x27] = kind, 1
        struct.pack_into('<HI', b, 0x28, 0x184, 0)
        struct.pack_into('<I', b, 0x30, ref)
        return b
    piece = node(0x18, 10, 5, 40, 20, uilayout.name_hash('logo'))
    frame = node(0x0F, 100, 200, 300, 80)
    struct.pack_into('<I', frame, 0x38, 0x50)
    struct.pack_into('<I', frame, 0x48, 0xA0)
    struct.pack_into('<I', frame, 0x4C, 0x8001)
    body = bytearray(0x90)
    struct.pack_into('<QQ', body, 0, 0x90, 0x90 + 0xA0)
    body += frame + piece
    data = b'IFF0ASSH' + bytes(8) + b'VOIDASS0' + struct.pack('<II', 0x81234567, len(body)) + bytes(body)
    lay = uilayout.Layout(data)
    a = lay.assets[0]
    table = uilayout.Layout.texture_table(['logo', 'other'])
    assert list(lay.pieces(a, table)) == ['logo']
    assert lay.restyle(a, [{'texture': 'LOGO', 'color': '#ff8000', 'opacity': 50, 'dx': 3, 'size': 2, 'use': 'other'}]) == 1
    n = uilayout.Layout(lay.bytes()).assets[0].nodes()[1]
    assert (n.rgba(), n.x, n.y, n.w, n.h) == ((255, 128, 0, 127), 13, 5, 80, 40) and table[n.ref] == 'other'
    assert lay.restyle(a, [{'texture': 'missing', 'opacity': 0}]) == 0

def test_sorted_saves_and_tidy():
    import tempfile
    from modtheshow import mods as M
    assert M.category_of('nsw/uniforms/al/bos/home/uniform.tex') == 'Uniforms'
    assert M.category_of('NSW/UI/GAME/THEME1.NSW') == 'Scoreboards'
    assert M.category_of('NSW/UI/ART/FONTS/FONTS.TEX') == 'Fonts'
    assert M.category_of('NSW/UI/FRONTEND/MAIN.TEX') == 'Menus' and M.category_of('X/Y') == 'Other'
    root = tempfile.mkdtemp()

    class G:
        mods = root
    lib = M.Library(G())
    code = lib.create('Arcade Code Mods')

    def put(mod, *parts):
        p = os.path.join(mod.path, *parts)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, 'w').write('x')
    put(code, 'code', 'arcade.patch')
    put(code, 'romfs', 'NSW', 'UI', 'GAME', 'THEME1.NSW')
    put(code, 'textures', 'NSW', 'UNIFORMS', 'AL', 'BOS', 'HOME', 'UNIFORM.TEX', 'jersey.png')
    assert code.categories() == ['Uniforms', 'Scoreboards', 'Code']
    moved = lib.tidy()
    assert sorted(c for _, c, _ in moved) == ['Scoreboards', 'Uniforms']
    by = {m.name: m for m in lib.list()}
    assert by['Arcade Code Mods'].categories() == ['Code']
    assert by['My Uniforms'].categories() == ['Uniforms'] and by['My Scoreboards'].categories() == ['Scoreboards']
    assert 'Uniforms' in by['My Uniforms'].changes() and lib.tidy() == []
    assert lib.workspace('Uniforms').folder == by['My Uniforms'].folder and lib.workspace('Sounds') is None
    lib.delete(by['My Uniforms'])
    assert 'My Uniforms' not in {m.name for m in lib.list()}


if __name__ == '__main__':
    test_apply_disable_restore()
    test_restore_exe()
    test_drop_sets()
    test_switch_wiring()
    test_shared_zip_rules()
    test_layout_recipe_targets()
    test_roster_keys()
    test_uniform_builder()
    test_name_hash()
    test_layout_restyle()
    test_sorted_saves_and_tidy()
    print('ok')
