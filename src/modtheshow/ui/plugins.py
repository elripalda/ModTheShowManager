"""Code Plugins: instruction patches from mods, built into mlb.exe with the recomp's own tools."""
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QFileDialog, QHBoxLayout, QListWidget, QListWidgetItem, QMessageBox,
                               QPlainTextEdit, QVBoxLayout, QWidget)

from .. import codemods
from .common import button, header, label, panel, section_title
from .workers import Job, start


class PluginsPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.setObjectName('Page')
        self.main = main
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(18)
        self.b_arcade = button('Add Arcade Samples', on_click=self.add_arcade)
        self.b_new = button('New Code Mod', on_click=self.new_patch)
        self.b_build = button('Rebuild Game', True, self.rebuild)
        outer.addWidget(header('Code Plugins', 'Mods that change how the game plays. A code mod is a list of '
                               'instruction patches; Rebuild Game bakes the ones that are switched on into mlb.exe '
                               '(about two minutes), and each can still be turned off per launch.',
                               [self.b_arcade, self.b_new, self.b_build]))
        row = QHBoxLayout()
        row.setSpacing(20)
        left = panel()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(18, 18, 18, 18)
        ll.setSpacing(12)
        ll.addWidget(section_title('Code mods'))
        self.list = QListWidget()
        self.list.setStyleSheet('QListWidget { border: none; padding: 0; background: transparent; }')
        self.list.setSelectionMode(QListWidget.NoSelection)
        ll.addWidget(self.list, 1)
        self.empty = label('No code mods yet. Add Arcade Samples gives you ready-made ones (moonshots, juiced ball, '
                           'thin air). New Code Mod puts a starter file in your mod that explains the format.',
                           'Soft', wrap=True)
        self.hint = label('Tick what you want, press Rebuild Game once, then launch from the manager. After that you '
                          'can tick and untick without rebuilding.', 'Sub', wrap=True)
        ll.addWidget(self.hint)
        ll.addWidget(self.empty)
        row.addWidget(left, 3)
        right = panel()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(18, 18, 18, 18)
        rl.setSpacing(12)
        rl.addWidget(section_title('Build'))
        self.recomp_label = label('', 'Soft', wrap=True)
        rl.addWidget(self.recomp_label)
        pick = QHBoxLayout()
        pick.setSpacing(8)
        self.b_pick = button('Find Recomp Folder', on_click=self.pick_recomp)
        self.b_restore = button('Restore Original mlb.exe', on_click=self.restore)
        pick.addWidget(self.b_pick, 1)
        pick.addWidget(self.b_restore, 1)
        rl.addLayout(pick)
        self.state = label('', 'Sub', wrap=True)
        rl.addWidget(self.state)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText('Build output shows here.')
        rl.addWidget(self.log, 1)
        row.addWidget(right, 2)
        outer.addLayout(row, 1)

    # ---- state
    def recomp(self):
        return codemods.find_recomp(self.main.settings.get('recomp'))

    def switches(self):
        return self.main.settings.setdefault('code_switches', {})

    def env(self):
        """Environment for a launch: every known set, on or off."""
        sets, _, _ = codemods.collect(self.main.lib.list())
        sw = self.switches()
        return {env: '1' if sw.get(name, bool(default)) else '0' for name, env, default, _ in sets}

    def activate(self):
        self.refresh()

    def refresh(self):
        sets, text, bad = codemods.collect(self.main.lib.list())
        self.list.clear()
        sw = self.switches()
        for name, env, default, mod in sets:
            it = QListWidgetItem()
            w = QWidget()
            hl = QHBoxLayout(w)
            hl.setContentsMargins(4, 0, 4, 0)
            chk = QCheckBox(name.replace('_', ' ').title())
            chk.setChecked(sw.get(name, bool(default)))
            chk.setToolTip(f'Switch {env}. Takes effect the next time you launch from the manager.')
            chk.toggled.connect(lambda on, n=name: self._toggle(n, on))
            chk.setMinimumWidth(170)
            hl.addWidget(chk)
            d = label(codemods.DESCRIPTIONS.get(name, mod), 'Sub', wrap=True)
            hl.addWidget(d, 1)
            from PySide6.QtCore import QSize
            it.setSizeHint(QSize(0, 56))
            self.list.addItem(it)
            self.list.setItemWidget(it, w)
        self.empty.setVisible(not sets)
        self.hint.setVisible(bool(sets))
        self.b_arcade.setEnabled(not any(m.name == codemods.ARCADE_NAME for m in self.main.lib.list()))
        self.list.setVisible(bool(sets))
        r = self.recomp()
        self.recomp_label.setText(f'Recomp folder: {r}' if r else
                                  'The recomp folder (where MLBTS-Setup.exe is) wasn’t found. Point the manager at it '
                                  'to build code mods.')
        sig = codemods.signature(text)
        built = self.main.settings.get('code_built', '')
        if bad:
            self.state.setText('Problems:\n' + '\n'.join(bad[:8]))
        elif sig == built:
            self.state.setText('The game is built with the code mods above.' if sig else
                               'No code mods are switched on. The game is the standard build.')
        else:
            self.state.setText('Code mods changed since the last build. Rebuild Game to use them.')
        self.b_build.setEnabled(bool(r) and not bad and sig != built)
        self.b_restore.setEnabled(os.path.exists(os.path.join(self.main.game.root, 'mlb.original.exe')))

    def _toggle(self, name, on):
        self.switches()[name] = on
        self.main.save_settings()

    # ---- actions
    def pick_recomp(self):
        path = QFileDialog.getExistingDirectory(self, 'Recomp Folder (with MLBTS-Setup.exe)', self.main.last_dir())
        if not path:
            return
        if not codemods.is_recomp(path):
            QMessageBox.warning(self, 'Not the Recomp Folder', 'That folder has no recomp, tools and python folders. '
                                'Pick the folder MLBTS-Setup.exe is in.')
            return
        self.main.settings['recomp'] = path
        self.main.save_settings()
        self.refresh()

    def add_arcade(self):
        lib = self.main.lib
        mod = next((m for m in lib.list() if m.name == codemods.ARCADE_NAME), None)
        if mod is None:
            mod = lib.create(codemods.ARCADE_NAME, 'Ripalda')
        folder = os.path.join(mod.path, 'code')
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, 'arcade.patch'), 'w', encoding='utf-8') as f:
            f.write(codemods.ARCADE)
        if not mod.enabled:
            lib.set_enabled(mod, True)
        self.main.changed('Arcade samples added. Tick the ones you want, then Rebuild Game.')
        self.refresh()

    def new_patch(self):
        mod = self.main.active_mod(ask=True)
        if not mod:
            return
        folder = os.path.join(mod.path, 'code')
        os.makedirs(folder, exist_ok=True)
        path, n = os.path.join(folder, 'my code mod.patch'), 2
        while os.path.exists(path):
            path, n = os.path.join(folder, f'my code mod {n}.patch'), n + 1
        with open(path, 'w', encoding='utf-8') as f:
            f.write(codemods.TEMPLATE)
        from .modspage import open_folder
        open_folder(folder)
        self.main.toast(f'Starter file made in {mod.name}\\code. Edit it, then come back and Rebuild Game.')
        self.refresh()

    def rebuild(self):
        if self.main.game.running():
            QMessageBox.information(self, 'Game Is Running', 'Close MLB The Show 26 first, then try again.')
            return
        sets, text, bad = codemods.collect(self.main.lib.list())
        if bad:
            return
        r = QMessageBox.question(self, 'Rebuild Game', 'This rebuilds mlb.exe with the code mods that are switched '
                                 'on. It takes about two minutes and your current mlb.exe is kept as '
                                 'mlb.original.exe.\n\nRebuild now?')
        if r != QMessageBox.Yes:
            return
        recomp, root = self.recomp(), self.main.game.root
        self.log.clear()
        self.b_build.setEnabled(False)
        job = Job(lambda j: codemods.rebuild(recomp, root, text, log=j.log))
        job.sig.log.connect(self._line)
        job.sig.done.connect(lambda _: self._built(codemods.signature(text)))
        job.sig.failed.connect(self._failed)
        self._job = job
        start(job)

    def _line(self, text):
        self.log.appendPlainText(text)

    def _built(self, sig):
        self.main.settings['code_built'] = sig
        self.main.save_settings()
        self.main.toast('Game rebuilt with your code mods.')
        self.refresh()

    def _failed(self, tb):
        lines = tb.strip().splitlines()
        at = next((i for i, l in enumerate(lines) if 'PatchError' in l), len(lines) - 1)
        self.log.appendPlainText('\n'.join(lines[at:]).replace('modtheshow.codemods.PatchError: ', ''))
        self.main.toast('The rebuild failed. The game was not changed.')
        self.refresh()

    def restore(self):
        if self.main.game.running():
            QMessageBox.information(self, 'Game Is Running', 'Close MLB The Show 26 first, then try again.')
            return
        if codemods.restore_exe(self.main.game.root):
            self.main.settings['code_built'] = ''
            self.main.save_settings()
            self.main.toast('The original mlb.exe is back.')
        self.refresh()
