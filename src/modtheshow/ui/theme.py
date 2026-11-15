import os

from PySide6.QtGui import QFontDatabase

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets')

BG = '#070e1c'
S1 = '#0d1729'
S2 = '#132039'
LINE = '#1f2d4a'
LINE_HI = '#3a4f7a'
TEXT = '#e9eef7'
SOFT = '#c3cde3'
MUTED = '#97a6c4'
RED = '#d8323f'
RED_HI = '#e64a56'
AMBER = '#f0b44c'
R = 8


def load_fonts():
    for f in ('Inter-Regular.otf', 'Inter-SemiBold.otf', 'Anton-Regular.ttf'):
        QFontDatabase.addApplicationFont(os.path.join(ASSETS, 'fonts', f))


QSS = f"""
* {{ font-family: 'Inter', 'Segoe UI', sans-serif; font-size: 13px; color: {TEXT}; }}
QMainWindow, QWidget#Root, QStackedWidget, QScrollArea, QWidget#Page {{ background: {BG}; }}
QWidget#Sidebar {{ background: {S1}; border-right: 1px solid {LINE}; }}
QLabel#Group {{ color: {MUTED}; font-size: 11px; font-weight: 600; letter-spacing: 1.4px; padding: 0 10px; }}
QLabel#H1 {{ font-family: 'Anton'; font-size: 34px; letter-spacing: 0.6px; }}
QLabel#H2 {{ font-family: 'Anton'; font-size: 18px; letter-spacing: 0.5px; }}
QLabel#StripTitle {{ font-family: 'Anton'; font-size: 15px; letter-spacing: 0.6px; padding: 0 14px; }}
QLabel#StripLabel {{ color: {MUTED}; font-size: 11px; font-weight: 600; letter-spacing: 1.4px; }}
QLabel#StripValue {{ font-family: 'Anton'; font-size: 20px; }}
QLabel#StripValueHi {{ font-family: 'Anton'; font-size: 20px; color: {AMBER}; }}
QLabel#Sub, QLabel[muted="true"] {{ color: {MUTED}; }}
QLabel#Soft {{ color: {SOFT}; }}
QLabel#Badge {{ background: {S2}; border: 1px solid {LINE}; border-radius: {R}px; padding: 1px 8px; color: {MUTED};
               font-size: 11px; }}
QLabel#BadgeMod {{ background: rgba(216,50,63,0.16); border: 1px solid rgba(216,50,63,0.6); border-radius: {R}px;
                  padding: 1px 8px; color: #ffc2c8; font-size: 11px; font-weight: 600; }}
QFrame#Strip {{ background: {BG}; border-bottom: 1px solid {LINE}; }}
QFrame#Scorebug {{ background: {S1}; border: 1px solid {LINE}; border-radius: {R}px; }}
QFrame#ScoreCell {{ border-left: 1px solid {LINE}; }}
QFrame#Panel {{ background: {S1}; border: 1px solid {LINE}; border-radius: {R}px; }}
QFrame#Banner {{ background: rgba(240,180,76,0.08); border: 1px solid rgba(240,180,76,0.5); border-radius: {R}px; }}
QFrame#Dashed {{ border: 1px dashed {LINE}; border-radius: {R}px; }}
QPushButton {{ background: {S2}; border: 1px solid {LINE}; border-radius: {R}px; padding: 0 16px; min-height: 40px;
              font-weight: 600; }}
QPushButton:hover {{ border-color: {LINE_HI}; background: #182847; }}
QPushButton:pressed {{ background: #101b31; }}
QPushButton:disabled {{ color: #56617d; border-color: #1a2540; background: #0f192d; }}
QPushButton#Primary {{ background: {RED}; border: 1px solid {RED}; color: white; }}
QPushButton#Primary:hover {{ background: {RED_HI}; border-color: {RED_HI}; }}
QPushButton#Primary:disabled {{ background: #4d1d27; border-color: #4d1d27; color: #c99aa3; }}
QPushButton#Nav {{ background: transparent; border: none; text-align: left; padding: 0 10px; min-height: 40px;
                  color: {MUTED}; font-size: 14px; font-weight: 500; }}
QPushButton#Nav:hover {{ background: {S2}; color: {TEXT}; }}
QPushButton#Nav:checked {{ background: {S2}; color: {TEXT}; font-weight: 600; }}
QPushButton#Nav:disabled {{ color: #6f7c9c; background: transparent; }}
QPushButton#Seg {{ min-height: 32px; padding: 0 12px; background: transparent; color: {MUTED}; font-size: 12px; }}
QPushButton#Seg:checked {{ background: {S2}; color: {TEXT}; border-color: {LINE_HI}; }}
QPushButton#Chip {{ min-height: 28px; padding: 0 10px; background: transparent; color: {SOFT}; font-size: 12px;
                   font-weight: 500; }}
QPushButton#Chip:checked {{ background: {S2}; color: {TEXT}; border-color: {LINE_HI}; font-weight: 600; }}
QPushButton#Icon {{ min-height: 34px; min-width: 34px; padding: 0 8px; background: transparent; border-color: transparent;
                   color: {MUTED}; }}
QPushButton#Icon:hover {{ background: {S2}; border-color: {LINE}; color: {TEXT}; }}
QLineEdit, QComboBox, QPlainTextEdit {{ background: {S1}; border: 1px solid {LINE}; border-radius: {R}px;
    padding: 0 10px; min-height: 38px; selection-background-color: {RED}; }}
QPlainTextEdit {{ padding: 8px; font-family: 'Consolas', monospace; font-size: 12px; }}
QLineEdit:focus, QComboBox:focus {{ border-color: {LINE_HI}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{ background: {S1}; border: 1px solid {LINE}; selection-background-color: {S2}; padding: 4px; }}
QTreeWidget, QListWidget {{ background: {S1}; border: 1px solid {LINE}; border-radius: {R}px; outline: none; padding: 6px; }}
QTreeWidget::item, QListWidget::item {{ padding: 5px 4px; border-radius: {R}px; color: {SOFT}; }}
QTreeWidget::item:hover, QListWidget::item:hover {{ background: {S2}; color: {TEXT}; }}
QTreeWidget::item:selected, QListWidget::item:selected {{ background: {S2}; color: {TEXT}; }}
QTreeWidget::branch {{ background: transparent; }}
QListWidget#Grid::item {{ border: 1px solid {LINE}; margin: 4px; padding: 6px; }}
QListWidget#Grid::item:selected {{ border-color: {LINE_HI}; background: {S2}; }}
QListWidget#Mods {{ padding: 0; }}
QListWidget#Mods::item {{ padding: 0; border-radius: 0; border-bottom: 1px solid {LINE}; }}
QListWidget#Mods::item:hover, QListWidget#Mods::item:selected {{ background: #101b31; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #2a3a60; border-radius: 4px; min-height: 30px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #2a3a60; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ width: 0; height: 0; background: none; }}
QProgressBar {{ background: {S2}; border: none; border-radius: 4px; max-height: 8px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: {RED}; border-radius: 4px; }}
QSplitter::handle {{ background: transparent; }}
QMenu {{ background: {S1}; border: 1px solid {LINE}; padding: 6px; border-radius: {R}px; }}
QMenu::item {{ padding: 8px 18px; border-radius: {R}px; }}
QMenu::item:selected {{ background: {S2}; }}
QMenu::separator {{ height: 1px; background: {LINE}; margin: 4px 8px; }}
QToolTip {{ background: {S2}; border: 1px solid {LINE}; color: {TEXT}; padding: 6px; }}
QDialog, QMessageBox {{ background: {BG}; }}
QCheckBox {{ spacing: 8px; }}
"""
