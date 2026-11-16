"""A design as a graph: the game data on the left, the rules in the middle, the pieces on the right, and a wire for
everything a piece shows or waits on. It is another way to look at the same design the Layers list edits: click a
piece to pick it, drag from a data box onto a piece to wire it up."""
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QComboBox, QGraphicsItem, QGraphicsPathItem, QGraphicsScene, QGraphicsView

from .. import uibuild
from . import theme

W_DATA, W_RULE, W_PIECE, ROW, GAP = 250, 170, 270, 30, 8
X_DATA, X_RULE, X_PIECE = 0, 360, 640
OPS = {'==': 'is', '!=': 'is not', '>': 'is more than', '>=': 'is at least', '<': 'is less than', '<=': 'is at most'}
TEAMS = {'away': 'Away team', 'home': 'Home team'}
WIRES = {'shows': '#58a6ff', 'when': '#ffd24a', 'team': '#3fb950'}


def rule_parts(rule):
    """A rule as [(data, words)] and how they are joined ('and', 'or' or '')."""
    for key, word in (('all', 'and'), ('any', 'or')):
        if key in rule:
            return [(r.get('data', ''), f'{OPS.get(r.get("is", "=="), "is")} {r.get("value", 1)}')
                    for r in rule[key] if r], word
    return [(rule.get('data', ''), f'{OPS.get(rule.get("is", "=="), "is")} {rule.get("value", 1)}')], ''


class Box(QGraphicsItem):
    """One box of the graph. kind: 'data', 'rule' or 'piece'. key: the query, or the piece's place in the list."""

    def __init__(self, kind, key, title, x, y, w, sub='', indent=0):
        super().__init__()
        self.kind, self.key, self.title, self.sub, self.w, self.indent = kind, key, title, sub, w, indent
        self.setPos(x + indent, y)
        self.chosen = False
        self.setAcceptHoverEvents(True)
        self.setToolTip({'data': 'Game data. Drag it onto a piece: a text shows it, anything else waits for it.',
                         'rule': 'A rule: the piece it leads to is drawn only while it holds.',
                         'piece': 'A piece of the design. Click to pick it.'}[kind] + (f'\n{sub}' if sub else ''))

    def boundingRect(self):
        return QRectF(0, 0, self.w - self.indent, ROW)

    def port(self, right):
        r = self.boundingRect()
        return self.mapToScene(QPointF(r.right() if right else r.left(), r.center().y()))

    def paint(self, qp, _opt, _widget=None):
        r = self.boundingRect()
        fill = {'data': theme.S2, 'rule': theme.S2, 'piece': theme.S1}[self.kind]
        qp.setRenderHint(QPainter.Antialiasing)
        qp.setBrush(QBrush(QColor(fill)))
        qp.setPen(QPen(QColor('#ffd54a' if self.chosen else theme.AMBER if self.kind == 'rule' else theme.LINE),
                      2 if self.chosen else 1))
        qp.drawRoundedRect(r.adjusted(1, 1, -1, -1), 7, 7)
        f = QFont(qp.font())
        f.setPointSizeF(9)
        qp.setFont(f)
        qp.setPen(QColor(theme.TEXT))
        text = qp.fontMetrics().elidedText(self.title, Qt.ElideRight, int(r.width()) - 20)
        qp.drawText(r.adjusted(10, 0, -10, 0), Qt.AlignVCenter | Qt.AlignLeft, text)


class DesignGraph(QGraphicsView):
    picked = Signal(int)                 # a piece was clicked: its place in the design's list
    wired = Signal(str, int)             # data was dragged onto a piece: the query, the piece's place

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.Antialiasing)
        self.setBackgroundBrush(QColor(theme.BG))
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setMinimumHeight(320)
        self._wire = None                # (the data box the drag started on, the line being drawn)
        self._press = None
        self.extra = []                  # data boxes added by hand, waiting to be wired
        self.boxes = {}
        self._design, self._chosen = None, -1
        self.more = QComboBox(self)      # bring in data the design does not use yet
        self.more.addItem('Add a data box…', None)
        for group, rows in uibuild.CATALOG:
            for name, q in rows:
                self.more.addItem(f'{group}: {name}', q)
        for q in uibuild.ASK:
            if q not in {x for _g, rows in uibuild.CATALOG for _n, x in rows}:
                self.more.addItem('Rules: ' + uibuild.data_name(q), q)
        for side in TEAMS.values():
            self.more.addItem('Teams: ' + side, side)
        self.more.setToolTip('Put a box of game data in the graph, then drag it onto a piece')
        self.more.activated.connect(self._more)
        self.more.setFixedWidth(theme.d(250))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.more.move(self.viewport().width() - self.more.width() - 12, 8)

    def _more(self, i):
        q = self.more.itemData(i)
        self.more.setCurrentIndex(0)
        if q and q not in self.extra:
            self.extra.append(q)
            self.show_design(self._design, self._chosen)
            if ('data', q) in self.boxes:
                self.ensureVisible(self.boxes['data', q], 40, 60)

    def show_design(self, design, chosen=-1):
        sc = self.scene()
        sc.clear()
        self.boxes, self._wire = {}, None
        self._design, self._chosen = design, chosen
        pieces = list(uibuild.walk((design or {}).get('pieces') or []))
        data, links, rules = [], [], []          # links: (from box key, to box key, kind of wire)

        def need(q):
            q = uibuild.bare(q)
            if q and q not in data:
                data.append(q)
            return ('data', q)
        for i, (p, _depth, _home, _where, _in) in enumerate(pieces):
            kind = uibuild.kind_of(p)
            for q in p.get('data') or []:
                links.append((need(q), ('piece', i), 'shows'))
            if kind == 'switch':
                links.append((need(p['switch']), ('piece', i), 'when'))
            side = p.get('tint') or (p.get(kind) if kind in ('team', 'logo') else None)
            if side in TEAMS:
                links.append((need(TEAMS[side]), ('piece', i), 'team'))
            if p.get('when'):
                parts, join = rule_parts(p['when'])
                key = ('rule', len(rules))
                rules.append((key, f' {join} '.join(f'{uibuild.data_name(d)} {words}' for d, words in parts), i))
                for d, _words in parts:
                    links.append((need(d), key, 'when'))
                links.append((key, ('piece', i), 'when'))
        for q in self.extra:
            need(q)
        # each data box sits near the pieces it feeds, so the wires cross as little as they can
        feeds = {}
        for a, b, _kind in links:
            if a[0] == 'data':
                row = b[1] if b[0] == 'piece' else rules[b[1]][2]
                feeds.setdefault(a[1], []).append(row)
        data.sort(key=lambda q: (sum(feeds[q]) / len(feeds[q]) if q in feeds else 1e9))
        y = 34
        for q in data:
            self._add(Box('data', q, uibuild.data_name(q), X_DATA, y, W_DATA, q))
            y += ROW + GAP
        py = 34
        rule_y = {}
        for i, (p, depth, _home, where, _in) in enumerate(pieces):
            b = self._add(Box('piece', i, where + uibuild.describe(p), X_PIECE, py, W_PIECE, indent=min(depth, 4) * 14))
            b.chosen = i == chosen
            rule_y[i] = py
            py += ROW + GAP
        for key, title, i in rules:
            self._add(Box('rule', key[1], title, X_RULE, rule_y[i], W_RULE, title))
        head = QFont(self.font())
        head.setPointSizeF(8)
        for x, text in ((X_DATA, 'GAME DATA'), (X_RULE, 'RULES'), (X_PIECE, 'PIECES')):
            t = sc.addSimpleText(text, head)
            t.setBrush(QColor(theme.MUTED))
            t.setPos(x + 4, 6)
        for a, b, kind in links:
            if a in self.boxes and b in self.boxes:
                self._link(self.boxes[a], self.boxes[b], kind)
        sc.setSceneRect(-20, -6, X_PIECE + W_PIECE + 40, max(y, py) + 30)
        if 0 <= chosen < len(pieces):
            self.ensureVisible(self.boxes['piece', chosen], 40, 60)

    def _add(self, box):
        self.scene().addItem(box)
        box.setZValue(2)
        self.boxes[box.kind, box.key] = box
        return box

    def _curve(self, a, b):
        path = QPainterPath(a)
        dx = max(40.0, (b.x() - a.x()) / 2)
        path.cubicTo(a + QPointF(dx, 0), b - QPointF(dx, 0), b)
        return path

    def _link(self, a, b, kind):
        item = QGraphicsPathItem(self._curve(a.port(True), b.port(False)))
        item.setPen(QPen(QColor(WIRES[kind]), 1.6))
        item.setZValue(1)
        item.setOpacity(0.85)
        self.scene().addItem(item)

    def _box_at(self, pos):
        for it in self.items(pos):
            if isinstance(it, Box):
                return it
        return None

    def mousePressEvent(self, e):
        b = self._box_at(e.position().toPoint())
        self._press = b
        if b is not None and b.kind == 'data' and e.button() == Qt.LeftButton:
            line = QGraphicsPathItem()
            line.setPen(QPen(QColor('#ffffff'), 1.6, Qt.DashLine))
            line.setZValue(3)
            self.scene().addItem(line)
            self._wire = (b, line)
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._wire:
            b, line = self._wire
            line.setPath(self._curve(b.port(True), self.mapToScene(e.position().toPoint())))
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        target = self._box_at(e.position().toPoint())
        if self._wire:
            b, line = self._wire
            self.scene().removeItem(line)
            self._wire = None
            if target is not None and target.kind == 'piece':
                self.wired.emit(str(b.key), int(target.key))
            return
        pick = None
        if target is not None and target is self._press:
            if target.kind == 'piece':
                pick = int(target.key)
            elif target.kind == 'rule':                    # a rule belongs to the piece it leads to
                pick = next((int(key) for (kind, key), box in self.boxes.items()
                             if kind == 'piece' and abs(box.y() - target.y()) < 1), None)
        super().mouseReleaseEvent(e)
        if pick is not None:                               # last: picking redraws the graph
            self.picked.emit(pick)
