"""Uniforms › Builder: recolour a part, add pinstripes and a logo, see it flat or on the player, save it into the mod."""
import os
import tempfile

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
                               QPushButton, QScrollArea, QSlider, QStackedWidget, QVBoxLayout, QWidget)
from PySide6.QtWidgets import QButtonGroup

from .. import uniformbuilder as UB
from .common import button, label, section_title
from .playerpreview import PlayerPreview
from .widgets import ImageView, pil_to_qimage


def _swatch(rgb):
    b = QPushButton()
    b.setCursor(Qt.PointingHandCursor)
    b.setFixedSize(54, 34)
    _paint(b, rgb)
    return b


def _paint(b, rgb):
    b.setStyleSheet(f'QPushButton {{ background: rgb({rgb[0]}, {rgb[1]}, {rgb[2]}); border: 2px solid rgba(128,128,128,0.6); '
                    f'border-radius: 10px; min-height: 0; padding: 0; }}')


class Mannequin(PlayerPreview):
    """The player from On a Player, wearing the builder's unsaved parts."""
    def __init__(self, main, drafts):
        self.drafts = drafts
        super().__init__(main)
        for w in (self.name, self.number, self.font, self.b_image):
            w.hide()

    def _override(self, pack, name):
        return self.drafts.get((pack, name)) or super()._override(pack, name)


def _blank():
    return dict(new={}, stripes=False, stripe_color=(20, 30, 70), spacing=36, width=3, logos=[], cur=-1)


class JerseyBuilder(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.folder, self.entry, self.rel = None, None, None
        self.base_img, self.small, self.colors = None, None, []
        self.state = {}                 # part index -> its settings, so every part keeps its edits while you switch
        self.bases = {}                 # part index -> (pack rel, texture name, image)
        self.drafts = {}                # (pack rel, texture name) -> PNG the player preview wears
        self._tmp = tempfile.mkdtemp(prefix='mts-builder-')
        self._loading = False
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(18)
        side = QVBoxLayout()
        side.setContentsMargins(0, 0, 10, 0)
        side.setSpacing(8)
        side.addWidget(section_title('Part'))
        self.part = QButtonGroup(self)          # one chip per part, two rows of four
        chips = QGridLayout()
        chips.setSpacing(6)
        for i, (name, _, _) in enumerate(UB.PARTS):
            b = QPushButton(name.replace(', New Style', ' 2'))
            b.setObjectName('Chip')
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setChecked(i == 0)
            self.part.addButton(b, i)
            chips.addWidget(b, i // 2, i % 2)
        self.part.idClicked.connect(self._load_part)
        self.part.currentIndex = self.part.checkedId
        side.addLayout(chips)
        side.addWidget(section_title('Colours'))
        self.sw_grid = QGridLayout()
        self.sw_grid.setSpacing(8)
        self.sw_grid.setAlignment(Qt.AlignLeft)
        side.addLayout(self.sw_grid)
        side.addWidget(label('Click a colour to change it everywhere on this part.', 'Sub', wrap=True))
        side.addWidget(section_title('Pinstripes'))
        row = QHBoxLayout()
        row.setSpacing(10)
        self.stripes = QCheckBox('On the fabric')
        self.stripes.toggled.connect(self._later)
        self.b_stripe = _swatch((20, 30, 70))
        self.b_stripe.clicked.connect(self._pick_stripe)
        row.addWidget(self.stripes, 1)
        row.addWidget(self.b_stripe)
        side.addLayout(row)
        self.spacing = self._slider(12, 120, 36)
        self.width = self._slider(1, 12, 3)
        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)
        for i, (text, sl) in enumerate((('Spacing', self.spacing), ('Thickness', self.width))):
            lb = label(text, 'Sub')
            lb.setFixedWidth(72)
            form.addWidget(lb, i, 0)
            form.addWidget(sl, i, 1)
        side.addLayout(form)
        side.addWidget(section_title('Logos'))
        self.logo_pick = QComboBox()             # every logo on this part; the sliders move the one shown
        self.logo_pick.currentIndexChanged.connect(self._logo_chosen)
        side.addWidget(self.logo_pick)
        lrow = QHBoxLayout()
        lrow.setSpacing(8)
        self.b_logo = button('Add a PNG', on_click=self._pick_logo)
        self.b_nologo = button('Take It Off', on_click=self._drop_logo)
        lrow.addWidget(self.b_logo, 1)
        lrow.addWidget(self.b_nologo, 1)
        side.addLayout(lrow)
        self.lx, self.ly, self.lw = self._slider(0, 100, 34), self._slider(0, 100, 36), self._slider(2, 60, 12)
        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)
        for i, (text, sl) in enumerate((('Across', self.lx), ('Down', self.ly), ('Size', self.lw))):
            lb = label(text, 'Sub')
            lb.setFixedWidth(72)
            form.addWidget(lb, i, 0)
            form.addWidget(sl, i, 1)
        side.addLayout(form)
        side.addWidget(section_title('Sharpness'))
        self.quality = QComboBox()
        self.quality.addItems(['Game size', 'Sharp (2x)', 'Sharpest (4x)'])
        self.quality.setCurrentIndex(1)
        self.quality.setToolTip('Builds the part larger than the game does, so logos and stripes stay crisp up close')
        side.addWidget(self.quality)
        side.addStretch(1)
        inner = QWidget()
        inner.setLayout(side)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(inner)
        inner.setObjectName('Clear')
        scroll.viewport().setAutoFillBackground(False)
        inner.setAutoFillBackground(False)
        brow = QHBoxLayout()
        brow.setSpacing(8)
        self.b_reset = button('Start Over', on_click=self._reset)
        self.b_save = button('Save to My Mod', True, self.save)
        brow.addWidget(self.b_reset, 1)
        brow.addWidget(self.b_save, 1)
        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(10)
        left.addWidget(scroll, 1)
        left.addLayout(brow)
        sw = QWidget()
        sw.setLayout(left)
        sw.setFixedWidth(320)
        lay.addWidget(sw)
        right = QVBoxLayout()
        right.setSpacing(8)
        top = QHBoxLayout()
        top.setSpacing(6)
        self.b_flat = QPushButton('Flat')
        self.b_worn = QPushButton('On the Player')
        for i, b in enumerate((self.b_flat, self.b_worn)):
            b.setObjectName('Chip')
            b.setCheckable(True)
            b.setAutoExclusive(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setChecked(i == 0)
            b.clicked.connect(self._view_changed)
            top.addWidget(b)
        top.addStretch(1)
        right.addLayout(top)
        self.views = QStackedWidget()
        self.view = ImageView()
        self.view.message = 'Pick a uniform'
        self.worn = Mannequin(main, self.drafts)
        self.views.addWidget(self.view)
        self.views.addWidget(self.worn)
        right.addWidget(self.views, 1)
        lay.addLayout(right, 1)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(90)
        self._timer.timeout.connect(self._render)
        self._enable(False)

    def _slider(self, lo, hi, value):
        s = QSlider(Qt.Horizontal)
        s.setRange(lo, hi)
        s.setValue(value)
        s.valueChanged.connect(self._later)
        return s

    def _enable(self, on):
        for w in (self.stripes, self.b_stripe, self.spacing, self.width, self.b_logo, self.b_nologo, self.lx, self.ly,
                  self.lw, self.b_reset, self.b_save, self.logo_pick, self.quality):
            w.setEnabled(on)

    # ---- loading
    def show_uniform(self, folder):
        if folder != self.folder:
            self.state, self.bases = {}, {}
            self.drafts.clear()
        self.folder = folder
        self._load_part()
        if self.views.currentIndex() == 1:
            self.worn.show_uniform(folder)

    def _base(self, i):
        """(pack rel, texture name, image) the part starts from: the mod's version when it has one."""
        if i in self.bases:
            return self.bases[i]
        from PIL import Image
        _, pack, name = UB.PARTS[i]
        rel = f'{self.folder}/{pack}'
        hit = None
        if rel in self.main.game.file_set():
            tex = self.main.tex(rel)
            entry = next((e for e in tex.entries if e['name'] == name), None) if tex else None
            if entry is not None and tex.simple(entry):
                mod = self.main.active_mod()
                png = self.main.lib.texture_path(mod, rel, name) if mod else None
                try:
                    img = Image.open(png).convert('RGBA') if png and os.path.exists(png) else tex.image(entry)
                    hit = (rel, name, img.convert('RGBA'))
                except Exception:
                    hit = None
        self.bases[i] = hit
        return hit

    def _load_part(self, *_):
        self.base_img = self.small = None
        while self.sw_grid.count():
            w = self.sw_grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.colors = []
        if not self.folder:
            return
        i = self.part.currentIndex()
        base = self._base(i)
        if base is None:
            self.view.set_image(None, 'This uniform has no ' + UB.PARTS[i][0].lower() + ' texture the builder can change.')
            self._enable(False)
            return
        self.rel, self.entry, self.base_img = base
        k = max(1, self.base_img.width // 1024)
        self.small = self.base_img.resize((self.base_img.width // k, self.base_img.height // k)) if k > 1 else self.base_img
        self.colors = [c for c, share in UB.palette(self.base_img, 8) if share > 0.002]
        st = self.state.setdefault(i, _blank())
        for n, c in enumerate(self.colors):
            b = _swatch(st['new'].get(n, c))
            b.setToolTip('Change this colour')
            b.clicked.connect(lambda _=False, n=n, btn=b: self._pick_color(n, btn))
            self.sw_grid.addWidget(b, n // 4, n % 4)
        self._loading = True
        self.stripes.setChecked(st['stripes'])
        _paint(self.b_stripe, st['stripe_color'])
        for key, sl in (('spacing', self.spacing), ('width', self.width)):
            sl.setValue(st[key])
        self._fill_logos(st)
        self._loading = False
        self._enable(True)
        self._render()

    # ---- edits
    def _st(self):
        return self.state.setdefault(self.part.currentIndex(), _blank())

    def _pick_color(self, n, btn):
        st = self._st()
        c = QColorDialog.getColor(QColor(*st['new'].get(n, self.colors[n])), self, 'New Colour')
        if c.isValid():
            st['new'][n] = (c.red(), c.green(), c.blue())
            _paint(btn, st['new'][n])
            self._later()

    def _pick_stripe(self):
        st = self._st()
        c = QColorDialog.getColor(QColor(*st['stripe_color']), self, 'Pinstripe Colour')
        if c.isValid():
            st['stripe_color'] = (c.red(), c.green(), c.blue())
            _paint(self.b_stripe, st['stripe_color'])
            self._later()

    def _fill_logos(self, st):
        """The logo list for this part, with the sliders on the chosen one."""
        was, self._loading = self._loading, True
        self.logo_pick.clear()
        for i, lg in enumerate(st['logos']):
            self.logo_pick.addItem(f"{i + 1}. {lg['name']}")
        if not st['logos']:
            self.logo_pick.addItem('No logos yet')
            st['cur'] = -1
        else:
            st['cur'] = max(0, min(st['cur'], len(st['logos']) - 1))
            self.logo_pick.setCurrentIndex(st['cur'])
            lg = st['logos'][st['cur']]
            for sl, key in ((self.lx, 'x'), (self.ly, 'y'), (self.lw, 'w')):
                sl.setValue(lg[key])
        self._loading = was

    def _logo_chosen(self, i):
        if self._loading:
            return
        st = self._st()
        if 0 <= i < len(st['logos']):
            st['cur'] = i
            self._fill_logos(st)

    def _pick_logo(self):
        from PIL import Image
        path, _ = QFileDialog.getOpenFileName(self, 'Logo', self.main.last_dir(), 'Images (*.png)')
        if path:
            self.main.remember_dir(path)
            try:
                img = Image.open(path).convert('RGBA')
            except Exception:
                self.main.toast('That image could not be opened.')
                return
            st = self._st()
            # each new logo lands a little further along, so two never hide each other
            st['logos'].append(dict(image=img, name=os.path.splitext(os.path.basename(path))[0][:18],
                                    x=min(90, 34 + 12 * len(st['logos'])), y=36, w=12))
            st['cur'] = len(st['logos']) - 1
            self._fill_logos(st)
            self._later()

    def _drop_logo(self):
        st = self._st()
        if 0 <= st['cur'] < len(st['logos']):
            st['logos'].pop(st['cur'])
            self._fill_logos(st)
            self._later()

    def _reset(self):
        self.state.pop(self.part.currentIndex(), None)
        if self.base_img is not None:
            self.drafts.pop((self.rel, self.entry), None)
        self._load_part()
        if self.views.currentIndex() == 1:
            self.worn.refresh()

    def _later(self, *_):
        if self._loading or self.base_img is None:
            return
        st = self._st()
        st.update(stripes=self.stripes.isChecked(), spacing=self.spacing.value(), width=self.width.value())
        if 0 <= st['cur'] < len(st['logos']):
            st['logos'][st['cur']].update(x=self.lx.value(), y=self.ly.value(), w=self.lw.value())
        self._timer.setInterval(450 if self.views.currentIndex() == 1 else 90)
        self._timer.start()

    def _view_changed(self):
        i = 1 if self.b_worn.isChecked() else 0
        self.views.setCurrentIndex(i)
        if i == 1 and self.folder:
            self._drafts()
            self.worn.show_uniform(self.folder)
        else:
            self._render()

    @staticmethod
    def _edited(st):
        return bool(st['new'] or st['stripes'] or st['logos'])

    def _made(self, i, small=None, quality=1):
        """The part with its edits (full size, or on the small preview copy)."""
        st = self.state.get(i) or _blank()
        rel, name, img = self._base(i)
        scale = 1.0
        if small is not None:
            scale, img = small.width / img.width, small
        colors = self.colors if i == self.part.currentIndex() else [c for c, s in UB.palette(self.bases[i][2], 8) if s > 0.002]
        swaps = [(colors[n], new) for n, new in st['new'].items() if n < len(colors)]
        stripes = None
        if st['stripes']:
            stripes = dict(color=st['stripe_color'], spacing=max(2, round(st['spacing'] * scale)),
                           width=max(1, round(st['width'] * scale)))
        logos = [dict(image=lg['image'], x=lg['x'] / 100, y=lg['y'] / 100, width=lg['w'] / 100) for lg in st['logos']]
        return UB.apply(img, swaps, stripes, logos=logos, quality=quality)

    def _drafts(self):
        """Write every edited part where the player preview picks it up."""
        for i, st in self.state.items():
            base = self.bases.get(i)
            if not base:
                continue
            key = (base[0], base[1])
            if self._edited(st):
                path = os.path.join(self._tmp, f'{i}.png')
                self._made(i).save(path)
                self.drafts[key] = path
            else:
                self.drafts.pop(key, None)

    def _render(self):
        if self.small is None:
            return
        if self.views.currentIndex() == 1:
            self._drafts()
            self.worn.refresh()
            return
        out = self._made(self.part.currentIndex(), self.small)
        self.view.set_image(pil_to_qimage(out.convert('RGB').convert('RGBA')))

    def save(self):
        todo = [i for i, st in self.state.items() if self.bases.get(i) and self._edited(st)]
        if not todo:
            self.main.toast('Nothing changed yet. Pick a colour, pinstripes or a logo first.')
            return
        mod = self.main.active_mod(ask=True)
        if not mod:
            return
        want = (1, 2, 4)[self.quality.currentIndex()]
        for i in todo:
            rel, name, img = self.bases[i]
            q = want
            while q > 1 and max(img.size) * q > 4096:      # sharp, but never past what the game's largest parts are
                q //= 2
            self.main.lib.add_texture(mod, rel, name, self._made(i, quality=q))
        names = ', '.join(UB.PARTS[i][0] for i in sorted(todo))
        self.state, self.bases = {}, {}
        self.drafts.clear()
        self.main.changed(f'{names} saved to {mod.name}.')
        self._load_part()
