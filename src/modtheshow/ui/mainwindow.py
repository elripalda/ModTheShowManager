import os
from collections import OrderedDict

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow,
                               QMessageBox, QProgressBar, QPushButton, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)

from .. import __version__, game as gamemod
from ..mods import Library
from ..texlib import Tex
from . import theme, workers
from .common import PickModDialog, button, label
from .gamefiles import GameFilesPage
from .home import HomePage
from .models import ModelsPage
from .sounds import SoundsPage
from .teams import TeamsPage
from .modspage import ModsPage
from .plugins import PluginsPage
from .settingspage import SettingsPage
from .pages import BatsPage, MenusPage, ScoreboardsPage, StadiumsPage, UniformsPage

NAV = [('START', [('Home', HomePage), ('Mods', ModsPage)]),
       ('CREATE', [('Uniforms', UniformsPage), ('Bats', BatsPage), ('Stadiums', StadiumsPage),
                   ('Scoreboards', ScoreboardsPage), ('Menus & Loading Screens', MenusPage), ('3D Models', ModelsPage),
                   ('Sounds', SoundsPage), ('Teams & Rosters', TeamsPage)]),
       ('TOOLS', [('Game Files', GameFilesPage), ('Code Plugins', PluginsPage), ('Settings', SettingsPage)])]


class Setup(QWidget):
    """First run: find the game."""

    def __init__(self, main):
        super().__init__()
        self.main = main
        self.setObjectName('Page')
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(18)
        logo = QLabel()
        logo.setPixmap(MainWindow.logo(360))
        logo.setAlignment(Qt.AlignCenter)
        lay.addWidget(logo)
        t = label('Mods for the MLB The Show 26 PC port', 'H2')
        t.setAlignment(Qt.AlignCenter)
        lay.addWidget(t, 0, Qt.AlignCenter)
        steps = QHBoxLayout()
        steps.setSpacing(12)
        from .home import Step
        for num, title, text in (
                ('1', 'Install the game', 'Run MLBTS-Setup.exe from the mlbts-native project. It builds the PC port '
                                          'from your own copy of the game.'),
                ('2', 'Point to it', 'Pick the folder the setup installed to. It is the one with mlb.exe and a game '
                                     'folder in it.'),
                ('3', 'Start modding', 'Your mods go in a mods folder there. The manager backs up every file before '
                                       'a mod touches it.')):
            st = Step(num, title, text)
            st.setFixedWidth(300)
            steps.addWidget(st)
        box = QWidget()
        box.setLayout(steps)
        lay.addWidget(box, 0, Qt.AlignCenter)
        b = button('Find My Game Folder', True, self.pick)
        b.setMinimumWidth(240)
        lay.addWidget(b, 0, Qt.AlignCenter)

    def pick(self):
        path = QFileDialog.getExistingDirectory(self, 'MLB The Show 26 Folder', r'C:\Games')
        if not path:
            return
        if not gamemod.is_game_folder(path):
            QMessageBox.warning(self, 'Not the Game Folder',
                                'That folder has no mlb.exe and game\\romfs. Pick the folder MLBTS-Setup installed to.')
            return
        self.main.open_game(path)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Mod the Show Manager')
        self.setWindowIcon(QIcon(os.path.join(theme.ASSETS, 'icon.ico')))
        self.resize(1440, 900)
        self.setMinimumSize(1100, 700)
        self.settings = gamemod.load_settings()
        self.game = None
        self.lib = None
        self._tex = OrderedDict()
        self._winners = None
        self.pages = {}
        self.update_info = None
        root = QWidget()
        root.setObjectName('Root')
        self.setCentralWidget(root)
        self.root_lay = QHBoxLayout(root)
        self.root_lay.setContentsMargins(0, 0, 0, 0)
        self.root_lay.setSpacing(0)
        path = self.settings.get('game') if gamemod.is_game_folder(self.settings.get('game')) else gamemod.detect()
        if path:
            self.open_game(path)
        else:
            self.root_lay.addWidget(Setup(self))

    @staticmethod
    def logo(width):
        """The logo, recoloured dark on the light theme (the art is white)."""
        pm = QPixmap(os.path.join(theme.ASSETS, 'logo.png')).scaledToWidth(width, Qt.SmoothTransformation)
        if theme.is_light():
            from PySide6.QtGui import QColor, QPainter
            qp = QPainter(pm)
            qp.setCompositionMode(QPainter.CompositionMode_SourceIn)
            qp.fillRect(pm.rect(), QColor(theme.TEXT))
            qp.end()
        return pm

    def retheme(self):
        """Theme or text size changed: restyle and rebuild the window where it was."""
        from PySide6.QtWidgets import QApplication
        theme.apply(QApplication.instance(), self.settings.get('theme', 'Dark'), self.settings.get('text_scale', 1.0))
        if self.game:
            self.cache_clear()
            self.open_game(self.game.root, show='Settings')

    def check_updates(self):
        if not self.settings.get('auto_update', True) or self.update_info is not None:
            return
        from .. import updater
        job = workers.Job(lambda j: updater.check(__version__))

        def done(info):
            if info:
                self.update_info = info
                self.toast(f'Version {info["version"]} is out. Settings has the update.')
        job.sig.done.connect(done)
        job.sig.failed.connect(lambda tb: None)
        self._upd_job = job
        workers.start(job)

    # ---- building
    def open_game(self, path, show='Home'):
        while self.root_lay.count():
            w = self.root_lay.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.settings['game'] = path
        self.save_settings()
        self.game = gamemod.Game(path)
        self.game.index()
        self.lib = Library(self.game)
        self.root_lay.addWidget(self._sidebar())
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        rl.addWidget(self._strip())
        self.stack = QStackedWidget()
        rl.addWidget(self.stack, 1)
        self.root_lay.addWidget(right, 1)
        for _, items in NAV:
            for name, cls in items:
                if cls:
                    page = cls(self)
                    self.pages[name] = page
                    self.stack.addWidget(page)
        self.pages['Mods'].set_library(self.lib)
        self.pages['Mods'].applied.connect(self.update_strip)
        self._fill_mods_combo()
        self.toast_box = QLabel(self.centralWidget())
        self.toast_box.setObjectName('Toast')
        self.toast_box.setWordWrap(True)
        self.toast_box.setAlignment(Qt.AlignCenter)
        self.toast_box.hide()
        self.update_strip()
        self.go(show)
        QTimer.singleShot(1500, self.check_updates)

    def _sidebar(self):
        side = QWidget()
        side.setObjectName('Sidebar')
        side.setFixedWidth(248)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(16, 26, 16, 18)
        lay.setSpacing(4)
        logo = QLabel()
        logo.setPixmap(self.logo(150))
        logo.setContentsMargins(6, 0, 0, 18)
        lay.addWidget(logo)
        self.nav = QButtonGroup(self)
        self.nav_buttons = {}
        for group, items in NAV:
            lay.addSpacing(8)
            g = label(group, 'Group')
            g.setContentsMargins(0, 0, 0, 4)
            lay.addWidget(g)
            for name, cls in items:
                b = QPushButton(name.replace('&', '&&'))
                b.setObjectName('Nav')
                b.setCheckable(True)
                b.setCursor(Qt.PointingHandCursor)
                if cls is None:
                    b.setEnabled(False)
                    b.setToolTip('Coming once the game\'s formats are cracked')
                    soon = QLabel('Soon', b)
                    soon.setStyleSheet(f'color: {theme.MUTED}; font-size: 11px; background: transparent;')
                    bl = QHBoxLayout(b)
                    bl.setContentsMargins(0, 0, 10, 0)
                    bl.addStretch(1)
                    bl.addWidget(soon)
                else:
                    b.clicked.connect(lambda _=False, n=name: self.go(n))
                    self.nav.addButton(b)
                self.nav_buttons[name] = b
                lay.addWidget(b)
        lay.addStretch(1)
        ver = label(f'Version {__version__} · Ripalda', 'Sub')
        ver.setContentsMargins(10, 4, 4, 0)
        ver.setStyleSheet('font-size: 11px;')
        lay.addWidget(ver)
        return side

    def _strip(self):
        strip = QFrame()
        strip.setObjectName('Strip')
        strip.setFixedHeight(64)
        lay = QHBoxLayout(strip)
        lay.setContentsMargins(28, 0, 28, 0)
        lay.setSpacing(12)
        bug = QFrame()
        bug.setObjectName('Scorebug')
        bug.setFixedHeight(38)
        bl = QHBoxLayout(bug)
        bl.setContentsMargins(0, 0, 4, 0)
        bl.setSpacing(0)
        bl.addWidget(label('MLB THE SHOW 26', 'StripTitle'))
        self.cells = {}
        for key in ('MODS', 'ON', 'NOT APPLIED'):
            cell = QFrame()
            cell.setObjectName('ScoreCell')
            cl = QHBoxLayout(cell)
            cl.setContentsMargins(14, 0, 14, 0)
            cl.setSpacing(8)
            cl.addWidget(label(key, 'StripLabel'))
            v = label('0', 'StripValue')
            cl.addWidget(v)
            self.cells[key] = v
            bl.addWidget(cell)
        bug.setMinimumWidth(bug.sizeHint().width() + 40)
        lay.addWidget(bug)
        lay.addStretch(1)
        self.progress = QProgressBar()
        self.progress.setFixedWidth(160)
        self.progress.hide()
        lay.addWidget(self.progress)
        lay.addWidget(label('Saving To', 'StripLabel'))
        self.mods_combo = QComboBox()
        self.mods_combo.setMinimumWidth(220)
        self.mods_combo.setAccessibleName('Mod that new changes are saved to')
        self.mods_combo.activated.connect(self._combo_picked)
        lay.addWidget(self.mods_combo)
        self.apply_btn = button('Apply Changes', True, self.apply)
        self.apply_btn.setToolTip('Put the mods that are switched on into the game')
        lay.addWidget(self.apply_btn)
        play = button('Launch Game', on_click=self.launch)
        lay.addWidget(play)
        return strip

    # ---- navigation
    def go(self, name):
        page = self.pages[name]
        changed = self.stack.currentWidget() is not page
        self.stack.setCurrentWidget(page)
        self.nav_buttons[name].setChecked(True)
        if changed and theme.MOTION:
            from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation
            a = QPropertyAnimation(page, b'pos', self)
            a.setDuration(170)
            a.setStartValue(QPoint(0, 14))
            a.setEndValue(QPoint(0, 0))
            a.setEasingCurve(QEasingCurve.OutCubic)
            a.start(QPropertyAnimation.DeleteWhenStopped)
            self._page_anim = a
        if hasattr(page, 'activate'):
            QTimer.singleShot(0, page.activate)

    def change_game(self):
        path = QFileDialog.getExistingDirectory(self, 'MLB The Show 26 Folder', self.game.root if self.game else '')
        if path and gamemod.is_game_folder(path):
            self.cache_clear()
            self.open_game(path)
        elif path:
            QMessageBox.warning(self, 'Not the Game Folder', 'That folder has no mlb.exe and game\\romfs.')

    # ---- shared services for the pages
    def save_settings(self):
        gamemod.save_settings(self.settings)

    def last_dir(self):
        return self.settings.get('last_dir') or os.path.expanduser('~')

    def remember_dir(self, path):
        self.settings['last_dir'] = path if os.path.isdir(path) else os.path.dirname(path)
        self.save_settings()

    def tex(self, rel):
        """Texture pack, read from the untouched original, cached."""
        key = rel.upper()
        if key in self._tex:
            self._tex.move_to_end(key)
            return self._tex[key]
        try:
            t = Tex(self.game.original(rel))
        except Exception:
            return None
        self._tex[key] = t
        while len(self._tex) > 10:
            self._tex.popitem(last=False)
        return t

    def cache_clear(self):
        self._tex.clear()
        self._winners = None

    def _win(self):
        if self._winners is None:
            self._winners = self.lib.winners()
        return self._winners

    def overrides(self):
        tex, _ = self._win()
        return {pack: {n: png for n, (_m, png) in names.items()} for pack, names in tex.items()}

    def mod_png(self, rel, name):
        tex, _ = self._win()
        return tex.get(rel.upper(), {}).get(name)

    def mod_file(self, rel):
        _, files = self._win()
        return files.get(rel.upper())

    def current_file(self, rel):
        """Where a whole-file edit should start from: the active mod's copy, else whatever mod wins, else the game."""
        mod = self.active_mod()
        if mod:
            own = os.path.join(mod.path, 'romfs', *rel.upper().split('/'))
            if os.path.exists(own):
                return own
        hit = self.mod_file(rel)
        return hit[1] if hit and os.path.exists(hit[1]) else self.game.original(rel)

    def save_file(self, rel, write, message):
        """Write a whole file into the active mod. write(path) produces it."""
        import tempfile
        mod = self.active_mod(ask=True)
        if not mod:
            return False
        tmp = os.path.join(tempfile.mkdtemp(prefix='mts_'), os.path.basename(rel))
        write(tmp)
        self.lib.add_file(mod, rel, tmp)
        self.changed(message.format(mod=mod.name))
        return True

    def active_mod(self, ask=False):
        folder = self.settings.get('active_mod')
        for m in self.lib.list():
            if m.folder == folder:
                return m
        if not ask:
            return None
        dlg = PickModDialog(self, self.lib.list())
        if not dlg.exec() or not dlg.choice:
            return None
        kind, val = dlg.choice
        if kind == 'new':
            m = self.lib.create(val, self.settings.get('author', ''))
        else:
            m = next(x for x in self.lib.list() if x.folder == val)
        self.set_active_mod(m.folder)
        return m

    def set_active_mod(self, folder):
        self.settings['active_mod'] = folder
        self.save_settings()
        self._fill_mods_combo()
        self.toast('New changes now go into ' + next((m.name for m in self.lib.list() if m.folder == folder), folder))

    def _fill_mods_combo(self):
        self.mods_combo.blockSignals(True)
        self.mods_combo.clear()
        cur = self.settings.get('active_mod')
        sel = -1
        for i, m in enumerate(self.lib.list()):
            self.mods_combo.addItem(m.name, m.folder)
            if m.folder == cur:
                sel = i
        self.mods_combo.addItem('New Mod…', '__new__')
        if sel < 0:
            self.mods_combo.insertItem(0, 'Pick a mod', None)
            sel = 0
        self.mods_combo.setCurrentIndex(sel)
        self.mods_combo.blockSignals(False)

    def _combo_picked(self, i):
        data = self.mods_combo.itemData(i)
        if data == '__new__':
            m = self.pages['Mods'].new_mod()
            if not m:
                self._fill_mods_combo()
        elif data:
            self.set_active_mod(data)

    def changed(self, message=''):
        """A mod's contents changed."""
        self._winners = None
        self.pages['Mods'].refresh()
        cur = self.stack.currentWidget()
        if hasattr(cur, 'refresh_overrides'):
            cur.refresh_overrides()
        self._fill_mods_combo()
        self.update_strip()
        if message:
            self.toast(message)

    def update_strip(self):
        if not self.lib:
            return
        mods = self.lib.list()
        self.cells['MODS'].setText(str(len(mods)))
        self.cells['ON'].setText(str(sum(m.enabled for m in mods)))
        n = self.lib.pending_count()
        self.cells['NOT APPLIED'].setText(str(n))
        self.cells['NOT APPLIED'].setObjectName('StripValueHi' if n else 'StripValue')
        self.cells['NOT APPLIED'].setStyleSheet('')
        self.apply_btn.setEnabled(bool(n))
        self.apply_btn.setText(f'Apply {n} Change{"s" if n != 1 else ""}' if n else 'Game Up to Date')
        self._winners = None
        home = self.pages.get('Home')
        if home is not None and self.stack.currentWidget() is home:
            home.refresh()

    def apply(self):
        self.go('Mods')
        self.pages['Mods'].apply()

    def toast(self, text):
        b = self.toast_box
        b.setText(text)
        w = b.fontMetrics().horizontalAdvance(text) + 44
        b.setFixedWidth(min(640, max(240, w)))
        b.adjustSize()
        self._place_toast()
        b.show()
        b.raise_()
        QTimer.singleShot(6000, lambda t=text: b.text() == t and b.hide())

    def _place_toast(self):
        b = getattr(self, 'toast_box', None)
        if b is None:
            return
        c = self.centralWidget()
        side = 248
        x = side + (c.width() - side - b.width()) // 2
        b.move(max(side + 12, x), c.height() - b.height() - 28)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._place_toast()

    def run(self, fn, text, done=None):
        self.toast(text)
        self.progress.setValue(0)
        self.progress.show()
        job = workers.Job(fn)
        job.sig.progress.connect(lambda d, t: (self.progress.setMaximum(max(1, t)), self.progress.setValue(d)))

        def ok(res):
            self.progress.hide()
            if done:
                done(res)

        def bad(tb):
            self.progress.hide()
            QMessageBox.critical(self, 'Something Went Wrong', tb.strip().splitlines()[-1] + '\n\n' + tb[-1200:])
        job.sig.done.connect(ok)
        job.sig.failed.connect(bad)
        self._jobs = getattr(self, '_jobs', [])
        self._jobs.append(job)
        workers.start(job)

    def launch(self):
        if self.lib.pending():
            r = QMessageBox.question(self, 'Changes Not Applied',
                                     'Some mod changes aren\'t in the game yet. Launch anyway?\n\n'
                                     'Choose No to go to Mods and apply them first.')
            if r != QMessageBox.Yes:
                self.go('Mods')
                return
        try:
            self.game.launch(self.pages['Code Plugins'].env())
            self.toast('Launching MLB The Show 26...')
        except Exception as x:
            QMessageBox.warning(self, 'Could Not Launch', str(x))

    def closeEvent(self, e):
        for p in self.pages.values():
            g = getattr(p, 'grid', None)
            if g is not None:
                g.stop()
        from .viewer3d import ModelView3D
        for v in self.findChildren(ModelView3D):      # free GPU textures while their context still exists
            try:
                v.set_meshes([])
            except Exception:
                pass
        super().closeEvent(e)
