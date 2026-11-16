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
DESCRIPTIONS = {}     # set name -> one line shown in the manager (from '#: name: text' lines)


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
    DESCRIPTIONS.update({m.group(1): m.group(2).strip() for m in
                         re.finditer(r'^#:\s*(\w+)\s*[:=-]\s*(.+)$', text, re.M)})
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
                and all(HEX.match(w) or re.fullmatch(r'@page:x\d{1,2}', w) for w in f[5:]):
            if f[1] not in names:
                bad.append(f'{at}: site uses set {f[1]} before it is defined')
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
    """Joined table of the enabled mods: sets [(name, env, default, mod name)], text, problems."""
    sets, lines, bad, seen = [], [], [], {}
    for m in mods:
        if not m.enabled:
            continue
        for path, text in mod_patches(m):
            s, l, b = parse(text, f'{m.name}/{os.path.basename(path)}')
            bad += b
            for name, env, default in s:
                if name in seen:
                    bad.append(f'{m.name}: set {name} is also in {seen[name]}')
                seen[name] = m.name
                sets.append((name, env, default, m.name))
            lines.append(f'# {m.name}: {os.path.basename(path)}')
            lines += l
    return sets, '\n'.join(lines) + '\n', bad


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


def signature(text):
    import hashlib
    body = '\n'.join(l for l in text.splitlines() if not l.startswith('#'))
    return hashlib.sha1(body.encode()).hexdigest()[:16] if body.strip() else ''


def rebuild(recomp, game_root, patch_text, log=print):
    """Run the recomp's generator and build with the patch table, then swap mlb.exe (the old one is kept once as
    mlb.original.exe). Raises PatchError with the tool's last lines when a step fails."""
    if not is_recomp(recomp):
        raise PatchError('That is not the recomp folder (the one with MLBTS-Setup.exe).')
    py = os.path.join(recomp, 'python', 'python.exe')
    work = os.path.join(recomp, 'temp', 'modtheshow')
    gen, out = os.path.join(work, 'gen'), os.path.join(work, 'build')
    os.makedirs(work, exist_ok=True)
    table = os.path.join(work, 'patches.txt')
    with open(table, 'w', encoding='utf-8') as f:
        f.write(patch_text)
    exefs = os.path.join(game_root, 'game', 'exefs')
    steps = [('Translating the game code', [py, '-I', '-X', 'utf8', os.path.join(recomp, 'recomp', 'gen.py'),
                                           '--exefs', exefs, '--out', gen, '--modules', 'main,sdk'] +
              (['--patches', table] if signature(patch_text) else [])),
             ('Compiling', [py, '-I', '-X', 'utf8', os.path.join(recomp, 'tools', 'build.py'),
                            '--toolchain', os.path.join(recomp, 'llvm'),
                            '--deps', os.path.join(recomp, 'runtime', 'deps'),
                            '--ninja', os.path.join(recomp, 'bin', 'ninja.exe'),
                            '--runtime-lib', os.path.join(recomp, 'runtime', 'libmlbrt.a'), '--portable',
                            '--gen', gen, '--out', out])]
    for title, cmd in steps:
        log(title + '...')
        p = subprocess.Popen(cmd, cwd=recomp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             errors='replace', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        tail = []
        for line in p.stdout:
            line = line.rstrip()
            if line:
                tail = (tail + [line])[-12:]
                if re.match(r'emitted \d+/\d+ chunks|\[\d+/\d+\]', line):
                    log(f'{title}: {line.split("]")[0].lstrip("[") if line.startswith("[") else line}')
        if p.wait():
            raise PatchError(f'{title} failed:\n' + '\n'.join(tail))
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
    return exe


def restore_exe(game_root):
    keep = os.path.join(game_root, 'mlb.original.exe')
    if not os.path.exists(keep):
        return False
    os.replace(keep, os.path.join(game_root, 'mlb.exe'))
    return True


TEMPLATE = '''# A code mod for MLB The Show 26 (PC recomp). Lines starting with # are notes.
#
# set  <name> <SWITCH> <default>      one switchable group of patches. SWITCH is upper case, e.g. MLB_MOD_MYCHEAT
# site <set> <module> <offset> <original> <replacement> [<replacement> ...]
#
# <module> is main or sdk. <offset> is where the instruction sits in that module (hex). <original> is the ARM64
# instruction word that is there now (hex); the build stops if it does not match, so a patch made for another game
# version cannot land in the wrong place. Each <replacement> is the ARM64 instruction word to run instead.
#
# Example (not a real patch):
# set  example MLB_MOD_EXAMPLE 1
# site example main 123456 1e202008 1e204008
'''


ARCADE_NAME = 'Arcade Code Mods'
ARCADE = '''# Arcade code mods for MLB The Show 26 (PC recomp), game version 1.0.15.
# Made with Mod the Show Manager. Every patch only swaps a number the game uses, so a set that misbehaves can be
# switched off before the next launch.
#
# How the hit ones work: when the bat meets the ball the game has the hit's power in mph and a direction. It turns
# mph into feet per second (x 1.4667) and that becomes the ball's speed off the bat. These sets change that one
# number, so every ball leaves the bat faster. If several are on, the first one below wins.

#: orbit_shots: Balls leave the bat 3x faster. Everything is gone.
set  orbit_shots MLB_MOD_ORBIT 0
site orbit_shots main 167d0b4 72a7f769 72a81189

#: god_power: Balls leave the bat 2x faster.
set  god_power MLB_MOD_GODPOWER 0
site god_power main 167d0b4 72a7f769 72a80769

#: moonshot: Balls leave the bat 1.5x faster. Warning track fly balls become upper deck shots.
set  moonshot MLB_MOD_MOONSHOT 0
site moonshot main 167d0b4 72a7f769 72a80189

#: juiced_ball: Balls leave the bat 1.25x faster. A lively ball without getting silly.
set  juiced_ball MLB_MOD_JUICED 0
site juiced_ball main 167d0b4 72a7f769 72a7fd49

#: dead_ball: Balls leave the bat 20% slower. 1910s baseball.
set  dead_ball MLB_MOD_DEADBALL 0
site dead_ball main 167d0b4 72a7f769 72a7f2c9

# The game works out air density from the park's temperature and altitude; thinner air means less drag, so fly
# balls carry (it is why Coors Field plays the way it does). This quarters the result everywhere. Pitches may break
# less too, since the same air moves them.
#: thin_air: Every park plays like it is four times higher than Coors Field. Fly balls carry forever.
set  thin_air MLB_MOD_THINAIR 0
site thin_air main 165ac78 1e210800 1e210800 1e2a1001 1e210800

# Experimental: a thrown ball's speed (mph to feet per second) x 1.25. Aim may be off.
#: rocket_arms: Experimental. Thrown balls travel 1.25x faster.
set  rocket_arms MLB_MOD_ROCKETARMS 0
site rocket_arms main 1688088 72a7f768 72a7fd48

# The swing's aim error is (where the PCI is) minus (where the pitch crosses the plate). These move the PCI onto the
# ball right before that subtraction, so the contact is always centred. Timing is still up to you.
#: auto_pci: Your PCI snaps onto the ball on every swing. You only have to time it. Offline fun only.
set  auto_pci MLB_MOD_AUTOPCI 0
site auto_pci main 35671c 1e203860 f9402288 79417908 51002508 4b0803e9 2a080128 131f7d08 1e260069 1e26000a 4a09014a 0a08014a 4a0a0129 1e270123 bd000a63 1e203860
site auto_pci main 356724 1e213841 f9402288 79417908 51002508 4b0803e9 2a080128 131f7d08 1e260049 1e26002a 4a09014a 0a08014a 4a0a0129 1e270122 bd000e62 1e213841

#: auto_pci_everyone: Same, but for every hitter, CPU included. Use it if the one above does nothing.
set  auto_pci_everyone MLB_MOD_AUTOPCI_EVERYONE 0
site auto_pci_everyone main 35671c 1e203860 1e204003 bd000a63 1e203860
site auto_pci_everyone main 356724 1e213841 1e204022 bd000e62 1e213841

# The game marks a swing "perfect PCI" and "perfect timing" with two flags. This sets both for human hitters.
#: perfect_perfect: Experimental. Every ball you put in play counts as Perfect-Perfect contact.
set  perfect_perfect MLB_MOD_PERFECT 0
site perfect_perfect main 167a8cc 79009a68 79417b49 51002529 4b0903ea 2a090149 531f7d29 2a090108 79009a68
site perfect_perfect main 167a8d8 12000002 12000002 79417b49 51002529 4b0903ea 2a090149 531f7d29 2a090042

#: unbreakable_bats: Bats never break.
set  unbreakable_bats MLB_MOD_NOBREAK 0
site unbreakable_bats main 35acdc 1e2dcc2b 1e2041ab

# Fatigue per pitch starts from 2.1; this makes it 0.525.
#: iron_arms: Experimental. Pitchers tire four times slower.
set  iron_arms MLB_MOD_IRONARMS 0
site iron_arms main 3c56fc 72a800c8 72a7e0c8
site iron_arms main 3c5710 72a800c8 72a7e0c8
'''
