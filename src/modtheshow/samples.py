"""Sample mods, built on this PC from this install's own files (nothing from the game ships with the manager).

Each sample is (key, name, description, build). build(game, lib, current_file) makes the mod and returns it, or
raises ValueError with a line saying why it could not.
"""
import os
import struct
import tempfile

from . import rosterjson, rosters as R, uilayout
from .uilayout import name_hash

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


# smoked glass: the light plates go dark and see-through, the dark lines and letters go white
GLASS = [
 {'from': '#cecece', 'kind': 'image', 'texture': '', 'solid': True, 'to': '#0b0f16', 'opacity': 52},
 {'from': '#c0c0c0', 'kind': 'image', 'texture': '', 'solid': True, 'to': '#0b0f16', 'opacity': 52},
 {'from': '#e0e0e0', 'kind': 'image', 'texture': '', 'solid': True, 'to': '#0b0f16', 'opacity': 46},
 {'from': '#dbdbdb', 'kind': 'image', 'texture': '', 'solid': True, 'to': '#0b0f16', 'opacity': 46},
 {'from': '#ffffff', 'texture': 't2_texture_chalk', 'opacity': 5},
 {'from': '#6e6e6e', 'texture': 'gradient_radial', 'opacity': 0},
 {'from': '#323232', 'kind': 'image', 'texture': '', 'to': '#ffffff'},
 {'from': '#2f3641', 'to': '#ffffff'},
 {'from': '#8c8c8c', 'kind': 'image', 'texture': '', 'to': '#ffffff', 'opacity': 20},
 {'from': '#000000', 'kind': 'text', 'to': '#ffffff'},
 {'from': '#252c34', 'kind': 'text', 'to': '#ffffff'},
 {'from': '#323232', 'kind': 'text', 'to': '#ffffff'},
 {'from': '#252c34', 'texture': 't1_outbkg', 'to': '#05070b'},
]

ROW = 0xDC303B63          # Theme 1's team row: one template, drawn for each team


def wide_top_bar(lay, split=False, gap=0):
    """Rearrange Theme 1's scorebug into one wide strip across the top: away row, home row, then inning, bases,
    count and outs in a line. The pitcher and batter bars keep rising above it, so the strip sits low enough for
    the tallest of them. Works on the stock layout.

    split puts the inning-to-outs block in the middle and gives the home team a mirrored row (score inside, logo
    on the outer edge), which takes a second copy of the row template. gap (with split) parts the three blocks
    into separate tiles, the frame shrinking to sit behind the middle one."""
    mirrored = None
    if split:
        if ROW not in lay.by_hash:
            raise ValueError('The team row was not found in the layout.')
        mirrored = lay.clone(lay.by_hash[ROW], 'MTS_TeamRow_Mirrored')
        lay.mirror(mirrored)
    a = lay.find('Scorebar')
    c = a.container() if a else None
    if c is None or not c.children or not c.children[0].children:
        raise ValueError('The scorebug was not found in the layout.')
    H, RW, IW = 62, 315, 260                 # strip height, team row width, width of the inning-to-outs block
    gap = gap if split else 0
    W = 2 * RW + IW + 2 * gap
    TOP = 148                                # the strip's top edge on screen: room for the batter panel above it

    def at(rel, kind=None):
        n = lay.node_at(a, rel, kind)
        if n is None:
            raise ValueError('This scorebug is not laid out like the stock Theme 1, so the wide bar cannot be built.')
        return n
    panel, info, home, away = at(0x4910, 0x0F), at(0x4BA0, 0x0F), at(0x9BC8, 0x0F), at(0x9D40, 0x0F)
    win, banner, glow, kzone = at(0x9EB8, 0x0F), at(0xA0E0, 0x0F), at(0x10250, 0x0F), at(0x102F0, 0x1C)
    card = at(0x3F48, 0x0F)
    if round(away.w) != 259 or round(info.w) != 212:
        raise ValueError('This scorebug has already been rearranged. Start from the stock layout.')
    lay.move(c, (1920 - W) / 2, TOP - 55)              # the strip starts 55 below the container's own top
    lay.resize(c, W + 10, c.h)
    # the frame behind everything (behind the middle tile only, when the blocks are parted)
    block = 5 + (RW + gap if split else 2 * RW)
    FW = IW if gap else W
    if gap:
        lay.move(panel, block, panel.y)
    lay.resize(panel, FW, H + 4)
    for k in panel.children:
        if k.kind == 0x1E or (k.kind == 0x0F and k.w > 400):
            lay.resize(k, FW, H + 4 if k.kind == 0x1E else H + 2)
        elif k.kind == 0x18 and k.w > 400:
            lay.resize(k, FW - (473 - k.w), k.h)
        elif k.kind == 0x18:                               # the shade down the right edge
            lay.move(k, FW - 40, k.y)
            lay.resize(k, k.w, H - 2)
            if split:
                lay.recolor(k, alpha=0)
    # the two team rows, side by side
    for row, x in ((away, 5), (home, 5 + RW + (IW + 2 * gap if split else 0))):
        lay.move(row, x, 14)
        lay.resize(row, RW, H)
        lay.resize(row.children[0], RW, H)
    if split:
        lay.retarget(home.children[0], mirrored)
    # inning, bases, count, outs in one line
    lay.move(info, block, 14)
    lay.resize(info, IW, H)
    slide = info.children[0]
    lay.resize(slide, IW, H)
    lay._keys(slide, uilayout.P_X, lambda v: v if v < 100 else v + (IW - 214))     # it slides a full block aside
    body, looks, play = at(0x4C40, 0x0F), at(0x4C90, 0x1C), at(0x4DF0, 0x0F)
    for n in (body, looks, play):
        lay.resize(n, IW, H)
    bases, outs, inning, count, lines = at(0x4E40), at(0x6710), at(0x6E28), at(0x7288), at(0x7358)
    lay.scale_tree(inning, 0.80)
    lay.move(inning, -20, -9)
    lay.scale_tree(bases, 0.74)
    lay.move(bases, 44, 5)
    lay.move(count, 118, 6)
    lay.move(outs, 190, 6)
    lay.recolor(lines, alpha=0)
    # "MID 1ST": the block that slides in between innings
    eoi = at(0x8F38, 0x0F)
    lay.move(eoi, -IW, 0)
    lay.resize(eoi, IW, H)
    for k in eoi.children:
        lay.resize(k, IW, H)
    # what sits on top of the strip
    lay.resize(win, W, H)
    lay.resize(glow, W, glow.h)
    for k in glow.children:
        lay.resize(k, k.w * W / 473, k.h)
    lay.move(kzone, block, 14)
    lay.scale_tree(kzone, H / 103)
    lay.recolor(banner, alpha=0)
    # the player card is too tall to rise above a top bar: it hangs under the strip's right end instead
    lay.move(card, 5 + W - card.w, 14 + H + 8)
    return a


def glass_bar(lay, table):
    """Three floating tiles of smoked glass: a team at each end, tinted its own colour, and the game state between
    them. table is the theme pack's texture names by hash (Layout.texture_table)."""
    a = wide_top_bar(lay, split=True, gap=10)
    lay.repaint(a, GLASS, table)
    return a


# textures in Theme 1's pack that no layout draws (equipment brand marks): a design's own pictures go into these
CARRIERS = ['100percent_logo', '44pro_logo', 'aria_logo', 'b45_logo', 'bwp_logo', 'brucebolt_logo',
            'dingerbats_logo', 'gform_logo', 'lizardskin_logo', 'oldhickory_logo', 'taterbats_logo', 'trinity_logo']


THEMES = tuple(f'NSW/UI/GAME/THEME{n}.NSW' for n in (1, 2, 3, 4))      # the scorebugs a design can take the place of
_PICTURES = (0x18, 0x01, 0x04)


def scorebug_frame(lay, a):
    """The nodes from a scorebug's container down to its window: the first piece in the scene in play that is
    another overlay, always shown, and about the size of the bug. A design is drawn in its place. None when the
    scorebug has no such piece."""
    from . import uirender
    c = a.container() if a else None
    sc = uirender.scenes(a) if c is not None else []
    if not sc:
        return None

    def walk(n, path):
        for k in n.children:
            if (k.color >> 24) == 0 or n.kind == 0x1C:        # faded out, or one look of several: not always shown
                continue
            if k.kind == 0x1E and k.w >= 0.5 * c.w and k.h >= 0.4 * c.h and k.ref in lay.by_hash:
                return path + [k]
            hit = walk(k, path + [k])
            if hit:
                return hit
        return None
    return walk(sc[0], [c, sc[0]])


def _spare_textures(lay, hidden, textures):
    """Textures of the pack that only the hidden pieces drew, biggest first: with those pieces gone a design's own
    pictures can take them over. hidden: node offsets. textures: {name: (width, height)} of the pack."""
    by_hash = {name_hash(n): n for n in textures}
    gone, kept = set(), set()
    for x in lay.assets:
        for n in x.nodes():
            if n.kind in _PICTURES and n.ref in by_hash:
                (gone if n.off in hidden else kept).add(n.ref)
    spare = [by_hash[h] for h in gone - kept if min(textures[by_hash[h]]) >= 32]
    return sorted(spare, key=lambda n: (-textures[n][0] * textures[n][1], n))


def replace_scorebug(lay, design, x=None, y=None, textures=None):
    """Swap a theme's scorebug for a design of our own (uibuild): the stock pieces are hidden and the design is
    drawn where the bug's window was. x, y place its top-left corner; by default it sits bottom centre. On Theme 1
    a design with "bars": true keeps the game's batter and pitcher bars, rising from its top edge. textures:
    {name: (width, height)} of the theme's pack, which a design with pictures of its own needs on the other
    themes. Leaves lay.carriers (the textures its pictures may take) and lay.design_origin (how far the design
    sits from the scorebug's own corner)."""
    from . import uibuild
    a = lay.find('Scorebar')
    if a is None or a.container() is None:
        raise ValueError('This layout has no scorebug.')
    panel = lay.node_at(a, 0x4910, 0x0F)
    main = next((k for k in panel.children if k.kind == 0x1E), None) if panel is not None else None
    if main is not None and main.ref in lay.by_hash and lay.by_hash[main.ref].name == 'Main':
        return _replace_theme1(lay, design, x, y)
    path = scorebug_frame(lay, a)
    if not path:
        raise ValueError('This theme’s scorebug has no window a design can take the place of.')
    on = {n.off for n in path}
    hide = [k for n in path[:-1] for k in n.children if k.off not in on]
    hidden = {m.off for k in hide for m in k.walk()}
    have = textures or {}
    carriers = [c for c in CARRIERS if c in have] + _spare_textures(lay, hidden, have)
    rel = [n.off - a.body for n in path]                     # building the design moves the file: find them again
    hide_rel = [k.off - a.body for k in hide]
    asset = uibuild.install(lay, design, carriers)
    a = lay.find('Scorebar')
    w, h = design['size']
    for r in hide_rel:
        lay.recolor(lay.node_at(a, r), alpha=0)
    nodes = [lay.node_at(a, r) for r in rel]
    lay.retarget(nodes[-1], asset)
    for n in nodes[1:]:
        lay.move(n, 0, 0)
        lay.resize(n, w, h)
        lay.recolor(n, rgb=(255, 255, 255), alpha=255)       # the stock window's own tint would colour the design
        if n.kind == 0x0F:
            struct.pack_into('<Q', lay.d, n.off + 0x40, 0)   # and so would a team colour asked for it
    lay.move(nodes[0], (1920 - w) / 2 if x is None else x, 1080 - 60 - h if y is None else y)
    lay.resize(nodes[0], w, h)
    lay.carriers, lay.design_origin = carriers, (0, 0)
    return a


def card_frame(lay, a):
    """The nodes from a broadcast screen's root down to a piece a card can take the place of: the first overlay it
    shows that sits in a group the screen keeps lit. None when it has none."""
    root = a.root() if a else None
    if root is None:
        return None

    def walk(n, path, lit):
        for k in n.children:
            if k.kind == 0x1E and len(path) > 1 and k.w >= 100 and k.h >= 100 and k.ref in lay.by_hash and \
                    not (k.w >= 1900 and k.h >= 1000):
                return path + [k]
            if k.kind == 0x1C or (lit and (k.color >> 24) == 0):   # one look of several, or a layer faded out
                continue
            hit = walk(k, path + [k], lit)
            if hit:
                return hit
        return None
    # a screen that fades every layer in has no lit group: then any layer will do, and the card lights it itself
    return walk(root, [root], True) or walk(root, [root], False)


def replace_overlay(lay, name, design, textures=None):
    """Draw a design of our own in place of a broadcast screen's content: the starting lineup, the due-up card.
    The screen's backdrop and its timing stay; the content beside the piece the design takes over is hidden.
    design["x"], ["y"] place the card on the screen. textures: {name: (width, height)} of the pack, for a design
    with pictures of its own."""
    from . import uibuild
    from .uilayout import P_ALPHA
    a = lay.find(name)
    path = card_frame(lay, a)
    if not path:
        raise ValueError(f'This file has no {name} screen a card can take the place of.')
    on = {n.off for n in path}
    hide = [k for n in path[1:-1] for k in n.children if k.off not in on]
    # under the root the full-screen layers are the backdrop and stay; smaller pieces there belong to the old content
    hide += [k for k in path[0].children if k.off not in on and k.w > 0 and k.h > 0 and not (k.w >= 1900 and k.h >= 1000)]
    hidden = {m.off for k in hide for m in k.walk()}
    carriers = _spare_textures(lay, hidden, textures or {})
    rel = [n.off - a.body for n in path]
    hide_rel = [k.off - a.body for k in hide]
    asset = uibuild.install(lay, design, carriers)
    a = lay.find(name)
    w, h = design['size']
    for r in hide_rel:
        lay.recolor(lay.node_at(a, r), alpha=0)
    nodes = [lay.node_at(a, r) for r in rel]
    lay.retarget(nodes[-1], asset)
    for i, n in enumerate(nodes[1:]):
        lay.move(n, *((float(design.get('x', 0)), float(design.get('y', 0))) if i == 0 else (0, 0)))
        lay.resize(n, w, h)
        lay.recolor(n, rgb=(255, 255, 255), alpha=255)
        if n.kind == 0x0F:
            struct.pack_into('<Q', lay.d, n.off + 0x40, 0)
    lay._keys(nodes[-1], P_ALPHA, lambda v: 255)             # the piece it replaces may have been kept dark
    lay.carriers, lay.design_origin = carriers, (0, 0)
    return a


def _lineup_card():
    """The starting nine, built from nothing: the club's colour and logo across the top, then a row for each
    spot in the order with position, name, the side he bats from and his line."""
    W, head, row = 780, 112, 72
    gold, dim, ink = '#ffd24a', '#b8c2cf', '#0b0f15'
    H = head + 9 * row + 14
    p = [{'name': 'Card', 'box': [0, 0, W, H], 'color': ink, 'opacity': 94},
         {'name': 'Club colour', 'team': 'card', 'at': [0, 0, W, head]},
         {'name': 'Header shade', 'box': [0, head - 46, W, 46], 'color': '#000000', 'opacity': 30},
         {'name': 'Club logo', 'logo': 'card', 'kind': 2, 'at': [22, 12, 88, 88]},
         {'name': 'City', 'text': '^d0^', 'data': ['TEAM_UI CITY [ PRESENTATION ETEAM ]'], 'at': [128, 10, W - 150, 56],
          'size': 42, 'align': 'left'},
         {'name': 'Title', 'text': 'STARTING LINEUP', 'at': [130, 66, W - 150, 36], 'size': 24, 'align': 'left',
          'color': gold},
         {'name': 'Rule', 'box': [0, head, W, 3], 'color': gold}]
    for i in range(9):
        y = head + 8 + i * row
        rows = [{'name': 'Order', 'text': str(i + 1), 'at': [14, 14, 44, 44], 'size': 30, 'color': gold},
                {'name': 'Position', 'text': '^d0^',
                 'data': [f'PAUSE_MENU LINEUP_FROM_TEAM_POS_STR [ OFF_TEAM_HOME_AWAY ] [ {i} ]'],
                 'at': [66, 18, 70, 38], 'size': 24, 'color': dim},
                {'name': 'Name', 'text': '^d0^', 'data': [f'NAME [ FULL_NAME ] PAUSE_MENU LINEUP [ {i} ] PROFILE'],
                 'at': [146, 12, 400, 48], 'size': 32, 'align': 'left'},
                {'name': 'Bats', 'text': '^d0^',
                 'data': [f'HAND_STR [ PLAYER_UI BAT_HAND [ PAUSE_MENU LINEUP [ {i} ] ] , 0 ]'],
                 'at': [556, 18, 54, 38], 'size': 22, 'color': dim},
                {'name': 'Line', 'text': '^d0^', 'data': [f'LINEUP_STAT [ {i} ]'], 'at': [616, 14, 146, 44],
                 'size': 28, 'align': 'right', 'color': gold}]
        if i % 2 == 0:
            rows.insert(0, {'name': 'Stripe', 'box': [0, 0, W, row], 'color': '#ffffff', 'opacity': 5})
        p.append({'name': f'Batter {i + 1}', 'group': rows, 'at': [0, y, W, row]})
    return {'name': 'MTS_LineupCard', 'replaces': 'PresIntroStartingLineup', 'size': [W, H], 'x': 96, 'y': 150,
            'pieces': p}


def _break_card():
    """Between innings, built from nothing: the line score by inning with runs, hits and errors, and under it the
    three batters due up for the club the card is about."""
    W, name_w, cell, gold, dim, ink = 900, 150, 52, '#ffd24a', '#b8c2cf', '#0b0f15'
    top, row, rhe = 64, 50, name_w + 9 * cell + 22
    p = [{'name': 'Card', 'box': [0, 0, W, top + 46 + 2 * row + 18 + 42 + 3 * 52 + 12], 'color': ink, 'opacity': 94},
         {'name': 'Club colour', 'team': 'card', 'at': [0, 0, W, top]},
         {'name': 'Club logo', 'logo': 'card', 'kind': 2, 'at': [14, 6, 52, 52]},
         {'name': 'Title', 'text': 'THROUGH ^d0^', 'data': ['SCOREBAR INNING_STR [ 0 ]'], 'at': [80, 10, 420, 44],
          'size': 30, 'align': 'left'},
         {'name': 'Rule', 'box': [0, top, W, 3], 'color': gold},
         {'name': 'Table line', 'box': [rhe - 12, top + 14, 2, 36 + 2 * row], 'color': '#ffffff', 'opacity': 30}]
    for i in range(9):
        p.append({'name': f'Inning {i + 1}', 'text': '^d0^', 'data': [f'BoxScore INNING_STR [ {i} ]'],
                  'at': [name_w + i * cell, top + 12, cell, 30], 'size': 20, 'color': dim})
    for j, t in enumerate('RHE'):
        p.append({'name': t, 'text': t, 'at': [rhe + j * 56, top + 12, 56, 30], 'size': 20, 'color': dim})
    for team, side in ((0, 'AWAY'), (1, 'HOME')):
        y = top + 46 + team * row
        cells = [{'name': 'Club', 'text': '^d0^', 'data': [f'{side}_TEAM TEAM_PROF SHORT_NAME'],
                  'at': [18, 4, name_w - 24, row - 8], 'size': 30, 'align': 'left'}]
        for i in range(9):
            cells.append({'name': f'Inning {i + 1}', 'text': '^d0^', 'data': [f'BoxScore INNING_VAL [ {team} , {i} ]'],
                          'at': [name_w + i * cell, 4, cell, row - 8], 'size': 26, 'color': dim})
        for j, q in enumerate((f'BoxScore RUNS [ {team} ]', f'BoxScore HITS [ {team} ]', f'BoxScore ERRORS [ {team} ]')):
            cells.append({'name': 'RHE'[j], 'text': '^d0^', 'data': [q], 'at': [rhe + j * 56, 4, 56, row - 8],
                          'size': 28, 'color': gold if j == 0 else '#ffffff'})
        p.append({'name': f'{side.title()} line', 'group': cells, 'at': [0, y, W, row]})
    y0 = top + 46 + 2 * row + 18
    p += [{'name': 'Due up band', 'box': [0, y0, W, 34], 'color': '#ffffff', 'opacity': 8},
          {'name': 'Due up', 'text': 'DUE UP', 'at': [18, y0 + 3, 200, 28], 'size': 20, 'align': 'left', 'color': gold}]
    for i in range(3):
        y = y0 + 42 + i * 52
        p.append({'name': f'Due up {i + 1}', 'at': [0, y, W, 52], 'group': [
            {'name': 'Position', 'text': '^d0^', 'data': [f'POS_STR [ PLAYER_UI POSITION [ DUEUP PLAYER [ {i} ] ] ]'],
             'at': [18, 8, 70, 36], 'size': 24, 'color': dim, 'align': 'left'},
            {'name': 'Name', 'text': '^d0^', 'data': [f'NAME [ FULL_NAME ] DUEUP PLAYER [ {i} ] PROFILE'],
             'at': [96, 4, 520, 44], 'size': 30, 'align': 'left'},
            {'name': 'Today', 'text': '^d0^', 'data': [f'DUEUP PLAYER_AB_STAT [ {i} ]'], 'at': [W - 240, 6, 222, 40],
             'size': 26, 'align': 'right', 'color': gold}]})
    return {'name': 'MTS_BreakCard', 'replaces': 'PresFSDueUp', 'size': [W, y0 + 42 + 3 * 52 + 12], 'x': 510,
            'y': 300, 'pieces': p}


def _replace_theme1(lay, design, x=None, y=None):
    from . import uibuild
    asset = uibuild.install(lay, design, CARRIERS)
    lay.carriers, lay.design_origin = list(CARRIERS), (5, 53)
    a = lay.find('Scorebar')
    c = a.container() if a else None
    panel = lay.node_at(a, 0x4910, 0x0F) if c is not None else None
    if panel is None or not c.children or not c.children[0].children:
        raise ValueError('This scorebug is not laid out like the stock Theme 1.')
    w, h = design['size']
    keep = ()
    if design.get('bars'):
        batter, pitcher = lay.node_at(a, 0x488, 0x0F), lay.node_at(a, 0x3D40, 0x0F)
        if batter is not None and pitcher is not None:
            keep = (batter, pitcher)
            # the batter sheet is tall and used to hide behind the bug: cut it off at the design's top edge instead
            lay.resize(batter, batter.w, 12 - batter.y)
    for k in c.children[0].children[0].children:
        if k is not panel and k not in keep:
            lay.recolor(k, alpha=0)
    inst = None
    for k in panel.children:
        if k.kind == 0x1E and inst is None:
            inst = k
        else:
            lay.recolor(k, alpha=0)
    if inst is None:
        raise ValueError('The scorebug frame was not found.')
    lay.retarget(inst, asset)
    lay.move(inst, 0, 0)
    lay.resize(inst, w, h)
    lay.move(panel, 5, 12)
    lay.resize(panel, w, h)
    lay.move(c, ((1920 - w) / 2 if x is None else x) - 5, (1080 - 60 - h if y is None else y) - 53)
    lay.resize(c, w + 10, h + 60)
    return a


def _art_path(name):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'scorebug', name)


def diamond(x, y, size, on='#ffd24a', off='#ffffff', off_opacity=26):
    """The three bases as a diamond: second on top, third and first below it, each lit while a runner is on it."""
    art, step = _art_path('base.png'), size // 2 + 1
    out = []
    for name, tab, bx, by in (('Second base', '2ND', x + step, y), ('Third base', '3RD', x, y + step),
                              ('First base', '1ST', x + 2 * step, y + step)):
        out.append({'name': name, 'image': art, 'at': [bx, by, size, size], 'color': off, 'opacity': off_opacity})
        out.append({'name': name + ' (runner on)', 'image': art, 'at': [bx, by, size, size], 'color': on,
                    'when': {'data': f'SCOREBAR {tab}_BASE_TAB', 'is': '==', 'value': 1}})
    return out


def out_dots(x, y, size, gap=6, on='#ffd24a', off='#ffffff', off_opacity=26, count=2):
    """A dot for each out, lit as they are made."""
    art, out = _art_path('dot.png'), []
    for i in range(count):
        at = [x + i * (size + gap), y, size, size]
        out.append({'name': f'Out {i + 1}', 'image': art, 'at': at, 'color': off, 'opacity': off_opacity})
        out.append({'name': f'Out {i + 1} (made)', 'image': art, 'at': at, 'color': on,
                    'when': {'data': 'SCORER OUTS', 'is': '>=', 'value': i + 1}})
    return out


def half_inning(x, y, drop=38, size=14, on='#ffd24a', off='#ffffff'):
    """An arrow up above the inning number and an arrow down below it: the one for this half is lit."""
    up, down = _art_path('arrow_up.png'), _art_path('arrow_down.png')
    return [{'name': 'Top of the inning', 'image': up, 'at': [x, y, size, size], 'color': off, 'opacity': 26},
            {'name': 'Bottom of the inning', 'image': down, 'at': [x, y + drop, size, size], 'color': off,
             'opacity': 26},
            {'name': 'Top (lit)', 'image': up, 'at': [x, y, size, size], 'color': on,
             'when': {'data': 'IG IS_BOTTOM', 'is': '==', 'value': 0}},
            {'name': 'Bottom (lit)', 'image': down, 'at': [x, y + drop, size, size], 'color': on,
             'when': {'data': 'IG IS_BOTTOM', 'is': '==', 'value': 1}}]


def count(x, y, size=30, font=25, color='#ffffff'):
    """Balls and strikes as two numbers with a dash drawn between them, so the dash never touches a number."""
    w, h = round(size * 0.9), round(size * 1.2)
    return [{'name': 'Balls', 'text': '^d0^', 'data': ['IG BALLS'], 'at': [x, y, w, h], 'size': size, 'font': font,
             'align': 'right', 'color': color},
            {'name': 'Dash', 'box': [x + w + 7, y + h // 2 - 1, round(size * 0.36), max(3, size // 8)], 'color': color},
            {'name': 'Strikes', 'text': '^d0^', 'data': ['IG STRIKES'],
             'at': [x + w + 14 + round(size * 0.36), y, w, h], 'size': size, 'font': font, 'align': 'left',
             'color': color}]


def _lit(on):
    return [{'box': [0, 0, 12, 12], 'color': '#ffd24a' if on else '#3a3a3a'}]


# a plain line of text along the bottom, the way a 1970s broadcast would have done it: built from nothing
CLASSIC = {'name': 'MTS_Classic', 'size': [700, 46], 'pieces': [
    {'box': [0, 0, 700, 46], 'color': '#0c0c0c', 'opacity': 88},
    {'box': [0, 0, 700, 2], 'color': '#ffffff', 'opacity': 55},
    {'text': '^d0^', 'data': ['AWAY_TEAM TEAM_PROF SHORT_NAME'], 'at': [14, 5, 80, 36], 'size': 30, 'align': 'left'},
    {'text': '^d0^', 'data': ['SCORER AWAY_SCORE'], 'at': [96, 5, 54, 36], 'size': 30, 'align': 'right',
     'color': '#ffd24a'},
    {'box': [168, 10, 2, 26], 'color': '#ffffff', 'opacity': 35},
    {'text': '^d0^', 'data': ['HOME_TEAM TEAM_PROF SHORT_NAME'], 'at': [186, 5, 80, 36], 'size': 30, 'align': 'left'},
    {'text': '^d0^', 'data': ['SCORER HOME_SCORE'], 'at': [268, 5, 54, 36], 'size': 30, 'align': 'right',
     'color': '#ffd24a'},
    {'box': [340, 10, 2, 26], 'color': '#ffffff', 'opacity': 35},
    {'switch': 'IG IS_BOTTOM', 'at': [354, 5, 50, 36], 'looks': [
        [{'text': 'TOP', 'at': [0, 0, 50, 36], 'size': 22, 'align': 'left'}],
        [{'text': 'BOT', 'at': [0, 0, 50, 36], 'size': 22, 'align': 'left'}]]},
    {'text': '^d0^', 'data': ['SCOREBAR INNING_STR [ 0 ]'], 'at': [404, 5, 34, 36], 'size': 30, 'align': 'left',
     'color': '#ffd24a'},
    {'box': [446, 10, 2, 26], 'color': '#ffffff', 'opacity': 35},
    *diamond(458, 6, 16, off_opacity=30),
    *count(506, 5, size=30),
    {'text': '^d0^ OUT', 'data': ['SCORER OUTS'], 'at': [596, 5, 92, 36], 'size': 26, 'align': 'right'},
]}


def _line_score():
    """A ballpark line score: runs by inning for both teams, then runs, hits and errors, and the count below."""
    W, name_w, cell, top, row = 640, 96, 34, 24, 32
    rhe = name_w + 9 * cell + 14
    p = [{'box': [0, 0, W, top + 2 * row + 30], 'color': '#0d1f14', 'opacity': 92},
         {'box': [0, top, W, 2], 'color': '#e8e2c8', 'opacity': 70},
         {'box': [0, top + 2 * row, W, 2], 'color': '#e8e2c8', 'opacity': 70},
         {'box': [rhe - 8, 4, 2, top + 2 * row - 8], 'color': '#e8e2c8', 'opacity': 45}]
    for i in range(9):
        p.append({'text': str(i + 1), 'at': [name_w + i * cell, 1, cell, top - 2], 'size': 18, 'color': '#e8e2c8'})
    for j, t in enumerate('RHE'):
        p.append({'text': t, 'at': [rhe + j * 40, 1, 40, top - 2], 'size': 18, 'color': '#e8e2c8'})
    for team, side in ((0, 'AWAY'), (1, 'HOME')):
        y = top + 3 + team * row
        p.append({'text': '^d0^', 'data': [f'{side}_TEAM TEAM_PROF SHORT_NAME'], 'at': [12, y, name_w - 16, row - 4],
                  'size': 26, 'align': 'left', 'color': '#ffffff'})
        for i in range(9):
            p.append({'text': '^d0^', 'data': [f'BoxScore INNING_VAL [ {team} , {i} ]'],
                      'at': [name_w + i * cell, y, cell, row - 4], 'size': 24, 'color': '#e8e2c8'})
        for j, q in enumerate((f'SCORER {side}_SCORE', f'BoxScore HITS [ {team} ]', f'BoxScore ERRORS [ {team} ]')):
            p.append({'text': '^d0^', 'data': [q], 'at': [rhe + j * 40, y, 40, row - 4], 'size': 24,
                      'color': '#ffd24a' if j == 0 else '#e8e2c8'})
    y = top + 2 * row + 4
    p += [{'switch': 'IG IS_BOTTOM', 'at': [12, y, 46, 24], 'looks': [
              [{'text': 'TOP', 'at': [0, 0, 46, 24], 'size': 18, 'align': 'left', 'color': '#e8e2c8'}],
              [{'text': 'BOT', 'at': [0, 0, 46, 24], 'size': 18, 'align': 'left', 'color': '#e8e2c8'}]]},
          {'text': '^d0^', 'data': ['SCOREBAR INNING_STR [ 1 ]'], 'at': [58, y, 60, 24], 'size': 18, 'align': 'left',
           'color': '#e8e2c8'},
          {'text': 'BALL ^d0^   STRIKE ^d1^   OUT ^d2^', 'data': ['IG BALLS', 'IG STRIKES', 'SCORER OUTS'],
           'at': [W - 372, y, 360, 24], 'size': 18, 'align': 'right', 'color': '#ffffff'}]
    return {'name': 'MTS_LineScore', 'size': [W, top + 2 * row + 30], 'pieces': p}


def _team_tiles():
    """Three tiles: each club in its own colour with its logo, the game state on dark glass between them. The
    tiles slide in from the sides when the game starts."""
    TW, CW, H, G = 250, 230, 56, 8
    W = 2 * TW + CW + 2 * G

    def tile(side, x, mirror):
        logo = [TW - 62, -4, 64, 64] if mirror else [-2, -4, 64, 64]
        name = [TW - 152, 8, 84, 40] if mirror else [68, 8, 84, 40]
        score = [6, 6, 76, 44] if mirror else [TW - 82, 6, 76, 44]
        return {'group': [
            {'tint': side, 'at': [0, 0, TW, H], 'group': [
                {'box': [0, 0, TW, H], 'color': '#ffffff', 'opacity': 86},
                {'box': [score[0] - 6, 0, 88, H], 'color': '#9a9a9a', 'opacity': 86}]},
            {'image': 'gradient_vertical', 'at': [0, 0, TW, H], 'color': '#ffffff', 'opacity': 10},
            {'box': [0, 0, TW, 2], 'color': '#ffffff', 'opacity': 55},
            {'logo': side, 'kind': 2, 'at': logo},
            {'text': '^d0^', 'data': [f'{side.upper()}_TEAM TEAM_PROF SHORT_NAME'], 'at': name, 'size': 30,
             'font': 25},
            {'text': '^d0^', 'data': [f'SCORER {side.upper()}_SCORE'], 'at': score, 'size': 34, 'font': 37}],
            'at': [x, 0, TW, H], 'clip': True,
            'enter': {'from': [60 if mirror else -60, 0], 'frames': 20, 'delay': 0 if not mirror else 4}}
    cx = TW + G
    mid = {'name': 'Game state', 'group': [
        {'box': [0, 0, CW, H], 'color': '#0b0f16', 'opacity': 62},
        {'box': [0, 0, CW, 2], 'color': '#ffffff', 'opacity': 55},
        *half_inning(10, 3, drop=37, size=12),
        {'name': 'Inning', 'text': '^d0^', 'data': ['SCOREBAR INNING_STR [ 0 ]'], 'at': [3, 14, 26, 28], 'size': 20},
        *diamond(40, 9, 20),
        *count(96, 2, size=26),
        *out_dots(117, 40, 9, gap=5),
        {'name': 'Outs', 'text': '^d0^ OUT', 'data': ['SCORER OUTS'], 'at': [168, 10, 56, 36], 'size': 17,
         'align': 'right'}],
        'at': [cx, 0, CW, H], 'enter': {'frames': 16, 'delay': 14}}
    return {'name': 'MTS_TeamTiles', 'size': [W, H], 'bars': True,
            'pieces': [tile('away', 0, False), mid, tile('home', cx + CW + G, True)]}


def _glass_tiles():
    """Rounded tiles of glass, drawn from the manager's own pictures: each club's tile in its colour under a sheen
    and a light rim, the game state on smoked glass between them."""
    TW, CW, H, G = 280, 280, 68, 10
    W = 2 * TW + CW + 2 * G
    body, gloss = _art_path('glass_body.png'), _art_path('glass_gloss.png')

    def tile(side, x, mirror):
        logo = [TW - 82, -3, 74, 74] if mirror else [8, -3, 74, 74]
        name = [TW - 180, 12, 96, 44] if mirror else [84, 12, 96, 44]
        score = [22, 8, 84, 52] if mirror else [TW - 106, 8, 84, 52]
        return {'name': f'{side.title()} tile', 'group': [
            {'name': 'Glass in the club colour', 'tint': side, 'at': [0, 0, TW, H],
             'group': [{'image': body, 'at': [0, 0, TW, H], 'opacity': 90}]},
            {'name': 'Sheen and rim', 'image': gloss, 'at': [0, 0, TW, H]},
            {'name': 'Logo', 'logo': side, 'kind': 2, 'at': logo},
            {'name': 'Club', 'text': '^d0^', 'data': [f'{side.upper()}_TEAM TEAM_PROF SHORT_NAME'], 'at': name,
             'size': 30, 'font': 25},
            {'name': 'Score', 'text': '^d0^', 'data': [f'SCORER {side.upper()}_SCORE'], 'at': score, 'size': 38,
             'font': 37}],
            'at': [x, 0, TW, H],
            'enter': {'from': [70 if mirror else -70, 0], 'frames': 22, 'delay': 0 if not mirror else 4}}
    cx = TW + G
    mid = {'name': 'Game state', 'group': [
        {'name': 'Smoked glass', 'image': body, 'at': [0, 0, CW, H], 'color': '#0b0f16', 'opacity': 66},
        {'name': 'Sheen and rim', 'image': gloss, 'at': [0, 0, CW, H], 'opacity': 70},
        *half_inning(22, 5, drop=44, size=14),
        {'name': 'Inning', 'text': '^d0^', 'data': ['SCOREBAR INNING_STR [ 0 ]'], 'at': [14, 18, 30, 32], 'size': 22},
        *diamond(62, 14, 24),
        *count(126, 5, size=30),
        *out_dots(153, 50, 10, gap=6),
        {'name': 'Outs', 'text': '^d0^ OUT', 'data': ['SCORER OUTS'], 'at': [210, 18, 58, 32], 'size': 18,
         'align': 'right'}],
        'at': [cx, 0, CW, H], 'enter': {'frames': 16, 'delay': 16}}
    return {'name': 'MTS_GlassTiles', 'size': [W, H], 'bars': True,
            'pieces': [tile('away', 0, False), mid, tile('home', cx + CW + G, True)]}


def _base(on):
    return [{'box': [0, 0, 14, 14], 'color': '#ffd24a' if on else '#ffffff', 'opacity': 100 if on else 22}]


def _night_strip():
    """One thin dark strip along the top: logos at the ends, a line of each club's colour under its side, the game
    state in the middle, and a FULL COUNT tag that drops out from under it on 3-2."""
    W, H = 760, 44
    full = {'all': [{'data': 'IG BALLS', 'is': '==', 'value': 3}, {'data': 'IG STRIKES', 'is': '==', 'value': 2}]}
    p = [{'name': 'Strip', 'box': [0, 0, W, H], 'color': '#0a0c10', 'opacity': 86},
         {'name': 'Away colour line', 'tint': 'away', 'at': [0, H - 4, 290, 4], 'group': [{'box': [0, 0, 290, 4]}]},
         {'name': 'Home colour line', 'tint': 'home', 'at': [W - 290, H - 4, 290, 4],
          'group': [{'box': [0, 0, 290, 4]}]},
         {'name': 'Away logo', 'logo': 'away', 'kind': 2, 'at': [10, 2, 38, 38]},
         {'name': 'Away club', 'text': '^d0^', 'data': ['AWAY_TEAM TEAM_PROF SHORT_NAME'], 'at': [58, 3, 90, 36],
          'size': 26, 'align': 'left'},
         {'name': 'Away score', 'text': '^d0^', 'data': ['SCORER AWAY_SCORE'], 'at': [190, 1, 90, 40], 'size': 30,
          'font': 37, 'align': 'right'},
         {'name': 'Home score', 'text': '^d0^', 'data': ['SCORER HOME_SCORE'], 'at': [W - 280, 1, 90, 40],
          'size': 30, 'font': 37, 'align': 'left'},
         {'name': 'Home club', 'text': '^d0^', 'data': ['HOME_TEAM TEAM_PROF SHORT_NAME'],
          'at': [W - 148, 3, 90, 36], 'size': 26, 'align': 'right'},
         {'name': 'Home logo', 'logo': 'home', 'kind': 2, 'at': [W - 48, 2, 38, 38]},
         *half_inning(312, 1, drop=28, size=11),
         {'name': 'Inning', 'text': '^d0^', 'data': ['SCOREBAR INNING_STR [ 0 ]'], 'at': [305, 9, 26, 22], 'size': 17},
         *diamond(342, 5, 18),
         *count(392, 0, size=22),
         *out_dots(404, 30, 8, gap=5),
         {'name': 'Full count tag', 'at': [315, H + 4, 130, 22], 'when': full,
          'enter': {'from': [0, -14], 'frames': 12},
          'group': [{'box': [0, 0, 130, 22], 'color': '#ffd24a'},
                    {'text': 'FULL COUNT', 'at': [0, 0, 130, 22], 'size': 15, 'color': '#101010'}]}]
    return {'name': 'MTS_NightStrip', 'size': [W, H + 28], 'x': (1920 - W) // 2, 'y': 44, 'pieces': p}


def _matchup_deck():
    """Two rows: the game on top, and under it who is pitching to whom, with the pitch count, the last pitch's
    speed and the batter's line. Each club's half of the top row takes its colour."""
    W, H, R = 820, 50, 30
    dim, gold = '#c9d1dc', '#ffd24a'
    half = 270
    p = [{'name': 'Top row', 'box': [0, 0, W, H], 'color': '#0d1117', 'opacity': 92},
         {'name': 'Away colour', 'team': 'away', 'at': [0, 0, half, H], 'opacity': 88},
         {'name': 'Home colour', 'team': 'home', 'at': [W - half, 0, half, H], 'opacity': 88},
         {'name': 'Away shade', 'box': [half - 78, 0, 78, H], 'color': '#000000', 'opacity': 34},
         {'name': 'Home shade', 'box': [W - half, 0, 78, H], 'color': '#000000', 'opacity': 34},
         {'name': 'Away logo', 'logo': 'away', 'kind': 2, 'at': [8, 4, 42, 42]},
         {'name': 'Away club', 'text': '^d0^', 'data': ['AWAY_TEAM TEAM_PROF SHORT_NAME'], 'at': [58, 6, 110, 38],
          'size': 28, 'align': 'left'},
         {'name': 'Away score', 'text': '^d0^', 'data': ['SCORER AWAY_SCORE'], 'at': [half - 78, 2, 78, 46],
          'size': 34, 'font': 37},
         {'name': 'Home score', 'text': '^d0^', 'data': ['SCORER HOME_SCORE'], 'at': [W - half, 2, 78, 46],
          'size': 34, 'font': 37},
         {'name': 'Home club', 'text': '^d0^', 'data': ['HOME_TEAM TEAM_PROF SHORT_NAME'],
          'at': [W - 168, 6, 110, 38], 'size': 28, 'align': 'right'},
         {'name': 'Home logo', 'logo': 'home', 'kind': 2, 'at': [W - 50, 4, 42, 42]},
         *half_inning(half + 14, 3, drop=32, size=12, on=gold),
         {'name': 'Inning', 'text': '^d0^', 'data': ['SCOREBAR INNING_STR [ 0 ]'], 'at': [half + 6, 12, 28, 26],
          'size': 20},
         *diamond(half + 46, 7, 20, on=gold),
         *count(half + 108, 2, size=26),
         *out_dots(half + 124, 36, 9, gap=6, on=gold),
         {'name': 'Outs word', 'text': '^d0^ OUT', 'data': ['SCORER OUTS'], 'at': [half + 190, 12, 84, 26], 'size': 18,
          'color': dim},
         {'name': 'Bottom row', 'box': [0, H, W, R], 'color': '#06080b', 'opacity': 94},
         {'name': 'Rule', 'box': [0, H, W, 2], 'color': gold},
         {'name': 'P', 'text': 'P', 'at': [10, H + 4, 20, 24], 'size': 16, 'color': gold, 'align': 'left'},
         {'name': 'Pitcher', 'text': '^d0^', 'data': ['PLAYER_UI LAST_NAME [ CURRENT_PITCHER ]'],
          'at': [32, H + 4, 190, 24], 'size': 18, 'align': 'left'},
         {'name': 'Pitch count', 'text': 'P ^d0^', 'data': ['PITCH_BAT_STATS PITCH_COUNT'],
          'at': [224, H + 4, 70, 24], 'size': 16, 'color': dim, 'align': 'left'},
         {'name': 'Speed', 'text': '^d0^ MPH', 'data': ['SCOREBAR SPEED'], 'at': [W // 2 - 60, H + 4, 120, 24],
          'size': 17, 'color': gold},
         {'name': 'Batter line', 'text': '^d0^', 'data': ['CURRENT_BATTER SEASON_STATS AVG'],
          'at': [W - 312, H + 4, 70, 24], 'size': 16, 'color': dim, 'align': 'right'},
         {'name': 'Batter', 'text': '^d0^', 'data': ['NAME [ LAST_NAME ] CURRENT_BATTER PROFILE'],
          'at': [W - 238, H + 4, 190, 24], 'size': 18, 'align': 'right'},
         {'name': 'AB', 'text': 'AB', 'at': [W - 34, H + 4, 26, 24], 'size': 16, 'color': gold, 'align': 'right'}]
    return {'name': 'MTS_Matchup', 'size': [W, H + R], 'x': (1920 - W) // 2, 'y': 1080 - 66 - H - R, 'pieces': p}


LINE_SCORE = _line_score()
TEAM_TILES = _team_tiles()
GLASS_TILES = _glass_tiles()
DESIGNS = {'classic': ('Classic Line', CLASSIC), 'linescore': ('Line Score', LINE_SCORE),
           'tiles': ('Team Tiles', TEAM_TILES), 'glasstiles': ('Glass Tiles', GLASS_TILES),
           'strip': ('Night Strip', _night_strip()), 'matchup': ('Matchup Deck', _matchup_deck())}
# broadcast cards built from nothing: each takes the place of one of the game's own screens
CARDS = {'lineup': ('Lineup Card', _lineup_card()), 'break': ('Inning Break Card', _break_card())}


def place_design(lay, design, textures=None):
    """Build a design into a layout where it belongs: a card over the screen it names, anything else as the
    scorebug."""
    if design.get('replaces'):
        return replace_overlay(lay, str(design['replaces']), design, textures)
    return replace_scorebug(lay, design, design.get('x'), design.get('y'), textures)


def _design_sample(game, lib, name, description, slug, design):
    if THEME not in game.file_set():
        raise ValueError('This install has no scorebug layout (THEME1.NSW).')
    from . import recipes
    lay = uilayout.Layout.open(game.original(THEME))
    replace_scorebug(lay, design, design.get('x'), design.get('y'))
    mod = _mod(lib, name, description)
    folder = os.path.join(mod.path, 'layouts')
    os.makedirs(folder, exist_ok=True)
    import json
    with open(os.path.join(folder, slug + '.json'), 'w', encoding='utf-8') as f:
        json.dump([recipes.style_recipe(THEME, lay, game.original(THEME))], f)
    if lay.art:                                   # the design's own pictures, each into the texture that carries it
        from PIL import Image
        from . import texlib, uibuild
        pack = THEME[:-4] + '.TEX'
        with texlib.Tex(game.original(pack), readonly=True) as t:
            sizes = {e['name']: (e['w'], e['h']) for e in t.entries}
        for carrier, path in lay.art.items():
            if carrier in sizes:
                lib.add_texture(mod, pack, carrier, uibuild.fit_art(Image.open(path), *sizes[carrier]))
    return mod, 'Pick scorebug Theme 1, switch other scorebug mods off, apply, and start a game.'


def scorebug_glasstiles(game, lib, current_file):
    return _design_sample(game, lib, 'Sample: Glass Tiles', 'A scorebug built from nothing: rounded glass tiles, '
                          'each club in its own colour under a sheen, sliding in from the sides.', 'glass-tiles',
                          GLASS_TILES)


def scorebug_strip(game, lib, current_file):
    return _design_sample(game, lib, 'Sample: Night Strip', 'A scorebug built from nothing: one thin dark strip along '
                          'the top, with a FULL COUNT tag that drops out on 3-2.', 'night-strip',
                          DESIGNS['strip'][1])


def scorebug_classic(game, lib, current_file):
    return _design_sample(game, lib, 'Sample: Classic Line', 'A scorebug built from nothing: one line of text along '
                          'the bottom, the way an old broadcast did it.', 'classic-line', CLASSIC)


def scorebug_tiles(game, lib, current_file):
    return _design_sample(game, lib, 'Sample: Team Tiles', 'A scorebug built from nothing: each club on a tile of '
                          'its own colour with its logo, the game state between them. The tiles slide in.',
                          'team-tiles', TEAM_TILES)


def scorebug_linescore(game, lib, current_file):
    return _design_sample(game, lib, 'Sample: Line Score', 'A scorebug built from nothing: a ballpark line score '
                          'with runs by inning, hits and errors.', 'line-score', LINE_SCORE)


def _style_sample(game, lib, name, description, slug, split, glass=False):
    if THEME not in game.file_set():
        raise ValueError('This install has no scorebug layout (THEME1.NSW).')
    from . import recipes
    lay = uilayout.Layout.open(game.original(THEME))
    if glass:
        glass_bar(lay, recipes._texture_table(game, THEME))
    else:
        wide_top_bar(lay, split=split)
    mod = _mod(lib, name, description)
    folder = os.path.join(mod.path, 'layouts')
    os.makedirs(folder, exist_ok=True)
    import json
    with open(os.path.join(folder, slug + '.json'), 'w', encoding='utf-8') as f:
        json.dump([recipes.style_recipe(THEME, lay, game.original(THEME))], f)
    return mod, 'Pick scorebug Theme 1, switch other scorebug mods off, apply, and start a game.'


def scorebug_wide(game, lib, current_file):
    return _style_sample(game, lib, 'Sample: Wide Top Bar', 'Theme 1 as one wide strip across the top of the '
                         'screen: both teams, inning, bases, count and outs in a line.', 'wide-top-bar', False)


def scorebug_split(game, lib, current_file):
    return _style_sample(game, lib, 'Sample: Split Bar', 'A wide strip with the teams at either end and the '
                         'inning, bases, count and outs between them. The home side is mirrored.', 'split-bar', True)


def scorebug_glass(game, lib, current_file):
    return _style_sample(game, lib, 'Sample: Glass Bar', 'Three floating tiles of smoked glass across the top: each '
                         'team tinted its own colour, the game state between them.', 'glass-bar', True, glass=True)


def scorebug_text_test(game, lib, current_file):
    if THEME not in game.file_set():
        raise ValueError('This install has no scorebug layout (THEME1.NSW).')
    mod = _mod(lib, 'Test: Scorebug Text', 'A check for the text settings: every scorebug text half again as big, '
               'in red, in the wide font. Switch it off when you are done.')
    folder = os.path.join(mod.path, 'layouts')
    os.makedirs(folder, exist_ok=True)
    import json
    with open(os.path.join(folder, 'scorebug-text.json'), 'w', encoding='utf-8') as f:
        json.dump([{'file': THEME, 'asset': 'Scorebar', 'text': {'size': 'x1.5', 'font': 2, 'color': '#ff2020'}}],
                  f, indent=2)
    return mod, 'Pick scorebug Theme 1, apply, start a game and send a screenshot of the scorebug.'


def scorebug_flat(game, lib, current_file):
    return _scorebug_style(game, lib, 'Sample: Flat White Scorebug', 'Theme 1 flat and white: no gradients or '
                           'chevrons, black lines and scores.', FLAT_WHITE)


BALLS = 'NSW/OBJECTS/BALLTEXTURES.TEX'


def fireball_skin(img, seed=7):
    """A ball's texture set alight: the leather glows from deep red through orange to yellow-white in licks of
    flame, and the seams stay as dark embers, so the stitching still reads as the ball spins. Painted over the
    game's own texture, which keeps every seam where the model expects it."""
    import numpy as np
    from PIL import Image
    src = np.asarray(img.convert('RGBA'), np.float32) / 255
    h, w = src.shape[:2]
    lum = src[..., :3] @ np.array([0.299, 0.587, 0.114], np.float32)
    rng = np.random.default_rng(seed)
    flame = np.zeros((h, w), np.float32)
    for cells, weight in ((4, 0.5), (8, 0.3), (16, 0.2)):          # a few sizes of soft noise make the licks
        grid = rng.random((cells + 1, cells + 1)).astype(np.float32)
        big = Image.fromarray((grid * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
        flame += weight * np.asarray(big, np.float32) / 255
    sat = src[..., :3].max(-1) - src[..., :3].min(-1)
    leather = np.clip((lum - 0.45) / 0.4, 0, 1) * np.clip(1 - sat * 3, 0, 1)      # pale and plain: not a seam
    heat = np.clip(0.25 + 0.75 * flame, 0, 1) * leather
    stops = np.array([[0.20, 0.02, 0.00], [0.75, 0.10, 0.00], [1.00, 0.45, 0.02], [1.00, 0.80, 0.20],
                      [1.00, 0.97, 0.75]], np.float32)
    pos = heat * (len(stops) - 1)
    i = np.clip(pos.astype(int), 0, len(stops) - 2)
    t = (pos - i)[..., None]
    out = stops[i] * (1 - t) + stops[i + 1] * t
    out = np.dstack([out, src[..., 3]])
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8), 'RGBA')


def fireball(game, lib, current_file):
    """The ball as a ball of fire, in every league's version of it. Goes with the Fireball code mod."""
    from . import texlib
    if BALLS not in game.file_set():
        raise ValueError('This install has no ball textures (BALLTEXTURES.TEX).')
    mod = _mod(lib, 'Sample: Fireball', 'The ball burns: glowing leather, ember seams.')
    with texlib.Tex(game.original(BALLS), readonly=True) as t:
        for e in t.entries:
            if e['name'].endswith('-color'):
                lib.add_texture(mod, BALLS, e['name'], fireball_skin(t.image(e)))
    return mod, 'Apply and start a game.'


SAMPLES = [
    ('yankees', 'Sample: 1927 Yankees', 'A classic roster brought in from a roster file: 25 players, built faces for '
     'the ones the game doesn’t have, lineups set for you.', yankees_1927),
    ('moonshot', 'Sample: Moonshot League', 'A ratings mod: every MLB hitter gets 125 power.', moonshot_league),
    ('scorebug', 'Sample: Scorebug Bottom Left', 'A layout mod: the scorebug moves to the bottom left corner.',
     scorebug_corner),
    ('midnight', 'Sample: Midnight Scorebug', 'A scorebug style: navy, gold lines, white scores.', scorebug_midnight),
    ('brick', 'Sample: Brick & Sand Scorebug', 'A scorebug style: brick red with sand trim.', scorebug_brick),
    ('wide', 'Sample: Wide Top Bar', 'A scorebug layout: one wide strip across the top of the screen.',
     scorebug_wide),
    ('split', 'Sample: Split Bar', 'A scorebug layout: teams at either end, the game state in the middle.',
     scorebug_split),
    ('classic', 'Sample: Classic Line', 'A scorebug built from nothing: one line of text along the bottom.',
     scorebug_classic),
    ('linescore', 'Sample: Line Score', 'A scorebug built from nothing: runs by inning, hits and errors.',
     scorebug_linescore),
    ('glasstiles', 'Sample: Glass Tiles', 'A scorebug built from nothing: rounded glass tiles in team colours.',
     scorebug_glasstiles),
    ('strip', 'Sample: Night Strip', 'A scorebug built from nothing: a thin strip along the top.', scorebug_strip),
    ('tiles', 'Sample: Team Tiles', 'A scorebug built from nothing: team-colour tiles with logos that slide in.',
     scorebug_tiles),
    ('glass', 'Sample: Glass Bar', 'A scorebug style: three floating tiles of smoked glass.', scorebug_glass),
    ('texttest', 'Test: Scorebug Text', 'A check: scorebug text bigger, red and in another font.',
     scorebug_text_test),
    ('flat', 'Sample: Flat White Scorebug', 'A scorebug style: flat white, no gradients, black scores.',
     scorebug_flat),
    ('fireball', 'Sample: Fireball', 'A texture mod: the ball burns.', fireball),
]


def card_in_palette(card, palette):
    """A copy of a built-in card in a scorebug's colours: its dark behind everything, its light for the words, its
    first accent where the card's gold was."""
    import copy
    from . import boards, uibuild
    dark, light, accents = boards.roles(palette)
    out = copy.deepcopy(card)
    for old, new in (('#0b0f15', dark), ('#ffd24a', accents[0] if accents else light),
                     ('#b8c2cf', boards._mix(dark, light, 0.72)), ('#ffffff', light)):
        uibuild.recolour(out, old, new)
    return out


def pres_of(theme_rel):
    """The broadcast screens that go with a scorebug theme: THEME2.NSW has PRES/PRESOSDS2.NSW."""
    stem = theme_rel.upper().rsplit('/', 1)[-1]
    n = stem[5:-4] if stem.startswith('THEME') and stem.endswith('.NSW') else ''
    return f'NSW/UI/GAME/PRES/PRESOSDS{n}.NSW' if n.isdigit() else None
