"""The catalog screens: Uniforms, Bats, Stadiums, Scoreboards, Menus & Loading Screens."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
                               QScrollArea, QSplitter, QVBoxLayout, QWidget)

from .. import catalog
from .common import FilterBar, Inspector, SectionTitle, TextureGrid, button, header, panel


class CollectionPage(QWidget):
    """Left: what to pick (teams, parks...). Middle: optional variants and the texture grid. Right: the inspector."""
    TITLE = ''
    SUB = ''
    SEARCH = 'Find'
    MODE_HIDES_INSPECTOR = ()   # modes that use the whole width

    def __init__(self, main):
        super().__init__()
        self.setObjectName('Page')
        self.main = main
        self.loaded = False
        self.key = None
        self.packs = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(18)
        self.export_btn = button('Export All Shown', on_click=self.export_shown)
        outer.addWidget(header(self.TITLE, self.SUB, [self.export_btn]))
        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(16)
        # left
        left = panel()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(10, 10, 10, 10)
        ll.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText(self.SEARCH)
        self.search.setAccessibleName(self.SEARCH)
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter_list)
        ll.addWidget(self.search)
        self.list = QListWidget()
        self.list.setStyleSheet('QListWidget { border: none; padding: 0; background: transparent; }')
        self.list.currentItemChanged.connect(self._picked)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        ll.addWidget(self.list, 1)
        left.setMinimumWidth(220)
        left.setMaximumWidth(300)
        split.addWidget(left)
        # middle
        mid = panel()
        ml = QVBoxLayout(mid)
        ml.setContentsMargins(18, 18, 18, 18)
        ml.setSpacing(12)
        self.mid_title = SectionTitle()
        ml.addWidget(self.mid_title)
        self.variants = QWidget()
        self.vlay = QHBoxLayout(self.variants)
        self.vlay.setContentsMargins(0, 0, 0, 0)
        self.vlay.setSpacing(6)
        vscroll = QScrollArea()
        vscroll.setWidget(self.variants)
        vscroll.setWidgetResizable(True)
        vscroll.setFixedHeight(46)
        vscroll.setFrameShape(QScrollArea.NoFrame)
        vscroll.setStyleSheet('QScrollArea { background: transparent; } QScrollArea > QWidget > QWidget { background: transparent; }')
        self.vscroll = vscroll
        ml.addWidget(vscroll)
        self.filter = FilterBar('Filter textures by name')
        self.filter.changed.connect(lambda _: self._show())
        ml.addWidget(self.filter)
        self.grid = TextureGrid()
        self.grid.picked.connect(self._tex_picked)
        ml.addWidget(self.grid, 1)
        split.addWidget(mid)
        self.inspector = Inspector(main)
        split.addWidget(self.inspector)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setStretchFactor(2, 0)
        split.setSizes([250, 700, 360])
        outer.addWidget(split, 1)
        self.vgroup = QButtonGroup(self)
        self.vgroup.setExclusive(True)

    def add_modes(self, names, widgets):
        """Chips above the grid that switch it for other views (e.g. On a Player, Layout)."""
        from PySide6.QtWidgets import QStackedWidget
        lay = self.grid.parentWidget().layout()
        at = lay.indexOf(self.filter)
        bar = QWidget()
        modes = QHBoxLayout(bar)
        modes.setContentsMargins(0, 0, 0, 0)
        modes.setSpacing(6)
        self.mode_group = QButtonGroup(self)
        for i, text in enumerate(names):
            b = QPushButton(text.replace('&', '&&'))
            b.setObjectName('Chip')
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setChecked(i == 0)
            self.mode_group.addButton(b, i)
            modes.addWidget(b)
        modes.addStretch(1)
        lay.insertWidget(at, bar)
        self.mode_bar = bar
        self.stack = QStackedWidget()
        idx = lay.indexOf(self.grid)
        lay.removeWidget(self.grid)
        self.stack.addWidget(self.grid)
        for w in widgets:
            self.stack.addWidget(w)
        lay.insertWidget(idx, self.stack, 1)
        self.mode_group.idClicked.connect(self._mode)

    def _mode(self, i):
        self.stack.setCurrentIndex(i)
        self.filter.setVisible(i == 0)
        self.export_btn.setVisible(i == 0)
        self.inspector.setVisible(i not in self.MODE_HIDES_INSPECTOR)
        self.mode_changed(i)

    def mode_changed(self, i):
        pass

    def mode(self):
        return self.stack.currentIndex() if hasattr(self, 'stack') else 0

    # subclasses
    def groups(self):
        return []

    def variants_for(self, key):
        """[(variant label, [pack rels])]; one entry means no variant chips."""
        return [('', [key])]

    def title_for(self, key, name):
        return name

    # ---- plumbing
    def activate(self):
        if not self.loaded:
            self.loaded = True
            self.list.clear()
            for group, rows in self.groups():
                h = QListWidgetItem(group)
                h.setFlags(Qt.NoItemFlags)
                h.setForeground(self.palette().mid())
                f = h.font()
                f.setPointSizeF(8.5)
                f.setBold(True)
                f.setLetterSpacing(f.SpacingType.AbsoluteSpacing, 1.2)
                h.setFont(f)
                self.list.addItem(h)
                for key, name in rows:
                    it = QListWidgetItem(name)
                    it.setData(Qt.UserRole, key)
                    self.list.addItem(it)
            for i in range(self.list.count()):
                if self.list.item(i).flags() & Qt.ItemIsSelectable:
                    self.list.setCurrentRow(i)
                    break
        else:
            self._show()

    def _filter_list(self, text):
        t = text.lower()
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.flags() & Qt.ItemIsSelectable:
                it.setHidden(bool(t) and t not in it.text().lower())

    def _picked(self, cur, _prev):
        if cur is None or not (cur.flags() & Qt.ItemIsSelectable):
            return
        self.key = cur.data(Qt.UserRole)
        variants = self.variants_for(self.key)
        for b in self.vgroup.buttons():
            self.vgroup.removeButton(b)
        while self.vlay.count():
            w = self.vlay.takeAt(0).widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        self.vscroll.setVisible(len(variants) > 1)
        for i, (vl, packs) in enumerate(variants):
            b = QPushButton(vl.replace('&', '&&'))
            b.setObjectName('Chip')
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, p=packs, n=vl: self._set_packs(p, n))
            self.vgroup.addButton(b)
            self.vlay.addWidget(b)
            if i == 0:
                b.setChecked(True)
        self.vlay.addStretch(1)
        self._name = cur.text()
        self._set_packs(variants[0][1], variants[0][0] if len(variants) > 1 else '')

    def _set_packs(self, packs, variant):
        self.packs = packs
        title = self.title_for(self.key, self._name) + (f' · {variant}' if variant else '')
        n = sum(len(t.entries) for t in (self.main.tex(r) for r in packs) if t is not None)
        self.mid_title.set(title, [f'{n} textures', f'{len(packs)} pack{"s" if len(packs) != 1 else ""}'])
        self._show()

    def _show(self):
        texs = []
        for rel in self.packs:
            t = self.main.tex(rel)
            if t is not None:
                texs.append((rel, t))
        self.grid.show_packs(texs, self.main.overrides(), self.filter.edit.text(),
                             hide_maps=not self.filter.maps.isChecked())

    def _tex_picked(self, rel, idx):
        t = self.main.tex(rel)
        if t is not None:
            self.inspector.show_entry(rel, t, idx)

    def refresh_overrides(self):
        if self.loaded:
            cur = self.grid.currentRow()
            self._show()
            if 0 <= cur < self.grid.count():
                self.grid.setCurrentRow(cur)

    def export_shown(self):
        from PySide6.QtWidgets import QFileDialog
        import os
        folder = QFileDialog.getExistingDirectory(self, 'Export Textures To', self.main.last_dir())
        if not folder:
            return
        self.main.remember_dir(folder)
        packs = [(rel, self.main.tex(rel)) for rel in self.packs]

        def work(job):
            from .common import _export_pack
            n = 0
            for rel, t in packs:
                if t is None:
                    continue
                out = os.path.join(folder, *rel.split('/')[-3:])
                os.makedirs(out, exist_ok=True)
                n += _export_pack(t, out, job)
            return n
        self.main.run(work, 'Exporting textures...', lambda n: self.main.toast(f'Exported {n} textures to {folder}'))


class UniformsPage(CollectionPage):
    TITLE = 'Uniforms'
    SUB = 'Pick a team and a uniform, then swap any part with your own PNG. Export a part first to get the exact template.'
    SEARCH = 'Find a team'
    MODE_HIDES_INSPECTOR = (2, 3)

    def __init__(self, main):
        super().__init__(main)
        from .playerpreview import PlayerPreview
        from .schedule import ScheduleEditor, TeamUniforms, UniformList
        self.preview = PlayerPreview(main)
        data = TeamUniforms(main)
        self.schedule = ScheduleEditor(main, data)
        self.unilist = UniformList(main, data)
        self.add_modes(('Textures', 'On a Player', 'Schedule', 'Uniform List'), [self.preview, self.schedule, self.unilist])
        self._team_shown = None

    def _folder(self):
        return self.packs[0].rsplit('/', 1)[0] if getattr(self, 'packs', None) else None

    def mode_changed(self, i):
        if i == 1 and self._folder():
            self.preview.show_uniform(self._folder())
        elif i in (2, 3) and self.key:
            self.vscroll.setVisible(False)
            league, team = self.key
            self.mid_title.set(self._name, [])
            (self.schedule if i == 2 else self.unilist).show_team(f'{league}/{team}', self._name)
        if i in (0, 1) and self.key:
            self.vscroll.setVisible(len(self.variants_for(self.key)) > 1)

    def _set_packs(self, packs, variant):
        super()._set_packs(packs, variant)
        if self.mode():
            self.mode_changed(self.mode())

    def refresh_overrides(self):
        super().refresh_overrides()
        if self.loaded and self.stack.currentIndex() == 1:
            self.preview.refresh()

    def groups(self):
        out = []
        for g, rows in catalog.teams(self.main.game):
            out.append((g, [((league, code), name) for code, name, league in rows]))
        return out

    def variants_for(self, key):
        league, team = key
        rows = catalog.uniforms(self.main.game, league, team)
        return [(name, packs) for _, name, packs in rows] or [('', [])]


class StadiumsPage(CollectionPage):
    TITLE = 'Stadiums'
    SUB = 'Every sign, wall pad and banner in each park. Ads live in the big color sheets; glow maps end in _emissive.'
    SEARCH = 'Find a ballpark'
    MODE_HIDES_INSPECTOR = (1,)

    def __init__(self, main):
        super().__init__(main)
        from .stadium3d import StadiumView
        self.view3d = StadiumView(main)
        self.add_modes(('Signs & Textures', '3D View'), [self.view3d])

    def mode_changed(self, i):
        self.vscroll.setVisible(i == 0 and self.key is not None and len(self.variants_for(self.key)) > 1)
        if i == 1 and self.key:
            self.view3d.show_park(self.key)

    def _set_packs(self, packs, variant):
        super()._set_packs(packs, variant)
        if self.mode() == 1:
            self.mode_changed(1)

    def refresh_overrides(self):
        super().refresh_overrides()
        if self.loaded and self.mode() == 1:
            self.view3d.refresh()

    def groups(self):
        return [(g, [(path, name) for code, name, path in rows]) for g, rows in catalog.parks(self.main.game)]

    def variants_for(self, key):
        packs = catalog.packs_in(self.main.game, key)
        order = {'TEXTURES_COLOR.TEX': 0, 'TEXTURES_NORMAL.TEX': 3, 'FLUX_LIGHTMAPS.TEX': 4, 'FLUX_LIGHTMAPS_CLOSED.TEX': 5,
                 'GRASSPATTERNORTHO.TEX': 2}
        packs.sort(key=lambda p: (order.get(p.rsplit('/', 1)[1], 1), p))
        nice = {'TEXTURES_COLOR.TEX': 'Signs & Surfaces', 'GRASSPATTERNORTHO.TEX': 'Grass Pattern',
                'FLUX_LIGHTMAPS.TEX': 'Lightmaps', 'FLUX_LIGHTMAPS_CLOSED.TEX': 'Lightmaps (Roof Closed)',
                'TEXTURES_NORMAL.TEX': 'Normal Maps'}
        return [(nice.get(p.rsplit('/', 1)[1], p.rsplit('/', 1)[1][:-4].replace('_', ' ').title()), [p]) for p in packs] \
            or [('', [])]


class _ListOfPacks(CollectionPage):
    ROWS = staticmethod(lambda game: [])
    GROUP = ''

    def groups(self):
        return [(self.GROUP, [(rel, name) for name, rel in type(self).ROWS(self.main.game)])]


class ScoreboardsPage(_ListOfPacks):
    TITLE = 'Scoreboards'
    SUB = "Scorebug themes, broadcast graphics and every other in-game overlay. Reskin any piece; moving pieces comes " \
          "with Layout."
    SEARCH = 'Find a theme'
    MODE_HIDES_INSPECTOR = (1,)

    def __init__(self, main):
        super().__init__(main)
        from .layouteditor import LayoutEditor
        self.layout_editor = LayoutEditor(main)
        self.add_modes(('Textures', 'Layout'), [self.layout_editor])

    def _has_layout(self):
        return bool(self.packs) and self.packs[0][:-4] + '.NSW' in self.main.game.file_set()

    def _set_packs(self, packs, variant):
        super()._set_packs(packs, variant)
        has = self._has_layout()
        self.mode_bar.setVisible(has)
        if not has and self.mode():
            self.mode_group.button(0).setChecked(True)
            self._mode(0)
        elif self.mode() == 1:
            self.layout_editor.open(self.packs[0])

    def mode_changed(self, i):
        if i == 1 and self.packs:
            self.layout_editor.open(self.packs[0])

    def groups(self):
        return [(g, [(rel, name) for name, rel in rows]) for g, rows in catalog.scoreboard_groups(self.main.game)]


class MenusPage(_ListOfPacks):
    TITLE = 'Menus & Loading Screens'
    SUB = 'Loading screens, menu art, fonts, headshots, the uniform and player creators, sky textures and the ' \
          'player action shots. Card art and announcements are WEBP files under Game Files › CROSS/LIVE.'
    SEARCH = 'Find a pack'

    def groups(self):
        return [(g, [(rel, name) for name, rel in rows]) for g, rows in catalog.menu_groups(self.main.game)]


class BatsPage(_ListOfPacks):
    TITLE = 'Bats'
    SUB = 'The skins painted on bats in game, plus grips and barrel stamps. Each skin is a 1024×256 strip.'
    SEARCH = 'Find a bat pack'
    GROUP = 'BATS'
    ROWS = staticmethod(catalog.bat_packs)
