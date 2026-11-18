"""The developers' own switches, which the game still looks for when it starts.

The game reads BOOT/CONFIG_MAIN.TXT at start-up, or BOOT/CONFIG_MAIN_USER.TXT in its place when that file is there.
Each line is a switch name ('#' starts a comment). The file the game ships has every switch commented out; the code
still asks for a good number of them. The manager writes the USER file with the switches picked here and takes it
away again when none is on, so the game's own file is never touched.
"""
import os

SHIPPED = 'BOOT/CONFIG_MAIN.TXT'
USER = 'BOOT/CONFIG_MAIN_USER.TXT'
MARK = '# Written by Mod the Show Manager (Code Mods, Developer).'

# (name in the file, name shown, what it does as far as the name and the code around it say)
SWITCHES = [
    ('FastPlay', 'Fast Play', 'Less waiting between pitches.'),
    ('AIvAI', 'CPU vs CPU', 'The CPU plays both sides.'),
    ('NoWarmup', 'No Warmup', 'Skips the warm-up before play.'),
    ('NoIdle', 'No Idle', 'Players stop their idle fidgeting.'),
    ('NoTips', 'No Tips', 'No hints on screen.'),
    ('CatcherView', 'Catcher View', 'Starts from the catcher’s side.'),
    ('NoCrowd', 'No Crowd', 'An empty ballpark.'),
    ('NoDOF', 'No Depth of Field', 'Nothing in the picture is blurred.'),
    ('DisableUIElem', 'No Board Graphics', 'The stadium boards show no game graphics.'),
    ('DisableJumboBink', 'No Board Videos', 'The big board plays no videos.'),
    ('FastLoad', 'Fast Load', 'A shorter start-up.'),
    ('UnlockedEquipment', 'Unlocked Equipment', 'The developers’ own equipment unlock.'),
    ('Tutorial', 'Tutorial', 'Asks for the tutorial.'),
    ('Pregame', 'Pregame', 'Changes how a game is led in.'),
    ('TestStorylines', 'Test Storylines', 'A test setting for Storylines.'),
    ('No_Trophy', 'No Trophies', 'No trophy pop-ups.'),
    ('OpenBetaDemo', 'Open Beta Demo', 'Runs as the beta demo did. May hide most of the game.'),
    ('Mobile', 'Mobile', 'Runs as the phone version does. Expect surprises.'),
    ('GameOnly', 'Game Only', 'Straight into a match from a data file. May not start.'),
    ('HRDerbyOnly', 'Home Run Derby Only', 'Straight into a derby. May not start.'),
    ('TrainOnly', 'Training Only', 'Straight into training. May not start.'),
]
NAMES = [s[0] for s in SWITCHES]


def _lines(path):
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            return [ln.strip() for ln in f.read().splitlines()]
    except OSError:
        return []


def read(game):
    """The switches that are on: the set of names in the USER file."""
    have = {ln.split('=')[0].strip().lower() for ln in _lines(game.path(USER)) if ln and not ln.startswith('#')}
    return {n for n in NAMES if n.lower() in have}


def write(game, on):
    """Makes the USER file say exactly these switches (and whatever else was in it), or removes it when it would say
    nothing of ours. Returns True when the file is there afterwards."""
    path = game.path(USER)
    ours = {n.lower() for n in NAMES}
    there = os.path.exists(path)
    old = _lines(path) if there else []
    made_here = not there or MARK in old           # a file someone made by hand keeps their lines and stays theirs
    keep = [ln for ln in (old if there else _lines(game.path(SHIPPED)))
            if ln and not ln.startswith('#') and ln.split('=')[0].strip().lower() not in ours]
    picked = [n for n in NAMES if n in on]
    if not picked and made_here:
        if there:
            os.remove(path)
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\r\n') as f:
        f.write('\n'.join(([MARK] if made_here else []) + picked + keep) + '\n')
    return True
