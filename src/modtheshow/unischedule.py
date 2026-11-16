"""Uniform data from FRONTEND/UNIFORMS: what each team owns (MLBUNIS.JSON) and when it wears it (MLBUNIRULES.JSON).

A rule says: for team `teamid` (MLBUNIS gameid), in home (1) or away (0) games, wear jersey `uni_id` with pants
`pants_id` and the cap from `cap_id` (all MLBUNIS ids). It applies on the weekdays in dayOfWeekMask (bit 0 Sunday ..
bit 6 Saturday), at day/night `dayOrNight` (0 any), between date_start and date_stop written as MMDD (0 = open),
`percentage` of the time. A rule with chance 0 or no days is off.
"""
import json

UNIS = 'FRONTEND/UNIFORMS/MLBUNIS.JSON'
RULES = 'FRONTEND/UNIFORMS/MLBUNIRULES.JSON'
DAYS = ('Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat')
TIMES = ('Any time', 'Day', 'Night')
KINDS = {0: 'Home & Road', 1: 'Alternate', 2: 'City Connect', 3: 'Throwback', 4: 'Holiday', 5: 'Jackie Robinson Day',
         6: 'Spring & Practice', 8: 'All-Star', 9: 'Home Run Derby'}
FIELDS = ('teamid', 'uni_id', 'pants_id', 'cap_id', 'homeOrAway', 'percentage', 'dayOfWeekMask', 'dayOrNight',
          'date_start', 'date_stop', 'comment')


def load(path):
    with open(path, 'rb') as f:
        raw = f.read()
    return json.loads(raw.decode('utf-8-sig'))


def dump(doc, path):
    """Same shape the game ships: 4-space indent, CRLF."""
    text = json.dumps(doc, indent=4, ensure_ascii=False).replace('\n', '\r\n')
    with open(path, 'wb') as f:
        f.write(text.encode('utf-8'))


def new_rule(teamid, uni):
    return {'teamid': teamid, 'uni_id': uni, 'pants_id': uni, 'cap_id': uni, 'homeOrAway': 1, 'percentage': 100,
            'dayOfWeekMask': 127, 'dayOrNight': 0, 'date_start': 0, 'date_stop': 0, 'comment': ''}


def days_text(mask):
    if mask == 127:
        return 'Every day'
    if mask == 0:
        return 'Never'
    if mask == 0b1000001:
        return 'Weekends'
    if mask == 0b0111110:
        return 'Weekdays'
    on = [d for i, d in enumerate(DAYS) if mask >> i & 1]
    if len(on) == 6:
        return 'All but ' + next(d for i, d in enumerate(DAYS) if not mask >> i & 1)
    return ', '.join(on)


def date_text(md):
    if not md:
        return ''
    m, d = divmod(int(md), 100)
    names = 'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()
    return f'{names[m - 1]} {d}' if 1 <= m <= 12 else str(md)


def dates_text(a, b):
    if not a and not b:
        return 'All season'
    if a and a == b:
        return date_text(a)
    if a and not b:
        return 'From ' + date_text(a)
    if b and not a:
        return 'Until ' + date_text(b)
    return f'{date_text(a)} – {date_text(b)}'


def team_rules(rules, teamid):
    return [dict(r) for r in rules if r.get('teamid') == teamid]


def put_team_rules(rules, teamid, mine):
    """Swap one team's rules in place and keep everyone else where they were."""
    idx = [i for i, r in enumerate(rules) if r.get('teamid') == teamid]
    at = idx[0] if idx else next((i for i, r in enumerate(rules) if r.get('teamid', 0) > teamid), len(rules))
    rest = [r for r in rules if r.get('teamid') != teamid]
    at -= sum(1 for i in idx if i < at)
    return rest[:at] + [{k: r.get(k, '') for k in FIELDS} for r in mine] + rest[at:]
