"""Small animations. All of them do nothing when Reduce Motion is on (theme.MOTION False)."""
from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QTimer
from PySide6.QtWidgets import QGraphicsOpacityEffect

from . import theme


def fade_in(widgets, stagger=40, duration=220):
    """Widgets appear one after another. The opacity effect is taken off again when each is done, so it costs
    nothing afterwards."""
    if not theme.MOTION:
        return
    for i, w in enumerate(widgets):
        if w.graphicsEffect() is not None:
            continue
        fx = QGraphicsOpacityEffect(w)
        fx.setOpacity(0.0)
        w.setGraphicsEffect(fx)
        a = QPropertyAnimation(fx, b'opacity', w)
        a.setDuration(duration)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.OutCubic)
        a.finished.connect(lambda w=w: w.setGraphicsEffect(None))
        QTimer.singleShot(i * stagger, a.start)
        w._fade = a


def rise(widget, end, by=14, duration=180):
    """Slides a free-floating widget (not one in a layout) up into place."""
    if not theme.MOTION:
        widget.move(end)
        return
    a = QPropertyAnimation(widget, b'pos', widget)
    a.setDuration(duration)
    a.setStartValue(QPoint(end.x(), end.y() + by))
    a.setEndValue(end)
    a.setEasingCurve(QEasingCurve.OutCubic)
    a.start()
    widget._rise = a
