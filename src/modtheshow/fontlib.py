"""The game's UI fonts: NSW/UI/ART/FONTS/FONTS.NSW with the letter sheets in FONTS.TEX.

FONTS.NSW is one layout asset holding a font table. At +0x40 of the asset body are 0x30-byte font records (39 in
MLB The Show 26: 38 on the "english" sheet, the last on "symbols"); +0x20 holds the sheet's texture name hash and
+0x28 the offset of the font's glyph table. A glyph table is 124 records of 0x28 bytes:

  +0x00 u32  character, as its UTF-8 bytes (first byte lowest)
  +0x04 f32  u0, v0, u1, v1 on the sheet
  +0x14 u16  width, height in sheet pixels (with 4 px of padding on every side)
  +0x18 s16  bottom (from the baseline, up), left bearing, right bearing

The sheets keep each letter as a signed distance field in alpha (0.5 = the edge), which is why the game can draw
them at any size. Text boxes pick a font with byte +0x74 (font number = value >> 2).
"""
import struct

import numpy as np
from PIL import Image

from .uilayout import Layout, name_hash

FONTS = 'NSW/UI/ART/FONTS/FONTS.NSW'
SHEETS = 'NSW/UI/ART/FONTS/FONTS.TEX'
GLYPH = 0x28
PAD = 4


def char_of(code):
    """Glyph codes are the character's UTF-8 bytes, first byte lowest."""
    if code < 0x80:
        return chr(code)
    b = code.to_bytes(4, 'little').rstrip(b'\0')
    try:
        return b.decode('utf-8')
    except UnicodeDecodeError:
        return None


def code_of(ch):
    return int.from_bytes(ch.encode('utf-8'), 'little')


class Glyph:
    __slots__ = ('char', 'uv', 'w', 'h', 'bottom', 'left', 'right', 'off')

    @property
    def advance(self):
        return max(1, self.w - 2 * PAD + self.left + self.right)


class Font:
    def __init__(self, index, sheet, glyphs, rec):
        self.index, self.sheet, self.glyphs, self.rec = index, sheet, glyphs, rec

    @property
    def caps(self):
        """True when the lower-case letters are drawn as capitals (most scorebug fonts)."""
        a, b = self.glyphs.get(ord('a')), self.glyphs.get(ord('A'))
        return bool(a and b and a.h >= b.h - 2)


class FontTable:
    def __init__(self, data):
        self.layout = Layout(data)
        a = self.layout.assets[0]
        self.body = a.body
        d = self.layout.d
        self.fonts = []
        o = self.body + 0x40
        n = 0
        while o + 0x30 <= self.body + a.size:
            sheet, table = struct.unpack_from('<I4xI', d, o + 0x20)
            if sheet not in (name_hash('english'), name_hash('symbols')) or not table:
                break
            glyphs = {}
            for i in range(124):
                r = self.body + table + i * GLYPH
                if r + GLYPH > len(d):
                    break
                g = Glyph()
                g.off = r
                g.char = struct.unpack_from('<I', d, r)[0]
                g.uv = struct.unpack_from('<4f', d, r + 4)
                g.w, g.h, g.bottom, g.left, g.right = struct.unpack_from('<HHhhh', d, r + 0x14)
                glyphs[g.char] = g
            self.fonts.append(Font(n, 'english' if sheet == name_hash('english') else 'symbols', glyphs, o))
            o += 0x30
            n += 1

    @classmethod
    def open(cls, path):
        with open(path, 'rb') as f:
            return cls(f.read())

    def bytes(self):
        return self.layout.bytes()


def font_number(text_node_byte):
    return text_node_byte >> 2


def draw_text(font, sheet, text, height, color=(255, 255, 255, 255)):
    """Text in a game font as a PIL image, height px tall (capitals). sheet: the font's letter sheet (PIL RGBA)."""
    if font.caps:
        text = text.upper()
    ref = font.glyphs.get(ord('H')) or next(iter(font.glyphs.values()))
    cap = max(1, ref.h - 2 * PAD)
    k = height / cap
    glyphs = [font.glyphs.get(code_of(c)) for c in text]
    space = (font.glyphs.get(ord('I')) or ref).advance
    width = sum((g.advance if g and g.w else space) for g in glyphs)
    out = Image.new('RGBA', (max(1, int(width * k) + 4), max(1, int(height * 1.5) + 4)), (0, 0, 0, 0))
    W, H = sheet.size
    x = 2.0
    base = int(height * 1.2) + 2
    for g in glyphs:
        if not g or not g.w:
            x += space * k
            continue
        u0, v0, u1, v1 = g.uv
        tile = sheet.crop((round(u0 * W) - PAD, round(v0 * H) - PAD, round(u1 * W) + PAD, round(v1 * H) + PAD))
        tw, th = max(1, round(tile.width * k)), max(1, round(tile.height * k))
        a = np.asarray(tile.getchannel('A').resize((tw, th), Image.BILINEAR), np.float32) / 255
        edge = 0.5
        soft = max(0.02, 0.12 / max(k, 0.25))
        alpha = np.clip((a - edge) / soft + 0.5, 0, 1)
        g_img = np.zeros((th, tw, 4), np.float32)
        g_img[..., :3] = color[:3]
        g_img[..., 3] = alpha * color[3]
        top = base - round((g.bottom + g.h) * k)
        out.alpha_composite(Image.fromarray(g_img.astype(np.uint8), 'RGBA'), (int(x + (g.left - PAD) * k), top))
        x += g.advance * k
    bbox = out.getbbox()
    return out.crop(bbox) if bbox else out


# ---------------------------------------------------------------------- importing a font
SPREAD = 5           # how far the distance field reaches from the edge, in sheet pixels
SS = 2               # supersampling while drawing a letter


def _offsets(r):
    out = []
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            d = (dx * dx + dy * dy) ** 0.5
            if 0 < d <= r:
                out.append((dx, dy, d))
    return sorted(out, key=lambda o: o[2])


_OFFS = {}


def distance_field(mask, spread):
    """A signed distance field of a boolean mask, as 0-255 alpha with 128 on the edge (no SciPy needed)."""
    r = int(spread) + 1
    offs = _OFFS.setdefault(r, _offsets(r))
    h, w = mask.shape
    pad = np.pad(mask, r, mode='constant')
    inside = np.full(mask.shape, float(r))
    outside = np.full(mask.shape, float(r))
    for dx, dy, d in offs:
        nb = pad[r + dy:r + dy + h, r + dx:r + dx + w]
        np.minimum(inside, np.where(mask & ~nb, d, r), out=inside)      # distance to the nearest outside pixel
        np.minimum(outside, np.where(~mask & nb, d, r), out=outside)    # distance to the nearest inside pixel
    sd = np.where(mask, inside - 0.5, -(outside - 0.5))
    return np.clip(128 + sd * (127 / spread), 0, 255).astype(np.uint8)


def used_bottom(table, sheet_size):
    """The first sheet row below every letter in use, where new letters can go."""
    H = sheet_size[1]
    low = 0
    for f in table.fonts:
        if f.sheet != 'english':
            continue
        for g in f.glyphs.values():
            if g.w:
                low = max(low, int(round(g.uv[3] * H)) + PAD)
    return low + 2


def import_font(table, sheet, slot, font_path):
    """Draw the font file's letters into free space on the sheet and point font number slot at them. The letters
    take the slot's cap height, so text boxes that use it keep their size. Returns (new sheet, characters drawn)."""
    from PIL import ImageDraw, ImageFont
    f = table.fonts[slot]
    if f.sheet != 'english':
        raise ValueError('That font lives on the symbols sheet and cannot be replaced.')
    ref = f.glyphs.get(ord('H'))
    cap = (ref.h - 2 * PAD) if ref else 56
    probe = ImageFont.truetype(font_path, 200)
    hb = probe.getbbox('H')
    px = max(8, round(200 * cap / max(1, hb[3] - hb[1])))
    ttf = ImageFont.truetype(font_path, px * SS)
    ascent = ttf.getmetrics()[0]
    sheet = sheet.copy()
    W, H = sheet.size
    x, y, row = 2, used_bottom(table, sheet.size), 0
    a = np.asarray(sheet).copy()
    drawn = 0
    caps = f.caps
    d = table.layout.d
    for code, g in sorted(f.glyphs.items()):
        if not g.w:
            continue
        ch = char_of(code)
        if not ch:
            continue
        if caps:
            ch = ch.upper()
        box = ttf.getbbox(ch)
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        gw, gh = (box[2] - box[0]) // SS + 1, (box[3] - box[1]) // SS + 1
        tw, th = gw + 2 * PAD, gh + 2 * PAD
        if x + tw > W:
            x, y, row = 2, y + row + 2, 0
        if y + th > H:
            raise ValueError('The letter sheet is full. Reset the fonts in your mod and try again.')
        big = Image.new('L', (tw * SS, th * SS), 0)
        ImageDraw.Draw(big).text((PAD * SS - box[0], PAD * SS - box[1]), ch, font=ttf, fill=255)
        mask = np.asarray(big.resize((tw, th), Image.BOX)) >= 128
        a[y:y + th, x:x + tw, :3] = 255
        a[y:y + th, x:x + tw, 3] = distance_field(mask, SPREAD)
        adv = ttf.getlength(ch) / SS
        left = box[0] / SS
        bottom = (ascent - box[3]) / SS - (ascent / SS - px)       # from the baseline, up
        u0, v0 = (x + PAD) / W, (y + PAD) / H
        u1, v1 = (x + PAD + gw - 1) / W, (y + PAD + gh - 1) / H
        struct.pack_into('<4f', d, g.off + 4, u0, v0, u1, v1)
        struct.pack_into('<HHhhh', d, g.off + 0x14, tw - 1, th - 1, round(bottom) - PAD, round(left),
                         round(adv - left - gw))
        g.uv, g.w, g.h = (u0, v0, u1, v1), tw - 1, th - 1
        g.bottom, g.left, g.right = round(bottom) - PAD, round(left), round(adv - left - gw)
        x += tw + 2
        row = max(row, th)
        drawn += 1
    return Image.fromarray(a, 'RGBA'), drawn
