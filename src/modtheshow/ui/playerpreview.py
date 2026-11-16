"""A player mannequin dressed in a team's uniform: jersey, pants, arms and cleats, using the uniform slot you're
editing and any PNGs your mod has put over it. Used by the Uniforms page as a live preview."""
import os

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

from .. import modellib, uniform_text
from ..texfind import TextureFinder
from . import viewer3d
from .common import button, label
from .workers import Job, start

PARTS = [
    ('NSW/CHARACTERS/MASTERFILES/CLOTH/JERSEY/G4JERSEY_BUFF.MOD', None),
    ('NSW/CHARACTERS/MASTERFILES/CLOTH/PANTS/G4PANTS_LONG.MOD', None),
    ('NSW/CHARACTERS/ACCESSORIES/SHOES/SHOES_NIKE_ALPHAHUARACHEELITE4.MOD', None),
    ('NSW/CHARACTERS/ACCESSORIES/SHOES/SHOES_ADIDAS_ADIZEROEDGEPLUS.MOD', None),
    ('NSW/CHARACTERS/MASTERFILES/CAPCURVED.MOD', None),
    ('NSW/CHARACTERS/MASTERFILES/CAP.MOD', None),
]
# models stored in a bone's own space (the cap rides the head bone): where they sit on the mannequin
OFFSETS = {'CAP': (0.0, 2.52, 0.03)}
HELMET = 'AND/CHARACTERS/MASTERFILES/HELMETNEW.MOD'     # the batting helmet rides the head bone like the cap
SHOE_GAP = 0.035                                        # each cleat sits this much further out, clear of the pants
SKIN = '#b8866a'


class PlayerPreview(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.folder = None
        self._token = 0
        self._models = {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.name = QLineEdit(main.settings.get('preview_name', 'RIPALDA'))
        self.name.setPlaceholderText('Name on the back')
        self.name.setMaximumWidth(170)
        self.number = QLineEdit(main.settings.get('preview_number', '26'))
        self.number.setPlaceholderText('No.')
        self.number.setMaxLength(2)
        self.number.setMaximumWidth(56)
        self._retext = QTimer(self, singleShot=True, interval=350, timeout=self._text_changed)
        self.name.textChanged.connect(lambda _: self._retext.start())
        self.number.textChanged.connect(lambda _: self._retext.start())
        bar.addWidget(self.name)
        bar.addWidget(self.number)
        self.font = QComboBox()
        self.font.setToolTip("Use another team's lettering and numbers on this uniform (saved into your mod)")
        self.font.addItem('Font: this team')
        self._font_rows = []
        self.font.activated.connect(self._font_picked)
        bar.addWidget(self.font)
        self.quality = QComboBox()
        self.quality.addItems(['Standard', 'High Quality'])
        self.quality.setCurrentIndex(1)
        self.quality.currentIndexChanged.connect(self._quality_changed)
        self.quality.hide()
        self.note = label('', 'Sub')
        bar.addWidget(self.note, 1)
        bar.addWidget(button('Front', on_click=lambda: self._turn(0.0)))
        bar.addWidget(button('Back', on_click=lambda: self._turn(3.14159)))
        self.b_helmet = button('Helmet', on_click=self.refresh)
        self.b_helmet.setCheckable(True)
        self.b_helmet.setToolTip('Wear the batting helmet instead of the cap')
        bar.addWidget(self.b_helmet)
        self.b_image = button('Save Image', on_click=self.save_image)
        bar.addWidget(self.b_image)
        lay.addLayout(bar)
        self.gl = viewer3d.available()
        self._lay = lay
        if self.gl:
            self.view = viewer3d.ModelView3D(True)
            self.view.message = 'Loading the player…'
        else:
            self.view = label('This PC could not start the 3D preview (OpenGL).', 'Sub')
        lay.addWidget(self.view, 1)
        self.finder = TextureFinder(main.game, self._override)

    def _override(self, pack, name):
        mod = self.main.active_mod()
        if mod:
            p = self.main.lib.texture_path(mod, pack, name)
            if os.path.exists(p):
                return p
        hit = self.main.mod_png(pack, name)
        return hit[1] if hit else None

    def _fill_fonts(self):
        if self._font_rows:
            return
        from .. import catalog
        for _, rows in catalog.teams(self.main.game):
            for code, name, league in rows:
                folder = f'NSW/UNIFORMS/{league}/{code}/HOME'
                if f'{folder}/UNIFORM.TEX' in self.main.game.files and all(f != folder for _, f in self._font_rows):
                    self._font_rows.append((name, folder))
        for name, _ in self._font_rows:
            self.font.addItem(f'Font: {name}')

    def _font_picked(self, i):
        if i <= 0 or not self.folder:
            return
        name, src = self._font_rows[i - 1]
        mod = self.main.active_mod(ask=True)
        if not mod:
            self.font.setCurrentIndex(0)
            return
        from ..texlib import Tex
        dst_pack = f'{self.folder}/UNIFORM.TEX'
        try:
            with Tex(self.main.game.original(f'{src}/UNIFORM.TEX'), readonly=True) as srct, \
                    Tex(self.main.game.original(dst_pack), readonly=True) as dstt:
                for tex in ('letters-color', 'numbers-color'):
                    a, b = srct.find(tex), dstt.find(tex)
                    if not a or not b:
                        continue
                    img = srct.image(a[0])
                    if img.size != (b[0]['w'], b[0]['h']):
                        from PIL import Image
                        img = img.resize((b[0]['w'], b[0]['h']), Image.LANCZOS)
                    self.main.lib.add_texture(mod, dst_pack, tex, img)
        except Exception as x:
            self.note.setText(f'Could not copy that font: {x}')
            return
        self.font.setCurrentIndex(0)
        self.main.changed(f"{name} lettering saved into {mod.name} for this uniform. Apply to see it in the game.")
        self.refresh()

    def _text_changed(self):
        self.main.settings['preview_name'] = self.name.text()
        self.main.settings['preview_number'] = self.number.text()
        self.refresh()

    def _quality_changed(self, i):
        self.main.settings['render_quality'] = 'high' if i == 1 else 'standard'
        if not self.gl:
            return
        old = self.view
        self.view = viewer3d.ModelView3D(i == 1)
        self._lay.replaceWidget(old, self.view)
        old.hide()
        old.deleteLater()
        self.refresh()

    def _turn(self, yaw):
        if self.gl:
            self.view.yaw, self.view.pitch = yaw, 0.12
            self.view.update()

    def show_uniform(self, folder):
        """folder: a uniform slot, e.g. NSW/UNIFORMS/NL/ARI/HOME."""
        self.folder = folder
        self._fill_fonts()
        if not self.gl:
            return
        self.finder.uniform_folder = folder
        self._token += 1
        token = self._token
        files = set(self.main.game.files)
        hq = self.gl and self.view.hq
        pname, pnum = self.name.text().strip(), self.number.text().strip()
        helmet = self.b_helmet.isChecked() and HELMET in files and modellib.gpu_path(HELMET) in files
        self.note.setText('Dressing the player…')

        def work(job):
            meshes = []
            size = 4096 if hq else 1024
            any_rel = PARTS[0][0]
            letters = self.finder.image(any_rel, 'letters-color', 4096)
            numbers = self.finder.image(any_rel, 'numbers-color', 4096)
            overlay = uniform_text.back_image(letters, numbers, pname, pnum) if (pname or pnum) else None
            shoes_done = cap_done = False
            for rel, keep in PARTS + ([(HELMET, None)] if helmet else []):
                if ('SHOES' in rel and shoes_done) or ('/CAP' in rel and (cap_done or helmet)):
                    continue
                if rel not in files or modellib.gpu_path(rel) not in files:
                    continue
                M = self._models.get(rel)
                if M is None:
                    try:
                        M = modellib.Model.open(self.main.game.original(rel),
                                                self.main.game.original(modellib.gpu_path(rel)))
                    except Exception:
                        continue
                    self._models[rel] = M
                shoes_done = shoes_done or 'SHOES' in rel
                cap_done = cap_done or '/CAP' in rel
                offset = OFFSETS['CAP'] if '/CAP' in rel or rel == HELMET else None
                seen = set()
                for i, d in enumerate(M.draws):
                    name = d['name'].split(' (')[0]
                    low = name.lower()
                    if keep is not None and name not in keep:
                        continue
                    if keep is None and ('lowlod' in low or low.endswith('_lp') or 'female' in low):
                        continue
                    if name in seen and keep is not None:
                        continue
                    seen.add(name)
                    try:
                        p, n, uv, t = M.mesh(i)
                    except Exception:
                        continue
                    maps = M.material_maps(i)
                    if rel == HELMET:
                        # the shell and one ear flap; the model also carries the other flap and both jaw guards
                        shell = maps['color'] == 'helmetnew-color'
                        flap = maps['color'] == 'helmet-color' and p[:, 0].max() <= 0 and p[:, 1].min() > -0.45
                        if not (shell or flap):
                            continue
                    if 'SHOES' in rel and len(p):
                        p = p + np.array([SHOE_GAP if p[:, 0].mean() > 0 else -SHOE_GAP, 0, 0], np.float32)
                    if offset is not None:
                        p = p + np.array(offset, np.float32)
                    tex = maps['color']
                    img = self.finder.image(rel, tex, size) if tex else None
                    skin = 'arm' in low
                    entry = dict(p=p, n=n, uv=uv, t=t, img=None if skin else img,
                                 color=SKIN if skin else '#d8d2c4', tan=M.tangents(i))
                    if hq and not skin:
                        entry['normal'] = self.finder.image(rel, maps['normal'], size) if maps['normal'] else None
                        entry['rough'] = self.finder.image(rel, maps['rough'], size) if maps['rough'] else None
                    if 'JERSEY' in rel and overlay is not None:
                        entry['uvn'] = uniform_text.back_uv(p, n)
                        entry['overlay'] = overlay
                    meshes.append(entry)
            return meshes

        def done(parts):
            if token != self._token:
                return
            q = lambda im: viewer3d.pil_to_qimage(im) if im is not None else None
            ov_cache = {}
            def ov(im):
                if im is None:
                    return None
                if id(im) not in ov_cache:
                    ov_cache[id(im)] = q(im)
                return ov_cache[id(im)]
            ms = [viewer3d.Mesh(np.asarray(m['p'], np.float32), np.asarray(m['n'], np.float32),
                                np.asarray(m['uv'], np.float32), m['t'], color=m['color'], image=q(m['img']),
                                tan=m.get('tan'), normal_map=q(m.get('normal')), rough_map=q(m.get('rough')),
                                uvn=None if m.get('uvn') is None else np.asarray(m['uvn'], np.float32),
                                overlay=ov(m.get('overlay')))
                  for m in parts]
            first = not self.view.meshes
            self.view.set_meshes(ms, 'No player parts found in this game folder.', up='y', keep_camera=not first)
            if first:
                self._turn(0.0)
                self.view.dist = 3.7
            team = folder.split('/')
            self.note.setText(f'{team[-2]} · {team[-1]}  ·  drag to turn, wheel to zoom')

        job = Job(work)
        job.sig.done.connect(done)
        job.sig.failed.connect(lambda tb: self.note.setText('The player could not be loaded'))
        self._job = job
        start(job)

    def refresh(self):
        if self.folder:
            self.show_uniform(self.folder)

    def save_image(self):
        from PySide6.QtWidgets import QFileDialog
        if not self.gl or not self.folder:
            return
        name = '_'.join(self.folder.split('/')[-2:]) + '.png'
        out, _ = QFileDialog.getSaveFileName(self, 'Save Image', os.path.join(self.main.last_dir(), name),
                                             'PNG image (*.png)')
        if out:
            self.view.snapshot().save(out)
            self.main.toast(f'Saved {os.path.basename(out)}')
