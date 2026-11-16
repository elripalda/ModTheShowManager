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


if __name__ == '__main__':
    test_apply_disable_restore()
    test_restore_exe()
    test_drop_sets()
    test_switch_wiring()
    test_shared_zip_rules()
    test_layout_recipe_targets()
    test_roster_keys()
    print('ok')
