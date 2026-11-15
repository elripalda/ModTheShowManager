"""Names and numbers on jerseys.

A team uniform carries its own font as two atlases in UNIFORM.TEX: letters-color (A-Z, then ' - . and a set of small
caps) and numbers-color (0-9), coloured and outlined already, with alpha as the glyph shape. The game stamps glyphs
onto the jersey through the UV_playerNumber texture coordinates, which run in rows: v 1-2 is the name across the
shoulders, v 2-3 the big number on the back, v 3-4 the small number on the front.

compose() builds that three-row strip from the atlases so the preview shows a name and number. Replacing the two
atlas textures in a mod is how you change a team's font.
"""
import numpy as np
from PIL import Image

LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ\'-.'
ROW_W, ROW_H = 2048, 512


def glyph_boxes(atlas, merge=6):
    """Column ranges [(x0, x1)] of the glyphs in an atlas, left to right."""
    a = np.asarray(atlas.convert('RGBA'))[..., 3]
    col = (a > 40).sum(0) > 0
    runs, i, w = [], 0, len(col)
    while i < w:
        if col[i]:
            j = i
            while j < w and col[j]:
                j += 1
            runs.append([i, j])
            i = j
        else:
            i += 1
    out = []
    for r in runs:
        if out and r[0] - out[-1][1] < merge and (r[1] - r[0] < 8 or out[-1][1] - out[-1][0] < 8):
            out[-1][1] = r[1]
        else:
            out.append(r)
    return out


def _cut(atlas, box):
    a = atlas.convert('RGBA')
    g = a.crop((box[0], 0, box[1], a.height))
    bb = g.split()[3].getbbox()
    return g.crop((0, bb[1], g.width, bb[3])) if bb else g


def _line(atlas, boxes, text, charset, height, spacing=0.06):
    glyphs = []
    for ch in text.upper():
        if ch == ' ':
            glyphs.append(None)
            continue
        k = charset.find(ch)
        if k < 0 or k >= len(boxes):
            continue
        glyphs.append(_cut(atlas, boxes[k]))
    if not glyphs:
        return None
    gh = max(g.height for g in glyphs if g is not None) if any(glyphs) else 1
    scale = height / gh
    parts = [g.resize((max(1, int(g.width * scale)), max(1, int(g.height * scale))), Image.LANCZOS) if g else None
             for g in glyphs]
    space = int(height * 0.35)
    gap = int(height * spacing)
    width = sum((p.width if p else space) for p in parts) + gap * (len(parts) - 1)
    img = Image.new('RGBA', (max(1, width), height), (0, 0, 0, 0))
    x = 0
    for p in parts:
        if p:
            img.alpha_composite(p, (x, height - p.height))
            x += p.width
        else:
            x += space
        x += gap
    return img


def _place(row, line, fill=0.82, max_h=0.8):
    if line is None:
        return
    s = min(ROW_W * fill / line.width, ROW_H * max_h / line.height)
    w, h = max(1, int(line.width * s)), max(1, int(line.height * s))
    line = line.resize((w, h), Image.LANCZOS)
    row.alpha_composite(line, ((ROW_W - w) // 2, (ROW_H - h) // 2))


def compose(letters, numbers, name='', number=''):
    """RGBA strip of 3 rows (name, back number, front number) for the jersey's UV_playerNumber channel."""
    out = Image.new('RGBA', (ROW_W, ROW_H * 3), (0, 0, 0, 0))
    rows = [Image.new('RGBA', (ROW_W, ROW_H), (0, 0, 0, 0)) for _ in range(3)]
    if letters is not None and name:
        _place(rows[0], _line(letters, glyph_boxes(letters), name, LETTERS, 256), fill=0.9, max_h=0.7)
    if numbers is not None and number:
        nb = glyph_boxes(numbers)
        _place(rows[1], _line(numbers, nb, number, '0123456789', 256, 0.04), fill=0.75, max_h=0.9)
        _place(rows[2], _line(numbers, nb, number, '0123456789', 256, 0.04), fill=0.6, max_h=0.8)
    for k, r in enumerate(rows):
        out.alpha_composite(r, (0, ROW_H * k))
    return out


BACK = (-0.47, 0.47, 0.95, 1.86)        # x0, x1, y0, y1 of the print area on the jersey back (model units)


def back_image(letters, numbers, name='', number='', size=1024):
    """The print on a jersey back: name across the shoulders, number below, in the team's own font."""
    x0, x1, y0, y1 = BACK
    w, h = size, int(size * (y1 - y0) / (x1 - x0))
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    if letters is not None and name:
        line = _line(letters, glyph_boxes(letters), name, LETTERS, 256)
        if line is not None:
            s = min(w * 0.86 / line.width, h * 0.15 / line.height)
            line = line.resize((max(1, int(line.width * s)), max(1, int(line.height * s))), Image.LANCZOS)
            img.alpha_composite(line, ((w - line.width) // 2, int(h * 0.04)))
    if numbers is not None and number:
        line = _line(numbers, glyph_boxes(numbers), number, '0123456789', 256, 0.04)
        if line is not None:
            s = min(w * 0.78 / line.width, h * 0.62 / line.height)
            line = line.resize((max(1, int(line.width * s)), max(1, int(line.height * s))), Image.LANCZOS)
            img.alpha_composite(line, ((w - line.width) // 2, int(h * 0.24)))
    return img


def back_uv(pos, nrm=None):
    """Projected print coordinates for jersey vertices on the back (z < 0); -1 elsewhere. Range 0-1 inside the
    print area, outside it beyond 0-1 so triangles interpolate cleanly."""
    import numpy as np
    pos = np.asarray(pos, np.float32)
    out = np.full((len(pos), 2), -1.0, np.float32)
    x0, x1, y0, y1 = BACK
    back = pos[:, 2] < 0.05
    out[back, 0] = (x1 - pos[back, 0]) / (x1 - x0)
    out[back, 1] = (y1 - pos[back, 1]) / (y1 - y0)
    return out
