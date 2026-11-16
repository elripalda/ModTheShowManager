"""Teams & Rosters: rename teams, edit players, move players between teams."""
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QGridLayout, QHBoxLayout, QHeaderView, QLineEdit,
                               QListWidget, QListWidgetItem, QMessageBox, QScrollArea, QSpinBox, QSplitter,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from .. import rosters as R
from .common import SectionTitle, button, header, label, panel
from .schedule import table

DIVISIONS = {0: 'AL East', 1: 'AL Central', 2: 'AL West', 3: 'NL East', 4: 'NL Central', 5: 'NL West'}


class NumItem(QTableWidgetItem):
    def __lt__(self, other):
        try:
            return int(self.text()) < int(other.text())
        except ValueError:
            return super().__lt__(other)


class TeamsPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.setObjectName('Page')
        self.main = main
        self.db = None
        self.team = None
        self.player = None
        self._busy = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(18)
        self.b_reset = button('Back to Default', on_click=self.reset)
        self.b_save = button('Save to My Mod', True, self.save)
        outer.addWidget(header('Teams & Rosters', 'Rename any team, fix player names and ratings, or move a player to '
                               'another club. Saves go into your mod like everything else.',
                               [self._tools_button(), self._file_button(), self.b_reset, self.b_save]))
        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(16)

        # teams
        left = panel()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(10, 10, 10, 10)
        ll.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Find a team or player')
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        ll.addWidget(self.search)
        self.list = QListWidget()
        self.list.setStyleSheet('QListWidget { border: none; padding: 0; background: transparent; }')
        self.list.currentItemChanged.connect(self._team_picked)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        ll.addWidget(self.list, 1)
        left.setMinimumWidth(220)
        left.setMaximumWidth(300)
        split.addWidget(left)

        # team + roster
        mid = panel()
        ml = QVBoxLayout(mid)
        ml.setContentsMargins(18, 18, 18, 18)
        ml.setSpacing(12)
        self.title = SectionTitle()
        ml.addWidget(self.title)
        names = QGridLayout()
        names.setSpacing(8)
        self.city, self.tname, self.short = QLineEdit(), QLineEdit(), QLineEdit()
        for i, (w, ph, n) in enumerate(((self.city, 'City', 19), (self.tname, 'Team name', 19),
                                        (self.short, 'Abbreviation', 4))):
            w.setPlaceholderText(ph)
            w.setToolTip(f'{ph} (up to {n} characters)')
            w.setMaxLength(n)
            w.textEdited.connect(self._team_edited)
            names.addWidget(w, 0, i)
            names.setColumnStretch(i, 1)
        ml.addLayout(names)
        self.roster = table(['Player', '#', 'Pos', 'B/T', 'OVR'])
        h = self.roster.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in (1, 2, 3, 4):
            h.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self.roster.setEditTriggers(QAbstractItemView.NoEditTriggers)
        h.setSectionsClickable(True)
        h.setSortIndicatorShown(False)
        h.sectionClicked.connect(self._sort)
        self.roster.itemSelectionChanged.connect(self._player_picked)
        ml.addWidget(self.roster, 1)
        self.count = label('', 'Sub')
        ml.addWidget(self.count)
        split.addWidget(mid)

        # player
        right = panel()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(18, 18, 18, 18)
        rl.setSpacing(12)
        self.ptitle = SectionTitle('Player')
        rl.addWidget(self.ptitle)
        form = QGridLayout()
        form.setSpacing(8)
        self.first, self.last = QLineEdit(), QLineEdit()
        self.first.setPlaceholderText('First name')
        self.last.setPlaceholderText('Last name')
        for w in (self.first, self.last):
            w.setMaxLength(15)
            w.textEdited.connect(self._player_edited)
        form.addWidget(self.first, 0, 0)
        form.addWidget(self.last, 0, 1)
        self.pos = QComboBox()
        self.pos.addItems(R.POSITIONS)
        self.pos.setToolTip('Primary position')
        self.pos.currentIndexChanged.connect(self._player_edited)
        self.number = QSpinBox()
        self.number.setRange(0, 99)
        self.number.setPrefix('#')
        self.number.setToolTip('Jersey number')
        self.number.valueChanged.connect(self._player_edited)
        self.bats = QComboBox()
        self.bats.addItems(['Bats R', 'Bats L', 'Switch'])
        self.bats.currentIndexChanged.connect(self._player_edited)
        self.throws = QComboBox()
        self.throws.addItems(['Thr R', 'Thr L'])
        self.throws.currentIndexChanged.connect(self._player_edited)
        self.height = QSpinBox()
        self.height.setRange(60, 90)
        self.height.setSuffix(' in')
        self.height.setToolTip('Height in inches (74 in is 6 ft 2)')
        self.height.valueChanged.connect(self._player_edited)
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        for wdg in (self.pos, self.number, self.bats, self.throws):
            row2.addWidget(wdg, 1)
        form.addLayout(row2, 1, 0, 1, 2)
        self.move_to = QComboBox()
        self.move_to.setToolTip('Move to another club. He leaves his old lineup and rotation; the new team puts him '
                                'on the bench or in the bullpen.')
        self.move_to.currentIndexChanged.connect(self._player_edited)
        row3 = QHBoxLayout()
        row3.setSpacing(8)
        row3.addWidget(self.height, 1)
        row3.addWidget(self.move_to, 3)
        form.addLayout(row3, 2, 0, 1, 2)
        form.setColumnStretch(0, 1)
        form.setColumnStretch(1, 1)
        rl.addLayout(form)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet('QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }')
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        rw = QWidget()
        self.rgrid = QGridLayout(rw)
        self.rgrid.setContentsMargins(0, 0, 4, 0)
        self.rgrid.setHorizontalSpacing(10)
        self.rgrid.setVerticalSpacing(4)
        from .widgets import RatingSlider
        self.spins = {}
        for field, text, _h, _p in R.RATINGS:
            s = RatingSlider(text, 0, 125)
            s.valueChanged.connect(self._player_edited)
            self.spins[field] = s
        scroll.setWidget(rw)
        rl.addWidget(scroll, 1)
        self.right = right
        from PySide6.QtWidgets import QButtonGroup, QPushButton, QStackedWidget
        from .common import Inspector
        side = QWidget()
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(10)
        chips = QHBoxLayout()
        chips.setSpacing(6)
        self.side_group = QButtonGroup(self)
        self.gear_page = self._gear_page()
        for i, text in enumerate(('Player', 'Gear', 'Face')):
            b = QPushButton(text)
            b.setObjectName('Chip')
            b.setCheckable(True)
            b.setChecked(i == 0)
            b.setCursor(Qt.PointingHandCursor)
            self.side_group.addButton(b, i)
            chips.addWidget(b, 1)
        sl.addLayout(chips)
        self.side = QStackedWidget()
        self.side.addWidget(right)
        self.side.addWidget(self.gear_page)
        self.face = Inspector(main)
        self.face.setMaximumWidth(16777215)
        self.side.addWidget(self.face)
        sl.addWidget(self.side, 1)
        self.side_group.idClicked.connect(self._side)
        side.setMinimumWidth(380)
        side.setMaximumWidth(460)
        split.addWidget(side)
        split.setStretchFactor(1, 1)
        split.setSizes([250, 640, 420])
        outer.addWidget(split, 1)

    def _tools_button(self):
        from PySide6.QtWidgets import QMenu
        b = button('Tools')
        m = QMenu(b)
        m.addAction('Arcade Rosters (boost or scramble ratings)', self.league_tools)
        m.addAction('Auto Lineup for This Team', self.auto_lineup)
        m.addAction('Team Builder Names', self.team_builder)
        b.setMenu(m)
        return b

    def _file_button(self):
        from PySide6.QtWidgets import QMenu
        b = button('Import / Export')
        m = QMenu(b)
        m.addAction('Import a Roster File (.json)', self.import_json)
        m.addSeparator()
        m.addAction('Export This Team', lambda: self.export_json(False))
        m.addAction('Export All 30 MLB Teams', lambda: self.export_json(True))
        m.addAction('Save a Sample File to Edit', self.sample_json)
        b.setMenu(m)
        return b

    def _relist(self):
        """Team names in the list and the move menu, after a rename from a file."""
        for i in range(self.list.count()):
            it = self.list.item(i)
            idx = it.data(Qt.UserRole)
            if idx is not None and idx != R.FREE_AGENT and idx < len(self.db.teams):
                it.setText(self.db.teams[idx].full)
        for i in range(self.move_to.count()):
            idx = self.move_to.itemData(i)
            if idx != R.FREE_AGENT and idx < len(self.db.teams):
                self.move_to.setItemText(i, self.db.teams[idx].full)

    def auto_lineup(self):
        if not self.db or self.team is None:
            return
        if self.db.roster_of(self.team.index).auto_lineups(self.db.players):
            self._dirty(True)
            self.main.toast(f'New lineups set for {self.team.full}. Save to My Mod to keep them.')
        else:
            QMessageBox.information(self, 'Auto Lineup', 'This team needs a starting pitcher and at least eight position '
                                    'players first.')

    def export_json(self, everyone):
        from PySide6.QtWidgets import QFileDialog
        from .. import rosterjson as J
        if not self.db or (not everyone and self.team is None):
            return
        teams = list(range(30)) if everyone else [self.team.index]
        name = 'MLB Rosters.json' if everyone else f'{self.team.full}.json'
        path, _ = QFileDialog.getSaveFileName(self, 'Export Roster', os.path.join(self.main.last_dir(), name),
                                              'Roster (*.json)')
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(J.dump(J.export(self.db, teams)))
        except OSError as x:
            QMessageBox.warning(self, 'Could Not Export', str(x))
            return
        self.main.toast(f'Exported {os.path.basename(path)}')

    def sample_json(self):
        from PySide6.QtWidgets import QFileDialog
        from .. import rosterjson as J
        path, _ = QFileDialog.getSaveFileName(self, 'Sample Roster File', os.path.join(self.main.last_dir(),
                                              'Sample Roster.json'), 'Roster (*.json)')
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(J.dump(J.SAMPLE))
            except OSError as x:
                QMessageBox.warning(self, 'Could Not Save', str(x))
                return
            self.main.toast('Sample saved. Edit it, then Import a Roster File.')

    def import_json(self, path=None):
        from PySide6.QtWidgets import QFileDialog
        from .. import rosterjson as J
        if not self.db:
            return
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, 'Import Roster', self.main.last_dir(), 'Roster (*.json)')
        if not path:
            return
        try:
            rep = J.apply(self.db, J.load(path))
        except Exception as x:
            QMessageBox.warning(self, 'Could Not Import', f'That file could not be read as a roster:\n{x}')
            return
        self._relist()
        self._fill_roster()
        self._dirty(self.db.dirty())
        if rep.problems:
            QMessageBox.information(self, 'Imported With Notes', rep.text() + '\n\n' + '\n'.join(rep.problems[:25]))
        self.main.toast(rep.text() + ' Save to My Mod to keep it.')

    def league_tools(self):
        if not self.db:
            return
        from .leaguetools import LeagueTools
        dlg = LeagueTools(self)
        if dlg.exec():
            self._dirty(True)
            self._fill_roster()
            self.main.toast(f'{dlg.count} players changed. Save to My Mod to keep it.')

    def team_builder(self):
        from .teambuilder import NAMES, PLACES, TeamBuilderDialog
        fs = self.main.game.file_set()
        if NAMES not in fs or PLACES not in fs:
            QMessageBox.information(self, 'Not Found', 'This install has no custom team name lists.')
            return
        TeamBuilderDialog(self.main).exec()

    # ---- loading
    def activate(self):
        if self.db is None:
            self.load()

    def load(self):
        g = self.main.game
        if R.ROSTERS not in g.file_set() or R.PLAYERS not in g.file_set():
            self.title.set('No roster files found')
            return
        try:
            self.db = R.Database(self.main.current_file(R.ROSTERS), self.main.current_file(R.PLAYERS))
        except Exception as x:
            self.title.set('Could not read the rosters')
            self.count.setText(str(x))
            return
        self.list.clear()
        self._fill_gear_combos()
        groups = {}
        for t in self.db.teams:
            groups.setdefault(t.level(), []).append(t)
        for lvl in R.LEVEL_ORDER:
            teams = groups.get(lvl, [])
            if not teams:
                continue
            if lvl == 'MLB':
                teams = sorted(teams, key=lambda t: (t.division, t.full))
            self._head(lvl)
            for t in teams:
                it = QListWidgetItem(t.full)
                it.setData(Qt.UserRole, t.index)
                it.setToolTip(DIVISIONS.get(t.division, '') if lvl == 'MLB' else t.short)
                self.list.addItem(it)
        self._head('NO TEAM')
        it = QListWidgetItem('Free Agents')
        it.setData(Qt.UserRole, R.FREE_AGENT)
        self.list.addItem(it)
        self.move_to.blockSignals(True)
        self.move_to.clear()
        for t in self.db.teams:
            self.move_to.addItem(t.full, t.index)
        self.move_to.addItem('Free Agent', R.FREE_AGENT)
        self.move_to.blockSignals(False)
        for i in range(self.list.count()):
            if self.list.item(i).flags() & Qt.ItemIsSelectable:
                self.list.setCurrentRow(i)
                break
        self._dirty(False)

    def _head(self, text):
        h = QListWidgetItem(text.upper())
        h.setFlags(Qt.NoItemFlags)
        h.setForeground(self.palette().mid())
        f = h.font()
        f.setPointSizeF(8.5)
        f.setBold(True)
        h.setFont(f)
        self.list.addItem(h)

    def _filter(self, text):
        t = text.lower().strip()
        hits = set()
        if t and self.db:
            hits = {p.team for p in self.db.players if t in p.name.lower()}
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.flags() & Qt.ItemIsSelectable:
                idx = it.data(Qt.UserRole)
                it.setHidden(bool(t) and t not in it.text().lower() and idx not in hits)
        if self.team is not None:
            self._fill_roster()

    def _team_picked(self, cur, _prev):
        if cur is None or not (cur.flags() & Qt.ItemIsSelectable) or not self.db:
            return
        idx = cur.data(Qt.UserRole)
        self.team = self.db.teams[idx] if idx != R.FREE_AGENT else None
        self._busy = True
        editable = self.team is not None
        for w, v in ((self.city, self.team.city if editable else ''), (self.tname, self.team.name if editable else ''),
                     (self.short, self.team.short if editable else '')):
            w.setText(v)
            w.setEnabled(editable)
        self._busy = False
        self._team_idx = idx
        self._fill_roster()

    def _fill_roster(self):
        idx = getattr(self, '_team_idx', None)
        if idx is None:
            return
        q = self.search.text().lower().strip()
        players = self.db.roster(idx)
        if q and not (self.team and q in self.team.full.lower()):
            players = [p for p in players if q in p.name.lower()] or players
        self.title.set(self.db.team_name(idx), [self.team.level() if self.team else 'Unsigned'])
        self.roster.setRowCount(len(players))
        for r, p in enumerate(players):
            name = QTableWidgetItem(p.name)
            name.setData(Qt.UserRole, p.i)
            self.roster.setItem(r, 0, name)
            self.roster.setItem(r, 1, NumItem(str(p.bits('jersey'))))
            self.roster.setItem(r, 2, QTableWidgetItem(R.POSITIONS[p.pos] if p.pos < len(R.POSITIONS) else '?'))
            self.roster.setItem(r, 3, QTableWidgetItem(f"{'RLS'[min(p.bits('bats'), 2)]}/{'RL'[p.bits('throws')]}"))
            self.roster.setItem(r, 4, NumItem(str(p.rating('RANK'))))
        pitchers = sum(p.pitcher for p in players)
        self.count.setText(f'{len(players)} players · {pitchers} pitchers · {len(players) - pitchers} position players')
        if players:
            self.roster.selectRow(0)
        else:
            self.player = None
            self.right.setEnabled(False)

    def _sort(self, col):
        order = Qt.DescendingOrder if col == 4 else Qt.AscendingOrder
        if getattr(self, '_sorted', None) == (col, order):
            order = Qt.AscendingOrder if order == Qt.DescendingOrder else Qt.DescendingOrder
        self._sorted = (col, order)
        self.roster.sortItems(col, order)

    def _player_picked(self):
        if self._busy:
            return
        rows = self.roster.selectionModel().selectedRows()
        if not rows:
            return
        it = self.roster.item(rows[0].row(), 0)
        if it is None:
            return
        p = self.db.players[it.data(Qt.UserRole)]
        self.player = p
        self.right.setEnabled(True)
        self._busy = True
        self.ptitle.set(p.name, [f'#{p.bits("jersey")}', R.POSITIONS[p.pos] if p.pos < len(R.POSITIONS) else '?',
                                 f'OVR {p.rating("RANK")}'])
        self.first.setText(p.first)
        self.last.setText(p.last)
        self.pos.setCurrentIndex(min(p.pos, len(R.POSITIONS) - 1))
        self.number.setValue(p.bits('jersey'))
        self.bats.setCurrentIndex(min(p.bits('bats'), 2))
        self.throws.setCurrentIndex(p.bits('throws'))
        self.height.setValue(max(60, min(90, p.bits('height'))))
        j = self.move_to.findData(p.team)
        self.move_to.setCurrentIndex(j if j >= 0 else self.move_to.count() - 1)
        # pitchers and hitters see the ratings that matter to them, laid out two to a row
        while self.rgrid.count():
            w = self.rgrid.takeAt(0).widget()
            if w:
                w.hide()
        shown = [f for f, _t, hit, pit in R.RATINGS if (pit if p.pitcher else hit)]
        for n, f in enumerate(shown):
            s = self.spins[f]
            s.setValue(min(125, p.rating(f)))
            s.show()
            self.rgrid.addWidget(s, n, 0)
        self.rgrid.setRowStretch(len(shown), 1)
        self._busy = False
        if self.side.currentIndex() == 1:
            self._show_face()

    def _gear_page(self):
        w = panel()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(12)
        self.gtitle = SectionTitle('Gear')
        lay.addWidget(self.gtitle)
        lay.addWidget(label('What this player wears. Catcher gear only shows on catchers.', 'Sub', wrap=True))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet('QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }')
        inner = QWidget()
        self.ggrid = QGridLayout(inner)
        self.ggrid.setContentsMargins(0, 0, 4, 0)
        self.ggrid.setHorizontalSpacing(10)
        self.ggrid.setVerticalSpacing(6)
        self.gear = {}
        for r, (field, t, text) in enumerate(R.SLOTS):
            self.ggrid.addWidget(label(text, 'Sub'), r, 0)
            c = QComboBox()
            c.setMinimumWidth(180)
            c.currentIndexChanged.connect(self._gear_edited)
            self.ggrid.addWidget(c, r, 1)
            self.gear[field] = c
        self.ggrid.setColumnStretch(1, 1)
        self.ggrid.setRowStretch(len(R.SLOTS), 1)
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)
        return w

    def _fill_gear_combos(self):
        self.equipment = None
        try:
            if R.EQUIPMENT in self.main.game.file_set():
                self.equipment = R.Equipment(self.main.current_file(R.EQUIPMENT))
        except Exception:
            self.equipment = None
        for field, t, _text in R.SLOTS:
            c = self.gear[field]
            c.blockSignals(True)
            c.clear()
            if self.equipment:
                c.addItem('None', 0)
                for st, lab in self.equipment.choices(t):
                    if st:
                        c.addItem(lab, st)
            c.blockSignals(False)

    def _show_gear(self):
        p = self.player
        if p is None or not self.equipment:
            return
        self._busy = True
        self.gtitle.set(p.name, ['Gear'])
        catcher = p.pos == 1
        for r, (field, t, _text) in enumerate(R.SLOTS):
            c = self.gear[field]
            v = p.gear(field)
            j = c.findData(v)
            if j < 0:
                c.addItem(self.equipment.label(t, v), v)
                j = c.count() - 1
            c.setCurrentIndex(j)
            on = catcher or field not in ('CATCHER_MASK', 'CHEST_PROTECTOR', 'CATCHER_SHN_GRD')
            c.setVisible(on)
            self.ggrid.itemAtPosition(r, 0).widget().setVisible(on)
        self._busy = False

    def _gear_edited(self, *_):
        if self._busy or self.player is None:
            return
        changes = {f: c.currentData() for f, c in self.gear.items() if c.currentData() is not None
                   and c.currentData() != self.player.gear(f)}
        if changes:
            self.db.set_player(self.player, gear=changes)
            self._dirty(True)

    def _side(self, i):
        self.side.setCurrentIndex(i)
        if i == 1:
            self._show_gear()
        elif i == 2:
            self._show_face()

    def _show_face(self):
        p = self.player
        if p is None:
            return
        rel = R.find_head(self.main.game.file_set(), p.first, p.last)
        t = self.main.tex(rel) if rel else None
        if t is None or not t.entries:
            self.face.cur = None
            self.face._enable(False)
            self.face.title.setText(p.name.upper())
            self.face.view.set_image(None, 'No face found')
            self.face.note.setText('No face texture found for this player. Generic players use the shared face '
                                   'parts in the player creator.')
            return
        self.face.note.setText('Drop a PNG on the preview to replace this face. Export first to get the exact layout.')
        self.face.show_entry(rel, t, 0)
        self.face.title.setText(f'{p.name.upper()} · FACE')

    def refresh_overrides(self):
        if self.side.currentIndex() == 1:
            self._show_gear()
        elif self.side.currentIndex() == 2:
            self._show_face()

    # ---- edits
    def _team_edited(self, *_):
        if self._busy or self.team is None:
            return
        self.db.set_team(self.team, city=self.city.text(), name=self.tname.text(), short=self.short.text())
        it = self.list.currentItem()
        if it:
            it.setText(self.team.full)
        self.title.set(self.team.full, [self.team.level()])
        self._dirty(True)

    def _player_edited(self, *_):
        if self._busy or self.player is None:
            return
        p = self.player
        moved = self.move_to.currentData() != p.team
        ratings = {f: s.value() for f, s in self.spins.items() if s.isVisible() and s.value() != p.rating(f)}
        bits = {}
        if self.number.value() != p.bits('jersey'):
            bits['jersey'] = bits['jersey2'] = self.number.value()
        if self.bats.currentIndex() != p.bits('bats'):
            bits['bats'] = self.bats.currentIndex()
        if self.throws.currentIndex() != p.bits('throws'):
            bits['throws'] = self.throws.currentIndex()
        if self.height.value() != p.bits('height'):
            bits['height'] = self.height.value()
        try:
            self.db.set_player(p, first=self.first.text(), last=self.last.text(), pos=self.pos.currentIndex(),
                               team=self.move_to.currentData(), ratings=ratings, bits=bits)
        except ValueError as x:
            QMessageBox.information(self, 'No Room', str(x))
            self._busy = True
            self.move_to.setCurrentIndex(self.move_to.findData(p.team))
            self._busy = False
            return
        for f, v in ratings.items():
            p.att.fields[f] = (p.att.fields[f][0], int(v).to_bytes(1, 'little'))
        self._dirty(True)
        r = self.roster.currentRow()
        if moved:
            self.main.toast(f'{p.name} moved to {self.db.team_name(p.team)}. Save to keep it.')
            self._fill_roster()
        elif r >= 0:
            self._busy = True
            self.roster.item(r, 0).setText(p.name)
            self.roster.item(r, 1).setText(str(p.bits('jersey')))
            self.roster.item(r, 2).setText(R.POSITIONS[p.pos])
            self.roster.item(r, 3).setText(f"{'RLS'[min(p.bits('bats'), 2)]}/{'RL'[p.bits('throws')]}")
            self.roster.item(r, 4).setText(str(p.rating('RANK')))
            self.ptitle.set(p.name, [f'#{p.bits("jersey")}', R.POSITIONS[p.pos], f'OVR {p.rating("RANK")}'])
            self._busy = False

    def _dirty(self, on):
        self.b_save.setEnabled(on)

    # ---- saving
    def save(self):
        if not self.db or not self.db.dirty():
            return
        mod = self.main.active_mod(ask=True)
        if not mod:
            return
        sources = {}
        for base in (R.ROSTERS, R.PLAYERS):
            for rel in R.variants(base):
                if rel in self.main.game.file_set():
                    src = self.main.current_file(rel)
                    if os.path.exists(src):
                        sources[rel] = src
        import tempfile
        tmpdir = tempfile.mkdtemp(prefix='mts_')

        def out(rel, data):
            tmp = os.path.join(tmpdir, os.path.basename(rel))
            with open(tmp, 'wb') as f:
                f.write(data)
            self.main.lib.add_file(mod, rel, tmp)
        try:
            n = self.db.write(sources, out)
        except Exception as x:
            QMessageBox.warning(self, 'Could Not Save', str(x))
            return
        self.db.edits_t.clear()
        self.db.edits_p.clear()
        self.db.rosters.clear()
        self._dirty(False)
        self.main.changed(f'Rosters saved into {mod.name} ({n} files). Apply to use them.')

    def reset(self):
        if self.db and self.db.dirty():
            r = QMessageBox.question(self, 'Throw Away Changes?', 'Drop the roster changes you haven’t saved?')
            if r != QMessageBox.Yes:
                return
        mod = self.main.active_mod()
        removed = 0
        if mod:
            for base in (R.ROSTERS, R.PLAYERS):
                for rel in R.variants(base):
                    p = os.path.join(mod.path, 'romfs', *rel.split('/'))
                    if os.path.exists(p):
                        os.remove(p)
                        removed += 1
        self.db = None
        if removed:
            self.main.changed(f'Rosters in {mod.name} are back to the game’s.')
        self.load()
