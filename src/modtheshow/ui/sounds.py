"""Sounds: every audio file in the game, with play, stop and export to WAV."""
import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QComboBox, QFileDialog, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
                               QSplitter, QVBoxLayout, QWidget)

from .. import audio
from .common import SectionTitle, button, header, label, panel
from .workers import Job, start

GROUPS = [('All Sounds', ''), ('Sound Banks (bat cracks, mitts, menus)', 'BNK'),
          ('Reactions', 'BANK_STREAMS/REACTION_STREAMS/'), ('Crowd', 'BANK_STREAMS/CROWD_STREAMS/'),
          ('Other Streams', 'BANK_STREAMS/*'), ('Commentary, PA & Music', 'SKX')]


def _secs(s):
    if not s:
        return '-'
    m, s = divmod(int(round(s)), 60)
    return f'{m}:{s:02d}'


class SoundsPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.setObjectName('Page')
        self.main = main
        self.loaded = False
        self.dec = audio.Decoder()
        self.player = audio.Player()
        self.rel = None
        self.subsong = 0
        self.all = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(18)
        outer.addWidget(header('Sounds', 'Every sound file in the game. Play one, export it as WAV, and find the '
                                         'bat cracks, mitt pops and crowd beds you want to change.'))
        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(16)
        left = panel()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(10, 10, 10, 10)
        ll.setSpacing(8)
        self.group = QComboBox()
        for name, _ in GROUPS:
            self.group.addItem(name)
        self.group.currentIndexChanged.connect(self._filter)
        ll.addWidget(self.group)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Find a sound')
        self.search.setClearButtonEnabled(True)
        self._deb = QTimer(self, singleShot=True, interval=200, timeout=self._filter)
        self.search.textChanged.connect(lambda _: self._deb.start())
        ll.addWidget(self.search)
        self.list = QListWidget()
        self.list.setStyleSheet('QListWidget { border: none; padding: 0; background: transparent; }')
        self.list.currentItemChanged.connect(self._picked)
        ll.addWidget(self.list, 1)
        self.count = label('', 'Sub')
        ll.addWidget(self.count)
        left.setMinimumWidth(300)
        left.setMaximumWidth(460)
        split.addWidget(left)

        right = panel()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(22, 20, 22, 20)
        rl.setSpacing(12)
        self.title = SectionTitle('Sound')
        rl.addWidget(self.title)
        self.path = label('', 'Sub', wrap=True)
        rl.addWidget(self.path)
        self.facts = label('Pick a sound on the left.', 'Soft', wrap=True)
        rl.addWidget(self.facts)
        self.inside_label = label('SOUNDS IN THIS BANK', 'Group')
        rl.addWidget(self.inside_label)
        self.inside = QListWidget()
        self.inside.setStyleSheet('QListWidget { border: none; padding: 0; background: transparent; }')
        self.inside.currentRowChanged.connect(self._sub_picked)
        rl.addWidget(self.inside, 1)
        self.spacer = QWidget()
        rl.addWidget(self.spacer, 1)
        self.status = label('', 'Sub', wrap=True)
        rl.addWidget(self.status)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.b_play = button('Play', True, self.play)
        self.b_stop = button('Stop', on_click=self.stop)
        self.b_wav = button('Export WAV', on_click=self.export_wav)
        self.b_raw = button('Export Original File', on_click=self.export_raw)
        self.b_rep = button('Replace With WAV', on_click=self.replace_wav)
        self.b_rep.setToolTip('Stream files (.XVAG) only. Your WAV is written in the game’s own codec, with the '
                              'original’s channels and sample rate.')
        for b in (self.b_play, self.b_stop, self.b_wav, self.b_raw):
            row.addWidget(b, 1)
        rl.addLayout(row)
        rl.addWidget(self.b_rep)
        split.addWidget(right)
        split.setStretchFactor(1, 1)
        split.setSizes([380, 900])
        outer.addWidget(split, 1)
        self._show_inside(False)
        self._enable(False)
        if not self.dec.ok:
            self.status.setText('The extra audio decoder (vgmstream) is missing, so sound banks and AT9 clips can '
                                'only be exported as original files. Streams and archives still play.')

    # ---------------------------------------------------------- list
    def showEvent(self, e):
        super().showEvent(e)
        if not self.loaded:
            self.loaded = True
            files = self.main.game.files
            self.all = sorted(f for f in files if f.startswith('NSW/AUDIO/') and
                              (f.endswith(audio.AUDIO_EXT) or f.endswith('.SKX')))
            self._filter()

    def _filter(self):
        _, key = GROUPS[self.group.currentIndex()]
        q = self.search.text().strip().upper()
        known = [k for _, k in GROUPS if k.endswith('/')]
        hits = []
        for f in self.all:
            sub = f[len('NSW/AUDIO/'):]
            if key == 'BNK' and not f.endswith('.BNK'):
                continue
            if key == 'SKX' and not f.endswith('.SKX'):
                continue
            if key.endswith('/') and not sub.startswith(key):
                continue
            if key == 'BANK_STREAMS/*' and (not sub.startswith('BANK_STREAMS/') or any(sub.startswith(k) for k in known)):
                continue
            if q and q not in sub:
                continue
            hits.append(f)
        self.list.clear()
        for f in hits[:4000]:
            sub = f[len('NSW/AUDIO/'):]
            name = sub.rsplit('/', 1)[-1]
            it = QListWidgetItem(name.rsplit('.', 1)[0].replace('_', ' ').title())
            it.setData(Qt.UserRole, f)
            it.setToolTip(sub)
            self.list.addItem(it)
        self.count.setText(f'{len(hits):,} sound file{"s" if len(hits) != 1 else ""}')

    def _show_inside(self, on):
        self.inside_label.setVisible(on)
        self.inside.setVisible(on)
        self.spacer.setVisible(not on)

    def _enable(self, on, playable=True, need_dec=True):
        """need_dec: the sound has to go through vgmstream (ATRAC9, sound banks). SADPCM is decoded here."""
        can = on and playable and (self.dec.ok or not need_dec)
        self.b_play.setEnabled(can and self.player.ok)
        self.b_stop.setEnabled(on and self.player.ok)
        self.b_wav.setEnabled(can)
        self.b_raw.setEnabled(on)
        self.b_rep.setEnabled(on and bool(self.rel) and self.rel.endswith('.XVAG'))

    # ---------------------------------------------------------- details
    def _picked(self, cur, _prev):
        if not cur:
            return
        self.stop()
        self.rel = rel = cur.data(Qt.UserRole)
        self.subsong = 0
        path = self.main.game.original(rel)
        self.title.set(cur.text(), [rel.rsplit('.', 1)[-1]])
        self.path.setText(f'romfs/{rel}')
        self.inside.clear()
        if rel.endswith('.SKX'):
            self._skx = entries = audio.skx_entries(path[:-4] + '.KEY')
            try:
                self._skx_has = {i for i, off in audio.skx_table(path) if off is not None}
            except (OSError, ValueError):
                self._skx_has = set()
            self._show_inside(bool(entries))
            more = ' (showing the first 5,000)' if len(entries) > 5000 else ''
            self.inside_label.setText(f'{len(entries):,} SAMPLES IN THIS ARCHIVE{more}')
            self.inside.blockSignals(True)
            for v, n, script in entries[:5000]:
                it = QListWidgetItem(n)
                it.setData(Qt.UserRole, v)
                if script:
                    it.setToolTip(script)
                self.inside.addItem(it)
            self.inside.blockSignals(False)
            self.facts.setText('Commentary, PA and music archive. Pick a sample below to hear it.'
                               if self._skx_has else 'This archive only holds timing entries, no sound.')
            self._enable(True, playable=False)
            first = next((r for r in range(self.inside.count())
                          if self.inside.item(r).data(Qt.UserRole) in self._skx_has), -1)
            if first >= 0:
                self.inside.setCurrentRow(first)
            return
        info = audio.header_info(path)
        playable = 'note' not in info
        facts = [info.get('format', '')]
        if info.get('codec'):
            facts.append(f"codec {info['codec']}")
        if info.get('channels'):
            facts.append(f"{info['channels']} channel{'s' if info['channels'] != 1 else ''}")
        if info.get('rate'):
            facts.append(f"{info['rate']:,} Hz")
        if info.get('seconds'):
            facts.append(_secs(info['seconds']))
        if info.get('bank'):
            facts.append(f"“{info['bank']}”")
        self.facts.setText('  ·  '.join(facts) + (f"\n{info['note']}" if info.get('note') else ''))
        self._enable(True, playable, need_dec=info.get('codec') != 'SADPCM')
        self._show_inside(rel.endswith('.BNK'))
        if rel.endswith('.BNK') and self.dec.ok:
            self.inside_label.setText('SOUNDS IN THIS BANK')
            self._load_bank(path)

    def _load_bank(self, path):
        self.status.setText('Reading the bank…')
        rel = self.rel

        def work(job):
            first = self.dec.info(path, 1)
            if 'error' in first:
                return first
            n = first.get('streams', 1)
            names = []
            for k in range(1, min(n, 400) + 1):
                i = first if k == 1 else self.dec.info(path, k)
                names.append(i.get('name') or f'Sound {k}')
            return {'streams': n, 'names': names}

        def done(res):
            if rel != self.rel:
                return
            if 'error' in res:
                self.status.setText(res['error'])
                self._enable(True, playable=False)
                return
            for k, n in enumerate(res['names'], 1):
                self.inside.addItem(f'{k:>3}   {n}')
            more = f' (showing the first {len(res["names"])})' if res['streams'] > len(res['names']) else ''
            self.inside_label.setText(f'{res["streams"]:,} SOUNDS IN THIS BANK{more}')
            self.status.setText('')
            if self.inside.count():
                self.inside.setCurrentRow(0)

        job = Job(work)
        job.sig.done.connect(done)
        job.sig.failed.connect(lambda tb: self.status.setText('The bank could not be read.'))
        self._job = job
        start(job)

    def _sub_picked(self, row):
        if self.rel and self.rel.endswith('.SKX'):
            it = self.inside.item(row) if row >= 0 else None
            if it is None:
                return
            idx = it.data(Qt.UserRole)
            self.subsong = idx
            ok = idx in getattr(self, '_skx_has', ())
            info = audio.skx_info(self.main.game.original(self.rel), idx) if ok else {}
            facts = []
            if info:
                facts = [info['codec'], f"{info['channels']} channel{'s' if info['channels'] != 1 else ''}",
                         f"{info['rate']:,} Hz", _secs(info['seconds'])]
            script = next((sc for v, _, sc in self._skx if v == idx), '')
            self.facts.setText(('  ·  '.join(facts) if facts else 'A pause between lines, not a sound.') +
                               (f'\n“{script}”' if script else ''))
            # codec 9 clips are ATRAC9 and go through vgmstream
            need_dec = bool(info) and info.get('codec') != 'SADPCM'
            self._enable(True, playable=ok, need_dec=need_dec)
            return
        self.subsong = row + 1 if row >= 0 else 0

    # ---------------------------------------------------------- actions
    def _decode(self, then, out=None):
        if not self.rel:
            return
        path, sub = self.main.game.original(self.rel), self.subsong
        self.status.setText('Decoding…')

        def work(job):
            return self.dec.to_wav(path, out, sub, stereo=out is None)

        def done(wav):
            self.status.setText('')
            then(wav)

        job = Job(work)
        job.sig.done.connect(done)
        job.sig.failed.connect(lambda tb: self.status.setText('This sound could not be decoded.'))
        self._djob = job
        start(job)

    def play(self):
        self._decode(self.player.play)

    def stop(self):
        self.player.stop()

    def export_wav(self):
        if not self.rel:
            return
        base = self.rel.rsplit('/', 1)[-1].rsplit('.', 1)[0] + (f'_{self.subsong}' if self.rel.endswith('.BNK') else '')
        if self.rel.endswith('.SKX') and self.inside.currentItem():
            name = self.inside.currentItem().text().replace('\\', '/').rsplit('/', 1)[-1]
            base = name.rsplit('.', 1)[0] or base
        out, _ = QFileDialog.getSaveFileName(self, 'Export WAV', os.path.join(self.main.last_dir(), base + '.wav'),
                                             'WAV audio (*.wav)')
        if out:
            self._decode(lambda wav: self.main.toast(f'Saved {os.path.basename(wav)}'), out)

    def export_raw(self):
        if not self.rel:
            return
        import shutil
        name = self.rel.rsplit('/', 1)[-1]
        out, _ = QFileDialog.getSaveFileName(self, 'Export Original File', os.path.join(self.main.last_dir(), name))
        if out:
            shutil.copyfile(self.main.game.original(self.rel), out)
            self.main.toast(f'Saved {os.path.basename(out)}')

    def replace_wav(self):
        if not self.rel or not self.rel.endswith('.XVAG'):
            return
        wav, _ = QFileDialog.getOpenFileName(self, 'Replacement Sound', self.main.last_dir(), 'WAV (*.wav)')
        if not wav:
            return
        self.main.remember_dir(wav)
        from .. import xvagwrite
        rel, orig = self.rel, self.main.game.original(self.rel)
        try:
            self.main.save_file(rel, lambda p: xvagwrite.build(orig, wav, p),
                                rel.rsplit('/', 1)[-1] + ' replaced in {mod}. Apply, then listen for it in a game.')
        except Exception as x:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, 'Could Not Replace', str(x))

    def refresh_overrides(self):
        pass
