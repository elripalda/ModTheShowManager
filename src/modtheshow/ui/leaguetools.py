"""Arcade rosters: push ratings, body shapes and bats for many players at once."""
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
# body proportions every player carries (D_PLAYER_APP): 0 to 255, about 127 is the usual build
SHAPES = [('Head', ('HEAD_SCALE',)), ('Neck', ('NECK_SCALE',)), ('Shoulders and arms', ('SHOULDERS_SCALE', 'ARMS_SCALE')),
          ('Torso', ('SPINE_SCALE', 'COLLARBONE_SCALE')), ('Hips and legs', ('HIPS_SCALE', 'THIGHS_SCALE', 'GLUTES_SCALE'))]
SHAPE_PRESETS = [('Big Heads', {'Head': 255}), ('Tiny Heads', {'Head': 0}),
                 ('Bobbleheads', {'Head': 255, 'Neck': 0, 'Shoulders and arms': 40, 'Torso': 40, 'Hips and legs': 40}),
                 ('Giants', {'Neck': 255, 'Shoulders and arms': 255, 'Torso': 255, 'Hips and legs': 255})]
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
        grid.setColumnMinimumWidth(0, 170)
        lay.addLayout(grid)
        lay.addWidget(label('Body shapes work the same way. They use the sizes the game already has for created '
                            'players, so the biggest head is as big as the game draws one.', 'Sub', wrap=True))
        pre2 = QHBoxLayout()
        pre2.setSpacing(8)
        for name, vals in SHAPE_PRESETS:
            pre2.addWidget(button(name, on_click=lambda _=False, v=vals: self._preset(v, self.shapes)), 1)
        lay.addLayout(pre2)
        grid2 = QGridLayout()
        grid2.setHorizontalSpacing(12)
        grid2.setVerticalSpacing(8)
        self.shapes = {}
        for r, (name, _fields) in enumerate(SHAPES):
            chk = QCheckBox(name)
            sl = QSlider(Qt.Horizontal)
            sl.setRange(0, 255)
            sl.setValue(127)
            val = QLabel('127')
            val.setObjectName('RatingValue')
            val.setMinimumWidth(34)
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            sl.valueChanged.connect(lambda v, lab=val, c=chk: (lab.setText(str(v)), c.setChecked(True)))
            grid2.addWidget(chk, r, 0)
            grid2.addWidget(sl, r, 1)
            grid2.addWidget(val, r, 2)
            self.shapes[name] = (chk, sl)
        grid2.setColumnStretch(1, 1)
        grid2.setColumnMinimumWidth(0, 170)
        lay.addLayout(grid2)
        self.bats = QComboBox()
        self.bats.addItem('Leave bats as they are', None)
        metal = page.equipment.metal_bats() if getattr(page, 'equipment', None) else []
        if metal:
            self.bats.addItem('Aluminum bats for everyone (a mix)', [st for st, _ in metal])
            for st, lab in metal:
                self.bats.addItem(f'Aluminum: {lab}', [st])
            lay.addWidget(label('Aluminum bats are the ones Road to the Show uses in college games.', 'Sub', wrap=True))
            lay.addWidget(self.bats)
            self.ping = QCheckBox('Aluminum sound on contact (the game has one bat sound, so every bat pings)')
            self.ping.setChecked(True)
            self.ping.setEnabled(False)
            self.bats.currentIndexChanged.connect(lambda _i: self.ping.setEnabled(bool(self.bats.currentData())))
            lay.addWidget(self.ping)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.scope = QComboBox()
        self.scope.addItem('Every player in the game', 'all')
        self.scope.addItem('MLB teams only', 'mlb')
        if page.team is not None:
            self.scope.addItem(f'Only the {page.team.name}', 'team')
        row.addWidget(self.scope, 2)
        row.addWidget(button('Cancel', on_click=self.reject), 1)
        row.addWidget(button('Change Players', True, self.apply), 1)
        lay.addLayout(row)

    def _preset(self, vals, rows=None):
        for name, (chk, sl) in (self.rows if rows is None else rows).items():
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
        shape = {}
        for name, fields in SHAPES:
            chk, sl = self.shapes[name]
            if chk.isChecked():
                for f in fields:
                    shape[f] = sl.value()
        bats = self.bats.currentData()
        if not ratings and not shape and not bats:
            self.reject()
            return
        n = 0
        for p in db.players:
            if scope == 'mlb' and p.team >= 30:
                continue
            if scope == 'team' and p.team != self.page.team.index:
                continue
            fits = {f: v for f, v in shape.items() if p.app is not None and f in p.app.fields}
            if fits:
                db.set_player(p, shape=fits)
            mine = {f: v for f, v in ratings.items() if p.att is not None and f in p.att.fields
                    and not (p.pitcher and f.startswith(('POWER', 'CONTACT', 'PLATE')))
                    and not (not p.pitcher and f in GROUPS[5][1])}
            if mine:
                db.set_player(p, ratings=mine)
                for f, v in mine.items():
                    p.att.fields[f] = (p.att.fields[f][0], int(v).to_bytes(1, 'little'))
            swung = bool(bats) and p.acc is not None and 'BAT' in p.acc.fields
            if swung:
                db.set_player(p, gear={'BAT': bats[p.i % len(bats)]})
            if mine or fits or swung:
                n += 1
        self.count = n
        if bats and self.ping.isChecked():
            self.page.ping = True
        self.accept()
