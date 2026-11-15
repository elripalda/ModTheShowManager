import os
import sys


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
    app.setStyleSheet(theme.QSS)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
