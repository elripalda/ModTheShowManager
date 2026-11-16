"""Discover: mods people have shared, listed in community/index.json of the project's repository.

A shared mod is a zip that holds only what its author made: PNG textures, roster and layout recipes, code patches
and a mod.json. Zips with anything else in them (changed game files above all) are refused.
"""
import json
import os
import tempfile
import urllib.request
import zipfile

REPO = 'elripalda/ModTheShowManager'
INDEX = f'https://raw.githubusercontent.com/{REPO}/main/community/index.json'
SUBMIT = f'https://github.com/{REPO}/issues/new?template=share-a-mod.yml'
GUIDE = f'https://github.com/{REPO}/blob/main/community/README.md'
ALLOWED = {'textures': ('.png',), 'rosters': ('.json',), 'layouts': ('.json',), 'code': ('.patch',)}
ROOT_FILES = ('mod.json', 'readme.md', 'readme.txt', 'preview.png', 'preview.jpg', 'license', 'license.txt')
MAX_BYTES = 300 * 1024 * 1024


def _get(url, timeout=10):
    req = urllib.request.Request(url, headers={'User-Agent': 'ModTheShowManager'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_index():
    """[{id, name, author, description, kinds, version, url}]. Raises on network trouble or a broken index."""
    doc = json.loads(_get(INDEX).decode('utf-8-sig'))
    out = []
    for e in doc.get('mods', []) if isinstance(doc, dict) else []:
        if isinstance(e, dict) and e.get('name') and str(e.get('url', '')).startswith('https://'):
            out.append({'id': str(e.get('id') or e['name']), 'name': str(e['name']), 'author': str(e.get('author', '')),
                        'description': str(e.get('description', '')), 'kinds': [str(k) for k in e.get('kinds', [])],
                        'version': str(e.get('version', '')), 'url': str(e['url'])})
    return out


def check_zip(path):
    """Problems with a shared mod zip ([] when it is fine)."""
    bad = []
    try:
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if not n.endswith('/')]
            if sum(i.file_size for i in z.infolist()) > MAX_BYTES:
                return ['The mod unpacks to more than 300 MB.']
    except zipfile.BadZipFile:
        return ['That download is not a zip file.']
    tops = {n.split('/')[0] for n in names}
    single = len(tops) == 1 and any('/' in n for n in names)
    for n in names:
        rel = n.split('/', 1)[1] if single else n
        parts = rel.split('/')
        if '..' in parts or rel.startswith(('/', '\\')):
            bad.append(f'{n}: not a path inside the mod')
        elif len(parts) == 1:
            if parts[0].lower() not in ROOT_FILES:
                bad.append(f'{rel}: not something a shared mod holds')
        elif parts[0] not in ALLOWED or not rel.lower().endswith(ALLOWED[parts[0]]):
            bad.append(f'{rel}: shared mods hold PNG textures, recipes and code patches only')
    return bad[:8]


def install(entry, lib, progress=None):
    """Downloads and adds a shared mod, switched off. Returns the Mod. Raises ValueError with the reason."""
    tmp = os.path.join(tempfile.mkdtemp(prefix='mts_share_'), 'mod.zip')
    req = urllib.request.Request(entry['url'], headers={'User-Agent': 'ModTheShowManager'})
    with urllib.request.urlopen(req, timeout=30) as r, open(tmp, 'wb') as f:
        total, done = int(r.headers.get('Content-Length') or 0), 0
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            done += len(chunk)
            if done > MAX_BYTES:
                raise ValueError('The download is larger than 300 MB.')
            f.write(chunk)
            if progress:
                progress(done, total)
    problems = check_zip(tmp)
    if problems:
        raise ValueError('This mod can’t be added:\n' + '\n'.join(problems))
    mod = lib.import_zip(tmp)
    mod.meta.setdefault('name', entry['name'])
    mod.meta.setdefault('author', entry['author'])
    mod.meta['shared_id'] = entry['id']
    mod.save_meta()
    lib.set_enabled(mod, False)
    return mod


def pack(mod, out):
    """Zips a mod for sharing. Returns the files left out because a shared mod may not hold them."""
    skipped = []
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for dp, _, fs in os.walk(mod.path):
            for f in sorted(fs):
                p = os.path.join(dp, f)
                rel = os.path.relpath(p, mod.path).replace('\\', '/')
                parts = rel.split('/')
                ok = (len(parts) == 1 and parts[0].lower() in ROOT_FILES) or \
                     (parts[0] in ALLOWED and rel.lower().endswith(ALLOWED[parts[0]]))
                if ok:
                    z.write(p, f'{mod.folder}/{rel}')
                else:
                    skipped.append(rel)
    return skipped
