"""Game audio: what's there, what it is, and turning it into WAV for listening.

The Switch build keeps its sound in NSW/AUDIO:
  BANK_STREAMS/**.XVAG   Sony XVAG streams (crowd beds, reactions) in SADPCM (codec 0x0E), decoded by sadpcm.py.
  BANK_STREAMS/**.AT9    RIFF WAVE files with ATRAC9 audio (dugout claps, short reactions).
  *.BNK                  Sony Scream sound banks ("SBlk"), many sounds each: bat cracks, mitt pops, menus.
  *.SKX + .CTL/.KEY/.TBL commentary, PA, chants and music archives: XVAG clips back to back. The .KEY file names
                         every sample and the .TBL file says where each one starts.

XVAG and SKX audio is decoded here. ATRAC9 and Scream banks go through vgmstream-cli (bundled with the Windows
build, vgmstream.org). Nothing here changes game files.
"""
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile

AUDIO_EXT = ('.XVAG', '.AT9', '.BNK')
XVAG_CODECS = {0x06: 'PS ADPCM', 0x09: 'ATRAC9', 0x0E: 'SADPCM'}
_CREATE_NO_WINDOW = 0x08000000


def vgmstream_path():
    here = os.path.dirname(os.path.abspath(__file__))
    for p in (os.path.join(here, 'assets', 'vgmstream', 'vgmstream-cli.exe'),
              os.path.join(here, 'assets', 'vgmstream', 'vgmstream-cli'),
              shutil.which('vgmstream-cli') or ''):
        if p and os.path.exists(p):
            return p
    return None


def _run(args, timeout=60):
    kw = {}
    if sys.platform == 'win32':
        kw['creationflags'] = _CREATE_NO_WINDOW
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, **kw)


def header_info(path):
    """Quick facts from the file header without decoding: {format, channels, rate, seconds, codec, note}."""
    with open(path, 'rb') as f:
        head = f.read(0x200)
    size = os.path.getsize(path)
    if head[:4] == b'XVAG':
        out = dict(format='XVAG stream')
        i = head.find(b'fmat')
        if i >= 0:
            ch, codec, samples = struct.unpack_from('<III', head, i + 8)
            rate = struct.unpack_from('<I', head, i + 0x1C)[0]
            out.update(channels=ch, rate=rate, seconds=samples / rate if rate else 0,
                       codec=XVAG_CODECS.get(codec, f'0x{codec:02X}'))
        return out
    if head[:4] == b'RIFF' and head[8:12] == b'WAVE':
        fmt = head.find(b'fmt ')
        tag, ch, rate = struct.unpack_from('<HHI', head, fmt + 8)
        fact = head.find(b'fact')
        seconds = struct.unpack_from('<I', head, fact + 8)[0] / rate if fact > 0 and rate else 0
        codec = 'ATRAC9' if head.find(bytes.fromhex('d242e147ba368d4d88fc61654f8c836c')) > 0 else f'0x{tag:04X}'
        return dict(format='RIFF WAVE', channels=ch, rate=rate, seconds=seconds, codec=codec)
    if head[0x20:0x24] == b'SBlk':
        name = head[0x40:0x80].split(b'\0')[0].decode('latin1', 'replace')
        return dict(format='Scream sound bank', codec='several', bank=name, size=size)
    return dict(format='unknown')


class Decoder:
    """Wraps vgmstream-cli. All calls are blocking; run them off the UI thread."""

    def __init__(self):
        self.exe = vgmstream_path()
        self.tmp = tempfile.mkdtemp(prefix='mts_audio_')

    @property
    def ok(self):
        return self.exe is not None

    def info(self, path, subsong=0):
        """{'streams': n, 'name': str, 'channels': n, 'rate': n, 'seconds': f} or {'error': text}."""
        if not self.exe:
            return {'error': 'The audio decoder (vgmstream) is not installed next to the manager.'}
        args = [self.exe, '-m', path]
        if subsong:
            args[2:2] = ['-s', str(subsong)]
        try:
            r = _run(args, 30)
        except Exception as x:
            return {'error': str(x)}
        text = r.stdout + r.stderr
        if r.returncode != 0 or 'failed opening' in text.lower():
            return {'error': 'The decoder could not read this file.'}
        out = {'streams': 1}
        m = re.search(r'stream count:\s*(\d+)', text)
        if m:
            out['streams'] = int(m.group(1))
        m = re.search(r'stream name:\s*(.+)', text)
        if m:
            out['name'] = m.group(1).strip()
        m = re.search(r'channels:\s*(\d+)', text)
        if m:
            out['channels'] = int(m.group(1))
        m = re.search(r'sample rate:\s*(\d+)', text)
        if m:
            out['rate'] = int(m.group(1))
        m = re.search(r'stream total samples:\s*(\d+)', text) or re.search(r'play duration:\s*(\d+) samples', text)
        if m and out.get('rate'):
            out['seconds'] = int(m.group(1)) / out['rate']
        m = re.search(r'encoding:\s*(.+)', text)
        if m:
            out['codec'] = m.group(1).strip()
        return out

    def to_wav(self, path, out_wav=None, subsong=0, stereo=False):
        """Decode to a WAV file (loops played once). Returns the WAV path or raises. stereo folds surround
        streams down to two channels, for listening."""
        if out_wav is None:
            base = re.sub(r'[^A-Za-z0-9_.-]+', '_', os.path.basename(path))
            out_wav = os.path.join(self.tmp, f'{base}_{subsong}{"_st" if stereo else ""}.wav')
        up = path.upper()
        if up.endswith('.SKX'):
            clip = skx_clip(path, subsong)
            if _xvag_codec(clip) == 0x0E:
                _sadpcm_wav(clip, out_wav, stereo)
                return out_wav
            # an ATRAC9 clip: hand it to vgmstream as a file of its own
            path = os.path.join(self.tmp, f'clip_{subsong}.xvag')
            with open(path, 'wb') as f:
                f.write(clip)
            subsong = 0
        if up.endswith('.XVAG'):
            with open(path, 'rb') as f:
                data = f.read()
            if _xvag_codec(data) == 0x0E:
                _sadpcm_wav(data, out_wav, stereo)
                return out_wav
        if not self.exe:
            raise RuntimeError('The audio decoder (vgmstream) is not installed next to the manager.')
        args = [self.exe, '-i', '-o', out_wav, path]
        if subsong:
            args[1:1] = ['-s', str(subsong)]
        r = _run(args, 120)
        if r.returncode != 0 or not os.path.exists(out_wav):
            raise RuntimeError('The decoder could not turn this sound into WAV.')
        return out_wav


def _xvag_codec(data):
    i = data.find(b'fmat', 0, 0x400)
    return struct.unpack_from('<I', data, i + 12)[0] if data[:4] == b'XVAG' and i >= 0 else None


def _sadpcm_wav(data, out_wav, stereo=False):
    import wave

    import numpy as np

    from . import sadpcm
    channels, rate, samples, codec, body = sadpcm.xvag(data)
    if codec != 0x0E:
        raise RuntimeError(f'XVAG codec 0x{codec:02X} is not one the manager decodes.')
    pcm = sadpcm.decode(body, channels, samples)
    if stereo and channels > 2:
        x = pcm.astype(np.float64)
        left, right = x[:, 0::2].mean(1), x[:, 1::2].mean(1) if channels > 1 else x[:, 0]
        pcm = np.clip(np.stack([left, right], 1) * 1.4, -32768, 32767).astype(np.int16)
        channels = 2
    with wave.open(out_wav, 'wb') as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate or 48000)
        w.writeframes(pcm.astype('<i2').tobytes())


def skx_table(skx_path):
    """Where each sample of an SKX archive starts: [(sample index, byte offset or None)]. Offsets come from the
    .TBL file next to it: the sector size is the u16 at 0x18 and 6-byte records start at 0x64 (u32 sector, u16
    kind). Kind 0x0100 is a timer delay with no audio (None here). Some archives count sectors from the start of
    the file and some from the end of the first sector, so the first sound is looked at to tell which."""
    with open(skx_path[:-4] + '.TBL', 'rb') as f:
        t = f.read()
    if t[:4] != b'STBL' or len(t) < 0x64:
        raise ValueError('not an SKX table')
    count = struct.unpack_from('<I', t, 8)[0]
    sector = struct.unpack_from('<H', t, 0x18)[0] or 0x800
    if 0x64 + count * 6 > len(t):
        raise ValueError('SKX table is shorter than its sample count')
    recs = [struct.unpack_from('<IH', t, 0x64 + i * 6) for i in range(count)]
    sounds = [v for v, kind in recs if kind != 0x0100]
    base = None
    with open(skx_path, 'rb') as f:
        for v in sounds[:8]:
            for cand in (0, sector):
                f.seek(v * sector + cand)
                if f.read(4) == b'XVAG':
                    base = cand
                    break
            if base is not None:
                break
    if base is None:                 # an archive of pauses and nothing else
        return [(i, None) for i in range(count)]
    return [(i, v * sector + base if kind != 0x0100 else None) for i, (v, kind) in enumerate(recs)]


def skx_clip(skx_path, index):
    """The XVAG file of one sample, as bytes."""
    table = skx_table(skx_path)
    if not 0 <= index < len(table) or table[index][1] is None:
        raise RuntimeError('That entry has no sound in it.')
    start = table[index][1]
    later = sorted(o for _, o in table if o is not None and o > start)
    end = later[0] if later else os.path.getsize(skx_path)
    with open(skx_path, 'rb') as f:
        f.seek(start)
        data = f.read(end - start)
    if data[:4] != b'XVAG':
        raise RuntimeError('The archive has no sound where its table says.')
    return data


def skx_info(skx_path, index):
    """{channels, rate, seconds, codec} of one sample without decoding it."""
    table = skx_table(skx_path)
    if not 0 <= index < len(table) or table[index][1] is None:
        return {}
    with open(skx_path, 'rb') as f:
        f.seek(table[index][1])
        head = f.read(0x200)
    i = head.find(b'fmat')
    if head[:4] != b'XVAG' or i < 0:
        return {}
    ch, codec, samples = struct.unpack_from('<III', head, i + 8)
    rate = struct.unpack_from('<I', head, i + 0x1C)[0]
    return dict(channels=ch, rate=rate, seconds=samples / rate if rate else 0,
                codec=XVAG_CODECS.get(codec, f'0x{codec:02X}'))


def skx_entries(key_path):
    """Samples listed in an SKX .KEY file (XML): [(index, name, script)]. script is the line being spoken, when
    the file has it."""
    import html
    try:
        with open(key_path, encoding='cp1252', errors='replace') as f:
            text = f.read()
    except OSError:
        return []
    out = []
    for v, attrs, n in re.findall(r'<SAMPLEFILE value="(\d+)"([^>]*)>([^<]+)</SAMPLEFILE>', text):
        m = re.search(r'script="([^"]*)"', attrs)
        out.append((int(v), html.unescape(n), html.unescape(m.group(1)) if m else ''))
    return out


def skx_names(key_path):
    """Sample names from an SKX .KEY file."""
    return [(v, n) for v, n, _ in skx_entries(key_path)]


class Player:
    """Plays a WAV without extra libraries (winsound on Windows)."""

    def __init__(self):
        try:
            import winsound
            self._ws = winsound
        except ImportError:
            self._ws = None

    @property
    def ok(self):
        return self._ws is not None

    def play(self, wav):
        if self._ws:
            self._ws.PlaySound(wav, self._ws.SND_FILENAME | self._ws.SND_ASYNC | self._ws.SND_NODEFAULT)

    def stop(self):
        if self._ws:
            self._ws.PlaySound(None, 0)
