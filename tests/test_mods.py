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


def test_roster_keys():
    assert rosterjson._height('6\'2"') == 74 and rosterjson._height(74) == 74 and rosterjson._height('6-0') == 72
    assert rosterjson.RATING_KEYS['power_vs_r'] == 'POWER_RIGHT' and rosterjson._pos('SP') == 0
    import json
    assert json.loads(rosterjson.dump(rosterjson.SAMPLE))['teams'][0]['players'][0]['last'] == 'Ruth'


if __name__ == '__main__':
    test_apply_disable_restore()
    test_restore_exe()
    test_drop_sets()
    test_roster_keys()
    print('ok')
