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


BUILD_REV = 3      # goes up when the way the manager builds changes, so an older build is offered a rebuild
SWITCH_FILE = 'mts-code.cfg'
SWITCH_LOG = 'mts-code.log'


def signature(text):
    import hashlib
    body = '\n'.join(l for l in text.splitlines() if not l.startswith('#'))
    return hashlib.sha1(f'{BUILD_REV}\n{body}'.encode()).hexdigest()[:16] if body.strip() else ''


def switch_source(sets, hotkeys=True):
    """C for the switches of the built-in sets. sets: [(name, env, default)] in table order.

    The recomp's shipped runtime library was built without any patch sets, so its own switch array is never filled
    in and a set baked into the game could not be turned on. The manager points the lifted code at this array
    instead. It is filled before the game starts: each set's default, then mts-code.cfg in the game folder
    (name=0/1, written by the manager), then the set's environment variable. What was decided goes to
    logs/mts-code.log so it can be checked.

    hotkeys adds a small watcher thread (Windows): F2 steps through the code mods, F3 switches the one shown on or
    off while the game runs. The window title shows it for a moment and a tone confirms it (high for on, low for
    off). A change made this way is saved to mts-code.cfg."""
    rows = ',\n'.join(f'    {{"{n}", "{e}", {int(d)}, "{nice(n)}"}}' for n, e, d in sets)
    keys = '''
#ifdef _WIN32
#include <windows.h>

static void mts_save(void) {
    FILE *f = fopen("{SWITCH_FILE}", "w");
    int i;
    if (!f)
        return;
    fprintf(f, "# Code mod switches, written by Mod the Show Manager. name=1 is on.\\n");
    for (i = 0; i < MTS_SETS; i++)
        fprintf(f, "%s=%d\\n", mts_sets[i].name, mts_patch_on[i]);
    fclose(f);
}

static BOOL CALLBACK mts_find(HWND h, LPARAM out) {
    DWORD pid = 0;
    GetWindowThreadProcessId(h, &pid);
    if (pid == GetCurrentProcessId() && IsWindowVisible(h) && !GetWindow(h, GW_OWNER)) {
        *(HWND *)out = h;
        return FALSE;
    }
    return TRUE;
}

static DWORD WINAPI mts_keys(LPVOID unused) {
    char title[200], saved[200];
    int sel = 0, shown = 0, was2 = 0, was3 = 0;
    HWND win = NULL;
    (void)unused;
    saved[0] = 0;
    for (;;) {
        int f2, f3;
        DWORD pid = 0;
        Sleep(30);
        GetWindowThreadProcessId(GetForegroundWindow(), &pid);
        if (pid != GetCurrentProcessId()) {
            was2 = was3 = 0;
            continue;
        }
        f2 = (GetAsyncKeyState(VK_F2) & 0x8000) != 0;
        f3 = (GetAsyncKeyState(VK_F3) & 0x8000) != 0;
        if ((f2 && !was2) || (f3 && !was3)) {
            if (f2 && !was2 && shown)
                sel = (sel + 1) % MTS_SETS;
            if (f3 && !was3) {
                mts_patch_on[sel] = (uint8_t)!mts_patch_on[sel];
                mts_save();
            }
            win = NULL;
            EnumWindows(mts_find, (LPARAM)&win);
            if (win) {
                if (!shown)
                    GetWindowTextA(win, saved, sizeof saved);
                snprintf(title, sizeof title, "%s: %s   (F2 next, F3 on/off)", mts_sets[sel].title,
                         mts_patch_on[sel] ? "ON" : "OFF");
                SetWindowTextA(win, title);
            }
            Beep(f3 && !was3 ? (mts_patch_on[sel] ? 1047 : 392) : 659, 70);
            shown = 100;                      /* about three seconds */
        } else if (shown && !--shown && win && saved[0]) {
            SetWindowTextA(win, saved);
        }
        was2 = f2;
        was3 = f3;
    }
    return 0;
}
#endif
''' if hotkeys else ''
    keys = keys.replace('{SWITCH_FILE}', SWITCH_FILE)
    start = '''
#ifdef _WIN32
    CloseHandle(CreateThread(NULL, 0, mts_keys, NULL, 0, NULL));
#endif''' if hotkeys else ''
    return f'''// Written by Mod the Show Manager (codemods.switch_source). Switches for code mod sets.
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MTS_SETS {len(sets)}
uint8_t mts_patch_on[MTS_SETS + 1];

static const struct {{ const char *name; const char *env; int def; const char *title; }} mts_sets[MTS_SETS] = {{
{rows}
}};
{keys}
__attribute__((constructor)) static void mts_switches_init(void) {{
    const char *from[MTS_SETS];
    char line[256];
    FILE *f;
    int i;
    for (i = 0; i < MTS_SETS; i++) {{
        mts_patch_on[i] = (uint8_t)(mts_sets[i].def != 0);
        from[i] = "default";
    }}
    f = fopen("{SWITCH_FILE}", "r");
    if (f) {{
        while (fgets(line, sizeof line, f)) {{
            char *eq = strchr(line, '=');
            if (!eq || line[0] == '#')
                continue;
            *eq = 0;
            for (i = 0; i < MTS_SETS; i++)
                if (!strcmp(line, mts_sets[i].name)) {{
                    mts_patch_on[i] = (uint8_t)(eq[1] == '1');
                    from[i] = "{SWITCH_FILE}";
                }}
        }}
        fclose(f);
    }}
    for (i = 0; i < MTS_SETS; i++) {{
        const char *v = getenv(mts_sets[i].env);
        if (v && v[0]) {{
            mts_patch_on[i] = (uint8_t)(v[0] == '1');
            from[i] = "launch switch";
        }}
    }}
    f = fopen("logs/{SWITCH_LOG}", "w");
    if (f) {{
        fprintf(f, "Code mods built into this mlb.exe: %d\\n", MTS_SETS);
        for (i = 0; i < MTS_SETS; i++)
            fprintf(f, "%s=%d (%s)\\n", mts_sets[i].name, mts_patch_on[i], from[i]);
        fclose(f);
    }}{start}
}}
'''


def table_sets(patch_text):
    """[(name, env, default)] in the order the generator numbers them."""
    out = []
    for raw in patch_text.splitlines():
        f = raw.split('#', 1)[0].split()
        if len(f) == 4 and f[0] == 'set':
            out.append((f[1], f[2], int(f[3])))
    return out


def wire_switches(gen, patch_text, hotkeys=True):
    """After the generator ran: point every patched chunk at the manager's switch array and add its source.
    Returns how many chunks were changed."""
    sets = table_sets(patch_text)
    main = os.path.join(gen, 'main')
    src = os.path.join(main, 'mts_switches.c')
    if not sets:
        if os.path.exists(src):
            os.remove(src)
        return 0
    changed = 0
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
            if b'rt_patch_on' in data:
                with open(path, 'wb') as f:
                    f.write(data.replace(b'rt_patch_on', b'mts_patch_on'))
                changed += 1
    text = switch_source(sets, hotkeys)
    old = None
    if os.path.exists(src):
        with open(src, encoding='utf-8') as f:
            old = f.read()
    if old != text:
        with open(src, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
    return changed


def write_switches(game_root, states):
    """states: {set name: bool}. The built game reads this file when it starts, however it is launched."""
    path = os.path.join(game_root, SWITCH_FILE)
    body = ('# Code mod switches, written by Mod the Show Manager. name=1 is on.\n' +
            ''.join(f'{n}={1 if on else 0}\n' for n, on in states.items()))
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(body)


def read_switches(game_root):
    """{set name: bool} from mts-code.cfg (the game rewrites it when a mod is switched with F3), or {}."""
    out = {}
    try:
        with open(os.path.join(game_root, SWITCH_FILE), encoding='utf-8', errors='replace') as f:
            for line in f:
                m = re.match(r'(\w+)=([01])\s*$', line)
                if m:
                    out[m.group(1)] = m.group(2) == '1'
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
    for k, (title, cmd) in enumerate(steps):
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
        failed = p.wait() != 0
        if failed and k == 1 and signature(patch_text) and any('mts_switches' in t for t in tail):
            # the in-game keys are the only Windows-specific code the manager adds: build again without them
            log('Building without the in-game F2/F3 keys...')
            wire_switches(gen, patch_text, hotkeys=False)
            p = subprocess.run(cmd, cwd=recomp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                               errors='replace', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            tail = [l for l in p.stdout.splitlines() if l.strip()][-12:]
            failed = p.returncode != 0
        if failed:
            raise PatchError(f'{title} failed:\n' + '\n'.join(tail))
        if k == 0:
            n = wire_switches(gen, patch_text)
            if signature(patch_text):
                if not n:
                    raise PatchError('The translated code has no patched spots in it, so the code mods would do '
                                     'nothing. Nothing was changed.')
                log(f'Switches wired into {n} piece(s) of the game code')
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

# The PCI you see is kept by the batting interface: a spot in the strike zone (x, y in zone units at +0x10, in feet at
# +0x18) worked out from the stick every frame. Right after that, these put it where the pitch is going instead
# (pitch +0x148 / +0x14c, the same numbers the swing compares against), so the PCI on screen sits on the ball.
#: auto_pci_visual: New. The PCI on screen moves onto the pitch by itself, so you can see it. Turn it off if anything looks wrong.
set  auto_pci_visual MLB_MOD_AUTOPCI_VISUAL 0
site auto_pci_visual main 1530b4 1e204102 f94002e9 f940112a 3944914a 5100054a 531f7d4a 8b0a0d29 f9400d29 b981592a 8b0a0d29 f9400d29 f9400929 f9409929 f9400529 f9400529 f9406129 bd414930 bd414d31 1e2f1017 1e3f1018 1e377a10 1e386a10 1e377a31 1e386a31 f94002ca bd400952 1e2d1013 1f134a12 bd400d54 bd402555 1e2c1016 1e360ab5 1f155234 2d024670 2d035272 1e204102
site auto_pci_visual main 153da4 f94002c8 f94002e9 f940112a 3944914a 5100054a 531f7d4a 8b0a0d29 f9400d29 b981592a 8b0a0d29 f9400d29 f9400929 f9409929 f9400529 f9400529 f9406129 bd414930 bd414d31 1e2f1017 1e3f1018 1e377a10 1e386a10 1e377a31 1e386a31 f94002ca bd400952 1e2d1013 1f134a12 bd400d54 bd402555 1e2c1016 1e360ab5 1f155234 2d024670 2d035272 f94002c8

# The game marks a swing "perfect PCI" and "perfect timing" with two flags. This sets both for human hitters.
#: perfect_perfect: Experimental. Every ball you put in play counts as Perfect-Perfect contact.
set  perfect_perfect MLB_MOD_PERFECT 0
site perfect_perfect main 167a8cc 79009a68 79417b49 51002529 4b0903ea 2a090149 531f7d29 2a090108 79009a68
site perfect_perfect main 167a8d8 12000002 12000002 79417b49 51002529 4b0903ea 2a090149 531f7d29 2a090042

#: unbreakable_bats: Bats never break.
set  unbreakable_bats MLB_MOD_NOBREAK 0
site unbreakable_bats main 35acdc 1e2dcc2b 1e2041ab

# A pitch's speed is its base speed times a factor from 0.95 to 1.05 taken from the pitcher (pitch +0x110). These
# scale that factor.
#: heat: Experimental. Every pitch comes in about 15% faster.
set  heat MLB_MOD_HEAT 0
site heat main 24ada4 72a7ee68 529ae148 72a7f168
site heat main 24adb0 72a7f0c8 5291eb88 72a7f348

#: soft_toss: Experimental. Every pitch comes in about 15% slower.
set  soft_toss MLB_MOD_SOFTTOSS 0
site soft_toss main 24ada4 72a7ee68 52970a48 72a7e9c8
site soft_toss main 24adb0 72a7f0c8 528f5c28 72a7ec88

# Fatigue per pitch starts from 2.1; this makes it 0.525.
#: iron_arms: Experimental. Pitchers tire four times slower.
set  iron_arms MLB_MOD_IRONARMS 0
site iron_arms main 3c56fc 72a800c8 72a7e0c8
site iron_arms main 3c5710 72a800c8 72a7e0c8
'''


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
