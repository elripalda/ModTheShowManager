"""A player mannequin dressed in a team's uniform: jersey, pants, arms and cleats, using the uniform slot you're
editing and any PNGs your mod has put over it. Used by the Uniforms page as a live preview."""
import os

import numpy as np
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from .. import modellib
from ..texfind import TextureFinder
from . import viewer3d
from .common import button, label
from .workers import Job, start

PARTS = [
    ('NSW/CHARACTERS/MASTERFILES/CLOTH/JERSEY/G4JERSEY_BUFF.MOD', None),
    ('NSW/CHARACTERS/MASTERFILES/CLOTH/PANTS/G4PANTS_LONG.MOD', None),
    ('NSW/CHARACTERS/MASTERFILES/BODIES/STANDARDMALE/MALEBODY.MOD', ('Arm_L', 'Arm_R', 'socksHi')),
    ('NSW/CHARACTERS/ACCESSORIES/SHOES/SHOES_NIKE_ALPHAHUARACHEELITE4.MOD', None),
    ('NSW/CHARACTERS/ACCESSORIES/SHOES/SHOES_ADIDAS_ADIZEROEDGEPLUS.MOD', None),
]
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
        self.note = label('', 'Sub')
        bar.addWidget(self.note, 1)
        bar.addWidget(button('Front', on_click=lambda: self._turn(0.0)))
        bar.addWidget(button('Back', on_click=lambda: self._turn(3.14159)))
        bar.addWidget(button('Save Image', on_click=self.save_image))
        lay.addLayout(bar)
        self.gl = viewer3d.available()
        if self.gl:
            self.view = viewer3d.ModelView3D()
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

    def _turn(self, yaw):
        if self.gl:
            self.view.yaw, self.view.pitch = yaw, 0.12
            self.view.update()

    def show_uniform(self, folder):
        """folder: a uniform slot, e.g. NSW/UNIFORMS/NL/ARI/HOME."""
        self.folder = folder
        if not self.gl:
            return
        self.finder.uniform_folder = folder
        self._token += 1
        token = self._token
        files = set(self.main.game.files)
        self.note.setText('Dressing the player…')

        def work(job):
            meshes = []
            shoes_done = False
            for rel, keep in PARTS:
                if 'SHOES' in rel and shoes_done:
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
                    tex = M.color_texture(i)
                    img = self.finder.image(rel, tex, 1024) if tex else None
                    skin = 'arm' in low
                    meshes.append(dict(p=p, n=n, uv=uv, t=t, img=None if skin else img,
                                       color=SKIN if skin else '#d8d2c4'))
            return meshes

        def done(parts):
            if token != self._token:
                return
            ms = [viewer3d.Mesh(np.asarray(m['p'], np.float32), np.asarray(m['n'], np.float32),
                                np.asarray(m['uv'], np.float32), m['t'], color=m['color'],
                                image=viewer3d.pil_to_qimage(m['img']) if m['img'] is not None else None)
                  for m in parts]
            first = not self.view.meshes
            self.view.set_meshes(ms, 'No player parts found in this game folder.', up='y', keep_camera=not first)
            if first:
                self._turn(0.0)
                self.view.dist = 3.2
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
