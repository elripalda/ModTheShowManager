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

        self._raw, self._flags, self._parts, self._plain = raw, flags, {}, None

    def word(self, off):
        o = off - self.base
        if o < 0 or o + 4 > len(self.text):
            return None
        return struct.unpack_from('<I', self.text, o)[0]

    def u64(self, off):
        """Eight bytes at a module offset in the read-only or the writable data (a pointer the linker filled in), or
        None."""
        import lz4.block
        for i in (1, 2):
            file_off, mem, size = struct.unpack_from('<III', self._raw, 0x10 + 0x10 * i)
            if mem <= off and off + 8 <= mem + size:
                if i not in self._parts:
                    packed = struct.unpack_from('<I', self._raw, 0x60 + 4 * i)[0]
                    data = self._raw[file_off:file_off + packed]
                    self._parts[i] = lz4.block.decompress(data, uncompressed_size=size) if self._flags & (1 << i) \
                        else data[:size]
                return struct.unpack_from('<Q', self._parts[i], off - mem)[0]
        return None

    def plain(self):
        """The code as numbers, one per instruction, with everything that only says where something else is taken
        out: where a branch goes, which page an address is on, how far into the page. Two builds of the game that
        compiled a routine the same way give the same numbers for it, wherever the routine and its data ended up."""
        if self._plain is None:
            import numpy as np
            w = np.frombuffer(self.text, dtype='<u4', count=len(self.text) // 4).astype(np.uint32)
            m = w.copy()
            m[(w & 0x7C000000) == 0x14000000] &= 0xFC000000                     # b, bl
            m[((w & 0xFF000010) == 0x54000000) | ((w & 0x7E000000) == 0x34000000)] &= 0xFF00001F   # b.cond, cbz, cbnz
            m[(w & 0x7E000000) == 0x36000000] &= 0xFFF8001F                     # tbz, tbnz
            m[(w & 0x1F000000) == 0x10000000] &= 0x9F00001F                     # adr, adrp
            m[(w & 0x3B000000) == 0x18000000] &= 0xFF00001F                     # ldr from a literal
            # an add or a load/store that finishes an address an adrp started (same register, up to three before)
            use = ((w & 0x7F800000) == 0x11000000) | ((w & 0x3B000000) == 0x39000000)
            base = (w >> 5) & 31
            for back in (1, 2, 3):
                prev = np.roll(w, back)
                m[use & ((prev & 0x9F000000) == 0x90000000) & ((prev & 31) == base)] &= 0xFFC003FF
            self._plain = m
        return self._plain


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


PC_RELATIVE = ((0x7C000000, 0x14000000), (0xFF000010, 0x54000000), (0x7E000000, 0x34000000), (0x7E000000, 0x36000000),
               (0x1F000000, 0x10000000), (0x3B000000, 0x18000000))


def pc_relative(word):
    """An instruction whose meaning depends on where it sits (a branch, an address worked out from here)."""
    return any(word & mask == value for mask, value in PC_RELATIVE)


def around(code, off, reach=12):
    """The plain numbers of the instructions around a module offset: what a place in the code looks like."""
    i = (off - code.base) // 4
    return [int(x) for x in code.plain()[i - reach:i + reach + 1]]


def find(code, look, reaches=(12, 8, 5)):
    """Where in this game's code a place that looks like `look` (from around()) is: its module offset when there is
    exactly one, else None. A smaller neighbourhood is tried when the whole one is not there, since an update can
    change an instruction nearby and leave the place itself alone."""
    import numpy as np
    plain = code.plain()
    mid = len(look) // 2
    for reach in reaches:
        if reach > mid:
            continue
        part = look[mid - reach:mid + reach + 1]
        hits = np.nonzero(plain[reach:len(plain) - reach] == np.uint32(part[reach]))[0] + reach
        for k, want in enumerate(part):
            if k == reach or not len(hits):
                continue
            hits = hits[plain[hits + (k - reach)] == np.uint32(want)]
        if len(hits) == 1:
            return int(hits[0]) * 4 + code.base
        if len(hits) > 1:
            return None                       # it looks like several places: not safe to pick one
    return None


def relocate(code, patch_text, looks, pointers=None):
    """A table moved to this game's code: (text, {set: how many of its sites moved}).

    looks: {offset in the version the table was written for: around() of it there}. A site whose instruction is not
    where the table says is looked for by what the code around it looks like, and when it is found in exactly one
    place the site line is rewritten for there. An original that is a branch or an address is taken as this game has
    it. A set with a replacement that depends on where it sits is not moved. Sites that still do not fit are left as
    they are, for misfits() to report.

    pointers: {name: (offset of an adrp, bytes on to the load that finishes it)}: places where the code picks a
    pointer out of the linker's table. '#global <name> <offset>' lines are rewritten to what that pointer is in this
    game, or dropped when it cannot be found."""
    out, moved, stuck = [], {}, set()
    lines = patch_text.splitlines()
    for raw in lines:                         # first, which sets cannot be moved at all
        f = raw.split('#', 1)[0].split()
        if len(f) >= 6 and f[0] == 'site' and f[2] == 'main':
            try:
                orig = int(f[4], 16)
                words = [int(w, 16) for w in f[5:] if not w.startswith(('$', '@'))]
            except ValueError:
                continue
            if any(pc_relative(w) and w != orig for w in words):
                stuck.add(f[1])
    for raw in lines:
        f = raw.split('#', 1)[0].split()
        g = raw.split()
        if len(g) == 3 and g[0] == '#global' and pointers and g[1] in pointers:
            at = _pointer(code, looks, *pointers[g[1]])
            if at is not None:
                out.append(f'#global {g[1]} {at:x}')
            continue
        if len(f) >= 6 and f[0] == 'site' and f[2] == 'main':
            try:
                off, orig = int(f[3], 16), int(f[4], 16)
            except ValueError:
                out.append(raw)
                continue
            if code.word(off) != orig and off in looks and f[1] not in stuck:
                at = find(code, looks[off])
                have = code.word(at) if at is not None else None
                if have is not None and (have == orig or pc_relative(orig)):
                    f[3] = f'{at:x}'
                    f = [f'{have:08x}' if i >= 4 and w.lower() == f'{orig:08x}' else w for i, w in enumerate(f)]
                    raw = ' '.join(f)
                    moved[f[1]] = moved.get(f[1], 0) + 1
        out.append(raw)
    return '\n'.join(out) + '\n', moved


def _pointer(code, looks, adrp_off, on):
    """The pointer the code loads with the adrp at adrp_off (as written for the version the table was made for) and
    the load `on` bytes after it."""
    at = adrp_off
    if adrp_off in looks and around(code, adrp_off, len(looks[adrp_off]) // 2) != looks[adrp_off]:
        at = find(code, looks[adrp_off])
    if at is None:
        return None
    a, load = code.word(at), code.word(at + on)
    if a is None or load is None or a & 0x9F000000 != 0x90000000 or load & 0xFFC00000 != 0xF9400000:
        return None
    imm = ((a >> 5) & 0x7FFFF) << 2 | ((a >> 29) & 3)
    if imm & 0x100000:
        imm -= 0x200000
    slot = (at & ~0xFFF) + (imm << 12) + ((load >> 10) & 0xFFF) * 8
    return code.u64(slot)


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
