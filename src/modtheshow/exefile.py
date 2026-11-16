"""The game's code as installed: <game>/game/exefs/main (a Switch NSO), and what the install says about itself.

Code mods name an offset in this file and the instruction they expect to find there. Reading the file lets the manager
tell, before a build, which mods fit the game version that is installed.
"""
import json
import os
import struct

_CACHE = {}


class Code:
    """The .text of an NSO, by module offset."""

    def __init__(self, path):
        import lz4.block
        with open(path, 'rb') as f:
            raw = f.read()
        if raw[:4] != b'NSO0':
            raise ValueError('not an NSO file')
        flags = struct.unpack_from('<I', raw, 0xC)[0]
        file_off, self.base, size = struct.unpack_from('<III', raw, 0x10)
        packed = struct.unpack_from('<I', raw, 0x60)[0]
        data = raw[file_off:file_off + packed]
        self.text = lz4.block.decompress(data, uncompressed_size=size) if flags & 1 else data[:size]
        self.build_id = raw[0x40:0x60].rstrip(b'\0').hex()

    def word(self, off):
        o = off - self.base
        if o < 0 or o + 4 > len(self.text):
            return None
        return struct.unpack_from('<I', self.text, o)[0]


def main_path(game_root):
    return os.path.join(game_root, 'game', 'exefs', 'main')


def load(game_root):
    """Code of the installed game, or None when exefs/main is missing or unreadable. Cached per file version."""
    p = main_path(game_root)
    try:
        key = (p, os.path.getmtime(p), os.path.getsize(p))
    except OSError:
        return None
    if key not in _CACHE:
        _CACHE.clear()
        try:
            _CACHE[key] = Code(p)
        except Exception:
            _CACHE[key] = None
    return _CACHE[key]


def misfits(code, patch_text):
    """{set name: [text]} for the sets whose sites do not match this game's code."""
    out = {}
    for raw in patch_text.splitlines():
        f = raw.split('#', 1)[0].split()
        if len(f) >= 6 and f[0] == 'site' and f[2] == 'main':
            try:
                off, want = int(f[3], 16), int(f[4], 16)
            except ValueError:
                continue
            have = code.word(off)
            if have != want:
                out.setdefault(f[1], []).append(
                    f'main+{off:x} holds {"nothing" if have is None else format(have, "08x")}, the mod expects {want:08x}')
    return out


def install_info(game_root):
    """What the recomp wrote down about this install, plus a few things read off the folder."""
    info = {'release': '', 'built': '', 'play_seconds': 0, 'code_mods': False, 'exe_size': 0, 'build_id': ''}
    try:
        with open(os.path.join(game_root, 'mlbts-install.json'), encoding='utf-8') as f:
            doc = json.load(f)
        info['release'] = str(doc.get('release', ''))
        info['built'] = str(doc.get('steps', {}).get('build', {}).get('finished', ''))
    except (OSError, ValueError, AttributeError):
        pass
    try:
        with open(os.path.join(game_root, 'profile', 'playtime.txt'), encoding='utf-8') as f:
            for line in f:
                p = line.split()
                if len(p) == 2 and p[0] == 'total_seconds' and p[1].isdigit():
                    info['play_seconds'] = int(p[1])
    except OSError:
        pass
    info['code_mods'] = os.path.exists(os.path.join(game_root, 'mlb.original.exe'))
    try:
        info['exe_size'] = os.path.getsize(os.path.join(game_root, 'mlb.exe'))
    except OSError:
        pass
    return info


def read_cfg(game_root):
    """mlb.cfg as {KEY: value}."""
    out = {}
    try:
        with open(os.path.join(game_root, 'mlb.cfg'), encoding='utf-8', errors='replace') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    out[k.strip()] = v.strip()
    except OSError:
        pass
    return out


def write_cfg(game_root, changes):
    """Sets KEY=VALUE lines in mlb.cfg, keeping every other line as it is."""
    path = os.path.join(game_root, 'mlb.cfg')
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            lines = f.read().splitlines()
    except OSError:
        lines = []
    left = dict(changes)
    for i, line in enumerate(lines):
        s = line.strip()
        if s and not s.startswith('#') and '=' in s:
            k = s.split('=', 1)[0].strip()
            if k in left:
                lines[i] = f'{k}={left.pop(k)}'
    for k, v in left.items():
        lines += ['', f'{k}={v}']
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines) + '\n')
