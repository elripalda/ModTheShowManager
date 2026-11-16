import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from modtheshow import codemods, xvagwrite  # noqa: E402
import numpy as np  # noqa: E402


def test_parse():
    sets, lines, bad = codemods.parse('# note\nset fast MLB_MOD_FAST 1\nsite fast main 1a2b 1e202008 1e204008\n')
    assert sets == [('fast', 'MLB_MOD_FAST', 1)] and len(lines) == 2 and not bad
    _, _, bad = codemods.parse('site nope main 10 0 0\nrubbish\n')
    assert len(bad) == 2


def test_adpcm_round_trip():
    t = np.arange(4000) / 48000
    x = np.sin(2 * np.pi * 440 * t) * 9000
    data, n = xvagwrite.encode_channel(x)
    y = xvagwrite.decode_channel(data)[:len(x)]
    assert n >= len(x) and 10 * np.log10((x ** 2).mean() / ((x - y) ** 2).mean()) > 35


if __name__ == '__main__':
    test_parse()
    test_adpcm_round_trip()
    print('ok')
