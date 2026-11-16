"""Colours, type and the stylesheet. Three looks (Dark, Light, OLED) share one template; apply() switches live."""
import os

from PySide6.QtGui import QFontDatabase

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets')

PALETTES = {
    'Dark': dict(BG='#161616', S1='#1f1f1f', S2='#2b2b2b', LINE='#303030', LINE_HI='#555555', TEXT='#f4f4f4',
                 SOFT='#d0d0d0', MUTED='#9b9b9b', RED='#e23744', RED_HI='#ef5560', AMBER='#f0a23c', ON_RED='#ffffff'),
    'Light': dict(BG='#f1f1ef', S1='#ffffff', S2='#ebebe8', LINE='#dcdcd8', LINE_HI='#a9a9a4', TEXT='#171717',
                  SOFT='#383838', MUTED='#6c6c6c', RED='#d42a38', RED_HI='#e04552', AMBER='#b96f00', ON_RED='#ffffff'),
    'OLED': dict(BG='#000000', S1='#0b0b0b', S2='#191919', LINE='#232323', LINE_HI='#474747', TEXT='#f4f4f4',
                 SOFT='#cfcfcf', MUTED='#939393', RED='#e23744', RED_HI='#ef5560', AMBER='#f0a23c', ON_RED='#ffffff'),
}
NAME = 'Dark'
SCALE = 1.0
MOTION = True
R = 14          # cards
RC = 10         # controls
# filled by build()
BG = S1 = S2 = LINE = LINE_HI = TEXT = SOFT = MUTED = RED = RED_HI = AMBER = ON_RED = ''
HOVER = PRESSED = DIM = CHECK_A = CHECK_B = ''
QSS = ''


def mix(a, b, t):
    """Colour a moved t of the way to b."""
    pa = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    pb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return '#' + ''.join(f'{round(x + (y - x) * t):02x}' for x, y in zip(pa, pb))


def is_light():
    return NAME == 'Light'


def load_fonts():
    for f in ('Poppins-Regular.ttf', 'Poppins-Medium.ttf', 'Poppins-Bold.ttf'):
        QFontDatabase.addApplicationFont(os.path.join(ASSETS, 'fonts', f))


def px(n):
    return f'{max(9, round(n * SCALE))}px'


def build(name='Dark', scale=1.0):
    global NAME, SCALE, QSS, HOVER, PRESSED, DIM, CHECK_A, CHECK_B
    NAME = name if name in PALETTES else 'Dark'
    SCALE = scale
    globals().update(PALETTES[NAME])
    HOVER = mix(S2, TEXT, 0.07)
    PRESSED = mix(S2, BG, 0.4)
    DIM = mix(MUTED, BG, 0.5)
    CHECK_A, CHECK_B = mix(S1, TEXT, 0.05), mix(S1, TEXT, 0.11)
    dis_bg = mix(S1, BG, 0.4)
    red_dim = mix(RED, BG, 0.62)
    QSS = f"""
* {{ font-family: 'Poppins', 'Segoe UI', sans-serif; font-size: {px(13)}; color: {TEXT}; }}
QMainWindow, QWidget#Root, QStackedWidget, QScrollArea, QWidget#Page {{ background: {BG}; }}
QWidget#Sidebar {{ background: {BG}; border-right: 1px solid {LINE}; }}
QLabel#Group {{ color: {MUTED}; font-size: {px(10)}; font-weight: 500; letter-spacing: 1.6px; padding: 0 12px; }}
QLabel#H1 {{ font-size: {px(30)}; font-weight: 500; }}
QLabel#H2 {{ font-size: {px(17)}; font-weight: 500; }}
QLabel#StripTitle {{ font-size: {px(13)}; font-weight: 500; padding: 0 16px; }}
QLabel#StripLabel {{ color: {MUTED}; font-size: {px(11)}; font-weight: 500; }}
QLabel#StripValue {{ font-size: {px(16)}; font-weight: 500; }}
QLabel#StripValueHi {{ font-size: {px(16)}; font-weight: 500; color: {AMBER}; }}
QLabel#Sub, QLabel[muted="true"] {{ color: {MUTED}; }}
QLabel#Soft {{ color: {SOFT}; }}
QLabel#Badge {{ background: {S2}; border: none; border-radius: 11px; padding: 2px 10px; color: {SOFT};
               font-size: {px(11)}; }}
QLabel#BadgeMod {{ background: {mix(S1, RED, 0.2)}; border: none; border-radius: 11px; padding: 2px 10px;
                  color: {mix(RED, TEXT, 0.45)}; font-size: {px(11)}; font-weight: 500; }}
QFrame#Strip {{ background: {BG}; border-bottom: 1px solid {LINE}; }}
QFrame#Scorebug {{ background: {S1}; border: 1px solid {LINE}; border-radius: 19px; }}
QFrame#ScoreCell {{ border-left: 1px solid {LINE}; }}
QFrame#Panel {{ background: {S1}; border: 1px solid {LINE}; border-radius: {R}px; }}
QFrame#Banner {{ background: {mix(S1, AMBER, 0.1)}; border: 1px solid {mix(S1, AMBER, 0.5)}; border-radius: {R}px; }}
QFrame#Dashed {{ border: 1px dashed {LINE}; border-radius: {R}px; }}
QPushButton {{ background: {S2}; border: 1px solid {S2}; border-radius: 20px; padding: 0 18px; min-height: 40px;
              font-weight: 500; }}
QPushButton:hover {{ background: {HOVER}; border-color: {HOVER}; }}
QPushButton:pressed {{ background: {PRESSED}; }}
QPushButton:disabled {{ color: {DIM}; border-color: {dis_bg}; background: {dis_bg}; }}
QPushButton#Primary {{ background: {RED}; border: 1px solid {RED}; color: {ON_RED}; }}
QPushButton#Primary:hover {{ background: {RED_HI}; border-color: {RED_HI}; }}
QPushButton#Primary:disabled {{ background: {red_dim}; border-color: {red_dim}; color: {mix(ON_RED, red_dim, 0.45)}; }}
QPushButton#Nav {{ background: transparent; border: none; border-radius: 19px; text-align: left; padding: 0 14px;
                  min-height: 38px; color: {MUTED}; font-size: {px(13)}; font-weight: 400; }}
QPushButton#Nav:hover {{ background: {S2}; color: {TEXT}; }}
QPushButton#Nav:checked {{ background: {TEXT}; color: {BG}; font-weight: 500; }}
QPushButton#Nav:disabled {{ color: {DIM}; background: transparent; }}
QPushButton#Seg {{ min-height: 32px; border-radius: 16px; padding: 0 14px; background: transparent;
                  border: 1px solid {LINE}; color: {MUTED}; font-size: {px(12)}; }}
QPushButton#Seg:checked {{ background: {TEXT}; color: {BG}; border-color: {TEXT}; }}
QPushButton#Chip {{ min-height: 30px; border-radius: 15px; padding: 0 14px; background: transparent;
                   border: 1px solid {LINE}; color: {SOFT}; font-size: {px(12)}; font-weight: 400; }}
QPushButton#Chip:hover {{ border-color: {LINE_HI}; }}
QPushButton#Chip:checked {{ background: {TEXT}; color: {BG}; border-color: {TEXT}; font-weight: 500; }}
QPushButton#Icon {{ min-height: 34px; min-width: 34px; padding: 0 8px; background: transparent;
                   border-color: transparent; color: {MUTED}; }}
QPushButton#Icon:hover {{ background: {S2}; border-color: {S2}; color: {TEXT}; }}
QLineEdit, QComboBox, QPlainTextEdit, QDoubleSpinBox, QSpinBox, QDateEdit {{ background: {S2}; border: 1px solid {S2};
    border-radius: {RC}px; padding: 0 12px; min-height: 38px; color: {TEXT}; selection-background-color: {RED};
    selection-color: {ON_RED}; }}
QPlainTextEdit {{ padding: 8px; font-family: 'Consolas', monospace; font-size: {px(12)}; background: {S1};
    border-color: {LINE}; }}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus, QDateEdit:focus {{ border-color: {LINE_HI}; }}
QLineEdit:disabled, QComboBox:disabled, QDoubleSpinBox:disabled, QSpinBox:disabled, QDateEdit:disabled {{ color: {DIM}; }}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button, QSpinBox::up-button, QSpinBox::down-button {{ width: 16px;
    border: none; background: transparent; }}
QComboBox::drop-down, QDateEdit::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{ background: {S1}; border: 1px solid {LINE}; selection-background-color: {S2};
    selection-color: {TEXT}; padding: 4px; outline: none; }}
QCalendarWidget QWidget {{ background: {S1}; alternate-background-color: {S2}; }}
QCalendarWidget QToolButton {{ background: transparent; color: {TEXT}; font-weight: 500; padding: 4px 8px; }}
QCalendarWidget QAbstractItemView {{ selection-background-color: {RED}; selection-color: {ON_RED}; }}
QTableWidget {{ background: {S1}; border: 1px solid {LINE}; border-radius: {R}px; outline: none;
    gridline-color: {LINE}; selection-background-color: {S2}; selection-color: {TEXT}; }}
QTableWidget::item {{ padding: 0 10px; border-bottom: 1px solid {LINE}; color: {SOFT}; }}
QTableWidget::item:selected {{ background: {S2}; color: {TEXT}; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{ background: {S1}; color: {MUTED}; border: none; border-bottom: 1px solid {LINE};
    padding: 8px 10px; font-size: {px(11)}; font-weight: 500; }}
QTableCornerButton::section {{ background: {S1}; border: none; }}
QTreeWidget, QListWidget {{ background: {S1}; border: 1px solid {LINE}; border-radius: {R}px; outline: none;
    padding: 6px; }}
QTreeWidget::item, QListWidget::item {{ padding: 5px 8px; border-radius: 8px; color: {SOFT}; }}
QTreeWidget::item:hover, QListWidget::item:hover {{ background: {S2}; color: {TEXT}; }}
QTreeWidget::item:selected, QListWidget::item:selected {{ background: {S2}; color: {TEXT}; }}
QTreeWidget::branch {{ background: transparent; }}
QListWidget#Grid::item {{ border: 1px solid {LINE}; border-radius: 10px; margin: 4px; padding: 6px; }}
QListWidget#Grid::item:selected {{ border-color: {TEXT}; background: {S2}; }}
QListWidget#Mods {{ padding: 0; }}
QListWidget#Mods::item {{ padding: 0; border-radius: 0; border-bottom: 1px solid {LINE}; }}
QListWidget#Mods::item:hover, QListWidget#Mods::item:selected {{ background: {mix(S1, S2, 0.5)}; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {mix(S2, TEXT, 0.15)}; border-radius: 3px; min-height: 30px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {mix(S2, TEXT, 0.15)}; border-radius: 3px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ width: 0; height: 0;
    background: none; }}
QProgressBar {{ background: {S2}; border: none; border-radius: 4px; max-height: 8px; text-align: center;
    color: transparent; }}
QProgressBar::chunk {{ background: {RED}; border-radius: 4px; }}
QSplitter::handle {{ background: transparent; }}
QMenu {{ background: {S1}; border: 1px solid {LINE}; padding: 6px; border-radius: {RC}px; }}
QMenu::item {{ padding: 8px 18px; border-radius: 8px; }}
QMenu::item:selected {{ background: {S2}; }}
QMenu::separator {{ height: 1px; background: {LINE}; margin: 4px 8px; }}
QToolTip {{ background: {S2}; border: 1px solid {LINE}; color: {TEXT}; padding: 6px; }}
QDialog, QMessageBox {{ background: {BG}; }}
QCheckBox {{ spacing: 8px; }}
QLabel#Toast {{ background: {TEXT}; border: none; border-radius: 12px; padding: 12px 22px; color: {BG};
    font-weight: 500; }}
QFrame#Card {{ background: {S1}; border: 1px solid {LINE}; border-radius: {R}px; }}
QFrame#Card:hover {{ border-color: {LINE_HI}; background: {mix(S1, S2, 0.5)}; }}
QFrame#Card:disabled {{ background: {mix(S1, BG, 0.5)}; }}
QLabel#CardTitle {{ font-size: {px(17)}; font-weight: 500; }}
QLabel#CardTag {{ color: {SOFT}; font-weight: 500; }}
QFrame#Tile {{ background: {S2}; border: none; border-radius: {RC}px; }}
QLabel#TileHead {{ color: {MUTED}; font-size: {px(11)}; font-weight: 700; letter-spacing: 1px; }}
QLabel#TileValue {{ font-size: {px(16)}; font-weight: 500; }}
QFrame#Step {{ background: {S1}; border: 1px solid {LINE}; border-radius: {R}px; }}
QLabel#StepNum {{ background: {TEXT}; color: {BG}; border-radius: 17px; font-size: {px(14)}; font-weight: 700; }}
QLabel#StepTitle {{ font-weight: 500; font-size: {px(14)}; }}
QSlider::groove:horizontal {{ height: 6px; background: {S2}; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {RED}; border-radius: 3px; }}
QSlider::handle:horizontal {{ width: 16px; height: 16px; margin: -5px 0; border-radius: 8px; background: {TEXT};
    border: 2px solid {S1}; }}
QLabel#RatingValue {{ font-size: {px(14)}; font-weight: 700; }}
QLabel#RatingValue[tier="diamond"] {{ color: {'#0a84a8' if NAME == 'Light' else '#7ee0ff'}; }}
QLabel#RatingValue[tier="gold"] {{ color: {AMBER}; }}
QLabel#RatingValue[tier="silver"] {{ color: {SOFT}; }}
QLabel#RatingValue[tier="bronze"] {{ color: {'#a5622f' if NAME == 'Light' else '#d99a6c'}; }}
QLabel#RatingValue[tier="common"] {{ color: {MUTED}; }}
"""
    return QSS


def apply(app, name=None, scale=None):
    build(name or NAME, scale or SCALE)
    app.setStyleSheet(QSS)


build()
