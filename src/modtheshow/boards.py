"""Stadium boards: the scoreboards inside a ballpark.

A park's boards are layouts in the same format as the scorebug, kept beside the park:

    NSW/STADIUMS/<PARK>/SCOREBOARD/<PARK>.NSW  .TEX  .LANG_EN     the park's own screens
    NSW/STADIUMS/<PARK>/SCOREBOARD.SCR                            which screen is drawn onto which sign
    NSW/STADIUMS/COMMON/SCOREBOARD/                               boards shared by many parks

SCOREBOARD.SCR is plain text. Each ScriptUIElem block names a sign in the park's model (targetname), the layout file
(uiname), the screen in it (uiscreenname) and the size of the picture the game draws it into.

Unlike the scorebug, a board's colours are painted in: the park's reds and blues are plain numbers on its pieces. So
a board is matched to a scorebug by moving those numbers onto the scorebug's palette."""
import colorsys
import re

from . import uilayout

ROOT = 'NSW/STADIUMS'
COMMON = ROOT + '/COMMON/SCOREBOARD'
KINDS = (('_COTW', 'Postseason'), ('_HRD', 'Home Run Derby'), ('_CLOCKANALOG', 'Clock'), ('_ASG', 'All-Star Game'))
FILL = (0x18, 0x01, 0x04)          # nodes that draw a picture or a plain box
TEXT = 0x22
GROUP = 0x0F


def is_board(rel):
    r = str(rel).upper().strip('/')
    return r.startswith(ROOT + '/') and '/SCOREBOARD/' in r


def park_of(rel):
    """The park folder a board file belongs to ('ARZ'), or 'COMMON'."""
    parts = str(rel).upper().strip('/').split('/')
    return parts[2] if len(parts) > 3 else ''


def script_of(rel):
    """The .SCR beside a park's boards that says where each screen is shown."""
    park = park_of(rel)
    return f'{ROOT}/{park}/SCOREBOARD.SCR' if park and park != 'COMMON' else None


def script(text):
    """The blocks of a SCOREBOARD.SCR: [{'id', 'about', 'targetname', 'uiname', 'uiscreenname', 'type',
    'properties', 'width', 'height'}]. about is the comment written above the block."""
    out, about = [], ''
    lines = text.replace('\r', '').split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        m = re.match(r'ScriptUIElem\s+(\w+)\s*\{?', line)
        if m:
            e = {'id': m.group(1), 'about': about}
            i += 1
            while i < len(lines) and '}' not in lines[i]:
                body = lines[i].split('//')[0]
                kv = re.match(r'\s*(\w+)\s*=\s*"?([^";]*)"?\s*;', body)
                if kv:
                    v = kv.group(2).strip()
                    e[kv.group(1).lower()] = int(v) if v.isdigit() else v
                i += 1
            out.append(e)
            about = ''
        elif line.startswith('//'):
            t = line.lstrip('/ ').strip()
            if t and not set(t) <= set('*- ') and '****' not in t:
                about = t
        i += 1
    return out


def where_shown(blocks, park):
    """{screen name in lower case: block} for the screens of a park's own file."""
    out = {}
    for e in blocks:
        ui = str(e.get('uiname', '')).replace('\\', '/').rsplit('/', 1)[-1].lower()
        screen = str(e.get('uiscreenname') or e.get('uiname') or '').replace('\\', '/').rsplit('/', 1)[-1].lower()
        if screen and (ui == park.lower() or not e.get('uiscreenname')):
            out.setdefault(screen, e)
    return out


def size(asset):
    """(width, height) of the picture a board screen fills."""
    c = asset.container()
    if c is None or c.w <= 0 or c.h <= 0:
        return 1920, 1080
    return max(16, int(round(c.w))), max(16, int(round(c.h)))


def _hex(color):
    r, g, b, _ = uilayout.rgba(color)
    return f'#{r:02x}{g:02x}{b:02x}'


def _nodes(layout):
    for a in layout.assets:
        if a.container() is None:
            continue
        for n in a.nodes():
            yield n


def _counts(n):
    """Whether a node's colour is one the eye reads as a colour of the board: text, a plain box, or a tint that is
    not plain white (white on a picture or a group leaves it as drawn)."""
    if n.kind == TEXT:
        return True
    if n.kind in FILL:
        return n.ref in (uilayout.NONE, 0) or (n.color & 0xFFFFFF) != 0xFFFFFF
    if n.kind == GROUP:
        return (n.color & 0xFFFFFF) != 0xFFFFFF
    return False


def colours(layout):
    """The colours a board file is painted in, biggest first: [('#rrggbb', how much of the board)]. See-through
    pieces count for less."""
    seen = {}
    for n in _nodes(layout):
        if not _counts(n) or n.w <= 0 or n.h <= 0:
            continue
        alpha = (n.color >> 24) / 255
        if alpha <= 0.02:
            continue
        area = n.w * n.h * alpha * (0.35 if n.kind == TEXT else 1.0)
        seen[_hex(n.color)] = seen.get(_hex(n.color), 0) + area
    return sorted(seen.items(), key=lambda kv: -kv[1])


def recolour(layout, old, new):
    """Every piece of a board file painted old ('#rrggbb') gets new. Opacity is kept. Returns how many changed."""
    v = int(new.lstrip('#'), 16)
    rgb = (v >> 16) & 255, (v >> 8) & 255, v & 255
    n_changed = 0
    for n in _nodes(layout):
        if _counts(n) and _hex(n.color) == old.lower():
            layout.recolor(n, rgb=rgb)
            n_changed += 1
    return n_changed


def _hsv(c):
    v = int(c.lstrip('#'), 16)
    return colorsys.rgb_to_hsv(((v >> 16) & 255) / 255, ((v >> 8) & 255) / 255, (v & 255) / 255)


def _light(c):
    v = int(c.lstrip('#'), 16)
    return (0.299 * ((v >> 16) & 255) + 0.587 * ((v >> 8) & 255) + 0.114 * (v & 255)) / 255


def _mix(a, b, t):
    x, y = int(a.lstrip('#'), 16), int(b.lstrip('#'), 16)
    ch = lambda s: round(((x >> s) & 255) * (1 - t) + ((y >> s) & 255) * t)
    return f'#{ch(16):02x}{ch(8):02x}{ch(0):02x}'


def is_accent(c):
    h, s, v = _hsv(c)
    return s >= 0.28 and v >= 0.22


def roles(palette):
    """A palette (most used first) as (dark, light, [accents]): its darkest and lightest colours and the ones with
    colour in them, most used first."""
    palette = [str(c).lower() for c in palette if c]
    if not palette:
        return '#101010', '#ffffff', []
    plain = [c for c in palette if not is_accent(c)] or palette
    dark = min(plain, key=_light)
    light = max(palette, key=_light)
    if _light(light) - _light(dark) < 0.25:                # a palette with no light colour: words still need one
        light = '#ffffff' if _light(dark) < 0.5 else '#101010'
    return dark, light, [c for c in palette if is_accent(c) and c not in (dark, light)]


def match(layout, palette, keep_main=True):
    """Move a board's colours onto a scorebug's palette. Blacks, greys and whites land on a ramp from the
    palette's darkest colour (black) to its lightest (white), each by how light it is; each of the board's own colours takes one of
    the palette's. keep_main leaves the board's biggest colour alone: that is the park's club colour, which the
    scorebug shows too, as the team's. Returns {old: new} for what changed."""
    dark, light, accent = roles(palette)
    have = [c for c, _ in colours(layout)]
    main = next((c for c in have if is_accent(c)), None) if keep_main else None
    plan, k = {}, 0
    for c in have:
        if is_accent(c):
            if not accent or c == main:
                continue
            new = accent[k % len(accent)]
            k += 1
        else:
            new = _mix(dark, light, _light(c))
        if new != c:
            plan[c] = new
    # one pass over the nodes, so a colour that is another's target is not moved twice
    for n in _nodes(layout):
        if _counts(n):
            new = plan.get(_hex(n.color))
            if new:
                v = int(new[1:], 16)
                layout.recolor(n, rgb=((v >> 16) & 255, (v >> 8) & 255, v & 255))
    return plan


def fonts_used(layout):
    """{game font number: how many text boxes use it}."""
    out = {}
    for n in _nodes(layout):
        if n.kind == TEXT:
            f = layout.text_font(n)
            out[f] = out.get(f, 0) + 1
    return out


def set_font(layout, number, only=None):
    """Every text box of a board file (or only those using font `only`) takes game font `number`."""
    k = 0
    for n in _nodes(layout):
        if n.kind == TEXT and (only is None or layout.text_font(n) == only) and layout.text_font(n) != number:
            layout.set_text_font(n, number)
            k += 1
    return k


def label(rel):
    """A board file's name for a list: ('Chase Field', 'Postseason')."""
    from . import catalog
    park = park_of(rel)
    stem = str(rel).upper().rsplit('/', 1)[-1].rsplit('.', 1)[0]
    if park == 'COMMON':
        return 'Shared', stem.replace('_', ' ').title()
    kind = next((name for suffix, name in KINDS if stem.endswith(suffix)), '')
    if not kind and stem != park:
        kind = stem[len(park):].strip('_').replace('_', ' ').title() if stem.startswith(park) else stem.title()
    return catalog.park_name(park), kind
