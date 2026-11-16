"""The scoreboard sandbox: a UI layout (the scorebug and the other overlays) drawn the way the game lays it out, with
its real textures. Drag the overlay to place it, click any piece to tint, fade, move, resize, hide or repaint it, flip
the layout's states to see each look, and save the result into the active mod."""
import os

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFileDialog, QHBoxLayout,
                               QListView, QListWidget, QListWidgetItem, QMessageBox, QSpinBox, QVBoxLayout, QWidget)

from .. import fontlib, uilayout, uirender
from . import theme
from .common import button, label
from .widgets import pil_to_qimage

PRESETS = [('Game default', None), ('Bottom right', (1390, 838)), ('Bottom left', (40, 838)),
           ('Top right', (1390, 40)), ('Top left', (40, 40)), ('Bottom centre', (723, 860))]
BACKDROP = (31, 77, 46, 255)


class Canvas(QWidget):
    moved = Signal(float, float)
    released = Signal()
    picked = Signal(int)           # index into hits, -1 for none

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
        self._drag = None
        self._moved = False

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
        screen = QRectF(ox, oy, 1920 * k, 1080 * k)
        qp.fillRect(self.rect(), QColor(theme.BG))
        qp.setClipRect(screen)
        qp.fillRect(screen, QColor(*BACKDROP[:3]))
        if self.pixmap is not None:
            dx, dy = self.offset
            qp.drawPixmap(QRectF(ox + dx * k, oy + dy * k, 1920 * k, 1080 * k), self.pixmap, QRectF(self.pixmap.rect()))
        qp.setPen(QPen(QColor(255, 255, 255, 50), 1, Qt.DashLine))
        qp.setBrush(Qt.NoBrush)
        qp.drawRect(QRectF(ox + 96 * k, oy + 54 * k, 1728 * k, 972 * k))       # the TV safe area
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
            qp.drawText(screen, Qt.AlignCenter, 'Pick a scorebug theme')
        qp.end()

    def _to_screen(self, pos):
        k, ox, oy = self._fit()
        return (pos.x() - ox) / k, (pos.y() - oy) / k

    def mousePressEvent(self, e):
        self._drag = (e.position(), self.rect_)
        self._moved = False

    def mouseMoveEvent(self, e):
        if not (self._drag and self._drag[1]):
            return
        p0, r0 = self._drag
        k, _, _ = self._fit()
        if (e.position() - p0).manhattanLength() < 4 and not self._moved:
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
        elif self._drag and self._moved:
            self.released.emit()
        self._drag = None


class LayoutEditor(QWidget):
    """The scoreboard sandbox. One .NSW layout per scorebug theme."""
    HINT = ('Drag the red box to place the overlay. Click a piece to edit just that piece, or pick a texture in '
            'the strip to change every place it is drawn. Save writes the layout into your mod.')

    def __init__(self, main):
        super().__init__()
        self.main = main
        self.rel = None
        self.layout = None
        self._orig = None
        self.asset = None
        self.node = None
        self.states = {}           # {node offset: state shown}
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
        self.b_states_reset = button('All Looks to First', on_click=self._states_reset)
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
        self.canvas = Canvas()
        self.canvas.moved.connect(self._dragged)
        self.canvas.released.connect(self._redraw)
        self.canvas.picked.connect(self._picked)
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
        self.b_tcolor = button('Text Colour', on_click=self._text_color)
        self.b_font_import = button('Import Font…', on_click=self._import_font)
        self.b_font_import.setToolTip('Draw a font file of your own into the game, in place of the font this box uses')
        trow.addWidget(self.t_font, 3)
        trow.addWidget(self.t_size, 1)
        trow.addWidget(self.b_tcolor, 1)
        trow.addWidget(self.b_font_import, 1)
        self.text_row = QWidget()
        self.text_row.setLayout(trow)
        self.text_row.hide()
        lay.addWidget(self.text_row)
        self._fonts = None             # (FontTable, sheet) as the active mod has them
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

    # ------------------------------------------------------------------ opening
    def open(self, pack_rel):
        """pack_rel: the theme's texture pack, e.g. NSW/UI/GAME/THEME1.TEX."""
        rel = pack_rel[:-4] + '.NSW'
        self.rel = rel
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
            self._empty('This pack’s layout has no overlays the manager can place yet.')
            self.which.blockSignals(False)
            return
        self._enable(True)
        self.note.setText(self.HINT)
        for n in names:
            self.which.addItem(n)
        self.which.blockSignals(False)
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
                  self.state_node, self.state_pick, self.b_states_reset, self.fx, self.zoom):
            w.setEnabled(on)

    def _asset_changed(self, *_):
        if not self.layout or not self.which.currentText():
            return
        self._choose(None, None)
        self.asset = self.layout.find(self.which.currentText())
        self.node = self.asset.container() if self.asset else None
        self.states = {}
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
        self._fill_states()
        self._fill_strip()
        self.note.setText(self.HINT)
        self._redraw()

    # ------------------------------------------------------------------ drawing
    def _tex_img(self, name):
        """A texture as the mod has it (your replaced PNG if there is one), as a PIL image."""
        if name in self._img_cache:
            return self._img_cache[name]
        img = None
        try:
            from PIL import Image
            mod = self.main.active_mod()
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
        hidden = set()
        try:
            img, hits = uirender.render(self.layout, self.asset, self._tex_img, self._table, states=self.states,
                                        effects=self.fx.isChecked(), hidden=hidden, fonts=self._load_fonts())
        except Exception as x:
            self.note.setText(f'Could not draw the layout: {x}')
            return
        self._hits = hits
        self.canvas.pixmap = QPixmap.fromImage(pil_to_qimage(img))
        self.canvas.hits = [(h.rect[0], h.rect[1], h.rect[2], h.rect[3], h.node.kind == 0x22) for h in hits]
        self.canvas.offset = (0, 0)
        n = self.node
        if n:
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
                self.canvas.view = (ax + w / 2 - vw / 2, ay + h / 2 - vh / 2, vw, vh)
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

    # ------------------------------------------------------------------ states
    def _fill_states(self):
        self.state_node.blockSignals(True)
        self.state_node.clear()
        self._state_nodes = uirender.state_nodes(self.layout, self.asset) if self.asset else []
        counts = {}
        for a, n in self._state_nodes:
            counts[a.name] = counts.get(a.name, 0) + 1
            self.state_node.addItem(f'{a.name} · switch {counts[a.name]} · {len(n.states)} looks')
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
            self.state_pick.setValue(self.states.get(n.off, 0) + 1)
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
        mod = self.main.active_mod()
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
        self.t_font.blockSignals(False)

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

    def _text_size(self, v):
        for n in self._text_targets():
            self.layout.set_text_size(n, v)
        self._redraw()

    def _text_color(self):
        t = self._text_targets()
        if not t:
            return
        r, g, b, _ = self.layout.text_color(t[0])
        c = QColorDialog.getColor(QColor(r, g, b), self, 'Text colour')
        if c.isValid():
            for n in t:
                self.layout.set_text_color(n, rgb=(c.red(), c.green(), c.blue()))
            self._redraw()

    def _import_font(self):
        t = self._text_targets()
        fonts = self._load_fonts()
        if not t or not fonts:
            return
        path, _ = QFileDialog.getOpenFileName(self, 'Import a font', self.main.last_dir(), 'Fonts (*.ttf *.otf)')
        if not path:
            return
        self.main.remember_dir(path)
        mod = self.main.active_mod(ask=True)
        if not mod:
            return
        slot = self.layout.text_font(t[0])
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
            self.layout.move(self.node, self.sx.value(), self.sy.value())
            if abs(self.sscale.value() - self._scale0) > 1e-6:
                self.layout.scale(self.node, self.sscale.value())

    def reset(self):
        self.sscale.setValue(1.0)
        self._preset(0)
        if self.layout and self.asset:               # and every piece back to how the game has it
            for a in [self.asset] + [self.layout.by_hash[x] for x in self.asset.instances() if x in self.layout.by_hash]:
                for n in a.nodes():
                    if n is self.node:
                        continue
                    o = self._orig_node(n)
                    if (n.color, n.x, n.y, n.w, n.h, n.ref) != (o.color, o.x, o.y, o.w, o.h, o.ref):
                        self.layout.recolor(n, rgb=o.rgba()[:3], alpha=o.color >> 24)
                        self.layout.move(n, o.x, o.y)
                        self.layout.resize(n, o.w, o.h)
                        if n.ref != o.ref:
                            import struct
                            struct.pack_into('<I', self.layout.d, n.off + 0x30, o.ref)
                            n.ref = o.ref
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
