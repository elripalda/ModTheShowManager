import traceback

from PySide6.QtCore import QObject, QRunnable, QThread, QThreadPool, Signal

from .widgets import pil_to_qimage


class _Sig(QObject):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int)
    log = Signal(str)


class Job(QRunnable):
    """Run fn(job) on the thread pool. fn may call job.log(text) and job.progress(done, total)."""

    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.sig = _Sig()

    def log(self, text):
        self.sig.log.emit(str(text))

    def progress(self, done, total):
        self.sig.progress.emit(done, total)

    def run(self):
        try:
            res = self.fn(self)
        except Exception:
            self.sig.failed.emit(traceback.format_exc())
        else:
            self.sig.done.emit(res)


def start(job):
    QThreadPool.globalInstance().start(job)
    return job


class ThumbLoader(QThread):
    """Decodes every texture in a pack one after another and emits thumbnails as they come."""
    thumb = Signal(int, object)          # entry index, QImage (or None)

    def __init__(self, tex, size=128, overrides=None):
        super().__init__()
        self.tex, self.size, self.overrides = tex, size, overrides or {}
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        from PIL import Image
        for i, e in enumerate(self.tex.entries):
            if self._stop:
                return
            try:
                png = self.overrides.get(e['name'])
                img = Image.open(png) if png else self.tex.image(e)
                img.thumbnail((self.size, self.size))
                self.thumb.emit(i, pil_to_qimage(img))
            except Exception:
                self.thumb.emit(i, None)
