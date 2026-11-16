"""Move and scale UI layouts (the scorebug) on a 1920x1080 screen, drawn with their real textures, saved into the
active mod. Click a piece to see which texture it is and replace it."""
import os

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QColorDialog, QComboBox, QDoubleSpinBox, QFileDialog, QHBoxLayout, QListView,
                               QListWidget, QListWidgetItem, QMessageBox, QVBoxLayout, QWidget)

from .. import uilayout
from . import theme
from .common import button, label
from .widgets import pil_to_qimage

PRESETS = [('Game default', None), ('Bottom right', (1390, 838)), ('Bottom left', (40, 838)),
           ('Top right', (1390, 40)), ('Top left', (40, 40)), ('Bottom centre', (723, 860))]


class Canvas(QWidget):
    moved = Signal(float, float)
    picked = Signal(int)           # index into pieces, -1 for none

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(300)
        self.rect_ = None          # (x, y, w, h) in screen pixels
        self.scale = 1.0
        self.label = ''
        self.pieces = []           # [(dx, dy, w, h, argb, pixmap or None)] parts inside the box, relative to it
        self.chosen = -1
        self._drag = None
        self._moved = False

    def _fit(self):
        W, H = self.width() - 20, self.height() - 20
        k = min(W / 1920, H / 1080)
        ox, oy = (self.width() - 1920 * k) / 2, 10
        return k, ox, oy

    def paintEvent(self, e):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing)
        k, ox, oy = self._fit()
        screen = QRectF(ox, oy, 1920 * k, 1080 * k)
        qp.fillRect(self.rect(), QColor(theme.BG))
        # a hint of a ballgame: grass, dirt and the TV safe area
        qp.setClipRect(screen)
        qp.fillRect(screen, QColor('#1f4d2e'))
        qp.setPen(Qt.NoPen)
        qp.setBrush(QColor('#7a5534'))
        qp.drawEllipse(QPointF(ox + 960 * k, oy + 1180 * k), 520 * k, 420 * k)
        qp.setPen(QPen(QColor(255, 255, 255, 60), 1, Qt.DashLine))
        qp.setBrush(Qt.NoBrush)
        qp.drawRect(QRectF(ox + 96 * k, oy + 54 * k, 1728 * k, 972 * k))
        qp.setPen(QPen(QColor(theme.LINE), 1))
        qp.drawRect(screen)
        f = QFont(self.font())
        f.setPointSizeF(8)
        qp.setFont(f)
        if self.rect_:
            x, y, w, h = self.rect_
            s = self.scale
            r = QRectF(ox + x * k, oy + y * k, w * s * k, h * s * k)
            qp.setPen(Qt.NoPen)
            qp.setBrush(QColor(10, 20, 40, 150))
            qp.drawRoundedRect(r, 4, 4)
            qp.setRenderHint(QPainter.SmoothPixmapTransform)
            drawn = False
            for i, (dx, dy, pw, ph, argb, pm) in enumerate(self.pieces):
                pr = self._piece_rect(r, i, k)
                if pm is not None:
                    qp.drawPixmap(pr, pm, QRectF(pm.rect()))
                    drawn = True
                    continue
                rgb = argb & 0xffffff
                c = QColor(120, 160, 230, 30) if rgb in (0xffffff, 0) else \
                    QColor((argb >> 16) & 255, (argb >> 8) & 255, argb & 255, 110)
                qp.setPen(QPen(QColor(255, 255, 255, 30), 1))
                qp.setBrush(c)
                qp.drawRect(pr)
            if 0 <= self.chosen < len(self.pieces):
                qp.setPen(QPen(QColor('#ffd54a'), 2))
                qp.setBrush(Qt.NoBrush)
                qp.drawRect(self._piece_rect(r, self.chosen, k))
            qp.setPen(QPen(QColor(theme.RED), 2))
            qp.setBrush(Qt.NoBrush)
            qp.drawRoundedRect(r, 4, 4)
            if not drawn:
                qp.setPen(QColor('white'))
                f.setPointSizeF(9)
                f.setBold(True)
                qp.setFont(f)
                qp.drawText(r, Qt.AlignCenter, self.label)
        qp.end()

    def _box(self):
        k, ox, oy = self._fit()
        x, y, w, h = self.rect_
        return QRectF(ox + x * k, oy + y * k, w * self.scale * k, h * self.scale * k), k

    def _piece_rect(self, r, i, k):
        dx, dy, pw, ph = self.pieces[i][:4]
        s = self.scale
        return QRectF(r.x() + dx * s * k, r.y() + dy * s * k, pw * s * k, ph * s * k)

    def mousePressEvent(self, e):
        if self.rect_:
            self._drag = (e.position(), self.rect_[0], self.rect_[1])
            self._moved = False

    def mouseMoveEvent(self, e):
        if self._drag and self.rect_:
            p0, x0, y0 = self._drag
            k, _, _ = self._fit()
            if (e.position() - p0).manhattanLength() < 4 and not self._moved:
                return
            self._moved = True
            d = (e.position() - p0) / k
            x = max(-200, min(1920, x0 + d.x()))
            y = max(-200, min(1080, y0 + d.y()))
            self.rect_ = (round(x), round(y), self.rect_[2], self.rect_[3])
            self.moved.emit(self.rect_[0], self.rect_[1])
            self.update()

    def mouseReleaseEvent(self, e):
        if self._drag and not self._moved and self.rect_:
            # a click, not a drag: pick the smallest textured piece under the pointer
            r, k = self._box()
            best, area = -1, None
            for i, p in enumerate(self.pieces):
                if p[5] is not None and self._piece_rect(r, i, k).contains(e.position()):
                    a = p[2] * p[3]
                    if area is None or a < area:
                        best, area = i, a
            self.chosen = best
            self.picked.emit(best)
            self.update()
        self._drag = None


class LayoutEditor(QWidget):
    """Edit where a theme's scorebug sits. One .NSW layout per scorebug theme."""
    HINT = 'Drag the red box to place it. Pick a piece below to tint, fade, move, resize or repaint it. Save writes the layout into your mod.'

    def __init__(self, main):
        super().__init__()
        self.main = main
        self.rel = None
        self.layout = None
        self.asset = None
        self.node = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.which = QComboBox()
        self.which.setMinimumWidth(200)
        self.which.currentIndexChanged.connect(self._asset_changed)
        row.addWidget(self.which, 2)
        self.preset = QComboBox()
        for name, _ in PRESETS:
            self.preset.addItem(name)
        self.preset.activated.connect(self._preset)
        row.addWidget(self.preset, 1)
        self.sx = self._spin(-200, 1920, 0)
        self.sy = self._spin(-200, 1080, 0)
        self.sx.setPrefix('X  ')
        self.sy.setPrefix('Y  ')
        self.sx.valueChanged.connect(self._spins)
        self.sy.valueChanged.connect(self._spins)
        row.addWidget(self.sx, 1)
        row.addWidget(self.sy, 1)
        self.sscale = self._spin(0.5, 2.0, 2)
        self.sscale.setSingleStep(0.05)
        self.sscale.setValue(1.0)
        self.sscale.setPrefix('Scale  ')
        self.sscale.setToolTip('Beta: the game reads scale from the layout, but not every theme honours it')
        self.sscale.valueChanged.connect(self._spins)
        row.addWidget(self.sscale, 1)
        lay.addLayout(row)
        self.canvas = Canvas()
        self.canvas.moved.connect(self._dragged)
        self.canvas.picked.connect(self._picked)
        lay.addWidget(self.canvas, 1)
        self._pack, self._table, self._pix_cache, self._piece_tex = None, {}, {}, []
        self.strip = QListWidget()          # every texture the chosen overlay draws
        self.strip.setViewMode(QListView.IconMode)
        self.strip.setFlow(QListView.LeftToRight)
        self.strip.setWrapping(False)
        self.strip.setMovement(QListView.Static)
        self.strip.setIconSize(QSize(64, 44))
        self.strip.setGridSize(QSize(112, 78))
        self.strip.setFixedHeight(104)
        self.strip.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.strip.setToolTip('The textures this overlay is made of. Pick one to replace it.')
        self.strip.currentItemChanged.connect(self._strip_picked)
        lay.addWidget(self.strip)
        # the chosen piece: tint, opacity, a nudge and a size, applied to every place the overlay draws it
        tools = QHBoxLayout()
        tools.setSpacing(8)
        self.b_tint = button('Colour', on_click=self._tint)
        self.p_op = self._spin(0, 100, 0)
        self.p_op.setPrefix('Opacity  ')
        self.p_op.setSuffix(' %')
        self.p_dx = self._spin(-960, 960, 0)
        self.p_dx.setPrefix('Move X  ')
        self.p_dy = self._spin(-540, 540, 0)
        self.p_dy.setPrefix('Move Y  ')
        self.p_size = self._spin(25, 400, 0)
        self.p_size.setPrefix('Size  ')
        self.p_size.setSuffix(' %')
        self.b_piece = button('Replace PNG', on_click=self._replace_piece)
        self._tools = (self.b_tint, self.p_op, self.p_dx, self.p_dy, self.p_size, self.b_piece)
        for w in self._tools:
            w.setEnabled(False)
            tools.addWidget(w, 1)
        for sp in (self.p_op, self.p_dx, self.p_dy, self.p_size):
            sp.valueChanged.connect(self._piece_edit)
        self.tools_row = QWidget()
        self.tools_row.setLayout(tools)
        tools.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.tools_row)
        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        self.note = label(self.HINT, 'Sub', wrap=True)
        bottom.addWidget(self.note, 1)
        self.b_reset = button('Back to Default', on_click=self.reset)
        self.b_save = button('Save to My Mod', True, self.save)
        bottom.addWidget(self.b_reset)
        bottom.addWidget(self.b_save)
        lay.addLayout(bottom)

    @staticmethod
    def _spin(lo, hi, dec):
        s = QDoubleSpinBox()
        s.setRange(lo, hi)
        s.setDecimals(dec)
        s.setMinimumWidth(90)
        return s

    def open(self, pack_rel):
        """pack_rel: the theme's texture pack, e.g. NSW/UI/GAME/THEME1.TEX."""
        rel = pack_rel[:-4] + '.NSW'
        self.rel = rel
        self.which.blockSignals(True)
        self.which.clear()
        if rel not in self.main.game.file_set():
            self.layout = None
            self.asset = self.node = None
            self.canvas.rect_ = None
            self.canvas.pieces = []
            self._enable(False)
            self.note.setText('This pack has no layout file.')
            self.strip.clear()
            self.strip.hide()
            self.tools_row.hide()
            self.which.blockSignals(False)
            self.canvas.update()
            return
        self._pack, self._table, self._pix_cache = pack_rel, {}, {}
        try:
            tex = self.main.tex(pack_rel)
            self._table = uilayout.Layout.texture_table([e['name'] for e in tex.entries]) if tex else {}
        except Exception:
            self._table = {}
        try:
            self.layout = uilayout.Layout.open(self.main.current_file(rel))
            self._orig = uilayout.Layout.open(self.main.game.original(rel))
        except Exception as x:
            self.layout = None
            self.note.setText(f'Could not read the layout: {x}')
            self.which.blockSignals(False)
            return
        names = []
        for a in self.layout.assets:
            if not a.name.startswith('asset_') and a.container() is not None:
                names.append(a.name)
        first = ('Scorebar', 'BottomTicker')
        names = sorted(set(names), key=lambda n: (first.index(n) if n in first else len(first), n))
        if not names:
            self.layout = None
            self.asset = self.node = None
            self.canvas.rect_ = None
            self.canvas.pieces = []
            self.note.setText('This pack’s layout has no overlays the manager can place yet.')
            self.which.blockSignals(False)
            self.canvas.update()
            self._enable(False)
            return
        self._enable(True)
        self.note.setText(self.HINT)
        for n in names:
            self.which.addItem(n)
        self.which.blockSignals(False)
        self._asset_changed()

    def _enable(self, on):
        for w in (self.which, self.preset, self.sx, self.sy, self.sscale, self.b_reset, self.b_save):
            w.setEnabled(on)

    def _asset_changed(self, *_, keep=False):
        if not self.layout or not self.which.currentText():
            return
        if not keep:
            self._chosen_tex = None
            for w in self._tools:
                w.setEnabled(False)
        self.asset = self.layout.find(self.which.currentText())
        self.node = self.asset.container() if self.asset else None
        if self.node is None:
            self.canvas.rect_ = None
            self.canvas.update()
            return
        n = self.node
        for s in (self.sx, self.sy, self.sscale):
            s.blockSignals(True)
        self.sx.setValue(n.x)
        self.sy.setValue(n.y)
        self.sscale.setValue(n.sx / 0x80 if n.sx else 1.0)
        for s in (self.sx, self.sy, self.sscale):
            s.blockSignals(False)
        self._scale0 = self.sscale.value()
        cx, cy, _, _ = n.abs_rect()
        pieces = []
        for m in self.asset.nodes():
            p, inside = m.parent, False
            while p is not None:
                if p is n:
                    inside = True
                    break
                p = p.parent
            if inside and m.w > 1 and m.h > 1:
                mx, my, _, _ = m.abs_rect()
                name = self._table.get(m.ref)
                if not name and (mx - cx < -4 or my - cy < -4 or mx - cx + m.w > n.w + 4 or my - cy + m.h > n.h + 4):
                    continue
                if name and not m.color >> 24:
                    continue                      # fully transparent: a state that isn't showing
                pieces.append((mx - cx, my - cy, m.w, m.h, m.color, self._pix(name, m.color) if name else None, name))
        pieces = pieces[:400]
        if not keep:
            self._fill_strip()
            self.canvas.chosen = -1
        self._piece_tex = [p[6] for p in pieces]
        self.canvas.pieces = [p[:6] for p in pieces]
        if not keep:
            self.note.setText(self.HINT)
        self.canvas.rect_ = (n.x, n.y, n.w, n.h)
        self.canvas.scale = self.sscale.value()
        self.canvas.label = self.asset.name
        self.canvas.update()

    def _pix(self, name, argb):
        """The texture as the layout tints it (colour and opacity), small enough to draw quickly."""
        key = (name, argb)
        if key in self._pix_cache:
            return self._pix_cache[key]
        pm = None
        try:
            import numpy as np
            from PIL import Image
            hit = self.main.mod_png(self._pack, name)
            mod = self.main.active_mod()
            own = self.main.lib.texture_path(mod, self._pack, name) if mod else None
            if own and os.path.exists(own):
                img = Image.open(own).convert('RGBA')
            elif hit and os.path.exists(hit[1]):
                img = Image.open(hit[1]).convert('RGBA')
            else:
                tex = self.main.tex(self._pack)
                e = next(e for e in tex.entries if e['name'] == name)
                img = tex.image(e).convert('RGBA')
            img.thumbnail((256, 256))
            a = np.asarray(img, np.float32)
            tint = np.array([(argb >> 16) & 255, (argb >> 8) & 255, argb & 255, (argb >> 24) & 255], np.float32) / 255
            pm = QPixmap.fromImage(pil_to_qimage(Image.fromarray((a * tint).astype(np.uint8), 'RGBA')))
        except Exception:
            pm = None
        self._pix_cache[key] = pm
        return pm

    def _fill_strip(self):
        self.strip.blockSignals(True)
        self.strip.clear()
        seen = []
        for m in self.asset.nodes() if self.asset else []:
            for h in (m.ref, m.ref2):
                name = self._table.get(h)
                if name and name not in seen:
                    seen.append(name)
        for name in seen[:300]:
            pm = self._pix(name, 0xFFFFFFFF)
            tile = QPixmap(64, 44)                 # every thumbnail on the same tile, so the row lines up
            tile.fill(Qt.transparent)
            if pm is not None and not pm.isNull():
                fit = pm.scaled(64, 44, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                qp = QPainter(tile)
                qp.drawPixmap((64 - fit.width()) // 2, (44 - fit.height()) // 2, fit)
                qp.end()
            it = QListWidgetItem(QIcon(tile), name if len(name) < 16 else name[:14] + '…')
            it.setData(Qt.UserRole, name)
            it.setToolTip(name)
            it.setTextAlignment(Qt.AlignHCenter | Qt.AlignBottom)
            self.strip.addItem(it)
        self.strip.blockSignals(False)
        self.strip.setVisible(bool(seen))
        self.tools_row.setVisible(bool(seen))

    def _piece_nodes(self, name):
        """[(node, the same node in the untouched layout)] for every place the overlay draws this texture."""
        if not (self.asset and name):
            return []
        h = uilayout.name_hash(name)
        orig = next((a for a in self._orig.assets if a.hash == self.asset.hash), None)
        mine, theirs = self.asset.nodes(), orig.nodes() if orig else []
        if len(mine) != len(theirs):
            theirs = mine
        return [(n, o) for n, o in zip(mine, theirs) if o.ref == h or n.ref == h]

    def _strip_picked(self, item, _old=None):
        name = item.data(Qt.UserRole) if item else None
        self._chosen_tex = name
        pairs = self._piece_nodes(name)
        for w in self._tools:
            w.setEnabled(bool(pairs))
        self.b_piece.setEnabled(bool(name))
        if not pairs:
            if name:
                self.note.setText(f'“{name}” is a second layer of a piece. It can be repainted with Replace PNG.')
            return
        n, o = pairs[0]
        for sp, v in ((self.p_op, round((n.color >> 24) / 2.55)), (self.p_dx, n.x - o.x), (self.p_dy, n.y - o.y),
                      (self.p_size, round(100 * n.w / o.w) if o.w else 100)):
            sp.blockSignals(True)
            sp.setValue(v)
            sp.blockSignals(False)
        uses = 'once' if len(pairs) == 1 else f'{len(pairs)} times'
        self.note.setText(f'“{name}” is drawn {uses} in this overlay. Changes here apply to every one.')

    def _piece_edit(self, *_):
        for n, o in self._piece_nodes(getattr(self, '_chosen_tex', None)):
            self.layout.recolor(n, alpha=round(self.p_op.value() * 2.55))
            self.layout.move(n, o.x + self.p_dx.value(), o.y + self.p_dy.value())
            k = self.p_size.value() / 100
            self.layout.resize(n, o.w * k, o.h * k)
        self._refresh_canvas()

    def _tint(self):
        pairs = self._piece_nodes(getattr(self, '_chosen_tex', None))
        if not pairs:
            return
        c0 = pairs[0][0].color
        c = QColorDialog.getColor(QColor((c0 >> 16) & 255, (c0 >> 8) & 255, c0 & 255), self, 'Tint')
        if c.isValid():
            for n, _ in pairs:
                self.layout.recolor(n, rgb=(c.red(), c.green(), c.blue()))
            self._refresh_canvas()

    def _refresh_canvas(self):
        row = self.strip.currentRow()
        self._asset_changed(keep=True)
        if row >= 0:
            self.strip.blockSignals(True)
            self.strip.setCurrentRow(row)
            self.strip.blockSignals(False)

    def _picked(self, i):
        """A piece clicked on the screen: choose it in the strip."""
        name = self._piece_tex[i] if 0 <= i < len(self._piece_tex) else None
        if name:
            for k in range(self.strip.count()):
                if self.strip.item(k).data(Qt.UserRole) == name:
                    self.strip.setCurrentRow(k)
                    break
        elif self.layout and not self.strip.currentItem():
            self.note.setText(self.HINT)

    def _replace_piece(self):
        name = getattr(self, '_chosen_tex', None)
        if not name:
            return
        path, _ = QFileDialog.getOpenFileName(self, f'Replace {name}', self.main.last_dir(), 'Images (*.png)')
        if not path:
            return
        self.main.remember_dir(path)
        mod = self.main.active_mod(ask=True)
        if not mod:
            return
        try:
            from PIL import Image
            tex = self.main.tex(self._pack)
            e = next(e for e in tex.entries if e['name'] == name)
            img = Image.open(path).convert('RGBA')
            if img.size != (e['w'], e['h']) and not tex.can_grow(e, img.size):
                img = img.resize((e['w'], e['h']), Image.LANCZOS)
            self.main.lib.add_texture(mod, self._pack, name, img)
        except Exception as x:
            QMessageBox.warning(self, 'Could Not Replace', str(x))
            return
        self._pix_cache = {k: v for k, v in self._pix_cache.items() if k[0] != name}
        self.main.changed(f'{name} saved to {mod.name}')
        self._asset_changed()
        for i in range(self.strip.count()):
            if self.strip.item(i).data(Qt.UserRole) == name:
                self.strip.setCurrentRow(i)

    def _dragged(self, x, y):
        for s, v in ((self.sx, x), (self.sy, y)):
            s.blockSignals(True)
            s.setValue(v)
            s.blockSignals(False)
        self._apply()

    def _spins(self, *_):
        if self.canvas.rect_:
            r = self.canvas.rect_
            self.canvas.rect_ = (self.sx.value(), self.sy.value(), r[2], r[3])
            self.canvas.scale = self.sscale.value()
            self.canvas.update()
        self._apply()

    def _preset(self, i):
        _, pos = PRESETS[i]
        if self.node is None:
            return
        if pos is None:
            o = self._orig.find(self.asset.name)
            oc = o.container() if o else None
            pos = (oc.x, oc.y) if oc else (self.node.x, self.node.y)
        self.sx.setValue(pos[0])
        self.sy.setValue(pos[1])

    def _apply(self):
        if self.layout and self.node:
            self.layout.move(self.node, self.sx.value(), self.sy.value())
            if abs(self.sscale.value() - self._scale0) > 1e-6:
                self.layout.scale(self.node, self.sscale.value())

    def reset(self):
        self.sscale.setValue(1.0)
        self._preset(0)
        if self.layout and self.asset:               # and every piece back to how the game has it
            orig = next((a for a in self._orig.assets if a.hash == self.asset.hash), None)
            mine, theirs = self.asset.nodes(), orig.nodes() if orig else []
            if len(mine) == len(theirs):
                cont = self.node
                for n, o in zip(mine, theirs):
                    if n is cont:
                        continue
                    if (n.color, n.x, n.y, n.w, n.h, n.ref) != (o.color, o.x, o.y, o.w, o.h, o.ref):
                        self.layout.recolor(n, rgb=((o.color >> 16) & 255, (o.color >> 8) & 255, o.color & 255),
                                            alpha=o.color >> 24)
                        self.layout.move(n, o.x, o.y)
                        self.layout.resize(n, o.w, o.h)
            self._asset_changed()

    def save(self):
        if not self.layout:
            return
        data = self.layout.bytes()

        def write(path):
            with open(path, 'wb') as f:
                f.write(data)
        try:
            self.main.save_file(self.rel, write,
                                self.which.currentText() + ' layout saved into {mod}. Apply, then check it in a game.')
        except Exception as x:
            QMessageBox.warning(self, 'Could Not Save', str(x))
