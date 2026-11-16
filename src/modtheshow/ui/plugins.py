"""Code Mods: every mod that changes how the game plays, in one list. Each has one switch here; Rebuild Game builds them
into mlb.exe with the recomp's own tools, and the same list opens in the game on F4."""
import os
import shutil

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
                               QPlainTextEdit, QSlider, QVBoxLayout, QWidget)

from .. import codemods
from .common import badge, button, header, label, panel, section_title
from .widgets import Toggle
from .workers import Job, start

KEYS = ('F4 opens the list in the game. Up and Down move, Enter switches a mod on or off, Left and Right turn a '
        'dial. Changes take effect at once and are remembered. The game ignores the controller while the list is '
        'open, so close it with F4 before the next pitch. F6 sets off Fireworks. The Effects show while the '
        'game’s fps readout is on (F10), and it is switched on for them.')


class Row(QWidget):
    """One code mod: its switch, what it does, its dial when it has one, and what the last game showed."""

    def __init__(self, page, name, source, on, fits, dial, note, warn):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(14)
        self.toggle = Toggle()
        self.toggle.setChecked(on and fits)
        self.toggle.setEnabled(fits)
        self.toggle.toggled.connect(lambda state: page.toggle(name, state))
        lay.addWidget(self.toggle, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(4)
        top = QHBoxLayout()
        top.setSpacing(8)
        title = label(codemods.nice(name))
        title.setStyleSheet('font-size: 14px; font-weight: 600;')
        top.addWidget(title)
        if codemods.TAGS.get(name):
            top.addWidget(badge(codemods.TAGS[name]))
        if source != codemods.BUILT_IN:
            top.addWidget(badge(source, True))
        top.addStretch(1)
        col.addLayout(top)
        text = codemods.DESCRIPTIONS.get(name, '') if fits else \
            'Made for a different version of the game, so it is left out of the build.'
        if text:
            col.addWidget(label(text, 'Soft', wrap=True))
        if note:
            n = label(note, 'Sub', wrap=True)
            if warn:
                n.setStyleSheet('color: #E0A83C;')
            col.addWidget(n)
        lay.addLayout(col, 1)
        side = QWidget()                      # every row keeps this column, so the text lines up down the list
        side.setFixedWidth(210)
        sl = QHBoxLayout(side)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(10)
        if dial and fits:
            dname, value, lo, hi, step, what = dial
            self.slider = QSlider(Qt.Horizontal)
            self.slider.setRange(0, max(1, round((hi - lo) / step)))
            self.slider.setValue(round((value - lo) / step))
            self.slider.setToolTip(what)
            self.value = label(f'{value:.2f}')
            self.value.setFixedWidth(44)
            self.value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.value.setStyleSheet('font-weight: 600;')

            def moved(k):
                v = lo + k * step
                self.value.setText(f'{v:.2f}')
                page.turn(dname, v)
            self.slider.valueChanged.connect(moved)
            sl.addWidget(self.slider, 1)
            sl.addWidget(self.value)
        lay.addWidget(side, 0, Qt.AlignVCenter)


class PluginsPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.setObjectName('Page')
        self.main = main
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(18)
        self.b_more = button('Get More', on_click=lambda: main.go('Discover'))
        self.b_import = button('Import', on_click=self.import_file)
        self.b_new = button('Make Your Own', on_click=self.new_patch)
        self.b_build = button('Rebuild Game', True, self.rebuild)
        outer.addWidget(header('Code Mods', 'Mods that change how the game plays. Switch on what you want and press '
                               'Rebuild Game once (about two minutes). After that, switch them and turn their dials '
                               'here or in the game with F4, no rebuild needed.',
                               [self.b_more, self.b_import, self.b_new, self.b_build]))
        row = QHBoxLayout()
        row.setSpacing(20)
        left = panel()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(18, 18, 18, 18)
        ll.setSpacing(12)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search')
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(220)
        self.search.textChanged.connect(lambda _: self.refresh())
        ll.addWidget(section_title('Your code mods', [self.search]))
        self.list = QListWidget()
        self.list.setStyleSheet('QListWidget { border: none; padding: 0; background: transparent; }')
        self.list.setSelectionMode(QListWidget.NoSelection)
        self.list.setFocusPolicy(Qt.NoFocus)
        self.list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        ll.addWidget(self.list, 1)
        row.addWidget(left, 3)
        right = panel()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(18, 18, 18, 18)
        rl.setSpacing(12)
        rl.addWidget(section_title('Build'))
        self.state = label('', 'Soft', wrap=True)
        rl.addWidget(self.state)
        self.recomp_label = label('', 'Sub', wrap=True)
        rl.addWidget(self.recomp_label)
        pick = QHBoxLayout()
        pick.setSpacing(8)
        self.b_pick = button('Find Recomp Folder', on_click=self.pick_recomp)
        self.b_restore = button('Restore Original mlb.exe', on_click=self.restore)
        pick.addWidget(self.b_pick, 1)
        pick.addWidget(self.b_restore, 1)
        rl.addLayout(pick)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText('Build output shows here.')
        rl.addWidget(self.log, 1)
        rl.addWidget(section_title('Last game'))
        self.last = label('', 'Soft', wrap=True)
        rl.addWidget(self.last)
        rl.addWidget(section_title('In the game'))
        rl.addWidget(label(KEYS, 'Sub', wrap=True))
        row.addWidget(right, 2)
        outer.addLayout(row, 1)

    # ---- state
    def recomp(self):
        return codemods.find_recomp(self.main.settings.get('recomp'))

    def switches(self):
        return self.main.settings.setdefault('code_switches', {})

    def dial_values(self):
        return self.main.settings.setdefault('code_dials', {})

    def table(self):
        """(sets, table text without what does not fit this game, problems, {set: why it does not fit})"""
        sets, text, bad = codemods.collect(self.main.lib.list())
        text, misfit = codemods.fitting(self.main.game.root, text)
        return sets, text, bad, misfit

    def dials(self, text):
        """{dial name: (name, value now, lowest, highest, step, label)}"""
        have = self.dial_values()
        return {d[0]: (d[0], min(d[3], max(d[2], float(have.get(d[0], d[1])))), d[2], d[3], d[4], d[5])
                for d in codemods.dials(text)}

    def env(self):
        """Environment for a launch: every known set, on or off."""
        sets, _, _ = codemods.collect(self.main.lib.list())
        sw = self.switches()
        return {env: '1' if sw.get(name, bool(default)) else '0' for name, env, default, _ in sets}

    def launch_env(self):
        """Ready for a launch: what the in-game menu changed last time is taken in first, then the switches and
        dials go to the game folder. Returns the environment for the game."""
        sets, text, _ = codemods.collect(self.main.lib.list())
        self._sync(sets, text)
        self.write_switches()
        return self.env()

    def active_names(self):
        """Names of the code mods that are on, when the game is built with the current set."""
        sets, text, bad, misfit = self.table()
        if bad or not sets or codemods.signature(text) != self.main.settings.get('code_built', ''):
            return []
        sw = self.switches()
        return [codemods.nice(n) for n, _, default, _ in sets if sw.get(n, bool(default)) and n not in misfit]

    def activate(self):
        self.refresh()

    def _sync(self, sets, text):
        """The in-game menu saves what it changed; the switches and dials here follow it."""
        sw, dv = self.switches(), self.dial_values()
        known = {n for n, _, _, _ in sets}
        root = self.main.game.root
        changed = {n: on for n, on in codemods.read_switches(root).items() if n in known and sw.get(n) != on}
        turned = {n: v for n, v in codemods.read_dials(root).items()
                  if n in {d[0] for d in codemods.dials(text)} and abs(float(dv.get(n, v + 1)) - v) > 1e-6}
        if changed or turned:
            sw.update(changed)
            dv.update(turned)
            self.main.save_settings()

    def refresh(self):
        sets, text, bad, misfit = self.table()
        self._sync(sets, text)
        sw = self.switches()
        dials = self.dials(text)
        turns = codemods.set_dials(text)
        root = self.main.game.root
        sig, built = codemods.signature(text), self.main.settings.get('code_built', '')
        current = bool(sig) and sig == built
        ran = codemods.last_activity(root) if current else None
        seen = (codemods.last_launch(root) or {}) if current else {}
        want = self.search.text().strip().lower()
        self.list.clear()

        def add(widget, height=None):
            it = QListWidgetItem()
            it.setFlags(Qt.NoItemFlags)
            it.setSizeHint(QSize(100, height or widget.sizeHint().height()))
            self.list.addItem(it)
            self.list.setItemWidget(it, widget)

        shown = 0
        for group, members in codemods.grouped(sets):
            members = [m for m in members if not want or want in codemods.nice(m[0]).lower()
                       or want in codemods.DESCRIPTIONS.get(m[0], '').lower() or want in group.lower()]
            if not members:
                continue
            head = label(group.upper(), 'Sub')
            head.setStyleSheet('font-weight: 700; letter-spacing: 1px; padding: 12px 14px 2px 14px;')
            add(head, 38)
            for name, _env, default, source in members:
                on = sw.get(name, bool(default))
                note, warn = '', False
                if ran is not None and name in ran:
                    if ran[name]:
                        note = f'Its code ran {ran[name]:,} time{"s" if ran[name] != 1 else ""} in your last game.'
                    elif seen.get(name, (False, ''))[0]:
                        note, warn = 'It was on in your last game, but the game never got to its code.', True
                elif current and seen and name not in seen:
                    note = 'Not in the game yet. Press Rebuild Game.'
                if current and group == 'Effects' and \
                        int(self.main.settings.get('code_menu', codemods.MENU_FULL)) < codemods.MENU_FULL:
                    note, warn = ('This build could not join the in-game menu to the game, so this one has nothing '
                                  'to draw with.'), True
                dial = dials.get(turns.get(name, [None])[0])
                add(Row(self, name, source, on, name not in misfit, dial, note, warn), 64)
                shown += 1
        if not shown:
            add(label('Nothing matches that search.' if want else 'No code mods yet.', 'Soft'), 60)
        r = self.recomp()
        self.recomp_label.setText(f'Recomp folder: {r}' if r else
                                  'The recomp folder (where MLBTS-Setup.exe is) wasn’t found. Point the manager at it '
                                  'to build code mods.')
        frozen = current and not self.main.settings.get('code_live', True)
        stale = frozen and any(abs(v[1] - float(self.main.settings.get('code_built_dials', {}).get(k, v[1]))) > 1e-6
                               for k, v in dials.items())
        if bad:
            self.state.setText('Problems:\n' + '\n'.join(bad[:8]))
        elif current:
            text_ = ('The game is built with these code mods, so nothing needs rebuilding. Switching one on or off '
                     'here takes effect the next time the game starts, and at once with F4 in the game.')
            if frozen:
                text_ += ' This build has its dials fixed: after turning one, press Rebuild Game.'
            self.state.setText(text_)
        elif built:
            self.state.setText('The list has changed since the game was built. Press Rebuild Game to bring it up to date.')
        else:
            self.state.setText('Press Rebuild Game once to build the code mods into the game. Your current mlb.exe is '
                               'kept as mlb.original.exe.')
        # always there once the recomp is found: building again does no harm, and it is the way back when something
        # else (a game update, the recomp's own setup) has swapped mlb.exe for one without the code mods
        self.b_build.setEnabled(bool(r) and not bad and bool(sig))
        self.b_build.setObjectName('Primary' if (sig != built or stale) else '')
        self.b_build.style().unpolish(self.b_build)
        self.b_build.style().polish(self.b_build)
        self.b_restore.setEnabled(os.path.exists(os.path.join(root, 'mlb.original.exe')))
        self.last.setText(self._last_game_text(current))
        self._fit()
        QTimer.singleShot(0, self._fit)       # once more when the list has its real width

    def _fit(self):
        """Each row as tall as its wrapped text needs at the list's width."""
        width = self.list.viewport().width()
        if width < 200:
            return
        for i in range(self.list.count()):
            it = self.list.item(i)
            w = self.list.itemWidget(it)
            if isinstance(w, Row):
                h = max(64, w.heightForWidth(width - 36) + 6 if w.hasHeightForWidth() else w.sizeHint().height())
                if it.sizeHint().height() != h:
                    it.setSizeHint(QSize(100, h))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        QTimer.singleShot(0, self._fit)

    def _last_game_text(self, current):
        root = self.main.game.root
        seen = codemods.last_launch(root) if current else None
        if not current or seen is None:
            return 'Play a game after a rebuild and what the game recorded shows here, so you can see a mod working.'
        on = [codemods.nice(n) for n, (state, _) in seen.items() if state]
        bits = ['On when it started: ' + ', '.join(on) + '.' if on else 'Every code mod was off when it started.']
        g = codemods.last_game(root)
        if g.get('hits'):
            bits.append(f'{g["hits"]} ball{"s" if g["hits"] != 1 else ""} hit, the hardest at {g["hardest"]:.1f} mph.')
        if 'air' in g:
            bits.append(f'Air density {g["air"]:.3f} (about 0.075 untouched).')
        if g.get('bunts'):
            bits.append(f'Hardest bunt {g["hardest_bunt"]:.1f} mph.')
        if g.get('breaks'):
            bits.append(f'Pitches broke {g["usual_break"]:.2f} ft as a rule, {g["biggest_break"]:.2f} ft at most.')
        sw = codemods.last_swing(root)
        if 'error' in sw:
            bits.append(f'On the last swing the PCI was {sw["error"]:.2f} off the ball.')
        fx = codemods.last_effects(root)
        if fx.get('frames'):
            if not fx['ball']:
                bits.append('The effects were drawing but never got hold of the ball.')
            elif not fx['camera']:
                bits.append('The effects found the ball but not the camera.')
            else:
                bits.append(f'The effects followed {fx["flights"]} pitch{"es" if fx["flights"] != 1 else ""} and set '
                            f'{fx["lit"]} on fire.')
        return ' '.join(bits)

    # ---- switches and dials
    def toggle(self, name, on):
        self.switches()[name] = on
        self.main.save_settings()
        self.write_switches()

    def turn(self, dial, value):
        self.dial_values()[dial] = value
        self.main.save_settings()
        self.write_switches()

    def write_switches(self):
        """Puts the switches and dials in the game folder, where the built game reads them however it is started."""
        sets, text, _ = codemods.collect(self.main.lib.list())
        sw = self.switches()
        try:
            codemods.write_switches(self.main.game.root, {n: sw.get(n, bool(d)) for n, _, d, _ in sets},
                                    {k: v[1] for k, v in self.dials(text).items()})
        except OSError:
            pass

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

    def import_file(self):
        """A code mod someone sent you: a .patch file, or a shared mod's .zip."""
        path, _ = QFileDialog.getOpenFileName(self, 'Import a Code Mod', self.main.last_dir(),
                                              'Code mods (*.patch *.zip)')
        if not path:
            return
        lib = self.main.lib
        try:
            if path.lower().endswith('.zip'):
                mod = lib.import_zip(path)
            else:
                with open(path, encoding='utf-8', errors='replace') as f:
                    _sets, _lines, bad = codemods.parse(f.read(), os.path.basename(path))
                if bad:
                    QMessageBox.warning(self, 'Could Not Import', 'That file has lines the manager cannot read:\n\n' +
                                        '\n'.join(bad[:6]))
                    return
                stem = os.path.splitext(os.path.basename(path))[0]
                name, n = stem.replace('_', ' ').strip().title() or 'Code Mod', 2
                taken = {m.name for m in lib.list()}
                while name in taken:
                    name, n = f'{stem.replace("_", " ").strip().title()} {n}', n + 1
                mod = lib.create(name, '')
                os.makedirs(os.path.join(mod.path, 'code'), exist_ok=True)
                shutil.copy2(path, os.path.join(mod.path, 'code', os.path.basename(path)))
        except Exception as x:
            QMessageBox.warning(self, 'Could Not Import', str(x))
            return
        got = len(codemods.mod_patches(mod)) if mod else 0
        self.main.changed(f'{mod.name} added. Its code mods are in the list, switched off.' if got else
                          f'{mod.name} added to your mods. It has no code mods in it.')
        self.refresh()

    def new_patch(self):
        mod = self.main.active_mod(ask=True, kind='Code')
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
        self.main.toast(f'Starter file made in {mod.name}\\code. It explains the format. Edit it, then come back '
                        'and Rebuild Game.')
        self.refresh()

    def rebuild(self):
        if self.main.game.running():
            QMessageBox.information(self, 'Game Is Running', 'Close MLB The Show 26 first, then try again.')
            return
        sets, text, bad, _ = self.table()
        if bad:
            return
        sig_now = codemods.signature(text)
        fresh = sig_now and sig_now == self.main.settings.get('code_built', '')
        r = QMessageBox.question(self, 'Rebuild Game',
                                 ('The game already has these code mods built in, and switching them on or off needs '
                                  'no rebuild. Build it again anyway? It takes about two minutes.' if fresh else
                                  'This builds every code mod in the list into mlb.exe, switched off until you switch '
                                  'it on. It takes about two minutes and your current mlb.exe is kept as '
                                  'mlb.original.exe.\n\nRebuild now?'))
        if r != QMessageBox.Yes:
            return
        recomp, root = self.recomp(), self.main.game.root
        values = {k: v[1] for k, v in self.dials(text).items()}
        self.log.clear()
        self.b_build.setEnabled(False)
        job = Job(lambda j: codemods.rebuild(recomp, root, text, log=j.log, dial_values=values))
        job.sig.log.connect(self._line)
        job.sig.done.connect(lambda result: self._built(codemods.signature(text), result, values))
        job.sig.failed.connect(self._failed)
        self._job = job
        start(job)

    def _line(self, text):
        self.log.appendPlainText(text)

    def _built(self, sig, result, values):
        result = result if isinstance(result, dict) else {}
        s = self.main.settings
        s['code_built'] = sig
        s['code_live'] = bool(result.get('live', True))
        s['code_menu'] = int(result.get('menu', codemods.MENU_FULL))
        s['code_built_dials'] = dict(values)
        self.main.save_settings()
        self.write_switches()
        try:      # the note from an older build would only mislead
            os.remove(os.path.join(self.main.game.root, 'logs', codemods.SWITCH_LOG))
        except OSError:
            pass
        self.main.toast('Game rebuilt. Your code mods are in; press F4 in the game for the list.'
                        if s['code_menu'] else 'Game rebuilt with your code mods.')
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
