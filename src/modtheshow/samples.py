"""Sample mods, built on this PC from this install's own files (nothing from the game ships with the manager).

Each sample is (key, name, description, build). build(game, lib, current_file) makes the mod and returns it, or
raises ValueError with a line saying why it could not.
"""
import os
import tempfile

from . import codemods, rosterjson, rosters as R, uilayout

AUTHOR = 'Mod the Show Manager'
THEME = 'NSW/UI/GAME/THEME1.NSW'

YANKEES_1927 = {
    'format': rosterjson.FORMAT, 'version': 1,
    'teams': [{
        'team': 'New York Yankees', 'replace': True,
        'players': [
            # the lineup wore no numbers in 1927; these are the ones the club handed out two years later
            {'first': 'Earle', 'last': 'Combs', 'pos': 'CF', 'number': 1, 'bats': 'L', 'throws': 'R', 'height': "6'0",
             'overall': 90, 'ratings': {'contact_vs_r': 105, 'contact_vs_l': 92, 'power_vs_r': 52, 'power_vs_l': 45,
                                        'vision': 92, 'discipline': 80, 'speed': 84, 'fielding': 78}},
            {'first': 'Mark', 'last': 'Koenig', 'pos': 'SS', 'number': 2, 'bats': 'S', 'throws': 'R', 'height': "6'0",
             'overall': 76, 'ratings': {'contact_vs_r': 78, 'contact_vs_l': 74, 'power_vs_r': 38, 'power_vs_l': 35,
                                        'vision': 80, 'discipline': 50, 'speed': 60, 'fielding': 62}},
            {'first': 'Babe', 'last': 'Ruth', 'pos': 'RF', 'number': 3, 'bats': 'L', 'throws': 'L', 'height': "6'2",
             'overall': 99, 'ratings': {'contact_vs_r': 112, 'contact_vs_l': 100, 'power_vs_r': 125, 'power_vs_l': 118,
                                        'vision': 85, 'discipline': 110, 'speed': 55, 'arm_strength': 85}},
            {'first': 'Lou', 'last': 'Gehrig', 'pos': '1B', 'number': 4, 'bats': 'L', 'throws': 'L', 'height': "6'0",
             'overall': 99, 'ratings': {'contact_vs_r': 115, 'contact_vs_l': 102, 'power_vs_r': 118, 'power_vs_l': 105,
                                        'vision': 92, 'discipline': 100, 'speed': 58, 'durability': 99}},
            {'first': 'Bob', 'last': 'Meusel', 'pos': 'LF', 'number': 5, 'bats': 'R', 'throws': 'R', 'height': "6'3",
             'overall': 88, 'ratings': {'contact_vs_r': 92, 'contact_vs_l': 98, 'power_vs_r': 78, 'power_vs_l': 82,
                                        'vision': 70, 'discipline': 55, 'speed': 75, 'arm_strength': 99}},
            {'first': 'Tony', 'last': 'Lazzeri', 'pos': '2B', 'number': 6, 'bats': 'R', 'throws': 'R', 'height': "5'11",
             'overall': 90, 'ratings': {'contact_vs_r': 90, 'contact_vs_l': 96, 'power_vs_r': 84, 'power_vs_l': 90,
                                        'vision': 65, 'discipline': 78, 'speed': 72, 'fielding': 74}},
            {'first': 'Joe', 'last': 'Dugan', 'pos': '3B', 'number': 25, 'bats': 'R', 'throws': 'R', 'height': "5'11",
             'overall': 74, 'ratings': {'contact_vs_r': 74, 'contact_vs_l': 78, 'power_vs_r': 36, 'power_vs_l': 40,
                                        'vision': 78, 'discipline': 45, 'speed': 50, 'fielding': 76}},
            {'first': 'Pat', 'last': 'Collins', 'pos': 'C', 'number': 7, 'bats': 'R', 'throws': 'R', 'height': "5'9",
             'overall': 75, 'ratings': {'contact_vs_r': 70, 'contact_vs_l': 76, 'power_vs_r': 55, 'power_vs_l': 60,
                                        'vision': 60, 'discipline': 90, 'speed': 30, 'blocking': 65}},
            {'first': 'Johnny', 'last': 'Grabowski', 'pos': 'C', 'number': 8, 'bats': 'R', 'throws': 'R',
             'height': "5'10", 'overall': 68, 'ratings': {'contact_vs_r': 68, 'contact_vs_l': 70, 'power_vs_r': 30,
                                                           'power_vs_l': 32, 'blocking': 70}},
            {'first': 'Benny', 'last': 'Bengough', 'pos': 'C', 'number': 9, 'bats': 'R', 'throws': 'R',
             'height': "5'7", 'overall': 66, 'ratings': {'contact_vs_r': 66, 'contact_vs_l': 68, 'power_vs_r': 22,
                                                          'power_vs_l': 24, 'blocking': 78}},
            {'first': 'Ray', 'last': 'Morehart', 'pos': '2B', 'number': 20, 'bats': 'L', 'throws': 'R',
             'height': "5'9", 'overall': 67, 'ratings': {'contact_vs_r': 72, 'contact_vs_l': 60, 'power_vs_r': 28,
                                                          'power_vs_l': 22, 'speed': 62}},
            {'first': 'Mike', 'last': 'Gazella', 'pos': '3B', 'number': 22, 'bats': 'R', 'throws': 'R',
             'height': "5'7", 'overall': 68, 'ratings': {'contact_vs_r': 70, 'contact_vs_l': 74, 'power_vs_r': 26,
                                                          'power_vs_l': 28, 'discipline': 80}},
            {'first': 'Cedric', 'last': 'Durst', 'pos': 'LF', 'number': 27, 'bats': 'L', 'throws': 'L',
             'height': "5'11", 'overall': 65, 'ratings': {'contact_vs_r': 68, 'contact_vs_l': 55, 'power_vs_r': 35,
                                                           'power_vs_l': 28, 'speed': 60}},
            {'first': 'Ben', 'last': 'Paschal', 'pos': 'RF', 'number': 28, 'bats': 'R', 'throws': 'R',
             'height': "5'11", 'overall': 72, 'ratings': {'contact_vs_r': 82, 'contact_vs_l': 88, 'power_vs_r': 50,
                                                           'power_vs_l': 55, 'speed': 64}},
            {'first': 'Julie', 'last': 'Wera', 'pos': '3B', 'number': 29, 'bats': 'R', 'throws': 'R', 'height': "5'8",
             'overall': 60, 'ratings': {'contact_vs_r': 58, 'contact_vs_l': 62, 'power_vs_r': 30, 'power_vs_l': 32}},
            {'first': 'Waite', 'last': 'Hoyt', 'pos': 'SP', 'number': 12, 'bats': 'R', 'throws': 'R', 'height': "6'0",
             'overall': 92, 'ratings': {'stamina': 99, 'h_per_9': 82, 'hr_per_9': 92, 'k_per_9': 42, 'bb_per_9': 90,
                                        'pitching_clutch': 95}},
            {'first': 'Herb', 'last': 'Pennock', 'pos': 'SP', 'number': 11, 'bats': 'S', 'throws': 'L',
             'height': "6'0", 'overall': 88, 'ratings': {'stamina': 95, 'h_per_9': 74, 'hr_per_9': 90, 'k_per_9': 35,
                                                          'bb_per_9': 92, 'pitching_clutch': 99}},
            {'first': 'Urban', 'last': 'Shocker', 'pos': 'SP', 'number': 15, 'bats': 'R', 'throws': 'R',
             'height': "5'10", 'overall': 87, 'ratings': {'stamina': 92, 'h_per_9': 78, 'hr_per_9': 88, 'k_per_9': 30,
                                                           'bb_per_9': 94, 'pitching_clutch': 85}},
            {'first': 'Dutch', 'last': 'Ruether', 'pos': 'SP', 'number': 16, 'bats': 'L', 'throws': 'L',
             'height': "6'1", 'overall': 80, 'ratings': {'stamina': 88, 'h_per_9': 72, 'hr_per_9': 85, 'k_per_9': 30,
                                                          'bb_per_9': 78}},
            {'first': 'George', 'last': 'Pipgras', 'pos': 'SP', 'number': 14, 'bats': 'R', 'throws': 'R',
             'height': "6'1", 'overall': 78, 'ratings': {'stamina': 85, 'h_per_9': 76, 'hr_per_9': 80, 'k_per_9': 52,
                                                          'bb_per_9': 62}},
            {'first': 'Wilcy', 'last': 'Moore', 'pos': 'RP', 'number': 18, 'bats': 'R', 'throws': 'R', 'height': "6'0",
             'overall': 90, 'ratings': {'stamina': 70, 'h_per_9': 88, 'hr_per_9': 99, 'k_per_9': 38, 'bb_per_9': 88,
                                        'pitching_clutch': 99}},
            {'first': 'Bob', 'last': 'Shawkey', 'pos': 'RP', 'number': 17, 'bats': 'R', 'throws': 'R',
             'height': "5'11", 'overall': 74, 'ratings': {'stamina': 55, 'h_per_9': 74, 'hr_per_9': 82, 'k_per_9': 55,
                                                           'bb_per_9': 72}},
            {'first': 'Myles', 'last': 'Thomas', 'pos': 'RP', 'number': 19, 'bats': 'R', 'throws': 'R',
             'height': "5'9", 'overall': 66, 'ratings': {'stamina': 50, 'h_per_9': 62, 'hr_per_9': 78, 'k_per_9': 30,
                                                          'bb_per_9': 55}},
            {'first': 'Joe', 'last': 'Giard', 'pos': 'RP', 'number': 21, 'bats': 'L', 'throws': 'L', 'height': "5'10",
             'overall': 60, 'ratings': {'stamina': 40, 'h_per_9': 50, 'hr_per_9': 70, 'k_per_9': 35, 'bb_per_9': 45}},
            {'first': 'Walter', 'last': 'Beall', 'pos': 'RP', 'number': 23, 'bats': 'R', 'throws': 'R',
             'height': "5'10", 'overall': 58, 'ratings': {'stamina': 35, 'h_per_9': 58, 'hr_per_9': 72, 'k_per_9': 60,
                                                           'bb_per_9': 30}},
        ],
    }],
}


def _mod(lib, name, description):
    mod = next((m for m in lib.list() if m.name == name), None)
    if mod is None:
        mod = lib.create(name, AUTHOR, description)
    return mod


def _roster_mod(game, lib, current_file, name, description, change):
    fs = game.file_set()
    if R.ROSTERS not in fs or R.PLAYERS not in fs:
        raise ValueError('This install has no roster files.')
    db = R.Database(game.original(R.ROSTERS), game.original(R.PLAYERS))
    note = change(db)
    mod = _mod(lib, name, description)
    sources = {rel: game.original(rel) for base in (R.ROSTERS, R.PLAYERS) for rel in R.variants(base)
               if rel in fs and os.path.exists(game.original(rel))}
    tmp = tempfile.mkdtemp(prefix='mts_')

    def out(rel, data):
        p = os.path.join(tmp, os.path.basename(rel))
        with open(p, 'wb') as f:
            f.write(data)
        lib.add_file(mod, rel, p)
    db.write(sources, out)
    return mod, note


def yankees_1927(game, lib, current_file):
    """A league pack in its shareable form: the mod holds the roster file, and Apply carries it out."""
    mod = _mod(lib, 'Sample: 1927 Yankees',
               'Murderers’ Row takes over the Yankees. Ruth and Gehrig use the game’s own legends; the rest are new '
               'players with built faces.')
    folder = os.path.join(mod.path, 'rosters')
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, '1927 Yankees.json'), 'w', encoding='utf-8') as f:
        f.write(rosterjson.dump(YANKEES_1927))
    return mod, '25 players in a roster file. Nothing from the game is in this mod, so it can be shared.'


def moonshot_league(game, lib, current_file):
    def change(db):
        n = 0
        for p in db.players:
            if p.team < 30 and not p.pitcher and p.att is not None:
                db.set_player(p, ratings={'POWER_LEFT': 125, 'POWER_RIGHT': 125})
                n += 1
        return f'{n} hitters set to 125 power.'
    return _roster_mod(game, lib, current_file, 'Sample: Moonshot League',
                       'Every MLB hitter has 125 power against both hands. Pairs well with the Moonshot code mod.',
                       change)


def scorebug_corner(game, lib, current_file):
    if THEME not in game.file_set():
        raise ValueError('This install has no scorebug layout (THEME1.NSW).')
    asset = uilayout.Layout.open(game.original(THEME)).find('Scorebar')
    if asset is None or asset.container() is None:
        raise ValueError('The scorebug was not found in the layout.')
    mod = _mod(lib, 'Sample: Scorebug Bottom Left', 'Moves the scorebug to the bottom left corner. Change it again in '
               'Scoreboards, Layout.')
    folder = os.path.join(mod.path, 'layouts')
    os.makedirs(folder, exist_ok=True)
    import json
    with open(os.path.join(folder, 'scorebug.json'), 'w', encoding='utf-8') as f:
        json.dump([{'file': THEME, 'asset': 'Scorebar', 'x': 40, 'y': 838}], f, indent=2)
    return mod, 'Scorebug moves to 40, 838 when applied.'


# colour styles for Theme 1's scorebug, matched by the colours the game paints it with
MIDNIGHT = [
    {'from': '#cecece', 'to': '#18202e'},
    {'from': '#c0c0c0', 'to': '#18202e'},
    {'from': '#e0e0e0', 'to': '#222c3f'},
    {'from': '#dbdbdb', 'to': '#222c3f'},
    {'from': '#ffffff', 'texture': 'gradient_vertical', 'opacity': 12},
    {'from': '#ffffff', 'texture': '', 'kind': 'image', 'to': '#f2b632'},
    {'from': '#2f3641', 'to': '#f2b632'},
    {'from': '#8c8c8c', 'to': '#34405a'},
    {'from': '#252c34', 'kind': 'text', 'to': '#ffffff'},
    {'from': '#323232', 'kind': 'text', 'to': '#ffffff'},
    {'from': '#252c34', 'texture': 't1_outbkg', 'to': '#0b111c'},
    {'from': '#ffffff', 'texture': 'theshownetworkhorizontal', 'to': '#f2b632'},
]
BRICK_SAND = [
    {'from': '#cecece', 'to': '#6e1a25'},
    {'from': '#c0c0c0', 'to': '#6e1a25'},
    {'from': '#e0e0e0', 'to': '#e6d8b5'},
    {'from': '#dbdbdb', 'to': '#e6d8b5'},
    {'from': '#ffffff', 'texture': 'gradient_vertical', 'opacity': 18},
    {'from': '#ffffff', 'texture': '', 'kind': 'image', 'to': '#e6d8b5'},
    {'from': '#2f3641', 'to': '#3f0e15'},
    {'from': '#8c8c8c', 'to': '#b9a77e'},
    {'from': '#252c34', 'kind': 'text', 'to': '#3f0e15'},
    {'from': '#323232', 'kind': 'text', 'to': '#f6eedb'},
    {'from': '#252c34', 'texture': 't1_outbkg', 'to': '#3f0e15'},
    {'from': '#ffffff', 'texture': 'theshownetworkhorizontal', 'to': '#e6d8b5'},
]
FLAT_WHITE = [
    {'from': '#cecece', 'to': '#f5f5f3'},
    {'from': '#c0c0c0', 'to': '#f5f5f3'},
    {'from': '#e0e0e0', 'to': '#ffffff'},
    {'from': '#dbdbdb', 'to': '#ffffff'},
    {'from': '#ffffff', 'texture': 'gradient_vertical', 'opacity': 0},
    {'from': '#808080', 'texture': 'gradient_vertical', 'opacity': 0},
    {'from': '#000000', 'texture': 'gradient_vertical', 'opacity': 0},
    {'from': '#ffffff', 'texture': 't1_chvrns', 'opacity': 0},
    {'from': '#ffffff', 'texture': '', 'kind': 'image', 'to': '#111111'},
    {'from': '#2f3641', 'to': '#111111'},
    {'from': '#8c8c8c', 'to': '#d6d6d2'},
    {'from': '#252c34', 'kind': 'text', 'to': '#111111'},
    {'from': '#323232', 'kind': 'text', 'to': '#111111'},
    {'from': '#252c34', 'texture': 't1_outbkg', 'to': '#111111'},
    {'from': '#ffffff', 'texture': 'theshownetworkhorizontal', 'to': '#111111'},
]


def _scorebug_style(game, lib, name, description, colours):
    if THEME not in game.file_set():
        raise ValueError('This install has no scorebug layout (THEME1.NSW).')
    asset = uilayout.Layout.open(game.original(THEME)).find('Scorebar')
    if asset is None or asset.container() is None:
        raise ValueError('The scorebug was not found in the layout.')
    mod = _mod(lib, name, description)
    folder = os.path.join(mod.path, 'layouts')
    os.makedirs(folder, exist_ok=True)
    import json
    with open(os.path.join(folder, 'scorebug-style.json'), 'w', encoding='utf-8') as f:
        json.dump([{'file': THEME, 'asset': 'Scorebar', 'colours': colours}], f, indent=2)
    return mod, 'Pick scorebug Theme 1 in the game’s settings, apply, and start a game.'


def scorebug_midnight(game, lib, current_file):
    return _scorebug_style(game, lib, 'Sample: Midnight Scorebug', 'Theme 1 in deep navy with gold lines and white '
                           'scores.', MIDNIGHT)


def scorebug_brick(game, lib, current_file):
    return _scorebug_style(game, lib, 'Sample: Brick & Sand Scorebug', 'Theme 1 in brick red with sand trim.',
                           BRICK_SAND)


def scorebug_flat(game, lib, current_file):
    return _scorebug_style(game, lib, 'Sample: Flat White Scorebug', 'Theme 1 flat and white: no gradients or '
                           'chevrons, black lines and scores.', FLAT_WHITE)


def arcade_code(game, lib, current_file):
    mod = _mod(lib, codemods.ARCADE_NAME, 'Auto PCI, moonshots, juiced ball and more. Switch them on in Code Plugins.')
    folder = os.path.join(mod.path, 'code')
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, 'arcade.patch'), 'w', encoding='utf-8') as f:
        f.write(codemods.ARCADE)
    return mod, 'Tick the ones you want in Code Plugins, then Rebuild Game.'


SAMPLES = [
    ('yankees', 'Sample: 1927 Yankees', 'A classic roster brought in from a roster file: 25 players, built faces for '
     'the ones the game doesn’t have, lineups set for you.', yankees_1927),
    ('moonshot', 'Sample: Moonshot League', 'A ratings mod: every MLB hitter gets 125 power.', moonshot_league),
    ('scorebug', 'Sample: Scorebug Bottom Left', 'A layout mod: the scorebug moves to the bottom left corner.',
     scorebug_corner),
    ('midnight', 'Sample: Midnight Scorebug', 'A scorebug style: navy, gold lines, white scores.', scorebug_midnight),
    ('brick', 'Sample: Brick & Sand Scorebug', 'A scorebug style: brick red with sand trim.', scorebug_brick),
    ('flat', 'Sample: Flat White Scorebug', 'A scorebug style: flat white, no gradients, black scores.',
     scorebug_flat),
    ('arcade', codemods.ARCADE_NAME, 'Code mods: Auto PCI, Perfect-Perfect, moonshots, juiced ball, thin air and more.',
     arcade_code),
]
