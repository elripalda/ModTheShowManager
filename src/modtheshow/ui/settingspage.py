"""Settings: how the app looks, where the game and the recomp are, and updates."""
import os

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QFileDialog, QGridLayout, QHBoxLayout,
                               QMessageBox, QPushButton, QVBoxLayout, QWidget)

from .. import __version__, codemods, updater
from . import theme
from .common import button, header, label, panel, section_title
from .workers import Job, start

SIZES = [('Small', 0.92), ('Normal', 1.0), ('Large', 1.12), ('Extra Large', 1.25)]


def segments(names, current, on_pick):
    row = QHBoxLayout()
    row.setSpacing(6)
    group = QButtonGroup(row)
    for n in names:
        b = QPushButton(n)
        b.setObjectName('Seg')
        b.setCheckable(True)
        b.setCursor(Qt.PointingHandCursor)
        b.setChecked(n == current)
        b.clicked.connect(lambda _=False, v=n: on_pick(v))
        group.addButton(b)
        row.addWidget(b, 1)
    row.group = group
    return row


class SettingsPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.setObjectName('Page')
        self.main = main
        s = main.settings
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(18)
        outer.addWidget(header('Settings', 'How the manager looks, where your game is, and updates.'))
        grid = QGridLayout()
        grid.setSpacing(16)

        look = self._card('Appearance')
        look.lay.addWidget(label('Theme', 'Sub'))
        look.lay.addLayout(segments(list(theme.PALETTES), s.get('theme', 'Dark'), self._theme))
        look.lay.addWidget(label('Text size', 'Sub'))
        cur = next((n for n, v in SIZES if abs(v - s.get('text_scale', 1.0)) < 0.01), 'Normal')
        look.lay.addLayout(segments([n for n, _ in SIZES], cur, self._size))
        self.motion = QCheckBox('Animations')
        self.motion.setChecked(s.get('motion', True))
        self.motion.toggled.connect(self._motion)
        look.lay.addWidget(self.motion)
        look.lay.addStretch(1)
        grid.addWidget(look, 0, 0)

        game = self._card('Game')
        game.lay.addWidget(label('MLB The Show 26', 'Sub'))
        game.lay.addWidget(label(main.game.root, wrap=True))
        game.lay.addWidget(label('Recomp tools (for code mods)', 'Sub'))
        self.recomp = label('', wrap=True)
        game.lay.addWidget(self.recomp)
        game.lay.addStretch(1)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(button('Change Game Folder', on_click=main.change_game), 1)
        row.addWidget(button('Find Recomp Folder', on_click=self._recomp), 1)
        game.lay.addLayout(row)
        grid.addWidget(game, 0, 1)

        upd = self._card('Updates')
        upd.lay.addWidget(label(f'You have version {__version__}.'))
        self.upd_text = label('', 'Sub', wrap=True)
        upd.lay.addWidget(self.upd_text)
        self.auto = QCheckBox('Check when the manager starts')
        self.auto.setChecked(s.get('auto_update', True))
        self.auto.toggled.connect(lambda on: self._set('auto_update', on))
        upd.lay.addWidget(self.auto)
        upd.lay.addStretch(1)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.b_check = button('Check Now', on_click=self.check)
        self.b_update = button('Download and Install', True, self.install)
        self.b_update.setEnabled(False)
        row.addWidget(self.b_check, 1)
        row.addWidget(self.b_update, 1)
        upd.lay.addLayout(row)
        grid.addWidget(upd, 1, 0)

        files = self._card('Your files')
        files.lay.addWidget(label('Mods live in the game folder under mods. The original of every file a mod changes '
                                  'is kept in mod-backup, so Restore Original Game always works.', 'Sub', wrap=True))
        files.lay.addStretch(1)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(button('Open Mods Folder', on_click=lambda: self._open(main.lib.root)), 1)
        row.addWidget(button('Open Backups', on_click=lambda: self._open(main.game.backup)), 1)
        files.lay.addLayout(row)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(button('Modding Guide', on_click=lambda: QDesktopServices.openUrl(
            QUrl('https://github.com/elripalda/ModTheShowManager/blob/main/docs/MODDING_GUIDE.md'))), 1)
        row.addWidget(button('Project Page', on_click=lambda: QDesktopServices.openUrl(
            QUrl('https://github.com/elripalda/ModTheShowManager'))), 1)
        files.lay.addLayout(row)
        grid.addWidget(files, 1, 1)
        for i in (0, 1):
            grid.setColumnStretch(i, 1)
            grid.setRowStretch(i, 1)
        outer.addLayout(grid, 1)
        self.found = None

    def _card(self, title):
        p = panel()
        p.lay = QVBoxLayout(p)
        p.lay.setContentsMargins(20, 18, 20, 18)
        p.lay.setSpacing(10)
        p.lay.addWidget(section_title(title))
        return p

    def activate(self):
        r = codemods.find_recomp(self.main.settings.get('recomp'))
        self.recomp.setText(r or 'Not found yet')
        if self.main.update_info:
            self._show_update(self.main.update_info)

    def _set(self, key, value):
        self.main.settings[key] = value
        self.main.save_settings()

    def _open(self, path):
        os.makedirs(path, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _theme(self, name):
        self._set('theme', name)
        self.main.retheme()

    def _size(self, name):
        self._set('text_scale', dict(SIZES)[name])
        self.main.retheme()

    def _motion(self, on):
        self._set('motion', on)
        theme.MOTION = on

    def _recomp(self):
        path = QFileDialog.getExistingDirectory(self, 'Recomp Folder (with MLBTS-Setup.exe)', self.main.last_dir())
        if not path:
            return
        if not codemods.is_recomp(path):
            QMessageBox.warning(self, 'Not the Recomp Folder', 'Pick the folder MLBTS-Setup.exe is in.')
            return
        self._set('recomp', path)
        self.activate()

    # ---- updates
    def check(self):
        self.b_check.setEnabled(False)
        self.upd_text.setText('Checking...')
        job = Job(lambda j: updater.check(__version__))
        job.sig.done.connect(self._checked)
        job.sig.failed.connect(lambda tb: (self.b_check.setEnabled(True),
                                           self.upd_text.setText('Could not reach GitHub. Try again later.')))
        self._job = job
        start(job)

    def _checked(self, info):
        self.b_check.setEnabled(True)
        self.main.update_info = info
        if info:
            self._show_update(info)
        else:
            self.upd_text.setText('You’re up to date.')

    def _show_update(self, info):
        self.found = info
        self.upd_text.setText(f'Version {info["version"]} is out.')
        self.b_update.setEnabled(True)

    def install(self):
        info = self.found
        if not info:
            return
        if not info.get('asset'):
            QDesktopServices.openUrl(QUrl(info['url']))
            return
        self.b_update.setEnabled(False)
        self.upd_text.setText('Downloading...')
        job = Job(lambda j: updater.download(info['asset'], info['name'], j.progress))
        job.sig.progress.connect(lambda d, t: self.upd_text.setText(
            f'Downloading... {d * 100 // t}%' if t else 'Downloading...'))
        job.sig.done.connect(self._downloaded)
        job.sig.failed.connect(lambda tb: (self.b_update.setEnabled(True),
                                           self.upd_text.setText('The download failed. Try again.')))
        self._job = job
        start(job)

    def _downloaded(self, path):
        try:
            updater.run_installer(path)
        except Exception as x:
            self.upd_text.setText(f'Could not start the installer: {x}')
            return
        QApplication.instance().quit()
