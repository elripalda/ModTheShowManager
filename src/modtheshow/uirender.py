"""Draw a UI layout asset (a scorebug, a ticker) the way the game lays it out, with its real textures.

Only the still picture: the node tree at rest, every States node on the state picked for it (the first one unless
told otherwise), groups clipping what they hold. Pieces that the game fades in with an animation (flag 0x80) and
additive glows (flag 0x20) are left out unless effects is on, since at rest they sit at full strength in the file.
Text boxes are drawn with sample words in their own font, size and colour when the font table is given, since the
real words come from the game while it runs.
"""
import numpy as np
from PIL import Image, ImageChops

from .uilayout import NONE

DRAWN = (0x18, 0x01, 0x04)


class Hit:
    """One piece as drawn: its node, where it landed on screen, the texture it drew and the asset it came from."""
    __slots__ = ('node', 'rect', 'texture', 'path', 'clip')

    def __init__(self, node, rect, texture, path, clip):
        self.node, self.rect, self.texture, self.path, self.clip = node, rect, texture, path, clip


def _tint(img, rgba):
    a = np.asarray(img, np.float32)
    a = a * np.asarray(rgba, np.float32)
    return Image.fromarray(a.clip(0, 255).astype(np.uint8), 'RGBA')


def render(layout, asset, texture, table, size=(1920, 1080), states=None, effects=False, hidden=(), background=None,
           only=None, fonts=None, sample=None):
    """Draw asset. texture(name) -> PIL RGBA image or None; table: {hash: texture name} for the layout's pack. states: {node offset: state index}. hidden: node offsets
    to leave out. only: draw just this node (an offset) and what it holds. fonts: (FontTable, sheet) to draw text
    boxes with; sample(node) -> the words to show in a text box. Returns (image, [Hit]) with hits in draw
    order, last on top."""
    states = states or {}
    canvas = Image.new('RGBA', size, background or (0, 0, 0, 0))
    hits = []
    cache = {}

    def tex(name):
        if name not in cache:
            try:
                cache[name] = texture(name)
            except Exception:
                cache[name] = None
        return cache[name]

    def blit(img, x, y, w, h, clip, add):
        x0, y0 = int(round(x)), int(round(y))
        iw, ih = max(1, int(round(w))), max(1, int(round(h)))
        cx0, cy0, cx1, cy1 = (int(round(v)) for v in clip)
        cx0, cy0 = max(cx0, 0), max(cy0, 0)
        cx1, cy1 = min(cx1, size[0]), min(cy1, size[1])
        lx0, ly0, lx1, ly1 = max(x0, cx0), max(y0, cy0), min(x0 + iw, cx1), min(y0 + ih, cy1)
        if lx1 <= lx0 or ly1 <= ly0 or iw > 6000 or ih > 6000:
            return False
        if img.size != (iw, ih):
            img = img.resize((iw, ih), Image.BILINEAR)
        part = img.crop((lx0 - x0, ly0 - y0, lx1 - x0, ly1 - y0))
        if add:
            box = (lx0, ly0, lx1, ly1)
            base = canvas.crop(box)
            a = np.asarray(part, np.float32)
            glow = (a[..., :3] * (a[..., 3:4] / 255)).clip(0, 255).astype(np.uint8)
            rgb = ImageChops.add(base.convert('RGB'), Image.fromarray(glow, 'RGB'))
            out = rgb.convert('RGBA')
            out.putalpha(ImageChops.lighter(base.getchannel('A'), part.getchannel('A')))
            canvas.paste(out, box)
        else:
            canvas.alpha_composite(part, (lx0, ly0))
        return True

    def _text(n, ax, ay, c, clip):
        from . import fontlib
        table, sheet = fonts
        num = layout.text_font(n)
        if not (0 <= num < len(table.fonts)) or sheet is None:
            return
        px = layout.text_size(n)
        words = sample(n) if sample else ('88' if not layout.text_label(n) else 'ABC')
        if not words or px < 2:
            return
        r, g, b, a = layout.text_color(n)
        col = (r * c[0], g * c[1], b * c[2], a * c[3])
        try:
            img = fontlib.draw_text(table.fonts[num], sheet, words, px * 0.7, tuple(int(v) for v in col))
        except Exception:
            return
        x = ax + (n.w - img.width) / 2
        y = ay + (n.h - img.height) / 2
        box = (max(clip[0], ax), max(clip[1], ay), min(clip[2], ax + n.w), min(clip[3], ay + n.h))
        blit(img, x, y, img.width, img.height, box, False)

    def draw(n, ox, oy, tint, clip, path, depth, on):
        if n.off in hidden:
            return
        r, g, b, a = n.rgba()
        c = tint * np.array([r, g, b, a], np.float32) / 255
        if c[3] <= 0.004:
            return
        if not effects and n.flags & 0xA0:
            return
        on = on or only is None or n.off == only
        ax, ay = ox + n.x, oy + n.y
        if on and n.kind in DRAWN and n.w >= 1 and n.h >= 1:
            name = table.get(n.ref) if n.ref != NONE else None
            img = tex(name) if name else None
            if img is None:
                img = Image.new('RGBA', (8, 8), (255, 255, 255, 255))
            elif n.kflip:
                if n.kflip & 1:
                    img = img.transpose(Image.FLIP_LEFT_RIGHT)
                if n.kflip & 2:
                    img = img.transpose(Image.FLIP_TOP_BOTTOM)
            if blit(_tint(img, c), ax, ay, n.w, n.h, clip, bool(n.flags & 0x20)):
                hits.append(Hit(n, (ax, ay, n.w, n.h), name, path, clip))
        elif on and n.kind == 0x22 and n.w >= 1 and n.h >= 1:
            if fonts is not None:
                _text(n, ax, ay, c, clip)
            hits.append(Hit(n, (ax, ay, n.w, n.h), None, path, clip))
        if n.kind == 0x1E:
            sub = layout.by_hash.get(n.ref)
            if sub is not None and depth < 8 and sub.root() is not None:
                inner = (max(clip[0], ax), max(clip[1], ay), min(clip[2], ax + n.w), min(clip[3], ay + n.h))
                draw(sub.root(), ax, ay, c, inner, path + (sub.name,), depth + 1, on)
            return
        kids = n.children
        if n.kind == 0x1C:
            per = n.state_children()
            i = states.get(n.off, 0)
            pick = per[i] if 0 <= i < len(per) else None
            kids = [pick] if pick is not None else []
        nclip = clip
        if n.kind in (0x0F, 0x0C) and n.parent is not None and n.w > 0 and n.h > 0:
            nclip = (max(clip[0], ax), max(clip[1], ay), min(clip[2], ax + n.w), min(clip[3], ay + n.h))
        for k in kids:
            draw(k, ax, ay, c, nclip, path, depth, on)

    root = asset.root()
    if root is not None:
        draw(root, 0, 0, np.ones(4, np.float32), (0, 0, size[0], size[1]), (asset.name,), 0, False)
    return canvas, hits


def state_nodes(layout, asset, depth=0, seen=None):
    """Every States node an asset draws, its own and those of the assets it shows, with the asset each belongs to."""
    seen = seen if seen is not None else set()
    out = []
    if asset.hash in seen or depth > 8:
        return out
    seen.add(asset.hash)
    for n in asset.nodes():
        if n.kind == 0x1C and n.states and len(n.states) > 1:
            out.append((asset, n))
        if n.kind == 0x1E:
            sub = layout.by_hash.get(n.ref)
            if sub is not None:
                out += state_nodes(layout, sub, depth + 1, seen)
    return out
