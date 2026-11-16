"""Build a piece of UI from a description: our own boxes, text, logos, team colours and switches, compiled into the
game's layout format and read by the game like its own.

A design is plain data:

    {"name": "MTS_Classic", "size": [640, 44], "pieces": [
        {"box": [0, 0, 640, 44], "color": "#101010", "opacity": 80},
        {"text": "^d0^", "data": ["AWAY_TEAM TEAM_PROF SHORT_NAME"], "at": [12, 6, 90, 32], "size": 28},
        {"logo": "away", "kind": 2, "at": [0, 0, 44, 44]},
        {"team": "home", "at": [320, 0, 320, 44], "opacity": 70},
        {"tint": "away", "group": [...], "at": [0, 0, 320, 44]},
        {"switch": "SCORER OUTS", "at": [500, 0, 60, 44], "looks": [[...], [...], [...]]},
        {"group": [...], "at": [0, 0, 100, 44], "clip": true}]}

text holds ^d0^ ^d1^ where live values go and data names the game query for each (see docs/SCOREBUG_DATA.md); with no
data it is fixed words. A switch draws the look numbered by its query's value. Everything is positioned inside its
parent, in 1920 x 1080 screen pixels.

A tint group gives the boxes and images inside it a team's colour (white takes it exactly, grey takes it darker;
text and logos keep their own). "team_colors": {"HOU": "#eb6e1f"} at the top of a design overrides a club's colour
wherever the design uses it. "enter": {"from": [dx, dy], "fade": true, "frames": 24, "delay": 0} on a piece moves
and fades it in when the design first appears.
"""
import struct

from . import teamart, uiquery
from .uilayout import NONE, P_ALPHA, P_X, P_Y, name_hash

NAMED = (0xA7732924, 0xF2232E7B, 0xFA7C7D26)      # the three animation names every asset lists, even with none
WASH = 0x8948743A                                 # Theme 1's team-colour fill: handed a team, it paints its colour
TEAM = {'away': 'AWAY_TEAM_ID', 'home': 'HOME_TEAM_ID'}
ALIGN = {'left': 0, 'centre': 1, 'center': 1, 'right': 2}


# data a scorebug piece is likely to show; the first block is what the stock scorebug itself reads during play
DATA = ['AWAY_TEAM TEAM_PROF SHORT_NAME', 'HOME_TEAM TEAM_PROF SHORT_NAME', 'SCORER AWAY_SCORE', 'SCORER HOME_SCORE',
        'SCOREBAR INNING_STR [ 0 ]', 'SCOREBAR INNING_STR [ 1 ]', 'IG BALLS', 'IG STRIKES', 'SCORER OUTS',
        'SCOREBAR BATTER_BAR_NAME [ 0 ]', 'CURRENT_BATTER SEASON_STATS AVG', 'CURRENT_BATTER SEASON_STATS HR',
        'CURRENT_BATTER SEASON_STATS RBI', 'PITCH_BAT_STATS PITCH_COUNT', 'SCOREBAR SPEED', 'SCORER PITCH_CLOCK',
        'BoxScore HITS [ 0 ]', 'BoxScore HITS [ 1 ]', 'BoxScore ERRORS [ 0 ]', 'BoxScore ERRORS [ 1 ]',
        'BoxScore INNING_VAL [ 0 , 0 ]', 'BoxScore INNING_VAL [ 1 , 0 ]']
SWITCHES = ['IG IS_BOTTOM', 'SCORER OUTS', 'SCOREBAR 1ST_BASE_TAB', 'SCOREBAR 2ND_BASE_TAB', 'SCOREBAR 3RD_BASE_TAB',
            'IG BALLS', 'IG STRIKES']


def kind_of(piece):
    return next((k for k in ('box', 'image', 'text', 'logo', 'team', 'switch', 'group', 'asset') if k in piece), '?')


def describe(piece):
    """A few words naming a piece, for a list."""
    k = kind_of(piece)
    if k == 'text':
        return f'Text  {piece["text"]}'
    if k in ('logo', 'team'):
        return ('Logo  ' if k == 'logo' else 'Team colour  ') + str(piece[k])
    if k == 'switch':
        return f'Switch  {piece["switch"]}'
    return {'box': 'Box', 'image': 'Image', 'group': 'Group', 'asset': 'Asset'}.get(k, k) + \
        (f'  {piece.get("color", "")}' if k == 'box' else '')


def rect(piece):
    return list(piece.get('at') or piece.get('box') or [0, 0, 10, 10])


def set_rect(piece, at):
    at = [round(float(v), 1) for v in at]
    if 'box' in piece and 'at' not in piece:
        piece['box'] = at
    else:
        piece['at'] = at


def _rgba(color, opacity=None, alpha=None):
    v = int(str(color or '#ffffff').lstrip('#'), 16)
    a = 255 if opacity is None else max(0, min(255, round(float(opacity) * 2.55)))
    return (v >> 16) & 255, (v >> 8) & 255, v & 255, a if alpha is None else alpha


def _query(q):
    q = str(q).strip()
    return q if q.startswith('[') else f'[ {q} ]'


class Builder:
    def __init__(self, name):
        self.name = name
        self.tree = bytearray()
        self.fix = []                 # (position of a u64 in the tree, query text)
        self.static, self.live = {}, {}
        self.n_text = 0
        self.team_colors = {}         # {club: '#rrggbb'}: colours of our own in place of the game's
        self.motions = []             # (node position in the tree, [x, y], alpha, the piece's "enter")

    # ---- nodes
    def _head(self, kind, at, color=(255, 255, 255, 255), size=0x50, flags=1, anchor=5):
        b = bytearray(size)
        b[0:4] = bytes(color)
        x, y, w, h = (float(v) for v in at)
        struct.pack_into('<5f', b, 4, x, y, 0.0, w, h)
        struct.pack_into('<HHHHH', b, 0x1C, 0, anchor, 5, 0x80, 0x80)
        b[0x26], b[0x27] = kind, flags
        struct.pack_into('<I', b, 0x28, 0x184)
        return b

    def group(self, at, pieces, clip=False, color=(255, 255, 255, 255)):
        p = len(self.tree)
        self.tree += self._head(0x0F, at, color)
        for piece in pieces:
            self.piece(piece)
        struct.pack_into('<Q', self.tree, p + 0x38, 0x50)
        struct.pack_into('<I', self.tree, p + 0x48, len(self.tree) - p)
        struct.pack_into('<I', self.tree, p + 0x4C, 0x8000 | (0x100 if clip else 0) | len(pieces))

    def box(self, at, color, texture=None):
        b = self._head(0x18, at, color)
        struct.pack_into('<QQ', b, 0x30, name_hash(texture) if texture else NONE, NONE)
        b[0x48] = 0xFF
        self.tree += b

    def logo(self, at, team, kind=2, color=(255, 255, 255, 255)):
        b = self._head(0x18, at, color)
        struct.pack_into('<QQ', b, 0x30, 0, NONE)
        b[0x48], b[0x4A] = 0xFF, 1
        self.fix.append((len(self.tree) + 0x30, f'[ UI LOGO [ {TEAM[team]} , {int(kind)} ] ]'))
        self.tree += b

    def text(self, at, words, data=(), font=25, size=28, color=(255, 255, 255, 255), align=1,
             outline=(0, 0, 0, 255)):
        self.n_text += 1
        tid = name_hash(f'{self.name}_text_{self.n_text}')
        if data:
            self.live[tid] = (words, [uiquery.tokens(_query(q)) for q in data])
        else:
            self.static[tid] = words
        b = self._head(0x22, at, color, size=0x80)
        b[0x40:0x44] = bytes(outline)
        b[0x44:0x48] = bytes((0, 0, 0, 255))
        b[0x48:0x4C] = bytes((255, 215, 0, 255))
        px = max(1, min(4095, int(round(float(size) * 16))))
        struct.pack_into('<IIfHHIHHI', b, 0x4C, tid, 0, 1.0, px, 0, 0, px, 0x80, 0x870)
        b[0x70], b[0x71], b[0x72] = int(font) & 0x3F, 0x80, 0x10 | ((int(align) & 3) << 2)
        struct.pack_into('<I', b, 0x74, 0x2B)
        self.tree += b

    def instance(self, at, asset_hash, args=(), color=(255, 255, 255, 255)):
        n = len(args)
        size = 0x58 + 8 * n + ((4 * n + 7) // 8) * 8
        b = self._head(0x1E, at, color, size=size)
        struct.pack_into('<QQQQHH', b, 0x30, asset_hash, 0, 0x58 + 8 * n, 0x58, size, n)
        for i, q in enumerate(args):
            self.fix.append((len(self.tree) + 0x58 + 8 * i, _query(q)))
        self.tree += b

    def switch(self, at, query, looks):
        p, n = len(self.tree), len(looks)
        head = 0x78 + 8 * n
        self.tree += self._head(0x1C, at, size=head + 0x10)
        self.fix.append((p + 0x30, _query(query)))
        self.tree += self._head(0x0F, (0, 0, at[2], 0), (255, 255, 255, 0))      # the label every switch carries
        label = len(self.tree) - 0x50
        struct.pack_into('<Q', self.tree, label + 0x38, 0x50)
        struct.pack_into('<II', self.tree, label + 0x48, 0x50, 0x8000)
        first = len(self.tree) - p
        for i, look in enumerate(looks):
            struct.pack_into('<Q', self.tree, p + 0x78 + 8 * i, len(self.tree) - p)
            self.group((0, 0, at[2], at[3]), look)
        struct.pack_into('<QQQQ', self.tree, p + 0x38, head, first, head + 0x10, 0x78)
        struct.pack_into('<II', self.tree, p + 0x6C, len(self.tree) - p, n)

    def _by_team(self, at, side, default, override):
        """The pieces for a team's colour, with our own colour swapped in for the clubs that have one: a chain of
        two-look switches asking "is this club number N?"."""
        inner = default
        for club, color in self.team_colors.items():
            n = teamart.index(club)
            if n < 0:
                raise ValueError(f'{club} is not one of the thirty clubs')
            inner = [{'switch': f'QCOMP [ {side.upper()}_TEAM TEAM_PROF TEAM_INX , == , {n} ]',
                      'at': [0, 0, at[2], at[3]], 'looks': [inner, override(color)]}]
        return inner

    def tinted(self, at, side, pieces, shade=0, clip=False):
        p = len(self.tree)
        self.group(at, pieces, clip)
        self.fix.append((p + 0x40, f'[ UI CAP_TEAM_CLR [ {TEAM[side]}{" , 1" if shade else ""} ] ]'))

    def piece(self, s):
        at = s.get('at') or s.get('box')
        if at is None or len(at) != 4:
            raise ValueError(f'a piece needs "at": [x, y, width, height]: {s}')
        col = _rgba(s.get('color'), s.get('opacity'))
        start = len(self.tree)
        if s.get('enter'):
            self.motions.append((start, [float(at[0]), float(at[1])], col[3], dict(s['enter'])))
        if 'tint' in s:
            side, kids, w, h = s['tint'], s.get('group') or [], at[2], at[3]
            if self.team_colors and not s.get('_plain'):
                own = lambda c: [{'group': kids, 'at': [0, 0, w, h], 'color': c}]
                default = [{'tint': side, 'group': kids, 'at': [0, 0, w, h], 'shade': s.get('shade', 0),
                            '_plain': True}]
                self.group(at, self._by_team(at, side, default, own), bool(s.get('clip')))
            else:
                self.tinted(at, side, kids, s.get('shade', 0), bool(s.get('clip')))
        elif 'team' in s and not s.get('wash'):
            side, w, h = s['team'], at[2], at[3]
            fill = lambda c: [{'box': [0, 0, w, h], 'color': c, 'opacity': s.get('opacity', 100)}]
            default = [{'tint': side, 'group': fill('#ffffff'), 'at': [0, 0, w, h], '_plain': True}]
            self.group(at, self._by_team(at, side, default, fill))
        elif 'box' in s:
            self.box(at, col, s.get('texture'))
        elif 'image' in s:
            self.box(at, col, s['image'])
        elif 'text' in s:
            self.text(at, str(s['text']), s.get('data') or (), s.get('font', 25), s.get('size', 28), col,
                      ALIGN.get(str(s.get('align', 'centre')).lower(), 1), _rgba(s.get('outline', '#000000')))
        elif 'logo' in s:
            self.logo(at, s['logo'], s.get('kind', 2), col)
        elif 'team' in s:
            self.group(at, [], clip=True)
            g = len(self.tree) - 0x50                     # the fill is a big sheet: clip it to this piece
            self.instance((-50, -64, at[2] + 100, at[3] + 128), WASH, [TEAM[s['team']]], col)
            struct.pack_into('<I', self.tree, g + 0x48, len(self.tree) - g)
            struct.pack_into('<I', self.tree, g + 0x4C, 0x8000 | 0x100 | 1)
        elif 'switch' in s:
            self.switch(at, s['switch'], s.get('looks') or [])
        elif 'group' in s:
            self.group(at, s['group'], bool(s.get('clip')), col)
        elif 'asset' in s:
            self.instance(at, name_hash(s['asset']) if isinstance(s['asset'], str) else int(s['asset']),
                          s.get('args') or (), col)
        else:
            raise ValueError(f'not a piece the builder knows: {sorted(s)}')


def _motion(motions, tree_at, at):
    """One animation moving and fading pieces in, as the bytes of an asset's animation section placed at `at`: its
    entry, one track per piece, their channels, their keys."""
    if not motions:
        return b''
    tracks = []
    for pos, (x, y), alpha, m in motions:
        n, d = max(1, int(m.get('frames', 24))), max(0, int(m.get('delay', 0)))
        dx, dy = (list(m.get('from') or [0, 0]) + [0, 0])[:2]
        chans = []
        for prop, a, b in ((P_X, x + dx, x), (P_Y, y + dy, y), (P_ALPHA, 0, alpha)):
            if (prop == P_ALPHA and m.get('fade', True)) or (prop != P_ALPHA and a != b):
                keys = ([(0, a)] if d else []) + [(d, a), (d + n, b)]
                chans.append((prop, keys))
        if chans:
            tracks.append((tree_at + pos, chans))
    if not tracks:
        return b''
    last = max(k[-1][0] for _, chans in tracks for _, k in chans)
    t_at = at + 16
    c_at = t_at + 24 * len(tracks)
    k_at = c_at + 16 * sum(len(c) for _, c in tracks)
    out = bytearray(struct.pack('<QHHI', t_at, len(tracks), last, last))
    chan_bytes, key_bytes = bytearray(), bytearray()
    for node, chans in tracks:
        out += struct.pack('<QQHHHH', c_at + len(chan_bytes), node, 0xFFFF, max(k[-1][0] for _, k in chans),
                           len(chans), 0)
        for prop, keys in chans:
            chan_bytes += struct.pack('<QHBBI', k_at + len(key_bytes), keys[-1][0], len(keys), prop, 0)
            for i, (frame, v) in enumerate(keys):
                if prop == P_ALPHA:
                    key_bytes += struct.pack('<HBBBBH', frame, max(0, min(255, int(round(v)))), 0, 0, 1, 0)
                else:
                    key_bytes += struct.pack('<HBBf', frame, 0, 1 if i == len(keys) - 1 else 6, float(v))
    return bytes(out + chan_bytes + key_bytes)


def build(design):
    """(chunk bytes, hash, fixed words {id: text}, live words {id: (text, [token lists])}) for a design."""
    name = str(design['name'])
    w, h = design['size']
    b = Builder(name)
    b.team_colors = {str(k).upper(): v for k, v in (design.get('team_colors') or {}).items()}
    b.tree += b._head(0x0F, (0, 0, w, h))                       # root, with the pieces in one group under it
    b.tree[0x1E:0x22] = bytes(4)
    b.group((0, 0, w, h), design.get('pieces') or [])
    struct.pack_into('<Q', b.tree, 0x38, 0x50)
    struct.pack_into('<II', b.tree, 0x48, len(b.tree), 0x8000 | 1)
    tree_at = 0x90
    motion = _motion(b.motions, tree_at, tree_at + len(b.tree))
    anim_at = tree_at + len(b.tree)
    named_at = anim_at + len(motion)
    start_at = named_at + 16 * len(NAMED)
    # what to do when the design first appears: play the animation (written the way the game's team row does it)
    start = struct.pack('<QQQQQ', start_at + 24, tree_at, 0x14444, 0x82A, anim_at) if motion else b''
    pool_at = start_at + len(start)
    pool, where = bytearray(), {}
    for _pos, q in b.fix:
        if q in where:
            continue
        toks = uiquery.tokens(q)
        if not toks or uiquery.text(toks) != q:
            raise ValueError(f'the builder does not know every word of {q}')
        where[q] = pool_at + len(pool)
        pool += bytes(16)
    for q, rec in where.items():
        toks = uiquery.tokens(q)
        struct.pack_into('<QQ', pool, rec - pool_at, pool_at + len(pool), len(toks))
        pool += struct.pack(f'<{len(toks)}I', *toks)
        pool += bytes(-len(pool) % 8)
    for pos, q in b.fix:
        struct.pack_into('<Q', b.tree, pos, where[q])
    strings_at = pool_at + len(pool)
    label = name.encode('ascii') + b'\0'
    body = bytearray(0x90)
    sec = [0] * 13
    sec[0], sec[1], sec[7], sec[12] = tree_at, anim_at, named_at, strings_at
    if motion:
        sec[3] = start_at
        struct.pack_into('<HH', body, 0x72, 1, 1)
    struct.pack_into('<13Q', body, 0, *sec)
    struct.pack_into('<I', body, 0x6C, strings_at + len(label))
    struct.pack_into('<H', body, 0x70, 1)
    struct.pack_into('<H', body, 0x7C, len(NAMED))
    struct.pack_into('<HHHH', body, 0x84, 1920, 1080, 0, 39)
    body += b.tree + motion
    for hsh in NAMED:
        body += struct.pack('<IIQ', hsh, 0, 0)
    body += start + pool + label
    body += bytes(-len(body) % 16)
    hsh = name_hash(name)
    return b'VOIDASS0' + struct.pack('<II', hsh, len(body)) + bytes(body), hsh, b.static, b.live


def install(layout, design):
    """Compile a design into a layout file and return its asset. Its words are kept on the layout
    (layout.words) for the .LANG file that goes with it."""
    chunk, hsh, static, live = build(design)
    asset = layout.add_asset(chunk)
    layout.designs.append(design)
    layout.words[0].update(static)
    layout.words[1].update(live)
    return asset
