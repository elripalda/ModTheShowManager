"""Game audio: what's there, what it is, and turning it into WAV for listening.

The Switch build keeps its sound in NSW/AUDIO:
  BANK_STREAMS/**.XVAG   Sony XVAG streams (crowd beds, reactions). Header parsed here; their Switch codec (0x0E)
                         is not decodable yet.
  BANK_STREAMS/**.AT9    RIFF WAVE files with ATRAC9 audio (dugout claps, short reactions).
  *.BNK                  Sony Scream sound banks ("SBlk"), many sounds each: bat cracks, mitt pops, menus.
  *.SKX + .CTL/.KEY/.TBL commentary, PA, chants and music archives; the .KEY file names every sample.

Decoding goes through vgmstream-cli (bundled with the Windows build, vgmstream.org), which reads ATRAC9 and Scream
banks. Nothing here changes game files.
"""
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile

AUDIO_EXT = ('.XVAG', '.AT9', '.BNK')
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
            out.update(channels=ch, rate=rate, seconds=samples / rate if rate else 0, codec=f'0x{codec:02X}')
            if codec == 0x0E:
                out['note'] = 'Switch codec 0x0E: listening to these is not possible yet.'
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

    def to_wav(self, path, out_wav=None, subsong=0):
        """Decode to a WAV file (loops played once). Returns the WAV path or raises."""
        if not self.exe:
            raise RuntimeError('The audio decoder (vgmstream) is not installed next to the manager.')
        if out_wav is None:
            base = re.sub(r'[^A-Za-z0-9_.-]+', '_', os.path.basename(path))
            out_wav = os.path.join(self.tmp, f'{base}_{subsong}.wav')
        args = [self.exe, '-i', '-o', out_wav, path]
        if subsong:
            args[1:1] = ['-s', str(subsong)]
        r = _run(args, 120)
        if r.returncode != 0 or not os.path.exists(out_wav):
            raise RuntimeError('The decoder could not turn this sound into WAV.')
        return out_wav


def skx_names(key_path):
    """Sample names from an SKX .KEY file (XML)."""
    try:
        with open(key_path, encoding='cp1252', errors='replace') as f:
            text = f.read()
    except OSError:
        return []
    return [(int(v), n) for v, n in re.findall(r'<SAMPLEFILE value="(\d+)">([^<]+)</SAMPLEFILE>', text)]


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
