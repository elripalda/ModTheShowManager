"""Jersey builder: recolour a uniform part, add pinstripes, put a logo on it. Works on the part's colour texture.

A uniform texture is flat colours with trim and logos drawn on top, so the tools here work by colour: the most common
colour is the fabric, and a colour swap moves every pixel near one colour towards another while keeping the edges soft.
The alpha channel is left alone (in these textures it is a mask the game uses, not transparency).
"""
import numpy as np

PARTS = [('Jersey', 'UNIFORM.TEX', 'jersey-color'), ('Sleeves', 'UNIFORM.TEX', 'sleeves-color'),
         ('Undershirt', 'UNIFORM.TEX', 'tshirt-color'), ('Pants', 'PANTS.TEX', 'pants-color'),
         ('Socks', 'PANTS.TEX', 'highsocks-color'), ('Cap', 'CAPHELMET.TEX', 'cap-color'),
         ('Helmet', 'CAPHELMET.TEX', 'helmet-color'), ('Helmet, New Style', 'CAPHELMET.TEX', 'helmetnew-color')]


def palette(img, count=6):
    """The part's main colours, most common first: [((r, g, b), share of the texture)]."""
    a = np.asarray(img.convert('RGB').resize((256, max(1, 256 * img.height // img.width))), np.int32).reshape(-1, 3)
    q = (a >> 3)
    keys = (q[:, 0] << 10) | (q[:, 1] << 5) | q[:, 2]
    vals, counts = np.unique(keys, return_counts=True)
    out = []
    for k in np.argsort(-counts):
        c = np.array([(vals[k] >> 10) & 31, (vals[k] >> 5) & 31, vals[k] & 31]) * 8 + 4
        sel = a[keys == vals[k]]
        c = sel.mean(0) if len(sel) else c
        if any(np.abs(np.array(o[0]) - c).sum() < 60 for o in out):
            continue
        out.append((tuple(int(round(x)) for x in c), counts[k] / len(a)))
        if len(out) >= count:
            break
    return out


def _weight(rgb, color, tol):
    d = np.sqrt(((rgb - np.array(color, np.float32)) ** 2).sum(-1))
    return np.clip(1.0 - d / tol, 0.0, 1.0)


def lettering(normal, grow=5):
    """Where a part's sewn-on logos and lettering are, from its normal texture (they shine: its alpha). A PIL 'L'
    mask the size of the normal texture, a few pixels wider than the art, or None when the part has none."""
    from PIL import Image, ImageFilter
    a = np.asarray(normal.convert('RGBA'))[:, :, 3] > 24
    if not a.any() or a.mean() > 0.35:
        return None
    return Image.fromarray((a * 255).astype(np.uint8), 'L').filter(ImageFilter.MaxFilter(2 * grow + 1))


def apply(img, swaps=(), stripes=None, logo=None, logos=(), quality=1, erase=None):
    """img: PIL RGBA. swaps: [(from rgb, to rgb)]. stripes: dict(color, spacing, width) drawn on the fabric (the most
    common colour). logos: [dict(image PIL RGBA, x, y, width)] with x, y the centre as fractions of the texture.
    quality 2 or 4 builds the part at that many times the game's size, so logos and stripes stay sharp. erase: a mask
    (see lettering) of old art to paint over with the fabric colour first. Returns a new PIL RGBA image."""
    from PIL import Image
    quality = int(quality) if quality in (2, 4, 8) else 1
    if quality > 1:
        img = img.convert('RGBA').resize((img.width * quality, img.height * quality), Image.LANCZOS)
    src = np.asarray(img.convert('RGBA'), np.float32)
    rgb, alpha = src[:, :, :3].copy(), src[:, :, 3]
    base = np.array(palette(img, 1)[0][0], np.float32)
    if erase is not None:                        # the old lettering goes: plain fabric where it was
        from PIL import ImageFilter
        near = erase.filter(ImageFilter.MaxFilter(25))            # and its outline or shadow just outside it
        gone = np.asarray(erase.resize(img.size, Image.BILINEAR), np.float32) / 255.0
        ring = np.asarray(near.resize(img.size, Image.BILINEAR), np.float32) / 255.0
        gone = np.maximum(gone, ring * (_weight(rgb, base, 46.0) < 0.6))[:, :, None]
        rgb = rgb * (1 - gone) + base * gone
    orig = rgb.copy()
    fabric = _weight(orig, base, 46.0)
    for old, new in swaps:
        w = _weight(orig, old, 46.0)[:, :, None]
        rgb += (np.array(new, np.float32) - np.array(old, np.float32)) * np.sqrt(w)
    if stripes and stripes.get('spacing', 0) > 1:
        sp, wd = int(stripes['spacing']) * quality, max(1, int(stripes.get('width', 2)) * quality)
        x = np.arange(rgb.shape[1])
        on = ((x % sp) < wd).astype(np.float32)[None, :, None]
        w = (fabric > 0.55).astype(np.float32)[:, :, None] * on
        rgb = rgb * (1 - w) + np.array(stripes['color'], np.float32) * w
    out = Image.fromarray(np.dstack([np.clip(rgb, 0, 255), alpha]).astype(np.uint8), 'RGBA')
    keep = out.split()[3]
    for lg in ([logo] if logo else []) + list(logos):
        if not lg or lg.get('image') is None:
            continue
        art = lg['image'].convert('RGBA')
        w = max(8, int(out.width * float(lg.get('width', 0.12))))
        h = max(8, int(art.height * w / art.width))
        art = art.resize((w, h), Image.LANCZOS)
        cx, cy = int(out.width * float(lg.get('x', 0.34))), int(out.height * float(lg.get('y', 0.36)))
        out.paste(art, (cx - w // 2, cy - h // 2), art)
    out.putalpha(keep)                           # the mask stays as the game made it
    return out


def _blobs(mask):
    """Connected patches of a small boolean grid: (labels, count), 0 for off."""
    h, w = mask.shape
    labels = np.zeros((h, w), np.int32)
    count = 0
    for y, x in zip(*np.nonzero(mask)):
        if labels[y, x]:
            continue
        count += 1
        labels[y, x] = count
        todo = [(y, x)]
        while todo:
            cy, cx = todo.pop()
            for ny in (cy - 1, cy, cy + 1):
                for nx in (cx - 1, cx, cx + 1):
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not labels[ny, nx]:
                        labels[ny, nx] = count
                        todo.append((ny, nx))
    return labels, count


def settle_normal(color, normal, cell=8):
    """A part's normal texture with the stitching of logos that are no longer on the part taken out.

    The normal texture carries each sewn-on logo twice: raised in its colours, and as a shine mask in its alpha. When a
    mod changes the colour texture and the old logo is gone from it, both stay behind and show as a glossy ghost of the
    old logo. A patch of shine is kept when the new colour texture still has an outline where the patch ends (the logo
    is still there, recoloured or not) and is flattened when it does not. color: the new colour texture, normal: the
    game's normal texture (PIL). Returns the new normal, or None when nothing had to change."""
    from PIL import Image
    n = np.asarray(normal.convert('RGBA')).copy()
    h, w = n.shape[:2]
    if h % cell or w % cell or min(h, w) < cell * 8:
        return None
    shine = n[:, :, 3] > 24
    if not shine.any() or shine.mean() > 0.35:
        return None
    c = np.asarray(color.convert('RGB').resize((w, h), Image.BILINEAR), np.int16)
    d = 3
    step = np.zeros((h, w), np.int16)
    step[:, d:-d] = np.abs(c[:, 2 * d:] - c[:, :-2 * d]).max(-1)
    step[d:-d, :] = np.maximum(step[d:-d, :], np.abs(c[2 * d:, :] - c[:-2 * d, :]).max(-1))
    inner = shine.copy()
    inner[1:, :] &= shine[:-1, :]
    inner[:-1, :] &= shine[1:, :]
    inner[:, 1:] &= shine[:, :-1]
    inner[:, :-1] &= shine[:, 1:]
    rim = shine & ~inner
    small = shine.reshape(h // cell, cell, w // cell, cell).any((1, 3))
    labels, count = _blobs(small)
    big = np.repeat(np.repeat(labels, cell, 0), cell, 1)
    gone = np.zeros(count + 1, bool)
    for k in range(1, count + 1):
        edge = rim & (big == k)
        total = int(edge.sum())
        gone[k] = total > 0 and float((step[edge] > 28).sum()) / total < 0.5
    if not gone.any():
        return None
    area = shine & gone[big]
    for _ in range(4):                         # a few pixels wider, to take the raised edge with it
        wide = area.copy()
        wide[1:, :] |= area[:-1, :]
        wide[:-1, :] |= area[1:, :]
        wide[:, 1:] |= area[:, :-1]
        wide[:, :-1] |= area[:, 1:]
        area = wide
    area &= ~(shine & ~gone[big])              # but never into a patch that stays
    flat = np.median(n[~shine][::7, :3], axis=0)
    n[area] = (int(flat[0]), int(flat[1]), int(flat[2]), 0)
    return Image.fromarray(n, 'RGBA')
