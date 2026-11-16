"""Game Files: every file in the RomFS, OpenIV style."""
import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QLineEdit, QPlainTextEdit, QSplitter,
                               QStackedWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from .common import FilterBar, Inspector, SectionTitle, TextureGrid, button, fmt_size, header, label, panel
from .widgets import ImageView, pil_to_qimage

TEXT_EXT = ('.XML', '.SCR', '.TXT', '.JSON', '.INI', '.CFG', '.CSV', '.H', '.LS4', '.TBL')
IMAGE_EXT = ('.WEBP', '.PNG', '.JPG', '.JPEG', '.BMP')


class FileView(QFrame):
    """Preview and actions for a file that is not a texture pack."""

    def __init__(self, main):
        super().__init__()
        self.main = main
        self.rel = None
        self.setObjectName('Panel')
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(12)
        self.title = SectionTitle()
        lay.addWidget(self.title)
        self.info = label('', 'Sub', wrap=True)
        lay.addWidget(self.info)
        self.stack = QStackedWidget()
        self.image = ImageView()
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.empty = label('No preview for this kind of file yet. You can still export it or replace it through a mod.',
                           'Soft', wrap=True)
        self.empty.setAlignment(Qt.AlignCenter)
        for w in (self.image, self.text, self.empty):
            self.stack.addWidget(w)
        lay.addWidget(self.stack, 1)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.b_export = button('Export File', on_click=self.export)
        self.b_edit = button('Edit a Copy in My Mod', on_click=self.edit_copy)
        self.b_replace = button('Replace File', True, self.replace)
        row.addWidget(self.b_export)
        row.addWidget(self.b_edit)
        row.addStretch(1)
        row.addWidget(self.b_replace)
        lay.addLayout(row)

    def show_file(self, rel, size):
        self.rel = rel
        up = rel.upper()
        self.title.set(rel.rsplit('/', 1)[-1], [fmt_size(size)])
        mod = self.main.mod_file(rel)
        self.info.setText(f'romfs/{rel}' + (f'   ·   Replaced by {mod[0].name}' if mod else ''))
        src = mod[1] if mod else self.main.game.original(rel)
        self.b_edit.setVisible(up.endswith(TEXT_EXT))
        try:
            if up.endswith(IMAGE_EXT):
                from PIL import Image
                self.image.set_image(pil_to_qimage(Image.open(src)))
                self.stack.setCurrentWidget(self.image)
            elif up.endswith(TEXT_EXT):
                with open(src, 'rb') as f:
                    data = f.read(400_000)
                self.text.setPlainText(data.decode('utf-8', errors='replace'))
                self.stack.setCurrentWidget(self.text)
            else:
                self.stack.setCurrentWidget(self.empty)
        except Exception as x:
            self.empty.setText(f'Could not preview this file: {x}')
            self.stack.setCurrentWidget(self.empty)

    def export(self):
        if not self.rel:
            return
        name = self.rel.rsplit('/', 1)[-1]
        path, _ = QFileDialog.getSaveFileName(self, 'Export File', os.path.join(self.main.last_dir(), name))
        if path:
            import shutil
            self.main.remember_dir(path)
            shutil.copy2(self.main.game.original(self.rel), path)
            self.main.toast(f'Exported {name}')

    def replace(self):
        if not self.rel:
            return
        up = self.rel.upper()
        filt = 'Images (*.png *.jpg *.jpeg *.webp)' if up.endswith(IMAGE_EXT) else 'All files (*)'
        path, _ = QFileDialog.getOpenFileName(self, 'Replace File', self.main.last_dir(), filt)
        if not path:
            return
        self.main.remember_dir(path)
        mod = self.main.active_mod(ask=True, rel=self.rel)
        if not mod:
            return
        if up.endswith(IMAGE_EXT) and not path.upper().endswith(os.path.splitext(up)[1]):
            # convert to the game's format and size
            from PIL import Image
            import tempfile
            orig = Image.open(self.main.game.original(self.rel))
            img = Image.open(path).convert('RGBA')
            if img.size != orig.size:
                img = img.resize(orig.size, Image.LANCZOS)
            tmp = os.path.join(tempfile.gettempdir(), 'mts_' + self.rel.rsplit('/', 1)[-1])
            fmt = {'.WEBP': 'WEBP', '.PNG': 'PNG', '.JPG': 'JPEG', '.JPEG': 'JPEG', '.BMP': 'BMP'}[os.path.splitext(up)[1]]
            (img if fmt in ('WEBP', 'PNG') else img.convert('RGB')).save(tmp, fmt, quality=95)
            path = tmp
        self.main.lib.add_file(mod, self.rel, path)
        self.main.changed(f'{self.rel.rsplit("/", 1)[-1]} saved to {mod.name}')
        self.show_file(self.rel, os.path.getsize(path))

    def edit_copy(self):
        if not self.rel:
            return
        mod = self.main.active_mod(ask=True, rel=self.rel)
        if not mod:
            return
        dst = os.path.join(mod.path, 'romfs', *self.rel.upper().split('/'))
        if not os.path.exists(dst):
            self.main.lib.add_file(mod, self.rel, self.main.game.original(self.rel))
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(dst))
        self.main.changed(f'Editing a copy of {self.rel.rsplit("/", 1)[-1]} in {mod.name}. Save it, then Apply.')


class GameFilesPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.setObjectName('Page')
        self.main = main
        self.loaded = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(18)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search files, e.g. jersey or ARZ')
        self.search.setAccessibleName('Search game files')
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(320)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._search)
        self.search.textChanged.connect(lambda _: self._timer.start())
        self.count_label = label('', 'Sub')
        outer.addWidget(header('Game Files', 'Every file in the game, read straight from your install. Preview any texture,'
                               ' export it, or send it to a mod.', [self.search]))
        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(16)
        left = panel()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(8, 8, 8, 8)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setTextElideMode(Qt.ElideMiddle)
        self.tree.setStyleSheet('QTreeWidget { border: none; background: transparent; padding: 0; }')
        self.tree.itemExpanded.connect(self._expand)
        self.tree.currentItemChanged.connect(self._picked)
        ll.addWidget(self.tree, 1)
        ll.addWidget(self.count_label)
        left.setMinimumWidth(240)
        left.setMaximumWidth(380)
        split.addWidget(left)
        self.right = QStackedWidget()
        # texture pack view
        texw = QWidget()
        tl = QHBoxLayout(texw)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(16)
        mid = panel()
        ml = QVBoxLayout(mid)
        ml.setContentsMargins(18, 18, 18, 18)
        ml.setSpacing(12)
        self.mid_title = SectionTitle()
        ml.addWidget(self.mid_title)
        self.filter = FilterBar('Filter textures by name')
        self.filter.changed.connect(lambda _: self._show_pack())
        ml.addWidget(self.filter)
        self.grid = TextureGrid()
        self.grid.picked.connect(self._tex_picked)
        ml.addWidget(self.grid, 1)
        tl.addWidget(mid, 1)
        self.inspector = Inspector(main)
        tl.addWidget(self.inspector)
        self.right.addWidget(texw)
        self.fileview = FileView(main)
        self.right.addWidget(self.fileview)
        self.hello = panel()
        hl = QVBoxLayout(self.hello)
        hi = label('Pick a file on the left. Texture packs end in .TEX: stadiums are in NSW/STADIUMS, uniforms in '
                   'NSW/UNIFORMS, the scorebug in NSW/UI/GAME.', 'Soft', wrap=True)
        hi.setAlignment(Qt.AlignCenter)
        hl.addWidget(hi)
        self.right.addWidget(self.hello)
        self.right.setCurrentWidget(self.hello)
        split.addWidget(self.right)
        split.setSizes([300, 1000])
        outer.addWidget(split, 1)
        self.pack = None

    def activate(self):
        if self.loaded:
            return
        self.loaded = True
        self.tree.clear()
        root = self.main.game.tree
        self._fill(self.tree.invisibleRootItem(), root)
        self.count_label.setText(f'{len(self.main.game.files):,} files')

    def _item(self, node):
        it = QTreeWidgetItem([node.name + ('' if node.is_dir else f'   {fmt_size(node.size)}')])
        it.setData(0, Qt.UserRole, node)
        if node.is_dir:
            it.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
        return it

    def _fill(self, parent, node):
        kids = sorted(node.children.values(), key=lambda n: (not n.is_dir, n.name))
        parent.addChildren([self._item(k) for k in kids])

    def _expand(self, it):
        node = it.data(0, Qt.UserRole)
        if node and node.is_dir and it.childCount() == 0:
            self._fill(it, node)

    def _search(self):
        q = self.search.text().strip().upper()
        self.tree.clear()
        if not q:
            self._fill(self.tree.invisibleRootItem(), self.main.game.tree)
            self.count_label.setText(f'{len(self.main.game.files):,} files')
            return
        hits = [f for f in self.main.game.files if q in f.upper()][:3000]
        from ..game import Node
        for f in hits:
            n = Node(f, f)
            n.size = self._size(f)
            it = QTreeWidgetItem([f])
            it.setData(0, Qt.UserRole, n)
            self.tree.addTopLevelItem(it)
        self.count_label.setText(f'{len(hits):,} match{"es" if len(hits) != 1 else ""}' +
                                 (' (first 3,000)' if len(hits) == 3000 else ''))

    def _size(self, rel):
        node = self.main.game.tree
        for part in rel.split('/'):
            node = node.children.get(part) if node.children else None
            if node is None:
                return 0
        return node.size

    def _picked(self, cur, _prev):
        if cur is None:
            return
        node = cur.data(0, Qt.UserRole)
        if node is None or node.is_dir:
            return
        rel = node.path
        if rel.upper().endswith('.TEX'):
            t = self.main.tex(rel)
            if t is None:
                self.fileview.show_file(rel, node.size)
                self.right.setCurrentWidget(self.fileview)
                return
            self.pack = rel
            self.mid_title.set(rel.rsplit('/', 1)[-1], [f'{len(t.entries)} textures', fmt_size(node.size)])
            self._show_pack()
            self.right.setCurrentIndex(0)
        else:
            self.fileview.show_file(rel, node.size)
            self.right.setCurrentWidget(self.fileview)

    def _show_pack(self):
        if not self.pack:
            return
        t = self.main.tex(self.pack)
        if t is not None:
            self.grid.show_packs([(self.pack, t)], self.main.overrides(), self.filter.edit.text())

    def _tex_picked(self, rel, idx):
        t = self.main.tex(rel)
        if t is not None:
            self.inspector.show_entry(rel, t, idx)

    def refresh_overrides(self):
        if self.pack and self.right.currentIndex() == 0:
            cur = self.grid.currentRow()
            self._show_pack()
            if 0 <= cur < self.grid.count():
                self.grid.setCurrentRow(cur)
