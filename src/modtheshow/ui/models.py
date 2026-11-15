"""3D Models: browse the game's models, look at them, export OBJ, swap meshes."""
import os
import tempfile

import numpy as np
from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPolygonF
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QHBoxLayout, QLineEdit,
                               QListWidget, QListWidgetItem, QMessageBox, QSplitter, QVBoxLayout, QWidget)

from .. import batshapes, modellib
from . import theme
from .common import SectionTitle, button, header, label, panel

CATEGORIES = [('All Models', ''), ('Bats & Game Objects', 'NSW/OBJECTS/'), ('Stadium Props', 'NSW/STADIUMS/'),
              ('Player Gear', 'NSW/CHARACTERS/'), ('Everything Else', '*')]
MESH_COLORS = ['#d9b98a', '#9fb4d9', '#c9c2b0', '#b8d0a2', '#d9a3a3', '#a9a3d9', '#d0c38a', '#8ec9c4']
MAX_LIST = 2500


class ModelView(QWidget):
    """Flat-shaded preview. Drag to turn, wheel to zoom, double-click to reset."""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(320)
        self.setMouseTracking(False)
        self.meshes = []        # (positions, tris, color, visible)
        self.highlight = None
        self.reset()
        self._drag = None
        self._fast = False
        self._settle = QTimer(self, singleShot=True, interval=160, timeout=self._full)
        self.message = 'Pick a model on the left'

    def reset(self):
        self.yaw, self.pitch, self.zoom = 0.65, 0.35, 1.0
        self.update()

    def set_meshes(self, meshes, message=''):
        self.meshes = meshes
        self.message = message
        self.highlight = None
        allp = [m[0] for m in meshes if len(m[0])]
        if allp:
            p = np.concatenate(allp)
            self.center = (p.min(0) + p.max(0)) / 2
            self.radius = float(np.linalg.norm(p - self.center, axis=1).max()) or 1.0
        self.update()

    def _full(self):
        self._fast = False
        self.update()

    def mousePressEvent(self, e):
        self._drag = (e.position(), self.yaw, self.pitch)

    def mouseMoveEvent(self, e):
        if self._drag:
            p0, y0, x0 = self._drag
            d = e.position() - p0
            self.yaw = y0 + d.x() * 0.01
            self.pitch = float(np.clip(x0 + d.y() * 0.01, -1.5, 1.5))
            self._fast = True
            self._settle.start()
            self.update()

    def mouseReleaseEvent(self, e):
        self._drag = None

    def mouseDoubleClickEvent(self, e):
        self.reset()

    def wheelEvent(self, e):
        self.zoom = float(np.clip(self.zoom * (1.15 if e.angleDelta().y() > 0 else 1 / 1.15), 0.2, 12))
        self._fast = True
        self._settle.start()
        self.update()

    def paintEvent(self, e):
        qp = QPainter(self)
        qp.fillRect(self.rect(), QColor(theme.BG))
        # checker floor dots for a sense of scale
        qp.setPen(QColor('#16233d'))
        for x in range(0, self.width(), 24):
            for y in range(0, self.height(), 24):
                qp.drawPoint(x, y)
        vis = [m for m in self.meshes if m[3] and len(m[1])]
        if not vis:
            qp.setPen(QColor(theme.MUTED))
            qp.drawText(self.rect(), Qt.AlignCenter | Qt.TextWordWrap, self.message)
            return
        cy, sy, cx, sx = np.cos(self.yaw), np.sin(self.yaw), np.cos(self.pitch), np.sin(self.pitch)
        ry = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])      # turn around the model's z
        rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
        rot = rx @ ry
        scale = min(self.width(), self.height()) * 0.46 / self.radius * self.zoom
        w2, h2 = self.width() / 2, self.height() / 2
        budget = 12000 if self._fast else 60000
        total = sum(len(m[1]) for m in vis)
        step = max(1, total // budget)
        polys, depth, shade, cols = [], [], [], []
        light = np.array([0.35, -0.55, 0.76])
        light /= np.linalg.norm(light)
        for idx, (p, tris, color, _) in enumerate(vis):
            t = tris[::step]
            q = (p - self.center) @ rot.T          # x right, y depth, z up
            tri = q[t]
            nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
            ln = np.linalg.norm(nrm, axis=1)
            ok = ln > 1e-12
            tri, nrm, ln = tri[ok], nrm[ok], ln[ok]
            nrm /= ln[:, None]
            s = np.abs(nrm @ light) * 0.78 + 0.22
            polys.append(tri)
            depth.append(tri[:, :, 1].mean(1))
            shade.append(s)
            cols.append(np.full(len(tri), idx))
        tri = np.concatenate(polys)
        order = np.argsort(-np.concatenate(depth))
        shade = np.concatenate(shade)[order]
        cols = np.concatenate(cols)[order]
        tri = tri[order]
        sx2 = w2 + tri[:, :, 0] * scale
        sy2 = h2 - tri[:, :, 2] * scale
        qp.setPen(Qt.NoPen)
        base = [QColor(m[2]) for m in vis]
        rgb = np.array([[c.red(), c.green(), c.blue()] for c in base], np.float32)
        fill = (rgb[cols] * shade[:, None]).clip(0, 255).astype(np.int32)
        for k in range(len(tri)):
            r, g, b = fill[k]
            qp.setBrush(QColor(int(r), int(g), int(b)))
            qp.drawPolygon(QPolygonF([QPointF(sx2[k, 0], sy2[k, 0]), QPointF(sx2[k, 1], sy2[k, 1]),
                                      QPointF(sx2[k, 2], sy2[k, 2])]))
        qp.setPen(QColor(theme.MUTED))
        qp.drawText(12, self.height() - 12, 'Drag to turn  ·  Wheel to zoom  ·  Double-click to reset')


class ModelsPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.setObjectName('Page')
        self.main = main
        self.loaded = False
        self.rel = None
        self.model = None
        self.editor = None
        self.all = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(18)
        outer.addWidget(header('3D Models', 'Look at any bat, ball or stadium prop, export it to OBJ for Blender, '
                                            'and put your own geometry back in. Edits are saved into your mod.'))
        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(16)
        # left: list
        left = panel()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(10, 10, 10, 10)
        ll.setSpacing(8)
        self.cat = QComboBox()
        for name, _ in CATEGORIES:
            self.cat.addItem(name)
        self.cat.setCurrentIndex(1)
        self.cat.currentIndexChanged.connect(self._filter)
        ll.addWidget(self.cat)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Find a model')
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _: self._debounce.start())
        ll.addWidget(self.search)
        self._debounce = QTimer(self, singleShot=True, interval=200, timeout=self._filter)
        self.list = QListWidget()
        self.list.setStyleSheet('QListWidget { border: none; padding: 0; background: transparent; }')
        self.list.currentItemChanged.connect(self._picked)
        ll.addWidget(self.list, 1)
        self.count = label('', 'Sub')
        ll.addWidget(self.count)
        left.setMinimumWidth(240)
        left.setMaximumWidth(330)
        split.addWidget(left)
        # middle: viewer
        mid = panel()
        ml = QVBoxLayout(mid)
        ml.setContentsMargins(18, 18, 18, 18)
        ml.setSpacing(12)
        self.title = SectionTitle('Model')
        ml.addWidget(self.title)
        self.path = label('', 'Sub', wrap=True)
        ml.addWidget(self.path)
        self.view = ModelView()
        ml.addWidget(self.view, 1)
        split.addWidget(mid)
        # right: meshes and actions
        right = panel()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(18, 18, 18, 18)
        rl.setSpacing(10)
        rl.addWidget(SectionTitle('Meshes'))
        self.facts = label('', 'Soft', wrap=True)
        rl.addWidget(self.facts)
        self.meshes = QListWidget()
        self.meshes.setStyleSheet('QListWidget { border: none; padding: 0; background: transparent; }')
        self.meshes.itemChanged.connect(self._mesh_toggled)
        rl.addWidget(self.meshes, 1)
        self.fit = QCheckBox('Fit imported OBJ to the original mesh size')
        self.fit.setChecked(True)
        rl.addWidget(self.fit)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.b_export = button('Export OBJ', on_click=self.export_obj)
        self.b_hide = button('Hide Mesh', on_click=self.hide_mesh)
        row.addWidget(self.b_export, 1)
        row.addWidget(self.b_hide, 1)
        rl.addLayout(row)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.b_revert = button('Revert Model', on_click=self.revert)
        self.b_replace = button('Replace With OBJ', True, self.replace_obj)
        row.addWidget(self.b_revert, 1)
        row.addWidget(self.b_replace, 1)
        rl.addLayout(row)
        # scale tool
        rl.addSpacing(6)
        rl.addWidget(label('SCALE SELECTED MESH', 'Group'))
        row = QHBoxLayout()
        row.setSpacing(8)
        self.sx, self.sy, self.sz = (self._spin() for _ in range(3))
        for nm, sp in (('X', self.sx), ('Y', self.sy), ('Z', self.sz)):
            sp.setPrefix(f'{nm}  ')
            sp.setMinimumWidth(66)
            row.addWidget(sp, 1)
        self.b_scale = button('Scale', on_click=self.scale_mesh)
        self.b_scale.setMinimumWidth(72)
        row.addWidget(self.b_scale)
        rl.addLayout(row)
        # bat shapes, only for the game bat
        self.bat_box = QWidget()
        bl = QVBoxLayout(self.bat_box)
        bl.setContentsMargins(0, 6, 0, 0)
        bl.setSpacing(8)
        bl.addWidget(label('BAT SHAPES', 'Group'))
        bl.addWidget(label('Reshapes every bat in the game at once. Textures and grip tape stay lined up.', 'Sub', wrap=True))
        row = QHBoxLayout()
        row.setSpacing(8)
        self.preset = QComboBox()
        self.preset.addItems(list(batshapes.PRESETS))
        self.thick = self._spin(0.5, 2.0)
        self.thick.setToolTip('Thickness')
        self.thick.setPrefix('Thick  ')
        self.thick.setMinimumWidth(110)
        row.addWidget(self.preset, 1)
        row.addWidget(self.thick)
        rl.addWidget(self.bat_box)
        bl.addLayout(row)
        self.b_shape = button('Reshape All Bats', True, self.reshape_bats)
        bl.addWidget(self.b_shape)
        self.bat_box.hide()
        right.setMinimumWidth(330)
        right.setMaximumWidth(400)
        split.addWidget(right)
        split.setStretchFactor(1, 1)
        split.setSizes([270, 700, 360])
        outer.addWidget(split, 1)
        self._enable(False)

    def _spin(self, lo=0.05, hi=20.0):
        s = QDoubleSpinBox()
        s.setRange(lo, hi)
        s.setSingleStep(0.1)
        s.setDecimals(2)
        s.setValue(1.0)
        s.setMinimumWidth(70)
        return s

    def _enable(self, on, editable=False):
        self.b_export.setEnabled(on)
        for b in (self.b_hide, self.b_replace, self.b_scale, self.b_shape):
            b.setEnabled(on and editable)
        self.b_revert.setEnabled(on and bool(self.rel and (self._own(self.rel) or self._own(modellib.gpu_path(self.rel)))))

    # ---------------------------------------------------------- list
    def showEvent(self, e):
        super().showEvent(e)
        if not self.loaded:
            self.loaded = True
            files = set(self.main.game.files)
            self.all = sorted(f for f in files if modellib.is_model(f) and modellib.gpu_path(f) in files)
            self._filter()

    def _filter(self):
        q = self.search.text().strip().upper()
        _, pre = CATEGORIES[self.cat.currentIndex()]
        known = [p for _, p in CATEGORIES if p not in ('', '*')]
        hits = []
        for f in self.all:
            if pre == '*':
                if any(f.startswith(k) for k in known):
                    continue
            elif pre and not f.startswith(pre):
                continue
            if q and q not in f:
                continue
            hits.append(f)
        self.list.clear()
        for f in hits[:MAX_LIST]:
            parts = f.split('/')
            where = parts[2] if len(parts) > 3 and parts[1] in ('STADIUMS', 'CHARACTERS') else ''
            if where in ('PROPS', 'ACCESSORIES', 'MASTERFILES') and len(parts) > 4:
                where = parts[3] if parts[1] == 'CHARACTERS' else 'Shared'
            it = QListWidgetItem(parts[-1][:-4] + (f'   ·   {where.title()}' if where else ''))
            it.setData(Qt.UserRole, f)
            it.setToolTip(f)
            self.list.addItem(it)
        more = f'  (showing {MAX_LIST})' if len(hits) > MAX_LIST else ''
        self.count.setText(f'{len(hits):,} model{"" if len(hits) == 1 else "s"}{more}')

    def _picked(self, cur, _prev):
        if cur:
            self.open(cur.data(Qt.UserRole))

    # ---------------------------------------------------------- loading
    def _own(self, rel):
        """The active mod's copy of a file, even when that mod is switched off."""
        mod = self.main.active_mod()
        if mod:
            p = os.path.join(mod.path, 'romfs', *rel.split('/'))
            if os.path.exists(p):
                return mod, p
        return self.main.mod_file(rel)

    def _paths(self, rel):
        """Current files for a model: the active mod's copy, else the winning mod's, else the original."""
        mod, gmod = self._own(rel), self._own(modellib.gpu_path(rel))
        d = mod[1] if mod else self.main.game.original(rel)
        g = gmod[1] if gmod else self.main.game.original(modellib.gpu_path(rel))
        return d, g, bool(mod or gmod)

    def open(self, rel):
        self.rel = rel
        d, g, modded = self._paths(rel)
        name = rel.rsplit('/', 1)[-1][:-4]
        self.path.setText(f'romfs/{rel}' + ('   ·   from your mod' if modded else ''))
        self.meshes.blockSignals(True)
        self.meshes.clear()
        self.meshes.blockSignals(False)
        self.bat_box.setVisible(rel == batshapes.BAT)
        try:
            self.model = modellib.Model.open(d, g)
        except Exception as x:
            self.model = self.editor = None
            self.title.set(name, ['Not readable'])
            self.facts.setText(str(x))
            self.view.set_meshes([], f'This model can\'t be shown yet.\n{x}')
            self._enable(False)
            return
        M = self.model
        self.editor = modellib.Editor(M) if M.editable else None
        self.title.set(name, [f'{len(M.draws)} mesh' + ('es' if len(M.draws) != 1 else ''),
                              'Modded' if modded else 'Original'] + ([] if M.editable else ['View Only']))
        mn, mx = M.bounds()
        size = mx - mn
        tris = sum(d['icount'] for d in M.draws) // 3
        self.facts.setText(f'{M.vbo_info[0][0]:,} vertices  ·  {tris:,} triangles\n'
                           f'Size {size[0]:.2f} × {size[1]:.2f} × {size[2]:.2f}  ·  layout {M.layout_name}' +
                           ('' if M.editable else '\nSkinned to a skeleton. Viewing and editing these comes next.'))
        self.meshes.blockSignals(True)
        for i, dr in enumerate(M.draws):
            it = QListWidgetItem(f'{dr["name"]}   ·   {dr["icount"] // 3:,} tris')
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if i == 0 or not self._is_alt(M, i) else Qt.Unchecked)
            it.setForeground(QColor(MESH_COLORS[i % len(MESH_COLORS)]))
            self.meshes.addItem(it)
        self.meshes.blockSignals(False)
        if self.meshes.count():
            self.meshes.setCurrentRow(0)
        self._redraw()
        self._enable(True, M.editable)

    @staticmethod
    def _is_alt(M, i):
        """The bat file holds several alternative bats on top of each other; show only the standard one by default."""
        names = [d['name'] for d in M.draws]
        return names[0] == 'bat' and names[i] not in ('bat', 'batGrip_Cross')

    def _mesh_data(self, i):
        if self.editor:
            pos = self.editor.get(i, 'POSITION')[:, :3]
            tris = self.editor.parts[i]['idx'].astype(np.int64).reshape(-1, 3)
            return pos, tris
        try:
            p, _, _, t = self.model.mesh(i)
            return p, t
        except Exception:
            return np.zeros((0, 3)), np.zeros((0, 3), np.int64)

    def _redraw(self):
        if not self.model:
            return
        meshes = []
        for i in range(len(self.model.draws)):
            it = self.meshes.item(i)
            p, t = self._mesh_data(i)
            meshes.append((p, t, MESH_COLORS[i % len(MESH_COLORS)], it.checkState() == Qt.Checked))
        self.view.set_meshes(meshes, 'Turn a mesh on in the list to see it')

    def _mesh_toggled(self, _it):
        self._redraw()

    def _selected(self):
        r = self.meshes.currentRow()
        if r < 0:
            QMessageBox.information(self, 'Pick a Mesh', 'Pick a mesh in the list first.')
        return r

    # ---------------------------------------------------------- actions
    def export_obj(self):
        if not self.model:
            return
        name = self.rel.rsplit('/', 1)[-1][:-4]
        start = os.path.join(self.main.settings.get('last_dir', os.path.expanduser('~')), name + '.obj')
        out, _ = QFileDialog.getSaveFileName(self, 'Export OBJ', start, 'Wavefront OBJ (*.obj)')
        if not out:
            return
        self.main.settings['last_dir'] = os.path.dirname(out)
        visible = [i for i in range(self.meshes.count()) if self.meshes.item(i).checkState() == Qt.Checked]
        if self.editor:
            d, g = self.editor.save()
            modellib.Model(d, g).write_obj(out, visible or None)
        else:
            self.model.write_obj(out, visible or None)
        self.main.toast(f'Exported {os.path.basename(out)} ({len(visible) or len(self.model.draws)} meshes)')

    def _save(self, message):
        mod = self.main.active_mod(ask=True)
        if not mod:
            return False
        d, g = self.editor.save()
        tmp = tempfile.mkdtemp(prefix='mts_')
        for rel, data in ((self.rel, d), (modellib.gpu_path(self.rel), g)):
            p = os.path.join(tmp, os.path.basename(rel))
            with open(p, 'wb') as f:
                f.write(data)
            self.main.lib.add_file(mod, rel, p)
        off = '' if mod.enabled else ' That mod is switched off in Mods, so turn it on before applying.'
        self.main.changed(f'{message}. Saved to {mod.name}.{off}')
        self.open(self.rel)
        return True

    def replace_obj(self):
        i = self._selected()
        if i < 0 or not self.editor:
            return
        path, _ = QFileDialog.getOpenFileName(self, 'Replace Mesh With OBJ', self.main.settings.get('last_dir', ''),
                                              'Wavefront OBJ (*.obj)')
        if not path:
            return
        self.main.settings['last_dir'] = os.path.dirname(path)
        try:
            P, N, T, tris = modellib.read_obj(path)
            if self.fit.isChecked():
                old = self.editor.get(i, 'POSITION')[:, :3]
                omn, omx = old.min(0), old.max(0)
                nmn, nmx = P.min(0), P.max(0)
                s = float((omx - omn).max() / max((nmx - nmn).max(), 1e-9))
                P = (P - (nmn + nmx) / 2) * s + (omn + omx) / 2
            self.editor.replace(i, P, N, T, tris)
        except Exception as x:
            QMessageBox.warning(self, 'Could Not Use That OBJ', str(x))
            return
        name = self.model.draws[i]['name']
        self._save(f'{name} replaced with {os.path.basename(path)} ({len(tris):,} triangles)')

    def hide_mesh(self):
        i = self._selected()
        if i < 0 or not self.editor:
            return
        self.editor.hide(i)
        self._save(f'{self.model.draws[i]["name"]} hidden')

    def scale_mesh(self):
        i = self._selected()
        if i < 0 or not self.editor:
            return
        pos = self.editor.get(i, 'POSITION')
        p = pos[:, :3]
        c = (p.min(0) + p.max(0)) / 2
        f = np.array([self.sx.value(), self.sy.value(), self.sz.value()])
        new = pos.copy()
        new[:, :3] = (p - c) * f + c
        self.editor.put(i, 'POSITION', new)
        n = self.editor.get(i, 'NORMAL')
        if n is not None:
            v = n[:, :3] / f
            n = n.copy()
            n[:, :3] = v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9)
            self.editor.put(i, 'NORMAL', n)
        self._save(f'{self.model.draws[i]["name"]} scaled')

    def reshape_bats(self):
        if not self.editor or self.rel != batshapes.BAT:
            return
        # always start from the original bat so presets don't stack
        M = modellib.Model.open(self.main.game.original(self.rel), self.main.game.original(modellib.gpu_path(self.rel)))
        self.editor = modellib.Editor(M)
        self.model = M
        batshapes.apply(self.editor, self.preset.currentText(), self.thick.value())
        self._save(f'Every bat is now a {self.preset.currentText()}')

    def revert(self):
        if not self.rel:
            return
        hit = self._own(self.rel) or self._own(modellib.gpu_path(self.rel))
        if not hit:
            return
        owner = hit[0]
        if QMessageBox.question(self, 'Revert Model', f'Remove this model from {owner.name}?') != QMessageBox.Yes:
            return
        for rel in (self.rel, modellib.gpu_path(self.rel)):
            h = self._own(rel)
            if h and h[0].folder == owner.folder:
                try:
                    os.remove(h[1])
                except OSError:
                    pass
        self.main.changed(f'Model reverted in {owner.name}')
        self.open(self.rel)

    def refresh_overrides(self):
        if self.rel and self.isVisible():
            self.open(self.rel)
