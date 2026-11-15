"""Pieces every screen shares: headings, the texture grid and the inspector."""
import os
import re

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QDialog, QDialogButtonBox, QFileDialog, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
                               QPushButton, QSizePolicy, QVBoxLayout, QWidget)

from . import theme
from .widgets import ImageView, pil_to_qimage
from .workers import ThumbLoader


def label(text, name=None, wrap=False):
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


def badge(text, mod=False):
    b = QLabel(text)
    b.setObjectName('BadgeMod' if mod else 'Badge')
    return b


def button(text, primary=False, on_click=None):
    b = QPushButton(text)
    if primary:
        b.setObjectName('Primary')
    b.setCursor(Qt.PointingHandCursor)
    if on_click:
        b.clicked.connect(on_click)
    return b


def panel():
    f = QFrame()
    f.setObjectName('Panel')
    return f


def header(title, sub, actions=()):
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(12)
    col = QVBoxLayout()
    col.setSpacing(6)
    col.addWidget(label(title.upper(), 'H1'))
    s = label(sub, 'Sub', wrap=True)
    s.setMaximumWidth(720)
    col.addWidget(s)
    lay.addLayout(col, 1)
    for a in actions:
        lay.addWidget(a, 0, Qt.AlignBottom)
    return w


class SectionTitle(QWidget):
    """An H2 with badges on the right; update it in place with set()."""

    def __init__(self, text='', badges=()):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.title = label('', 'H2')
        lay.addWidget(self.title, 1)
        self.badges = []
        for _ in range(3):
            b = badge('')
            b.hide()
            lay.addWidget(b)
            self.badges.append(b)
        self.set(text, badges)

    def set(self, text, badges=()):
        self.title.setText(text.upper())
        for i, b in enumerate(self.badges):
            if i < len(badges):
                b.setText(badges[i])
                b.show()
            else:
                b.hide()


def section_title(text, right=()):
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(8)
    lay.addWidget(label(text.upper(), 'H2'))
    lay.addStretch(1)
    for r in right:
        lay.addWidget(r)
    return w


def masked(rel):
    """Uniform textures use alpha as a mask (lettering, trim), not as transparency."""
    return rel.upper().startswith('NSW/UNIFORMS')


def for_display(rel, img):
    if masked(rel):
        return img.convert('RGB').convert('RGBA')
    return img


def fmt_size(n):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or unit == 'GB':
            return f'{n:.0f} {unit}' if unit == 'B' else f'{n:.1f} {unit}'
        n /= 1024


def placeholder_icon(size=112):
    pm = QPixmap(size, size)
    pm.fill(QColor(theme.S1))
    p = QPainter(pm)
    p.setPen(QColor('#24324f'))
    p.drawRect(0, 0, size - 1, size - 1)
    p.end()
    return QIcon(pm)


def framed_icon(qimage, size=112):
    """Thumbnail centred on a checkerboard tile so transparent art reads."""
    pm = QPixmap(size, size)
    pm.fill(QColor('#141f37'))
    p = QPainter(pm)
    for y in range(0, size, 8):
        for x in range(0, size, 8):
            if (x // 8 + y // 8) % 2:
                p.fillRect(x, y, 8, 8, QColor('#1b2843'))
    if qimage is not None and not qimage.isNull():
        img = qimage.scaled(size - 8, size - 8, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        p.drawImage((size - img.width()) // 2, (size - img.height()) // 2, img)
    p.end()
    return QIcon(pm)


class TextureGrid(QListWidget):
    """Every texture of one or more packs as live thumbnails. Items carry (pack rel, entry index)."""
    picked = Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('Grid')
        self.setViewMode(QListWidget.IconMode)
        self.setResizeMode(QListWidget.Adjust)
        self.setMovement(QListWidget.Static)
        self.setUniformItemSizes(True)
        self.setIconSize(QSize(112, 112))
        self.setGridSize(QSize(138, 164))
        self.setWordWrap(True)
        self.setSpacing(2)
        self.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.loaders = []
        self.items = {}
        self.currentItemChanged.connect(self._changed)

    def stop(self):
        for ld in self.loaders:
            ld.stop()
            ld.wait(2000)
        self.loaders = []

    def show_packs(self, packs, overrides=None, filter_text='', hide_maps=False):
        """packs: [(pack rel, Tex)]; overrides: {pack rel: {texture name: png}} from enabled mods.
        hide_maps leaves out normal, roughness, metal and occlusion maps."""
        self.stop()
        self.clear()
        self.items = {}
        overrides = overrides or {}
        ph = placeholder_icon()
        ft = filter_text.lower()
        for rel, tex in packs:
            mods = overrides.get(rel.upper(), {})
            for i, e in enumerate(tex.entries):
                if ft and ft not in e['name'].lower():
                    continue
                if hide_maps and is_surface_map(e['name']):
                    continue
                text = f"{e['name']}\n{e['w']}×{e['h']}" + ('  · Modded' if e['name'] in mods else '')
                it = QListWidgetItem(ph, text)
                it.setData(Qt.UserRole, (rel, i))
                it.setToolTip(f"{e['name']}\n{e['w']} × {e['h']}\n{rel}")
                it.setSizeHint(QSize(134, 160))
                self.addItem(it)
                self.items[(rel, i)] = it
            ld = ThumbLoader(tex, 112, mods, opaque=masked(rel))
            ld.thumb.connect(lambda idx, img, r=rel: self._thumb(r, idx, img))
            self.loaders.append(ld)
        # load one pack after another so the first pack fills in first
        for a, b in zip(self.loaders, self.loaders[1:]):
            a.finished.connect(b.start)
        if self.loaders:
            self.loaders[0].start()
        if self.count():
            self.setCurrentRow(0)

    def _thumb(self, rel, idx, img):
        it = self.items.get((rel, idx))
        if it is not None:
            it.setIcon(framed_icon(img))

    def _changed(self, cur, _prev):
        if cur is not None:
            rel, idx = cur.data(Qt.UserRole)
            self.picked.emit(rel, idx)


SURFACE_MAP = re.compile(r'normal|rough|metal(ness|lic)?\b|[-_]ao\b|ambientocclusion|occlude|specular|[-_]nrm\b', re.I)


def is_surface_map(name):
    return SURFACE_MAP.search(name) is not None


BAT_PACKS = ('NSW/OBJECTS/BATSKINS.TEX', 'NSW/OBJECTS/G4BATTEXTURES.TEX')


class Inspector(QFrame):
    """Preview of the picked texture with Original / Modded, its facts and what you can do with it."""

    def __init__(self, main):
        super().__init__()
        self.main = main
        self.setObjectName('Panel')
        self.setMinimumWidth(320)
        self.setMaximumWidth(400)
        self.cur = None            # (rel, tex, entry)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(14)
        self.title = label('TEXTURE', 'H2', wrap=True)
        lay.addWidget(self.title)
        seg = QHBoxLayout()
        seg.setSpacing(6)
        self.group = QButtonGroup(self)
        self.b_orig = QPushButton('Original')
        self.b_mod = QPushButton('Modded')
        self.b_bat = QPushButton('On a Bat')
        self.b_bat.setCheckable(True)
        self.b_bat.setObjectName('Seg')
        self.b_bat.toggled.connect(lambda _: self._render())
        for b in (self.b_orig, self.b_mod):
            b.setObjectName('Seg')
            b.setCheckable(True)
            self.group.addButton(b)
            seg.addWidget(b)
            b.clicked.connect(self._render)
        self.b_orig.setChecked(True)
        seg.addWidget(self.b_bat)
        self.b_bat.hide()
        lay.addLayout(seg)
        from PySide6.QtWidgets import QStackedWidget
        self.stack = QStackedWidget()
        self.view = ImageView()
        self.view.setMinimumHeight(230)
        self.view.dropped.connect(self.replace_from)
        self.stack.addWidget(self.view)
        self.bat_view = None
        self._bat_model = None
        lay.addWidget(self.stack, 1)
        self.facts = QGridLayout()
        self.facts.setHorizontalSpacing(16)
        self.facts.setVerticalSpacing(6)
        lay.addLayout(self.facts)
        self.note = label('Drop a PNG on the preview to replace it. Smaller mip levels are rebuilt for you.', 'Sub',
                          wrap=True)
        lay.addWidget(self.note)
        self.b_replace = button('Replace With PNG', True, self.replace)
        lay.addWidget(self.b_replace)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.b_export = button('Export PNG', on_click=self.export)
        self.b_revert = button('Revert', on_click=self.revert)
        row.addWidget(self.b_export)
        row.addWidget(self.b_revert)
        lay.addLayout(row)
        self.b_export_all = button('Export Whole Pack', on_click=self.export_all)
        lay.addWidget(self.b_export_all)
        self._enable(False)

    def _enable(self, on):
        for b in (self.b_replace, self.b_export, self.b_export_all, self.b_orig, self.b_mod):
            b.setEnabled(on)
        self.b_revert.setEnabled(False)

    def _set_facts(self, rows):
        if not hasattr(self, '_fact_labels'):
            self._fact_labels = []
            for r in range(5):
                a = label('', 'Sub')
                b = label('', wrap=True)
                b.setTextInteractionFlags(Qt.TextSelectableByMouse)
                self.facts.addWidget(a, r, 0, Qt.AlignTop)
                self.facts.addWidget(b, r, 1)
                self._fact_labels.append((a, b))
            self.facts.setColumnStretch(1, 1)
        for i, (a, b) in enumerate(self._fact_labels):
            if i < len(rows):
                a.setText(rows[i][0])
                b.setText(rows[i][1])
                a.show()
                b.show()
            else:
                a.hide()
                b.hide()

    def show_entry(self, rel, tex, idx):
        e = tex.entries[idx]
        self.cur = (rel, tex, e)
        self.title.setText(e['name'])
        from ..texlib import FORMATS
        fmt = FORMATS.get(e['fmt'], ('?',))[0].upper()
        mod = self.main.mod_png(rel, e['name'])
        rows = [('Size', f"{e['w']} × {e['h']}"), ('Format', f"{fmt}, {e['mips']} mip level{'s' if e['mips'] != 1 else ''}"),
                ('Pack', rel), ('Status', f'Modded in {mod[0].name}' if mod else 'Original')]
        self._set_facts(rows)
        self._enable(True)
        importable = tex.simple(e)
        self.b_replace.setEnabled(importable)
        self.b_replace.setToolTip('' if importable else 'This format can be exported but not replaced yet')
        self.b_mod.setEnabled(bool(mod))
        (self.b_mod if mod else self.b_orig).setChecked(True)
        bat = rel.upper() in BAT_PACKS and not is_surface_map(e['name']) and 'grip' not in e['name'].lower()
        self.b_bat.setVisible(bat)
        if not bat and self.b_bat.isChecked():
            self.b_bat.setChecked(False)
        self.b_revert.setEnabled(bool(self.main.active_mod() and self.main.lib.texture_path(
            self.main.active_mod(), rel, e['name']) and os.path.exists(self.main.lib.texture_path(
                self.main.active_mod(), rel, e['name']))))
        self._render()

    def _render(self):
        if not self.cur:
            return
        rel, tex, e = self.cur
        try:
            mod = self.main.mod_png(rel, e['name'])
            if self.b_mod.isChecked() and mod:
                from PIL import Image
                img = Image.open(mod[1])
            else:
                img = tex.image(e)
            if self.b_bat.isChecked() and self.b_bat.isVisible() and self._show_on_bat(rel, tex, e, img):
                return
            self.stack.setCurrentIndex(0)
            self.view.set_image(pil_to_qimage(for_display(rel, img)))
        except Exception as x:
            self.stack.setCurrentIndex(0)
            self.view.set_image(None, f'Cannot preview this one yet\n{str(x)[:80]}')

    def _show_on_bat(self, rel, tex, e, img):
        """Wrap the texture around the game bat. False when 3D isn't available."""
        from . import viewer3d
        from .. import modellib
        if self.bat_view is None:
            if not viewer3d.available():
                return False
            self.bat_view = viewer3d.ModelView3D(self.main.settings.get('render_quality') == 'high')
            self.bat_view.setMinimumHeight(230)
            self.stack.addWidget(self.bat_view)
        if self._bat_model is None:
            try:
                rel_mod = 'NSW/OBJECTS/G4GAMEBAT.MOD'
                M = modellib.Model.open(self.main.game.original(rel_mod),
                                        self.main.game.original(modellib.gpu_path(rel_mod)))
                parts = []
                for i, d in enumerate(M.draws):
                    if d['name'] in ('bat', 'batGrip_Cross'):
                        p, n, uv, t = M.mesh(i)
                        parts.append((d['name'], p, n, uv, t, M.tangents(i)))
                self._bat_model = parts
            except Exception:
                return False
        normal = None
        if self.bat_view.hq:
            nm = re.sub(r'-color$', '-normal', e['name'])
            hit = tex.find(nm) if nm != e['name'] else []
            if hit:
                try:
                    normal = pil_to_qimage(tex.image(hit[0]))
                except Exception:
                    normal = None
        q = pil_to_qimage(img.convert('RGBA'))
        meshes = []
        for name, p, n, uv, t, tan in self._bat_model:
            grip = 'Grip' in name
            meshes.append(viewer3d.Mesh(p, n, uv, t, color='#20242c' if grip else '#d9b98a',
                                        image=None if grip else q, tan=tan,
                                        normal_map=None if grip else normal, rough=0.45))
        first = not self.bat_view.meshes
        self.bat_view.set_meshes(meshes, '', up='z', keep_camera=not first)
        if first:
            self.bat_view.yaw, self.bat_view.pitch, self.bat_view.dist = 0.9, 0.1, 3.3
        self.stack.setCurrentWidget(self.bat_view)
        return True

    # ---- actions
    def export(self):
        if not self.cur:
            return
        rel, tex, e = self.cur
        path, _ = QFileDialog.getSaveFileName(self, 'Export PNG', os.path.join(self.main.last_dir(), e['name'] + '.png'),
                                              'PNG (*.png)')
        if path:
            self.main.remember_dir(path)
            img = tex.image(e)
            if masked(rel):
                img.convert('RGB').save(path)
                img.split()[3].save(path[:-4] + '_mask.png')
                self.main.toast(f'Exported {os.path.basename(path)} (and its mask)')
            else:
                img.save(path)
                self.main.toast(f'Exported {os.path.basename(path)}')

    def export_all(self):
        if not self.cur:
            return
        rel, tex, _ = self.cur
        folder = QFileDialog.getExistingDirectory(self, 'Export Whole Pack To', self.main.last_dir())
        if not folder:
            return
        out = os.path.join(folder, rel.rsplit('/', 1)[-1])
        os.makedirs(out, exist_ok=True)
        self.main.remember_dir(out)
        self.main.run(lambda job: _export_pack(tex, out, job), f'Exporting {rel}...',
                      lambda n: self.main.toast(f'Exported {n} textures to {out}'))

    def replace(self):
        if not self.cur:
            return
        path, _ = QFileDialog.getOpenFileName(self, 'Replace With PNG', self.main.last_dir(), 'Images (*.png *.jpg *.jpeg)')
        if path:
            self.main.remember_dir(path)
            self.replace_from(path)

    def replace_from(self, path):
        if not self.cur:
            return
        rel, tex, e = self.cur
        if not tex.simple(e):
            QMessageBox.information(self, 'Not Yet', 'This texture format can be exported but not replaced yet.')
            return
        mod = self.main.active_mod(ask=True)
        if not mod:
            return
        from PIL import Image
        img = Image.open(path).convert('RGBA')
        if img.size != (e['w'], e['h']):
            r = QMessageBox.question(self, 'Different Size',
                                     f"Your image is {img.width}×{img.height}; the game uses {e['w']}×{e['h']}.\n\n"
                                     f"Resize it to fit?")
            if r != QMessageBox.Yes:
                return
            img = img.resize((e['w'], e['h']), Image.LANCZOS)
        if masked(rel) and img.split()[3].getextrema()[0] == 255:
            # an opaque PNG keeps the game's mask, so lettering and trim still behave
            img.putalpha(tex.image(e).split()[3])
        self.main.lib.add_texture(mod, rel, e['name'], img)
        self.main.changed(f'{e["name"]} saved to {mod.name}')
        idx = tex.entries.index(e)
        self.show_entry(rel, tex, idx)
        self.b_mod.setChecked(True)
        self._render()

    def revert(self):
        if not self.cur:
            return
        rel, tex, e = self.cur
        mod = self.main.active_mod()
        if mod:
            self.main.lib.remove_texture(mod, rel, e['name'])
            self.main.changed(f'{e["name"]} removed from {mod.name}')
            self.show_entry(rel, tex, tex.entries.index(e))


def _export_pack(tex, out, job):
    n = 0
    total = len(tex.entries)
    seen = {}
    for i, e in enumerate(tex.entries):
        name = e['name']
        seen[name] = seen.get(name, 0) + 1
        fname = name if seen[name] == 1 else f'{name}__{seen[name]}'
        try:
            tex.image(e).save(os.path.join(out, fname + '.png'))
            n += 1
        except Exception:
            pass
        job.progress(i + 1, total)
    return n


class PickModDialog(QDialog):
    """Which mod new changes go into."""

    def __init__(self, parent, mods):
        super().__init__(parent)
        self.setWindowTitle('Save Changes To')
        self.setMinimumWidth(420)
        self.choice = None
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lay.addWidget(label('Pick the mod your change goes into, or start a new one.', 'Soft', wrap=True))
        self.list = QListWidget()
        for m in mods:
            it = QListWidgetItem(m.name)
            it.setData(Qt.UserRole, m.folder)
            self.list.addItem(it)
        self.list.setMinimumHeight(160)
        lay.addWidget(self.list)
        row = QHBoxLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText('New mod name')
        lab = QLabel('New mod')
        lab.setBuddy(self.name)
        row.addWidget(lab)
        row.addWidget(self.name, 1)
        lay.addLayout(row)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText('Use This Mod')
        bb.button(QDialogButtonBox.Ok).setObjectName('Primary')
        bb.accepted.connect(self._ok)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        if mods:
            self.list.setCurrentRow(0)

    def _ok(self):
        if self.name.text().strip():
            self.choice = ('new', self.name.text().strip())
        elif self.list.currentItem():
            self.choice = ('existing', self.list.currentItem().data(Qt.UserRole))
        else:
            return
        self.accept()


class FilterBar(QWidget):
    """A search box plus optional chips."""
    changed = Signal(str)

    def __init__(self, placeholder='Filter textures'):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.setAccessibleName(placeholder)
        self.edit.setClearButtonEnabled(True)
        self.edit.textChanged.connect(self.changed.emit)
        lay.addWidget(self.edit, 1)
        from PySide6.QtWidgets import QCheckBox
        self.maps = QCheckBox('Show surface maps')
        self.maps.setToolTip('Normal, roughness, metal and occlusion maps. They look strange on their own; '
                             'most mods only change the colour textures.')
        self.maps.toggled.connect(lambda _: self.changed.emit(self.edit.text()))
        lay.addWidget(self.maps)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
