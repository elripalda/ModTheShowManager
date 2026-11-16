"""Rosters as JSON: export a team to a file you can read and edit, import one back.

The file is plain enough to write by hand or have an AI write (a 1998 roster, a fantasy league, your softball team):

    {
      "format": "modtheshow-roster",
      "teams": [
        {
          "team": "New York Yankees",
          "rename": {"city": "Gotham", "name": "Knights", "short": "GTH"},
          "replace": true,
          "players": [
            {"first": "Babe", "last": "Ruth", "pos": "RF", "number": 3, "bats": "L", "throws": "L",
             "height": "6'2\\"", "overall": 99, "ratings": {"power_vs_r": 125, "contact_vs_r": 110},
             "gear": {"bat": 12}, "like": "Aaron Judge"}
          ]
        }
      ]
    }

How a player in the file is matched: "id" (the game's player id) if given, otherwise the exact name. A name the game
does not have takes over a spare player with a built (not scanned) face, so new players never wear a real player's
head. "like" copies another player's whole look. "replace" sends everyone on the team who is not in the file to free
agency first. Anything left out of a player keeps its value.
"""
import json
import re

from . import rosters as R

FORMAT = 'modtheshow-roster'
BATS = ('R', 'L', 'S')
ALL_POS = R.POSITIONS + ('DH',)


def _key(label):
    return re.sub(r'[^a-z0-9]+', '_', label.lower()).strip('_')


RATING_KEYS = {_key(label): field for field, label, _, _ in R.RATINGS}
RATING_KEYS.update({field.lower(): field for field, _, _, _ in R.RATINGS})
RATING_NAME = {field: _key(label) for field, label, _, _ in R.RATINGS}
GEAR_KEYS = {_key(label): field for field, _, label in R.SLOTS}
GEAR_KEYS.update({field.lower(): field for field, _, _ in R.SLOTS})
GEAR_NAME = {field: _key(label) for field, _, label in R.SLOTS}


def _height_text(inches):
    return f'{inches // 12}\'{inches % 12}"'


def _height(v):
    """Inches from 74, "74", "6'2", "6-2" or "6 ft 2"."""
    if isinstance(v, (int, float)):
        return int(v)
    m = re.findall(r'\d+', str(v))
    if not m:
        raise ValueError(f'height {v!r}')
    if len(m) == 1:
        n = int(m[0])
        return n if n > 11 else n * 12
    return int(m[0]) * 12 + int(m[1])


def player_dict(p):
    d = {'id': p.id, 'first': p.first, 'last': p.last,
         'pos': R.POSITIONS[p.pos] if p.pos < len(R.POSITIONS) else p.pos,
         'number': p.bits('jersey'), 'bats': BATS[min(p.bits('bats'), 2)], 'throws': 'L' if p.bits('throws') else 'R',
         'height': _height_text(p.bits('height'))}
    if p.att is not None:
        use = 3 if p.pitcher else 2
        d['overall'] = p.rating('RANK')
        d['ratings'] = {RATING_NAME[f]: p.rating(f) for f, _, *who in R.RATINGS
                        if f != 'RANK' and f in p.att.fields and who[use - 2]}
    if p.acc is not None:
        gear = {GEAR_NAME[f]: p.gear(f) for f, _, _ in R.SLOTS if f in p.acc.fields and p.gear(f)}
        if gear:
            d['gear'] = gear
    d['face'] = 'built' if p.generic_face else 'scanned'
    return d


def export(db, team_indexes):
    teams = []
    for i in team_indexes:
        t = db.teams[i]
        ros = db.roster_of(i)
        order = {n - 1: k for k, n in enumerate(ros.slots) if n}
        players = sorted(db.roster(i), key=lambda p: order.get(p.i, 999))
        teams.append({'team': t.full, 'short': t.short, 'players': [player_dict(p) for p in players]})
    return {'format': FORMAT, 'version': 1, 'teams': teams}


def dump(doc):
    """Readable JSON: one player per line."""
    out = ['{', f'  "format": {json.dumps(doc["format"])},', f'  "version": {doc.get("version", 1)},', '  "teams": [']
    for ti, t in enumerate(doc['teams']):
        out.append('    {')
        for k, v in t.items():
            if k != 'players':
                out.append(f'      {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)},')
        out.append('      "players": [')
        rows = [json.dumps(p, ensure_ascii=False) for p in t['players']]
        out += [f'        {r}{"," if i < len(rows) - 1 else ""}' for i, r in enumerate(rows)]
        out.append('      ]')
        out.append('    }' + (',' if ti < len(doc['teams']) - 1 else ''))
    out += ['  ]', '}']
    return '\n'.join(out) + '\n'


class Report:
    def __init__(self):
        self.updated, self.created, self.released, self.problems = 0, 0, 0, []

    def text(self):
        parts = [f'{self.updated} player(s) updated', f'{self.created} new']
        if self.released:
            parts.append(f'{self.released} sent to free agency')
        return ', '.join(parts) + '.'


def find_team(db, name):
    want = str(name).strip().lower()
    for t in db.teams:
        if want in (t.full.lower(), t.name.lower(), t.short.lower()):
            return t
    if want.isdigit() and int(want) < len(db.teams):
        return db.teams[int(want)]
    return None


def _pos(v):
    if isinstance(v, int):
        return v
    s = str(v).strip().upper()
    s = {'SP': 'P', 'RP': 'P', 'CP': 'P', 'OF': 'CF', 'IF': 'SS', 'DH': '1B'}.get(s, s)
    if s not in R.POSITIONS:
        raise ValueError(f'position {v!r}')
    return R.POSITIONS.index(s)


def _donors(db, taken):
    """Spare players with built faces, best candidates first: free agents, then the lowest minor league teams."""
    def rank(p):
        return (0 if p.team == R.FREE_AGENT else 1, -p.team if p.team != R.FREE_AGENT else 0, p.rating('RANK'))
    pool = [p for p in db.players if p.generic_face and p.i not in taken and (p.team == R.FREE_AGENT or p.team >= 65)]
    return sorted(pool, key=rank)


def apply(db, doc):
    """Applies a roster document to an open Database (nothing is written to disk here). Returns a Report."""
    if not isinstance(doc, dict) or not isinstance(doc.get('teams'), list):
        raise ValueError('Not a roster file: it needs a "teams" list.')
    rep = Report()
    by_name, by_id = {}, {}
    for p in db.players:
        by_name.setdefault((p.first.lower(), p.last.lower()), p)
        by_id.setdefault(p.id, p)
    taken = set()
    # everyone named in the file is spoken for before any spare is handed out
    for t in doc['teams']:
        for d in t.get('players', []):
            p = by_id.get(d.get('id')) if d.get('id') is not None else None
            p = p or by_name.get((str(d.get('first', '')).lower(), str(d.get('last', '')).lower()))
            if p:
                taken.add(p.i)
    donors = None
    for t in doc['teams']:
        team = find_team(db, t.get('team', ''))
        if team is None:
            rep.problems.append(f'No team called {t.get("team")!r}.')
            continue
        rn = t.get('rename') or {}
        if rn:
            db.set_team(team, city=rn.get('city'), name=rn.get('name'), short=rn.get('short'))
        rows = []
        for d in t.get('players', []):
            p = by_id.get(d.get('id')) if d.get('id') is not None else None
            p = p or by_name.get((str(d.get('first', '')).lower(), str(d.get('last', '')).lower()))
            rows.append((d, p))
        if t.get('replace'):
            keep = {p.i for _, p in rows if p}
            for p in db.roster(team.index):
                if p.i not in keep:
                    db.set_player(p, team=R.FREE_AGENT)
                    rep.released += 1
        for d, p in rows:
            label = f'{d.get("first", "")} {d.get("last", "")}'.strip() or '(no name)'
            try:
                pos = _pos(d['pos']) if 'pos' in d else None
                new = p is None
                if new:
                    if not d.get('last'):
                        raise ValueError('needs a last name')
                    if donors is None:
                        donors = _donors(db, taken)
                    want_p = pos == 0 if pos is not None else False
                    k = next((i for i, c in enumerate(donors) if c.pitcher == want_p and c.i not in taken), None)
                    if k is None:
                        k = next((i for i, c in enumerate(donors) if c.i not in taken), None)
                    if k is None:
                        raise ValueError('no spare player left to turn into them')
                    p = donors.pop(k)
                    taken.add(p.i)
                kw = {}
                if 'first' in d and d['first'] != p.first:
                    kw['first'] = str(d['first'])[:15]
                if 'last' in d and d['last'] != p.last:
                    kw['last'] = str(d['last'])[:15]
                if pos is not None and pos != p.pos:
                    kw['pos'] = pos
                bits = {}
                if 'number' in d:
                    bits['jersey'] = bits['jersey2'] = max(0, min(99, int(d['number'])))
                if 'bats' in d:
                    bits['bats'] = BATS.index(str(d['bats']).strip().upper()[:1])
                if 'throws' in d:
                    bits['throws'] = 1 if str(d['throws']).strip().upper().startswith('L') else 0
                if 'height' in d:
                    bits['height'] = max(60, min(90, _height(d['height'])))
                bits = {k: v for k, v in bits.items() if p.bits(k) != v}
                if bits:
                    kw['bits'] = bits
                ratings = {}
                if 'overall' in d:
                    ratings['RANK'] = int(d['overall'])
                for k, v in (d.get('ratings') or {}).items():
                    f = RATING_KEYS.get(_key(str(k)))
                    if f is None:
                        rep.problems.append(f'{label}: no rating called {k!r}.')
                    elif p.att is not None and f in p.att.fields:
                        ratings[f] = max(0, min(125, int(v)))
                ratings = {f: v for f, v in ratings.items() if p.rating(f) != v}
                if ratings:
                    kw['ratings'] = ratings
                gear = {}
                for k, v in (d.get('gear') or {}).items():
                    f = GEAR_KEYS.get(_key(str(k)))
                    if f is None:
                        rep.problems.append(f'{label}: no gear slot called {k!r}.')
                    else:
                        gear[f] = int(v)
                gear = {f: v for f, v in gear.items() if p.gear(f) != v}
                if gear:
                    kw['gear'] = gear
                if d.get('like'):
                    parts = str(d['like']).strip().lower().rsplit(' ', 1)
                    src = by_name.get((parts[0], parts[1])) if len(parts) == 2 else None
                    src = src or next((q for q in db.players if q.name.lower() == str(d['like']).strip().lower()), None)
                    if src is None:
                        rep.problems.append(f'{label}: no player called {d["like"]!r} to look like.')
                    else:
                        kw['look'] = src
                moved = p.team != team.index
                if kw:
                    db.set_player(p, **kw)       # the position goes in first so the team move finds the right slot
                if moved:
                    db.set_player(p, team=team.index)
                by_name[(p.first.lower(), p.last.lower())] = p
                rep.created += new
                rep.updated += (not new) and bool(kw or moved)
            except (ValueError, KeyError, TypeError) as x:
                rep.problems.append(f'{label}: {x}')
        ros = db.roster_of(team.index)
        if ros.holes() and not ros.auto_lineups(db.players):
            rep.problems.append(f'{team.full}: not enough players to fill a lineup (it needs a starter and a hitter '
                                'for every position).')
    return rep


def random_name(db, rng=None):
    """A first and last name drawn from the game's own players (each from a different one)."""
    import random
    rng = rng or random
    pool = [p for p in db.players if p.first and p.last and p.first.isascii() and p.last.isascii()]
    return rng.choice(pool).first, rng.choice(pool).last


def create_player(db, team, pos, overall=None, first=None, last=None, rng=None):
    """Turns a spare built-face player into a new one on team. pos is a position index (0 pitcher). Ratings are
    the spare's own, moved up or down together so his overall lands on `overall`. Returns the Player."""
    import random
    rng = rng or random
    spare = next((c for c in _donors(db, set()) if c.pitcher == (pos == 0)), None)
    if spare is None:
        raise ValueError('no spare player left to turn into a new one')
    if first is None or last is None:
        first, last = random_name(db, rng)
    kw = {'first': first[:15], 'last': last[:15], 'pos': pos,
          'bits': {'jersey': rng.randint(1, 99), 'jersey2': 0}}
    kw['bits']['jersey2'] = kw['bits']['jersey']
    if overall is not None and spare.att is not None:
        shift = int(overall) - spare.rating('RANK')
        use = 3 if pos == 0 else 2
        kw['ratings'] = {f: max(20, min(99 if f != 'RANK' else 125, spare.rating(f) + shift))
                         for f, _, *who in R.RATINGS if who[use - 2] and f in spare.att.fields and f != 'POTENTIAL'}
        kw['ratings']['RANK'] = max(1, min(125, int(overall)))
    db.set_player(spare, **kw)
    db.set_player(spare, team=team.index)
    return spare


def load(path):
    with open(path, encoding='utf-8-sig') as f:
        return json.load(f)


SAMPLE = {
    'format': FORMAT, 'version': 1,
    'teams': [{
        'team': 'New York Yankees', 'replace': False,
        'players': [
            {'first': 'Babe', 'last': 'Ruth', 'pos': 'RF', 'number': 3, 'bats': 'L', 'throws': 'L', 'height': '6\'2"',
             'overall': 99, 'ratings': {'contact_vs_r': 110, 'contact_vs_l': 99, 'power_vs_r': 125, 'power_vs_l': 115,
                                        'vision': 90, 'discipline': 99, 'speed': 55}},
            {'first': 'Lou', 'last': 'Gehrig', 'pos': '1B', 'number': 4, 'bats': 'L', 'throws': 'L', 'height': '6\'0"',
             'overall': 99, 'ratings': {'contact_vs_r': 115, 'contact_vs_l': 100, 'power_vs_r': 115, 'power_vs_l': 100,
                                        'vision': 95, 'discipline': 95, 'durability': 99}},
        ],
    }],
}
