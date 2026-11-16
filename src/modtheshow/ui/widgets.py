from PySide6.QtCore import Property, QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QAbstractButton, QWidget

from . import theme


def pil_to_qimage(img):
    img = img.convert('RGBA')
    data = img.tobytes('raw', 'RGBA')
    return QImage(data, img.width, img.height, img.width * 4, QImage.Format_RGBA8888).copy()


class Toggle(QAbstractButton):
    """An on/off switch."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(44, 24)
        self._pos = 0.0
        self._anim = QPropertyAnimation(self, b'pos', self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._go)

    def _go(self, on):
        self._anim.stop()
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def setChecked(self, on):
        super().setChecked(on)
        self._anim.stop()
        self._pos = 1.0 if on else 0.0
        self.update()

    def getPos(self):
        return self._pos

    def setPos(self, v):
        self._pos = v
        self.update()

    pos = Property(float, getPos, setPos)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        off, on = QColor(theme.LINE_HI), QColor(theme.RED)
        c = QColor(int(off.red() + (on.red() - off.red()) * self._pos),
                   int(off.green() + (on.green() - off.green()) * self._pos),
                   int(off.blue() + (on.blue() - off.blue()) * self._pos))
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawRoundedRect(QRectF(0, 0, 44, 24), 12, 12)
        p.setBrush(QColor('white'))
        p.drawEllipse(QPointF(12 + 20 * self._pos, 12), 9, 9)


class ImageView(QWidget):
    """Texture preview on a checkerboard: fits the window, wheel zooms, drag pans. Accepts dropped PNGs."""
    dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumSize(240, 200)
        self.pix = None
        self.zoom = None          # None = fit
        self.offset = QPointF(0, 0)
        self._drag = None
        self.message = 'Pick a texture'
        tile = QPixmap(16, 16)
        tile.fill(QColor(theme.CHECK_A))
        tp = QPainter(tile)
        tp.fillRect(0, 0, 8, 8, QColor(theme.CHECK_B))
        tp.fillRect(8, 8, 8, 8, QColor(theme.CHECK_B))
        tp.end()
        self.checker = QBrush(tile)

    def set_image(self, qimage, message=''):
        self.pix = QPixmap.fromImage(qimage) if qimage is not None else None
        self.zoom, self.offset = None, QPointF(0, 0)
        self.message = message
        self.update()

    def _scale(self):
        if self.zoom is not None:
            return self.zoom
        w, h = self.pix.width(), self.pix.height()
        return min((self.width() - 24) / w, (self.height() - 24) / h, 8.0)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        p.fillRect(self.rect(), QColor(theme.S1))
        if not self.pix:
            p.setPen(QColor(theme.MUTED))
            p.drawText(self.rect(), Qt.AlignCenter, self.message)
            return
        s = self._scale()
        w, h = self.pix.width() * s, self.pix.height() * s
        r = QRectF((self.width() - w) / 2 + self.offset.x(), (self.height() - h) / 2 + self.offset.y(), w, h)
        p.fillRect(r, self.checker)
        if s >= 2:
            p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        p.drawPixmap(r, self.pix, QRectF(self.pix.rect()))
        p.setPen(QPen(QColor(theme.LINE)))
        p.drawRect(r)

    def wheelEvent(self, e):
        if not self.pix:
            return
        s = self._scale() * (1.2 if e.angleDelta().y() > 0 else 1 / 1.2)
        self.zoom = max(0.05, min(32.0, s))
        self.update()

    def mouseDoubleClickEvent(self, _):
        self.zoom, self.offset = None, QPointF(0, 0)
        self.update()

    def mousePressEvent(self, e):
        self._drag = e.position()

    def mouseMoveEvent(self, e):
        if self._drag is not None and self.pix:
            self.offset += e.position() - self._drag
            self._drag = e.position()
            self.update()

    def mouseReleaseEvent(self, _):
        self._drag = None

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() and any(u.toLocalFile().lower().endswith('.png') for u in e.mimeData().urls()):
            e.acceptProposedAction()

    def dropEvent(self, e):
        for u in e.mimeData().urls():
            if u.toLocalFile().lower().endswith('.png'):
                self.dropped.emit(u.toLocalFile())
                break


class RatingSlider(QWidget):
    """A labelled 0-99 slider with its value beside it, the way ratings screens show them."""
    valueChanged = Signal(int)

    def __init__(self, text, lo=0, hi=99):
        super().__init__()
        from PySide6.QtWidgets import QHBoxLayout, QLabel, QSlider
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        self.name = QLabel(text)
        self.name.setObjectName('Sub')
        self.name.setMinimumWidth(96)
        lay.addWidget(self.name)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(lo, hi)
        self.slider.setPageStep(5)
        lay.addWidget(self.slider, 1)
        self.value_label = QLabel('0')
        self.value_label.setObjectName('RatingValue')
        self.value_label.setMinimumWidth(30)
        self.value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(self.value_label)
        self.slider.valueChanged.connect(self._changed)

    def _changed(self, v):
        self.value_label.setText(str(v))
        self.value_label.setProperty('tier', 'diamond' if v >= 85 else 'gold' if v >= 75 else 'silver' if v >= 65
                                     else 'bronze' if v >= 50 else 'common')
        self.value_label.style().unpolish(self.value_label)
        self.value_label.style().polish(self.value_label)
        self.valueChanged.emit(v)

    def value(self):
        return self.slider.value()

    def setValue(self, v):
        self.slider.setValue(int(v))
        self._changed(self.slider.value())

    def blockSignals(self, b):
        self.slider.blockSignals(b)
        return super().blockSignals(b)
