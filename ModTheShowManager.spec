# PyInstaller build for Mod the Show Manager: pyinstaller ModTheShowManager.spec
from PyInstaller.utils.hooks import collect_all, collect_data_files

datas = [('src/modtheshow/assets', 'modtheshow/assets')]
binaries, hidden = [], []
for pkg in ('etcpak', 'texture2ddecoder', 'lz4'):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hidden += h
datas += collect_data_files('archspec')
hidden += ['archspec.cpu']

a = Analysis(['src/run.py'], pathex=['src'], binaries=binaries, datas=datas, hiddenimports=hidden,
             excludes=['tkinter', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.Qt3DCore',
                       'PySide6.QtQuick', 'PySide6.QtQml', 'PySide6.QtMultimedia', 'PySide6.QtCharts',
                       'PySide6.QtDataVisualization', 'PySide6.QtPdf'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, name='ModTheShowManager', icon='src/modtheshow/assets/icon.ico',
          console=False, upx=False, version='version_info.txt')
