"""When each uniform gets worn (MLBUNIRULES.JSON) and which uniforms show in the menus (MLBUNIS.JSON)."""
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDateEdit, QGridLayout, QHBoxLayout,
                               QHeaderView, QLineEdit, QMessageBox, QPushButton, QSpinBox, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from .. import unischedule as us
from .common import button, label

OPEN = QDate(2000, 1, 1)      # the "Open" value; 2000 is a leap year so Feb 29 works


def _md(d):
    return 0 if d == OPEN else d.month() * 100 + d.day()


def _qd(md):
    if not md:
        return OPEN
    m, d = divmod(int(md), 100)
    q = QDate(2000, m, d)
    return q if q.isValid() and q != OPEN else QDate(2000, 1, 2)


class TeamUniforms:
    """The two JSON files, read once per team pick."""

    def __init__(self, main):
        self.main = main
        self.unis = self.rules = None

    def load(self):
        self.unis = us.load(self.main.current_file(us.UNIS))
        self.rules = us.load(self.main.current_file(us.RULES))

    def team(self, uniform_path):
        """(gameid, [uniform dicts]) for a uniform_path like 'NL/ARI'."""
        mine = [u for u in self.unis['uniforms'] if u.get('uniform_path', '').upper() == uniform_path.upper()]
        return (mine[0]['gameid'] if mine else None), mine

    def name(self, uid):
        for u in self.unis['uniforms']:
            if u['id'] == uid:
                return u['dpy_name']
        return f'#{uid}'


def table(headers):
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.verticalHeader().setVisible(False)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setSelectionMode(QAbstractItemView.SingleSelection)
    t.setAlternatingRowColors(False)
    t.setShowGrid(False)
    t.setWordWrap(False)
    t.verticalHeader().setDefaultSectionSize(34)
    t.setFocusPolicy(Qt.NoFocus)
    t.horizontalHeader().setHighlightSections(False)
    return t


class ScheduleEditor(QWidget):
    def __init__(self, main, data):
        super().__init__()
        self.main, self.data = main, data
        self.teamid = None
        self.rules = []
        self.unis = []
        self._busy = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        self.note = label('', 'Sub', wrap=True)
        lay.addWidget(self.note)
        self.table = table(['Games', 'Jersey', 'Pants', 'Cap', 'Days', 'Dates', 'Chance', 'Note'])
        h = self.table.horizontalHeader()
        for i in range(8):
            h.setSectionResizeMode(i, QHeaderView.Stretch if i in (4, 7) else QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._pick)
        lay.addWidget(self.table, 1)

        # the form for the selected rule
        form = QGridLayout()
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(8)
        self.games = QComboBox()
        self.games.addItems(['Road games', 'Home games'])
        self.jersey, self.pants, self.cap = QComboBox(), QComboBox(), QComboBox()
        for i, (w, tip) in enumerate(((self.games, 'Games'), (self.jersey, 'Jersey'), (self.pants, 'Pants'),
                                      (self.cap, 'Cap'))):
            w.setToolTip(tip)
            w.setAccessibleName(tip)
            w.setMinimumWidth(120)
            form.addWidget(w, 0, i)
            form.setColumnStretch(i, 1)
        days = QHBoxLayout()
        days.setSpacing(4)
        self.day_btns = []
        for d in us.DAYS:
            b = QPushButton(d)
            b.setObjectName('Chip')
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.toggled.connect(self._edited)
            days.addWidget(b, 1)
            self.day_btns.append(b)
        dw = QWidget()
        dw.setLayout(days)
        days.setContentsMargins(0, 0, 0, 0)
        form.addWidget(dw, 1, 0, 1, 4)
        self.time = QComboBox()
        self.time.addItems(us.TIMES)
        self.time.setToolTip('The shipped data isn’t fully consistent about day and night, so check it in a game')
        form.addWidget(self.time, 2, 2)
        self.chance = QSpinBox()
        self.chance.setRange(0, 100)
        self.chance.setSuffix('%  of games')
        form.addWidget(self.chance, 2, 3)
        self.start, self.stop = QDateEdit(), QDateEdit()
        for w, pre in ((self.start, 'From  '), (self.stop, 'Until  ')):
            w.setDisplayFormat(f"'{pre}'MMM d")
            w.setMinimumDate(OPEN)
            w.setMaximumDate(QDate(2000, 12, 31))
            w.setSpecialValueText(pre + 'open')
            w.setCalendarPopup(True)
            w.setToolTip(pre.strip() + ' (pick the very first entry for no limit)')
            w.dateChanged.connect(self._edited)
        form.addWidget(self.start, 2, 0)
        form.addWidget(self.stop, 2, 1)
        self.comment = QLineEdit()
        self.comment.setPlaceholderText('Note to yourself (the game ignores it)')
        self.comment.textEdited.connect(self._edited)
        form.addWidget(self.comment, 3, 0, 1, 4)
        for w in (self.games, self.jersey, self.pants, self.cap, self.time):
            w.currentIndexChanged.connect(self._edited)
        self.chance.valueChanged.connect(self._edited)
        self.form = QWidget()
        self.form.setLayout(form)
        form.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.form)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.b_add = button('Add Rule', on_click=self.add)
        self.b_dup = button('Duplicate', on_click=self.dup)
        self.b_del = button('Delete', on_click=self.delete)
        self.b_reset = button('Back to Default', on_click=self.reset)
        self.b_save = button('Save to My Mod', True, self.save)
        for b in (self.b_add, self.b_dup, self.b_del, self.b_reset, self.b_save):
            row.addWidget(b, 1)
        lay.addLayout(row)

    # ---- loading
    def show_team(self, uniform_path, team_name):
        try:
            self.data.load()
        except Exception as x:
            self.note.setText(f'Could not read the uniform data: {x}')
            self.teamid = None
            return
        self.teamid, self.unis = self.data.team(uniform_path)
        self.team_name = team_name
        self.rules = us.team_rules(self.data.rules['uni_rules'], self.teamid) if self.teamid is not None else []
        self._fill_combos()
        self._fill_table(0)

    def _fill_combos(self):
        ids = {u['id'] for u in self.unis}
        extra = {r[k] for r in self.rules for k in ('uni_id', 'pants_id', 'cap_id')} - ids
        self._busy = True
        for c in (self.jersey, self.pants, self.cap):
            c.clear()
            for u in self.unis:
                c.addItem(u['dpy_name'], u['id'])
            for e in sorted(extra):
                c.addItem(self.data.name(e), e)
        self._busy = False

    def _fill_table(self, select):
        self._busy = True
        self.table.setRowCount(len(self.rules))
        for i in range(len(self.rules)):
            self._fill_row(i)
        self._busy = False
        has = bool(self.rules)
        self.form.setEnabled(has)
        self.b_dup.setEnabled(has)
        self.b_del.setEnabled(has)
        self.b_add.setEnabled(self.teamid is not None and bool(self.unis))
        self.b_save.setEnabled(self.teamid is not None)
        n = len(self.rules)
        self.note.setText(
            f'{self.team_name} has {n} special rule{"s" if n != 1 else ""}. Games no rule covers use the regular home '
            'and road set. Turn a rule off by setting its chance to 0.' if self.teamid is not None
            else 'This team has no entry in the uniform data.')
        if has:
            self.table.selectRow(max(0, min(select, n - 1)))
        else:
            self._pick()

    def _fill_row(self, i):
        r = self.rules[i]
        off = not r['percentage'] or not r['dayOfWeekMask']
        t = r['dayOrNight']
        cells = ['Home' if r['homeOrAway'] else 'Road', self.data.name(r['uni_id']), self.data.name(r['pants_id']),
                 self.data.name(r['cap_id']), us.days_text(r['dayOfWeekMask']) + (f' · {us.TIMES[t]}' if 0 < t < 3 else ''),
                 us.dates_text(r['date_start'], r['date_stop']), 'Off' if off else f"{r['percentage']}%",
                 r.get('comment', '')]
        for c, text in enumerate(cells):
            it = self.table.item(i, c) or QTableWidgetItem()
            it.setText(text)
            it.setToolTip(text)
            it.setForeground(self.palette().mid() if off else self.palette().text())
            if self.table.item(i, c) is None:
                self.table.setItem(i, c, it)

    def _pick(self):
        if self._busy:
            return
        i = self.table.currentRow()
        if not (0 <= i < len(self.rules)):
            return
        r = self.rules[i]
        self._busy = True
        self.games.setCurrentIndex(1 if r['homeOrAway'] else 0)
        for c, k in ((self.jersey, 'uni_id'), (self.pants, 'pants_id'), (self.cap, 'cap_id')):
            j = c.findData(r[k])
            c.setCurrentIndex(j if j >= 0 else 0)
        for b, bit in zip(self.day_btns, range(7)):
            b.setChecked(bool(r['dayOfWeekMask'] >> bit & 1))
        self.time.setCurrentIndex(r['dayOrNight'] if 0 <= r['dayOrNight'] < 3 else 0)
        self.chance.setValue(int(r['percentage']))
        self.start.setDate(_qd(r['date_start']))
        self.stop.setDate(_qd(r['date_stop']))
        self.comment.setText(r.get('comment', ''))
        self._busy = False

    def _edited(self, *_):
        if self._busy:
            return
        i = self.table.currentRow()
        if not (0 <= i < len(self.rules)):
            return
        r = self.rules[i]
        r['homeOrAway'] = self.games.currentIndex()
        r['uni_id'] = self.jersey.currentData()
        r['pants_id'] = self.pants.currentData()
        r['cap_id'] = self.cap.currentData()
        r['dayOfWeekMask'] = sum(1 << k for k, b in enumerate(self.day_btns) if b.isChecked())
        r['dayOrNight'] = self.time.currentIndex()
        r['percentage'] = self.chance.value()
        r['date_start'] = _md(self.start.date())
        r['date_stop'] = _md(self.stop.date())
        r['comment'] = self.comment.text()
        self._busy = True
        self._fill_row(i)
        self._busy = False

    # ---- actions
    def add(self):
        if self.teamid is None or not self.unis:
            return
        self.rules.append(us.new_rule(self.teamid, self.unis[0]['id']))
        self._fill_table(len(self.rules) - 1)

    def dup(self):
        i = self.table.currentRow()
        if 0 <= i < len(self.rules):
            self.rules.insert(i + 1, dict(self.rules[i]))
            self._fill_table(i + 1)

    def delete(self):
        i = self.table.currentRow()
        if 0 <= i < len(self.rules):
            del self.rules[i]
            self._fill_table(i)

    def reset(self):
        doc = us.load(self.main.game.original(us.RULES))
        self.rules = us.team_rules(doc['uni_rules'], self.teamid)
        self._fill_table(0)
        self.main.toast('Back to the game’s schedule. Save to keep it.')

    def save(self):
        if self.teamid is None:
            return
        doc = self.data.rules
        doc['uni_rules'] = us.put_team_rules(doc['uni_rules'], self.teamid, self.rules)
        if 'count' in doc:
            doc['count'] = len(doc['uni_rules'])
        try:
            self.main.save_file(us.RULES, lambda p: us.dump(doc, p),
                                self.team_name + ' schedule saved into {mod}. Apply to use it.')
        except Exception as x:
            QMessageBox.warning(self, 'Could Not Save', str(x))


class UniformList(QWidget):
    """Rename uniforms, choose which show up in the uniform picker, and which get the City Connect look."""

    def __init__(self, main, data):
        super().__init__()
        self.main, self.data = main, data
        self.unis = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        self.note = label('Double-click a name to rename it. Untick In Menus to hide a uniform from the uniform '
                          'picker; the schedule can still use it. Tick City Connect Look on any jersey and the game '
                          'treats it as City Connect: scorebugs show the City Connect logo and the colour you kept '
                          'for City Connect in Team Colours.', 'Sub', wrap=True)
        lay.addWidget(self.note)
        self.table = table(['In Menus', 'City Connect Look', 'Name', 'Type', 'Year', 'Folder'])
        h = self.table.horizontalHeader()
        for i in (0, 1, 3, 4, 5):
            h.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        self._game_types = {}
        lay.addWidget(self.table, 1)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addStretch(1)
        self.b_reset = button('Back to Default', on_click=self.reset)
        self.b_save = button('Save to My Mod', True, self.save)
        row.addWidget(self.b_reset)
        row.addWidget(self.b_save)
        lay.addLayout(row)

    def show_team(self, uniform_path, team_name):
        try:
            self.data.load()
        except Exception as x:
            self.note.setText(f'Could not read the uniform data: {x}')
            return
        self.team_name = team_name
        _, self.unis = self.data.team(uniform_path)
        if not self._game_types:
            try:
                self._game_types = {u['id']: u['unitype'] for u in
                                    us.load(self.main.game.original(us.UNIS))['uniforms']}
            except Exception:
                self._game_types = {}
        self._fill()

    def _tick(self, row, col, on, name, changed=None):
        chk = QCheckBox()
        chk.setChecked(on)
        chk.setAccessibleName(name)
        if changed:
            chk.toggled.connect(changed)
        box = QWidget()
        bl = QHBoxLayout(box)
        bl.setContentsMargins(12, 0, 0, 0)
        bl.addWidget(chk)
        self.table.setCellWidget(row, col, box)

    def _fill(self):
        self.table.setRowCount(len(self.unis))
        for i, u in enumerate(self.unis):
            self._tick(i, 0, not u.get('hideInFE'), 'Show in menus')
            self._tick(i, 1, u['unitype'] == us.CITY_CONNECT, 'City Connect look', lambda on, i=i: self._look(i, on))
            name = QTableWidgetItem(u['dpy_name'])
            name.setFlags(name.flags() | Qt.ItemIsEditable)
            self.table.setItem(i, 2, name)
            for c, text in ((3, us.KINDS.get(u['unitype'], str(u['unitype']))), (4, str(u.get('year', ''))),
                            (5, u.get('assetname', '').upper())):
                it = QTableWidgetItem(text)
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(i, c, it)

    def _look(self, i, on):
        u = self.unis[i]
        us.set_city_connect(u, on, self._game_types.get(u['id'], u['unitype']))
        self.table.item(i, 3).setText(us.KINDS.get(u['unitype'], str(u['unitype'])))

    def _collect(self):
        for i, u in enumerate(self.unis):
            chk = self.table.cellWidget(i, 0).findChild(QCheckBox)
            u['hideInFE'] = 0 if chk.isChecked() else 1
            u['dpy_name'] = self.table.item(i, 2).text().strip() or u['dpy_name']

    def reset(self):
        orig = {u['id']: u for u in us.load(self.main.game.original(us.UNIS))['uniforms']}
        for u in self.unis:
            o = orig.get(u['id'])
            if o:
                u['hideInFE'], u['dpy_name'], u['unitype'] = o.get('hideInFE', 0), o['dpy_name'], o['unitype']
        self._fill()
        self.main.toast('Back to the game’s names. Save to keep them.')

    def save(self):
        self._collect()
        doc = self.data.unis
        try:
            self.main.save_file(us.UNIS, lambda p: us.dump(doc, p),
                                self.team_name + ' uniforms saved into {mod}. Apply to use them.')
        except Exception as x:
            QMessageBox.warning(self, 'Could Not Save', str(x))
