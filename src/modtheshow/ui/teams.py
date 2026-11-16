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
                               'another club. Saves go into your mod like everything else.', [self.b_reset, self.b_save]))
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
        self.roster = table(['Player', 'Pos', 'OVR', 'Team'])
        h = self.roster.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in (1, 2, 3):
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
        form.addWidget(self.pos, 1, 0)
        self.move_to = QComboBox()
        self.move_to.setToolTip('Beta: lineups and rotations aren’t rebuilt for you. After moving players, set them '
                                'in the game’s own roster screens.')
        self.move_to.currentIndexChanged.connect(self._player_edited)
        form.addWidget(self.move_to, 1, 1)
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
        self.rgrid.setVerticalSpacing(6)
        self.spins = {}
        for field, text, _h, _p in R.RATINGS:
            s = QSpinBox()
            s.setRange(0, 125)
            s.setPrefix(text + '   ')
            s.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
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
        for i, text in enumerate(('Player', 'Face')):
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
            self.roster.setItem(r, 1, QTableWidgetItem(R.POSITIONS[p.pos] if p.pos < len(R.POSITIONS) else '?'))
            self.roster.setItem(r, 2, NumItem(str(p.rating('RANK'))))
            self.roster.setItem(r, 3, QTableWidgetItem(self.db.teams[p.team].short if p.team < len(self.db.teams)
                                                       else 'FA'))
        pitchers = sum(p.pitcher for p in players)
        self.count.setText(f'{len(players)} players · {pitchers} pitchers · {len(players) - pitchers} position players')
        if players:
            self.roster.selectRow(0)
        else:
            self.player = None
            self.right.setEnabled(False)

    def _sort(self, col):
        order = Qt.DescendingOrder if col == 2 else Qt.AscendingOrder
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
        self.ptitle.set(p.name, [R.POSITIONS[p.pos] if p.pos < len(R.POSITIONS) else '?', f'OVR {p.rating("RANK")}'])
        self.first.setText(p.first)
        self.last.setText(p.last)
        self.pos.setCurrentIndex(min(p.pos, len(R.POSITIONS) - 1))
        j = self.move_to.findData(p.team)
        self.move_to.setCurrentIndex(j if j >= 0 else self.move_to.count() - 1)
        # pitchers and hitters see the ratings that matter to them, laid out two to a row
        while self.rgrid.count():
            w = self.rgrid.takeAt(0).widget()
            if w:
                w.hide()
        shown = [f for f, _t, hit, pit in R.RATINGS if (pit if p.pitcher else hit)]
        if len(shown) % 2:
            shown = shown[:-1]
        for n, f in enumerate(shown):
            s = self.spins[f]
            s.setValue(p.rating(f))
            s.show()
            self.rgrid.addWidget(s, n // 2, n % 2)
        self.rgrid.setRowStretch(len(shown) // 2, 1)
        self._busy = False
        if self.side.currentIndex() == 1:
            self._show_face()

    def _side(self, i):
        self.side.setCurrentIndex(i)
        if i == 1:
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
        self.db.set_player(p, first=self.first.text(), last=self.last.text(), pos=self.pos.currentIndex(),
                           team=self.move_to.currentData(), ratings=ratings)
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
            self.roster.item(r, 1).setText(R.POSITIONS[p.pos])
            self.roster.item(r, 2).setText(str(p.rating('RANK')))
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
