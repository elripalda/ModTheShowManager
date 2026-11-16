import datetime
import json
import os

from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QImage, QPixmap
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMenu, QMessageBox, QPlainTextEdit,
                               QProgressBar, QPushButton, QVBoxLayout, QWidget)

from .. import codemods, recipes
from . import theme, workers
from .common import badge, button, header, label, panel, section_title
from .widgets import Toggle

CATEGORY = [('NSW/UNIFORMS', 'Uniforms'), ('NSW/STADIUMS', 'Stadiums'), ('NSW/UI/GAME', 'Scoreboards'),
            ('NSW/OBJECTS/BAT', 'Bats'), ('NSW/LOADINGSCREEN', 'Loading Screens'), ('NSW/UI', 'Menus'),
            ('CROSS/LIVE', 'Card Art')]


def open_folder(path):
    QDesktopServices.openUrl(QUrl.fromLocalFile(path))


class ModInfoDialog(QDialog):
    def __init__(self, parent, title, meta=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(440)
        meta = meta or {}
        lay = QVBoxLayout(self)
        lay.setSpacing(14)
        form = QFormLayout()
        form.setSpacing(10)
        self.name = QLineEdit(meta.get('name', ''))
        self.author = QLineEdit(meta.get('author', ''))
        self.version = QLineEdit(meta.get('version', '1.0'))
        self.desc = QPlainTextEdit(meta.get('description', ''))
        self.desc.setFixedHeight(84)
        form.addRow('Name', self.name)
        form.addRow('Author', self.author)
        form.addRow('Version', self.version)
        form.addRow('Description', self.desc)
        lay.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText('Save')
        bb.button(QDialogButtonBox.Ok).setObjectName('Primary')
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def values(self):
        return {'name': self.name.text().strip() or 'New Mod', 'author': self.author.text().strip(),
                'version': self.version.text().strip() or '1.0', 'description': self.desc.toPlainText().strip()}


def mod_cover(mod):
    """First texture PNG of a mod, as a small pixmap."""
    for dp, _, fs in os.walk(os.path.join(mod.path, 'textures')):
        for f in sorted(fs):
            if f.lower().endswith('.png') and 'normal' not in f.lower() and 'emissive' not in f.lower():
                img = QImage(os.path.join(dp, f))
                if not img.isNull():
                    return QPixmap.fromImage(img.scaled(96, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))
    return None


def mod_categories(mod):
    rels = list(mod.textures().keys()) + list(mod.files().keys())
    cats = []
    for prefix, name in CATEGORY:
        if any(r.startswith(prefix) for r in rels) and name not in cats:
            cats.append(name)
    return cats


class ModRow(QWidget):
    changed = Signal()

    def __init__(self, page, mod, overrides):
        super().__init__()
        self.page, self.mod = page, mod
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 14, 12, 14)
        lay.setSpacing(16)
        cover = QLabel()
        cover.setFixedSize(96, 60)
        cover.setAlignment(Qt.AlignCenter)
        cover.setStyleSheet(f'background: {theme.S2}; border: none; border-radius: 10px;')
        pm = mod_cover(mod)
        if pm:
            cover.setPixmap(pm)
        lay.addWidget(cover)
        text = QVBoxLayout()
        text.setSpacing(5)
        top = QHBoxLayout()
        top.setSpacing(10)
        name = label(mod.name)
        name.setStyleSheet('font-size: 15px; font-weight: 600;')
        top.addWidget(name)
        meta = []
        if mod.meta.get('version'):
            meta.append('v' + mod.meta['version'])
        if mod.meta.get('author'):
            meta.append(mod.meta['author'])
        if meta:
            top.addWidget(label(' · '.join(meta), 'Sub'))
        top.addStretch(1)
        text.addLayout(top)
        if mod.meta.get('description'):
            text.addWidget(label(mod.meta['description'], 'Soft', wrap=True))
        chips = QHBoxLayout()
        chips.setSpacing(6)
        nt, nf = mod.counts()
        for c in mod_categories(mod):
            chips.addWidget(badge(c))
        if nt:
            chips.addWidget(badge(f'{nt} texture{"s" if nt != 1 else ""}'))
        if nf:
            chips.addWidget(badge(f'{nf} file{"s" if nf != 1 else ""}'))
        nc = len(codemods.mod_patches(mod))
        if nc:
            chips.addWidget(badge('Code mod'))
        nr = recipes.count(mod.path)
        if nr:
            chips.addWidget(badge(f'{nr} recipe{"s" if nr != 1 else ""}'))
        if not nt and not nf and not nc and not nr:
            chips.addWidget(badge('Empty: add textures from any section'))
        if overrides:
            chips.addWidget(badge(f'Overrides {", ".join(sorted(overrides))}', True))
        chips.addStretch(1)
        text.addLayout(chips)
        lay.addLayout(text, 1)
        self.toggle = Toggle()
        self.toggle.setChecked(mod.enabled)
        self.toggle.setAccessibleName(f'{mod.name} on or off')
        self.toggle.toggled.connect(self._toggle)
        lay.addWidget(self.toggle, 0, Qt.AlignVCenter)
        for text_, tip, d in (('▲', 'Move up', -1), ('▼', 'Move down', 1)):
            b = QPushButton(text_)
            b.setObjectName('Icon')
            b.setToolTip(tip)
            b.setAccessibleName(f'{tip}: {mod.name}')
            b.clicked.connect(lambda _=False, dd=d: self._move(dd))
            lay.addWidget(b, 0, Qt.AlignVCenter)
        more = QPushButton('•••')
        more.setObjectName('Icon')
        more.setAccessibleName(f'More for {mod.name}')
        more.clicked.connect(self._menu)
        lay.addWidget(more, 0, Qt.AlignVCenter)
        if not mod.enabled:
            for w in (cover, name):
                w.setEnabled(False)

    def _toggle(self, on):
        self.page.lib.set_enabled(self.mod, on)
        self.changed.emit()

    def _move(self, d):
        self.page.lib.move(self.mod, d)
        self.changed.emit()

    def _menu(self):
        m = QMenu(self)
        m.addAction('Save New Changes Here', lambda: self.page.main.set_active_mod(self.mod.folder))
        m.addAction('Edit Info', self._edit)
        m.addAction('Open Folder', lambda: open_folder(self.mod.path))
        m.addAction('Export as .zip', self._export)
        m.addSeparator()
        m.addAction('Move to Top', lambda: self._move(-10000))
        m.addAction('Move to Bottom (wins conflicts)', lambda: self._move(10000))
        m.addSeparator()
        m.addAction('Delete', self._delete)
        m.exec(self.cursor().pos())

    def _edit(self):
        dlg = ModInfoDialog(self, 'Edit Mod', self.mod.meta)
        if dlg.exec():
            self.mod.meta.update(dlg.values())
            self.mod.save_meta()
            self.changed.emit()

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Export Mod', f'{self.mod.name}.zip', 'Zip (*.zip)')
        if path:
            self.page.lib.export_zip(self.mod, path)
            self.page.main.toast(f'Exported {os.path.basename(path)}')

    def _delete(self):
        if QMessageBox.question(self, 'Delete Mod', f'Delete "{self.mod.name}" and all its files?') == QMessageBox.Yes:
            self.page.lib.delete(self.mod)
            self.changed.emit()


class SamplesDialog(QDialog):
    """Ready-made mods, built here from this install's own files."""

    def __init__(self, page):
        super().__init__(page)
        from PySide6.QtWidgets import QCheckBox
        from .. import samples
        self.page, self.made, self.notes = page, [], []
        self.setWindowTitle('Sample Mods')
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lay.addWidget(label('Each one shows a different kind of mod. They are made on your PC from your own game '
                            'files and added switched off, so nothing changes until you switch one on and Apply.',
                            'Sub', wrap=True))
        have = {m.name for m in page.lib.list()}
        self.boxes = []
        for key, name, text, build in samples.SAMPLES:
            c = QCheckBox(name + ('  (already added, tick to rebuild it)' if name in have else ''))
            c.setChecked(name not in have)
            lay.addWidget(c)
            d = label(text, 'Sub', wrap=True)
            d.setContentsMargins(28, 0, 0, 6)
            lay.addWidget(d)
            self.boxes.append((c, name, build))
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText('Add Samples')
        bb.button(QDialogButtonBox.Ok).setObjectName('Primary')
        bb.accepted.connect(self._go)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _go(self):
        main, lib = self.page.main, self.page.lib
        for c, name, build in self.boxes:
            if not c.isChecked():
                continue
            new = not any(m.name == name for m in lib.list())
            try:
                mod, note = build(main.game, lib, main.current_file)
            except Exception as x:
                self.notes.append(f'{name}: {x}')
                continue
            if new and (mod.textures() or mod.files() or recipes.has_any(mod.path)):
                # (a code-only mod stays on: it changes nothing until it is built and ticked)
                lib.set_enabled(mod, False)
            self.made.append(name)
            self.notes.append(f'{name}: {note}')
        self.accept()


class ModsPage(QWidget):
    applied = Signal()

    def __init__(self, main):
        super().__init__()
        self.setObjectName('Page')
        self.main = main
        self.lib = None
        self.setAcceptDrops(True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 20)
        lay.setSpacing(18)
        lay.addWidget(header('Mods', 'Switch mods on, set the order, then apply. When two mods change the same texture, '
                             'the lower one wins.', [button('Sample Mods', on_click=self.samples),
                                                    button('Import Mod', on_click=self.import_zip),
                                                    button('New Mod', on_click=self.new_mod)]))
        self.banner = QFrame()
        self.banner.setObjectName('Banner')
        bl = QHBoxLayout(self.banner)
        bl.setContentsMargins(16, 12, 16, 12)
        self.banner_title = label('')
        self.banner_title.setStyleSheet(f'color: {theme.AMBER}; font-weight: 500;')
        bl.addWidget(self.banner_title)
        self.banner_text = label('Apply to put them in the game.', 'Soft')
        bl.addWidget(self.banner_text, 1)
        lay.addWidget(self.banner)
        body = QHBoxLayout()
        body.setSpacing(20)
        self.listbox = panel()
        lb = QVBoxLayout(self.listbox)
        lb.setContentsMargins(0, 0, 0, 0)
        self.list = QListWidget()
        self.list.setObjectName('Mods')
        self.list.setStyleSheet('QListWidget#Mods { border: none; background: transparent; }')
        self.list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.list.setSelectionMode(QListWidget.NoSelection)
        lb.addWidget(self.list)
        self.empty = label('No mods yet. Make one with New Mod, open any section and replace a texture, or drop a mod '
                           '.zip here.', 'Soft', wrap=True)
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setContentsMargins(30, 40, 30, 40)
        lb.addWidget(self.empty)
        body.addWidget(self.listbox, 3)
        aside = QVBoxLayout()
        aside.setSpacing(20)
        self.conf_panel = panel()
        cp = QVBoxLayout(self.conf_panel)
        cp.setContentsMargins(18, 18, 18, 18)
        cp.setSpacing(10)
        cp.addWidget(section_title('Conflicts'))
        self.conf_text = label('', 'Soft', wrap=True)
        cp.addWidget(self.conf_text)
        aside.addWidget(self.conf_panel)
        self.game_panel = panel()
        gp = QVBoxLayout(self.game_panel)
        gp.setContentsMargins(18, 18, 18, 18)
        gp.setSpacing(10)
        gp.addWidget(section_title('In the Game Now'))
        self.game_text = label('', 'Soft', wrap=True)
        gp.addWidget(self.game_text)
        aside.addWidget(self.game_panel)
        aside.addStretch(1)
        aw = QWidget()
        aw.setLayout(aside)
        aw.setMinimumWidth(280)
        aw.setMaximumWidth(360)
        body.addWidget(aw, 1)
        lay.addLayout(body, 1)
        bar = panel()
        bb = QHBoxLayout(bar)
        bb.setContentsMargins(16, 12, 16, 12)
        bb.setSpacing(12)
        self.status = label('', 'Sub')
        bb.addWidget(self.status, 1)
        self.progress = QProgressBar()
        self.progress.setFixedWidth(220)
        self.progress.hide()
        bb.addWidget(self.progress)
        bb.addWidget(button('All Off', on_click=lambda: self.set_all(False)))
        bb.addWidget(button('All On', on_click=lambda: self.set_all(True)))
        self.restore_btn = button('Restore Original Game', on_click=self.restore)
        bb.addWidget(self.restore_btn)
        self.apply_btn = button('Apply Mods', True, self.apply)
        self.apply_btn.setMinimumWidth(170)
        bb.addWidget(self.apply_btn)
        lay.addWidget(bar)

    def set_library(self, lib):
        self.lib = lib
        self.refresh()

    def refresh(self):
        if not self.lib:
            return
        self.list.clear()
        conflicts = self.lib.conflicts()
        beats = {}
        for (_, _), names in conflicts.items():
            for loser in names[:-1]:
                beats.setdefault(names[-1], set()).add(loser)
        mods = self.lib.list()
        for m in mods:
            row = ModRow(self, m, beats.get(m.name, set()))
            row.changed.connect(self.refresh)
            it = QListWidgetItem()
            it.setSizeHint(QSize(100, row.sizeHint().height()))
            self.list.addItem(it)
            self.list.setItemWidget(it, row)
        self.empty.setVisible(not mods)
        self.list.setVisible(bool(mods))
        if conflicts:
            lines = []
            for (k, n), names in list(conflicts.items())[:6]:
                lines.append(f'{n or k.rsplit("/", 1)[-1]}: {names[-1]} wins over {", ".join(names[:-1])}')
            more = len(conflicts) - 6
            self.conf_text.setText('\n'.join(lines) + (f'\n+{more} more' if more > 0 else ''))
        else:
            self.conf_text.setText('No two mods change the same thing. Nothing is overridden.')
        self.game_text.setText(self._applied_text())
        pending = self.lib.pending()
        self.banner.setVisible(pending)
        on = sum(m.enabled for m in mods)
        self.banner_title.setText('Your changes aren\'t in the game yet.')
        self.apply_btn.setText('Apply Changes' if pending else 'Apply Mods')
        if not self.progress.isVisible():
            self.status.setText(f'{on} of {len(mods)} mods on. Applying takes a few seconds; close the game first.')
        self.main.update_strip()

    def _applied_text(self):
        try:
            with open(os.path.join(self.main.game.backup, 'applied.json'), encoding='utf-8') as f:
                data = json.load(f)
        except (OSError, ValueError):
            return 'The game is untouched. Nothing has been applied yet.'
        when = datetime.datetime.fromtimestamp(data.get('when', 0)).strftime('%b %d, %I:%M %p').replace(' 0', ' ')
        names = [m.name for m in self.lib.list() if m.folder in {x[0] for x in data.get('mods', [])}]
        return (f'Applied {when}\n' + (', '.join(names) if names else 'No mods') +
                '\nOriginals are kept in mod-backup.')

    def samples(self):
        if not self.lib:
            return
        dlg = SamplesDialog(self)
        if dlg.exec() and dlg.made:
            self.refresh()
            self.main.changed(f'{len(dlg.made)} sample mod{"s" if len(dlg.made) != 1 else ""} added, switched off. '
                              'Switch on the ones you want and Apply.')
            if dlg.notes:
                QMessageBox.information(self, 'Sample Mods', '\n'.join(dlg.notes))

    def set_all(self, on):
        if not self.lib:
            return
        for m in self.lib.list():
            if m.enabled != on:
                self.lib.set_enabled(m, on)
        self.refresh()

    def new_mod(self):
        dlg = ModInfoDialog(self, 'New Mod', {'author': self.main.settings.get('author', '')})
        if dlg.exec():
            v = dlg.values()
            self.main.settings['author'] = v['author']
            self.main.save_settings()
            m = self.lib.create(v['name'], v['author'], v['description'])
            m.meta['version'] = v['version']
            m.save_meta()
            self.main.set_active_mod(m.folder)
            self.refresh()
            return m
        return None

    def import_zip(self, path=None):
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, 'Import Mod', self.main.last_dir(), 'Mod (*.zip)')
        if path:
            try:
                m = self.lib.import_zip(path)
                self.main.toast(f'Imported {m.name}')
            except Exception as x:
                QMessageBox.warning(self, 'Import Mod', f'Could not import that zip:\n{x}')
            self.refresh()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() and any(u.toLocalFile().lower().endswith('.zip') for u in e.mimeData().urls()):
            e.acceptProposedAction()

    def dropEvent(self, e):
        for u in e.mimeData().urls():
            if u.toLocalFile().lower().endswith('.zip'):
                self.import_zip(u.toLocalFile())

    def _busy(self, on, text=''):
        self.apply_btn.setEnabled(not on)
        self.restore_btn.setEnabled(not on)
        self.progress.setVisible(on)
        self.progress.setValue(0)
        if text:
            self.status.setText(text)

    def _check_game(self):
        if self.main.game.running():
            QMessageBox.information(self, 'Game Is Running', 'Close MLB The Show 26 first, then try again.')
            return False
        return True

    def apply(self):
        if not self._check_game():
            return
        self._busy(True, 'Applying mods...')
        lib = self.lib
        job = workers.Job(lambda j: lib.apply(log=j.log, progress=j.progress))
        job.sig.progress.connect(lambda d, t: (self.progress.setMaximum(max(1, t)), self.progress.setValue(d)))
        job.sig.log.connect(self.status.setText)
        job.sig.done.connect(self._applied)
        job.sig.failed.connect(self._failed)
        self._job = workers.start(job)

    def _applied(self, res):
        changed, problems = res
        self._busy(False)
        self.main.cache_clear()
        self.refresh()
        self.applied.emit()
        self.status.setText(f'Mods applied: {len(set(changed))} game file(s) changed. Launch the game to see them.')
        if problems:
            QMessageBox.warning(self, 'Applied With Problems', 'Some items were skipped:\n\n' + '\n'.join(problems[:30]))

    def _failed(self, tb):
        self._busy(False, 'Apply failed')
        last = tb.strip().splitlines()[-1]
        if 'PermissionError' in tb:
            last = 'A game file is locked. Close the game (and anything using its files), then try again.'
        QMessageBox.critical(self, 'Something Went Wrong', f'{last}\n\nDetails:\n{tb[-1500:]}')
        self.refresh()

    def restore(self):
        if not self._check_game():
            return
        if QMessageBox.question(self, 'Restore Original Game',
                                'Put every original game file back, bring back the standard mlb.exe if code mods '
                                'were built in, and switch all mods off?\n\n'
                                'Your mods stay in the list, so you can switch them back on and Apply later.'
                                ) != QMessageBox.Yes:
            return
        self._busy(True, 'Restoring...')
        lib = self.lib

        def work(j):
            rels = lib.restore(log=j.log)
            for m in lib.list():
                if m.enabled:
                    lib.set_enabled(m, False)
            if codemods.restore_exe(self.main.game.root):
                self.main.settings['code_built'] = ''
                self.main.save_settings()
            return rels

        job = workers.Job(work)
        job.sig.done.connect(lambda r: (self._busy(False), self.main.cache_clear(), self.main.changed(), self.refresh(),
                                        self.applied.emit(),
                                        self.status.setText(f'Restored {len(r)} original file(s) and switched every mod '
                                                            'off. The game is back to stock.')))
        job.sig.failed.connect(self._failed)
        self._job = workers.start(job)
