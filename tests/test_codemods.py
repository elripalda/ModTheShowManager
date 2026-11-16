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


def test_sadpcm_round_trip():
    import struct
    import tempfile
    import wave
    from modtheshow import sadpcm
    t = np.arange(9000) / 48000
    x = np.sin(2 * np.pi * 440 * t) * 9000 + np.sin(2 * np.pi * 2500 * t) * 2000
    data, frames = sadpcm.encode_channel(x)
    assert len(data) == frames * 96 and frames == -(-len(x) // 168)
    y = sadpcm.decode_frames(data, frames)[:len(x)]
    assert 10 * np.log10((x ** 2).mean() / ((x - y) ** 2).mean()) > 30
    # two channels take turns frame by frame
    both, n = sadpcm.encode(np.stack([x, -x]))
    pcm = sadpcm.decode(both, 2, n)
    assert pcm.shape == (len(x), 2) and abs(float(pcm[2000, 0]) + float(pcm[2000, 1])) < 600
    # a replacement keeps the header and only changes the length and the audio
    d = tempfile.mkdtemp()
    head = bytearray(0x80)
    head[:4] = b'XVAG'
    struct.pack_into('<I', head, 4, 0x80)
    head[0x20:0x24] = b'fmat'
    struct.pack_into('<IIIIIIII', head, 0x24, 0x24, 1, 0x0E, 100, 100, 1, 48000, 9600)
    with open(d + '/o.xvag', 'wb') as f:
        f.write(head + bytes(9600))
    with wave.open(d + '/in.wav', 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(48000)
        w.writeframes(np.clip(x, -32768, 32767).astype('<i2').tobytes())
    samples, rate, ch = xvagwrite.build(d + '/o.xvag', d + '/in.wav', d + '/new.xvag')
    with open(d + '/new.xvag', 'rb') as f:
        new = f.read()
    c2, r2, n2, codec, body = sadpcm.xvag(new)
    assert (c2, r2, n2, codec) == (1, 48000, len(x), 0x0E) and len(body) == frames * 96
    z = sadpcm.decode(body, 1, n2)[:, 0]
    assert 10 * np.log10((x ** 2).mean() / ((x - z) ** 2).mean()) > 30


if __name__ == '__main__':
    test_parse()
    test_adpcm_round_trip()
    test_sadpcm_round_trip()
    print('ok')
