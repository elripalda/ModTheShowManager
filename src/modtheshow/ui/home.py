"""The start screen: where you are, what's waiting to be applied, and a door into every section."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from .common import button, label

SECTIONS = [
    ('Uniforms', 'Jerseys, pants, caps and helmets', 'See them on a player, swap fonts, set what each team wears and when.'),
    ('Bats', 'Bat skins, grips and shapes', 'Reskin bats or turn one into a wiffle or fungo bat.'),
    ('Stadiums', 'Signs, walls and grass', 'Every ad board, wall pad and mow pattern in each park.'),
    ('Scoreboards', 'The scorebug and overlays', 'Reskin the scorebug or move it anywhere on screen.'),
    ('Menus & Loading Screens', 'Front end art and fonts', 'Loading screens, menu art, headshots and fonts.'),
    ('3D Models', 'Look at and swap meshes', 'Open any model, export it, replace it with your own.'),
    ('Sounds', 'Crowd, bats and music', 'Listen to the game’s audio and export it.'),
    ('Teams & Rosters', 'Players, gear and ratings', 'Edit any player, his gear and ratings, and move him between clubs.'),
]
STEPS = [('1', 'Pick a mod', 'Choose where your changes go in Saving To, up top. New Mod makes one.'),
         ('2', 'Change things', 'Open a section below. Every change lands in your mod, never the game.'),
         ('3', 'Apply', 'Apply Changes puts the mods that are switched on into the game.'),
         ('4', 'Play', 'Launch the game. Restore Original Game in Mods undoes everything.')]


class Card(QFrame):
    clicked = Signal()

    def __init__(self, title, tag, text, enabled=True):
        super().__init__()
        self.setObjectName('Card')
        self.setMinimumHeight(150)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(6)
        t = label(title, 'CardTitle')
        lay.addWidget(t)
        g = label(tag, 'CardTag')
        lay.addWidget(g)
        lay.addSpacing(4)
        self.desc = label(text, 'Sub', wrap=True)
        lay.addWidget(self.desc, 1, Qt.AlignTop)
        self.title, self.text = title, text
        self.set_ready(enabled)

    def set_ready(self, ok):
        self.setEnabled(ok)
        self.setCursor(Qt.PointingHandCursor if ok else Qt.ArrowCursor)
        self.desc.setText(self.text if ok else 'Coming soon.')

    def mouseReleaseEvent(self, e):
        if self.isEnabled() and e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()


class Step(QFrame):
    def __init__(self, num, title, text):
        super().__init__()
        self.setObjectName('Step')
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(14)
        n = QLabel(num)
        n.setObjectName('StepNum')
        n.setAlignment(Qt.AlignCenter)
        n.setFixedSize(34, 34)
        lay.addWidget(n, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(3)
        col.addWidget(label(title, 'StepTitle'))
        col.addWidget(label(text, 'Sub', wrap=True))
        lay.addLayout(col, 1)


class HomePage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.setObjectName('Page')
        self.main = main
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        outer.addWidget(scroll)
        body = QWidget()
        body.setObjectName('Page')
        scroll.setWidget(body)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(28, 24, 28, 28)
        lay.setSpacing(22)

        top = QHBoxLayout()
        top.setSpacing(12)
        col = QVBoxLayout()
        col.setSpacing(6)
        col.addWidget(label('Welcome back', 'H1'))
        self.summary = label('', 'Sub', wrap=True)
        col.addWidget(self.summary)
        top.addLayout(col, 1)
        self.b_mods = button('Manage Mods', on_click=lambda: main.go('Mods'))
        self.b_new = button('New Mod', on_click=lambda: main.pages['Mods'].new_mod())
        for b in (self.b_new, self.b_mods):
            b.setMinimumWidth(170)
            top.addWidget(b, 0, Qt.AlignBottom)
        lay.addLayout(top)

        steps = QGridLayout()
        steps.setSpacing(12)
        for i, s in enumerate(STEPS):
            steps.addWidget(Step(*s), 0, i)
            steps.setColumnStretch(i, 1)
        lay.addLayout(steps)

        feat = QFrame()
        feat.setObjectName('Card')
        fl = QHBoxLayout(feat)
        fl.setContentsMargins(20, 16, 20, 16)
        fl.setSpacing(16)
        fc = QVBoxLayout()
        fc.setSpacing(4)
        fc.addWidget(label('Arcade mods', 'CardTitle'))
        fc.addWidget(label('Moonshot home runs, a juiced ball, thin air, or everyone rated 125. Switch them on, '
                           'rebuild once, and play.', 'Sub', wrap=True))
        fl.addLayout(fc, 1)
        b1 = button('Arcade Rosters', on_click=lambda: main.go('Teams & Rosters'))
        b2 = button('Code Plugins', True, lambda: main.go('Code Plugins'))
        for b in (b1, b2):
            b.setMinimumWidth(170)
            fl.addWidget(b)
        lay.addWidget(feat)
        lay.addWidget(label('What do you want to change?', 'H2'))
        grid = QGridLayout()
        grid.setSpacing(12)
        self.cards = []
        for i, (name, tag, text) in enumerate(SECTIONS):
            c = Card(name, tag, text, False)
            c.clicked.connect(lambda n=name: main.go(n))
            grid.addWidget(c, i // 4, i % 4)
            self.cards.append(c)
        for i in range(4):
            grid.setColumnStretch(i, 1)
        lay.addLayout(grid)
        lay.addStretch(1)

    def activate(self):
        self.refresh()

    def refresh(self):
        for c in self.cards:
            c.set_ready(c.title in self.main.pages)
        lib = self.main.lib
        if not lib:
            return
        mods = lib.list()
        on = sum(m.enabled for m in mods)
        pending = lib.pending_count()
        act = self.main.active_mod()
        parts = [f'{len(mods)} mod{"s" if len(mods) != 1 else ""}, {on} switched on.']
        parts.append(f'New changes go into {act.name}.' if act else 'Pick a mod in Saving To before you start.')
        if pending:
            parts.append(f'{pending} change{"s" if pending != 1 else ""} waiting to go into the game.')
        else:
            parts.append('The game is up to date.')
        self.summary.setText(' '.join(parts))
