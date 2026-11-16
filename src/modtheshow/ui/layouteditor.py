"""Move and scale UI layouts (the scorebug) on a 1920x1080 screen, saved into the active mod."""
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QHBoxLayout, QMessageBox, QVBoxLayout, QWidget

from .. import uilayout
from . import theme
from .common import button, label

PRESETS = [('Game default', None), ('Bottom right', (1390, 838)), ('Bottom left', (40, 838)),
           ('Top right', (1390, 40)), ('Top left', (40, 40)), ('Bottom centre', (723, 860))]


class Canvas(QWidget):
    moved = Signal(float, float)

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(300)
        self.rect_ = None          # (x, y, w, h) in screen pixels
        self.scale = 1.0
        self.label = ''
        self.pieces = []           # [(dx, dy, w, h, argb)] parts inside the box, relative to it
        self._drag = None

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
            for dx, dy, pw, ph, argb in self.pieces:
                rgb = argb & 0xffffff
                c = QColor(120, 160, 230, 45) if rgb in (0xffffff, 0) else \
                    QColor((argb >> 16) & 255, (argb >> 8) & 255, argb & 255, 150)
                pr = QRectF(r.x() + dx * s * k, r.y() + dy * s * k, pw * s * k, ph * s * k)
                qp.setPen(QPen(QColor(255, 255, 255, 40), 1))
                qp.setBrush(c)
                qp.drawRect(pr)
            qp.setPen(QPen(QColor(theme.RED), 2))
            qp.setBrush(Qt.NoBrush)
            qp.drawRoundedRect(r, 4, 4)
            qp.setPen(QColor('white'))
            f.setPointSizeF(9)
            f.setBold(True)
            qp.setFont(f)
            qp.drawText(r, Qt.AlignCenter, self.label)
        qp.end()

    def mousePressEvent(self, e):
        if self.rect_:
            self._drag = (e.position(), self.rect_[0], self.rect_[1])

    def mouseMoveEvent(self, e):
        if self._drag and self.rect_:
            p0, x0, y0 = self._drag
            k, _, _ = self._fit()
            d = (e.position() - p0) / k
            x = max(-200, min(1920, x0 + d.x()))
            y = max(-200, min(1080, y0 + d.y()))
            self.rect_ = (round(x), round(y), self.rect_[2], self.rect_[3])
            self.moved.emit(self.rect_[0], self.rect_[1])
            self.update()

    def mouseReleaseEvent(self, e):
        self._drag = None


class LayoutEditor(QWidget):
    """Edit where a theme's scorebug sits. One .NSW layout per scorebug theme."""

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
        lay.addWidget(self.canvas, 1)
        bottom = QHBoxLayout()
        self.note = label('Drag the red box or type a position. Save writes this layout into your mod.', 'Sub', wrap=True)
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
            self.which.blockSignals(False)
            self.canvas.update()
            return
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
        self.note.setText('Drag the red box or type a position. Save writes this layout into your mod.')
        for n in names:
            self.which.addItem(n)
        self.which.blockSignals(False)
        self._asset_changed()

    def _enable(self, on):
        for w in (self.which, self.preset, self.sx, self.sy, self.sscale, self.b_reset, self.b_save):
            w.setEnabled(on)

    def _asset_changed(self, *_):
        if not self.layout or not self.which.currentText():
            return
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
                if mx - cx < -4 or my - cy < -4 or mx - cx + m.w > n.w + 4 or my - cy + m.h > n.h + 4:
                    continue
                pieces.append((mx - cx, my - cy, m.w, m.h, m.color))
        self.canvas.pieces = pieces[:400]
        self.canvas.rect_ = (n.x, n.y, n.w, n.h)
        self.canvas.scale = self.sscale.value()
        self.canvas.label = self.asset.name
        self.canvas.update()

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
