"""Arcade rosters: push ratings for many players at once."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QGridLayout, QHBoxLayout, QLabel, QSlider, QVBoxLayout

from .common import button, label

GROUPS = [('Power', ('POWER_LEFT', 'POWER_RIGHT')),
          ('Contact', ('CONTACT_LEFT', 'CONTACT_RIGHT', 'PLATE_VISION')),
          ('Speed', ('SPEED', 'BASE_STEALING')),
          ('Fielding', ('FIELDING_ABILITY', 'REACTION_TIME')),
          ('Arm', ('ARM_STRENGTH', 'ARM_ACCURACY')),
          ('Pitching', ('HITS_PER_BF', 'HITS_PER_BF_RGHT', 'K_PER_BF_LEFT', 'K_PER_BF_RIGHT', 'BB_PER_BF', 'HR_PER_BF',
                        'PITCHING_CLUTCH', 'STAMINA'))]
PRESETS = [('Moonshot League', {'Power': 125}), ('Track Meet', {'Speed': 125}),
           ('Gold Gloves', {'Fielding': 125, 'Arm': 125}), ('Everyone Maxed', {g: 125 for g, _ in GROUPS})]


class LeagueTools(QDialog):
    def __init__(self, page):
        super().__init__(page)
        self.page = page
        self.setWindowTitle('Arcade Rosters')
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 22, 22, 22)
        lay.setSpacing(14)
        lay.addWidget(label('Set ratings for a whole league at once. 99 is the game’s normal top; up to 125 is what '
                            'boosted cards reach. Nothing changes until you press Save to My Mod on the page.',
                            'Sub', wrap=True))
        pre = QHBoxLayout()
        pre.setSpacing(8)
        for name, vals in PRESETS:
            pre.addWidget(button(name, on_click=lambda _=False, v=vals: self._preset(v)), 1)
        lay.addLayout(pre)
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        self.rows = {}
        for r, (name, _fields) in enumerate(GROUPS):
            chk = QCheckBox(name)
            sl = QSlider(Qt.Horizontal)
            sl.setRange(1, 125)
            sl.setValue(99)
            val = QLabel('99')
            val.setObjectName('RatingValue')
            val.setMinimumWidth(34)
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            sl.valueChanged.connect(lambda v, lab=val, c=chk: (lab.setText(str(v)), c.setChecked(True)))
            grid.addWidget(chk, r, 0)
            grid.addWidget(sl, r, 1)
            grid.addWidget(val, r, 2)
            self.rows[name] = (chk, sl)
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.scope = QComboBox()
        self.scope.addItem('Every player in the game', 'all')
        self.scope.addItem('MLB teams only', 'mlb')
        if page.team is not None:
            self.scope.addItem(f'Only the {page.team.name}', 'team')
        row.addWidget(self.scope, 2)
        row.addWidget(button('Cancel', on_click=self.reject), 1)
        row.addWidget(button('Change Ratings', True, self.apply), 1)
        lay.addLayout(row)

    def _preset(self, vals):
        for name, (chk, sl) in self.rows.items():
            if name in vals:
                sl.setValue(vals[name])
                chk.setChecked(True)
            else:
                chk.setChecked(False)

    def apply(self):
        db, scope = self.page.db, self.scope.currentData()
        ratings = {}
        for name, fields in GROUPS:
            chk, sl = self.rows[name]
            if chk.isChecked():
                for f in fields:
                    ratings[f] = sl.value()
        if not ratings:
            self.reject()
            return
        n = 0
        for p in db.players:
            if scope == 'mlb' and p.team >= 30:
                continue
            if scope == 'team' and p.team != self.page.team.index:
                continue
            mine = {f: v for f, v in ratings.items() if p.att is not None and f in p.att.fields
                    and not (p.pitcher and f.startswith(('POWER', 'CONTACT', 'PLATE')))
                    and not (not p.pitcher and f in GROUPS[5][1])}
            if mine:
                db.set_player(p, ratings=mine)
                for f, v in mine.items():
                    p.att.fields[f] = (p.att.fields[f][0], int(v).to_bytes(1, 'little'))
                n += 1
        self.count = n
        self.accept()
