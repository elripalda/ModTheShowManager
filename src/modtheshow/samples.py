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
    def change(db):
        rep = rosterjson.apply(db, YANKEES_1927)
        return rep.text()
    return _roster_mod(game, lib, current_file, 'Sample: 1927 Yankees',
                       'Murderers’ Row takes over the Yankees. Ruth and Gehrig use the game’s own legends; the rest '
                       'are new players with built faces.', change)


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
    layout = uilayout.Layout.open(game.original(THEME))
    asset = layout.find('Scorebar')
    node = asset.container() if asset else None
    if node is None:
        raise ValueError('The scorebug was not found in the layout.')
    layout.move(node, 40, 838)
    mod = _mod(lib, 'Sample: Scorebug Bottom Left', 'Moves the scorebug to the bottom left corner. Change it again in '
               'Scoreboards, Layout.')
    tmp = os.path.join(tempfile.mkdtemp(prefix='mts_'), 'THEME1.NSW')
    with open(tmp, 'wb') as f:
        f.write(layout.bytes())
    lib.add_file(mod, THEME, tmp)
    return mod, 'Scorebug moved to 40, 838.'


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
    ('arcade', codemods.ARCADE_NAME, 'Code mods: Auto PCI, Perfect-Perfect, moonshots, juiced ball, thin air and more.',
     arcade_code),
]
