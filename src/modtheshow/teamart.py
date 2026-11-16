"""Team art for previews: where the game keeps each team's logos, and a colour to wash a team's row with.

The logos are the game's own (NSW/UI/ART/TEXTURES/LOGOn.TEX, one texture per team named logoN_<abbreviation>, with
_cc for City Connect). The colours are a table kept here: close to what the game paints, not read from it yet."""

LOGO_PACKS = {'wordmark': 'NSW/UI/ART/TEXTURES/LOGO1.TEX', 'primary': 'NSW/UI/ART/TEXTURES/LOGO2.TEX',
              'tile': 'NSW/UI/ART/TEXTURES/LOGO4.TEX'}

COLORS = {
    'ATH': '#003831', 'ATL': '#13274F', 'AZ': '#111111', 'BAL': '#DF4601', 'BOS': '#BD3039', 'CHC': '#0E3386',
    'CIN': '#C6011F', 'CLE': '#00385D', 'COL': '#333366', 'CWS': '#27251F', 'DET': '#0C2340', 'HOU': '#002D62',
    'KC': '#004687', 'LAA': '#BA0021', 'LAD': '#005A9C', 'MIA': '#00A3E0', 'MIL': '#12284B', 'MIN': '#002B5C',
    'NYM': '#002D72', 'NYY': '#0C2340', 'PHI': '#E81828', 'PIT': '#27251F', 'SD': '#2F241D', 'SEA': '#0C2C56',
    'SF': '#FD5A1E', 'STL': '#C41E3A', 'TB': '#092C5C', 'TEX': '#003278', 'TOR': '#134A8E', 'WAS': '#AB0003',
}


def color(abbr, default=(40, 40, 40)):
    """(r, g, b) for a team's row."""
    v = COLORS.get(str(abbr).upper().replace('_CC', ''))
    if not v:
        return default
    n = int(v[1:], 16)
    return n >> 16, (n >> 8) & 255, n & 255


def logo_name(abbr, kind='primary', city_connect=False):
    """(pack, texture name) of a team's logo."""
    pack = LOGO_PACKS[kind]
    n = pack.rsplit('/', 1)[1][:-4].lower()
    return pack, f'{n}_{str(abbr).lower()}' + ('_cc' if city_connect else '')


# the game's own numbering of the thirty clubs (TEAM_PROF TEAM_INX), which is also the order of its logo packs
ORDER = ['BAL', 'BOS', 'NYY', 'TB', 'TOR', 'CWS', 'CLE', 'DET', 'KC', 'MIN', 'HOU', 'LAA', 'ATH', 'SEA', 'TEX',
         'ATL', 'MIA', 'NYM', 'PHI', 'WAS', 'CHC', 'CIN', 'MIL', 'PIT', 'STL', 'AZ', 'COL', 'LAD', 'SD', 'SF']


def index(abbr):
    """A club's number in the game, or -1."""
    a = str(abbr).upper().replace('_CC', '')
    return ORDER.index(a) if a in ORDER else -1


def main_color(img):
    """The colour a logo is mostly drawn in, as (r, g, b): the most common of its solid, not-white, not-black
    pixels. None when it has none. Used for a City Connect look, whose colours are not in the table above."""
    if img is None:
        return None
    small = img.convert('RGBA').resize((48, 48))
    seen = {}
    for r, g, b, a in small.getdata():
        if a < 200 or max(r, g, b) < 40 or min(r, g, b) > 215:
            continue
        key = (r >> 4, g >> 4, b >> 4)
        seen[key] = seen.get(key, 0) + 1
    if not seen:
        return None
    r, g, b = max(seen, key=seen.get)
    return r * 16 + 8, g * 16 + 8, b * 16 + 8
