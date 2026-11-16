"""Teams and players from FRONTEND/STATS (the game's LE90 database files).

An LE90 file describes its tables first ([DESC]: table name, then 32-byte field records of name, id, type, count and
byte size), then holds the data ([DATA]): table name, u32 record count, records. A record is its fields in DESC order,
followed by any child tables it owns (a player owns a contract, animations, audio and so on).

ROSTERS.BIN: D_TEAM_PROF, one per team (MLB, minors, classic and custom teams), in team index order.
PLAYERS.BIN: PLR_PROFS (names, position, team), then D_PLAYER_ACC, D_PLAYER_APP and PLR_ATT in the same player order.
The team a player belongs to is byte 0 of PLR_PROFS.SIGNED_PACK; 255 means free agent.

Edits are written in place (fixed-size fields), so the file layout never changes. The game ships _LIVE and _INJ
copies of both files; every save patches all of them.
"""
import os
import re
import struct

ROSTERS = 'FRONTEND/STATS/ROSTERS.BIN'
PLAYERS = 'FRONTEND/STATS/PLAYERS.BIN'
VARIANTS = ('', '_LIVE', '_INJ')
POSITIONS = ('P', 'C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF')
FREE_AGENT = 255
LEVEL_ORDER = ('MLB', 'Triple-A', 'Double-A', 'High-A', 'All-Star & Classic', 'Other Teams')

# rating fields worth editing, (field, label, hitter?, pitcher?)
RATINGS = [('RANK', 'Overall', 1, 1), ('POTENTIAL', 'Potential', 1, 1),
           ('CONTACT_LEFT', 'Contact vs L', 1, 0), ('CONTACT_RIGHT', 'Contact vs R', 1, 0),
           ('POWER_LEFT', 'Power vs L', 1, 0), ('POWER_RIGHT', 'Power vs R', 1, 0),
           ('PLATE_VISION', 'Vision', 1, 0), ('PLATE_DISCIPLINE', 'Discipline', 1, 0),
           ('BATTING_CLUTCH', 'Clutch', 1, 0), ('BUNTING_ABILITY', 'Bunting', 1, 0),
           ('SPEED', 'Speed', 1, 1), ('BASE_STEALING', 'Stealing', 1, 0),
           ('ARM_STRENGTH', 'Arm Strength', 1, 1), ('ARM_ACCURACY', 'Arm Accuracy', 1, 1),
           ('FIELDING_ABILITY', 'Fielding', 1, 1), ('REACTION_TIME', 'Reaction', 1, 1),
           ('DURABILITY', 'Durability', 1, 1), ('BLOCKING', 'Blocking', 1, 0),
           ('STAMINA', 'Stamina', 0, 1), ('PITCHING_CLUTCH', 'Pitching Clutch', 0, 1),
           ('HITS_PER_BF', 'H per 9', 0, 1), ('HR_PER_BF', 'HR per 9', 0, 1),
           ('K_PER_BF_RIGHT', 'K per 9', 0, 1), ('BB_PER_BF', 'BB per 9', 0, 1)]


EQUIPMENT = 'FRONTEND/EQUIPMENT/MLBEQUIPMENT.JSON'
# D_PLAYER_ACC field -> (equipment type in MLBEQUIPMENT.JSON, label). The stored value is the item's `style`.
SLOTS = [('BAT', 0, 'Bat'), ('BAT_GRIP', 8, 'Bat Grip'), ('BATTING_GLOVES', 1, 'Batting Gloves'), ('GLOVE', 3, 'Glove'),
         ('SHOES', 2, 'Cleats'), ('ELBOW_GUARD', 9, 'Elbow Guard'), ('SHIN_GUARD', 12, 'Shin Guard'),
         ('WRIST_BRACES', 14, 'Wrist Guard'), ('COMP_SLEEVES', 13, 'Sleeve'), ('GLASSES', 7, 'Eyewear'),
         ('CATCHER_MASK', 10, 'Catcher Mask'), ('CHEST_PROTECTOR', 11, 'Chest Protector'),
         ('CATCHER_SHN_GRD', 15, 'Leg Guards')]


class Equipment:
    """The equipment catalog: for each slot, the items a player can wear, in the game's order."""

    def __init__(self, path):
        import json
        with open(path, 'rb') as f:
            doc = json.loads(f.read().decode('utf-8-sig'))
        makers = {m['id']: m for m in doc.get('makers', [])}
        self.by_type = {}
        for it in doc.get('eqlist', []):
            brand = makers.get(it.get('brand'), {}).get('name', '')
            brand = '' if brand.lower().startswith('zgeneric') else brand
            name = it['name'].strip()
            label = '' if name.lower() in ('tbd', '') else (name if name.lower().startswith(brand.lower()) else (brand + ' ' + name).strip())
            self.by_type.setdefault(it['type'], []).append((it['style'], label, bool(it.get('enb')), it))
        for t in self.by_type:
            self.by_type[t].sort(key=lambda x: x[0])

    def metal_bats(self):
        """[(style, label)] of the aluminum bats (the Road to the Show college ones): bats the catalog marks mtl=1."""
        return [(st, lab or f'Metal bat {st}') for st, lab, _on, it in self.by_type.get(0, [])
                if 'mtl=1' in str(it.get('gfxinfo', '')).replace(' ', '')]

    def choices(self, slot_type):
        """[(style, label)] for a slot, enabled items only (plus 'None' for 0 where the game uses it)."""
        out = [(st, lab) for st, lab, en, _ in self.by_type.get(slot_type, []) if en and lab]
        if slot_type == 0:      # bats: the metal ones are switched off in the list but a player can still be given one
            out += [(st, f'Aluminum: {lab}') for st, lab in self.metal_bats()]
        seen, uniq = set(), []
        for st, lab in out:
            if st not in seen:
                seen.add(st)
                uniq.append((st, lab))
        return uniq

    def label(self, slot_type, style):
        for st, lab, _en, _ in self.by_type.get(slot_type, []):
            if st == style and lab:
                return lab
        return 'None' if style == 0 else f'#{style}'


# The game's sounds for a regular stadium, and the set it loads for high school and college games. Every sound has
# the same name in both; in the second one the ball comes off an aluminum bat.
STADIUM_SOUNDS = 'NSW/AUDIO/GAMEFX_EXTERIOR_STADIUMS.BNK'
COLLEGE_SOUNDS = 'NSW/AUDIO/GAMEFX_AMATEUR.BNK'
_ITEM = re.compile(r'\{[^{}]*\}')


def allow_metal_bats(text):
    """The equipment list with its aluminum bats switched on, and how many were off.

    The list ships them with "enb": 0. When the game builds a bat it asks whether the style is switched off, and
    hands over the plain wood bat if it is, unless the game is a Road to the Show college game or the style is one
    of 22, 63, 64, 119, 120. Only that one number changes; the rest of the file is kept to the letter."""
    n = 0

    def fix(m):
        nonlocal n
        block = m.group(0)
        if not re.search(r'"type"\s*:\s*0\s*,', block) or not re.search(r'"gfxinfo"\s*:\s*"[^"]*mtl\s*=\s*1', block):
            return block
        out = re.sub(r'("enb"\s*:\s*)0\b', r'\g<1>1', block, count=1)
        n += out != block
        return out
    return _ITEM.sub(fix, text), n


def metal_bat_files(source, files, folder, sound=False):
    """[(game path, file to put there)] that aluminum bats need besides the roster: the equipment list with the
    bats switched on and, with sound, the college game sounds standing in for the stadium ones.

    source(rel) gives the file to start from, files is the set of paths the game has, folder is where the new
    files are written."""
    out = []
    if EQUIPMENT in files and os.path.exists(source(EQUIPMENT)):
        with open(source(EQUIPMENT), 'rb') as f:
            text, n = allow_metal_bats(f.read().decode('latin-1'))
        if n:
            p = os.path.join(folder, os.path.basename(EQUIPMENT))
            with open(p, 'wb') as f:
                f.write(text.encode('latin-1'))
            out.append((EQUIPMENT, p))
    if sound and STADIUM_SOUNDS in files and COLLEGE_SOUNDS in files and os.path.exists(source(COLLEGE_SOUNDS)):
        out.append((STADIUM_SOUNDS, source(COLLEGE_SOUNDS)))
    return out


class Rec:
    __slots__ = ('table', 'off', 'fields', 'kids')

    def __init__(self, table, off):
        self.table, self.off, self.fields, self.kids = table, off, {}, {}

    def raw(self, name):
        return self.fields[name][1]

    def at(self, name):
        return self.fields[name][0]

    def int(self, name):
        return int.from_bytes(self.raw(name), 'little')

    def text(self, name):
        return self.raw(name).split(b'\0')[0].decode('latin1')


class LE90:
    def __init__(self, data):
        self.d = bytearray(data)
        if self.d[:4] != b'LE90':
            raise ValueError('not a stats database (LE90)')
        d, o = self.d, 8
        if d[o:o + 6] != b'[DESC]':
            raise ValueError('no [DESC] block')
        o += 6
        self.desc = {}
        while d[o:o + 6] != b'[DATA]':
            name = self._name(o)
            _size, nf = struct.unpack_from('<II', d, o + 16)
            o += 24
            fields = []
            for _ in range(nf):
                fn = d[o:o + 22].split(b'\0')[0].decode('latin1')
                _fid, _type, _count, size, _pad = struct.unpack_from('<5H', d, o + 22)
                fields.append((fn, size))
                o += 32
            self.desc[name] = fields
            if o >= len(d):
                raise ValueError('[DATA] block missing')
        o += 6
        self.tables = {}
        self._kidset = {}
        while o < len(d) and self._name(o) in self.desc:
            name = self._name(o)
            recs, o = self._table(o, 0)
            self.tables.setdefault(name, recs)
        self.end = o

    def _name(self, o):
        return self.d[o:o + 16].split(b'\0')[0].decode('latin1', 'replace')

    def _table(self, o, depth):
        name = self._name(o)
        n, = struct.unpack_from('<I', self.d, o + 16)
        o += 20
        recs = []
        for _ in range(n):
            r = Rec(name, o)
            for fn, size in self.desc[name]:
                r.fields[fn] = (o, bytes(self.d[o:o + size]))
                o += size
            if depth == 0:
                allowed = self._kidset.get(name)
                while o < len(self.d) and self._name(o) in self.desc:
                    kn = self._name(o)
                    if (allowed is not None and kn not in allowed) or kn == name or kn in r.kids:
                        break
                    r.kids[kn], o = self._table(o, 1)
                self._kidset.setdefault(name, set(r.kids))
            recs.append(r)
            if o > len(self.d):
                raise ValueError(f'{name} runs past the end of the file')
        return recs, o

    def put(self, rec, name, value):
        off, old = rec.fields[name]
        if isinstance(value, str):
            b = value.encode('latin1', 'replace')[:len(old) - 1]
            value = b + b'\0' * (len(old) - len(b))
        elif isinstance(value, int):
            value = value.to_bytes(len(old), 'little', signed=value < 0)
        assert len(value) == len(old)
        self.d[off:off + len(old)] = value
        rec.fields[name] = (off, bytes(value))

    def bytes(self):
        return bytes(self.d)


def read(path):
    with open(path, 'rb') as f:
        return LE90(f.read())


class Team:
    def __init__(self, index, rec):
        self.index, self.rec = index, rec
        self.city = rec.text('CITY_NAME')
        self.name = rec.text('TEAM_NAME')
        self.short = rec.text('SHORT_NAME')
        self.league = rec.int('LEAGUE_INX')
        self.division = rec.int('DIVISION_INX')

    @property
    def full(self):
        return f'{self.city} {self.name}'.strip() if self.city != self.name else self.name

    def level(self):
        i = self.index
        return ('MLB' if i < 30 else 'All-Star & Classic' if i < 35 else 'Triple-A' if i < 65 else
                'Double-A' if i < 95 else 'High-A' if i < 125 else 'Other Teams')


class Player:
    def __init__(self, i, prof, att, acc=None, app=None):
        self.i, self.prof, self.att, self.acc, self.app = i, prof, att, acc, app
        self.id = prof.int('PLAYER_ID')
        self.first = prof.text('FIRST_NAME')
        self.last = prof.text('LAST_NAME')
        self.pos = prof.int('POSITION')
        self.team = prof.raw('SIGNED_PACK')[0]

    # packed fields: (field, bit, width). UNSIGNED_PACK is 28 bytes little-endian.
    BITS = {'jersey': ('UNSIGNED_PACK', 128, 7), 'jersey2': ('UNSIGNED_PACK', 135, 7),
            'height': ('UNSIGNED_PACK', 9, 7), 'bats': ('UNSIGNED_PACK', 23, 2), 'throws': ('SIGNED_PACK', 30, 1)}

    def bits(self, key):
        f, b, w = self.BITS[key]
        return (self.prof.int(f) >> b) & ((1 << w) - 1)

    @property
    def name(self):
        return f'{self.first} {self.last}'.strip()

    @property
    def pitcher(self):
        return self.pos == 0

    @property
    def generic_face(self):
        """True when the player uses a built face (HEAD_SHAPE set) rather than a scanned head."""
        return self.app is not None and 'HEAD_SHAPE' in self.app.fields and self.app.int('HEAD_SHAPE') > 0

    def rating(self, field):
        return self.att.int(field) if self.att is not None and field in self.att.fields else 0

    def gear(self, field):
        return self.acc.int(field) if self.acc is not None and field in self.acc.fields else 0


def _plain(text):
    import unicodedata
    t = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in t if c.isalnum()).upper()


def head_candidates(first, last):
    """Folder names under NSW/CHARACTERS/HEADS the game might use for a player (LAST_FIRST, Jr. folded in)."""
    f, l = _plain(first), _plain(last)
    bare = last
    for suf in (' Jr.', ' Jr', ' Sr.', ' IV', ' III', ' II'):
        bare = bare.replace(suf, '')
    bare = _plain(bare)
    out = []
    for ln in (l, bare):
        for fn in (f, f[:2], f[:3]):
            out.append(f'{ln}_{fn}')
    return list(dict.fromkeys(x for x in out if not x.endswith('_')))


_HEADS = {}


def _head_folders(files):
    key = id(files)
    if key not in _HEADS:
        pre = 'NSW/CHARACTERS/HEADS/'
        _HEADS.clear()
        _HEADS[key] = {f.split('/')[3] for f in files if f.startswith(pre) and f.endswith('-COLOR.TEX')}
    return _HEADS[key]


def find_head(files, first, last):
    """files: a set of romfs paths. Returns the face texture pack path, or None."""
    folders = _head_folders(files)
    cands = head_candidates(first, last)
    hit = next((c for c in cands if c in folders), None)
    if hit is None:
        # same-name players get a letter on the end (BELL_JOSHE); take it when only one fits
        for c in cands[:1] + cands[3:4]:
            near = [f for f in folders if f.startswith(c) and len(f) == len(c) + 1]
            if len(near) == 1:
                hit = near[0]
                break
    return f'NSW/CHARACTERS/HEADS/{hit}/{hit}-COLOR.TEX' if hit else None


class Roster:
    """A team's D_ROSTER_HLPR: 95 slots of 1-based player numbers (0 = empty) and five lineups.

    Slots 0-4 are the rotation, 5 the closer, 6-29 the bullpen, 30-94 position players. A lineup's ROSTER holds
    the slot playing each defensive position (0 P, 1 C, 2 1B, 3 2B, 4 3B, 5 SS, 6 LF, 7 CF, 8 RF, 9 DH; 255 none)
    and BATTING_ORDER the positions batting 1-9.
    """
    PITCHERS = range(0, 30)
    HITTERS = range(30, 95)

    def __init__(self, rec):
        self.rec = rec
        self.slots = list(struct.unpack('<95I', rec.raw('PLAYER_NUMS')))
        self.lineups = [(bytearray(l.raw('ROSTER')), bytearray(l.raw('BATTING_ORDER'))) for l in rec.kids.get('D_LINEUP', [])]
        # how each lineup was set up: None unused, True with a DH, False with the pitcher batting
        self.shape = [None if all(b == 255 for b in r) else r[9] != 255 for r, _ in self.lineups]
        self.dirty = False

    def slot_of(self, player_index):
        try:
            return self.slots.index(player_index + 1)
        except ValueError:
            return None

    def remove(self, player_index):
        k = self.slot_of(player_index)
        if k is None:
            return
        self.slots[k] = 0
        self.dirty = True
        if k < 6:        # rotation or closer: the next arm moves up, so lineups pointing here stay right
            nxt = next((j for j in range(6, 30) if self.slots[j]), None)
            if nxt is not None:
                self.slots[k], self.slots[nxt] = self.slots[nxt], 0
                k = nxt
        # anyone this slot was playing gets covered by the first bench bat or bullpen arm not already used
        for roster, order in self.lineups:
            for pos, sl in enumerate(roster):
                if sl == k:
                    pool = self.HITTERS if pos else range(6, 30)
                    sub = next((j for j in pool if self.slots[j] and j not in roster), 255)
                    roster[pos] = sub
                    if sub == 255 and pos and pos in order:
                        order[order.index(pos)] = 0

    def holes(self):
        """True when a lineup in use has a position nobody is playing."""
        return any(sh is not None and any(sl == 255 or not self.slots[sl] for sl in r[:9])
                   for (r, _), sh in zip(self.lineups, self.shape))

    def auto_lineups(self, players):
        """Fills every lineup in use from the players on the roster: the best glove-for-position at each spot, the best
        remaining bat at DH, and a batting order from best hitter down. players is Database.players."""
        def who(sl):
            return players[self.slots[sl] - 1]

        def bat(p):
            return sum(p.rating(f) for f in ('CONTACT_LEFT', 'CONTACT_RIGHT', 'POWER_LEFT', 'POWER_RIGHT'))

        hitters = [sl for sl in self.HITTERS if self.slots[sl]]
        if not hitters or not self.slots[0]:
            return False
        near = {1: (1,), 2: (2, 4, 3), 3: (3, 5, 4), 4: (4, 5, 3, 2), 5: (5, 3, 4), 6: (6, 8, 7), 7: (7, 6, 8), 8: (8, 6, 7)}
        field, used = {}, set()
        for pos in (1, 5, 7, 3, 4, 2, 8, 6):          # hardest spots to cover first
            for accept in near[pos]:
                fit = [sl for sl in hitters if sl not in used and who(sl).pos == accept]
                if fit:
                    break
            else:
                fit = [sl for sl in hitters if sl not in used]
            if not fit:
                return False
            best = max(fit, key=lambda sl: who(sl).rating('RANK'))
            field[pos] = best
            used.add(best)
        spare = [sl for sl in hitters if sl not in used]
        dh = max(spare, key=lambda sl: bat(who(sl))) if spare else 255
        for k, ((roster, order), shape) in enumerate(zip(self.lineups, self.shape)):
            if shape is None:
                continue
            roster[0] = 0
            for pos, sl in field.items():
                roster[pos] = sl
            use_dh = shape and dh != 255
            roster[9] = dh if use_dh else 255
            spots = sorted(list(field) + ([9] if use_dh else []), key=lambda pos: -bat(who(roster[pos])))
            if not use_dh:
                spots = spots + [0]
            order[:] = bytes(spots[:9])
        self.dirty = True
        return True

    def add(self, player_index, pitcher):
        group = self.PITCHERS if pitcher else self.HITTERS
        k = next((j for j in group if self.slots[j] == 0), None)
        if k is None:
            return False
        self.slots[k] = player_index + 1
        self.dirty = True
        return True

    def apply(self, db):
        db.put(self.rec, 'PLAYER_NUMS', struct.pack('<95I', *self.slots))
        for (roster, order), l in zip(self.lineups, self.rec.kids.get('D_LINEUP', [])):
            db.put(l, 'ROSTER', bytes(roster))
            db.put(l, 'BATTING_ORDER', bytes(order))


class Database:
    """Teams and players, with edits that can be written back to every copy the game ships."""

    def __init__(self, rosters_path, players_path):
        self.rdb = read(rosters_path)
        self.pdb = read(players_path)
        self.teams = [Team(i, r) for i, r in enumerate(self.rdb.tables.get('D_TEAM_PROF', []))]
        profs = self.pdb.tables.get('PLR_PROFS', [])
        atts = self.pdb.tables.get('PLR_ATT', [])
        accs = self.pdb.tables.get('D_PLAYER_ACC', [])
        if atts and len(atts) != len(profs):
            atts = []
        if accs and len(accs) != len(profs):
            accs = []
        apps = self.pdb.tables.get('D_PLAYER_APP', [])
        if apps and len(apps) != len(profs):
            apps = []
        self.players = [Player(i, p, atts[i] if atts else None, accs[i] if accs else None, apps[i] if apps else None)
                        for i, p in enumerate(profs)]
        self.edits_t = {}     # team index -> {field: value}
        self.edits_p = {}     # player index -> {('prof'|'att', field): value}
        self.rosters = {}     # team index -> Roster, once touched

    def team_name(self, idx):
        if idx == FREE_AGENT:
            return 'Free Agent'
        return self.teams[idx].full if 0 <= idx < len(self.teams) else f'Team {idx}'

    def roster(self, idx):
        return [p for p in self.players if p.team == idx]

    # ---- edits
    def set_team(self, team, city=None, name=None, short=None):
        e = self.edits_t.setdefault(team.index, {})
        for field, v in (('CITY_NAME', city), ('TEAM_NAME', name), ('SHORT_NAME', short)):
            if v is not None:
                e[field] = v
        team.city = city if city is not None else team.city
        team.name = name if name is not None else team.name
        team.short = short if short is not None else team.short

    def set_player(self, p, **kw):
        e = self.edits_p.setdefault(p.i, {})
        if 'first' in kw:
            p.first = kw['first']
            e[('prof', 'FIRST_NAME')] = p.first
        if 'last' in kw:
            p.last = kw['last']
            e[('prof', 'LAST_NAME')] = p.last
        if 'pos' in kw:
            p.pos = int(kw['pos'])
            e[('prof', 'POSITION')] = p.pos
        if 'team' in kw and int(kw['team']) != p.team:
            old, new = p.team, int(kw['team'])
            if old < len(self.teams):
                self.roster_of(old).remove(p.i)
            if new < len(self.teams) and not self.roster_of(new).add(p.i, p.pitcher):
                raise ValueError(f'{self.team_name(new)} has no open {"pitcher" if p.pitcher else "position player"} slot')
            p.team = new
            e[('team',)] = p.team
        for f, v in kw.get('ratings', {}).items():
            e[('att', f)] = max(0, min(255, int(v)))
            if p.att is not None and f in p.att.fields:      # readable straight away, before anything is saved
                off, old = p.att.fields[f]
                p.att.fields[f] = (off, int(e[('att', f)]).to_bytes(len(old), 'little'))
        for key, v in kw.get('bits', {}).items():
            f, b, w = Player.BITS[key]
            raw = p.prof.int(f)
            raw = (raw & ~(((1 << w) - 1) << b)) | ((int(v) & ((1 << w) - 1)) << b)
            size = len(p.prof.raw(f))
            p.prof.fields[f] = (p.prof.fields[f][0], raw.to_bytes(size, 'little'))
            e[('prof', f)] = p.prof.raw(f)
        if kw.get('look') is not None and kw['look'].app is not None and p.app is not None:
            # wear another player's face and body: the whole appearance record is copied
            src = kw['look']
            e[('app',)] = src.i
            for f, (off, _) in list(p.app.fields.items()):
                p.app.fields[f] = (off, src.app.raw(f))
        for f, v in kw.get('shape', {}).items():
            # body proportions (HEAD_SCALE, NECK_SCALE and friends): a byte each, 127 or so is the usual build
            if p.app is not None and f in p.app.fields:
                e[('shape', f)] = max(0, min(255, int(v)))
                p.app.fields[f] = (p.app.fields[f][0], int(e[('shape', f)]).to_bytes(len(p.app.raw(f)), 'little'))
        for f, v in kw.get('gear', {}).items():
            size = len(p.acc.raw(f)) if p.acc is not None and f in p.acc.fields else 1
            e[('acc', f)] = max(0, min((1 << (8 * size)) - 1, int(v)))
            if p.acc is not None and f in p.acc.fields:
                p.acc.fields[f] = (p.acc.fields[f][0], int(e[('acc', f)]).to_bytes(size, 'little'))

    def roster_of(self, team_index):
        if team_index not in self.rosters:
            hl = self.rdb.tables.get('D_ROSTER_HLPR', [])
            self.rosters[team_index] = Roster(hl[team_index])
        return self.rosters[team_index]

    def dirty(self):
        return bool(self.edits_t or self.edits_p or any(r.dirty for r in self.rosters.values()))

    def _apply_teams(self, db, edits):
        teams = db.tables.get('D_TEAM_PROF', [])
        for idx, e in edits.items():
            if idx < len(teams):
                for f, v in e.items():
                    db.put(teams[idx], f, v)
        hl = db.tables.get('D_ROSTER_HLPR', [])
        for idx, r in self.rosters.items():
            if r.dirty and idx < len(hl):
                mine = Roster(hl[idx])
                mine.slots, mine.lineups = r.slots, r.lineups
                mine.apply(db)

    def _apply_players(self, db, edits):
        profs = db.tables.get('PLR_PROFS', [])
        atts = db.tables.get('PLR_ATT', [])
        accs = db.tables.get('D_PLAYER_ACC', [])
        apps = db.tables.get('D_PLAYER_APP', [])
        same = len(profs) == len(self.players) and all(
            profs[i].int('PLAYER_ID') == self.players[i].id for i in range(0, len(profs), 97))
        by_id = None if same else {}
        if by_id is not None:
            for i, r in enumerate(profs):
                by_id.setdefault(r.int('PLAYER_ID'), i)

        def locate(i):
            j = i if same else by_id.get(self.players[i].id)
            return j if j is not None and j < len(profs) else None

        for i, e in edits.items():
            j = locate(i)
            if j is None:
                continue
            for key, v in sorted(e.items(), key=lambda kv: kv[0][0] == 'shape'):     # a copied look first, shapes on top
                if key == ('app',):
                    k = locate(v)
                    if k is not None and j < len(apps) and k < len(apps):
                        # the source's bytes as they were when the edit was made (kept on the in-memory record)
                        for f in apps[j].fields:
                            db.put(apps[j], f, self.players[i].app.raw(f))
                elif key == ('team',):
                    sp = bytearray(profs[j].raw('SIGNED_PACK'))
                    sp[0] = v
                    db.put(profs[j], 'SIGNED_PACK', bytes(sp))
                elif key[0] == 'prof':
                    db.put(profs[j], key[1], v)
                elif key[0] == 'att' and j < len(atts) and key[1] in atts[j].fields:
                    db.put(atts[j], key[1], v)
                elif key[0] == 'acc' and j < len(accs) and key[1] in accs[j].fields:
                    db.put(accs[j], key[1], v)
                elif key[0] == 'shape' and j < len(apps) and key[1] in apps[j].fields:
                    db.put(apps[j], key[1], v)

    def write(self, sources, out):
        """sources: {rel: path to read}; out(rel, bytes) stores the result. Patches every variant that exists."""
        n = 0
        for rel, path in sources.items():
            db = read(path)
            if rel.startswith('FRONTEND/STATS/ROSTERS'):
                self._apply_teams(db, self.edits_t)
            else:
                self._apply_players(db, self.edits_p)
            out(rel, db.bytes())
            n += 1
        return n


def variants(base):
    stem = base[:-4]
    return [stem + v + '.BIN' for v in VARIANTS]
