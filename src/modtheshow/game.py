"""The game install: where it is, its file index, and whether it is running."""
import json
import os
import subprocess
import sys

CANDIDATES = [r'C:\Games\MLB The Show 26', r'D:\Games\MLB The Show 26', os.path.expanduser(r'~\Games\MLB The Show 26')]


def is_game_folder(path):
    return bool(path) and os.path.isfile(os.path.join(path, 'mlb.exe')) and \
        os.path.isdir(os.path.join(path, 'game', 'romfs'))


def detect():
    for c in CANDIDATES:
        if is_game_folder(c):
            return c
    return None


def settings_path():
    base = os.environ.get('APPDATA') or os.path.expanduser('~/.config')
    d = os.path.join(base, 'ModTheShow')
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, 'settings.json')


def load_settings():
    try:
        with open(settings_path(), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def write_json(path, data):
    """Writes through a temp file, so a crash or a full disk never leaves half a file behind."""
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def save_settings(s):
    write_json(settings_path(), s)


def log_path():
    return os.path.join(os.path.dirname(settings_path()), 'manager.log')


class Node:
    __slots__ = ('name', 'children', 'size', 'path')

    def __init__(self, name, path=''):
        self.name, self.path, self.children, self.size = name, path, None, 0

    @property
    def is_dir(self):
        return self.children is not None


class Game:
    def __init__(self, root):
        self.root = root
        self.romfs = os.path.join(root, 'game', 'romfs')
        self.tsv = os.path.join(root, 'game', 'romfs_list.tsv')
        self.mods = os.path.join(root, 'mods')
        self.backup = os.path.join(root, 'mod-backup')
        self.exe = os.path.join(root, 'mlb.exe')
        self.tree = None
        self.files = []          # every romfs path, upper case with forward slashes, no leading slash

    def path(self, rel):
        return os.path.join(self.romfs, *rel.strip('/\\').replace('\\', '/').split('/'))

    def original(self, rel):
        """The untouched file: its backup when a mod replaced it."""
        b = os.path.join(self.backup, *rel.strip('/').split('/'))
        return b if os.path.exists(b) else self.path(rel)

    def index(self):
        """Folder tree of the RomFS, from romfs_list.tsv (fast) or a disk walk."""
        root = Node('romfs')
        entries = []
        if os.path.exists(self.tsv):
            with open(self.tsv, encoding='utf-8', errors='replace') as f:
                for line in f:
                    p = line.rstrip('\r\n').split('\t')
                    if len(p) == 3:
                        entries.append((p[2].strip('/'), int(p[0]) if p[0].isdigit() else 0))
        else:
            for dp, _, fs in os.walk(self.romfs):
                for fn in fs:
                    full = os.path.join(dp, fn)
                    entries.append((os.path.relpath(full, self.romfs).replace('\\', '/'), os.path.getsize(full)))
        root.children = {}
        for rel, size in entries:
            parts = rel.split('/')
            node = root
            for i, part in enumerate(parts[:-1]):
                nxt = node.children.get(part)
                if nxt is None:
                    nxt = node.children[part] = Node(part, '/'.join(parts[:i + 1]))
                    nxt.children = {}
                node = nxt
            leaf = Node(parts[-1], rel)
            leaf.size = size
            node.children[parts[-1]] = leaf
        self.tree = root
        self.files = [e[0] for e in entries]
        self._set = None
        return root

    def file_set(self):
        if getattr(self, '_set', None) is None:
            self._set = set(self.files)
        return self._set

    def running(self):
        if os.name != 'nt':
            return False
        try:
            out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq mlb.exe', '/NH'], capture_output=True, text=True,
                                 timeout=15, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).stdout
        except Exception:
            return False
        return 'mlb.exe' in out.lower()

    def launch(self, env=None):
        full = dict(os.environ, **env) if env else None
        if sys.platform == 'win32':
            subprocess.Popen([self.exe], cwd=self.root, env=full,
                             creationflags=getattr(subprocess, 'DETACHED_PROCESS', 0))
        else:
            subprocess.Popen([self.exe], cwd=self.root, env=full)
