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


def test_roster_mods_combine():
    """Two mods that each carry the roster file are laid over the original in turn, not one over the other."""
    d = tempfile.mkdtemp()
    def put(name, data):
        with open(os.path.join(d, name), 'wb') as f:
            f.write(data)
        return os.path.join(d, name)
    orig = put('o', bytes(range(16)))
    a = put('a', bytes([0, 1, 99, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]))
    b = put('b', bytes([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 77, 12, 13, 14, 15]))
    c = put('c', bytes([0, 1, 55, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]))
    assert M.stack_files(orig, [a, b]) == bytes([0, 1, 99, 3, 4, 5, 6, 7, 8, 9, 10, 77, 12, 13, 14, 15])
    assert M.stack_files(orig, [a, c])[2] == 55 and M.stack_files(orig, [c, a])[2] == 99       # the later one wins
    assert M.stack_files(orig, [a, put('short', b'123')]) is None
    assert M.STACKABLE.match('FRONTEND/STATS/PLAYERS_LIVE.BIN') and not M.STACKABLE.match('NSW/UI/X.TEX')
    # and through a real Apply: both mods' changes land in the game's file, and restoring puts the original back
    root = tempfile.mkdtemp()
    rel = 'FRONTEND/STATS/PLAYERS.BIN'
    p = os.path.join(root, 'game', 'romfs', *rel.split('/'))
    os.makedirs(os.path.dirname(p))
    with open(p, 'wb') as f:
        f.write(bytes(range(16)))
    with open(os.path.join(root, 'game', 'romfs_list.tsv'), 'w', newline='') as f:
        f.write(f'16\t0\t/{rel}\n')
    g = G.Game(root)
    g.index()
    lib = M.Library(g)
    for name, src in (('Bats', a), ('Power', b)):
        lib.add_file(lib.create(name), rel, src)
    assert not lib.conflicts() and list(lib.stacks()) == [rel]
    lib.apply(log=lambda *_: None)
    with open(p, 'rb') as f:
        assert f.read() == bytes([0, 1, 99, 3, 4, 5, 6, 7, 8, 9, 10, 77, 12, 13, 14, 15])
    lib.restore(log=lambda *_: None)
    with open(p, 'rb') as f:
        assert f.read() == bytes(range(16))


def test_drop_sets():
    text = 'set a A 0\nsite a main 10 1 2\nset b B 0\nsite b main 20 3 4\n'
    assert codemods.drop_sets(text, {'a'}) == 'set b B 0\nsite b main 20 3 4\n'
    sets, _, bad = codemods.parse(codemods.ARCADE)
    assert not bad and {'auto_pci', 'exit_velocity', 'air', 'perfect_perfect', 'pitch_speed', 'pitch_break',
                        'power_bunts', 'bouncy_ball'} <= {s[0] for s in sets}


def test_built_in_code_mods():
    """The manager's own code mods are always in the list, without a mod; a mod's code is in whether the mod is on
    or off; a set two files carry is taken once; the old samples mod is skipped."""
    class M:
        def __init__(self, name, files):
            self.name, self.enabled = name, False
            self.path = tempfile.mkdtemp()
            os.makedirs(os.path.join(self.path, 'code'))
            for f, text in files.items():
                with open(os.path.join(self.path, 'code', f), 'w') as fh:
                    fh.write(text)
    mine = M('Zed', {'z.patch': '#group Mine\n#: zed: Does zed.\n#tag zed: New\nset zed MLB_ZED 0\nsite zed main 10 1 2\n'
                                'set air MLB_AIR2 0\nsite air main 20 3 4\n'})
    old = M(codemods.ARCADE_NAME, {'arcade.patch': 'set moonshot MLB_MOD_MOONSHOT 0\nsite moonshot main 167d0b4 1 2\n'})
    sets, text, bad = codemods.collect([mine, old])
    names = [s[0] for s in sets]
    assert not bad and names[0] == 'exit_velocity' and names[-1] == 'zed' and 'moonshot' not in names
    assert names.count('air') == 1 and dict((s[0], s[3]) for s in sets)['air'] == codemods.BUILT_IN
    assert 'site air main 20' not in text and dict((s[0], s[3]) for s in sets)['zed'] == 'Zed'
    groups = codemods.grouped(sets)
    assert [g for g, _ in groups][0] == 'Hitting' and groups[-1][0] == 'Mine'
    assert codemods.TAGS['zed'] == 'New' and codemods.DESCRIPTIONS['zed'] == 'Does zed.'
    assert codemods.signature(text) and codemods.signature(text) == codemods.signature(codemods.collect([mine])[1])


def test_dials():
    table = ('#dial power 1.5 0.5 4 0.25 Power x\n#dial air 2 1 3 0.5 Air\nset boost MLB_BOOST 0\n'
             'site boost main 10 1e210800 1e210800 $power:s1 1e210800 $air:s2\nset plain MLB_PLAIN 1\n'
             'site plain main 20 1 2\n')
    sets, lines, bad = codemods.parse(table)
    assert not bad and lines[0].startswith('#dial power')
    assert codemods.parse('set a MLB_A 0\nsite a main 10 1 $nope:s1\n')[2]            # a dial nobody defined
    assert codemods.dials(table)[0] == ('power', 1.5, 0.5, 4.0, 0.25, 'Power x')
    assert codemods.set_dials(table) == {'boost': ['power', 'air']} and codemods.dial_uses(table) == 2
    assert codemods.menu_rows(table) == [(0, 1, 1), (0, 2, 0), (1, 0, 1)]
    low = codemods.lower(table)
    assert 'site boost main 10 1e210800 1e210800 1e3e3001 1e3e3001 1e210800 1e3e5002 1e3e5002' in low and '$' not in low
    # the generator writes the placeholder as a float's bits; the manager swaps in the live number and a counter
    # (a number a real patch loads once, like the -1.5 here, is left alone)
    chunk = ('extern uint8_t rt_patch_on[];\nvoid f(Cpu *c) {\n    if (rt_patch_on[0]) { c->v[1] = 0xbf880000ull; '
             'c->v[1] = 0xbf880000ull; c->v[2] = 0xbf900000ull; c->v[2] = 0xbf900000ull; c->v[24] = 0xbfc00000ull; } '
             'else { c->v[1] = 0xbf880000ull; }\n}\n')
    wired = codemods.wire_chunk(chunk)
    assert ('if (mts_patch_on[0]) { mts_ran[0]++; c->v[1] = (uint64_t)mts_dial[1]; c->v[2] = (uint64_t)mts_dial[2]; '
            'c->v[24] = 0xbfc00000ull; }') in wired
    assert 'extern uint32_t mts_dial[];' in wired and codemods.wire_chunk(wired) == wired
    # when the live dials cannot be connected they are built in as fixed numbers
    frozen = codemods.freeze(table, {'power': 3})
    assert '#dial' not in frozen and 'site boost main 10 1e210800 1e210800 1e211001 1e210800 1e201002' in frozen
    assert codemods.fmov_word(1.25, 1) == (0x1e2e9001, 1.25) and codemods.fmov_word(0.3, 0)[1] == 0.296875
    src = codemods.switch_source(codemods.table_sets(table), codemods.MENU_FULL, codemods.dials(table),
                                 codemods.menu_rows(table))
    assert '#define MTS_DIALS 2' in src and '{"power", "Power x", 1.5f, 0.5f, 4.0f, 0.25f}' in src
    assert 'input_block(on)' in src and '#define MTS_SEAMS 1' in src and 'GetForegroundDrawList' in src
    plain = codemods.switch_source(codemods.table_sets(table), codemods.MENU_PLAIN, codemods.dials(table))
    assert '#define MTS_SEAMS 0' in plain and 'VK_F4' in plain
    assert 'VK_F4' not in codemods.switch_source(codemods.table_sets(table), codemods.MENU_NONE)
    root = tempfile.mkdtemp()
    os.makedirs(os.path.join(root, 'logs'))
    codemods.write_switches(root, {'boost': True}, {'power': 2.25})
    assert codemods.read_switches(root) == {'boost': True} and codemods.read_dials(root) == {'power': 2.25}
    assert codemods.last_activity(root) is None
    with open(os.path.join(root, 'logs', codemods.SWITCH_LOG), 'w') as f:
        f.write('Code mods built into this mlb.exe: 2\nboost=1 (mts-code.cfg)\nplain=0 (default)\n'
                'dial power=2.250\nran boost=41\nran plain=0\n')
    assert codemods.last_activity(root) == {'boost': 41, 'plain': 0}
    assert codemods.last_launch(root) == {'boost': (True, 'mts-code.cfg'), 'plain': (False, 'default')}
    with open(os.path.join(root, 'logs', 'mlb.log'), 'w') as f:
        f.write('[lm 0] Actual Pitch Movement: 0.712, .0.287, (0.768 ft)\nAutoHit::m_fPowerMPH\t\t= 99.013588f;\n'
                'AutoHit::m_fAirDensity\t= 0.302412f;\nAutoHit::m_fPowerMPH\t\t= 107.430801f;\n')
    assert codemods.last_game(root) == {'hits': 2, 'hardest': 107.430801, 'air': 0.302412, 'breaks': 1,
                                        'biggest_break': 0.768, 'usual_break': 0.768}
    with open(os.path.join(root, 'logs', 'mlb.log'), 'a') as f:
        f.write('[lm 0] Hit Type: BUNT\n[lm 0] AUTO WIND  x = 0.000 y = 0.000 z = 0.000\n[lm 0] Hit Direction: 3B LINE\n'
                '[lm 0] AutoHit::m_fAzimuthAngle\t= 31.5f;\nAutoHit::m_fInclineAngle\t= -7.8f;\n'
                'AutoHit::m_fPowerMPH\t\t= 88.5f;\n')
    assert codemods.last_game(root)['hardest_bunt'] == 88.5 and codemods.last_game(root)['bunts'] == 1


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
    assert 'rt_patch_on' not in text and 'if (mts_patch_on[1]) { mts_ran[1]++;' in text
    with open(os.path.join(gen, 'main', 'mts_switches.c')) as f:
        src = f.read()
    assert '{"a", "MLB_A", 0, "A", ""}' in src and '{"b", "MLB_B", 1, "B", ""}' in src and '#define MTS_SETS 2' in src
    assert 'VK_F2' in src and 'VK_F2' not in codemods.switch_source([('a', 'MLB_A', 0)], codemods.MENU_NONE)
    assert codemods.wire_switches(gen, table) == 1                 # a second pass changes nothing
    with open(os.path.join(gen, 'main', 'main_0001.c')) as f:
        assert f.read() == text
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
    # a saved style: only the bytes that changed, put back onto the game's own file
    import json
    import tempfile
    from modtheshow import recipes
    root = tempfile.mkdtemp()
    live = os.path.join(root, 'T.NSW')
    with open(live, 'wb') as f:
        f.write(data)

    class G:
        def path(self, rel):
            return live

        def original(self, rel):
            return live

    class Mo:
        path, name = os.path.join(root, 'm'), 'm'
    entry = recipes.style_recipe('T.NSW', lay, live)
    assert entry['runs'] and 'asset' not in entry
    os.makedirs(os.path.join(Mo.path, 'layouts'))
    with open(os.path.join(Mo.path, 'layouts', 's.json'), 'w') as f:
        json.dump([entry], f)
    problems = []
    recipes.apply_layouts(G(), [Mo()], problems)
    with open(live, 'rb') as f:
        assert not problems and f.read() == lay.bytes(), problems
    entry['of'] = '0' * 40                                   # made for another version of the file: refused
    with open(os.path.join(Mo.path, 'layouts', 's.json'), 'w') as f:
        json.dump([entry], f)
    recipes.apply_layouts(G(), [Mo()], problems)
    assert len(problems) == 1 and 'different version' in problems[0]
    # a package's palette recipe: the file's painted colours moved onto a scorebug's, with none of the file in the mod
    from modtheshow import boards
    with open(live, 'wb') as f:
        f.write(lay.bytes())
    with open(os.path.join(Mo.path, 'layouts', 's.json'), 'w') as f:
        json.dump([{'file': 'T.NSW', 'match': ['#ffffff', '#ffd24a', '#0a0c10'], 'keep': False}], f)
    want = uilayout.Layout(lay.bytes())
    plan = boards.match(want, ['#ffffff', '#ffd24a', '#0a0c10'], keep_main=False)
    problems = []
    recipes.apply_layouts(G(), [Mo()], problems)
    with open(live, 'rb') as f:
        got = f.read()
    assert not problems and got == want.bytes(), problems
    assert plan

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
    test_roster_mods_combine()
    test_drop_sets()
    test_built_in_code_mods()
    test_dials()
    test_switch_wiring()
    test_shared_zip_rules()
    test_layout_recipe_targets()
    test_roster_keys()
    test_uniform_builder()
    test_name_hash()
    test_layout_restyle()
    test_sorted_saves_and_tidy()
    print('ok')


def test_metal_bats_allowed(tmp_path):
    from modtheshow import rosters as R
    text = ('{\n "makers": [{"id": 0, "name": "zGeneric"}],\n "eqlist": [\n'
            '  {"id": 1, "enb": 1, "enb_mobile": 0, "type": 0, "style": 0, "gfxinfo": "tx=$_$(B)_Tier1"},\n'
            '  {"id": 2, "enb": 0, "enb_mobile": 0, "type": 0, "style": 7, "gfxinfo": "mtl=1"},\n'
            '  {"id": 3, "enb": 0, "enb_mobile": 0, "type": 0, "style": 9, "gfxinfo": "tx=$_$(B)_Tier2"},\n'
            '  {"id": 4, "enb": 0, "enb_mobile": 0, "type": 3, "style": 7, "gfxinfo": "mtl=1"}\n ]\n}\n')
    out, n = R.allow_metal_bats(text)
    assert n == 1 and len(out) == len(text)
    assert [i for i, (a, b) in enumerate(zip(text, out)) if a != b] == [text.index('"id": 2') + len('"id": 2, "enb": ')]
    assert R.allow_metal_bats(out) == (out, 0)

    game = tmp_path / 'game'
    for rel, data in ((R.EQUIPMENT, text.encode()), (R.COLLEGE_SOUNDS, b'college'), (R.STADIUM_SOUNDS, b'stadium')):
        f = game / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)
    files = {R.EQUIPMENT, R.COLLEGE_SOUNDS, R.STADIUM_SOUNDS}
    src = lambda rel: str(game / rel)
    quiet = R.metal_bat_files(src, files, str(tmp_path))
    assert [rel for rel, _ in quiet] == [R.EQUIPMENT]
    loud = dict(R.metal_bat_files(src, files, str(tmp_path), sound=True))
    assert open(loud[R.EQUIPMENT], 'rb').read() == out.encode()
    assert open(loud[R.STADIUM_SOUNDS], 'rb').read() == b'college'
    assert R.metal_bat_files(src, {R.EQUIPMENT}, str(tmp_path), sound=True)[0][0] == R.EQUIPMENT


def test_effects_source():
    # a dial a mod reads by itself (#turns) belongs to its set like one a site loads, and goes when dials are frozen
    table = ('#dial heat 95 60 110 1 Fire from mph\n#turns fire heat\nset fire MLB_FIRE 0\n'
             'site fire main 10 fc1e0fe8 aa0003f0 fc1e0fe8\n')
    sets, lines, bad = codemods.parse(table)
    assert not bad and '#turns fire heat' in lines
    assert codemods.parse('#turns fire nope\nset fire MLB_FIRE 0\nsite fire main 10 1 2\n')[2]
    assert codemods.set_dials(table) == {'fire': ['heat']} and codemods.dial_uses(table) == 0
    assert codemods.menu_rows(table) == [(0, 1, 1)] and '#turns' not in codemods.freeze(table)
    # a site that opens with mov x16, xN hands the register over, however the generator keeps x16
    for x16 in ('c->x[16]', 'x16'):
        chunk = ('extern uint8_t rt_patch_on[];\nvoid f(Cpu *c) {\n    if (rt_patch_on[0]) { %s = (uint64_t)(0ull | x0); '
                 'sp_ = sp_ - 32; } else { sp_ = sp_ - 32; }\n}\n' % x16)
        wired = codemods.wire_chunk(chunk)
        assert 'mts_ran[0]++; %s = (uint64_t)(0ull | x0); mts_tap(0, %s); sp_' % (x16, x16) in wired
        assert 'void mts_tap(int set, uint64_t value);' in wired and codemods.wire_chunk(wired) == wired
    # the built-in list: its drawn effects are in, with what they read from the game
    sets, text, bad = codemods.collect([])
    names = [s[0] for s in sets]
    assert not bad and {'gravity', 'fireball', 'on_fire', 'fireworks'} <= set(names)
    assert codemods.GROUPS['fireball'] == 'Effects' and codemods.set_dials(text)['fireball'] == ['fire_from']
    full = codemods.switch_source(codemods.table_sets(text), codemods.MENU_FULL, codemods.dials(text),
                                  codemods.menu_rows(text))
    assert 'mts_fx_frame();' in full and '{FX}' not in full and 'AddCircleFilled' in full and 'VK_F6' in full
    assert 'void mts_tap(int set, uint64_t value)' in full and full.count('{') == full.count('}')
    none = codemods.switch_source(codemods.table_sets(text), codemods.MENU_NONE, codemods.dials(text))
    assert 'mts_fx_frame' not in none and 'void mts_tap(int set, uint64_t value)' in none
    root = tempfile.mkdtemp()
    os.makedirs(os.path.join(root, 'logs'))
    assert codemods.last_effects(root) == {}
    with open(os.path.join(root, 'logs', codemods.SWITCH_LOG), 'w') as f:
        f.write('ran fireball=12\nmenu opened=0 game_drew=0 window_shown=0\n'
                'fx frames=5120 camera=5120 ball=found node=found flights=31 lit=7 swings=18\n')
    assert codemods.last_effects(root) == {'frames': 5120, 'camera': 5120, 'ball': True, 'flights': 31, 'lit': 7,
                                           'swings': 18}


def test_code_mods_follow_the_game_version():
    import struct
    from modtheshow import exefile

    def code_of(words):
        c = exefile.Code.__new__(exefile.Code)
        c.text, c.base, c.build_id, c._plain = struct.pack(f'<{len(words)}I', *words), 0, 'x', None
        return c
    # a routine: unremarkable instructions, a call, the spot a mod changes, a branch, an address being built
    routine = [0x52800000 + (i << 5) for i in range(1, 13)] + [0x94000010, 0x1e210800, 0x54000041, 0x90000008,
                                                              0x91014108] + [0x52900000 + (i << 5) for i in range(1, 13)]
    filler = [0xd2800000 + (i << 5) for i in range(40)]
    old = code_of(filler + routine + filler[::-1])
    site = (40 + 13) * 4
    assert old.word(site) == 0x1e210800 and exefile.pc_relative(0x94000010) and not exefile.pc_relative(0x1e210800)
    look = exefile.around(old, site)
    assert len(look) == 25 and exefile.find(old, look) == site
    # the "update": the routine sits 7 instructions further on, its call, branch and address point elsewhere
    moved = [0x94000321 if w == 0x94000010 else 0x54000761 if w == 0x54000041 else 0xb0000048 if w == 0x90000008
             else 0x91000108 if w == 0x91014108 else w for w in routine]
    new = code_of(filler + [0xd503201f] * 7 + moved + filler[::-1])
    assert new.word(site) != 0x1e210800 and exefile.find(new, look) == site + 28
    table = 'set a MLB_A 0\nsite a main %x 1e210800 1e210800 1e210800\nset b MLB_B 0\nsite b main 10 1 2\n' % site
    assert set(exefile.misfits(new, table)) == {'a', 'b'}
    out, how = exefile.relocate(new, table, {site: look})
    assert how == {'a': 1} and 'site a main %x 1e210800 1e210800 1e210800' % (site + 28) in out
    assert set(exefile.misfits(new, out)) == {'b'}                     # a mod nobody has a picture of stays left out
    # a site on a branch takes the branch as this game has it; a replacement that depends on its place is not moved
    branch = (40 + 14) * 4
    t2 = 'set c MLB_C 0\nsite c main %x 54000041 d503201f 54000041\n' % branch
    out2, how2 = exefile.relocate(new, t2, {branch: exefile.around(old, branch)})
    assert how2 == {'c': 1} and 'site c main %x 54000761 d503201f 54000761' % (branch + 28) in out2
    t3 = 'set d MLB_D 0\nsite d main %x 1e210800 14000005\n' % site
    assert exefile.relocate(new, t3, {site: look})[1] == {}
    # two places that look alike: no guessing
    twins = code_of(filler + routine + routine + filler[::-1])
    assert exefile.find(twins, look, (5,)) is None
    # where the camera is travels with the table, into the effects' source
    sets, text, bad = codemods.collect([])
    assert codemods.globals_of(text) == {'camera': 0x28f51f8}
    src = codemods.switch_source(codemods.table_sets(text), codemods.MENU_FULL, codemods.dials(text),
                                 codemods.menu_rows(text), codemods.globals_of(text))
    assert '#define MTS_G_CAMERA 0x28f51f8ull' in src and '{G_CAMERA}' not in src
    assert '#define MTS_G_CAMERA 0x0ull' in codemods.switch_source(codemods.table_sets(text), codemods.MENU_FULL)
    from modtheshow import codesigs
    wanted = {int(f[3], 16) for f in (r.split('#', 1)[0].split() for r in codemods.ARCADE.splitlines())
              if len(f) >= 6 and f[0] == 'site'}
    assert wanted <= set(codesigs.LOOKS)                               # every built-in site has its picture


def test_old_stitching_goes_with_the_logo():
    # a part's normal texture keeps a sewn-on logo raised and shiny (alpha); when the colours no longer show the logo,
    # that goes, and a logo that is still there (recoloured or not) keeps it
    import numpy as np
    from PIL import Image, ImageDraw
    from modtheshow import uniformbuilder as UB
    color = Image.new('RGBA', (512, 256), (230, 230, 215, 255))
    d = ImageDraw.Draw(color)
    d.rectangle((100, 60, 180, 140), fill=(170, 20, 40, 255))          # the chest logo
    d.rectangle((380, 20, 400, 30), fill=(10, 30, 90, 255))            # a small league patch
    normal = Image.new('RGBA', (512, 256), (129, 128, 253, 0))
    d = ImageDraw.Draw(normal)
    d.rectangle((100, 60, 180, 140), fill=(128, 128, 128, 255))
    d.rectangle((380, 20, 400, 30), fill=(128, 128, 128, 255))
    assert UB.settle_normal(color, normal) is None
    assert UB.settle_normal(UB.apply(color, [((170, 20, 40), (20, 60, 200))]), normal) is None
    plain = color.copy()
    ImageDraw.Draw(plain).rectangle((90, 50, 190, 150), fill=(230, 230, 215, 255))
    out = np.asarray(UB.settle_normal(plain, normal))
    assert out[100, 140, 3] == 0 and tuple(out[100, 140, :3]) == (129, 128, 253)      # chest: flat and matte again
    assert out[25, 390, 3] == 255                                                     # the patch that stayed keeps its own
    assert UB.settle_normal(plain.resize((1024, 512)), normal) is not None            # a sharper colour texture too


def test_developer_switches(tmp_path):
    from modtheshow import devswitches as D
    from modtheshow.game import Game
    g = Game(str(tmp_path))
    os.makedirs(os.path.dirname(g.path(D.SHIPPED)))
    with open(g.path(D.SHIPPED), 'w') as f:
        f.write('#FastPlay\r\n## Always run AI vs AI game.\r\n#AIvAI\r\nInning=9\r\n')
    assert D.read(g) == set() and not D.write(g, set()) and not os.path.exists(g.path(D.USER))
    assert D.write(g, {'AIvAI', 'NoCrowd'}) and D.read(g) == {'AIvAI', 'NoCrowd'}
    lines = open(g.path(D.USER)).read().split()
    assert 'Inning=9' in lines and 'FastPlay' not in lines             # what the game's own file set stays set
    assert not D.write(g, set()) and not os.path.exists(g.path(D.USER))
    with open(g.path(D.USER), 'w') as f:                               # a file someone made by hand keeps their lines
        f.write('MySwitch\nNoTips\n')
    assert D.read(g) == {'NoTips'} and D.write(g, set()) and 'MySwitch' in open(g.path(D.USER)).read()
    assert D.write(g, {'NoDOF'}) and D.write(g, set()) and open(g.path(D.USER)).read().split() == ['MySwitch']
    # the two code mods in the Developer box are built in, and each writes its yes before the game reads it
    sets, text, bad = codemods.collect([])
    assert not bad and {'debug_menu', 'franchise_extras'} <= {s[0] for s in sets}
    assert codemods.GROUPS['debug_menu'] == 'Developer'
