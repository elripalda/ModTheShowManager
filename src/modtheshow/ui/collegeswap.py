"""Swap a University: turn one of the game's colleges into a school of your own.

Everything tied to the team is in one window: its two names, its three logos and its two uniforms (in the jersey
builder). The ballpark stays as it is. A college's short name is the key the game finds its logos, uniforms and
recruiting numbers by, so that one is shown but not changed.
"""
import json
import os

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (QDialog, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QStackedWidget, QVBoxLayout, QWidget)

from .common import button, label, panel, section_title
from .jerseybuilder import JerseyBuilder
from .widgets import pil_to_qimage

UNIS = 'FRONTEND/UNIFORMS/MLBUNIS.JSON'
LOGOS = [('Wordmark', 1, 'Scoreboards and team lists'), ('Logo', 2, 'The main logo'), ('Small Logo', 4, 'Tiles and icons')]
FIRST, LAST = 135, 153                 # the colleges' places in the team table
PAGES = ('Names and Logos', 'Home Uniform', 'Road Uniform')


def pack(n):
    return f'NSW/UI/ART/TEXTURES/LOGO{n}.TEX'


def colleges(db):
    return [t for t in db.teams if FIRST <= t.index <= LAST]


def uniform_folders(game, main, index):
    """{'home': folder, 'away': folder} for a team, from the game's uniform list."""
    try:
        with open(main.current_file(UNIS), encoding='utf-8') as f:
            rows = json.load(f)['uniforms']
    except (OSError, ValueError, KeyError):
        return {}
    out = {}
    for u in rows:
        if u.get('gameid') == index and u.get('uniform_path'):
            out[u.get('assetname', '').lower()] = f"NSW/UNIFORMS/{u['uniform_path']}/{u.get('assetname', '').upper()}"
    return out


class LogoBox(QWidget):
    """One logo: what it is now, and a button to put another in its place."""

    def __init__(self, dialog, title, n, what):
        super().__init__()
        self.dialog, self.n = dialog, n
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(label(title))
        self.view = QLabel()
        self.view.setFixedHeight(150)
        self.view.setMinimumWidth(160)
        self.view.setAlignment(Qt.AlignCenter)
        self.view.setObjectName('Well')
        self.view.setStyleSheet('background: rgba(255,255,255,0.05); border-radius: 10px;')
        lay.addWidget(self.view)
        lay.addWidget(label(what, 'Sub'))
        lay.addWidget(button('Replace', on_click=self.pick))

    def show_image(self, img):
        if img is None:
            self.view.setText('Not found')
            return
        pm = QPixmap.fromImage(pil_to_qimage(img))
        self.view.setPixmap(pm.scaled(184, 134, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def pick(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Pick a Logo', '', 'Pictures (*.png *.jpg *.jpeg *.webp)')
        if path:
            self.dialog.set_logo(self.n, path)


class CollegeSwap(QDialog):
    def __init__(self, page):
        super().__init__(page)
        self.setWindowTitle('Swap a University')
        self.resize(1240, 780)
        self.page, self.main, self.db = page, page.main, page.db
        self.team = None
        self.new_logos = {}                  # (team index, n) -> PIL image picked for it
        self.new_names = {}                  # team index -> (school, nickname)
        row = QHBoxLayout(self)
        row.setContentsMargins(18, 18, 18, 18)
        row.setSpacing(16)
        left = panel()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(14, 14, 14, 14)
        ll.addWidget(section_title('Universities'))
        self.list = QListWidget()
        self.list.setIconSize(QSize(34, 34))
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.setTextElideMode(Qt.ElideRight)
        ll.addWidget(self.list, 1)
        left.setFixedWidth(270)
        row.addWidget(left)
        right = panel()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(18, 16, 18, 16)
        rl.setSpacing(12)
        tabs = QHBoxLayout()
        tabs.setSpacing(8)
        self.tabs = []
        for i, name in enumerate(PAGES):
            b = button(name, on_click=lambda _=False, i=i: self.show_page(i))
            b.setCheckable(True)
            tabs.addWidget(b, 1)
            self.tabs.append(b)
        rl.addLayout(tabs)
        self.stack = QStackedWidget()
        rl.addWidget(self.stack, 1)
        self.stack.addWidget(self._names_page())
        self.builders = []
        for _ in (1, 2):
            b = JerseyBuilder(self.main)
            self.builders.append(b)
            self.stack.addWidget(b)
        row.addWidget(right, 1)
        for t in colleges(self.db):
            it = QListWidgetItem(t.full)
            it.setData(Qt.UserRole, t.index)
            img = self._logo(t, 4)
            if img is not None:
                it.setIcon(QIcon(QPixmap.fromImage(pil_to_qimage(img))))
            self.list.addItem(it)
        self.list.currentItemChanged.connect(self._picked)
        self.list.setCurrentRow(0)
        self.show_page(0)

    # ---- the names and logos page
    def _names_page(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 6, 0, 0)
        lay.setSpacing(14)
        lay.addWidget(section_title('Names'))
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        self.school, self.nick, self.short = QLineEdit(), QLineEdit(), QLineEdit()
        self.short.setReadOnly(True)
        for i, (text, box) in enumerate((('School', self.school), ('Nickname', self.nick), ('Short name', self.short))):
            grid.addWidget(label(text, 'Sub'), 0, i)
            grid.addWidget(box, 1, i)
            grid.setColumnStretch(i, 1)
        self.school.textEdited.connect(self._named)
        self.nick.textEdited.connect(self._named)
        lay.addLayout(grid)
        lay.addWidget(label('The short name is how the game finds this team’s logos, uniforms and recruiting numbers, '
                            'so it stays. The long school name on the recruiting screens stays too for now.', 'Sub',
                            wrap=True))
        lay.addWidget(section_title('Logos', [button('One Picture for All Three', on_click=self.pick_all)]))
        logos = QHBoxLayout()
        logos.setSpacing(16)
        self.boxes = {}
        for title, n, what in LOGOS:
            box = LogoBox(self, title, n, what)
            self.boxes[n] = box
            logos.addWidget(box, 1)
        lay.addLayout(logos)
        lay.addWidget(label('A picture with a clear background works best. The ballpark keeps its own signs.', 'Sub',
                            wrap=True))
        lay.addStretch(1)
        foot = QHBoxLayout()
        self.note = label('', 'Soft')
        foot.addWidget(self.note, 1)
        foot.addWidget(button('Save to My Mod', True, self.save))
        lay.addLayout(foot)
        return w

    def _logo(self, team, n):
        """The team's logo as it stands: a picture picked here, the mod's, or the game's."""
        if (team.index, n) in self.new_logos:
            return self.new_logos[(team.index, n)]
        from PIL import Image
        rel, name = pack(n), f'logo{n}uni_{team.short.lower()}'
        try:
            mod = self.main.active_mod()
            png = self.main.lib.texture_path(mod, rel, name) if mod else None
            if png and os.path.exists(png):
                return Image.open(png).convert('RGBA')
            tex = self.main.tex(rel)
            hit = tex.find(name) if tex else []
            return tex.image(hit[0]).convert('RGBA') if hit else None
        except Exception:
            return None

    def _picked(self, cur, _prev=None):
        if cur is None:
            return
        self.team = next(t for t in self.db.teams if t.index == cur.data(Qt.UserRole))
        school, nick = self.new_names.get(self.team.index, (self.team.city, self.team.name))
        self.school.setText(school)
        self.nick.setText(nick)
        self.short.setText(self.team.short)
        for n, box in self.boxes.items():
            box.show_image(self._logo(self.team, n))
        self._load_uniform(self.stack.currentIndex())
        self._status()

    def _named(self, *_):
        if self.team is not None:
            self.new_names[self.team.index] = (self.school.text().strip(), self.nick.text().strip())
            self._status()

    def set_logo(self, n, path):
        from PIL import Image
        try:
            self.new_logos[(self.team.index, n)] = Image.open(path).convert('RGBA')
        except Exception as e:
            self.main.toast(f'Could not read that picture: {e}')
            return
        self.boxes[n].show_image(self._logo(self.team, n))
        self._status()

    def pick_all(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Pick a Logo', '', 'Pictures (*.png *.jpg *.jpeg *.webp)')
        if path:
            for _t, n, _w in LOGOS:
                self.set_logo(n, path)

    def _status(self):
        n = len(self.new_logos) + sum(1 for i, v in self.new_names.items()
                                      if v != next((t.city, t.name) for t in self.db.teams if t.index == i))
        self.note.setText(f'{n} change{"s" if n != 1 else ""} to save.' if n else 'Nothing changed yet.')

    # ---- uniforms
    def show_page(self, i):
        for k, b in enumerate(self.tabs):
            b.setChecked(k == i)
            b.setObjectName('Primary' if k == i else '')
            b.style().unpolish(b)
            b.style().polish(b)
        self.stack.setCurrentIndex(i)
        self._load_uniform(i)

    def _load_uniform(self, i):
        if i in (1, 2) and self.team is not None:
            folder = uniform_folders(self.main.game, self.main, self.team.index).get('home' if i == 1 else 'away')
            if folder:
                self.builders[i - 1].show_uniform(folder)

    # ---- saving
    def save(self):
        names = {i: v for i, v in self.new_names.items()
                 if all(v) and v != next((t.city, t.name) for t in self.db.teams if t.index == i)}
        if not names and not self.new_logos:
            self.main.toast('Nothing changed yet. Type a name or pick a logo first.')
            return
        mod = self.main.active_mod(ask=True)
        if not mod:
            return
        by = {t.index: t for t in self.db.teams}
        for (index, n), img in self.new_logos.items():
            rel, name = pack(n), f'logo{n}uni_{by[index].short.lower()}'
            tex = self.main.tex(rel)
            hit = tex.find(name) if tex else []
            if hit:
                self.main.lib.add_texture(mod, rel, name, _square(img, hit[0]['w'], hit[0]['h']))
        for index, (school, nick) in names.items():
            self.db.edits_t.setdefault(index, {}).update({'CITY_NAME': school, 'TEAM_NAME': nick})
            by[index].city, by[index].name = school, nick
        done = len(self.new_logos) + len(names)
        self.new_logos, self.new_names = {}, {}
        if names:
            self.page._dirty(True)
            self.page.save()
        self.main.changed(f'{done} change{"s" if done != 1 else ""} saved to {mod.name}. Apply to use them.')
        for i in range(self.list.count()):
            it = self.list.item(i)
            it.setText(by[it.data(Qt.UserRole)].full)
        self._status()


def _square(img, w, h):
    """The picture centred on a clear canvas the size of the texture, so nothing is stretched."""
    from PIL import Image
    scale = min(w / img.width, h / img.height)
    art = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
    out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    out.paste(art, ((w - art.width) // 2, (h - art.height) // 2), art)
    return out
