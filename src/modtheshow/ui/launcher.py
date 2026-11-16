"""The launcher card on Home: what state the game is in, a Play button, and the game's display settings."""
import datetime
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QFrame, QGridLayout, QHBoxLayout,
                               QSpinBox, QVBoxLayout)

from .. import exefile
from .common import button, label


def _when(iso):
    try:
        t = datetime.datetime.strptime(iso, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc).astimezone()
        return t.strftime('%b %d').replace(' 0', ' ')
    except ValueError:
        return ''


def _played(seconds):
    if seconds < 60:
        return 'Not played yet' if not seconds else 'Under a minute'
    h, m = divmod(seconds // 60, 60)
    return f'{h} h {m} min' if h else f'{m} min'


class Tile(QFrame):
    def __init__(self, title):
        super().__init__()
        self.setObjectName('Tile')
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(3)
        lay.addWidget(label(title, 'TileHead'))
        self.value = label('', 'TileValue')
        self.note = label('', 'Sub', wrap=True)
        lay.addWidget(self.value)
        lay.addWidget(self.note, 1, Qt.AlignTop)
        self.setMinimumHeight(96)

    def set(self, value, note=''):
        self.value.setText(value)
        self.note.setText(note)


class GameSettings(QDialog):
    """A few lines of mlb.cfg. The rest lives in the game's own F1 menu."""

    def __init__(self, parent, root):
        super().__init__(parent)
        self.root = root
        self.setWindowTitle('Game Display')
        self.setMinimumWidth(420)
        cfg = exefile.read_cfg(root)
        lay = QVBoxLayout(self)
        lay.setSpacing(14)
        lay.addWidget(label('These are the game’s own settings (mlb.cfg). Everything else is in the game under F1.',
                            'Sub', wrap=True))
        form = QFormLayout()
        form.setSpacing(10)
        self.full = QCheckBox('Start in fullscreen')
        self.full.setChecked(cfg.get('MLB_FULLSCREEN', '0') not in ('0', 'off', ''))
        self.fps = QCheckBox('Show the FPS counter')
        self.fps.setChecked(cfg.get('MLB_PERF_OVERLAY', 'off') not in ('0', 'off', ''))
        self.scale = QSpinBox()
        self.scale.setRange(50, 200)
        self.scale.setSingleStep(10)
        self.scale.setSuffix(' %')
        self.scale.setValue(self._num(cfg.get('MLB_RENDER_SCALE'), 100))
        self.sharp = QSpinBox()
        self.sharp.setRange(0, 100)
        self.sharp.setSingleStep(5)
        self.sharp.setValue(self._num(cfg.get('MLB_SHARPNESS'), 50))
        form.addRow('', self.full)
        form.addRow('', self.fps)
        form.addRow('Render scale', self.scale)
        form.addRow('Sharpness', self.sharp)
        lay.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText('Save')
        bb.button(QDialogButtonBox.Ok).setObjectName('Primary')
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._overlay = cfg.get('MLB_PERF_OVERLAY', 'off')

    @staticmethod
    def _num(v, default):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return default

    def _save(self):
        overlay = (self._overlay if self._overlay not in ('0', 'off', '') else 'fps') if self.fps.isChecked() else 'off'
        try:
            exefile.write_cfg(self.root, {'MLB_FULLSCREEN': '1' if self.full.isChecked() else '0',
                                          'MLB_PERF_OVERLAY': overlay, 'MLB_RENDER_SCALE': str(self.scale.value()),
                                          'MLB_SHARPNESS': str(self.sharp.value())})
        except OSError as x:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, 'Could Not Save', str(x))
            return
        self.accept()


class LauncherCard(QFrame):
    def __init__(self, main):
        super().__init__()
        self.setObjectName('Panel')
        self.main = main
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(14)
        top = QHBoxLayout()
        top.setSpacing(12)
        col = QVBoxLayout()
        col.setSpacing(3)
        col.addWidget(label('MLB The Show 26', 'CardTitle'))
        self.sub = label('', 'Sub')
        col.addWidget(self.sub)
        top.addLayout(col, 1)
        self.b_cfg = button('Game Display', on_click=self.settings)
        self.b_play = button('Play', True, main.launch)
        for b in (self.b_cfg, self.b_play):
            b.setMinimumWidth(170)
            top.addWidget(b, 0, Qt.AlignVCenter)
        lay.addLayout(top)
        grid = QGridLayout()
        grid.setSpacing(12)
        self.t_files, self.t_code, self.t_display, self.t_time = (Tile('GAME FILES'), Tile('GAME CODE'),
                                                                    Tile('DISPLAY'), Tile('PLAY TIME'))
        for i, t in enumerate((self.t_files, self.t_code, self.t_display, self.t_time)):
            grid.addWidget(t, 0, i)
            grid.setColumnStretch(i, 1)
        lay.addLayout(grid)

    def settings(self):
        if GameSettings(self, self.main.game.root).exec():
            self.refresh()
            self.main.toast('Saved. The game uses it the next time it starts.')

    def refresh(self):
        g, lib = self.main.game, self.main.lib
        info = exefile.install_info(g.root)
        bits = [f'Recomp {info["release"].split("+")[0]}' if info['release'] else 'Recomp install']
        if _when(info['built']):
            bits.append(f'built {_when(info["built"])}')
        bits.append(g.root)
        self.sub.setText(' · '.join(bits))
        on = [m for m in lib.list() if m.enabled] if lib else []
        pending = lib.pending_count() if lib else 0
        applied = os.path.exists(os.path.join(g.backup, 'applied.json'))
        if pending:
            self.t_files.set(f'{pending} change{"s" if pending != 1 else ""} waiting', 'Apply Changes puts them in.')
        elif on and applied:
            self.t_files.set(f'{len(on)} mod{"s" if len(on) != 1 else ""} in the game', 'Originals are safe in mod-backup.')
        else:
            self.t_files.set('Stock', 'No mods are in the game right now.')
        plug = self.main.pages.get('Code Mods')
        names = plug.active_names() if plug else []
        if names:
            self.t_code.set(f'{len(names)} code mod{"s" if len(names) != 1 else ""} on',
                            ', '.join(names[:3]) + (f' +{len(names) - 3}' if len(names) > 3 else ''))
        elif info['code_mods']:
            self.t_code.set('Built for code mods', 'None are switched on.')
        else:
            self.t_code.set('Standard', 'The mlb.exe the recomp built.')
        cfg = exefile.read_cfg(g.root)
        full = cfg.get('MLB_FULLSCREEN', '0') not in ('0', 'off', '')
        self.t_display.set('Fullscreen' if full else 'Windowed', f'Render scale {cfg.get("MLB_RENDER_SCALE", "100")}%')
        self.t_time.set(_played(info['play_seconds']), 'Counted by the game.')
