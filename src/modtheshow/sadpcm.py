"""Sony SADPCM, the codec the Switch build's XVAG streams and SKX clips use (XVAG codec 0x0E).

Worked out from the game's own decoder (main+1b4ab80 in 1.0.15) and its filter table (main+1df27a0).

A frame is 96 bytes and holds 168 samples of one channel; channels take turns frame by frame. It is four groups of
42 samples that follow each other in time:

    4 x u32 (little endian), one per group:
        bits  0-11   second sample, signed 12 bit
        bits 12-23   first sample, signed 12 bit
        bits 24-27   filter (0-15)
        bits 28-31   shift
    80 bytes of 4-bit codes, high nibble first. Nibble k belongs to group k % 4, step k // 4, so the four groups
    are woven together and each gets 40 codes.

The two header samples are full values (x16 for 16-bit). Every sample after that is

    s[n] = k0 * s[n-1] + k1 * s[n-2] + (code << shift)

with k0, k1 from the filter table and code a signed nibble.
"""
import struct

import numpy as np

FRAME = 96
SAMPLES = 168
K = np.array([(0, 0), (0.9375, 0), (1.796875, -0.8125), (1.53125, -0.859375), (1.90625, -0.9375), (0.46875, 0),
              (0.8984375, -0.40625), (0.765625, -0.4296875), (0.953125, -0.46875), (0.234375, 0),
              (0.44921875, -0.203125), (0.3828125, -0.21484375), (0.4765625, -0.234375), (0.5, -0.234375),
              (0.234375, -0.234375), (0.109375, -0.234375)], np.float64)


def decode_frames(data, frames):
    """data: bytes of whole frames for ONE channel, back to back. Returns float samples in 16-bit units."""
    raw = np.frombuffer(data, np.uint8, frames * FRAME).reshape(frames, FRAME)
    head = raw[:, :16].copy().view('<u4')                                   # frames x 4 groups
    first = ((head >> 12) & 0xFFF).astype(np.int32)
    second = (head & 0xFFF).astype(np.int32)
    first = (first ^ 0x800) - 0x800
    second = (second ^ 0x800) - 0x800
    k0 = K[(head >> 24) & 0xF, 0]
    k1 = K[(head >> 24) & 0xF, 1]
    shift = (head >> 28).astype(np.int64)
    codes = raw[:, 16:]
    nib = np.empty((frames, 160), np.int64)
    nib[:, 0::2] = codes >> 4
    nib[:, 1::2] = codes & 0xF
    nib = (nib ^ 8) - 8
    nib = nib.reshape(frames, 40, 4)                                        # step, group
    delta = (nib << shift[:, None, :]).astype(np.float64)
    out = np.empty((frames, 4, 42), np.float64)
    s2 = first * 16.0
    s1 = second * 16.0
    out[:, :, 0] = s2
    out[:, :, 1] = s1
    for t in range(40):
        s = k0 * s1 + k1 * s2 + delta[:, t, :]
        out[:, :, t + 2] = s
        s2, s1 = s1, s
    return out.reshape(frames * SAMPLES)


def decode(data, channels, samples=None):
    """Interleaved frames for `channels` channels -> int16 array shaped (n, channels)."""
    frames = len(data) // (FRAME * channels)
    if frames <= 0:
        return np.zeros((0, channels), np.int16)
    raw = np.frombuffer(data, np.uint8, frames * channels * FRAME).reshape(frames, channels, FRAME)
    out = np.empty((frames * SAMPLES, channels), np.float64)
    for c in range(channels):
        out[:, c] = decode_frames(raw[:, c].tobytes(), frames)
    if samples:
        out = out[:samples]
    return np.clip(np.rint(out), -32768, 32767).astype(np.int16)


def xvag(data):
    """Parses an XVAG file held in memory. Returns (channels, rate, samples, codec, audio bytes)."""
    if data[:4] != b'XVAG':
        raise ValueError('not an XVAG file')
    start = struct.unpack_from('<I', data, 4)[0]
    i = data.find(b'fmat', 0, max(start, 0x400))
    if i < 0:
        raise ValueError('XVAG without a format chunk')
    channels, codec, samples = struct.unpack_from('<III', data, i + 8)
    rate = struct.unpack_from('<I', data, i + 0x1C)[0]
    return channels, rate, samples, codec, data[start:]


def to_wav(data, out_path):
    """XVAG bytes (codec 0x0E) -> a 16-bit WAV file. Returns (channels, rate, samples)."""
    import wave
    channels, rate, samples, codec, audio = xvag(data)
    if codec != 0x0E:
        raise ValueError(f'XVAG codec 0x{codec:02X} is not SADPCM')
    pcm = decode(audio, channels, samples)
    with wave.open(out_path, 'wb') as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate or 48000)
        w.writeframes(pcm.astype('<i2').tobytes())
    return channels, rate, len(pcm)


def encode_channel(x):
    """One channel of samples (16-bit units) -> SADPCM frames. Each group of 42 samples tries every filter and shift
    and keeps the pair that comes out closest; the decoder's arithmetic is mirrored exactly, so what the game will
    play is what was measured here."""
    x = np.asarray(x, np.float64)
    frames = max(1, -(-len(x) // SAMPLES))
    pad = np.zeros(frames * SAMPLES)
    pad[:len(x)] = x
    g = pad.reshape(frames * 4, 42)                              # groups in time order
    n = len(g)
    first = np.clip(np.rint(g[:, 0] / 16), -2048, 2047)
    second = np.clip(np.rint(g[:, 1] / 16), -2048, 2047)
    filt = np.repeat(np.arange(16), 13)                          # 208 candidates per group
    shift = np.tile(np.arange(13), 16)
    k0, k1 = K[filt, 0][None, :], K[filt, 1][None, :]
    step = (2.0 ** shift)[None, :]
    s2 = np.repeat(first[:, None] * 16.0, 208, 1)
    s1 = np.repeat(second[:, None] * 16.0, 208, 1)
    err = np.zeros((n, 208))
    codes = np.empty((n, 208, 40), np.int8)
    for t in range(40):
        pred = k0 * s1 + k1 * s2
        q = np.clip(np.rint((g[:, t + 2][:, None] - pred) / step), -8, 7)
        s = pred + q * step
        codes[:, :, t] = q
        err += (s - g[:, t + 2][:, None]) ** 2
        # a candidate that runs away past 16 bits would clip in the game; make it lose
        err += np.where(np.abs(s) > 32767, 1e12, 0.0)
        s2, s1 = s1, s
    best = err.argmin(1)
    rows = np.arange(n)
    bf, bs = filt[best], shift[best]
    bc = codes[rows, best]                                       # n x 40
    head = ((bs.astype(np.uint32) << 28) | (bf.astype(np.uint32) << 24) |
            ((first.astype(np.int64) & 0xFFF).astype(np.uint32) << 12) | (second.astype(np.int64) & 0xFFF).astype(np.uint32))
    out = np.zeros((frames, FRAME), np.uint8)
    out[:, :16] = head.astype('<u4').reshape(frames, 4).view(np.uint8).reshape(frames, 16)
    nib = (bc.reshape(frames, 4, 40).transpose(0, 2, 1).reshape(frames, 160) & 0xF).astype(np.uint8)   # step, group
    out[:, 16:] = (nib[:, 0::2] << 4) | nib[:, 1::2]
    return out.tobytes(), frames


def encode(pcm):
    """pcm shaped (channels, n) in 16-bit units -> (interleaved frame bytes, sample count)."""
    pcm = np.atleast_2d(np.asarray(pcm, np.float64))
    enc = [encode_channel(c) for c in pcm]
    frames = enc[0][1]
    per = [np.frombuffer(e[0], np.uint8).reshape(frames, FRAME) for e in enc]
    return np.stack(per, 1).tobytes(), pcm.shape[1]
