"""Looks at the project's GitHub releases for a newer version and fetches its installer."""
import json
import os
import re
import subprocess
import tempfile
import urllib.request

REPO = 'elripalda/ModTheShowManager'
PAGE = f'https://github.com/{REPO}/releases'


def _tuple(v):
    return tuple(int(x) for x in re.findall(r'\d+', v)[:4]) or (0,)


def newer(latest, current):
    return _tuple(latest) > _tuple(current)


def check(current, timeout=6):
    """{'version', 'url', 'asset', 'notes'} when a newer release is out, else None. Raises on network trouble."""
    req = urllib.request.Request(f'https://api.github.com/repos/{REPO}/releases/latest',
                                 headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'ModTheShowManager'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            rel = json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        if e.code == 404:        # no release published yet
            return None
        raise
    tag = rel.get('tag_name', '')
    if not tag or not newer(tag, current):
        return None
    assets = rel.get('assets', [])
    pick = next((a for a in assets if a['name'].lower().endswith('setup.exe')), None) or \
        next((a for a in assets if a['name'].lower().endswith('.exe')), None)
    return {'version': tag.lstrip('v'), 'url': rel.get('html_url', PAGE),
            'asset': pick['browser_download_url'] if pick else '', 'name': pick['name'] if pick else '',
            'notes': (rel.get('body') or '').strip()}


def download(url, name, progress=None):
    out = os.path.join(tempfile.mkdtemp(prefix='mts_update_'), name)
    req = urllib.request.Request(url, headers={'User-Agent': 'ModTheShowManager'})
    with urllib.request.urlopen(req, timeout=30) as r, open(out, 'wb') as f:
        total = int(r.headers.get('Content-Length') or 0)
        done = 0
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    return out


def run_installer(path):
    subprocess.Popen([path], creationflags=getattr(subprocess, 'DETACHED_PROCESS', 0))
