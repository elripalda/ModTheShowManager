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
