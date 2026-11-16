"""Code mods: instruction patches baked into mlb.exe by the recomp's own builder, switched per launch.

The game's code is lifted to C when the recomp is installed, so it cannot be byte-patched afterwards. The recomp's
generator takes a patch table instead (recomp/patches.py in mlbts-native):

    set  <name> <ENV_SWITCH> <default 0/1>
    site <set> <module> <offset hex> <original word hex> <replacement word hex> [...]

A mod carries such a table in  <mod>/code/*.patch . The manager joins the tables of the mods that are switched on,
runs the generator and the build from the recomp folder (the one MLBTS-Setup.exe lives in), and swaps mlb.exe. Each
set stays switchable: the manager starts the game with the set's switch in the environment.
"""
import os
import re
import shutil
import subprocess

HEX = re.compile(r'^[0-9a-fA-F]{1,8}$')
# a live number the game reads while it runs:  #dial <name> <start> <lowest> <highest> <step> <what it is>
DIAL = re.compile(r'^#dial\s+([a-z][a-z0-9_]*)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+([\d.]+)\s+(.+?)\s*$')
DIAL_WORD = re.compile(r'^\$([a-z][a-z0-9_]*):s(\d{1,2})$')      # in a site: load that dial into float register sN
MAX_DIALS = 15


def dials(text):
    """[(name, start, lowest, highest, step, label)] for the #dial lines of a table, in order."""
    out, seen = [], set()
    for raw in text.splitlines():
        m = DIAL.match(raw.strip())
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            lo, hi = sorted((float(m.group(3)), float(m.group(4))))
            out.append((m.group(1), min(hi, max(lo, float(m.group(2)))), lo, hi, float(m.group(5)) or 0.1,
                        m.group(6)))
    return out


def dial_word(k, reg):
    """The instruction a dial is written as for the generator: fmov s<reg>, #-(1 + k/16). No real patch loads such
    a number, so the manager can find it in the translated code and put the live value in its place."""
    return 0x1E201000 | ((0xF0 | k) << 13) | reg


def dial_bits(k):
    """The bits of -(1 + k/16) as a float: what the generator writes for dial k's placeholder."""
    return 0xBF800000 + k * 0x80000


def lower(text):
    """A table as the recomp's generator reads it: every $dial:sN word becomes its placeholder instruction."""
    index = {name: i + 1 for i, (name, *_rest) in enumerate(dials(text))}
    out = []
    for raw in text.splitlines():
        f = raw.split('#', 1)[0].split()
        if f and f[0] == 'site':
            words = []
            for w in f:
                m = DIAL_WORD.match(w)
                words.append(f'{dial_word(index[m.group(1)], int(m.group(2))):08x}' if m and m.group(1) in index
                             else w)
            raw = ' '.join(words)
        out.append(raw)
    return '\n'.join(out) + '\n'


def fmov_word(value, reg):
    """fmov s<reg>, #value as an instruction word, for the number nearest to value that such an instruction can
    hold (n/16 x a power of two, n from 16 to 31, between 0.125 and 31), and that number."""
    best = None
    for sign in (0, 1):
        for exp in range(8):
            for frac in range(16):
                v = (16 + frac) / 16.0 * 2.0 ** (((exp ^ 4) & 7) - 3) * (-1 if sign else 1)
                if best is None or abs(v - value) < abs(best[1] - value):
                    best = ((sign << 7) | (exp << 4) | frac, v)
    return 0x1E201000 | (best[0] << 13) | reg, best[1]


def freeze(text, values=None):
    """The table with every dial written in as a fixed number (values: {dial name: number}, else where each dial
    starts) and the #dial lines gone: what is built when the live dials cannot be connected."""
    start = {name: v for name, v, *_rest in dials(text)}
    start.update({k: v for k, v in (values or {}).items() if k in start})
    out = []
    for raw in text.splitlines():
        if DIAL.match(raw.strip()):
            continue
        f = raw.split('#', 1)[0].split()
        if f and f[0] == 'site':
            words = []
            for w in f:
                m = DIAL_WORD.match(w)
                words.append(f'{fmov_word(start[m.group(1)], int(m.group(2)))[0]:08x}' if m and m.group(1) in start
                             else w)
            raw = ' '.join(words)
        out.append(raw)
    return '\n'.join(out) + '\n'


DESCRIPTIONS = {}     # set name -> one line shown in the manager (from '#: name: text' lines)
GROUPS = {}           # set name -> the heading it is listed under (from '#group Heading' lines above it)
TAGS = {}             # set name -> a short mark beside its name (from '#tag name: Experimental' lines)
BUILT_IN = 'Built in'
OTHER = 'More'


class PatchError(ValueError):
    pass


def find_recomp(hint=None):
    cands = [hint] if hint else []
    home = os.path.expanduser('~')
    cands += [os.path.join(home, 'Desktop', 'RL', 'mlbts-native'), os.path.join(home, 'Desktop', 'mlbts-native'),
              os.path.join(home, 'Downloads', 'mlbts-native'), r'C:\mlbts-native']
    for c in cands:
        if c and is_recomp(c):
            return c
    return None


def is_recomp(path):
    return bool(path) and all(os.path.exists(os.path.join(path, *p)) for p in
                              (('recomp', 'gen.py'), ('tools', 'build.py'), ('python', 'python.exe')))


def parse(text, where=''):
    """[(name, env, default)], [site line], problems."""
    sets, lines, bad = [], [], []
    names = set()
    known = {d[0] for d in dials(text)}
    if len(known) > MAX_DIALS:
        bad.append(f'{where}: more than {MAX_DIALS} dials')
    lines += [raw.strip() for raw in text.splitlines() if DIAL.match(raw.strip())]
    DESCRIPTIONS.update({m.group(1): m.group(2).strip() for m in
                         re.finditer(r'^#:\s*(\w+)\s*[:=-]\s*(.+)$', text, re.M)})
    TAGS.update({m.group(1): m.group(2).strip() for m in re.finditer(r'^#tag\s+(\w+)\s*[:=-]\s*(.+)$', text, re.M)})
    group = None
    for raw in text.splitlines():
        m = re.match(r'#group\s+(.+?)\s*$', raw.strip())
        if m:
            group = m.group(1)
        else:
            f = raw.split('#', 1)[0].split()
            if len(f) == 4 and f[0] == 'set' and group:
                GROUPS[f[1]] = group
    for no, raw in enumerate(text.splitlines(), 1):
        f = raw.split('#', 1)[0].split()
        if not f:
            continue
        at = f'{where}:{no}'
        if f[0] == 'set' and len(f) == 4 and f[3] in ('0', '1') and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', f[1]) \
                and re.fullmatch(r'[A-Z_][A-Z0-9_]*', f[2]):
            if f[1] in names:
                bad.append(f'{at}: set {f[1]} is defined twice')
            names.add(f[1])
            sets.append((f[1], f[2], int(f[3])))
            lines.append(' '.join(f))
        elif f[0] == 'site' and len(f) >= 6 and f[2] in ('main', 'sdk') and HEX.match(f[3]) and HEX.match(f[4]) \
                and all(HEX.match(w) or re.fullmatch(r'@page:x\d{1,2}', w) or DIAL_WORD.match(w) for w in f[5:]):
            if f[1] not in names:
                bad.append(f'{at}: site uses set {f[1]} before it is defined')
            for w in f[5:]:
                m = DIAL_WORD.match(w)
                if m and (m.group(1) not in known or int(m.group(2)) > 31):
                    bad.append(f'{at}: {w} names a dial this file does not define with #dial')
            lines.append(' '.join(f))
        else:
            bad.append(f'{at}: cannot read "{raw.strip()}"')
    return sets, lines, bad


def mod_patches(mod):
    """[(path, text)] of a mod's code/*.patch files."""
    folder = os.path.join(mod.path, 'code')
    out = []
    if os.path.isdir(folder):
        for f in sorted(os.listdir(folder)):
            if f.lower().endswith('.patch'):
                p = os.path.join(folder, f)
                with open(p, encoding='utf-8', errors='replace') as fh:
                    out.append((p, fh.read()))
    return out


def collect(mods):
    """Joined table of every code mod there is: sets [(name, env, default, where it is from)], text, problems.
    The manager's own come first and need no mod; then every mod that carries code, on or off in Mods (a code mod
    has one switch, in Code Mods). A set that two files both carry is taken from the first and left out of the
    second."""
    sources = [(BUILT_IN, 'built-in.patch', ARCADE)]
    for m in sorted(mods, key=lambda m: m.name.lower()):
        if m.name != ARCADE_NAME:              # the samples mod of older versions: the built-in ones replace it
            sources += [(m.name, os.path.basename(path), text) for path, text in mod_patches(m)]
    sets, lines, bad, seen = [], [], [], {}
    for source, file, text in sources:
        kept = [{k: d[k] for k in seen if k in d} for d in (DESCRIPTIONS, GROUPS, TAGS)]
        s, l, b = parse(text, f'{source}/{file}')
        for d, was in zip((DESCRIPTIONS, GROUPS, TAGS), kept):     # what a set says about itself comes from the file
            for k in seen:                                         # the set was taken from
                d.pop(k, None)
            d.update(was)
        bad += b
        twice = {name for name, _, _ in s if name in seen}
        have_dials = {d[0] for d in dials('\n'.join(lines))}
        if twice or have_dials:
            l = [x for x in drop_sets('\n'.join(l), twice).splitlines()
                 if not (DIAL.match(x) and DIAL.match(x).group(1) in have_dials)]
        for name, env, default in s:
            if name not in seen:
                seen[name] = source
                sets.append((name, env, default, source))
        lines.append(f'# {source}: {file}')
        lines += l
    return sets, '\n'.join(lines) + '\n', bad


def grouped(sets):
    """[(heading, [set tuple])] in the order the headings first appear; sets without one come last under OTHER."""
    order, by = [], {}
    for t in sets:
        g = GROUPS.get(t[0], OTHER)
        if g not in by:
            by[g] = []
            if g != OTHER:
                order.append(g)
        by[g].append(t)
    return [(g, by[g]) for g in order + ([OTHER] if OTHER in by else [])]


def nice(name):
    """A set name as a title: auto_pci -> Auto PCI."""
    t = name.replace('_', ' ').title()
    for a in ('Pci', 'Cpu', 'Hr', 'Fps'):
        t = re.sub(rf'\b{a}\b', a.upper(), t)
    return t


def drop_sets(text, names):
    """The table without the named sets (their set and site lines)."""
    if not names:
        return text
    keep = []
    for raw in text.splitlines():
        f = raw.split('#', 1)[0].split()
        if len(f) >= 2 and f[0] in ('set', 'site') and f[1] in names:
            continue
        keep.append(raw)
    return '\n'.join(keep) + '\n'


def fitting(game_root, text):
    """(table text without the sets that do not match the installed game, {set: [why]})."""
    from . import exefile
    code = exefile.load(game_root)
    if code is None:
        return text, {}
    bad = exefile.misfits(code, text)
    return drop_sets(text, set(bad)), bad


BUILD_REV = 4      # goes up when the way the manager builds changes, so an older build is offered a rebuild
SWITCH_FILE = 'mts-code.cfg'
SWITCH_LOG = 'mts-code.log'


def signature(text):
    import hashlib
    body = '\n'.join(l for l in text.splitlines() if not l.startswith('#') or DIAL.match(l))
    return hashlib.sha1(f'{BUILD_REV}\n{body}'.encode()).hexdigest()[:16] if body.strip() else ''


def _c_text(text, limit=150):
    """Words as a C string the game's plain-text drawing can show: ASCII only, quotes and backslashes made safe."""
    swaps = {'\u2019': "'", '\u2018': "'", '\u201c': '"', '\u201d': '"', '\u00d7': 'x', '\u2013': '-', '\u2014': '-',
             '\u2026': '...'}
    t = ''.join(swaps.get(ch, ch) for ch in str(text))
    t = ''.join(ch for ch in t if 32 <= ord(ch) < 127)[:limit]
    return t.replace('\\', '\\\\').replace('"', '\\"')


def set_dials(patch_text):
    """{set name: [dial names its sites turn, in order]} for the sets that have any."""
    out = {}
    for raw in patch_text.splitlines():
        f = raw.split('#', 1)[0].split()
        if len(f) > 5 and f[0] == 'site':
            for w in f[5:]:
                m = DIAL_WORD.match(w)
                if m and m.group(1) not in out.setdefault(f[1], []):
                    out[f[1]].append(m.group(1))
    return {k: v for k, v in out.items() if v}


def menu_rows(patch_text):
    """The lines of the in-game menu: [(set index, dial number or 0, 1 for the set's own line)]. A set's first dial
    shares its line; any further dial gets a line of its own under it. A dial two sets share shows under the first."""
    number = {d[0]: k for k, d in enumerate(dials(patch_text), 1)}
    turns = set_dials(patch_text)
    rows, seen = [], set()
    for i, (name, _env, _default) in enumerate(table_sets(patch_text)):
        mine = [number[d] for d in turns.get(name, []) if d in number and number[d] not in seen]
        seen.update(mine)
        rows.append((i, mine[0] if mine else 0, 1))
        rows += [(i, k, 0) for k in mine[1:]]
    return rows


MENU_FULL, MENU_PLAIN, MENU_NONE = 2, 1, 0


def switch_source(sets, menu=MENU_FULL, dial_list=(), rows=None):
    """C for the built-in sets: their switches, their dials, their counters and the in-game menu. sets: [(name, env,
    default)] in table order; dial_list: dials(table); rows: menu_rows(table).

    The recomp's shipped runtime library was built without any patch sets, so its own switch array is never filled
    in and a set baked into the game could not be turned on. The manager points the lifted code at this array
    instead. It is filled before the game starts: each set's default, then mts-code.cfg in the game folder
    (name=0/1 for a switch, dial.name=1.500 for a dial, written by the manager), then the set's environment
    variable. What was decided goes to logs/mts-code.log, and so does how many times each set's code has run, so a
    mod that is on but never reached can be told from one that ran and changed nothing you could see.

    menu: MENU_FULL adds the in-game menu (F4) joined to the game's own input, MENU_PLAIN the same panel on its own,
    MENU_NONE neither (see codemenu.py)."""
    from . import codemenu
    if menu is True:
        menu = MENU_FULL
    menu = int(menu or 0)
    if rows is None:
        rows = [(i, 0, 1) for i in range(len(sets))]
    setrows = ''.join(f'    {{"{n}", "{e}", {int(d)}, "{_c_text(nice(n), 60)}", '
                      f'"{_c_text(DESCRIPTIONS.get(n, ""), 190)}"}},\n' for n, e, d in sets)
    dialrows = ''.join(f',\n    {{"{n}", "{_c_text(label, 60)}", {float(start)!r}f, {float(lo)!r}f, {float(hi)!r}f, '
                       f'{float(step)!r}f}}' for n, start, lo, hi, step, label in dial_list)
    menurows = ''.join(f'    {{{s_}, {d_}, {o_}}},\n' for s_, d_, o_ in rows)
    text = codemenu.HEAD + (codemenu.MENU if menu else '') + codemenu.TAIL
    for key, value in (('{START}', codemenu.START if menu else ''), ('{NSETS}', str(len(sets))),
                       ('{NDIALS}', str(len(dial_list))), ('{NROWS}', str(len(rows))),
                       ('{SEAMS}', '1' if menu == MENU_FULL else '0'), ('{SETROWS}', setrows),
                       ('{DIALROWS}', dialrows), ('{MENUROWS}', menurows), ('{SWITCH_FILE}', SWITCH_FILE),
                       ('{SWITCH_LOG}', SWITCH_LOG)):
        text = text.replace(key, value)
    return text


def table_sets(patch_text):
    """[(name, env, default)] in the order the generator numbers them."""
    out = []
    for raw in patch_text.splitlines():
        f = raw.split('#', 1)[0].split()
        if len(f) == 4 and f[0] == 'set':
            out.append((f[1], f[2], int(f[3])))
    return out


def wire_chunk(text):
    """One translated chunk made ready for the manager's runtime: the switch array is the manager's, every patched
    spot counts each time it runs, and a dial's placeholder number becomes the live one. Safe to run twice."""
    text = text.replace('rt_patch_on', 'mts_patch_on')
    if 'mts_patch_on' not in text:
        return text
    if 'extern uint32_t mts_dial[]' not in text:
        text = text.replace('extern uint8_t mts_patch_on[];',
                            'extern uint8_t mts_patch_on[];\nextern uint32_t mts_dial[];\n'
                            'extern volatile uint32_t mts_ran[];', 1)

    def live(m):
        k = (int(m.group(1), 16) - 0xBF800000) // 0x80000
        return f'= (uint64_t)mts_dial[{k}];' if 1 <= k <= MAX_DIALS else m.group(0)

    out = []
    for line in text.split('\n'):
        if 'if (mts_patch_on[' in line:
            line = re.sub(r'if \(mts_patch_on\[(\d+)\]\) \{(?! mts_ran)', r'if (mts_patch_on[\1]) { mts_ran[\1]++;', line)
            line = re.sub(r'= 0x(bf[89a-f][08]0000)ull;', live, line, flags=re.I)
        out.append(line)
    return '\n'.join(out)


def wire_switches(gen, patch_text, menu=MENU_FULL):
    """After the generator ran: point every patched chunk at the manager's switches, counters and dials, and add
    their source. Returns how many chunks hold patched code."""
    if menu is True:
        menu = MENU_FULL
    sets = table_sets(patch_text)
    main = os.path.join(gen, 'main')
    src = os.path.join(main, 'mts_switches.c')
    if not sets:
        if os.path.exists(src):
            os.remove(src)
        return 0
    changed = wired = 0
    for mod in ('main', 'sdk'):
        folder = os.path.join(gen, mod)
        if not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            if not name.endswith('.c') or name == 'mts_switches.c':
                continue
            path = os.path.join(folder, name)
            with open(path, 'rb') as f:
                data = f.read()
            if b'rt_patch_on' in data or b'mts_patch_on' in data:
                new = wire_chunk(data.decode('utf-8', 'surrogateescape')).encode('utf-8', 'surrogateescape')
                if new != data:
                    with open(path, 'wb') as f:
                        f.write(new)
                changed += 1
                wired += new.count(b'(uint64_t)mts_dial[')
    text = switch_source(sets, menu, dials(patch_text), menu_rows(patch_text))
    old = None
    if os.path.exists(src):
        with open(src, encoding='utf-8') as f:
            old = f.read()
    if old != text:
        with open(src, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
    wire_switches.dials_wired = wired
    return changed


def dial_uses(patch_text):
    """How many times the table's sites read a dial."""
    return sum(1 for raw in patch_text.splitlines() for w in raw.split('#', 1)[0].split()[5:]
               if raw.split('#', 1)[0].split()[:1] == ['site'] and DIAL_WORD.match(w))


def write_switches(game_root, states, dial_values=None):
    """states: {set name: bool}; dial_values: {dial name: number}. The built game reads this file when it starts,
    however it is launched."""
    path = os.path.join(game_root, SWITCH_FILE)
    body = ('# Code mod switches, written by Mod the Show Manager. name=1 is on. A dial is dial.name=number.\n' +
            ''.join(f'{n}={1 if on else 0}\n' for n, on in states.items()) +
            ''.join(f'dial.{n}={float(v):.3f}\n' for n, v in (dial_values or {}).items()))
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(body)


def _switch_lines(game_root):
    try:
        with open(os.path.join(game_root, SWITCH_FILE), encoding='utf-8', errors='replace') as f:
            return f.read().splitlines()
    except OSError:
        return []


def read_switches(game_root):
    """{set name: bool} from mts-code.cfg (the game rewrites it when a mod is switched while it runs), or {}."""
    out = {}
    for line in _switch_lines(game_root):
        m = re.match(r'(\w+)=([01])\s*$', line)
        if m:
            out[m.group(1)] = m.group(2) == '1'
    return out


def read_dials(game_root):
    """{dial name: number} from mts-code.cfg, as the manager or the in-game menu last left them."""
    out = {}
    for line in _switch_lines(game_root):
        m = re.match(r'dial\.(\w+)=(-?\d+(?:\.\d+)?)\s*$', line)
        if m:
            out[m.group(1)] = float(m.group(2))
    return out


def last_activity(game_root):
    """{set name: how many times its code ran} in the game's last session, or None for a build that kept no count
    (or a game that has not been started since it was built)."""
    out = None
    try:
        with open(os.path.join(game_root, 'logs', SWITCH_LOG), encoding='utf-8', errors='replace') as f:
            for line in f:
                m = re.match(r'ran (\w+)=(\d+)\s*$', line)
                if m:
                    out = out or {}
                    out[m.group(1)] = int(m.group(2))
    except OSError:
        pass
    return out


def last_launch(game_root):
    """{set name: (on, where the answer came from)} from the game's last start, or None if it never wrote one."""
    try:
        with open(os.path.join(game_root, 'logs', SWITCH_LOG), encoding='utf-8', errors='replace') as f:
            lines = f.read().splitlines()
    except OSError:
        return None
    out = {}
    for line in lines[1:]:
        m = re.match(r'(\w+)=([01]) \((.*)\)$', line)
        if m:
            out[m.group(1)] = (m.group(2) == '1', m.group(3))
    return out


def build_args(recomp, gen, out, exefs):
    """The recomp's build tool and what it is handed. Newer recomps (0.1.4 on) know more than one game version and
    tell them apart by the game's own code, so they are told where that code is; older ones do not take the
    option."""
    tool = os.path.join(recomp, 'tools', 'build.py')
    args = [tool, '--toolchain', os.path.join(recomp, 'llvm'), '--deps', os.path.join(recomp, 'runtime', 'deps'),
            '--ninja', os.path.join(recomp, 'bin', 'ninja.exe'),
            '--runtime-lib', os.path.join(recomp, 'runtime', 'libmlbrt.a'), '--portable', '--gen', gen, '--out', out]
    try:
        with open(tool, encoding='utf-8', errors='replace') as f:
            if "'--exefs'" in f.read():
                args += ['--exefs', exefs]
    except OSError:
        pass
    return args


def game_version(recomp, exefs):
    """The game version of the code in an ExeFS folder, as the recomp names it ('1.0.15'). None when the recomp
    keeps no list of versions, or the code is not one it knows."""
    import glob
    import hashlib
    import json
    try:
        with open(os.path.join(exefs, 'main'), 'rb') as f:
            digest = hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None
    for path in sorted(glob.glob(os.path.join(recomp, 'tools', 'data', 'expected-*.json'))):
        try:
            with open(path, encoding='utf-8') as f:
                known = json.load(f)
            if known['exefs_sha256']['main'] == digest:
                return str(known.get('display_version') or os.path.basename(path)[len('expected-'):-len('.json')])
        except (OSError, ValueError, KeyError, TypeError):
            pass
    return None


def rebuild(recomp, game_root, patch_text, log=print, dial_values=None):
    """Run the recomp's generator and build with the patch table, then swap mlb.exe (the old one is kept once as
    mlb.original.exe). Returns {'exe': path, 'live': whether the dials can be turned while the game runs, 'menu':
    which in-game menu was built}. Raises PatchError with the tool's last lines when a step fails."""
    if not is_recomp(recomp):
        raise PatchError('That is not the recomp folder (the one with MLBTS-Setup.exe).')
    py = os.path.join(recomp, 'python', 'python.exe')
    work = os.path.join(recomp, 'temp', 'modtheshow')
    gen, out = os.path.join(work, 'gen'), os.path.join(work, 'build')
    os.makedirs(work, exist_ok=True)
    table = os.path.join(work, 'patches.txt')
    exefs = os.path.join(game_root, 'game', 'exefs')
    patched = bool(signature(patch_text))
    quiet = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

    def run(title, cmd):
        """(failed, the tool's last lines)"""
        log(title + '...')
        p = subprocess.Popen(cmd, cwd=recomp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             errors='replace', creationflags=quiet)
        tail = []
        for line in p.stdout:
            line = line.rstrip()
            if line:
                tail = (tail + [line])[-12:]
                if re.match(r'emitted \d+/\d+ chunks|\[\d+/\d+\]', line):
                    log(f'{title}: {line.split("]")[0].lstrip("[") if line.startswith("[") else line}')
        return p.wait() != 0, tail

    def translate(text):
        with open(table, 'w', encoding='utf-8') as f:
            f.write(lower(text))              # dials go to the generator as instructions it can read
        failed, tail = run('Translating the game code',
                           [py, '-I', '-X', 'utf8', os.path.join(recomp, 'recomp', 'gen.py'), '--exefs', exefs,
                            '--out', gen, '--modules', 'main,sdk'] + (['--patches', table] if patched else []))
        if failed:
            raise PatchError('Translating the game code failed:\n' + '\n'.join(tail))
        n = wire_switches(gen, text)
        if patched and not n:
            raise PatchError('The translated code has no patched spots in it, so the code mods would do nothing. '
                             'Nothing was changed.')
        return n

    version = game_version(recomp, exefs)
    if version:
        log(f'Game code: version {version}')
    live = True
    n = translate(patch_text)
    want, got = dial_uses(patch_text), getattr(wire_switches, 'dials_wired', 0)
    if got < want:
        # the translated code does not show the dials the way the manager looks for them: build them in as fixed
        # numbers instead, so the mods still work (a dial then changes with the next rebuild, not in the game)
        log('The dials could not be connected live, so they are built in at their current numbers.')
        live = False
        patch_text = freeze(patch_text, dial_values)
        n = translate(patch_text)
    if patched:
        log(f'Switches wired into {n} piece(s) of the game code' + (f', {got} dial(s) connected' if live and want else ''))
    cmd = [py, '-I', '-X', 'utf8'] + build_args(recomp, gen, out, exefs)
    failed, tail = run('Compiling', cmd)
    level = MENU_FULL
    while failed and level and patched and any('mts_switches' in t for t in tail):
        # the menu is the only Windows-specific code the manager adds: build again with less of it
        level -= 1
        log('Building with the plain in-game menu...' if level else 'Building without the in-game menu...')
        wire_switches(gen, patch_text, menu=level)
        p = subprocess.run(cmd, cwd=recomp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                           errors='replace', creationflags=quiet)
        tail = [l for l in p.stdout.splitlines() if l.strip()][-12:]
        failed = p.returncode != 0
    if failed:
        raise PatchError('Compiling failed:\n' + '\n'.join(tail))
    built = os.path.join(out, 'mlb.exe')
    if not os.path.exists(built):
        raise PatchError('The build finished without an mlb.exe.')
    exe = os.path.join(game_root, 'mlb.exe')
    keep = os.path.join(game_root, 'mlb.original.exe')
    if os.path.exists(exe) and not os.path.exists(keep):
        shutil.copy2(exe, keep)
    tmp = exe + '.new'
    shutil.copy2(built, tmp)
    try:
        os.replace(tmp, exe)
    except PermissionError:
        os.remove(tmp)
        raise PatchError('mlb.exe is in use. Close the game and try again.') from None
    log('Done')
    return {'exe': exe, 'live': live, 'menu': level if patched else MENU_NONE}


def restore_exe(game_root):
    keep = os.path.join(game_root, 'mlb.original.exe')
    if not os.path.exists(keep):
        return False
    os.replace(keep, os.path.join(game_root, 'mlb.exe'))
    return True


TEMPLATE = '''# A code mod for MLB The Show 26 (PC recomp). Lines starting with # are notes, except the four kinds below.
#
# set  <name> <SWITCH> <default>      one switchable code mod. SWITCH is upper case, e.g. MLB_MOD_MYCHEAT
# site <set> <module> <offset> <original> <replacement> [<replacement> ...]
#
# <module> is main or sdk. <offset> is where the instruction sits in that module (hex). <original> is the ARM64
# instruction word that is there now (hex); the build stops if it does not match, so a patch made for another game
# version cannot land in the wrong place. Each <replacement> is an ARM64 instruction word to run instead.
#
# What Code Mods and the in-game menu (F4) show:
#   #group Hitting                    the heading the sets under this line are listed under
#   #: my_cheat: What it does, in a sentence.
#   #tag my_cheat: Experimental       a short mark beside the name
#
# A dial is a number you can turn while the game runs:
#   #dial my_power 1.5 0.5 4 0.25 Power      name, where it starts, lowest, highest, step, what to call it
# and in a site, $my_power:s1 as a replacement word loads it into float register s1.
#
# Example (not a real patch):
# #group Hitting
# #: example: Doubles something.
# #dial example_amount 2 1 4 0.5 Amount
# set  example MLB_MOD_EXAMPLE 0
# site example main 123456 1e210800 $example_amount:s1 1e210800
'''


ARCADE_NAME = 'Arcade Code Mods'
ARCADE = '''# The code mods that come with Mod the Show Manager, for MLB The Show 26 (PC recomp), game version 1.0.15.
# Each one changes a number or a decision the game makes, so one that misbehaves can be switched off in the game
# (F4) or before the next launch.

#group Hitting

# The power of a hit is kept in mph on the hit itself; the game turns it into the ball's speed, and the exit
# velocity on screen is read from the same place. This multiplies it right before that, so the ball flies harder
# and the reading goes up with it. The game's own log confirms it (AutoHit::m_fPowerMPH).
#: exit_velocity: Every ball comes off the bat this many times harder, and the exit velocity on screen shows it. 1.5 turns warning-track flies into upper deck shots; 3 and up is silly.
#dial exit_velocity 1.5 0.5 5 0.25 Exit velocity x
set  exit_velocity MLB_MOD_EXITVELO 0
site exit_velocity main 167d0b8 bd404a60 bd404a60 $exit_velocity:s1 1e210800 bd004a60

# The swing's aim error is (where the PCI is) minus (where the pitch crosses the plate). These move the PCI onto the
# ball right before that subtraction, so the contact is always centred. Timing is still up to you.
#: auto_pci: Your PCI snaps onto the ball on every swing. You only have to time it. Offline fun only.
set  auto_pci MLB_MOD_AUTOPCI 0
site auto_pci main 35671c 1e203860 f9402288 79417908 51002508 4b0803e9 2a080128 131f7d08 1e260069 1e26000a 4a09014a 0a08014a 4a0a0129 1e270123 bd000a63 1e203860
site auto_pci main 356724 1e213841 f9402288 79417908 51002508 4b0803e9 2a080128 131f7d08 1e260049 1e26002a 4a09014a 0a08014a 4a0a0129 1e270122 bd000e62 1e213841

#: auto_pci_everyone: The same for every hitter, CPU included. Use it if Auto PCI does nothing for you.
set  auto_pci_everyone MLB_MOD_AUTOPCI_EVERYONE 0
site auto_pci_everyone main 35671c 1e203860 1e204003 bd000a63 1e203860
site auto_pci_everyone main 356724 1e213841 1e204022 bd000e62 1e213841

# The PCI you see is kept by the batting interface: a spot in the strike zone (x, y in zone units at +0x10, in feet at
# +0x18) worked out from the stick every frame. Right after that, these put it where the pitch is going instead
# (pitch +0x148 / +0x14c, the same numbers the swing compares against), so the PCI on screen sits on the ball.
#: auto_pci_visual: The PCI on screen moves onto the pitch by itself, so you can watch it work. Goes with Auto PCI.
#tag auto_pci_visual: Experimental
set  auto_pci_visual MLB_MOD_AUTOPCI_VISUAL 0
site auto_pci_visual main 1530b4 1e204102 f94002e9 f940112a 3944914a 5100054a 531f7d4a 8b0a0d29 f9400d29 b981592a 8b0a0d29 f9400d29 f9400929 f9409929 f9400529 f9400529 f9406129 bd414930 bd414d31 1e2f1017 1e3f1018 1e377a10 1e386a10 1e377a31 1e386a31 f94002ca bd400952 1e2d1013 1f134a12 bd400d54 bd402555 1e2c1016 1e360ab5 1f155234 2d024670 2d035272 1e204102
site auto_pci_visual main 153da4 f94002c8 f94002e9 f940112a 3944914a 5100054a 531f7d4a 8b0a0d29 f9400d29 b981592a 8b0a0d29 f9400d29 f9400929 f9409929 f9400529 f9400529 f9406129 bd414930 bd414d31 1e2f1017 1e3f1018 1e377a10 1e386a10 1e377a31 1e386a31 f94002ca bd400952 1e2d1013 1f134a12 bd400d54 bd402555 1e2c1016 1e360ab5 1f155234 2d024670 2d035272 f94002c8

# The game marks a swing "perfect PCI" and "perfect timing" with two flags. This sets both for human hitters.
#: perfect_perfect: Every ball you put in play counts as Perfect-Perfect contact.
#tag perfect_perfect: Experimental
set  perfect_perfect MLB_MOD_PERFECT 0
site perfect_perfect main 167a8cc 79009a68 79417b49 51002529 4b0903ea 2a090149 531f7d29 2a090108 79009a68
site perfect_perfect main 167a8d8 12000002 12000002 79417b49 51002529 4b0903ea 2a090149 531f7d29 2a090042

#: unbreakable_bats: Bats never break.
set  unbreakable_bats MLB_MOD_NOBREAK 0
site unbreakable_bats main 35acdc 1e2dcc2b 1e2041ab

# A bunt is given its direction and its power (never more than 130 mph) and becomes hit type BUNT. This multiplies
# the power right before it is stored, so the ball comes off the bat like a swing. The game's log shows it
# (Hit Type: BUNT, AutoHit::m_fPowerMPH).
#: power_bunts: A bunt comes off the bat this many times harder, like a real swing. 4 turns a soft bunt into a rocket through the infield.
#tag power_bunts: Experimental
#dial power_bunts 4 1 8 0.5 Bunt power x
set  power_bunts MLB_MOD_POWERBUNTS 0
site power_bunts main 1676838 bd004a61 $power_bunts:s2 1e220821 bd004a61

#group Ball and Air

# The game works out air density from the park's temperature and altitude; thinner air means less drag, so fly
# balls carry (it is why Coors Field plays the way it does). This multiplies the result everywhere. The game's own
# log confirms it (AutoHit::m_fAirDensity, about 0.075 untouched). It does not move pitches.
#: air: How much air the ball flies through. 0.25 makes every park play four times higher than Coors Field and fly balls carry forever; 2 and up makes them die at the warning track.
#dial air 0.25 0.25 8 0.25 Air x
set  air MLB_MOD_AIR 0
site air main 165ac78 1e210800 1e210800 $air:s1 1e210800

# When the ball hits something, how much of its speed it keeps is the ball's own bounce times the surface's. This
# multiplies that, for the ground and the walls alike.
#: bouncy_ball: How much the ball bounces off the ground and the walls. 1.5 is a super ball; past 2 it may never settle down.
#tag bouncy_ball: Experimental
#dial bouncy_ball 1.5 0.25 2.5 0.25 Bounce x
set  bouncy_ball MLB_MOD_BOUNCY 0
site bouncy_ball main 1659528 1e210813 1e210813 $bouncy_ball:s1 1e210a73

# A thrown ball's speed (mph to feet per second) x 1.25. Aim may be off.
#: rocket_arms: Thrown balls travel 1.25x faster.
#tag rocket_arms: Experimental
set  rocket_arms MLB_MOD_ROCKETARMS 0
site rocket_arms main 1688088 72a7f768 72a7fd48

#group Pitching

# A pitch is launched from its speed in mph: times 1.4667 is feet per second, and the distance to the plate over
# that is how long it is in the air. This multiplies the speed there. The number on screen is the pitch's own and
# stays as it was.
#: pitch_speed: How fast every pitch gets to the plate. 1.3 makes a 95 mph fastball play like 123; 0.6 is slow-pitch softball.
#tag pitch_speed: Experimental
#dial pitch_speed 1.3 0.4 2 0.05 Pitch speed x
set  pitch_speed MLB_MOD_PITCHSPEED 0
site pitch_speed main 1655b18 1e220802 1e220802 $pitch_speed:s0 1e200842

# A spinning ball is pushed sideways by the air (spin crossed with its velocity, times a lift number, over the
# ball's mass). That push is what makes a pitch break. This multiplies it, for every ball in the air, so hit balls
# hook and slice more too. The game's log shows it (Actual Pitch Movement, in feet).
#: pitch_break: How hard spin bends the ball. 2.5 is wiffle ball: sliders sweep across the whole plate. 0 and nothing moves at all.
#tag pitch_break: Experimental
#dial pitch_break 2.5 0 6 0.25 Break x
set  pitch_break MLB_MOD_BREAK 0
site pitch_break main 1657168 1e270120 1e270120 $pitch_break:s3 1e230800

# Fatigue per pitch starts from 2.1; this makes it 0.525.
#: iron_arms: Pitchers tire four times slower.
#tag iron_arms: Experimental
set  iron_arms MLB_MOD_IRONARMS 0
site iron_arms main 3c56fc 72a800c8 72a7e0c8
site iron_arms main 3c5710 72a800c8 72a7e0c8
'''


def last_game(game_root):
    """What the game's own log (logs/mlb.log) recorded in its last session, for checking a code mod did something:
    {'hits': how many balls were put in play, 'hardest': mph, 'bunts', 'hardest_bunt', 'air': air density,
    'breaks': how many pitches, 'biggest_break': feet, 'usual_break': feet}, with whatever was found."""
    path = os.path.join(game_root, 'logs', 'mlb.log')
    try:
        size = os.path.getsize(path)
        with open(path, 'rb') as f:
            f.seek(max(0, size - 8_000_000))
            tail = f.read().decode('utf-8', 'replace')
    except OSError:
        return {}
    out = {}
    mph = [float(x) for x in re.findall(r'AutoHit::m_fPowerMPH\s*= (-?[\d.]+)f', tail)]
    if mph:
        out['hits'], out['hardest'] = len(mph), max(mph)
    bunts = [float(x) for x in re.findall(r'Hit Type: BUNT\b(?:.*\n){1,12}?.*AutoHit::m_fPowerMPH\s*= (-?[\d.]+)f', tail)]
    if bunts:
        out['bunts'], out['hardest_bunt'] = len(bunts), max(bunts)
    m = re.findall(r'AutoHit::m_fAirDensity\s*= (-?[\d.]+)f', tail)
    if m:
        out['air'] = float(m[-1])
    m = [float(x) for x in re.findall(r'Actual Pitch Movement: .*\((-?[\d.]+) ft\)', tail)]
    if m:
        out['breaks'], out['biggest_break'] = len(m), max(m)
        out['usual_break'] = sorted(m)[len(m) // 2]
    return out


def last_swing(game_root):
    """What the game's own log (logs/mlb.log) says about the last swing: {'error': aim error, 'perfect': (pci,
    timing)} with whatever was found, or {}. Handy for checking Auto PCI (error 0.00) and Perfect-Perfect (1 1)."""
    path = os.path.join(game_root, 'logs', 'mlb.log')
    try:
        size = os.path.getsize(path)
        with open(path, 'rb') as f:
            f.seek(max(0, size - 8_000_000))
            tail = f.read().decode('utf-8', 'replace')
    except OSError:
        return {}
    out = {}
    m = re.findall(r'ErrorMag: (-?[\d.]+)', tail)
    if m:
        out['error'] = float(m[-1])
    m = re.findall(r'PERFECT PERFECT (\d) (\d)', tail)
    if m:
        out['perfect'] = (int(m[-1][0]), int(m[-1][1]))
    return out
