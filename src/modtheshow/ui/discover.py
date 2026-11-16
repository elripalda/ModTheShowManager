"""Discover: mods other people have shared, one click to add."""
from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QListWidget, QListWidgetItem, QMessageBox, QVBoxLayout, QWidget

from .. import community
from .common import badge, button, header, label, panel
from .workers import Job, start


class Row(QWidget):
    def __init__(self, page, entry, have):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 14, 14, 14)
        lay.setSpacing(16)
        col = QVBoxLayout()
        col.setSpacing(5)
        top = QHBoxLayout()
        top.setSpacing(10)
        name = label(entry['name'])
        name.setStyleSheet('font-size: 15px; font-weight: 600;')
        top.addWidget(name)
        meta = ' · '.join(x for x in ('v' + entry['version'] if entry['version'] else '', entry['author']) if x)
        if meta:
            top.addWidget(label(meta, 'Sub'))
        top.addStretch(1)
        col.addLayout(top)
        if entry['description']:
            col.addWidget(label(entry['description'], 'Soft', wrap=True))
        chips = QHBoxLayout()
        chips.setSpacing(6)
        for k in entry['kinds']:
            chips.addWidget(badge(k))
        chips.addStretch(1)
        col.addLayout(chips)
        lay.addLayout(col, 1)
        self.btn = button('In Your Mods' if have else 'Add', not have, lambda: page.install(entry, self.btn))
        self.btn.setEnabled(not have)
        self.btn.setMinimumWidth(150)
        lay.addWidget(self.btn, 0, Qt.AlignVCenter)


class DiscoverPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.setObjectName('Page')
        self.main = main
        self.entries = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(18)
        lay.addWidget(header('Discover', 'Mods other people have shared. Adding one puts it in your Mods list, '
                             'switched off, until you switch it on and apply.',
                             [button('Refresh', on_click=self.load),
                              button('How Sharing Works', on_click=lambda: QDesktopServices.openUrl(QUrl(community.GUIDE))),
                              button('Share a Mod', True, self.share)]))
        box = panel()
        bl = QVBoxLayout(box)
        bl.setContentsMargins(0, 0, 0, 0)
        self.list = QListWidget()
        self.list.setObjectName('Mods')
        self.list.setStyleSheet('QListWidget#Mods { border: none; background: transparent; }')
        self.list.setSelectionMode(QListWidget.NoSelection)
        self.list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        bl.addWidget(self.list)
        self.note = label('', 'Soft', wrap=True)
        self.note.setAlignment(Qt.AlignCenter)
        self.note.setContentsMargins(30, 40, 30, 40)
        bl.addWidget(self.note)
        lay.addWidget(box, 1)

    def activate(self):
        if self.entries is None:
            self.load()
        else:
            self._fill()

    def load(self):
        self.list.hide()
        self.note.show()
        self.note.setText('Looking for shared mods…')
        job = Job(lambda j: community.fetch_index())
        job.sig.done.connect(self._loaded)
        job.sig.failed.connect(lambda tb: self.note.setText('The list of shared mods couldn’t be reached. Check your '
                                                           'connection and press Refresh.'))
        self._job = job
        start(job)

    def _loaded(self, entries):
        self.entries = entries
        self._fill()

    def _fill(self):
        self.list.clear()
        have = {m.meta.get('shared_id') for m in self.main.lib.list()} | {m.name for m in self.main.lib.list()}
        for e in self.entries or []:
            row = Row(self, e, e['id'] in have or e['name'] in have)
            it = QListWidgetItem()
            it.setSizeHint(QSize(100, row.sizeHint().height()))
            self.list.addItem(it)
            self.list.setItemWidget(it, row)
        empty = not self.entries
        self.list.setVisible(not empty)
        self.note.setVisible(empty)
        if empty:
            self.note.setText('Nothing has been shared yet. Be the first: Share a Mod.')

    def install(self, entry, btn):
        btn.setEnabled(False)
        btn.setText('Adding…')
        lib = self.main.lib
        job = Job(lambda j: community.install(entry, lib))

        def done(mod):
            self.main.changed(f'{mod.name} added to your mods, switched off. Switch it on in Mods and apply.')
            self._fill()

        def failed(tb):
            btn.setEnabled(True)
            btn.setText('Add')
            QMessageBox.warning(self, 'Could Not Add', tb.strip().splitlines()[-1].replace('ValueError: ', ''))
        job.sig.done.connect(done)
        job.sig.failed.connect(failed)
        self._ijob = job
        start(job)

    def share(self):
        """Packs the mod in Saving To for sharing, then opens the form to send it in."""
        from PySide6.QtWidgets import QFileDialog
        import os
        mod = self.main.active_mod(ask=True)
        if not mod:
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Pack Mod for Sharing',
                                              os.path.join(self.main.last_dir(), mod.name + '.zip'), 'Zip (*.zip)')
        if not path:
            return
        try:
            skipped = community.pack(mod, path)
        except OSError as x:
            QMessageBox.warning(self, 'Could Not Pack', str(x))
            return
        text = f'{os.path.basename(path)} is ready. The form that opens next asks for it.'
        if skipped:
            text += ('\n\nLeft out, because a shared mod can only hold what you made (PNG textures, recipes and code '
                     'patches), not changed game files:\n' + '\n'.join(skipped[:10]))
        QMessageBox.information(self, 'Packed for Sharing', text)
        QDesktopServices.openUrl(QUrl(community.SUBMIT))
