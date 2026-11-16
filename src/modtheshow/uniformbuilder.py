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


def apply(img, swaps=(), stripes=None, logo=None):
    """img: PIL RGBA. swaps: [(from rgb, to rgb)]. stripes: dict(color, spacing, width) drawn on the fabric (the first
    swap's source, or the most common colour). logo: dict(image PIL RGBA, x, y, width) with x, y the centre as
    fractions of the texture. Returns a new PIL RGBA image of the same size."""
    from PIL import Image
    src = np.asarray(img.convert('RGBA'), np.float32)
    rgb, alpha = src[:, :, :3].copy(), src[:, :, 3]
    base = np.array(palette(img, 1)[0][0], np.float32)
    orig = rgb.copy()
    fabric = _weight(orig, base, 46.0)
    for old, new in swaps:
        w = _weight(orig, old, 46.0)[:, :, None]
        rgb += (np.array(new, np.float32) - np.array(old, np.float32)) * np.sqrt(w)
    if stripes and stripes.get('spacing', 0) > 1:
        sp, wd = int(stripes['spacing']), max(1, int(stripes.get('width', 2)))
        x = np.arange(rgb.shape[1])
        on = ((x % sp) < wd).astype(np.float32)[None, :, None]
        w = (fabric > 0.55).astype(np.float32)[:, :, None] * on
        rgb = rgb * (1 - w) + np.array(stripes['color'], np.float32) * w
    out = Image.fromarray(np.dstack([np.clip(rgb, 0, 255), alpha]).astype(np.uint8), 'RGBA')
    if logo and logo.get('image') is not None:
        art = logo['image'].convert('RGBA')
        w = max(8, int(img.width * float(logo.get('width', 0.12))))
        h = max(8, int(art.height * w / art.width))
        art = art.resize((w, h), Image.LANCZOS)
        cx, cy = int(img.width * float(logo.get('x', 0.34))), int(img.height * float(logo.get('y', 0.36)))
        keep = out.split()[3]
        out.paste(art, (cx - w // 2, cy - h // 2), art)
        out.putalpha(keep)                       # the mask stays as the game made it
    return out
