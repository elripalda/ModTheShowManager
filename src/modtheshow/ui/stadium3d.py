"""A ballpark in 3D: the park's SCENE model with its own textures, to orbit or fly through."""
import os

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QFileDialog, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from .. import modellib
from ..texfind import TextureFinder
from . import viewer3d
from .common import button, label
from .workers import Job, start


class StadiumView(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.folder = None
        self._token = 0
        self.finder = TextureFinder(main.game, self._override)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.b_orbit = QPushButton('Orbit')
        self.b_fly = QPushButton('Fly Through')
        for b in (self.b_orbit, self.b_fly):
            b.setObjectName('Seg')
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            row.addWidget(b, 1)
        self.b_orbit.setChecked(True)
        self.b_orbit.clicked.connect(lambda: self._walk(False))
        self.b_fly.clicked.connect(lambda: self._walk(True))
        self.textures = QCheckBox('Textures')
        self.textures.setChecked(True)
        self.textures.toggled.connect(self._textured)
        row.addWidget(self.textures)
        self.roof = QCheckBox('Hide Roof')
        self.roof.setToolTip('Hide roof pieces to see inside covered parks')
        self.roof.toggled.connect(self._roof)
        row.addWidget(self.roof)
        self.b_save = button('Save Image', on_click=self.save_image)
        row.addWidget(self.b_save, 1)
        lay.addLayout(row)
        self.gl = viewer3d.available()
        if self.gl:
            self.view = viewer3d.ModelView3D(hq=False)
            self.view.show_floor = False
            self.view.message = 'Pick a ballpark'
        else:
            self.view = label('3D needs OpenGL 2.1, which this PC didn’t offer.', 'Sub', wrap=True)
        lay.addWidget(self.view, 1)
        self.note = label('Drag to look around · right-drag to pan · scroll to zoom. In Fly Through, W A S D move, Q and '
                          'E go down and up, hold Shift to go faster.', 'Sub', wrap=True)
        lay.addWidget(self.note)

    def _override(self, pack, name):
        hit = self.main.mod_png(pack, name)
        return hit[1] if hit else None

    def _walk(self, on):
        self.b_orbit.setChecked(not on)
        self.b_fly.setChecked(on)
        if self.gl:
            self.view.set_walk(on)
            if on:      # stand behind home plate (the park's origin), looking out at centre field
                from PySide6.QtGui import QVector3D
                c = self.view.center
                self.view.pan = QVector3D(-float(c[0]), 6.0 - float(c[1]), 14.0 - float(c[2]))
                self.view.yaw, self.view.pitch = 0.0, 0.04
                self.view.update()
            self.view.setFocus()

    def _textured(self, on):
        if self.gl:
            self.view.set_textured(on)

    def _roof(self, hide):
        if self.gl:
            for m in self.view.meshes:
                if getattr(m, 'is_roof', False):
                    m.visible = not hide
            self.view.update()

    def show_park(self, folder):
        """folder: NSW/STADIUMS/<CODE>."""
        if not self.gl or folder == self.folder:
            return
        self.folder = folder
        rel = folder + '/SCENE.MOD'
        files = self.main.game.file_set()
        if rel not in files:
            self.view.set_meshes([], 'This park has no 3D scene file.')
            return
        try:
            with open(self.main.current_file(rel), 'rb') as f:
                d = f.read()
            with open(self.main.current_file(modellib.gpu_path(rel)), 'rb') as f:
                g = f.read()
            model = modellib.Model(d, g)
        except Exception as x:
            self.view.set_meshes([], f'Could not open the park model: {x}')
            return
        meshes, names = [], []
        for i, dr in enumerate(model.draws):
            try:
                p, n, uv, t = model.mesh(i)
            except Exception:
                continue
            tex = model.color_texture(i) or ''
            low = f"{dr['name']} {tex}".lower()
            cut = any(k in low for k in ('alpha', 'net', 'fence', 'tree', 'leaf', 'trellis', 'rail', 'flag', 'crowd'))
            meshes.append(viewer3d.Mesh(np.asarray(p, np.float32), None if n is None else np.asarray(n, np.float32),
                                        None if uv is None else np.asarray(uv, np.float32), t, color='#8a93a6',
                                        cutout=cut))
            names.append(tex)
            meshes[-1].is_roof = 'roof' in low and 'sign' not in low
            meshes[-1].visible = not (self.roof.isChecked() and meshes[-1].is_roof)
        self._separate_ground(meshes)
        self.view.set_meshes(meshes, 'This park has no meshes the manager can read.')
        self._frame_on_park()
        self._walk(self.b_fly.isChecked())
        self._load_textures(rel, names)

    @staticmethod
    def _separate_ground(meshes):
        """The field is flat layers at the same height (grass, mow pattern, dirt, logos). Drawn as they are, they
        flicker through each other; lift each a hair, smallest on top, the way the game's own draw order does."""
        flat = []
        for m in meshes:
            if len(m.pos) and float(m.pos[:, 1].max() - m.pos[:, 1].min()) < 0.6 and abs(float(m.pos[:, 1].mean())) < 3:
                ext = m.pos.max(0) - m.pos.min(0)
                flat.append((float(ext[0] * ext[2]), m))
        flat.sort(key=lambda t: -t[0])
        for rank, (_, m) in enumerate(flat):
            m.pos = m.pos.copy()
            m.pos[:, 1] += 0.025 * min(rank, 60)

    def _frame_on_park(self):
        """Parks sit on a huge backdrop (the city around them); aim at the park itself."""
        boxes = [(m.pos.min(0), m.pos.max(0)) for m in self.view.meshes if len(m.pos)]
        if not boxes:
            return
        allmn = np.min([b[0] for b in boxes], 0)
        allmx = np.max([b[1] for b in boxes], 0)
        full = float(np.linalg.norm(allmx - allmn)) or 1.0
        # home plate sits at the origin; keep what's around the field and leave out the city backdrop
        near = full * 0.12
        keep = [b for b in boxes if np.hypot(*((b[0] + b[1]) / 2)[[0, 2]]) < near
                and np.linalg.norm(b[1] - b[0]) < full * 0.3] or boxes
        mn = np.min([b[0] for b in keep], 0)
        mx = np.max([b[1] for b in keep], 0)
        self.view.center = (mn + mx) / 2
        self.view.radius = float(np.linalg.norm(mx - mn) / 2) or 1.0
        self.view.reset()
        self.view.dist = 2.4

    def _load_textures(self, rel, names):
        if not self.textures.isChecked():
            return
        self._token += 1
        token = self._token
        self.note_text = self.note.text()

        def work(job):
            cache = {}
            out = []
            for n in names:
                if n and n not in cache:
                    img = self.finder.image(rel, n, 512)
                    cache[n] = viewer3d.pil_to_qimage(img) if img is not None else None
                out.append(cache.get(n))
            return out

        def done(images):
            if token != self._token:
                return
            self.view.makeCurrent()
            for m, q in zip(self.view.meshes, images):
                self.view.free_textures(m)
                if q is not None:
                    m.image = q
            self.view.doneCurrent()
            self.view.update()

        job = Job(work)
        job.sig.done.connect(done)
        job.sig.failed.connect(lambda tb: print(tb))
        self._job = job
        start(job)

    def refresh(self):
        f, self.folder = self.folder, None
        if f:
            self.show_park(f)

    def save_image(self):
        if not self.gl:
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Save Image', os.path.join(self.main.last_dir(), 'ballpark.png'),
                                              'PNG (*.png)')
        if path:
            self.main.remember_dir(path)
            self.view.snapshot().save(path)
