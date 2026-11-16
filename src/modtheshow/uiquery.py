"""The little query language layouts use to read the game.

A States node picks its look, an instance passes arguments, and a live text fills its ^dN^ slots, all with the same
thing: a token list. Tokens are name hashes (uilayout.name_hash) or small numbers (31-bit, so 0x7FFFFFFF is -1),
stored last word first. Read backwards they are bracketed queries:

    [ SCOREBAR OUT_TAB ]                         how many outs
    [ IG STRIKES ]                               the count
    [ TEAM_UI SHORT_NAME [ OFF_TEAM_ID ] ]       the batting team's abbreviation
    [ UI TEMPLATE_QUERY_INX [ 2 ] ]              the third argument this copy of the overlay was given
    [ IF_Q_ELSE_INT [ QCOMP [ a , == , 6 ] , x , y ] ]

The words are the game's own (they are in its debug text); querynames.txt lists the ones layouts use. A Situation
is a pretend moment of a game that answers the queries, so an overlay can be drawn the way it looks in play.
"""
import os

from .uilayout import name_hash

_HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = {}


def _load():
    if NAMES:
        return
    try:
        with open(os.path.join(_HERE, 'assets', 'querynames.txt'), encoding='utf-8') as f:
            for w in f.read().split('\n'):
                if w:
                    NAMES[name_hash(w)] = w
    except OSError:
        pass


def word(tok):
    _load()
    if tok < 0x80000000:
        return tok - 0x80000000 if tok >= 0x40000000 else tok
    return NAMES.get(tok, f'#{tok:08x}')


def tokens(text):
    """The token list for a query written out, e.g. '[ SCOREBAR OUT_TAB ]'."""
    out = []
    for w in text.split():
        if w.lstrip('-').isdigit():
            out.append(int(w) & 0x7FFFFFFF)
        elif w.startswith('#'):
            out.append(int(w[1:], 16))
        else:
            out.append(name_hash(w))
    return out[::-1]


def text(toks):
    return ' '.join(str(word(t)) for t in reversed(toks))


def parse(toks):
    """Token list -> expression: a list of items, each a word, a number, or a list of comma-separated expressions."""
    items = [word(t) for t in reversed(toks)]
    pos = 0

    def expr(stop):
        nonlocal pos
        out = []
        while pos < len(items) and items[pos] not in stop:
            it = items[pos]
            pos += 1
            if it == '[':
                args = [expr((',', ']'))]
                while pos < len(items) and items[pos] == ',':
                    pos += 1
                    args.append(expr((',', ']')))
                pos += 1                                  # the closing bracket
                out.append(args)
            else:
                out.append(it)
        return out
    e = expr(())
    while len(e) == 1 and isinstance(e[0], list) and len(e[0]) == 1:      # the outer [ ]
        e = e[0][0]
    return e


OPS = {'==': lambda a, b: a == b, '!=': lambda a, b: a != b, '<': lambda a, b: a < b, '<=': lambda a, b: a <= b,
       '>': lambda a, b: a > b, '>=': lambda a, b: a >= b, '+': lambda a, b: a + b, '-': lambda a, b: a - b,
       '*': lambda a, b: a * b}


def _num(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


class Situation:
    """A pretend moment of a game. Friendly fields in, answers to the game's queries out."""

    def __init__(self, **kw):
        self.away, self.home = 'TOR', 'AZ'
        self.away_score, self.home_score = 0, 0
        self.inning, self.bottom = 1, False
        self.balls, self.strikes, self.outs = 0, 0, 0
        self.first = self.second = self.third = False
        self.batter, self.batter_first, self.batter_avg, self.batter_spot = 'SPRINGER', 'GEORGE', '.309', 1
        self.pitcher, self.pitcher_first, self.pitch_count = 'GALLEN', 'ZAC', 0
        self.speed, self.pitch = 0, 'FB'
        self.away_color, self.home_color = (19, 74, 142), (20, 20, 20)       # the wash behind each team's row
        self.away_logo = self.home_logo = None                              # PIL images, when you have them
        self.extra = {}                    # query text -> value, for anything else
        for k, v in kw.items():
            setattr(self, k, v)

    # team ids: 0 away, 1 home
    def _teams(self):
        off = 1 if self.bottom else 0
        return {'AWAY_TEAM_ID': 0, 'HOME_TEAM_ID': 1, 'OFF_TEAM_ID': off, 'DEF_TEAM_ID': 1 - off}

    def team_color(self, team):
        return self.home_color if _num(team) == 1 else self.away_color

    def team_logo(self, team):
        return self.home_logo if _num(team) == 1 else self.away_logo

    def answer(self, path, args):
        """The value of a query: path is its words, args the values in its brackets. None when not known."""
        key = ' '.join(path)
        if key in self.extra:
            return self.extra[key]
        teams = self._teams()
        if key in teams:
            return teams[key]
        ordinal = lambda n: f'{n}{"th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")}'
        a0 = args[0] if args else None
        simple = {
            'SCOREBAR OUT_TAB': self.outs, 'IG OUTS': self.outs, 'IG BALLS': self.balls, 'IG STRIKES': self.strikes,
            'SCOREBAR 1ST_BASE_TAB': int(self.first), 'SCOREBAR 2ND_BASE_TAB': int(self.second),
            'SCOREBAR 3RD_BASE_TAB': int(self.third), 'IG IS_BOTTOM': int(self.bottom), 'IG INNING': self.inning,
            'SCOREBAR SPEED': self.speed, 'SCOREBAR SPEED_TAB': int(bool(self.speed)),
            'SCOREBAR CALLOUT_TYPE': self.pitch, 'PITCH_BAT_STATS PITCH_COUNT': self.pitch_count,
            'SCOREBAR BATTER_LINEUP_INDEX': self.batter_spot, 'SCOREBAR BATTER_STATS': self.batter_avg,
            'SCOREBAR BATTER_BAR_INFO': self.batter_avg, 'IS_COLLEGE_GAME': 0, 'POSTSEASON_TAB': 0,
            'PLAYER_UI LAST_NAME': self.pitcher if a0 == 'CURRENT_PITCHER' else self.batter,
            'PLAYER_UI FIRST_NAME': self.pitcher_first if a0 == 'CURRENT_PITCHER' else self.batter_first,
            'PLAYER_UI FULL_NAME': (f'{self.pitcher_first} {self.pitcher}' if a0 == 'CURRENT_PITCHER'
                                    else f'{self.batter_first} {self.batter}'),
            'CURRENT_PITCHER': 'CURRENT_PITCHER', 'CURRENT_BATTER': 'CURRENT_BATTER', 'ON_DECK': 'ON_DECK',
            'WIN_EXPECTANCY': 50, 'IS_VALID_TEAM': 1, 'IS_MLB_TEAM_TAB': 1,
            'SCORER AWAY_SCORE': self.away_score, 'SCORER HOME_SCORE': self.home_score,
            'AWAY_TEAM TEAM_PROF SHORT_NAME': self.away, 'HOME_TEAM TEAM_PROF SHORT_NAME': self.home,
            'OFF_TEAM TEAM_PROF TEAM_NAME': self.home if self.bottom else self.away,
            'SCOREBAR PREVIOUS_SCORE': self.home_score if _num(a0) == 1 else self.away_score,
            'USE_SECONDARY_COLOR': 0, 'MODIFIABLE_LOGO': 0, 'SCOREBAR IS_RAID': 0, 'SCOREBAR END_OF_INNING_STRING': '',
            'UI LOGO': _num(a0), 'SCOREBAR EXIT_VELO_TAB': 0, 'SCOREBAR HOMERUN_ANIM_TAB': 0,
            'SCOREBAR HOMERUN_TAB': 0, 'SCOREBAR STRIKEOUT_TAB': 0, 'SCOREBAR WIN_EXP_TAB': 0,
            'SCOREBAR HAS_NOTABLE': 0, 'SCOREBAR HITTER_TYPE': 0, 'SCOREBAR SLIDEUP_TAB': 0,
            'SCORER PITCH_CLOCK': 15, 'HAS_3D_LOGO': 0,
            'SCORER OUTS': self.outs, 'SCORER BALLS': self.balls, 'SCORER STRIKES': self.strikes,
            'SCORER INNING': self.inning, 'AWAY_TEAM_ID': 0, 'HOME_TEAM_ID': 1,
            'CURRENT_BATTER SEASON_STATS AVG': self.batter_avg,
        }
        if key in simple:
            return simple[key]
        if key in ('TEAM_UI SHORT_NAME', 'TEAM_UI TEAM', 'TEAM_UI ABBREV_NAME'):
            return self.home if _num(a0) == 1 else self.away
        if key in ('TEAM_UI SCORE', 'SCOREBAR SCORE', 'IG SCORE', 'SCOREBAR RUNS', 'IG RUNS'):
            return self.home_score if _num(a0) == 1 else self.away_score
        if key in ('AWAY_TEAM TEAM_PROF TEAM_INX', 'HOME_TEAM TEAM_PROF TEAM_INX'):
            from . import teamart
            return teamart.index(self.away if key.startswith('AWAY') else self.home)
        if key == 'UI CAP_TEAM_CLR':                           # a team's colour (its second colour with a 1 after it)
            r, g, b = self.team_color(a0)
            if len(args) > 1 and _num(args[1]):
                r, g, b = (int(v * 0.55) for v in (r, g, b))
            return f'#{r:02x}{g:02x}{b:02x}'
        if key == 'BoxScore INNING_VAL':                       # a made-up line: the runs fall in the latest inning
            team, inn = _num(a0), _num(args[1]) if len(args) > 1 else 0
            played = self.inning - (0 if team == 0 or self.bottom else 1)
            if inn >= played:
                return ''
            return (self.home_score if team else self.away_score) if inn == played - 1 else 0
        if key in ('BoxScore HITS', 'BoxScore ERRORS'):
            return (self.home_score if _num(a0) else self.away_score) + 2 if key.endswith('HITS') else 0
        if key == 'BoxScore INNING_STR':
            return str(_num(a0) + 1)
        if key == 'SCOREBAR INNING_STR':
            return str(self.inning) if not _num(a0) else ordinal(self.inning)
        if key == 'SCOREBAR BATTER_BAR_NAME':
            return self.batter if not _num(a0) else self.batter_first
        if key.startswith('NAME ') or key == 'NAME':
            who = 'pitcher' if 'CURRENT_PITCHER' in path else 'batter'
            first = a0 == 'FIRST_NAME'
            full = a0 == 'FULL_NAME'
            if full:
                return f'{getattr(self, who + "_first")} {getattr(self, who)}'
            return getattr(self, who + ('_first' if first else ''))
        return None


class Context:
    """Evaluates expressions for one copy of an overlay: a Situation plus the arguments the copy was given."""

    def __init__(self, sit, args=(), parent=None):
        self.sit, self.args, self.parent = sit, list(args), parent
        self.unknown = set()

    def child(self, arg_token_lists):
        c = Context(self.sit, [self.value(parse(t)) if t else None for t in arg_token_lists], self)
        c.unknown = self.unknown
        return c

    def value(self, e):
        if not isinstance(e, list):
            return e
        path = [x for x in e if not isinstance(x, list)]
        groups = [x for x in e if isinstance(x, list)]
        if len(e) == 1 and not groups:
            v = e[0]
            if isinstance(v, int) or v in OPS:
                return v
        args = [self.value(a) for g in groups for a in g]
        key = ' '.join(str(p) for p in path)
        if key in ('UI TEMPLATE_QUERY_INX', 'UI TEMPLATE_QUERY'):
            i = _num(args[0]) if key.endswith('INX') and args else 0
            return self.args[i] if 0 <= i < len(self.args) else None
        if key == 'IF_Q_ELSE_INT' and len(args) >= 3:
            return args[1] if args[0] else args[2]
        if key in ('QCOMP', 'UI MATH', 'MATH') and len(args) >= 3 and args[1] in OPS:
            return OPS[args[1]](_num(args[0]), _num(args[2]))
        v = self.sit.answer([str(p) for p in path], args)
        if v is None and path:
            self.unknown.add(key)
        return v

    def number(self, toks):
        return _num(self.value(parse(toks))) if toks else 0
