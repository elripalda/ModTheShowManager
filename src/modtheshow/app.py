import os
import sys


def _install_log(get_window):
    """Unhandled errors go to manager.log and a short note on screen; the window stays up."""
    import datetime
    import traceback

    from . import __version__
    from .game import log_path

    class _Null:
        def write(self, *_):
            return 0

        def flush(self):
            pass

    for name in ('stdout', 'stderr'):          # a windowed exe has neither
        if getattr(sys, name) is None:
            setattr(sys, name, _Null())

    def hook(kind, value, tb):
        text = ''.join(traceback.format_exception(kind, value, tb))
        try:
            path = log_path()
            if os.path.exists(path) and os.path.getsize(path) > 512 * 1024:
                os.replace(path, path + '.old')
            with open(path, 'a', encoding='utf-8') as f:
                f.write(f'\n[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] build {__version__}\n{text}')
        except OSError:
            pass
        try:
            sys.stderr.write(text)
            win = get_window()
            if win is not None:
                win.toast('Something went wrong there. Details are in the log (Settings, Open Log).')
        except Exception:
            pass

    sys.excepthook = hook


def main():
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from .ui import theme
    from .ui.mainwindow import MainWindow

    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Ripalda.ModTheShowManager')
        except Exception:
            pass
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName('Mod the Show Manager')
    app.setOrganizationName('Ripalda')
    app.setWindowIcon(QIcon(os.path.join(theme.ASSETS, 'icon.ico')))
    theme.load_fonts()
    from . import game as gamemod
    st = gamemod.load_settings()
    theme.MOTION = st.get('motion', True)
    theme.apply(app, st.get('theme', 'Dark'), st.get('text_scale', 1.0))
    holder = []
    _install_log(lambda: holder[0] if holder else None)
    win = MainWindow()
    holder.append(win)
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
