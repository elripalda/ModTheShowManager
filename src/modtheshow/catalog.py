"""What the game's folders mean: teams, uniforms, ballparks and the packs behind each section of the app."""

TEAMS = {
    'ARI': 'Arizona Diamondbacks', 'ATL': 'Atlanta Braves', 'BAL': 'Baltimore Orioles', 'BOS': 'Boston Red Sox',
    'CHC': 'Chicago Cubs', 'CWS': 'Chicago White Sox', 'CIN': 'Cincinnati Reds', 'CLE': 'Cleveland Guardians',
    'COL': 'Colorado Rockies', 'DET': 'Detroit Tigers', 'HOU': 'Houston Astros', 'KC': 'Kansas City Royals',
    'LAA': 'Los Angeles Angels', 'LAD': 'Los Angeles Dodgers', 'MIA': 'Miami Marlins', 'MIL': 'Milwaukee Brewers',
    'MIN': 'Minnesota Twins', 'NYM': 'New York Mets', 'NYY': 'New York Yankees', 'OAK': 'Athletics',
    'PHI': 'Philadelphia Phillies', 'PIT': 'Pittsburgh Pirates', 'SD': 'San Diego Padres', 'SF': 'San Francisco Giants',
    'SEA': 'Seattle Mariners', 'STL': 'St. Louis Cardinals', 'TB': 'Tampa Bay Rays', 'TEX': 'Texas Rangers',
    'TOR': 'Toronto Blue Jays', 'WSH': 'Washington Nationals', 'AL': 'American League All-Stars',
    'NL': 'National League All-Stars',
}

DIVISIONS = [
    ('AL EAST', ['BAL', 'BOS', 'NYY', 'TB', 'TOR']), ('AL CENTRAL', ['CWS', 'CLE', 'DET', 'KC', 'MIN']),
    ('AL WEST', ['HOU', 'LAA', 'OAK', 'SEA', 'TEX']), ('NL EAST', ['ATL', 'MIA', 'NYM', 'PHI', 'WSH']),
    ('NL CENTRAL', ['CHC', 'CIN', 'MIL', 'PIT', 'STL']), ('NL WEST', ['ARI', 'COL', 'LAD', 'SD', 'SF']),
]

LEAGUES = {'AL': 'American League', 'NL': 'National League', 'AAA': 'Triple-A', 'AA': 'Double-A',
           'NLB': 'Negro Leagues', 'WBC': 'World Baseball Classic', 'NCAA': 'College', 'HS': 'High School',
           'MINIS': 'Mini Seasons', 'JETER': 'Jeter', 'EXTRA': 'Extra', 'SKINS': 'Skins'}

SLOTS = {
    'HOME': 'Home', 'AWAY': 'Away', 'ALT1': 'Alt 1', 'ALT2': 'Alt 2', 'ALT3': 'Alt 3', 'ALT4': 'Alt 4',
    'CC1H': 'City Connect', 'CC2H': 'City Connect 2', 'BPH': 'Batting Practice Home', 'BPA': 'Batting Practice Away',
    'JUL4': 'July 4th', 'ARMF': 'Armed Forces', 'ASGH': 'All-Star Game', 'HRD': 'Home Run Derby',
    'STPAT': "St. Patrick's Day", 'JR42A': 'Jackie Robinson Day', 'SPRH': 'Spring Training Home',
    'SPRA': 'Spring Training Away', 'MEMD': 'Memorial Day', 'MOTH': "Mother's Day", 'FATH': "Father's Day",
}
SLOT_ORDER = ['HOME', 'AWAY', 'ALT1', 'ALT2', 'ALT3', 'ALT4', 'CC1H', 'CC2H']

PARTS = {'UNIFORM.TEX': 'Uniform', 'DECALS.TEX': 'Patches', 'CAPHELMET.TEX': 'Cap & Helmet', 'PANTS.TEX': 'Pants',
         'STANCE.TEX': 'Stance'}

PARKS = {
    'ARZ': 'Chase Field', 'ATL': 'Truist Park', 'BAL': 'Oriole Park at Camden Yards', 'BOS': 'Fenway Park',
    'CHC': 'Wrigley Field', 'CHW': 'Rate Field', 'CIN': 'Great American Ball Park', 'CLE': 'Progressive Field',
    'COL': 'Coors Field', 'DET': 'Comerica Park', 'FLA': 'loanDepot park', 'HOU': 'Daikin Park',
    'KC': 'Kauffman Stadium', 'LAA': 'Angel Stadium', 'LAD': 'Dodger Stadium', 'MIL': 'American Family Field',
    'MIN': 'Target Field', 'NYM': 'Citi Field', 'NYY': 'Yankee Stadium', 'PHI': 'Citizens Bank Park',
    'PIT': 'PNC Park', 'SAC': 'Sutter Health Park', 'SD': 'Petco Park', 'SEA': 'T-Mobile Park', 'SF': 'Oracle Park',
    'STL': 'Busch Stadium', 'TB': 'Tropicana Field', 'TEX': 'Globe Life Field', 'TOR': 'Rogers Centre',
    'WAS': 'Nationals Park', 'OLD_ATL': 'Classic Atlanta Park', 'OLD_FLA': 'Classic Miami Park',
    'OLD_MIN': 'Classic Minnesota Park', 'OLD_NYM': 'Classic New York (NL) Park', 'OLD_NYY': 'Classic Yankee Stadium',
    'OLD_SEA': 'Classic Seattle Park', 'OLD_TEX': 'Classic Texas Park',
}


def park_name(code):
    if code in PARKS:
        return PARKS[code]
    for pre, label in (('WBC_', 'WBC '), ('AX_COLLEGE_', 'College '), ('NGL_', 'Negro Leagues '),
                       ('RTTS_', 'Road to the Show '), ('MILB_', 'Minor League '), ('MINIS_', 'Mini Seasons ')):
        if code.startswith(pre):
            return label + code[len(pre):].replace('_', ' ').title()
    return code.replace('_', ' ').title()


def slot_name(code):
    if code in SLOTS:
        return SLOTS[code]
    if code.startswith('TB') and len(code) >= 4:
        return 'Throwback ' + code[2:].replace('ALTH', ' Alt ').replace('H', ' Home').replace('A', ' Away').strip()
    return code.title()


def _dir(game, rel):
    node = game.tree
    for part in rel.strip('/').split('/'):
        if not part:
            continue
        node = (node.children or {}).get(part)
        if node is None:
            return None
    return node


def packs_in(game, rel, recursive=False):
    """.TEX packs under a folder."""
    node = _dir(game, rel)
    out = []
    if node is None or not node.is_dir:
        return out

    def walk(n):
        for c in sorted(n.children.values(), key=lambda x: x.name):
            if c.is_dir:
                if recursive:
                    walk(c)
            elif c.name.upper().endswith('.TEX'):
                out.append(c.path)
    walk(node)
    return out


def teams(game):
    """[(group label, [(code, name, league)])] for every team that has uniforms."""
    groups = []
    have = {}
    for league in ('AL', 'NL'):
        node = _dir(game, f'NSW/UNIFORMS/{league}')
        if node and node.is_dir:
            for code in node.children:
                have[code] = league
    for label, codes in DIVISIONS:
        rows = [(c, TEAMS[c], have[c]) for c in codes if c in have]
        if rows:
            groups.append((label, rows))
    stars = [(c, TEAMS.get(c, c), have[c]) for c in ('AL', 'NL') if c in have]
    if stars:
        groups.append(('ALL-STARS', stars))
    root = _dir(game, 'NSW/UNIFORMS')
    for league in sorted((root.children if root and root.is_dir else {}).keys()):
        if league in ('AL', 'NL') or not root.children[league].is_dir:
            continue
        rows = [(c, c.title() if len(c) > 4 else c, league) for c in sorted(root.children[league].children)
                if root.children[league].children[c].is_dir]
        if rows:
            groups.append((LEAGUES.get(league, league).upper(), rows))
    return groups


def uniforms(game, league, team):
    """[(slot code, slot name, [pack paths])] in a sensible order."""
    node = _dir(game, f'NSW/UNIFORMS/{league}/{team}')
    if node is None:
        return []
    slots = [c for c in node.children.values() if c.is_dir]
    rank = {s: i for i, s in enumerate(SLOT_ORDER)}
    slots.sort(key=lambda c: (rank.get(c.name, 50), c.name))
    out = []
    for s in slots:
        packs = [c.path for c in sorted(s.children.values(), key=lambda x: x.name) if c.name.upper().endswith('.TEX')]
        if packs:
            out.append((s.name, slot_name(s.name), packs))
    return out


def parks(game):
    node = _dir(game, 'NSW/STADIUMS')
    groups = {'MLB': [], 'CLASSIC': [], 'WORLD BASEBALL CLASSIC': [], 'COLLEGE': [], 'NEGRO LEAGUES': [], 'MORE': []}
    if node is None:
        return []
    for code, c in node.children.items():
        if not c.is_dir or code in ('COMMON', 'PROPS', 'CUSTOM', 'NOWHERE') or code.startswith(('CRAS', 'XCRAS', 'EXT_')):
            continue
        if not packs_in(game, c.path):
            continue
        name = park_name(code)
        if code in PARKS and not code.startswith('OLD_'):
            g = 'MLB'
        elif code.startswith('OLD_'):
            g = 'CLASSIC'
        elif code.startswith('WBC_'):
            g = 'WORLD BASEBALL CLASSIC'
        elif code.startswith('AX_COLLEGE_'):
            g = 'COLLEGE'
        elif code.startswith('NGL_'):
            g = 'NEGRO LEAGUES'
        else:
            g = 'MORE'
        groups[g].append((code, name, c.path))
    return [(g, sorted(rows, key=lambda r: r[1])) for g, rows in groups.items() if rows]


def _nice(p, strip=''):
    n = p.rsplit('/', 1)[1][:-4]
    if strip and n.startswith(strip):
        n = n[len(strip):]
    return n.replace('_', ' ').title().strip() or p.rsplit('/', 1)[1][:-4].title()


def scoreboard_groups(game):
    """[(group, [(label, pack)])] - every in-game overlay pack."""
    themes = {'THEME1': 'Theme 1', 'THEME2': 'Theme 2', 'THEME3': 'Theme 3', 'THEME4': 'Theme 4',
              'THEMEMOMENTS': 'Moments', 'GAME': 'In-Game Shared', 'TRAIN': 'Training'}
    bugs, pres, other = [], [], []
    for p in packs_in(game, 'NSW/UI/GAME', recursive=True):
        code = p.rsplit('/', 1)[1][:-4]
        if '/PRES/' in p:
            pres.append(('Presentation ' + _nice(p, 'PRESOSDS'), p))
        elif code in themes:
            bugs.append((themes[code], p))
        else:
            other.append((_nice(p), p))
    bugs.sort(key=lambda r: list(themes.values()).index(r[0]) if r[0] in themes.values() else 99)
    for folder, label in (('NSW/OSD', 'On-Screen Display'), ('NSW/UI/HRDERBY', 'Home Run Derby')):
        for p in packs_in(game, folder, recursive=True):
            other.append((f'{label}: {_nice(p)}', p))
    out = [('SCOREBUG THEMES', bugs), ('BROADCAST PRESENTATION', pres), ('OTHER OVERLAYS', other)]
    return [(g, rows) for g, rows in out if rows]


def scoreboard_packs(game):
    return [r for _, rows in scoreboard_groups(game) for r in rows]


def menu_groups(game):
    """[(group, [(label, pack)])] - front end, loading screens, creators, player art."""
    def packs(folder, recursive=True):
        return packs_in(game, folder, recursive=recursive)
    groups = []
    rows = [('Loading: ' + _nice(p), p) for p in packs('NSW/LOADINGSCREENBACKGROUNDS')]
    rows += [(_nice(p), p) for p in ('NSW/UI/STATS/DYNAMICLOADINGSCREENS.TEX',) if _dir(game, p)]
    groups.append(('LOADING SCREENS', rows))
    rows = [(_nice(p), p) for p in ('NSW/UI/FRONTEND/FRONTEND.TEX', 'NSW/UI/OPTIONS.TEX', 'NSW/UI/CREATEPLAYEROPTIONS.TEX',
                                     'NSW/UI/QUIRKS.TEX') if _dir(game, p)]
    rows += [(_nice(p), p) for p in packs('NSW/UI/FRONTEND') if p != 'NSW/UI/FRONTEND/FRONTEND.TEX']
    rows += [('Art: ' + _nice(p), p) for p in packs('NSW/UI/ART/TEXTURES')]
    rows += [('Fonts: ' + _nice(p), p) for p in packs('NSW/UI/ART/FONTS')]
    rows += [('Headshots: ' + _nice(p), p) for p in packs('NSW/UI/ART/MUGS')]
    rows += [('Live Content: ' + _nice(p), p) for p in packs('NSW/LIVECONTENT')]
    groups.append(('MENUS & FRONT END', rows))
    groups.append(('UNIFORM CREATOR (fonts, patches, templates)', [(_nice(p), p) for p in packs('NSW/CREATEUNIFORM')]))
    groups.append(('PLAYER CREATOR', [(_nice(p), p) for p in packs('NSW/CREATEPLAYER')]))
    groups.append(('SKY & LIGHTING', [(_nice(p), p) for p in packs('NSW/LIGHTING') + packs('NSW/GROUNDPLANE')]))
    groups.append(('PLAYER ACTION SHOTS', [(_nice(p), p) for p in packs('NSW/UI/ART/ACTIONSHOTS')]))
    return [(g, rows) for g, rows in groups if rows]


def menu_packs(game):
    return [r for _, rows in menu_groups(game) for r in rows]


def bat_packs(game):
    out = []
    for p, label in (('NSW/OBJECTS/BATSKINS.TEX', 'Bat Skins'), ('NSW/OBJECTS/G4BATTEXTURES.TEX', 'Bat Textures & Grips')):
        if _dir(game, p):
            out.append((label, p))
    for p in packs_in(game, 'NSW/OBJECTS/BATWEIGHTS'):
        out.append(('Bat Weight: ' + p.rsplit('_', 1)[1][:-4], p))
    return out
