"""Write a replacement .XVAG from a WAV, in the game's own codec (SADPCM, XVAG codec 0x0E; see sadpcm.py).

The replacement keeps the original's header, channel count and sample rate; only the length and the audio change.
The PS ADPCM (codec 6) coder further down is what replacements were written in before SADPCM was worked out.
"""
import struct
import wave

import numpy as np

COEF = [(0.0, 0.0), (60 / 64, 0.0), (115 / 64, -52 / 64), (98 / 64, -55 / 64), (122 / 64, -60 / 64)]


def read_wav(path):
    with wave.open(path, 'rb') as w:
        ch, width, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if width == 2:
        x = np.frombuffer(raw, '<i2').astype(np.float64)
    elif width == 1:
        x = (np.frombuffer(raw, np.uint8).astype(np.float64) - 128) * 256
    elif width == 3:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(np.int32)
        x = ((b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)) << 8 >> 16).astype(np.float64)
    elif width == 4:
        x = (np.frombuffer(raw, '<i4') >> 16).astype(np.float64)
    else:
        raise ValueError('unsupported WAV sample size')
    return x.reshape(-1, ch).T, rate


def fit(pcm, rate, channels, want_rate):
    """Match the original's channel count and sample rate (linear resample)."""
    if pcm.shape[0] != channels:
        mono = pcm.mean(0)
        pcm = np.stack([mono] * channels)
    if rate != want_rate and pcm.shape[1] > 1:
        n = int(round(pcm.shape[1] * want_rate / rate))
        src = np.linspace(0, pcm.shape[1] - 1, n)
        pcm = np.stack([np.interp(src, np.arange(pcm.shape[1]), c) for c in pcm])
    return pcm


def encode_channel(x):
    """PS ADPCM: 16-byte frames of 28 samples."""
    n = (len(x) + 27) // 28
    x = np.concatenate([x, np.zeros(n * 28 - len(x))])
    out = bytearray(n * 16)
    h1 = h2 = 0.0
    for f in range(n):
        blk = x[f * 28:f * 28 + 28]
        best = None
        for p, (c1, c2) in enumerate(COEF):
            # open loop residual picks the shift, then encode closed loop
            prev1 = np.concatenate([[h1], blk[:-1]])
            prev2 = np.concatenate([[h2, h1], blk[:-2]])
            peak = np.abs(blk - c1 * prev1 - c2 * prev2).max()
            shift = 12
            while shift > 0 and peak > (7.5 * (1 << (12 - shift))):
                shift -= 1
            step = float(1 << (12 - shift))
            a, b, err, nibs = h1, h2, 0.0, []
            for s in blk:
                pred = c1 * a + c2 * b
                q = int(round((s - pred) / step))
                q = -8 if q < -8 else 7 if q > 7 else q
                v = pred + q * step
                v = -32768.0 if v < -32768 else 32767.0 if v > 32767 else v
                err += (s - v) ** 2
                nibs.append(q & 15)
                b, a = a, v
            if best is None or err < best[0]:
                best = (err, p, shift, nibs, a, b)
        _, p, shift, nibs, h1, h2 = best
        o = f * 16
        out[o] = (p << 4) | shift
        out[o + 1] = 0
        for k in range(14):
            out[o + 2 + k] = nibs[2 * k] | (nibs[2 * k + 1] << 4)
    return bytes(out), n * 28


def decode_channel(data):
    out, h1, h2 = [], 0.0, 0.0
    for f in range(len(data) // 16):
        fr = data[f * 16:f * 16 + 16]
        c1, c2 = COEF[min(fr[0] >> 4, 4)]
        shift = fr[0] & 15
        for b in fr[2:]:
            for q in (b & 15, b >> 4):
                q = q - 16 if q >= 8 else q
                v = q * float(1 << (12 - shift)) + c1 * h1 + c2 * h2
                v = max(-32768.0, min(32767.0, v))
                out.append(v)
                h2, h1 = h1, v
    return np.array(out)


def build(original_path, wav_path, out_path):
    """Replacement for original_path (an XVAG) made from wav_path. Keeps the original's channels and sample rate."""
    from . import sadpcm
    with open(original_path, 'rb') as f:
        orig = f.read(0x1000)
    if orig[:4] != b'XVAG':
        raise ValueError('not an XVAG file')
    hdr = struct.unpack_from('<I', orig, 4)[0]
    fm = orig.find(b'fmat', 0, hdr)
    if fm < 0:
        raise ValueError('XVAG has no fmat chunk')
    channels, codec = struct.unpack_from('<II', orig, fm + 8)
    if codec != 0x0E:
        raise ValueError(f'this stream uses codec 0x{codec:02X}; only SADPCM (0x0E) streams can be replaced')
    rate = struct.unpack_from('<I', orig, fm + 0x1C)[0]
    pcm, wrate = read_wav(wav_path)
    pcm = np.clip(fit(pcm, wrate, channels, rate), -32768, 32767)
    data, samples = sadpcm.encode(pcm)
    head = bytearray(orig[:hdr])
    struct.pack_into('<II', head, fm + 0x10, samples, samples)
    struct.pack_into('<I', head, fm + 0x20, len(data))
    with open(out_path, 'wb') as f:
        f.write(head)
        f.write(data)
    return samples, rate, channels
