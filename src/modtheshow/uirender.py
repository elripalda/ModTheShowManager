"""Draw a UI layout asset (a scorebug, a ticker) the way the game lays it out, with its real textures.

Only the still picture: the node tree at rest, every States node on the state picked for it (the first one unless
told otherwise), with reused overlays stretched to fit and clipping groups honoured. Pieces that the game fades in with an animation (flag 0x80) and
additive glows (flag 0x20) are left out unless effects is on, since at rest they sit at full strength in the file.
Text boxes are drawn with sample words in their own font, size and colour when the font table is given, since the
real words come from the game while it runs.
"""
import struct

import numpy as np
from PIL import Image, ImageChops

from .uilayout import NONE, place

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
           only=None, fonts=None, sample=None, situation=None, lang=None, reveal=(), pose=None):
    """Draw asset. texture(name) -> PIL RGBA image or None; table: {hash: texture name} for the layout's pack. states: {node offset: state index}. hidden: node offsets
    to leave out. only: draw just this node (an offset) and what it holds. fonts: (FontTable, sheet) to draw text
    boxes with; sample(node) -> the words to show in a text box. situation: a uiquery.Situation, which picks every
    States node's look the way the game would and, with lang (the layout's uilang.Lang), fills in the text.
    reveal: offsets of see-through nodes to show anyway (the pop-ups an animation fades in). pose: one frame of an
    animation, from Asset.pose (it only reaches the asset's own nodes). Returns (image, [Hit]) with hits in draw
    order, last on top."""
    states = states or {}
    canvas = Image.new('RGBA', size, background or (0, 0, 0, 0))
    hits = []
    cache = {}
    picks = {}                     # {States node offset: the look drawn}
    code_states = getattr(situation, 'code_states', None) or {}

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

    def words_for(n, ctx):
        if sample:
            return sample(n)
        lab = layout.text_label(n)
        if lang is None or ctx is None:
            return '88' if not lab else 'ABC'
        from . import uilang, uiquery
        if lab in lang.static:
            return uilang.plain(lang.static[lab])
        if lab in lang.live:
            fmt, binds = lang.live[lab]
            out = uilang.plain(fmt)
            for i, toks in binds.items():
                v = ctx.value(uiquery.parse(toks))
                out = out.replace(f'^d{i}^', '' if v is None else str(v))
            return out
        return ''

    def _text(n, ax, ay, bw, bh, c, clip, ctx):
        from . import fontlib
        table, sheet = fonts
        num = layout.text_font(n)
        if not (0 <= num < len(table.fonts)) or sheet is None:
            return
        px = layout.text_size(n)
        words = words_for(n, ctx)
        if words:
            words = words.split('\n')[0].strip()
        if not words or px < 2:
            return
        col = (255 * c[0], 255 * c[1], 255 * c[2], 255 * c[3])      # the node's own colour fills the letters
        try:
            img = fontlib.draw_text(table.fonts[num], sheet, words, px * 0.82, tuple(int(v) for v in col))
        except Exception:
            return
        if img.width > bw > 8:                     # the game squeezes text that is too wide for its box
            img = img.resize((max(1, int(bw)), img.height))
        al = layout.text_align(n)
        x = ax + (0, (bw - img.width) / 2, bw - img.width)[min(al, 2)]
        y = ay + (bh - img.height) / 2
        box = (max(clip[0], ax), max(clip[1], ay), min(clip[2], ax + bw), min(clip[3], ay + bh))
        blit(img, x, y, img.width, img.height, box, False)

    def draw(n, ox, oy, tint, clip, path, depth, on, ctx, dw=0.0, dh=0.0, pw=0.0, ph=0.0, size=None, team=None):
        if n.off in hidden:
            return
        if n.kind == 0x0F and ctx is not None:             # a group can carry a team's colour for the art inside it
            own = layout._query_at(n.asset, struct.unpack_from('<Q', layout.d, n.off + 0x40)[0])
            if own:
                try:
                    from . import uiquery
                    v = ctx.value(uiquery.parse(own))
                    if isinstance(v, str) and v.startswith('#') and len(v) == 7:
                        team = np.array([int(v[1:3], 16), int(v[3:5], 16), int(v[5:7], 16), 255], np.float32) / 255
                except Exception:
                    pass
        r, g, b, a = n.rgba()
        ps = pose.get(n.off) if pose else None
        if ps and 11 in ps:
            a = ps[11]
        if a == 0 and n.off in reveal:
            a = 255
        c = tint * np.array([r, g, b, a], np.float32) / 255
        if c[3] <= 0.004:
            return
        if not effects and n.flags & 0x20:
            return                                  # glows and flares: they flash in with an animation
        on = on or only is None or n.off == only
        if size is not None:                        # the top of a reused overlay takes the size of its Instance
            nx, ny, nw, nh = 0.0, 0.0, size[0], size[1]
        else:
            nx, ny, nw, nh = place(n, dw, dh, pw, ph)
        if ps:
            nx, ny = ps.get(0, nx), ps.get(1, ny)
            nw, nh = ps.get(7, nw), ps.get(8, nh)
        ax, ay = ox + nx, oy + ny
        kid = (nw - n.w, nh - n.h, n.w, n.h)        # how its own children must adjust
        if on and n.kind == 0x18 and layout.is_slot(n) and nw >= 1 and nh >= 1:
            team = ctx.args[0] if ctx is not None and ctx.args else 0
            own = layout._query_at(n.asset, struct.unpack_from('<Q', layout.d, n.off + 0x30)[0])
            if own and ctx is not None:                    # the slot's own query says whose logo: UI LOGO [team, kind]
                try:
                    from . import uiquery
                    team = ctx.value(uiquery.parse(own))
                except Exception:
                    pass
            logo = situation.team_logo(team) if situation is not None else None
            if logo is not None:
                fit = logo.copy()
                fit.thumbnail((max(1, int(nw)), max(1, int(nh))))
                if blit(_tint(fit, c), ax + (nw - fit.width) / 2, ay + (nh - fit.height) / 2, fit.width,
                        fit.height, clip, False):
                    hits.append(Hit(n, (ax, ay, nw, nh), None, path, clip))
            elif situation is not None:
                hits.append(Hit(n, (ax, ay, nw, nh), None, path, clip))
        elif on and n.kind in DRAWN and nw >= 1 and nh >= 1:
            name = table.get(n.ref) if n.ref != NONE else None
            img = tex(name) if name else None
            if img is None:
                img = Image.new('RGBA', (8, 8), (255, 255, 255, 255))
            elif n.kflip:
                if n.kflip & 1:
                    img = img.transpose(Image.FLIP_LEFT_RIGHT)
                if n.kflip & 2:
                    img = img.transpose(Image.FLIP_TOP_BOTTOM)
            if blit(_tint(img, c if team is None else c * team), ax, ay, nw, nh, clip, bool(n.flags & 0x20)):
                hits.append(Hit(n, (ax, ay, nw, nh), name, path, clip))
        elif on and n.kind == 0x22 and nw >= 1 and nh >= 1:
            if fonts is not None:
                _text(n, ax, ay, nw, nh, c, clip, ctx)
            hits.append(Hit(n, (ax, ay, nw, nh), None, path, clip))
        if n.kind == 0x1E:
            sub = layout.by_hash.get(n.ref)
            if sub is not None and sub.name == 'CLgRC' and situation is not None:
                # the team-colour wash: the game paints it from the team this copy is handed
                team = ctx.child(layout.instance_args(n)).args
                rgb = situation.team_color(team[0] if team else 0)
                # in a game the row comes out the team's full colour, so the copy's own 70% is not thinned again
                fill = Image.new('RGBA', (8, 8), (int(rgb[0] * c[0]), int(rgb[1] * c[1]), int(rgb[2] * c[2]),
                                                  int(255 * min(1.0, c[3] / 0.7))))
                blit(fill, clip[0], clip[1], clip[2] - clip[0], clip[3] - clip[1], clip, False)
                return
            if sub is not None and depth < 8 and sub.root() is not None:
                sub_ctx = ctx.child(layout.instance_args(n)) if ctx is not None else None
                draw(sub.root(), ax, ay, c, clip, path + (sub.name,), depth + 1, on, sub_ctx,
                     size=(nw, nh) if nw > 0 and nh > 0 else None, team=team)
            return
        kids = n.children
        if n.kind == 0x1C:
            per = n.state_children()
            i = states.get(n.off)
            if i is None:
                sel = layout.selector(n) if ctx is not None else None
                i = ctx.number(sel) if sel else code_states.get(n.off, 0)
            picks[n.off] = i
            pick = per[i] if 0 <= i < len(per) else None
            looks = set(n.states)                   # children that aren't a look are always there
            kids = [k for k in n.children if k is pick or (k.off - n.off) not in looks]
        nclip = clip
        if n.clips and nw > 0 and nh > 0:
            nclip = (max(clip[0], ax), max(clip[1], ay), min(clip[2], ax + nw), min(clip[3], ay + nh))
        for k in kids:
            draw(k, ax, ay, c, nclip, path, depth, on, ctx, *kid, team=team)

    root = asset.root()
    if root is not None:
        ctx = None
        if situation is not None:
            from . import uiquery
            ctx = uiquery.Context(situation)
        draw(root, 0, 0, np.ones(4, np.float32), (0, 0, size[0], size[1]), (asset.name,), 0, False, ctx)
        render.unknown = sorted(ctx.unknown) if ctx is not None else []
    render.picks = picks
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


def scenes(asset):
    """The big pieces stacked in an overlay's frame. The game shows one at a time (the scorebug in play, the team
    logos between innings); the first is the one in play."""
    c = asset.container()
    return [k for k in c.children if k.kind in (0x0F, 0x1C) and k.w > 0 and k.h > 0] if c else []


def popups(layout, asset, scene):
    """[(node, name)] for the see-through groups in a scene that an animation fades in (batter bar, home run...)."""
    out = []

    def label(n):
        for m in n.walk():
            if m.kind == 0x1E:
                sub = layout.by_hash.get(m.ref)
                if sub is not None and not sub.name.startswith(('asset_', 'Main')):
                    return sub.name.replace('InGame_', '').replace('_', ' ')
            if m.kind == 0x1C:
                from . import uiquery
                sel = uiquery.text(layout.selector(m)).strip('[] ')
                if sel:
                    return sel.replace('SCOREBAR ', '').replace('_TAB', '').replace('_', ' ').title()
        return None

    def visit(n, depth):
        for k in n.children:
            if k.kind == 0x0F and k.rgba()[3] == 0 and k.w > 0:
                name = label(k)
                if name:
                    out.append((k, name))
            elif k.kind in (0x0F, 0x1C) and depth < 4:
                visit(k, depth + 1)
    visit(scene, 0)
    seen, uniq = {}, []
    for n, name in out:
        seen[name] = seen.get(name, 0) + 1
        uniq.append((n, name if seen[name] == 1 else f'{name} {seen[name]}'))
    return uniq
