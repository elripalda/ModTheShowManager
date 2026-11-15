"""TX12NSW texture packs from MLB The Show 26 (Switch): read, export to PNG, replace from PNG.

File layout (little endian):
  0x00  char[8] "TX12NSW\\0"   0x08 u32 version (12)
  0x0C  u32 packed data size  0x10 u32 unpacked data size  0x14 u32 entry size (0x140)
  0x20  entries, 0x140 bytes each, then a lookup table, then the payloads
Entry:
  0x00  u64 hash  0x10 char[64] name  0x50 u8[16] hash  0xB0 preview descriptor (0xC0 size, 0xC4 u16 w, h)
  0x60  u32 unpacked size  0x64 u16 width  0x66 u16 height  0x68 u16 depth  0x6A u16 layers  0x6C u32 mip count
  0xD0  4 chunk records of 0x14 bytes: u32 unpacked size, u32 packed size, u32 offset from the payload start,
        u32 offset in the unpacked image, u8 ?, u8 first mip level, u8 level count, u8 ?
        Big textures split mip 0 / mip 1 / the rest; record 4 can hold a preview copy at most 32 pixels across.
  0x120 f32[4] average colour  0x130 u32 flags  0x134 u32 absolute payload offset  0x13C u16 pixel format
Each chunk: LZ4 block, Tegra X1 block-linear swizzle, one level after another.
"""
import math
import struct

import lz4.block  # noqa: E402

try:
    import numpy as np
except ImportError:      # the plain-Python path below still works, just slower
    np = None

ENTRY = 0x140
STRIP = 8   # block rows per decode/encode call: keeps native buffers small (big ones crash on Windows)

# pixel format -> (codec, bytes per block, block size in pixels, can import)
FORMATS = {
    0x16: ('bc7', 16, 4, True),
    0x07: ('bc3', 16, 4, True),
    0x0D: ('bc1', 8, 4, True),
    0x06: ('bc3', 16, 4, True),
    0x13: ('bc4', 8, 4, True),    # one channel (greyscale): barrel stamps, masks
    0x02: ('rgba', 4, 1, True),
    0x05: ('bc1', 8, 4, False),   # normal maps (UI)
    0x59: ('bc5', 16, 4, False),  # normal maps (stadiums)
}


def _div(a, b):
    return (a + b - 1) // b


class Tex:
    def __init__(self, path):
        self.path = path
        self.d = bytearray(open(path, 'rb').read())
        if self.d[:7] != b'TX12NSW':
            raise ValueError(f'{path}: not a TX12NSW texture pack')
        self.entries = []
        o, first = 0x20, len(self.d)
        while o + ENTRY <= first:
            e = self._entry(o)
            if not e['name'] or e['offset'] < o + ENTRY or e['offset'] >= len(self.d):
                break
            first = min(first, e['offset'])
            self.entries.append(e)
            o += ENTRY

    def _entry(self, o):
        d = self.d
        name = bytes(d[o + 0x10:o + 0x50]).split(b'\0')[0].decode('ascii', 'replace')
        _, w, h = struct.unpack_from('<IHH', d, o + 0x60)
        mips = struct.unpack_from('<I', d, o + 0x6C)[0] or 1
        usize, psize = struct.unpack_from('<II', d, o + 0xD0)
        flags, off = struct.unpack_from('<II', d, o + 0x130)
        fmt = struct.unpack_from('<H', d, o + 0x13C)[0]
        pw, ph = struct.unpack_from('<HH', d, o + 0xC4)   # preview descriptor (0xB0..0xCF), when there is one
        recs = []
        for i in range(4):
            u, p, r, x, fl = struct.unpack_from('<5I', d, o + 0xD0 + i * 0x14)
            if u:
                recs.append(dict(slot=i, usize=u, psize=p, rel=r, start=(fl >> 8) & 0xFF, count=(fl >> 16) & 0xFF))
        e = dict(pos=o, name=name, w=w, h=h, mips=mips, fmt=fmt, usize=usize, psize=psize, flags=flags, offset=off,
                 recs=recs, preview=(pw, ph) if pw and ph else None)
        e['levels'] = levels(e)
        if e['levels'] is not None:
            for c in recs:
                c['plan'] = chunk_plan(e, c)
        return e

    def find(self, name):
        return [e for e in self.entries if e['name'].lower() == name.lower()]

    def readable(self, e):
        return e['fmt'] in FORMATS and e['levels'] is not None

    def simple(self, e):
        """Entries this tool can rebuild: known format and every chunk understood."""
        return self.readable(e) and FORMATS[e['fmt']][3] and all(c.get('plan') for c in e['recs'])

    def raw(self, e):
        return lz4.block.decompress(bytes(self.d[e['offset']:e['offset'] + e['psize']]),
                                    uncompressed_size=e['usize'])

    def image(self, e):
        """The full-size level as a PIL image."""
        from PIL import Image
        if not self.readable(e):
            raise ValueError(f"format {e['fmt']:#x} / layout not supported yet")
        codec, bpb, bs, _ = FORMATS[e['fmt']]
        wb, hb = _div(e['w'], bs), _div(e['h'], bs)
        lin = deswizzle(self.raw(e)[:e['levels'][0]], wb, hb, bpb)
        if codec == 'rgba':
            return Image.frombytes('RGBA', (wb, hb), lin).crop((0, 0, e['w'], e['h']))
        import texture2ddecoder
        dec = getattr(texture2ddecoder, 'decode_' + codec)
        img = Image.new('RGBA', (wb * 4, hb * 4))
        row = wb * bpb
        for y in range(0, hb, STRIP):
            n = min(STRIP, hb - y)
            px = dec(lin[y * row:(y + n) * row], wb * 4, n * 4)
            img.paste(Image.frombytes('RGBA', (wb * 4, n * 4), px, 'raw', 'BGRA'), (0, y * 4))
        img = img.crop((0, 0, e['w'], e['h']))
        if codec == 'bc4':                      # one channel: show it as greyscale
            r = img.split()[0]
            img = Image.merge('RGBA', (r, r, r, Image.new('L', img.size, 255)))
        return img

    def replace(self, e, img):
        """Encode img (same size as the entry), rebuild its mip levels, append the payload and point the entry at it."""
        from PIL import Image
        if not self.simple(e):
            raise ValueError(f"{e['name']}: format {e['fmt']:#x} cannot be imported yet")
        if img.size != (e['w'], e['h']):
            raise ValueError(f"{e['name']}: PNG is {img.size[0]}x{img.size[1]}, the game expects {e['w']}x{e['h']}")
        img = img.convert('RGBA')
        packed = []
        for c in sorted(e['recs'], key=lambda c: c['rel']):
            out = bytearray()
            for (mw, mh), size in c['plan']:
                lv = img if (mw, mh) == img.size else img.resize((mw, mh), Image.LANCZOS)
                data = encode_level(lv, e['fmt'])
                out += data + bytes(size - len(data))
            out += bytes(c['usize'] - len(out))
            packed.append((c, lz4.block.compress(bytes(out), mode='high_compression', compression=12,
                                                 store_size=False)))
        while len(self.d) % 16:
            self.d.append(0)
        off = len(self.d)
        for c, data in packed:
            while (len(self.d) - off) % 16:
                self.d.append(0)
            c.update(rel=len(self.d) - off, psize=len(data))
            self.d += data
            struct.pack_into('<III', self.d, e['pos'] + 0xD0 + c['slot'] * 0x14, c['usize'], c['psize'], c['rel'])
        struct.pack_into('<I', self.d, e['pos'] + 0x134, off)
        e.update(psize=e['recs'][0]['psize'], offset=off)

    def save(self, path):
        first = min(x['offset'] for x in self.entries)
        struct.pack_into('<I', self.d, 0x0C, len(self.d) - first)
        open(path, 'wb').write(self.d)


def encode_level(img, fmt):
    """One level, encoded and swizzled."""
    from PIL import Image
    codec, bpb, bs, _ = FORMATS[fmt]
    w, h = img.size
    wb, hb = _div(w, bs), _div(h, bs)
    if (wb * bs, hb * bs) != (w, h):
        pad = Image.new('RGBA', (wb * bs, hb * bs), (0, 0, 0, 0))
        pad.paste(img, (0, 0))
        img = pad
    if codec == 'bc4':                          # greyscale into the red channel
        g = img.convert('L')
        img = Image.merge('RGBA', (g, g, g, Image.new('L', img.size, 255)))
    if codec == 'rgba':
        lin = img.tobytes('raw', 'RGBA')
    else:
        import etcpak
        enc = getattr(etcpak, 'compress_' + codec)
        parts = []
        for y in range(0, hb, STRIP):
            n = min(STRIP, hb - y)
            parts.append(enc(img.crop((0, y * 4, wb * 4, (y + n) * 4)).tobytes('raw', 'RGBA'), wb * 4, n * 4))
        lin = b''.join(parts)
    return swizzle(lin, wb, hb, bpb)


# ---- Tegra X1 block linear: GOB = 64 bytes x 8 rows (512 bytes)
def block_height(h_blocks):
    bh = 16
    while bh > 1 and h_blocks <= (bh // 2) * 8:
        bh //= 2
    return bh


def level_size(w_blocks, h_blocks, bpb):
    bh = block_height(h_blocks)
    return _div(w_blocks * bpb, 64) * 64 * _div(h_blocks, 8 * bh) * 8 * bh


def levels(e):
    """Byte size of each stored level, or None when the layout is not understood."""
    if e['fmt'] not in FORMATS:
        return None
    _, bpb, bs, _ = FORMATS[e['fmt']]
    sizes = [level_size(_div(max(1, e['w'] >> m), bs), _div(max(1, e['h'] >> m), bs), bpb) for m in range(e['mips'])]
    if sum(sizes) == e['usize']:
        return sizes
    if sizes[0] == e['usize']:
        return sizes[:1]
    return None


def chunk_plan(e, c):
    """[((width, height), byte size), ...] of the levels a chunk holds, or None when it is not understood."""
    _, bpb, bs, _ = FORMATS[e['fmt']]

    def lv(w, h):
        return (w, h), level_size(_div(w, bs), _div(h, bs), bpb)

    chain = [lv(max(1, e['w'] >> m), max(1, e['h'] >> m)) for m in range(e['mips'])]
    plan = chain[c['start']:c['start'] + c['count']]
    if len(plan) == c['count'] and sum(p[1] for p in plan) == c['usize']:
        return plan
    if c['slot'] > 0 and c['start'] == 0 and c['count'] == 1:     # preview copy
        sizes = [e['preview']] if e.get('preview') else []
        k = max(e['w'], e['h']) / 32
        if k >= 1:
            sizes.append((max(1, round(e['w'] / k)), max(1, round(e['h'] / k))))
        for w, h in sizes:
            p = lv(w, h)
            if p[1] == c['usize']:
                return [p]
    return None


def _addr(x, y, width_bytes, bh):
    gobs_x = _div(width_bytes, 64)
    base = (y // (8 * bh)) * 512 * bh * gobs_x + (x // 64) * 512 * bh + ((y % (8 * bh)) // 8) * 512
    xx, yy = x % 64, y % 8
    return base + (xx // 32) * 256 + (yy // 2) * 64 + ((xx % 32) // 16) * 32 + (yy % 2) * 16 + (xx % 16)


_MAPS = {}


def _index_map(w_blocks, h_blocks, bpb):
    """For every byte of the linear image, its offset in the swizzled one (numpy, cached per size)."""
    key = (w_blocks, h_blocks, bpb)
    m = _MAPS.get(key)
    if m is None:
        wb, bh = w_blocks * bpb, block_height(h_blocks)
        gobs_x = _div(wb, 64)
        y = np.arange(h_blocks, dtype=np.int64)[:, None]
        x = np.arange(wb, dtype=np.int64)[None, :]
        base = (y // (8 * bh)) * 512 * bh * gobs_x + (x // 64) * 512 * bh + ((y % (8 * bh)) // 8) * 512
        xx, yy = x % 64, y % 8
        m = (base + (xx // 32) * 256 + (yy // 2) * 64 + ((xx % 32) // 16) * 32 + (yy % 2) * 16 + (xx % 16)).ravel()
        if len(_MAPS) > 64:
            _MAPS.clear()
        _MAPS[key] = m
    return m


def deswizzle(data, w_blocks, h_blocks, bpb=16):
    if np is not None:
        src = np.frombuffer(data, dtype=np.uint8)
        need = level_size(w_blocks, h_blocks, bpb)
        if len(src) < need:
            src = np.concatenate([src, np.zeros(need - len(src), np.uint8)])
        return src[_index_map(w_blocks, h_blocks, bpb)].tobytes()
    wb, bh = w_blocks * bpb, block_height(h_blocks)
    step = math.gcd(16, wb)
    out = bytearray(wb * h_blocks)
    for y in range(h_blocks):
        for x in range(0, wb, step):
            a = _addr(x, y, wb, bh)
            out[y * wb + x:y * wb + x + step] = data[a:a + step]
    return bytes(out)


def swizzle(linear, w_blocks, h_blocks, bpb=16):
    if np is not None:
        out = np.zeros(level_size(w_blocks, h_blocks, bpb), np.uint8)
        out[_index_map(w_blocks, h_blocks, bpb)] = np.frombuffer(linear, dtype=np.uint8)
        return out.tobytes()
    wb, bh = w_blocks * bpb, block_height(h_blocks)
    step = math.gcd(16, wb)
    out = bytearray(level_size(w_blocks, h_blocks, bpb))
    for y in range(h_blocks):
        for x in range(0, wb, step):
            a = _addr(x, y, wb, bh)
            out[a:a + step] = linear[y * wb + x:y * wb + x + step]
    return bytes(out)
