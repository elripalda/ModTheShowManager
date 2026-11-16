"""The lists the game's custom team builder picks from: team names and cities (FRONTEND/CUSTOMTEAM*.TDT)."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QVBoxLayout)

from .common import button, label, section_title

NAMES = 'FRONTEND/CUSTOMTEAMNAMES.TDT'
PLACES = 'FRONTEND/CUSTOMTEAMLOCATIONS.TDT'


def read_tdt(path):
    rows = []
    with open(path, 'rb') as f:
        for line in f.read().decode('utf-8-sig', 'replace').splitlines():
            if '\t' in line:
                name, num = line.rsplit('\t', 1)
                if num.strip().isdigit():
                    rows.append((name, int(num)))
    return rows


def write_tdt(rows, path):
    with open(path, 'wb') as f:
        f.write(''.join(f'{n}\t{i}\r\n' for n, i in rows).encode('utf-8'))


class Column(QVBoxLayout):
    def __init__(self, title, rows, hint):
        super().__init__()
        self.setSpacing(8)
        self.addWidget(section_title(title))
        self.list = QListWidget()
        self.list.setMinimumSize(280, 380)
        for name, num in rows:
            self._add(name, num)
        self.addWidget(self.list, 1)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(hint)
        self.edit.setMaxLength(24)
        self.edit.returnPressed.connect(self.add)
        row.addWidget(self.edit, 1)
        row.addWidget(button('Add', on_click=self.add))
        row.addWidget(button('Remove', on_click=self.remove))
        self.addLayout(row)
        self.next = max([n for _, n in rows], default=1000) + 1

    def _add(self, name, num):
        it = QListWidgetItem(name)
        it.setData(Qt.UserRole, num)
        it.setFlags(it.flags() | Qt.ItemIsEditable)
        self.list.addItem(it)
        return it

    def add(self):
        name = self.edit.text().strip()
        if not name:
            return
        it = self._add(name, self.next)
        self.next += 1
        self.edit.clear()
        self.list.scrollToItem(it)
        self.list.setCurrentItem(it)

    def remove(self):
        r = self.list.currentRow()
        if r >= 0:
            self.list.takeItem(r)

    def rows(self):
        out = []
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.text().strip():
                out.append((it.text().strip().replace('\t', ' '), it.data(Qt.UserRole)))
        return out


class TeamBuilderDialog(QDialog):
    def __init__(self, main):
        super().__init__(main)
        self.main = main
        self.setWindowTitle('Team Builder Names')
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 22, 22, 22)
        lay.setSpacing(14)
        lay.addWidget(label('The names and cities you can pick when you make a custom team in the game. Double-click '
                            'one to rename it. New ones have no PA announcer audio, so the announcer skips them.',
                            'Sub', wrap=True))
        cols = QHBoxLayout()
        cols.setSpacing(18)
        self.names = Column('Team names', read_tdt(main.current_file(NAMES)), 'New team name')
        self.places = Column('Cities', read_tdt(main.current_file(PLACES)), 'New city')
        cols.addLayout(self.names, 1)
        cols.addLayout(self.places, 1)
        lay.addLayout(cols, 1)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addStretch(1)
        row.addWidget(button('Cancel', on_click=self.reject))
        row.addWidget(button('Save to My Mod', True, self.save))
        lay.addLayout(row)

    def save(self):
        try:
            a, b = self.names.rows(), self.places.rows()
            if not self.main.save_file(NAMES, lambda p: write_tdt(a, p), ''):
                return
            self.main.save_file(PLACES, lambda p: write_tdt(b, p),
                                'Team builder names saved into {mod}. Apply to use them.')
        except Exception as x:
            QMessageBox.warning(self, 'Could Not Save', str(x))
            return
        self.accept()
