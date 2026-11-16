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
        self._empty_text = ('No code mods yet. Add Arcade Samples gives you ready-made ones (Auto PCI, moonshots, '
                            'juiced ball, thin air). New Code Mod puts a starter file in your mod that explains the '
                            'format.')
        self.empty = label(self._empty_text, 'Soft', wrap=True)
        self.hint = label('Tick what you want, press Rebuild Game once, then play. After that you can tick and '
                          'untick without rebuilding; it takes effect the next time the game starts. In the game, '
                          'F2 steps through the code mods and F3 switches the one shown on or off.', 'Sub', wrap=True)
        ll.addWidget(self.hint)
        ll.addWidget(self.empty)
        self.filler = QWidget()
        ll.addWidget(self.filler, 1)
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

    def active_names(self):
        """Names of the code mods that are ticked, when the game is built with the current set."""
        sets, text, bad = codemods.collect(self.main.lib.list())
        if bad or not sets:
            return []
        text, misfit = codemods.fitting(self.main.game.root, text)
        if codemods.signature(text) != self.main.settings.get('code_built', ''):
            return []
        sw = self.switches()
        return [codemods.nice(n) for n, _, default, _ in sets if sw.get(n, bool(default)) and n not in misfit]

    def activate(self):
        self.refresh()

    def refresh(self):
        sets, text, bad = codemods.collect(self.main.lib.list())
        text, misfit = codemods.fitting(self.main.game.root, text)
        self.list.clear()
        sw = self.switches()
        # F3 in the game changes the file; the ticks follow it
        known = {n for n, _, _, _ in sets}
        changed = {n: on for n, on in codemods.read_switches(self.main.game.root).items()
                   if n in known and sw.get(n) != on}
        if changed:
            sw.update(changed)
            self.main.save_settings()
        for name, env, default, mod in sets:
            it = QListWidgetItem()
            w = QWidget()
            hl = QHBoxLayout(w)
            hl.setContentsMargins(4, 0, 4, 0)
            chk = QCheckBox(codemods.nice(name))
            chk.setChecked(sw.get(name, bool(default)) and name not in misfit)
            chk.setToolTip(f'Takes effect the next time the game starts. Launch switch: {env}.')
            chk.toggled.connect(lambda on, n=name: self._toggle(n, on))
            if name in misfit:
                chk.setEnabled(False)
                chk.setToolTip('Made for a different game version:\n' + '\n'.join(misfit[name][:4]))
            chk.setMinimumWidth(170)
            hl.addWidget(chk)
            d = label('Doesn’t fit this game version, so it is left out of the build.' if name in misfit
                      else codemods.DESCRIPTIONS.get(name, mod), 'Sub', wrap=True)
            hl.addWidget(d, 1)
            from PySide6.QtCore import QSize
            it.setSizeHint(QSize(0, 56))
            self.list.addItem(it)
            self.list.setItemWidget(it, w)
        off = [m.name for m in self.main.lib.list() if not m.enabled and codemods.mod_patches(m)]
        self.empty.setText(f'Your code mods are in mods that are switched off ({", ".join(off[:3])}). Switch them on '
                           'in Mods and they show up here.' if off and not sets else self._empty_text)
        self.empty.setVisible(not sets)
        self.hint.setVisible(bool(sets))
        have = self._arcade_text()
        self.b_arcade.setText('Add Arcade Samples' if have is None else 'Update Arcade Samples')
        self.b_arcade.setEnabled(have != codemods.ARCADE)
        self.list.setVisible(bool(sets))
        self.filler.setVisible(not sets)
        r = self.recomp()
        self.recomp_label.setText(f'Recomp folder: {r}' if r else
                                  'The recomp folder (where MLBTS-Setup.exe is) wasn’t found. Point the manager at it '
                                  'to build code mods.')
        sig = codemods.signature(text)
        built = self.main.settings.get('code_built', '')
        if bad:
            self.state.setText('Problems:\n' + '\n'.join(bad[:8]))
        elif sig == built:
            self.state.setText(('The game is built with the code mods above.\n' + self._last_launch_text(sets))
                               if sig else 'No code mods are switched on. The game is the standard build.')
        else:
            self.state.setText('The game needs a rebuild before these code mods can work. Press Rebuild Game.')
        self.b_build.setEnabled(bool(r) and not bad and sig != built)
        self.b_restore.setEnabled(os.path.exists(os.path.join(self.main.game.root, 'mlb.original.exe')))

    def _toggle(self, name, on):
        self.switches()[name] = on
        self.main.save_settings()
        self.write_switches()

    def write_switches(self):
        """Puts the ticks in the game folder, where the built game reads them however it is started."""
        sets, _, _ = codemods.collect(self.main.lib.list())
        sw = self.switches()
        try:
            codemods.write_switches(self.main.game.root, {n: sw.get(n, bool(d)) for n, _, d, _ in sets})
        except OSError:
            pass

    def _last_launch_text(self, sets):
        seen = codemods.last_launch(self.main.game.root)
        if seen is None:
            return 'The game hasn’t been started since a rebuild, so there is nothing to check yet.'
        on = [codemods.nice(n) for n, (state, _) in seen.items() if state]
        missing = [codemods.nice(n) for n, _, _, _ in sets if n not in seen]
        text = ('Last time the game started it had on: ' + ', '.join(on) + '.') if on else \
            'Last time the game started, every code mod was off.'
        if missing:
            text += ' Not in that build: ' + ', '.join(missing[:4]) + '.'
        sw = codemods.last_swing(self.main.game.root)
        if sw:
            bits = []
            if 'error' in sw:
                bits.append(f'PCI was {sw["error"]:.2f} off the ball')
            if 'perfect' in sw:
                bits.append(f'perfect PCI {sw["perfect"][0]}, perfect timing {sw["perfect"][1]}')
            text += '\nLast swing in the game’s log: ' + ', '.join(bits) + '.'
        return text

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

    def _arcade_text(self):
        """The arcade patch file in the library, or None when the samples are not added."""
        mod = next((m for m in self.main.lib.list() if m.name == codemods.ARCADE_NAME), None)
        if mod is None:
            return None
        try:
            with open(os.path.join(mod.path, 'code', 'arcade.patch'), encoding='utf-8') as f:
                return f.read()
        except OSError:
            return ''

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
        text, _ = codemods.fitting(self.main.game.root, text)
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
        self.write_switches()
        try:      # the note from an older build would only mislead
            os.remove(os.path.join(self.main.game.root, 'logs', codemods.SWITCH_LOG))
        except OSError:
            pass
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
