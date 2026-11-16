"""The scoreboard sandbox: a UI layout (the scorebug and the other overlays) drawn the way the game lays it out, with
its real textures. Drag the overlay to place it, click any piece to tint, fade, move, resize, hide or repaint it, flip
the layout's states to see each look, and save the result into the active mod."""
import os

import json
import re
import time
import zipfile

from PySide6.QtCore import QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog, QDoubleSpinBox, QFileDialog,
                               QGridLayout, QHBoxLayout, QFrame, QInputDialog, QLineEdit, QListView, QListWidget, QListWidgetItem, QMenu,
                               QMessageBox, QPushButton, QScrollArea, QSlider, QSpinBox, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from .. import boards, fontlib, recipes, samples, teamart, uibuild, uilang, uilayout, uiquery, uirender
from . import theme
from .common import button, label
from .graphview import TEAMS, DesignGraph
from .widgets import pil_to_qimage

PRESETS = [('Game default', None), ('Bottom right', (1390, 838)), ('Bottom left', (40, 838)),
           ('Top right', (1390, 40)), ('Top left', (40, 40)), ('Bottom centre', (723, 860))]
BACKDROP = (31, 77, 46, 255)
MOTIONS = [('No motion', None), ('Fade in', {'frames': 20}), ('From the left', {'from': [-60, 0], 'frames': 20}),
           ('From the right', {'from': [60, 0], 'frames': 20}), ('From above', {'from': [0, -40], 'frames': 20}),
           ('From below', {'from': [0, 40], 'frames': 20})]


class TeamColours(QDialog):
    """Where a design's team colours come from, and the clubs that get a colour of your own: one for every uniform,
    one for City Connect."""
    SOURCES = (('The uniform each team is wearing', 'uniform'), ('The club, whatever it wears', 'club'))

    def __init__(self, parent, design):
        super().__init__(parent)
        self.setWindowTitle('Team Colours')
        self.colors = {k: v for k, v in uibuild.team_keys(design.get('team_colors')).items()}
        v = QVBoxLayout(self)
        v.setContentsMargins(*[theme.d(18)] * 4)
        v.setSpacing(theme.d(12))
        v.addWidget(label('TEAM COLOUR COMES FROM', 'StripLabel'))
        self.source = QComboBox()
        for text, key in self.SOURCES:
            self.source.addItem(text, key)
        self.source.setCurrentIndex(max(0, self.source.findData(design.get('team_color', 'uniform'))))
        v.addWidget(self.source)
        v.addWidget(label('The game colours a team by the cap of the uniform it has on, so alternates, throwbacks '
                          'and City Connect each bring their own. Give a club a colour of yours below and the '
                          'design uses it instead: in every uniform, only in City Connect, or one for each.',
                          'Sub', wrap=True))
        v.addWidget(label('YOUR COLOURS', 'StripLabel'))
        grid = QGridLayout()
        grid.setHorizontalSpacing(theme.d(8))
        grid.setVerticalSpacing(theme.d(6))
        self.cells = {}
        clubs = sorted(teamart.ORDER)
        for i, club in enumerate(clubs):                       # three even blocks of ten
            r, c = i % 10 + 1, (i // 10) * 4
            grid.addWidget(label(club, 'Sub'), r, c)
            for j, kind in enumerate(('any', 'cc')):
                b = QPushButton()
                b.setFixedSize(theme.d(92), theme.d(28))
                b.clicked.connect(lambda _=False, club=club, kind=kind: self._pick(club, kind))
                self.cells[club, kind] = b
                grid.addWidget(b, r, c + 1 + j)
        for block in range(3):
            grid.addWidget(label('Every uniform', 'Sub'), 0, block * 4 + 1)
            grid.addWidget(label('City Connect', 'Sub'), 0, block * 4 + 2)
            if block < 2:
                grid.setColumnMinimumWidth(block * 4 + 3, theme.d(18))
        v.addLayout(grid)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(button('Cancel', on_click=self.reject))
        row.addWidget(button('Use These', True, self.accept))
        v.addLayout(row)
        self._paint()

    def _paint(self):
        for (club, kind), b in self.cells.items():
            c = self.colors.get(club, {}).get(kind)
            b.setText('' if c else 'Game’s')
            b.setToolTip(f'{club}: {c}. Click to change it or go back to the game’s colour.' if c else
                         f'{club}: the game’s colour. Click to give it one of yours.')
            b.setStyleSheet(f'QPushButton {{ background: {c}; border: 1px solid {theme.LINE}; border-radius: 8px; '
                            'padding: 0; }' if c else
                            f'QPushButton {{ background: transparent; border: 1px dashed {theme.LINE}; '
                                      f'border-radius: 8px; color: {theme.MUTED}; font-size: 11px; padding: 0; }}')

    def _pick(self, club, kind):
        now = self.colors.get(club, {}).get(kind)
        if now:
            menu = QMenu(self)
            change = menu.addAction('Pick another colour…')
            clear = menu.addAction('Back to the game’s colour')
            act = menu.exec(self.cells[club, kind].mapToGlobal(self.cells[club, kind].rect().bottomLeft()))
            if act is clear:
                self.colors[club].pop(kind, None)
                self._paint()
            if act is not change:
                return
        start = now or '#%02x%02x%02x' % teamart.color(club)
        c = QColorDialog.getColor(QColor(start), self, f'{club}: {"City Connect" if kind == "cc" else "every uniform"}')
        if c.isValid():
            self.colors.setdefault(club, {})[kind] = c.name()
            self._paint()

    def result_into(self, design):
        out = {}
        for club in teamart.ORDER:
            c = self.colors.get(club) or {}
            if c.get('any'):
                out[club] = c['any']
            if c.get('cc'):
                out[club + ' CC'] = c['cc']
        if out:
            design['team_colors'] = out
        else:
            design.pop('team_colors', None)
        if self.source.currentData() == 'uniform':
            design.pop('team_color', None)
        else:
            design['team_color'] = self.source.currentData()


class Layers(QTreeWidget):
    """The pieces of a design as a tree, back to front, nested the way they are grouped."""
    activated = Signal(int)
    renamed = Signal(int)

    def __init__(self):
        super().__init__()
        self.setHeaderHidden(True)
        self.setRootIsDecorated(False)
        self.setIndentation(theme.d(14))
        self.setFixedHeight(theme.d(216))
        self._rows, self._quiet = [], False
        self.currentItemChanged.connect(lambda *_: None if self._quiet else self.activated.emit(self.currentIndex()))
        self.itemDoubleClicked.connect(lambda *_: self.renamed.emit(self.currentIndex()))

    def fill(self, rows):
        """rows: [(words, depth)] in drawing order."""
        self._quiet = True
        self.clear()
        self._rows, stack = [], []
        for text, depth in rows:
            it = QTreeWidgetItem([text])
            del stack[depth:]
            if stack:
                stack[-1].addChild(it)
            else:
                self.addTopLevelItem(it)
            stack.append(it)
            self._rows.append(it)
        self.expandAll()
        self._quiet = False

    def count(self):
        return len(self._rows)

    def currentIndex(self):
        it = self.currentItem()
        return next((i for i, r in enumerate(self._rows) if r is it), -1)

    def setCurrentIndex(self, i):
        self._quiet = True
        self.setCurrentItem(self._rows[i] if 0 <= i < len(self._rows) else None)
        self._quiet = False

    def itemText(self, i):
        return self._rows[i].text(0)

    def currentText(self):
        it = self.currentItem()
        return it.text(0) if it else ''


class Canvas(QWidget):
    moved = Signal(float, float)
    released = Signal()
    picked = Signal(int)           # index into hits, -1 for none
    nudged = Signal(float, float)  # a piece was dragged this far, in screen pixels

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(320)
        self.pixmap = None         # the whole 1920x1080 screen as drawn
        self.rect_ = None          # the overlay's frame (x, y, w, h) on that screen
        self.hits = []             # [(x, y, w, h, is_text)] for every drawn piece, last on top
        self.chosen = -1
        self.marks = []            # other places the chosen texture is drawn
        self.offset = (0, 0)       # live drag offset, until the picture is redrawn
        self.base = (0, 0)         # where the overlay was when the picture was drawn
        self.view = (0, 0, 1920, 1080)   # the part of the screen shown
        self.screen = (1920, 1080)       # the size of what is drawn: the TV picture, or a stadium board
        self.backdrop = BACKDROP[:3]
        self.safe = True                 # draw the TV safe area
        self.empty = 'Pick a scorebug theme'
        self._drag = None
        self._moved = False
        self.grab = None           # in a design: grab(x, y) -> the frame of the piece to drag from there, or None
        self._piece = None         # (where the drag started, the piece's frame)
        self.piece_off = None      # how far the piece being dragged has moved

    def _fit(self):
        W, H = self.width() - 20, self.height() - 20
        vx, vy, vw, vh = self.view
        k = min(W / vw, H / vh)
        ox = (self.width() - vw * k) / 2 - vx * k
        oy = (self.height() - vh * k) / 2 - vy * k
        return k, ox, oy

    def paintEvent(self, e):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing)
        qp.setRenderHint(QPainter.SmoothPixmapTransform)
        k, ox, oy = self._fit()
        sw, sh = self.screen
        screen = QRectF(ox, oy, sw * k, sh * k)
        qp.fillRect(self.rect(), QColor(theme.BG))
        qp.setClipRect(screen)
        qp.fillRect(screen, QColor(*self.backdrop))
        if self.pixmap is not None:
            dx, dy = self.offset
            qp.drawPixmap(QRectF(ox + dx * k, oy + dy * k, sw * k, sh * k), self.pixmap, QRectF(self.pixmap.rect()))
        qp.setBrush(Qt.NoBrush)
        if self.safe:
            qp.setPen(QPen(QColor(255, 255, 255, 50), 1, Qt.DashLine))
            qp.drawRect(QRectF(ox + 96 * k, oy + 54 * k, 1728 * k, 972 * k))   # the TV safe area
        dx, dy = self.offset
        for (x, y, w, h, is_text) in self.hits:
            if is_text:
                qp.setPen(QPen(QColor(255, 255, 255, 70), 1, Qt.DotLine))
                qp.drawRect(QRectF(ox + (x + dx) * k, oy + (y + dy) * k, w * k, h * k))
        qp.setPen(QPen(QColor(255, 213, 74, 110), 1))
        for (x, y, w, h) in self.marks:
            qp.drawRect(QRectF(ox + (x + dx) * k, oy + (y + dy) * k, w * k, h * k))
        if 0 <= self.chosen < len(self.hits):
            x, y, w, h, _ = self.hits[self.chosen]
            qp.setPen(QPen(QColor('#ffd54a'), 2))
            qp.drawRect(QRectF(ox + (x + dx) * k, oy + (y + dy) * k, w * k, h * k))
        if self._piece and self.piece_off:                # a piece on the move: its frame, where it will land
            x, y, w, h = self._piece[1]
            qp.setPen(QPen(QColor('#ffd54a'), 2, Qt.DashLine))
            qp.drawRect(QRectF(ox + (x + self.piece_off[0]) * k, oy + (y + self.piece_off[1]) * k, w * k, h * k))
        if self.rect_:
            x, y, w, h = self.rect_
            qp.setPen(QPen(QColor(theme.RED), 2))
            qp.drawRoundedRect(QRectF(ox + x * k, oy + y * k, w * k, h * k), 4, 4)
        qp.setClipping(False)
        qp.setPen(QPen(QColor(theme.LINE), 1))
        qp.drawRect(screen)
        if self.pixmap is None:
            f = QFont(self.font())
            f.setPointSizeF(10)
            qp.setFont(f)
            qp.setPen(QColor(theme.MUTED) if hasattr(theme, 'MUTED') else QColor('white'))
            qp.drawText(screen, Qt.AlignCenter, self.empty)
        qp.end()

    def _to_screen(self, pos):
        k, ox, oy = self._fit()
        return (pos.x() - ox) / k, (pos.y() - oy) / k

    def mousePressEvent(self, e):
        self._drag = (e.position(), self.rect_)
        self._moved = False
        self._piece, self.piece_off = None, None

    def mouseMoveEvent(self, e):
        if not (self._drag and self._drag[1]):
            return
        p0, r0 = self._drag
        k, _, _ = self._fit()
        if (e.position() - p0).manhattanLength() < 4 and not self._moved:
            return
        if not self._moved and self._piece is None and self.grab is not None:
            frame = self.grab(*self._to_screen(p0))       # a piece of the design under the pointer: drag that
            self._piece = (p0, frame) if frame else False
        if self._piece:
            d = (e.position() - p0) / k
            self._moved = True
            self.piece_off = (round(d.x()), round(d.y()))
            self.update()
            return
        sx, sy = self._to_screen(p0)
        x0, y0, w0, h0 = r0
        if not self._moved and not (x0 <= sx <= x0 + w0 and y0 <= sy <= y0 + h0):
            return                                  # drags start on the overlay
        self._moved = True
        d = (e.position() - p0) / k
        x = max(-200, min(1920, x0 + d.x()))
        y = max(-200, min(1080, y0 + d.y()))
        self.rect_ = (round(x), round(y), w0, h0)
        bx, by = self.base
        self.offset = (self.rect_[0] - bx, self.rect_[1] - by)
        self.moved.emit(self.rect_[0], self.rect_[1])
        self.update()

    def mouseReleaseEvent(self, e):
        if self._drag and not self._moved:
            # a click: the top piece under the pointer, the smallest when pieces are stacked the same
            sx, sy = self._to_screen(e.position())
            best, area = -1, None
            for i in range(len(self.hits) - 1, -1, -1):
                x, y, w, h, _ = self.hits[i]
                if x <= sx <= x + w and y <= sy <= y + h:
                    if area is None or w * h < area * 0.7:
                        best, area = i, w * h
            self.chosen = best
            self.picked.emit(best)
            self.update()
        elif self._drag and self._moved and self._piece:
            off = self.piece_off or (0, 0)
            self._piece, self.piece_off = None, None
            self.nudged.emit(off[0], off[1])
        elif self._drag and self._moved:
            self.released.emit()
        self._drag = None
        self._piece = None


class LayoutEditor(QWidget):
    """The scoreboard sandbox. One .NSW layout per scorebug theme."""
    HINT = ('Set the Game row and the overlay redraws the way it looks in play. Drag the red box to place it, click a '
            'piece to edit just that piece. Save writes the layout into your mod.')

    def __init__(self, main):
        super().__init__()
        self.main = main
        self.rel = None
        self.layout = None
        self._orig = None
        self.asset = None
        self.node = None
        self.states = {}           # {node offset: state shown}
        self.board = False         # a stadium board is open, not a TV overlay
        self.matchable = False     # a board or a broadcast screen: its colours can follow a scorebug
        self.screen = (1920, 1080)
        self._shown = {}           # {screen name: where the park shows it}, from the park's SCOREBOARD.SCR
        self._hits = []
        self._chosen_tex = None
        self._chosen_node = None
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
        # the game: a pretend moment (teams, score, inning, count, runners) the overlay is drawn for
        self.sit = uiquery.Situation()
        self._logos = {}
        self.lang, self._lang_base = None, None
        self._scene = 0
        self._reveal = set()
        grow = QHBoxLayout()
        grow.setSpacing(6)

        def small(value, lo, hi, tip, attr):
            sp = QSpinBox()
            sp.setRange(lo, hi)
            sp.setValue(value)
            sp.setToolTip(tip)
            sp.setMinimumWidth(52)
            sp.valueChanged.connect(lambda v, a=attr: self._sit_set(a, v))
            return sp

        def word(value, tip, attr):
            e = QLineEdit(value)
            e.setMaxLength(6)
            e.setFixedWidth(58)
            e.setToolTip(tip)
            e.textEdited.connect(lambda v, a=attr: self._sit_set(a, v.upper()))
            return e
        grow.addWidget(label('Game', 'Sub'))
        def uniform(side):
            c = QCheckBox('CC')
            c.setToolTip(f'The {side} team is wearing its City Connect uniform: its logo and colour change with it')
            c.toggled.connect(lambda on, a=side + '_cc': self._sit_set(a, on))
            return c
        grow.addWidget(word(self.sit.away, 'Away team', 'away'))
        grow.addWidget(uniform('away'))
        grow.addWidget(small(0, 0, 99, 'Away score', 'away_score'))
        grow.addWidget(word(self.sit.home, 'Home team', 'home'))
        grow.addWidget(uniform('home'))
        grow.addWidget(small(0, 0, 99, 'Home score', 'home_score'))
        self.g_half = QComboBox()
        self.g_half.addItems(['Top', 'Bottom'])
        self.g_half.currentIndexChanged.connect(lambda i: self._sit_set('bottom', bool(i)))
        grow.addWidget(self.g_half)
        sp = small(1, 1, 30, 'Inning', 'inning')
        sp.setPrefix('Inn  ')
        sp.setMinimumWidth(78)
        grow.addWidget(sp)
        for pre, hi, attr in (('B  ', 3, 'balls'), ('S  ', 2, 'strikes'), ('Out  ', 3, 'outs')):
            sp = small(0, 0, hi, attr.title(), attr)
            sp.setPrefix(pre)
            sp.setMinimumWidth(70)
            grow.addWidget(sp)
        for text, attr in (('1st', 'first'), ('2nd', 'second'), ('3rd', 'third')):
            c = QCheckBox(text)
            c.setToolTip(f'Runner on {text}')
            c.toggled.connect(lambda on, a=attr: self._sit_set(a, on))
            grow.addWidget(c)
        self.scene = QComboBox()
        self.scene.setToolTip('The game shows one of these at a time: the scorebug in play, or the team panels')
        self.scene.currentIndexChanged.connect(self._scene_changed)
        grow.addWidget(self.scene, 1)
        self.popup = QComboBox()
        self.popup.setToolTip('Panels the game fades in on top: the batter bar, a home run, a strikeout')
        self.popup.currentIndexChanged.connect(self._popup_changed)
        grow.addWidget(self.popup, 1)
        self.game_row = QWidget()
        self.game_row.setLayout(grow)
        grow.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.game_row)
        # states: the layout's switches (bases, counts, banners) and which look each shows
        srow = QHBoxLayout()
        srow.setSpacing(8)
        self.state_node = QComboBox()
        self.state_node.setToolTip('Parts of the overlay that switch between looks while you play')
        self.state_node.currentIndexChanged.connect(self._state_node_changed)
        srow.addWidget(self.state_node, 3)
        self.state_pick = QSpinBox()
        self.state_pick.setPrefix('Look  ')
        self.state_pick.setMinimumWidth(90)
        self.state_pick.valueChanged.connect(self._state_picked)
        srow.addWidget(self.state_pick, 1)
        self.b_states_reset = button('Follow the Game', on_click=self._states_reset)
        self.b_states_reset.setToolTip('Drop the looks you picked by hand; every switch follows the Game row again')
        srow.addWidget(self.b_states_reset, 1)
        self.fx = QCheckBox('Show animation layers')
        self.fx.setToolTip('Glows and pieces the game fades in with an animation. At rest they are hidden.')
        self.fx.toggled.connect(lambda *_: self._redraw())
        srow.addWidget(self.fx, 1)
        self.zoom = QCheckBox('Zoom in')
        self.zoom.setChecked(True)
        self.zoom.setToolTip('Fill the view with the overlay instead of the whole screen')
        self.zoom.toggled.connect(lambda *_: self._redraw())
        srow.addWidget(self.zoom, 0)
        lay.addLayout(srow)
        # the overlay's animations, a frame at a time or played
        arow = QHBoxLayout()
        arow.setSpacing(8)
        self.anim = QComboBox()
        self.anim.setToolTip('The moves the game plays on this overlay: bars sliding in, scores rolling, pop-ups')
        self.anim.activated.connect(self._anim_changed)
        self.frame = QSlider(Qt.Horizontal)
        self.frame.setEnabled(False)
        self.frame.valueChanged.connect(self._frame_changed)
        self.frame_at = label('', 'Sub')
        self.frame_at.setMinimumWidth(theme.d(76))
        self.frame_at.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.b_play = button('Play', on_click=self._play)
        self.b_play.setEnabled(False)
        arow.addWidget(self.anim, 3)
        arow.addWidget(self.frame, 5)
        arow.addWidget(self.frame_at, 0)
        arow.addWidget(self.b_play, 1)
        lay.addLayout(arow)
        self._clock = QTimer(self)
        self._clock.setInterval(30)
        self._clock.timeout.connect(self._tick)
        self._played = 0.0
        self.canvas = Canvas()
        self.canvas.moved.connect(self._dragged)
        self.canvas.released.connect(self._redraw)
        self.canvas.picked.connect(self._picked)
        self.canvas.nudged.connect(self._design_nudge)
        lay.addWidget(self.canvas, 1)
        self._pack, self._table, self._pix_cache, self._img_cache = None, {}, {}, {}
        self.strip = QListWidget()          # every texture the chosen overlay draws
        self.strip.setViewMode(QListView.IconMode)
        self.strip.setFlow(QListView.LeftToRight)
        self.strip.setWrapping(False)
        self.strip.setMovement(QListView.Static)
        self.strip.setIconSize(QSize(64, 44))
        self.strip.setGridSize(QSize(112, 78))
        self.strip.setFixedHeight(104)
        self.strip.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.strip.setToolTip('The textures this overlay is made of. Pick one to change every place it is drawn.')
        self.strip.currentItemChanged.connect(self._strip_picked)
        lay.addWidget(self.strip)
        # the chosen piece (or every use of the chosen texture): tint, opacity, a nudge, a size, hide, repaint
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
        self.b_hide = button('Hide', on_click=self._hide)
        self.b_piece = button('Replace PNG', on_click=self._replace_piece)
        self._tools = (self.b_tint, self.p_op, self.p_dx, self.p_dy, self.p_size, self.b_hide, self.b_piece)
        for w in self._tools:
            w.setEnabled(False)
            tools.addWidget(w, 1)
        for sp in (self.p_op, self.p_dx, self.p_dy, self.p_size):
            sp.valueChanged.connect(self._piece_edit)
        self.tools_row = QWidget()
        self.tools_row.setLayout(tools)
        tools.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.tools_row)
        # a text box: its font, size and colour, and bringing in a font of your own
        trow = QHBoxLayout()
        trow.setSpacing(8)
        trow.setContentsMargins(0, 0, 0, 0)
        self.t_font = QComboBox()
        self.t_font.setIconSize(QSize(150, 22))
        self.t_font.setToolTip('The game font this text box uses')
        self.t_font.activated.connect(self._text_font)
        self.t_size = self._spin(4, 200, 1)
        self.t_size.setPrefix('Text size  ')
        self.t_size.setSuffix(' px')
        self.t_size.valueChanged.connect(self._text_size)
        self.b_tcolor = button('Outline Colour', on_click=self._text_color)
        self.b_tcolor.setToolTip('The letters themselves take the Colour button above; this is their outline')
        self.t_align = QComboBox()
        self.t_align.addItems(['Left', 'Centre', 'Right'])
        self.t_align.activated.connect(self._text_align)
        self.b_font_import = button('Import Font…')
        self.b_font_import.setToolTip('Draw another font into the game, in place of the font this box uses')
        menu = QMenu(self.b_font_import)
        for name, file in fontlib.LIBRARY:
            menu.addAction(name, lambda f=file: self._import_font(fontlib.library_path(f)))
        menu.addSeparator()
        menu.addAction('From a file…', lambda: self._import_font())
        self.b_font_import.setMenu(menu)
        trow.addWidget(self.t_font, 3)
        trow.addWidget(self.t_size, 1)
        trow.addWidget(self.t_align, 1)
        trow.addWidget(self.b_tcolor, 1)
        trow.addWidget(self.b_font_import, 1)
        self.text_row = QWidget()
        self.text_row.setLayout(trow)
        self.text_row.hide()
        lay.addWidget(self.text_row)
        # a design of your own: its pieces, and the chosen piece's place, colour, words and data
        self.design = None
        drow = QHBoxLayout()
        drow.setSpacing(8)
        drow.setContentsMargins(0, 0, 0, 0)
        self.d_piece = Layers()
        self.d_piece.setToolTip('The pieces of this design, back to front. Click one here or on the screen to pick '
                                'it. Double-click to name it.')
        self.d_piece.activated.connect(self._design_pick)
        self.d_piece.renamed.connect(self._design_rename)
        self.b_up = button('Move Back', on_click=lambda: self._design_move(-1))
        self.b_up.setToolTip('Draw this piece earlier, so later pieces cover it')
        self.b_down = button('Move Forward', on_click=lambda: self._design_move(1))
        self.b_down.setToolTip('Draw this piece later, on top of the ones before it')
        drow.addWidget(self.d_piece, 3)
        for text, kind in (('+ Box', 'box'), ('+ Text', 'text'), ('+ Logo', 'logo'), ('+ Team Colour', 'team')):
            drow.addWidget(button(text, on_click=lambda _=False, k=kind: self._design_add(k)), 1)
        drow.addWidget(button('+ Image', on_click=self._design_image), 1)
        drow.addWidget(button('Team Colours…', on_click=self._design_teams), 1)
        drow.addWidget(button('Copy', on_click=self._design_copy), 1)
        drow.addWidget(button('Delete', on_click=self._design_delete), 1)
        drow.addWidget(button('Save Design…', on_click=self._design_save), 1)
        self.design_row = QWidget()
        self.design_row.setLayout(drow)
        self.design_row.hide()
        lay.addWidget(self.design_row)
        prow = QHBoxLayout()
        prow.setSpacing(8)
        prow.setContentsMargins(0, 0, 0, 0)
        self.d_at = []
        for pre, lo, hi in (('X  ', -1920, 1920), ('Y  ', -1080, 1080), ('W  ', 1, 1920), ('H  ', 1, 1080)):
            sp = self._spin(lo, hi, 0)
            sp.setPrefix(pre)
            sp.valueChanged.connect(self._design_edit)
            self.d_at.append(sp)
            prow.addWidget(sp, 1)
        self.d_color = button('Colour', on_click=self._design_color)
        prow.addWidget(self.d_color, 1)
        self.d_op = self._spin(0, 100, 0)
        self.d_op.setPrefix('Opacity  ')
        self.d_op.setSuffix(' %')
        self.d_op.valueChanged.connect(self._design_edit)
        prow.addWidget(self.d_op, 1)
        self.d_words = QLineEdit()
        self.d_words.setPlaceholderText('Words, with ^d0^ where a live value goes')
        self.d_words.editingFinished.connect(self._design_edit)
        prow.addWidget(self.d_words, 2)
        self.d_pick = QComboBox()                      # the same data by plain names
        self.d_pick.addItem('Add live data…', None)
        for group, rows in uibuild.CATALOG:
            for name, q in rows:
                self.d_pick.addItem(f'{group}: {name}', q)
        self.d_pick.setToolTip('Pick what this text shows: the pitcher, the batter, the pitch speed, the score… '
                               'On another kind of piece it adds a text showing it.')
        self.d_pick.activated.connect(self._design_add_data)
        self.b_package = button('Make a Package…', on_click=self._design_package)
        self.b_package.setToolTip('One mod with everything in this look: the scorebug, every ballpark’s boards and '
                                  'the lineup, due-up and other broadcast screens in its colours. Share that one mod.')
        self.graph = DesignGraph()
        self.graph.picked.connect(self._graph_picked)
        self.graph.wired.connect(self._graph_wired)
        self.graph.hide()
        self.b_graph = QCheckBox('Graph view')
        self.b_graph.setToolTip('See the design as a graph: game data, rules and pieces, wired together. Drag data '
                                'onto a piece to wire it. The Layers list keeps working beside it.')
        self.b_graph.setEnabled(False)
        self.b_graph.toggled.connect(self._graph_toggled)
        self.d_data = QComboBox()
        self.d_data.setEditable(True)
        self.d_data.setToolTip('The game data shown: one query for each ^d0^ ^d1^, separated by ;')
        self.d_data.addItems([''] + uibuild.DATA)
        self.d_data.activated.connect(self._design_edit)
        self.d_data.lineEdit().editingFinished.connect(self._design_edit)
        prow.addWidget(self.d_data, 3)
        self.d_size = self._spin(6, 200, 0)
        self.d_size.setPrefix('Size  ')
        self.d_size.valueChanged.connect(self._design_edit)
        prow.addWidget(self.d_size, 1)
        self.d_align = QComboBox()
        self.d_align.addItems(['Left', 'Centre', 'Right'])
        self.d_align.activated.connect(self._design_edit)
        prow.addWidget(self.d_align, 1)
        self.d_font = QComboBox()
        self.d_font.setIconSize(QSize(150, 22))
        self.d_font.setToolTip('The game font this text uses')
        self.d_font.activated.connect(self._design_edit)
        self.d_font_import = button('Import Font…')
        self.d_font_import.setToolTip('Draw another font into the game, in place of the font this text uses')
        menu2 = QMenu(self.d_font_import)
        for name, file in fontlib.LIBRARY:
            menu2.addAction(name, lambda f=file: self._import_font(fontlib.library_path(f)))
        menu2.addSeparator()
        menu2.addAction('From a file…', lambda: self._import_font())
        self.d_font_import.setMenu(menu2)
        # a rule: the piece is drawn only while it holds
        self.d_rule = QComboBox()
        self.d_rule.setEditable(True)
        self.d_rule.addItems([''] + uibuild.ASK)
        self.d_rule.lineEdit().setPlaceholderText('Always shown. Pick data to show it only when…')
        self.d_rule.setToolTip('A rule: this piece is drawn only while the game data you pick matches')
        self.d_rule.activated.connect(self._design_edit)
        self.d_rule.lineEdit().editingFinished.connect(self._design_edit)
        self.d_rule_op = QComboBox()
        OPS = (('is', '=='), ('is not', '!='), ('is more than', '>'), ('is at least', '>='), ('is less than', '<'),
               ('is at most', '<='))
        for text, op in OPS:
            self.d_rule_op.addItem(text, op)
        self.d_rule_op.activated.connect(self._design_edit)
        self.d_rule_val = self._spin(0, 99, 0)
        self.d_rule_val.valueChanged.connect(self._design_edit)
        self.d_join = QComboBox()                      # a second thing to ask, with "and" or "or"
        self.d_join.addItem('One rule', None)
        self.d_join.addItem('and', 'all')
        self.d_join.addItem('or', 'any')
        self.d_join.setToolTip('Ask a second thing as well: both must be true (and), or either one (or)')
        self.d_join.activated.connect(self._design_edit)
        self.d_rule2 = QComboBox()
        self.d_rule2.setEditable(True)
        self.d_rule2.addItems([''] + uibuild.ASK)
        self.d_rule2.lineEdit().setPlaceholderText('The second thing to ask')
        self.d_rule2.activated.connect(self._design_edit)
        self.d_rule2.lineEdit().editingFinished.connect(self._design_edit)
        self.d_rule2_op = QComboBox()
        for text, op in OPS:
            self.d_rule2_op.addItem(text, op)
        self.d_rule2_op.activated.connect(self._design_edit)
        self.d_rule2_val = self._spin(0, 99, 0)
        self.d_rule2_val.valueChanged.connect(self._design_edit)
        # line a piece up inside whatever it sits in, and the design's colours
        self.d_align_btns = [button(t, on_click=lambda _=False, a=a: self._design_align(a)) for t, a in (
            ('Left', 'l'), ('Centre', 'c'), ('Right', 'r'), ('Top', 't'), ('Middle', 'm'), ('Bottom', 'b'))]
        self.d_swatches = []
        for i in range(8):
            b = QPushButton()
            b.setFixedHeight(theme.d(30))
            b.clicked.connect(lambda _=False, i=i: self._design_recolour(i))
            self.d_swatches.append(b)
        self.d_move = QComboBox()
        self.d_move.setToolTip('How this piece arrives: when the scorebug first appears, or, for a piece with a '
                               'rule, each time the rule comes true')
        for text, m in MOTIONS:
            self.d_move.addItem(text, m)
        self.d_move.activated.connect(self._design_edit)
        prow.addWidget(self.d_move, 1)
        self.design_props = QWidget()
        self.design_props.setLayout(prow)
        self.design_props.hide()
        lay.addWidget(self.design_props)
        # a stadium board: its colours, and matching it to a scorebug
        self.bd_match = QComboBox()
        self.bd_match.setToolTip('Repaint this park’s boards in a scorebug’s colours: its dark behind everything, '
                                 'its light for the words, its accent colours for the board’s own')
        self.bd_match.activated.connect(self._board_match)
        self.bd_keep = QCheckBox('Keep the park’s colour')
        self.bd_keep.setChecked(True)
        self.bd_keep.setToolTip('Leave the board’s biggest colour alone: it is the home club’s, and the scorebug '
                                'shows the club’s colour too')
        self.bd_font = button('Use Its Font', on_click=self._board_font)
        self.bd_font.setToolTip('Give the board’s main font the font the scorebug uses most')
        self.bd_font.setEnabled(False)
        self.bd_all = button('Match Every Park…', on_click=self._board_all)
        self.bd_all.setToolTip('Repaint the boards of every ballpark in the scorebug you matched, and save them '
                               'into your mod in one go')
        self.bd_all.setEnabled(False)
        self._board_design = None
        self.bd_swatches = []
        for i in range(8):
            b = QPushButton()
            b.setFixedHeight(theme.d(30))
            b.clicked.connect(lambda _=False, i=i: self._board_recolour(i))
            self.bd_swatches.append(b)
        self._fonts = None             # (FontTable, sheet) as the active mod has them
        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        self.note = label(self.HINT, 'Sub', wrap=True)
        bottom.addWidget(self.note, 1)
        self.styles = QComboBox()
        self.styles.setMinimumWidth(theme.d(170))
        self.styles.setToolTip('Start from a whole look: a built-in one or one you saved')
        self.styles.activated.connect(self._style_picked)
        self.b_style = button('Save as Style…', on_click=self.save_style)
        self.b_style.setToolTip('Keep this look as its own small mod you can switch on, share or come back to')
        self.b_reset = button('Back to Default', on_click=self.reset)
        self.b_save = button('Save to My Mod', True, self.save)
        bottom.addWidget(self.styles)
        bottom.addWidget(self.b_style)
        bottom.addWidget(self.b_reset)
        bottom.addWidget(self.b_save)
        lay.addLayout(bottom)
        self._arrange(lay)

    def _arrange(self, lay):
        """Lay the editor out: what you are making and saving along the top, the screen with the pretend game and
        playback under it on the left, and one column of settings on the right, grouped by what they change."""
        d_buttons = self.design_row.findChildren(QPushButton)          # + Box, + Text, + Logo, + Team Colour, ...
        old = [self.tools_row, self.text_row, self.design_row, self.design_props]
        while lay.count():
            it = lay.takeAt(0)
            if it.layout() is not None:
                it.layout().setParent(None)

        def section(title, rows):
            box = QWidget()
            v = QVBoxLayout(box)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(6)
            v.addWidget(label(title.upper(), 'StripLabel'))
            for r in rows:
                if len(r) == 1:
                    v.addWidget(r[0])
                    continue
                h = QHBoxLayout()
                h.setSpacing(6)
                for w in r:
                    h.addWidget(w, 1)
                v.addLayout(h)
            return box
        # along the top: which overlay, the look to start from, and saving
        top = QHBoxLayout()
        top.setSpacing(8)
        self.which.setMinimumWidth(theme.d(220))
        self.styles.setMinimumWidth(theme.d(220))
        top.addWidget(self.which)
        top.addWidget(self.styles)
        top.addStretch(1)
        for w in (self.b_reset, self.b_style, self.b_save):
            top.addWidget(w)
        lay.addLayout(top)
        mid = QHBoxLayout()
        mid.setSpacing(12)
        # the screen, with the moment of the game it shows and what is playing
        left = QVBoxLayout()
        left.setSpacing(8)
        left.addWidget(self.canvas, 1)
        left.addWidget(self.graph, 1)
        self.game_row.layout().addStretch(1)
        left.addWidget(self.game_row)
        play = QHBoxLayout()
        play.setSpacing(8)
        play.addWidget(self.scene, 2)
        play.addWidget(self.popup, 2)
        play.addWidget(self.anim, 3)
        play.addWidget(self.frame, 4)
        play.addWidget(self.frame_at, 0)
        play.addWidget(self.b_play, 1)
        play.addWidget(self.fx, 0)
        play.addWidget(self.zoom, 0)
        play.addWidget(self.b_graph, 0)
        left.addLayout(play)
        mid.addLayout(left, 1)
        # the settings, grouped
        self.place_box = section('Place on screen', [[self.preset, self.sscale], [self.sx, self.sy]])
        add_box, add_text, add_logo, add_team, add_image, teams, copy_, delete, save = d_buttons
        self.design_row = section('Layers', [[self.d_piece], [self.b_up, self.b_down], [copy_, delete],
                                             [add_box, add_text], [add_logo, add_team], [add_image, teams],
                                             [save, self.b_package]])
        self.design_props = section('Chosen piece', [self.d_at[0:2], self.d_at[2:4], [self.d_color, self.d_op],
                                                     [self.d_words], [self.d_pick], [self.d_data],
                                                     [self.d_size, self.d_align],
                                                     [self.d_font], [self.d_font_import]])
        self.align_box = section('Line it up', [self.d_align_btns[0:3], self.d_align_btns[3:6]])
        self.colour_box = section('Colours of the design', [self.d_swatches[0:4], self.d_swatches[4:8]])
        self.rule_box = section('Rule and motion', [[self.d_rule], [self.d_rule_op, self.d_rule_val], [self.d_join],
                                                    [self.d_rule2], [self.d_rule2_op, self.d_rule2_val],
                                                    [self.d_move]])
        self.board_box = section('Match a scorebug', [[self.bd_match], [self.bd_keep, self.bd_font], [self.bd_all]])
        self.board_colours = section('Its colours', [self.bd_swatches[0:4], self.bd_swatches[4:8]])
        self.tools_row = section('Chosen piece', [[self.b_tint, self.p_op], [self.p_dx, self.p_dy],
                                                  [self.p_size, self.b_hide], [self.b_piece]])
        self.text_row = section('Its text', [[self.t_font], [self.t_size, self.t_align],
                                             [self.b_tcolor, self.b_font_import]])
        self.strip.setWrapping(True)
        self.strip.setFlow(QListView.LeftToRight)
        self.strip.setResizeMode(QListView.Adjust)
        self.strip.setGridSize(QSize(theme.d(104), theme.d(74)))
        self.strip.setFixedHeight(theme.d(232))
        self.strip.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.strip.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tex_box = section('Its textures', [[self.strip]])
        self.switch_box = section('Force a look', [[self.state_node], [self.state_pick, self.b_states_reset]])
        for w in old:
            w.deleteLater()
        for w in (self.design_row, self.design_props, self.align_box, self.colour_box, self.rule_box, self.text_row,
                  self.board_box, self.board_colours):
            w.hide()
        side = QWidget()
        side.setObjectName('Page')
        col = QVBoxLayout(side)
        col.setContentsMargins(0, 0, theme.d(14), 0)
        col.setSpacing(theme.d(18))
        for w in (self.place_box, self.board_box, self.board_colours, self.design_row, self.design_props,
                  self.align_box, self.colour_box, self.rule_box, self.tools_row, self.text_row, self.tex_box, self.switch_box):
            col.addWidget(w)
        col.addStretch(1)
        for cb in side.findChildren(QComboBox):          # a long entry must not push the column past its width
            cb.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            cb.setMinimumContentsLength(8)
            cb.setMinimumWidth(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(side)
        scroll.setFixedWidth(theme.d(392))
        mid.addWidget(scroll)
        lay.addLayout(mid, 1)
        lay.addWidget(self.note)

    @staticmethod
    def _spin(lo, hi, dec):
        s = QDoubleSpinBox()
        s.setRange(lo, hi)
        s.setDecimals(dec)
        s.setMinimumWidth(90)
        return s

    # ------------------------------------------------------------------ opening
    def open(self, pack_rel):
        """pack_rel: the theme's texture pack, e.g. NSW/UI/GAME/THEME1.TEX."""
        rel = pack_rel[:-4] + '.NSW'
        self.rel = rel
        self.board = boards.is_board(rel)
        self.matchable = self.board or '/PRES/' in rel.upper()       # painted colours a scorebug can lend its own to
        self._shown = {}
        self.canvas.safe = not self.board
        self.canvas.backdrop = (0, 0, 0) if self.board else BACKDROP[:3]
        self.canvas.empty = 'Pick a stadium board' if self.board else 'Pick a scorebug theme'
        self.which.blockSignals(True)
        self.which.clear()
        if rel not in self.main.game.file_set():
            self._empty('This pack has no layout file.')
            self.which.blockSignals(False)
            return
        self._pack, self._table, self._pix_cache, self._img_cache = pack_rel, {}, {}, {}
        self._fonts = None
        try:
            tex = self.main.tex(pack_rel)
            self._table = uilayout.Layout.texture_table([e['name'] for e in tex.entries]) if tex else {}
        except Exception:
            self._table = {}
        self.lang, self._lang_base = None, None
        try:
            lrel = pack_rel[:-4] + '.LANG_EN'
            if lrel in self.main.game.file_set():
                with open(self.main.current_file(lrel), 'rb') as f:
                    self._lang_base = f.read()
                self.lang = uilang.Lang(self._lang_base)
        except Exception:
            self.lang = None
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
        first = ['Scorebar', 'BottomTicker']
        if self.board:                       # the screens the park puts on its signs come first, biggest first
            try:
                srel = boards.script_of(rel)
                if srel and srel in self.main.game.file_set():
                    with open(self.main.current_file(srel), encoding='latin-1') as f:
                        self._shown = boards.where_shown(boards.script(f.read()), boards.park_of(rel))
            except Exception:
                self._shown = {}
            low = {n.lower(): n for n in names}
            first = [low[k] for k, e in sorted(self._shown.items(), key=lambda kv: -int(kv[1].get('width', 0)) *
                                                int(kv[1].get('height', 0))) if k in low]
        names = sorted(set(names), key=lambda n: (first.index(n) if n in first else len(first), n))
        if not names:
            self._empty('This pack’s layout has no overlays the manager can place yet.')
            self.which.blockSignals(False)
            return
        self._enable(True)
        self.note.setText(self.HINT)
        for n in names:
            self.which.addItem(n)
        self.which.blockSignals(False)
        self._design_stop()
        self._fill_styles()
        self._team_art()
        self.place_box.setVisible(not self.board)
        self.board_box.setVisible(self.matchable)
        self.board_colours.setVisible(self.matchable)
        self.bd_all.setVisible(self.board)
        self.bd_keep.setText('Keep the park’s colour' if self.board else 'Keep its main colour')
        self._board_design = None
        self.bd_font.setEnabled(False)
        self.bd_all.setEnabled(False)
        if self.matchable:
            self._fill_board()
        self._asset_changed()

    def _empty(self, why):
        self.layout = None
        self.asset = self.node = None
        self.canvas.pixmap = None
        self.canvas.rect_ = None
        self.canvas.hits = []
        self._enable(False)
        self.note.setText(why)
        self.strip.clear()
        self.strip.hide()
        self.tools_row.hide()
        self.canvas.update()

    def _enable(self, on):
        for w in (self.which, self.preset, self.sx, self.sy, self.sscale, self.b_reset, self.b_save,
                  self.state_node, self.state_pick, self.b_states_reset, self.fx, self.zoom, self.game_row,
                  self.anim, self.styles, self.b_style):
            w.setEnabled(on)

    def _asset_changed(self, *_):
        if not self.layout or not self.which.currentText():
            return
        self._choose(None, None)
        self.asset = self.layout.find(self.which.currentText())
        self.node = self.asset.container() if self.asset else None
        self.states = {}
        self.screen = boards.size(self.asset) if self.board and self.asset else (1920, 1080)
        self.canvas.screen = self.screen
        if self.node is None:
            self.canvas.rect_ = None
            self.canvas.pixmap = None
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
        self._fill_scenes()
        self._fill_states()
        self._fill_anims()
        self._fill_strip()
        self.note.setText(self._board_note() if self.board else self.HINT)
        self._redraw()

    # ------------------------------------------------------------------ animations
    def _fill_anims(self):
        self._clock.stop()
        self.b_play.setText('Play')
        self.anim.blockSignals(True)
        self.anim.clear()
        self.anim.addItem('Animation: none', -1)
        try:
            moves = [a for a in self.asset.animations() if a.frames and a.tracks]
        except Exception:
            moves = []
        seen = {}
        for a in sorted(moves, key=lambda a: (not a.name or a.name.startswith('#'), a.index)):
            text = a.label
            seen[text] = seen.get(text, 0) + 1
            if seen[text] > 1:
                text = text.replace('  ·', f' {seen[text]}  ·')
            self.anim.addItem(text, a.index)
        made = self._design_asset()
        if made is not None and made.animations():
            self.anim.insertItem(1, f'Design: entrance  ·  {made.animations()[0].frames} frames', -2)
        self.anim.blockSignals(False)
        self.anim.setEnabled(self.anim.count() > 1)
        self._anim_changed(0)

    def _design_asset(self):
        return self.layout.find(self.design['name']) if self.layout and self.design else None

    def _anim(self):
        i = self.anim.currentData()
        self._anim_of = self.asset
        if i == -2 and self._design_asset() is not None:
            self._anim_of = self._design_asset()
            return self._anim_of.animations()[0]
        if i is None or i < 0 or not self.asset:
            return None
        return self.asset.animations()[i]

    def _anim_changed(self, _i=0):
        a = self._anim()
        self._clock.stop()
        self.b_play.setText('Play')
        self.frame.blockSignals(True)
        self.frame.setRange(0, a.frames if a else 0)
        self.frame.setValue(0)
        self.frame.blockSignals(False)
        self.frame.setEnabled(a is not None)
        self.b_play.setEnabled(a is not None)
        self.frame_at.setText(f'0 / {a.frames}' if a else '')
        if self.layout and self.asset and self.node is not None:
            self._redraw()

    def _frame_changed(self, v):
        a = self._anim()
        self.frame_at.setText(f'{v} / {a.frames}' if a else '')
        self._redraw()

    def _play(self):
        a = self._anim()
        if a is None:
            return
        if self._clock.isActive():
            self._clock.stop()
            self.b_play.setText('Play')
            return
        if self.frame.value() >= a.frames:
            self.frame.setValue(0)
        self._played = time.monotonic() - self.frame.value() / 60.0
        self.b_play.setText('Stop')
        self._clock.start()

    def _tick(self):
        a = self._anim()
        if a is None:
            self._clock.stop()
            return
        f = int((time.monotonic() - self._played) * 60)          # the game runs these at 60 frames a second
        if f >= a.frames:
            f = a.frames
            self._clock.stop()
            self.b_play.setText('Play')
        self.frame.setValue(f)

    # ------------------------------------------------------------------ a design of your own
    def _design_start(self, design):
        """Work on a design: every change rebuilds the scorebug from it."""
        import copy
        self.design = copy.deepcopy(design)
        target = self.design.get('replaces')
        if target:                                        # a card: show the screen it takes the place of
            i = self.which.findText(str(target))
            if i < 0:
                self.design = None
                QMessageBox.information(self, 'Not on This Screen', f'This card takes the place of {target}, which '
                                        'this file does not have. Open a Broadcast Presentation pack that has it.')
                return False
            self.which.blockSignals(True)
            self.which.setCurrentIndex(i)
            self.which.blockSignals(False)
        elif not (self.rel and self.rel.upper() in samples.THEMES):
            self.design = None
            QMessageBox.information(self, 'A Scorebug Design', 'This design is a scorebug. Open one of the four '
                                    'scorebug themes to build it.')
            return False
        if self.design.get('fonts'):
            self._fonts = None                            # start from the game's fonts, then draw the design's in
            self._design_fonts()
        if self._design_build(0) is False:                # it cannot be built here: say why, and stay as you were
            why = self.note.text()
            self.design = None
            self._design_stop()
            QMessageBox.warning(self, 'This Design Does Not Fit Here', why)
            self.note.setText(self.HINT)
            return False
        return True

    def _design_stop(self):
        if self.design is not None:
            for w in (self.tools_row, self.tex_box, self.switch_box):
                w.show()
            self.board_box.setVisible(self.matchable)
            self.board_colours.setVisible(self.matchable)
            self.place_box.setVisible(not self.board)
        self.design = None
        self.canvas.grab = None
        self.b_graph.setChecked(False)
        self.b_graph.setEnabled(False)
        for w in (self.design_row, self.design_props, self.align_box, self.colour_box, self.rule_box):
            w.hide()

    def _design_build(self, keep=None):
        if self.design is None:
            return
        if keep is None:
            keep = self.d_piece.currentIndex()
        try:
            lay = uilayout.Layout.open(self.main.game.original(self.rel))
            tex = self.main.tex(self._pack)
            samples.place_design(lay, self.design, {e['name']: (e['w'], e['h']) for e in tex.entries} if tex else None)
            for carrier, path in lay.art.items():           # the design's own pictures, shown as the game will
                self._img_cache[carrier] = self._art(path)
        except Exception as x:
            self.note.setText(f'This design does not build: {x}')
            return False
        self._use(lay)
        self._pieces = list(uibuild.walk(self.design.get('pieces') or []))      # nested ones too, in drawing order
        pieces = self._pieces
        self.d_piece.fill([(where + uibuild.describe(p), depth) for p, depth, _home, where, _in in pieces])
        self._palette = uibuild.colours(self.design)[:8]
        for i, b in enumerate(self.d_swatches):
            c = self._palette[i] if i < len(self._palette) else None
            b.setEnabled(c is not None)
            b.setToolTip(f'{c}: change every piece of this colour' if c else '')
            b.setStyleSheet(f'QPushButton {{ background: {c}; border: 1px solid {theme.LINE}; border-radius: 8px; }}'
                            if c else f'QPushButton {{ background: transparent; border: 1px dashed {theme.LINE}; '
                                      'border-radius: 8px; }')
        self.canvas.grab = self._design_grab
        self.b_graph.setEnabled(True)
        self.d_piece.setCurrentIndex(max(0, min(keep, len(pieces) - 1)) if pieces else -1)
        self.design_row.show()
        for w in (self.design_props, self.align_box, self.colour_box, self.rule_box):
            w.setVisible(bool(pieces))
        for w in (self.tools_row, self.text_row, self.tex_box, self.switch_box, self.board_box, self.board_colours):
            w.hide()
        self.place_box.setVisible(not self.design.get('replaces') and not self.board)
        self._design_pick()

    # ------------------------------------------------------------------ the design as a graph
    def _graph_toggled(self, on):
        on = bool(on and self.design is not None)
        self.canvas.setVisible(not on)
        self.graph.setVisible(on)
        if on:
            self.graph.show_design(self.design, self.d_piece.currentIndex())

    def _graph_sync(self):
        if self.graph.isVisible() and self.design is not None:
            self.graph.show_design(self.design, self.d_piece.currentIndex())

    def _graph_picked(self, i):
        self.d_piece.setCurrentIndex(i)
        self._design_pick()

    def _graph_wired(self, query, i):
        """Data dragged onto a piece: a text shows it, a team piece or logo takes that team, anything else is
        drawn only while it is 1 (added to the rule it has, if it has one)."""
        pieces = getattr(self, '_pieces', [])
        if not (self.design and 0 <= i < len(pieces)):
            return
        p = pieces[i][0]
        kind = uibuild.kind_of(p)
        side = next((k for k, v in TEAMS.items() if v == query), None)
        if side:
            key = 'tint' if 'tint' in p else kind if kind in ('team', 'logo') else None
            if key is None:
                self.note.setText('A team goes onto a team colour, a tint group or a logo.')
                return
            p[key] = side
        elif kind == 'text' and query in {q for _g, rows in uibuild.CATALOG for _n, q in rows}:
            self._add_data(p, query)
        else:
            new = {'data': query, 'is': '==', 'value': 1}
            old = p.get('when')
            p['when'] = new if not old else {'all': (old['all'] + [new])[:2]} if 'all' in old else \
                old if 'any' in old else {'all': [old, new]}
        if query in self.graph.extra:
            self.graph.extra.remove(query)
        self._design_build(i)

    @staticmethod
    def _add_data(piece, query):
        data = list(piece.get('data') or [])
        data.append(query)
        words = str(piece.get('text', ''))
        mark = f'^d{len(data) - 1}^'
        piece['text'] = mark if (len(data) == 1 and words in ('', 'TEXT')) else (words + ' ' + mark).strip()
        piece['data'] = data

    def _design_add_data(self, i):
        """The plain-named data list: the chosen text shows it too; on any other piece a new text is made for it."""
        query = self.d_pick.itemData(i)
        self.d_pick.setCurrentIndex(0)
        if not query or self.design is None:
            return
        p = self._design_piece()
        if p is None or uibuild.kind_of(p) != 'text':
            self._design_add('text')
            p = self._design_piece()
        self._add_data(p, query)
        self._design_build()

    def _design_piece(self):
        pieces = getattr(self, '_pieces', []) if self.design else []
        i = self.d_piece.currentIndex()
        return pieces[i][0] if 0 <= i < len(pieces) else None

    def _design_home(self):
        """The list the chosen piece sits in (the design's own, or a group's)."""
        pieces = getattr(self, '_pieces', []) if self.design else []
        i = self.d_piece.currentIndex()
        return pieces[i][2] if 0 <= i < len(pieces) else None

    def _design_node(self, index):
        """The node a piece of the design was compiled into."""
        made = self._design_asset()
        pieces = getattr(self, '_pieces', [])
        if made is None or not (0 <= index < len(pieces)):
            return None
        rel = getattr(self.layout, 'piece_at', {}).get(id(pieces[index][0]))
        return self.layout.node_at(made, rel) if rel is not None else None

    def _design_pick(self, *_):
        self._graph_sync()
        p = self._design_piece()
        if p is None:
            return
        widgets = self.d_at + [self.d_op, self.d_words, self.d_data, self.d_size, self.d_align, self.d_move,
                               self.d_font]
        rule = p.get('when') or {}
        join = 'all' if 'all' in rule else 'any' if 'any' in rule else None
        first, second = ((rule[join] + [{}, {}])[:2]) if join else (rule, {})
        rules = (self.d_rule, self.d_rule_op, self.d_rule_val, self.d_join, self.d_rule2, self.d_rule2_op,
                 self.d_rule2_val)
        for w in rules:
            w.blockSignals(True)
        for r, (wd, wo, wv) in ((first, rules[0:3]), (second, rules[4:7])):
            wd.setEditText(str(r.get('data', '')))
            wo.setCurrentIndex(max(0, wo.findData(r.get('is', '=='))))
            wv.setValue(int(r.get('value', 1)))
        self.d_join.setCurrentIndex(max(0, self.d_join.findData(join)))
        for w in rules[4:7]:
            w.setEnabled(join is not None)
        for w in rules:
            w.blockSignals(False)
        if 'text' in p:
            self._load_fonts()
        for w in widgets:
            w.blockSignals(True)
        self.d_font.setCurrentIndex(self.d_font.findData(p.get('font', 25)))
        for w in (self.d_font, self.d_font_import):
            w.setEnabled('text' in p)
        enter = p.get('enter')
        self.d_move.setCurrentIndex(0 if not enter else next(
            (i for i, (_t, m) in enumerate(MOTIONS) if m and m.get('from') == enter.get('from')), 1))
        for sp, v in zip(self.d_at, uibuild.rect(p)):
            sp.setValue(v)
        self.d_op.setValue(p.get('opacity', 100))
        text = 'text' in p
        self.d_words.setText(str(p.get('text', '')))
        self.d_data.setEditText(' ; '.join(p.get('data') or []))
        self.d_size.setValue(p.get('size', 28))
        self.d_align.setCurrentIndex({'left': 0, 'right': 2}.get(str(p.get('align', 'centre')).lower(), 1))
        for w in (self.d_words, self.d_data, self.d_size, self.d_align):
            w.setEnabled(text)
        self.d_color.setEnabled(uibuild.kind_of(p) in ('box', 'image', 'text', 'logo'))
        for w in widgets:
            w.blockSignals(False)
        n = self._design_node(self.d_piece.currentIndex())
        self._chosen_node = n
        if n is not None:
            self.canvas.chosen = next((i for i, h in enumerate(self._hits) if h.node.off == n.off), -1)
            self.canvas.update()

    def _design_edit(self, *_):
        p = self._design_piece()
        if p is None:
            return
        uibuild.set_rect(p, [sp.value() for sp in self.d_at])
        if self.d_op.value() < 100 or 'opacity' in p:
            p['opacity'] = self.d_op.value()
        ask = [{'data': wd.currentText().strip(), 'is': wo.currentData(), 'value': int(wv.value())}
               for wd, wo, wv in ((self.d_rule, self.d_rule_op, self.d_rule_val),
                                  (self.d_rule2, self.d_rule2_op, self.d_rule2_val))]
        join = self.d_join.currentData()
        for w in (self.d_rule2, self.d_rule2_op, self.d_rule2_val):
            w.setEnabled(join is not None)
        if ask[0]['data'] and join and ask[1]['data']:
            p['when'] = {join: ask}
        elif ask[0]['data']:
            p['when'] = ask[0]
        else:
            p.pop('when', None)
        move = self.d_move.currentData()
        if move is None:
            p.pop('enter', None)
        elif (p.get('enter') or {}).get('from') != move.get('from') or 'enter' not in p:
            p['enter'] = dict(move, delay=(p.get('enter') or {}).get('delay', 0))
        if 'text' in p:
            p['text'] = self.d_words.text()
            data = [q.strip() for q in self.d_data.currentText().split(';') if q.strip()]
            holes = len(set(re.findall(r'\^d(\d+)\^', p['text'])))
            if data and not holes:                         # data picked for plain words: show it
                p['text'], holes = '^d0^', 1
            p['data'] = data[:holes]
            if len(p['data']) < holes:
                self.note.setText('Pick one piece of data for each ^d0^ ^d1^ in the words.')
                return
            if not p['data']:
                del p['data']
            p['size'] = self.d_size.value()
            p['align'] = ('left', 'centre', 'right')[self.d_align.currentIndex()]
            if self.d_font.currentData() is not None:
                p['font'] = self.d_font.currentData()
        self._design_build()

    def _design_frame(self, index):
        """Where a piece sits on the screen: (x, y, w, h)."""
        n = self._design_node(index)
        if n is None or self.node is None:
            return None
        x, y, w, h = n.abs_rect()
        ox, oy = self._design_origin()
        return (ox + x, oy + y, w, h)

    def _design_origin(self):
        """Where the design's top-left corner is on the screen."""
        if self.design and self.design.get('replaces'):            # a card says where it sits
            return float(self.design.get('x', 0)), float(self.design.get('y', 0))
        dx, dy = getattr(self.layout, 'design_origin', (5, 53))
        return self.sx.value() + dx, self.sy.value() + dy

    def _design_grab(self, sx, sy):
        """Dragging starts here: the chosen piece if the pointer is on it, else the smallest piece under the pointer.
        A piece that fills the whole design is left alone, so dragging the background still moves the scorebug."""
        pieces = getattr(self, '_pieces', [])
        inside = lambda f: f and f[0] <= sx <= f[0] + f[2] and f[1] <= sy <= f[1] + f[3]
        w, h = self.design['size']
        best, area = None, None
        now = self.d_piece.currentIndex()
        for k in ([now] if 0 <= now < len(pieces) else []) + list(range(len(pieces) - 1, -1, -1)):
            f = self._design_frame(k)
            if not inside(f) or f[2] * f[3] >= 0.9 * w * h:
                continue
            if k == now and best is None:
                best, area = k, 0
                break
            if area is None or f[2] * f[3] < area:
                best, area = k, f[2] * f[3]
        if best is None:
            return None
        self.d_piece.setCurrentIndex(best)
        self._design_pick()
        return self._design_frame(best)

    def _design_nudge(self, dx, dy):
        p = self._design_piece()
        if p is None or (not dx and not dy):
            return
        at = uibuild.rect(p)
        uibuild.set_rect(p, [round(at[0] + dx), round(at[1] + dy), at[2], at[3]])
        self._design_build()

    def _design_align(self, how):
        """Line the chosen piece up inside what it sits in (a group, a look, or the design itself)."""
        pieces, i = getattr(self, '_pieces', []), self.d_piece.currentIndex()
        if not (self.design and 0 <= i < len(pieces)):
            return
        p, parent = pieces[i][0], pieces[i][4]
        pw, ph = (uibuild.rect(parent)[2:] if parent is not None else self.design['size'])
        x, y, w, h = uibuild.rect(p)
        x = {'l': 0, 'c': (pw - w) / 2, 'r': pw - w}.get(how, x)
        y = {'t': 0, 'm': (ph - h) / 2, 'b': ph - h}.get(how, y)
        uibuild.set_rect(p, [round(x), round(y), w, h])
        self._design_build()

    def _design_recolour(self, i):
        palette = getattr(self, '_palette', [])
        if not (self.design and 0 <= i < len(palette)):
            return
        c = QColorDialog.getColor(QColor(palette[i]), self, 'Change this colour everywhere')
        if c.isValid() and c.name() != palette[i]:
            uibuild.recolour(self.design, palette[i], c.name())
            self._design_build()

    def _design_rename(self, _i=0):
        p = self._design_piece()
        if p is None:
            return
        text, ok = QInputDialog.getText(self, 'Name the piece', 'A name for this piece in the list:',
                                        text=str(p.get('name', '')))
        if ok:
            if text.strip():
                p['name'] = text.strip()
            else:
                p.pop('name', None)
            self._design_build()

    def _design_move(self, step):
        """Earlier or later in the drawing order, among the pieces it sits with."""
        p, home = self._design_piece(), self._design_home()
        if p is None or home is None:
            return
        i = next(k for k, x in enumerate(home) if x is p)
        j = i + step
        if 0 <= j < len(home):
            home[i], home[j] = home[j], home[i]
            self._design_build_on(p)

    def _design_color(self):
        p = self._design_piece()
        if p is None:
            return
        c = QColorDialog.getColor(QColor(p.get('color', '#ffffff')), self, 'Colour')
        if c.isValid():
            p['color'] = c.name()
            self._design_build()

    def _art(self, path):
        """A picture of the design's own, from its file (beside the design file when the path is not a full one)."""
        from PIL import Image
        full = path if os.path.isabs(path) else os.path.join((self.design or {}).get('_folder', ''), path)
        return Image.open(full).convert('RGBA')

    def _write_art(self, mod):
        """Put the design's pictures into a mod, each in the texture that carries it, sized to fit."""
        art = getattr(self.layout, 'art', None) or {}
        if not art or not mod:
            return
        tex = self.main.tex(self._pack)
        for carrier, path in art.items():
            e = next((e for e in tex.entries if e['name'] == carrier), None)
            if e is not None:
                self.main.lib.add_texture(mod, self._pack, carrier, uibuild.fit_art(self._art(path), e['w'], e['h']))

    def _design_image(self):
        if self.design is None:
            return
        path, _ = QFileDialog.getOpenFileName(self, 'Add a picture', self.main.last_dir(), 'Pictures (*.png)')
        if not path:
            return
        self.main.remember_dir(path)
        try:
            img = self._art(path)
        except Exception as x:
            QMessageBox.warning(self, 'Could Not Open', str(x))
            return
        w, h = self.design['size']
        k = min(1.0, w / img.width, h / img.height)        # at its own size, or shrunk to fit inside the design
        new = {'image': path, 'at': [0, 0, round(img.width * k), round(img.height * k)]}
        home, chosen = self._design_home(), self._design_piece()
        if chosen is not None and 'group' in chosen:
            home = chosen['group']
        elif home is None:
            home = self.design.setdefault('pieces', [])
        home.append(new)
        self._design_build_on(new)

    def _design_teams(self):
        """Where team colours come from, and colours of your own for particular clubs and uniforms."""
        if self.design is None:
            return
        try:
            dlg = TeamColours(self, self.design)
        except ValueError as x:
            QMessageBox.warning(self, 'Team Colours', str(x))
            return
        if dlg.exec() == QDialog.Accepted:
            dlg.result_into(self.design)
            self._design_build()

    def _design_add(self, kind):
        if self.design is None:
            return
        w, h = self.design['size']
        new = {'box': {'box': [10, 10, 80, 30], 'color': '#ffffff', 'opacity': 80},
               'text': {'text': 'TEXT', 'at': [10, 6, 120, 34], 'size': 28, 'color': '#ffffff'},
               'logo': {'logo': 'away', 'kind': 2, 'at': [4, 4, max(8, h - 8), max(8, h - 8)]},
               'team': {'team': 'away', 'at': [0, 0, min(160, w), h]}}[kind]
        if kind in ('logo', 'team'):                       # the second one you add is the other team's
            seen = [p[kind] for p in self.design['pieces'] if kind in p]
            new[kind] = 'home' if seen.count('away') > seen.count('home') else 'away'
        home, chosen = self._design_home(), self._design_piece()
        if chosen is not None and 'group' in chosen:       # a group is chosen: the new piece goes inside it
            home = chosen['group']
        elif home is None:
            home = self.design.setdefault('pieces', [])
        home.append(new)
        self._design_build_on(new)

    def _design_copy(self):
        import copy
        p = self._design_piece()
        if p is not None:
            twin = copy.deepcopy(p)
            at = uibuild.rect(twin)
            uibuild.set_rect(twin, [at[0] + 12, at[1] + 12, at[2], at[3]])
            self._design_home().append(twin)
            self._design_build_on(twin)

    def _design_build_on(self, piece):
        """Rebuild, then choose this piece."""
        self._design_build()
        k = next((k for k, p in enumerate(self._pieces) if p[0] is piece), 0)
        self.d_piece.setCurrentIndex(k)
        self._design_pick()

    def _design_delete(self):
        p, home, i = self._design_piece(), self._design_home(), self.d_piece.currentIndex()
        if p is not None and home is not None:
            home[:] = [x for x in home if x is not p]
            self._design_build(max(0, i - 1))

    def _design_save(self):
        if self.design is None:
            return
        path, kind = QFileDialog.getSaveFileName(self, 'Save the design', os.path.join(
            self.main.last_dir(), self.design.get('name', 'design') + uibuild.SHARED),
            f'Design to share, pictures and fonts inside (*{uibuild.SHARED});;Design only (*.json)')
        if not path:
            return
        self.main.remember_dir(path)
        try:
            if path.lower().endswith('.json'):
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump({k: v for k, v in self.design.items() if not k.startswith('_')}, f, indent=1)
            else:
                if not path.lower().endswith(uibuild.SHARED):
                    path += uibuild.SHARED
                uibuild.pack(self.design, path)
        except (OSError, ValueError) as x:
            QMessageBox.warning(self, 'Could Not Save the Design', str(x))
            return
        self.note.setText(f'Design saved to {os.path.basename(path)}. Open it again from Styles › Open a Design File.')

    def _design_package(self):
        """Everything in this look as one mod: the scorebug on this theme, every ballpark's boards and the
        broadcast screens repainted in its colours, and the design file itself for whoever wants to change it."""
        from .. import catalog
        if self.design is None or not self.layout:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle('Make a Package')
        v = QVBoxLayout(dlg)
        v.setContentsMargins(*[theme.d(18)] * 4)
        v.setSpacing(theme.d(10))
        v.addWidget(label('A package is one mod that carries a whole look. Switch it on and the game wears it '
                          'everywhere; export it from Mods to share it.', 'Sub', wrap=True))
        name_edit = QLineEdit(str(self.design.get('name', 'My Look')).replace('MTS_', ''))
        name_edit.setPlaceholderText('A name for the package')
        v.addWidget(name_edit)
        ticks = []
        for text in ('This design, where it is open now', 'Every ballpark’s boards, in its colours',
                     'The broadcast screens, in its colours, with a lineup card and an inning break card to match'):
            c = QCheckBox(text)
            c.setChecked(True)
            ticks.append(c)
            v.addWidget(c)
        keep = QCheckBox('Boards and screens keep their own main colour')
        keep.setChecked(True)
        v.addWidget(keep)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(button('Cancel', on_click=dlg.reject))
        row.addWidget(button('Make It', True, dlg.accept))
        v.addLayout(row)
        name = re.sub(r'\s+', ' ', name_edit.text()).strip() if dlg.exec() == QDialog.Accepted else ''
        if not name:
            return
        try:
            title = f'Package: {name}'
            mod = next((m for m in self.main.lib.list() if m.name == title), None) or self.main.lib.create(
                title, self.main.settings.get('author', ''), 'A full broadcast look: scorebug, stadium boards and '
                'broadcast screens in one palette. Made in the Scoreboard sandbox.')
            entries, palette = [], uibuild.colours(self.design)
            slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') or 'package'
            if ticks[0].isChecked():
                entries.append(recipes.style_recipe(self.rel, self.layout, self.main.game.original(self.rel)))
                self._write_art(mod)
                self._write_fonts(mod)
            fs = self.main.game.file_set()
            packs = [p for _g, rows in catalog.board_groups(self.main.game) for _n, p in rows] if ticks[1].isChecked() \
                else []
            if ticks[2].isChecked():
                packs += catalog.packs_in(self.main.game, 'NSW/UI/GAME/PRES')
            cards_rel = samples.pres_of(self.rel) if ticks[2].isChecked() else None
            if cards_rel and cards_rel in fs:             # this theme's own screens: matched, with the two cards built in
                lay = uilayout.Layout.open(self.main.game.original(cards_rel))
                boards.match(lay, palette, keep_main=keep.isChecked())
                made = 0
                for _title, card in samples.CARDS.values():
                    if lay.find(str(card['replaces'])) is not None:
                        try:
                            samples.place_design(lay, samples.card_in_palette(card, palette))
                            made += 1
                        except ValueError:
                            pass
                if made:
                    entries.append(recipes.style_recipe(cards_rel, lay, self.main.game.original(cards_rel)))
                else:
                    cards_rel = None
            for pack in packs:
                if pack[:-4].upper() + '.NSW' in ((self.rel.upper() if ticks[0].isChecked() else ''),
                                                  (cards_rel or '').upper()):
                    continue                              # this file already carries a design itself
                if pack[:-4] + '.NSW' in fs:
                    entries.append({'file': pack[:-4] + '.NSW', 'match': palette, 'keep': keep.isChecked()})
            folder = os.path.join(mod.path, 'layouts')
            os.makedirs(folder, exist_ok=True)
            with open(os.path.join(folder, slug + '.json'), 'w', encoding='utf-8') as f:
                json.dump(entries, f)
            os.makedirs(os.path.join(mod.path, 'designs'), exist_ok=True)
            uibuild.pack(self.design, os.path.join(mod.path, 'designs', slug + uibuild.SHARED))
        except Exception as x:
            QMessageBox.warning(self, 'Could Not Make the Package', str(x))
            return
        self._fill_styles()
        self.main.changed(f'{title} made: {len(entries)} screens in one mod. Switch it on in Mods and apply; export '
                          'it from there to share it.')

    def _design_open(self, path):
        """A design from a file: a .json, or one shared file with its pictures inside."""
        if path.lower().endswith(uibuild.SHARED):
            name = re.sub(r'[^A-Za-z0-9_-]+', '_', os.path.splitext(os.path.basename(path))[0]) or 'design'
            from .. import game as gamefile
            return uibuild.unpack(path, os.path.join(os.path.dirname(gamefile.settings_path()), 'designs', name))
        with open(path, encoding='utf-8') as f:
            design = json.load(f)
        design['_folder'] = os.path.dirname(path)
        return design

    # ------------------------------------------------------------------ styles
    def _lang_bytes(self):
        """The text file as the layout needs it: the game's plus the words of any design built into it."""
        if self._lang_base is None or not self.layout:
            return None
        if not (self.layout.words[0] or self.layout.words[1]):
            return self._lang_base
        return uilang.add(self._lang_base, *self.layout.words)

    def _use(self, lay):
        """Swap in a whole layout (a style, a design, the game's own)."""
        self.layout = lay
        try:
            data = self._lang_bytes()
            self.lang = uilang.Lang(data) if data else None
        except Exception:
            pass
        self._asset_changed()

    def _fill_styles(self):
        self.styles.blockSignals(True)
        self.styles.clear()
        self.styles.addItem('Styles', None)
        if self.rel and '/PRES/' in self.rel.upper():         # broadcast cards built from nothing
            for key, (title, design) in samples.CARDS.items():
                if self.which.findText(str(design['replaces'])) >= 0:
                    self.styles.addItem(title, ('card', key))
            self.styles.addItem('Open a Design File…', ('design', None))
        if self.rel and self.rel.upper() in samples.THEMES:
            if self.rel.upper() == samples.THEME:           # the stock bug rearranged: Theme 1's pieces only
                self.styles.addItem('Wide Top Bar', ('built-in', 'wide'))
                self.styles.addItem('Split Bar', ('built-in', 'split'))
                self.styles.addItem('Glass Bar', ('built-in', 'glass'))
            for key, (title, _d) in samples.DESIGNS.items():
                self.styles.addItem(title, ('built-in', key))
            self.styles.addItem('New Blank Design', ('new', None))
            self.styles.addItem('Open a Design File…', ('design', None))
        try:
            for m in self.main.lib.list():
                for path in recipes.files(m.path, 'layouts'):
                    try:
                        with open(path, encoding='utf-8') as f:
                            entries = json.load(f)
                    except (OSError, ValueError):
                        continue
                    for e in entries if isinstance(entries, list) else []:
                        if isinstance(e, dict) and e.get('runs') and \
                                str(e.get('file', '')).strip('/').upper() == self.rel.upper():
                            self.styles.addItem(m.name.replace('Scorebug: ', ''), ('saved', path))
                            break
        except Exception:
            pass
        self.styles.blockSignals(False)

    def _style_picked(self, i):
        what = self.styles.itemData(i)
        self.styles.setCurrentIndex(0)
        if not what or not self.layout:
            return
        try:
            lay = uilayout.Layout.open(self.main.game.original(self.rel))
            if what[0] == 'design':
                path, _ = QFileDialog.getOpenFileName(self, 'Open a design', self.main.last_dir(),
                                                      f'Designs (*{uibuild.SHARED} *.json)')
                if not path:
                    return
                self.main.remember_dir(path)
                if self._design_start(self._design_open(path)):
                    self.note.setText('Design opened. Add pieces, pick one to change it, then Save to My Mod.')
                return
            elif what[0] == 'new':
                if self._design_start({'name': 'MTS_Mine', 'size': [600, 48], 'pieces': [
                        {'box': [0, 0, 600, 48], 'color': '#101010', 'opacity': 85}]}):
                    self.note.setText('A blank design. Add pieces, pick one to change it, then Save to My Mod.')
                return
            elif what[0] == 'card':
                if self._design_start(samples.CARDS[what[1]][1]):
                    self.note.setText('Card loaded. It takes the place of the game’s own screen. Pick a piece to '
                                      'change it, then Save to My Mod.')
                return
            elif what[0] == 'built-in' and what[1] in samples.DESIGNS:
                if self._design_start(samples.DESIGNS[what[1]][1]):
                    self.note.setText('Design loaded. Add pieces, pick one to change it, then Save to My Mod.')
                return
            elif what == ('built-in', 'glass'):
                samples.glass_bar(lay, self._table)
            elif what[0] == 'built-in':
                samples.wide_top_bar(lay, split=what[1] == 'split')
            else:
                with open(what[1], encoding='utf-8') as f:
                    for e in json.load(f):
                        if e.get('runs') and str(e.get('file', '')).strip('/').upper() == self.rel.upper():
                            recipes.apply_style(lay, e)
        except Exception as x:
            QMessageBox.warning(self, 'Could Not Load the Style', str(x))
            return
        self._design_stop()
        self._use(lay)
        self.note.setText('Style loaded. Change what you like, then Save to My Mod or Save as Style.')

    def save_style(self):
        if not self.layout:
            return
        name, ok = QInputDialog.getText(self, 'Save as Style', 'A name for this look:')
        name = re.sub(r'\s+', ' ', name or '').strip()
        if not ok or not name:
            return
        try:
            entry = recipes.style_recipe(self.rel, self.layout, self.main.game.original(self.rel))
            if not entry['runs']:
                QMessageBox.information(self, 'Nothing to Save', 'This layout is the same as the game’s.')
                return
            title = f'Scorebug: {name}'
            mod = next((m for m in self.main.lib.list() if m.name == title), None)
            if mod is None:
                mod = self.main.lib.create(title, self.main.settings.get('author', ''),
                                           'A scorebug look saved from the Scoreboard sandbox.')
            folder = os.path.join(mod.path, 'layouts')
            os.makedirs(folder, exist_ok=True)
            slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') or 'style'
            with open(os.path.join(folder, slug + '.json'), 'w', encoding='utf-8') as f:
                json.dump([entry], f)
            self._write_art(mod)
            self._write_fonts(mod)
            own = self.main.active_mod(rel=self._pack)          # and the pieces you repainted for it
            src = os.path.dirname(self.main.lib.texture_path(own, self._pack, 'x')) if own else None
            if src and os.path.isdir(src) and own.path != mod.path:
                import shutil
                shutil.copytree(src, os.path.dirname(self.main.lib.texture_path(mod, self._pack, 'x')),
                                dirs_exist_ok=True)
        except Exception as x:
            QMessageBox.warning(self, 'Could Not Save the Style', str(x))
            return
        self._fill_styles()
        self.main.changed(f'{title} saved as its own mod. It is in the Styles list here and in your Mods list.')

    # ------------------------------------------------------------------ drawing
    def _tex_img(self, name):
        """A texture as the mod has it (your replaced PNG if there is one), as a PIL image."""
        if name in self._img_cache:
            return self._img_cache[name]
        img = None
        try:
            from PIL import Image
            mod = self.main.active_mod(rel=self._pack)
            own = self.main.lib.texture_path(mod, self._pack, name) if mod else None
            hit = self.main.mod_png(self._pack, name)
            if own and os.path.exists(own):
                img = Image.open(own).convert('RGBA')
            elif hit and os.path.exists(hit[1]):
                img = Image.open(hit[1]).convert('RGBA')
            else:
                tex = self.main.tex(self._pack)
                e = next(e for e in tex.entries if e['name'] == name)
                img = tex.image(e).convert('RGBA')
            if max(img.size) > 1024:
                img.thumbnail((1024, 1024))
        except Exception:
            img = None
        self._img_cache[name] = img
        return img

    def _redraw(self):
        if not (self.layout and self.asset):
            return
        sc = uirender.scenes(self.asset)
        hidden = {k.off for i, k in enumerate(sc) if i != self._scene} if len(sc) > 1 else set()
        try:
            a = self._anim()
            pose = self._anim_of.pose(a.index, self.frame.value()) if a else None
            img, hits = uirender.render(self.layout, self.asset, self._tex_img, self._table, states=self.states,
                                        effects=self.fx.isChecked(), hidden=hidden, fonts=self._load_fonts(),
                                        situation=self.sit, lang=self.lang, reveal=self._reveal, pose=pose,
                                        size=self.screen)
        except Exception as x:
            self.note.setText(f'Could not draw the layout: {x}')
            return
        self._hits = hits
        self.canvas.pixmap = QPixmap.fromImage(pil_to_qimage(img))
        self.canvas.hits = [(h.rect[0], h.rect[1], h.rect[2], h.rect[3], h.node.kind == 0x22) for h in hits]
        self.canvas.offset = (0, 0)
        n = self.node
        if self.board:                                   # a board fills its sign: nothing to place
            self.canvas.rect_ = None
            self.canvas.view = (0, 0, self.screen[0], self.screen[1])
        elif n:
            ax, ay, _, _ = n.abs_rect()
            self.canvas.rect_ = (ax, ay, n.w * self.sscale.value(), n.h * self.sscale.value())
            self.canvas.base = (ax, ay)
            if self.zoom.isChecked():
                w, h = self.canvas.rect_[2], self.canvas.rect_[3]
                pad = max(60, 0.25 * max(w, h))
                vw, vh = w + 2 * pad, h + 2 * pad
                if vw / vh < 16 / 9:
                    vw = vh * 16 / 9
                else:
                    vh = vw * 9 / 16
                vw, vh = min(vw, 1920), min(vh, 1080)
                vx = max(0, min(1920 - vw, ax + w / 2 - vw / 2))       # stay on the screen: no dead space past its edge
                vy = max(0, min(1080 - vh, ay + h / 2 - vh / 2))
                self.canvas.view = (vx, vy, vw, vh)
            else:
                self.canvas.view = (0, 0, 1920, 1080)
        else:
            self.canvas.rect_ = None
        chosen = self._chosen_node.off if self._chosen_node else None
        self.canvas.chosen = next((i for i, h in enumerate(hits) if h.node.off == chosen), -1)
        self._mark_texture()
        self.canvas.update()

    def _mark_texture(self):
        h = uilayout.name_hash(self._chosen_tex) if self._chosen_tex and not self._chosen_node else None
        self.canvas.marks = [x.rect for x in self._hits if h is not None and x.node.ref == h]

    # ------------------------------------------------------------------ the game
    def _sit_set(self, attr, value):
        setattr(self.sit, attr, value)
        if attr in ('away', 'home', 'away_cc', 'home_cc'):
            self._team_art()
        self._redraw()

    def _team_art(self):
        """Each team's logo (the game's own) and colour, for the two teams in the Game row and the uniform each has
        on. In City Connect the colour is read off the game's City Connect logo."""
        for side in ('away', 'home'):
            abbr = getattr(self.sit, side)
            dark = (19, 74, 142) if side == 'away' else (20, 20, 20)
            club = teamart.color(abbr, dark)
            cc = getattr(self.sit, side + '_cc', False)
            logo = self._logo(abbr, cc) if cc else None
            setattr(self.sit, side + '_club', club)
            setattr(self.sit, side + '_color', (teamart.main_color(logo) if logo is not None else None) or club)
            setattr(self.sit, side + '_logo', logo if logo is not None else self._logo(abbr))

    def _logo(self, abbr, city_connect=False):
        key = str(abbr).upper() + ('_CC' if city_connect else '')
        if key not in self._logos:
            img = None
            try:
                pack, name = teamart.logo_name(abbr, city_connect=city_connect)
                if pack in self.main.game.file_set():
                    tex = self.main.tex(pack)
                    e = next((e for e in tex.entries if e['name'].lower() == name), None)
                    img = tex.image(e).convert('RGBA') if e else None
            except Exception:
                img = None
            self._logos[key] = img
        return self._logos[key]

    def _fill_scenes(self):
        self._scene, self._reveal = 0, set()
        sc = uirender.scenes(self.asset) if self.asset else []
        self.scene.blockSignals(True)
        self.scene.clear()
        for i, k in enumerate(sc):
            self.scene.addItem('In play' if i == 0 else f'Scene {i + 1}  ({round(k.w)}×{round(k.h)})')
        self.scene.setEnabled(len(sc) > 1)
        self.scene.blockSignals(False)
        self._fill_popups()

    def _fill_popups(self):
        sc = uirender.scenes(self.asset) if self.asset else []
        self._popups = uirender.popups(self.layout, self.asset, sc[self._scene]) if sc else []
        self.popup.blockSignals(True)
        self.popup.clear()
        self.popup.addItem('No pop-up')
        for _n, name in self._popups:
            self.popup.addItem(name)
        self.popup.setEnabled(bool(self._popups))
        self.popup.blockSignals(False)

    def _scene_changed(self, i):
        if i < 0:
            return
        self._scene, self._reveal = i, set()
        self._fill_popups()
        self._redraw()

    def _popup_changed(self, i):
        self._reveal = {self._popups[i - 1][0].off} if 0 < i <= len(self._popups) else set()
        self._redraw()

    # ------------------------------------------------------------------ states
    def _fill_states(self):
        self.state_node.blockSignals(True)
        self.state_node.clear()
        self._state_nodes = uirender.state_nodes(self.layout, self.asset) if self.asset else []
        counts = {}
        for a, n in self._state_nodes:
            counts[a.name] = counts.get(a.name, 0) + 1
            q = uiquery.text(self.layout.selector(n)).strip('[] ')
            what = q if q and len(q) < 40 else ('set by the game' if not q else f'switch {counts[a.name]}')
            self.state_node.addItem(f'{a.name} · {what} · {len(n.states)} looks')
        self.state_node.blockSignals(False)
        has = bool(self._state_nodes)
        for w in (self.state_node, self.state_pick, self.b_states_reset):
            w.setEnabled(has)
        if not has:
            self.state_node.addItem('This overlay has no switches')
        self._state_node_changed()

    def _state_node_changed(self, *_):
        i = self.state_node.currentIndex()
        self.state_pick.blockSignals(True)
        if 0 <= i < len(getattr(self, '_state_nodes', [])):
            n = self._state_nodes[i][1]
            self.state_pick.setRange(1, len(n.states))
            self.state_pick.setValue(self.states.get(n.off, getattr(uirender.render, 'picks', {}).get(n.off, 0)) + 1)
        else:
            self.state_pick.setRange(1, 1)
        self.state_pick.blockSignals(False)

    def _state_picked(self, v):
        i = self.state_node.currentIndex()
        if 0 <= i < len(self._state_nodes):
            n = self._state_nodes[i][1]
            self.states[n.off] = v - 1
            empty = n.state_children()[v - 1] is None
            self.note.setText(f'Look {v} of {len(n.states)}' + (' is empty: this part shows nothing.' if empty else '.'))
            self._redraw()

    def _states_reset(self):
        self.states = {}
        self._state_node_changed()
        self._redraw()

    # ------------------------------------------------------------------ pieces
    def _pix(self, name, rgba=(255, 255, 255, 255)):
        key = (name, rgba)
        if key in self._pix_cache:
            return self._pix_cache[key]
        pm = None
        img = self._tex_img(name)
        if img is not None:
            t = img.copy()
            t.thumbnail((256, 256))
            pm = QPixmap.fromImage(pil_to_qimage(t))
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
            pm = self._pix(name)
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
        self.tools_row.setVisible(True)

    def _orig_node(self, node):
        if not self._orig:
            return node
        if not hasattr(self, '_orig_index') or self._orig_index[0] is not self._orig:
            self._orig_index = (self._orig, {})
        idx = self._orig_index[1]
        if not idx:
            for a in self._orig.assets:
                for n in a.nodes():
                    idx[n.off] = n
        return idx.get(node.off, node)

    def _targets(self):
        """[(node, the same node in the untouched layout)] the tools act on: the clicked piece, or every place the
        overlay draws the chosen texture."""
        if self._chosen_node is not None:
            return [(self._chosen_node, self._orig_node(self._chosen_node))]
        name = self._chosen_tex
        if not (self.asset and name):
            return []
        h = uilayout.name_hash(name)
        out = []
        seen = set()
        for a in [self.asset] + [self.layout.by_hash[x] for x in self.asset.instances() if x in self.layout.by_hash]:
            for n in a.nodes():
                if n.off not in seen and n.ref == h:
                    seen.add(n.off)
                    out.append((n, self._orig_node(n)))
        return out

    def _choose(self, node, tex):
        self._chosen_node, self._chosen_tex = node, tex
        self.text_row.setVisible(node is not None and node.kind == 0x22)
        pairs = self._targets()
        for w in self._tools:
            w.setEnabled(bool(pairs))
        self.b_piece.setEnabled(bool(tex))
        if not pairs:
            return
        n, o = pairs[0]
        for sp, v in ((self.p_op, round((n.color >> 24) / 2.55)), (self.p_dx, n.x - o.x), (self.p_dy, n.y - o.y),
                      (self.p_size, round(100 * n.w / o.w) if o.w else 100)):
            sp.blockSignals(True)
            sp.setValue(v)
            sp.blockSignals(False)
        self.b_hide.setText('Show' if (n.color >> 24) == 0 else 'Hide')
        self._fill_text_row()

    def _strip_picked(self, item, _old=None):
        name = item.data(Qt.UserRole) if item else None
        self._choose(None, name)
        pairs = self._targets()
        if name and not pairs:
            self.note.setText(f'“{name}” is a second layer of a piece. It can be repainted with Replace PNG.')
        elif name:
            uses = 'once' if len(pairs) == 1 else f'{len(pairs)} times'
            self.note.setText(f'“{name}” is drawn {uses} in this overlay. Changes here apply to every one.')
        self.canvas.chosen = -1
        self._mark_texture()
        self.canvas.update()

    def _picked(self, i):
        """A piece clicked on the screen: edit just that piece."""
        if not (0 <= i < len(self._hits)):
            self._choose(None, None)
            self.canvas.marks = []
            self.note.setText(self.HINT)
            return
        h = self._hits[i]
        if self.design is not None:                       # in a design: pick the piece this belongs to
            made = self._design_asset()
            at = getattr(self.layout, 'piece_at', {})
            by_rel = {at[id(p[0])]: k for k, p in enumerate(getattr(self, '_pieces', [])) if id(p[0]) in at}
            n = h.node
            while n is not None and made is not None:
                k = by_rel.get(n.off - made.body) if n.asset is made else None
                if k is not None:
                    self.d_piece.setCurrentIndex(k)
                    self._design_pick()
                    break
                n = n.parent
            return
        self.strip.blockSignals(True)
        self.strip.setCurrentRow(-1)
        for k in range(self.strip.count()):
            if h.texture and self.strip.item(k).data(Qt.UserRole) == h.texture:
                self.strip.setCurrentRow(k)
                break
        self.strip.blockSignals(False)
        self._choose(h.node, h.texture)
        n = h.node
        r, g, b, a = n.rgba()
        what = f'“{h.texture}”' if h.texture else ('a text box' if n.kind == 0x22 else f'a plain {n.kind_name.lower()}')
        where = ' › '.join(h.path)
        self.note.setText(f'{what} in {where}: {round(n.w)}×{round(n.h)} at {round(h.rect[0])}, {round(h.rect[1])}, '
                          f'colour #{r:02x}{g:02x}{b:02x}, {round(a / 2.55)}% opacity. Edits apply to this piece only.')
        self.canvas.marks = []
        self.canvas.update()

    def _piece_edit(self, *_):
        for n, o in self._targets():
            self.layout.recolor(n, alpha=round(self.p_op.value() * 2.55))
            self.layout.move(n, o.x + self.p_dx.value(), o.y + self.p_dy.value())
            k = self.p_size.value() / 100
            self.layout.resize(n, o.w * k, o.h * k)
        self._redraw()

    def _tint(self):
        pairs = self._targets()
        if not pairs:
            return
        r, g, b, _ = pairs[0][0].rgba()
        c = QColorDialog.getColor(QColor(r, g, b), self, 'Tint')
        if c.isValid():
            for n, _ in pairs:
                self.layout.recolor(n, rgb=(c.red(), c.green(), c.blue()))
            self._redraw()

    def _hide(self):
        pairs = self._targets()
        if not pairs:
            return
        show = (pairs[0][0].color >> 24) == 0
        for n, o in pairs:
            self.layout.recolor(n, alpha=(o.color >> 24) or 255 if show else 0)
        self._choose(self._chosen_node, self._chosen_tex)
        self._redraw()

    def _replace_piece(self):
        name = self._chosen_tex
        if not name:
            return
        path, _ = QFileDialog.getOpenFileName(self, f'Replace {name}', self.main.last_dir(), 'Images (*.png)')
        if not path:
            return
        self.main.remember_dir(path)
        mod = self.main.active_mod(ask=True, rel=self._pack)
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
        self._img_cache.pop(name, None)
        self.main.changed(f'{name} saved to {mod.name}')
        self._fill_strip()
        self._redraw()

    # ------------------------------------------------------------------ text and fonts
    def _load_fonts(self):
        if self._fonts is not None:
            return self._fonts or None
        self._fonts = False
        try:
            if fontlib.FONTS not in self.main.game.file_set():
                return None
            table = fontlib.FontTable.open(self.main.current_file(fontlib.FONTS))
            sheet = self._sheet_img()
            self._fonts = (table, sheet)
            self._fill_font_combo()
        except Exception:
            self._fonts = False
        return self._fonts or None

    def _sheet_img(self):
        from PIL import Image
        mod = self.main.active_mod(rel=fontlib.SHEETS)
        own = self.main.lib.texture_path(mod, fontlib.SHEETS, 'english') if mod else None
        hit = self.main.mod_png(fontlib.SHEETS, 'english')
        if own and os.path.exists(own):
            return Image.open(own).convert('RGBA')
        if hit and os.path.exists(hit[1]):
            return Image.open(hit[1]).convert('RGBA')
        tex = self.main.tex(fontlib.SHEETS)
        e = next(e for e in tex.entries if e['name'] == 'english')
        return tex.image(e)

    def _fill_font_combo(self):
        table, sheet = self._fonts
        self.t_font.blockSignals(True)
        self.t_font.clear()
        self.d_font.blockSignals(True)
        self.d_font.clear()
        for f in table.fonts:
            if f.sheet != 'english':
                continue
            icon = QIcon()
            try:
                c = QColor(theme.TEXT or '#e0e0e0')
                img = fontlib.draw_text(f, sheet, 'NYY 3 BOT 7th', 16, (c.red(), c.green(), c.blue(), 255))
                icon = QIcon(QPixmap.fromImage(pil_to_qimage(img)))
            except Exception:
                pass
            self.t_font.addItem(icon, f'{f.index}', f.index)
            self.d_font.addItem(icon, f'{f.index}', f.index)
        self.t_font.blockSignals(False)
        self.d_font.blockSignals(False)

    def _fill_text_row(self):
        n = self._chosen_node
        if n is None or n.kind != 0x22 or not self.layout:
            return
        self._load_fonts()
        for w in (self.t_size, self.t_font):
            w.blockSignals(True)
        self.t_size.setValue(self.layout.text_size(n))
        i = self.t_font.findData(self.layout.text_font(n))
        self.t_font.setCurrentIndex(i)
        self.t_align.setCurrentIndex(min(2, self.layout.text_align(n)))
        for w in (self.t_size, self.t_font):
            w.blockSignals(False)

    def _text_targets(self):
        n = self._chosen_node
        return [n] if n is not None and n.kind == 0x22 else []

    def _text_font(self, *_):
        num = self.t_font.currentData()
        if num is None:
            return
        for n in self._text_targets():
            self.layout.set_text_font(n, num)
        self._redraw()

    def _text_align(self, i):
        for n in self._text_targets():
            self.layout.set_text_align(n, i)
        self._redraw()

    def _text_size(self, v):
        for n in self._text_targets():
            self.layout.set_text_size(n, v)
        self._redraw()

    def _text_color(self):
        t = self._text_targets()
        if not t:
            return
        r, g, b, _ = self.layout.text_color(t[0])
        c = QColorDialog.getColor(QColor(r, g, b), self, 'Outline colour')
        if c.isValid():
            for n in t:
                self.layout.set_text_color(n, rgb=(c.red(), c.green(), c.blue()))
            self._redraw()

    def _design_fonts(self):
        """Draw the fonts a design names into the preview's copy of the game fonts. They are written to a mod when
        the design is saved."""
        named = (self.design or {}).get('fonts') or {}
        loaded = self._load_fonts() if named else None
        if not loaded:
            return
        table, sheet = loaded
        lib = dict(fontlib.LIBRARY)
        try:
            for slot, src in named.items():
                path = fontlib.library_path(lib[src]) if src in lib else (
                    src if os.path.isabs(src) else os.path.join(self.design.get('_folder', ''), src))
                sheet, _n = fontlib.import_font(table, sheet, int(slot), path)
        except Exception as x:
            self.note.setText(f'A font this design names could not be drawn in: {x}')
        self._fonts = (table, sheet)
        self._fill_font_combo()

    def _write_fonts(self, mod):
        """The game fonts as the design changed them, into a mod."""
        if not mod or not (self.design or {}).get('fonts') or not self._fonts:
            return
        import tempfile
        table, sheet = self._fonts
        tmp = os.path.join(tempfile.mkdtemp(prefix='mts_'), os.path.basename(fontlib.FONTS))
        with open(tmp, 'wb') as f:
            f.write(table.bytes())
        self.main.lib.add_file(mod, fontlib.FONTS, tmp)
        self.main.lib.add_texture(mod, fontlib.SHEETS, 'english', sheet)

    def _import_font(self, path=None):
        t = self._text_targets()
        fonts = self._load_fonts()
        if not t or not fonts:
            return
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, 'Import a font', self.main.last_dir(),
                                                  'Fonts (*.ttf *.otf)')
            if not path:
                return
            self.main.remember_dir(path)
        mod = self.main.active_mod(ask=True, rel=fontlib.SHEETS)
        if not mod:
            return
        slot = self.layout.text_font(t[0])
        if self.design is not None:                       # the design remembers the font, so it travels with it
            lib = {fontlib.library_path(f): n for n, f in fontlib.LIBRARY}
            self.design.setdefault('fonts', {})[str(slot)] = lib.get(path, path)
        table, sheet = fonts
        try:
            sheet2, drawn = fontlib.import_font(table, sheet, slot, path)
        except Exception as x:
            QMessageBox.warning(self, 'Could Not Import', str(x))
            return
        data = table.bytes()

        def write(p):
            with open(p, 'wb') as f:
                f.write(data)
        self.main.lib.add_texture(mod, fontlib.SHEETS, 'english', sheet2)
        self.main.save_file(fontlib.FONTS, write, f'{os.path.basename(path)} is now game font {slot} in {{mod}}. '
                            'Apply, then check it in a game.')
        self._fonts = (fontlib.FontTable(data), sheet2)
        self._fill_font_combo()
        self._fill_text_row()
        self.note.setText(f'{drawn} letters from {os.path.basename(path)} replace game font {slot}. Every text box '
                          'that uses that font, here and in the menus, changes with it.')
        self._redraw()

    # ------------------------------------------------------------------ placing the overlay
    def _dragged(self, x, y):
        for s, v in ((self.sx, x), (self.sy, y)):
            s.blockSignals(True)
            s.setValue(v)
            s.blockSignals(False)
        self._apply()

    def _spins(self, *_):
        self._apply()
        self._redraw()

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
            if self.design is not None and self.asset and self.asset.name == 'Scorebar':
                dx, dy = getattr(self.layout, 'design_origin', (5, 53))
                self.design['x'], self.design['y'] = self.sx.value() + dx, self.sy.value() + dy
            self.layout.move(self.node, self.sx.value(), self.sy.value())
            if abs(self.sscale.value() - self._scale0) > 1e-6:
                self.layout.scale(self.node, self.sscale.value())

    # ------------------------------------------------------------------ stadium boards
    def _board_note(self):
        e = self._shown.get(self.which.currentText().lower())
        w, h = self.screen
        if not e:
            return (f'A part of this park’s boards, {w} × {h}. Click a piece to edit it, or repaint the whole park '
                    'from the right. Save writes the boards into your mod.')
        about = str(e.get('about') or '').strip().rstrip('.')
        return ((about + '. ' if about else '') + f'Drawn onto the sign “{e.get("targetname", "")}” at '
                f'{e.get("width", w)} × {e.get("height", h)}. Click a piece to edit it, or repaint the whole park '
                'from the right. Save writes the boards into your mod.')

    def _board_sources(self):
        """[(title, design or path)] the scorebugs a board can be matched to: the built-in designs, the styles
        saved from a design, and a design file."""
        out = [(title, design) for _key, (title, design) in samples.DESIGNS.items()]
        try:
            for m in self.main.lib.list():
                for path in recipes.files(m.path, 'layouts'):
                    try:
                        with open(path, encoding='utf-8') as f:
                            entries = json.load(f)
                    except (OSError, ValueError):
                        continue
                    for e in entries if isinstance(entries, list) else []:
                        for d in (e.get('designs') or []) if isinstance(e, dict) else []:
                            out.append((m.name.replace('Scorebug: ', ''), d))
        except Exception:
            pass
        return out

    def _fill_board(self):
        """The Match list and the swatches of the board's own colours."""
        self.bd_match.blockSignals(True)
        self.bd_match.clear()
        self.bd_match.addItem('Pick a scorebug to match…', None)
        for title, design in self._board_sources():
            self.bd_match.addItem(title, design)
        self.bd_match.addItem('From a Design File…', 'file')
        self.bd_match.blockSignals(False)
        self._board_palette = [c for c, _ in boards.colours(self.layout)][:8] if self.layout else []
        for i, b in enumerate(self.bd_swatches):
            c = self._board_palette[i] if i < len(self._board_palette) else None
            b.setEnabled(c is not None)
            b.setToolTip(f'{c}: change every piece of this colour in the park’s boards' if c else '')
            b.setStyleSheet(f'QPushButton {{ background: {c}; border: 1px solid {theme.LINE}; border-radius: 8px; }}'
                            if c else f'QPushButton {{ background: transparent; border: 1px dashed {theme.LINE}; '
                                      'border-radius: 8px; }')

    def _board_match(self, i):
        design = self.bd_match.itemData(i)
        self.bd_match.setCurrentIndex(0)
        if not (self.matchable and self.layout and design):
            return
        if design == 'file':
            path, _ = QFileDialog.getOpenFileName(self, 'Open a design', self.main.last_dir(),
                                                  f'Designs (*{uibuild.SHARED} *.json)')
            if not path:
                return
            self.main.remember_dir(path)
            try:
                design = self._design_open(path)
            except (OSError, ValueError, KeyError, zipfile.BadZipFile) as x:
                QMessageBox.warning(self, 'Could Not Open the Design', str(x))
                return
        palette = uibuild.colours(design)
        if not palette:
            QMessageBox.information(self, 'Nothing to Match', 'That design has no colours of its own.')
            return
        try:
            plan = boards.match(self.layout, palette, keep_main=self.bd_keep.isChecked())
        except Exception as x:
            QMessageBox.warning(self, 'Could Not Match', str(x))
            return
        self._board_design = design
        self.bd_all.setEnabled(True)
        self.bd_font.setEnabled(any(uibuild.kind_of(p) == 'text' for p, *_ in uibuild.walk(design.get('pieces') or [])))
        self._fill_board()
        self._redraw()
        self.note.setText(f'{len(plan)} colours of these screens now follow {design.get("name", "the design")}. '
                          'Change any of them from the swatches, then Save to My Mod.')

    def _board_font(self):
        """The board's most used font becomes the font the matched scorebug uses most."""
        if not (self.matchable and self.layout and self._board_design):
            return
        used = {}
        for p, *_ in uibuild.walk(self._board_design.get('pieces') or []):
            if uibuild.kind_of(p) == 'text':
                f = int(p.get('font', 25))
                used[f] = used.get(f, 0) + 1
        have = boards.fonts_used(self.layout)
        if not used or not have:
            return
        font, main = max(used, key=used.get), max(have, key=have.get)
        n = boards.set_font(self.layout, font, only=main)
        self._redraw()
        self.note.setText(f'{n} text boxes of this park’s boards now use game font {font}, the scorebug’s. '
                          'A font you imported for the scorebug comes along with the scorebug’s own mod.')

    def _board_all(self):
        """Every park's boards in the matched scorebug's colours, written into the mod."""
        from .. import catalog
        design = self._board_design
        if not (self.board and design):
            return
        rows = [p for g, rs in catalog.board_groups(self.main.game) for _n, p in rs]
        name = design.get('name', 'the design')
        if QMessageBox.question(self, 'Match Every Park', f'Repaint {len(rows)} board files, every ballpark’s and '
                                f'the shared ones, in the colours of {name} and save them into your mod?\n\n'
                                'Boards you already changed in that mod are repainted from where you left them.') \
                != QMessageBox.Yes:
            return
        mod = self.main.active_mod(ask=True, rel=self.rel)
        if not mod:
            return
        import tempfile
        palette, keep = uibuild.colours(design), self.bd_keep.isChecked()
        tmp, done, failed = tempfile.mkdtemp(prefix='mts_'), 0, []
        for pack in rows:
            rel = pack[:-4] + '.NSW'
            try:
                lay = uilayout.Layout.open(self.main.current_file(rel))
                if rel.upper() == self.rel.upper():
                    lay = self.layout                     # the one on screen, as you have it
                elif not boards.match(lay, palette, keep_main=keep):
                    continue
                out = os.path.join(tmp, os.path.basename(rel))
                with open(out, 'wb') as f:
                    f.write(lay.bytes())
                self.main.lib.add_file(mod, rel, out)
                done += 1
            except Exception as x:
                failed.append(f'{os.path.basename(rel)}: {x}')
        self.main.changed(f'{done} board files now follow {name}, saved into {mod.name}. Apply, then look around a '
                          'ballpark.' + (f' {len(failed)} could not be read and were left alone.' if failed else ''))

    def _board_recolour(self, i):
        palette = getattr(self, '_board_palette', [])
        if not (self.matchable and self.layout and 0 <= i < len(palette)):
            return
        c = QColorDialog.getColor(QColor(palette[i]), self, 'Change this colour in all of the park’s boards')
        if c.isValid() and c.name() != palette[i]:
            boards.recolour(self.layout, palette[i], c.name())
            self._fill_board()
            self._redraw()

    def reset(self):
        """The overlay, and the overlays it shows, back to the game's own."""
        self._design_stop()
        if self.matchable and self.layout:                # these are repainted as a whole file: so is going back
            try:
                self._use(uilayout.Layout.open(self.main.game.original(self.rel)))
                self._fill_board()
            except Exception as x:
                QMessageBox.warning(self, 'Could Not Reset', str(x))
            return
        if self.layout and self.asset and self._orig is not None:
            try:
                self.layout.restore(self.asset, source=self._orig.d)
            except ValueError:                   # a style that added to the file: start over from the game's own
                try:
                    self._use(uilayout.Layout.open(self.main.game.original(self.rel)))
                except Exception as x:
                    QMessageBox.warning(self, 'Could Not Reset', str(x))
                return
        self._asset_changed()

    def save(self):
        if not self.layout:
            return
        data = self.layout.bytes()

        def write(path):
            with open(path, 'wb') as f:
                f.write(data)
        try:
            words = self.layout.words[0] or self.layout.words[1]
            lang = self._lang_bytes() if words else None
            if not self.main.save_file(self.rel, write, self.which.currentText() +
                                       ' layout saved into {mod}. Apply, then check it in a game.'):
                return
            if lang:                                         # a design's words travel with it
                import tempfile
                lrel = recipes.lang_of(self.rel)
                tmp = os.path.join(tempfile.mkdtemp(prefix='mts_'), os.path.basename(lrel))
                with open(tmp, 'wb') as f:
                    f.write(lang)
                mod = self.main.active_mod(rel=self.rel)
                if mod:
                    self.main.lib.add_file(mod, lrel, tmp)
                    self.main.changed('')
            self._write_art(self.main.active_mod(rel=self.rel))
            self._write_fonts(self.main.active_mod(rel=self.rel))
        except Exception as x:
            QMessageBox.warning(self, 'Could Not Save', str(x))
