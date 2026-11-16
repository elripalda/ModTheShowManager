"""Round trip through the texture engine without game files: swizzle, encode, pack, unpack, decode."""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import lz4.block  # noqa: E402
from PIL import Image  # noqa: E402

from modtheshow import texlib  # noqa: E402


def make_pack(fmt, w, h):
    """A one-texture TX12NSW pack holding a blank image of the given format."""
    entry = bytearray(texlib.ENTRY)
    entry[0x10:0x10 + 4] = b'test'
    level = texlib.level_size(texlib._div(w, 4), texlib._div(h, 4), texlib.FORMATS[fmt][1])
    payload = lz4.block.compress(bytes(level), store_size=False)
    off = 0x20 + texlib.ENTRY
    struct.pack_into('<IHH', entry, 0x60, level, w, h)
    struct.pack_into('<I', entry, 0x6C, 1)
    struct.pack_into('<5I', entry, 0xD0, level, len(payload), 0, 0, 0x00010001)
    struct.pack_into('<II', entry, 0x130, 0x00020900, off)
    struct.pack_into('<H', entry, 0x13C, fmt)
    head = bytearray(0x20)
    head[:8] = b'TX12NSW\0'
    struct.pack_into('<IIII', head, 8, 12, len(payload), level, texlib.ENTRY)
    return bytes(head + entry + payload)


def main():
    img = Image.new('RGBA', (256, 128))
    for x in range(256):
        for y in range(128):
            img.putpixel((x, y), (x, y * 2, 255 - x, 255))
    for fmt in (0x16, 0x07, 0x0D):
        path = f'test_{fmt:x}.tex'
        with open(path, 'wb') as f:
            f.write(make_pack(fmt, 256, 128))
        t = texlib.Tex(path)
        e = t.entries[0]
        assert t.simple(e), f'format {fmt:#x} should be replaceable'
        t.replace(e, img)
        t.save(path)
        back = texlib.Tex(path).image(texlib.Tex(path).entries[0]).convert('RGB')
        err = sum(abs(a - b) for p, q in zip(back.getdata(), img.convert('RGB').getdata()) for a, b in zip(p, q))
        err /= 256 * 128 * 3
        os.remove(path)
        print(f'format {fmt:#x}: mean error {err:.2f}')
        assert err < 12, err
    # a higher-resolution replacement: the entry grows to the PNG's size and still reads back
    path = 'test_hq.tex'
    with open(path, 'wb') as f:
        f.write(make_pack(0x07, 256, 128))
    t = texlib.Tex(path)
    e = t.entries[0]
    big = img.resize((1024, 512), Image.BILINEAR)
    assert t.can_grow(e, (1024, 512)) and not t.can_grow(e, (300, 150)) and not t.can_grow(e, (512, 128))
    t.replace(e, big)
    t.save(path)
    t2 = texlib.Tex(path)
    e2 = t2.entries[0]
    assert (e2['w'], e2['h'], e2['mips']) == (1024, 512, 3), (e2['w'], e2['h'], e2['mips'])
    assert t2.simple(e2)
    back = t2.image(e2).convert('RGB')
    err = sum(abs(a - b) for p, q in zip(back.getdata(), big.convert('RGB').getdata()) for a, b in zip(p, q))
    err /= 1024 * 512 * 3
    assert back.size == (1024, 512) and err < 12, err
    t2.replace(e2, big)                      # and it can be replaced again at its new size
    try:
        t2.replace(e2, img.resize((300, 150)))
        raise AssertionError('an odd size should be refused')
    except ValueError:
        pass
    os.remove(path)
    print(f'higher resolution: mean error {err:.2f}')
    lin = os.urandom(64 * 32 * 16)
    assert texlib.deswizzle(texlib.swizzle(lin, 64, 32, 16), 64, 32, 16) == lin
    print('ok')


if __name__ == '__main__':
    main()
