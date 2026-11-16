"""The C the manager adds to the game when it is rebuilt with code mods: the switches, the dials, the counters and the
in-game menu. codemods.switch_source fills the {PLACEHOLDERS} in.

Three strengths, tried in this order by codemods.rebuild until one builds:
  2  the menu, joined to the game's own input: the game ignores the pad and keys while the panel is open (as it does for
     its own F1 menu), and the pad moves through the panel
  1  the menu on its own: keyboard only, the game is not told
  0  no menu and no keys: the switches are read when the game starts and that is all
"""

HEAD = r"""// Written by Mod the Show Manager (codemods.switch_source). Switches, dials and the in-game menu for code mods.
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MTS_SETS {NSETS}
#define MTS_DIALS {NDIALS}
#define MTS_ROWS {NROWS}
#define MTS_SEAMS {SEAMS}
uint8_t mts_patch_on[MTS_SETS + 1];
uint32_t mts_dial[16];                     /* the bits of each dial's number, read by the patched code; 0 is unused */
volatile uint32_t mts_ran[MTS_SETS + 1];   /* how many times each set's code has run since the game started */

static const struct { const char *name, *env; int def; const char *title, *about; } mts_sets[MTS_SETS + 1] = {
{SETROWS}    {"", "", 0, "", ""}
};
static const struct { const char *name, *title; float def, lo, hi, step; } mts_dials[MTS_DIALS + 1] = {
    {"", "", 0.0f, 0.0f, 0.0f, 0.0f}{DIALROWS}
};
/* one line of the menu: a mod, the dial it turns (0: none), and whether the line is the mod's own (1) or one more
   dial of the mod above it (0) */
__attribute__((unused)) static const struct { int set, dial, own; } mts_rows[MTS_ROWS + 1] = {
{MENUROWS}    {0, 0, 0}
};
static float mts_dial_value[MTS_DIALS + 1];
static const char *mts_from[MTS_SETS + 1];

static void mts_set_dial(int k, float v) {
    if (v < mts_dials[k].lo) v = mts_dials[k].lo;
    if (v > mts_dials[k].hi) v = mts_dials[k].hi;
    mts_dial_value[k] = v;
    memcpy(&mts_dial[k], &v, sizeof v);
}

__attribute__((unused)) static void mts_save(void) {
    FILE *f = fopen("{SWITCH_FILE}", "w");
    int i;
    if (!f)
        return;
    fputs("# Code mod switches, written by Mod the Show Manager. name=1 is on. A dial is dial.name=number.\n", f);
    for (i = 0; i < MTS_SETS; i++)
        fprintf(f, "%s=%d\n", mts_sets[i].name, mts_patch_on[i]);
    for (i = 1; i <= MTS_DIALS; i++)
        fprintf(f, "dial.%s=%.3f\n", mts_dials[i].name, (double)mts_dial_value[i]);
    fclose(f);
}

static void mts_write_log(void) {
    FILE *f = fopen("logs/{SWITCH_LOG}", "w");
    int i;
    if (!f)
        return;
    fprintf(f, "Code mods built into this mlb.exe: %d\n", MTS_SETS);
    for (i = 0; i < MTS_SETS; i++)
        fprintf(f, "%s=%d (%s)\n", mts_sets[i].name, mts_patch_on[i], mts_from[i]);
    for (i = 1; i <= MTS_DIALS; i++)
        fprintf(f, "dial %s=%.3f\n", mts_dials[i].name, (double)mts_dial_value[i]);
    for (i = 0; i < MTS_SETS; i++)
        fprintf(f, "ran %s=%u\n", mts_sets[i].name, (unsigned)mts_ran[i]);
    fclose(f);
}
"""

MENU = r"""
#ifdef _WIN32
#include <windows.h>

/* The in-game menu: a small panel drawn over the game's window.
     F4                 open and close
     Up / Down          move                      (F2 moves down too)
     Enter              switch the mod on or off  (F3 too)
     Left / Right       turn a dial; on a mod without one, off and on
   F2 and F3 also work with the panel closed, the way they always did: a line shows what they did.
   Every change takes effect at once and is saved for the next start. */
#if MTS_SEAMS
/* the recomp runtime's own seams (runtime/gfx/input.h, input_win.h, ui/menu.h) */
extern HWND gfx_window_handle(void);
extern int menu_is_open(void);                 /* the game's F1 menu */
extern void input_menu(int open);              /* 1: the game gets no input, as while its own menu is open */
extern int input_pad_read(uint64_t *buttons, int32_t *lx, int32_t *ly);
#endif

#define MTS_SHOWN 12
static HWND mts_game, mts_panel;
static int mts_open, mts_sel, mts_top, mts_toast, mts_blocked;
static float mts_scale = 1.0f;
#define S(x) ((int)((x) * mts_scale + 0.5f))

#if !MTS_SEAMS
static BOOL CALLBACK mts_find(HWND w, LPARAM out) {
    DWORD pid = 0;
    GetWindowThreadProcessId(w, &pid);
    if (pid == GetCurrentProcessId() && w != mts_panel && IsWindowVisible(w) && !GetWindow(w, GW_OWNER)) {
        *(HWND *)out = w;
        return FALSE;
    }
    return TRUE;
}
#endif

static HWND mts_game_window(void) {
#if MTS_SEAMS
    return gfx_window_handle();
#else
    HWND w = NULL;
    EnumWindows(mts_find, (LPARAM)&w);
    return w;
#endif
}

static void mts_words(HDC dc, const char *t, int x, int y, int w, int h, COLORREF c, UINT how) {
    RECT r = {x, y, x + w, y + h};
    SetTextColor(dc, c);
    DrawTextA(dc, t, -1, &r, how | DT_NOPREFIX);
}

static void mts_box(HDC dc, int x, int y, int w, int h, COLORREF c) {
    RECT r = {x, y, x + w, y + h};
    HBRUSH b = CreateSolidBrush(c);
    FillRect(dc, &r, b);
    DeleteObject(b);
}

static void mts_row(HDC dc, int r, int y, int w) {
    char v[48];
    int set = mts_rows[r].set, dial = mts_rows[r].dial, own = mts_rows[r].own;
    int sel = r == mts_sel, on = mts_patch_on[set], h = S(30), x = own ? S(22) : S(44);
    COLORREF name = on ? RGB(244, 244, 244) : RGB(150, 154, 164);
    if (sel)
        mts_box(dc, S(8), y, w - S(16), h, RGB(44, 48, 58));
    mts_words(dc, own ? mts_sets[set].title : mts_dials[dial].title, x, y, w - x - S(250), h, name,
              DT_SINGLELINE | DT_VCENTER | DT_END_ELLIPSIS);
    if (dial) {
        snprintf(v, sizeof v, sel ? "<  %.2f  >" : "%.2f", (double)mts_dial_value[dial]);
        mts_words(dc, v, w - S(250), y, S(150), h, on ? RGB(255, 210, 74) : RGB(150, 154, 164),
                  DT_SINGLELINE | DT_VCENTER | DT_RIGHT);
    } else if (own && mts_ran[set]) {
        snprintf(v, sizeof v, "used %u", (unsigned)mts_ran[set]);
        mts_words(dc, v, w - S(250), y, S(150), h, RGB(120, 124, 134), DT_SINGLELINE | DT_VCENTER | DT_RIGHT);
    }
    if (own)
        mts_words(dc, on ? "ON" : "OFF", w - S(90), y, S(68), h, on ? RGB(64, 200, 110) : RGB(120, 124, 134),
                  DT_SINGLELINE | DT_VCENTER | DT_RIGHT);
}

static int mts_shown(void) {
    return MTS_ROWS < MTS_SHOWN ? MTS_ROWS : MTS_SHOWN;
}

static int mts_height(void) {
    return mts_open ? S(48) + mts_shown() * S(32) + S(112) : S(46);
}

static void mts_paint(HDC dc, int w, int h) {
    HFONT big = CreateFontA(-S(17), 0, 0, 0, FW_SEMIBOLD, 0, 0, 0, DEFAULT_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, "Segoe UI");
    HFONT small = CreateFontA(-S(14), 0, 0, 0, FW_NORMAL, 0, 0, 0, DEFAULT_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, "Segoe UI");
    HFONT was = (HFONT)SelectObject(dc, big);
    char line[96];
    int i, y, set = mts_rows[mts_sel].set;
    SetBkMode(dc, TRANSPARENT);
    mts_box(dc, 0, 0, w, h, RGB(16, 18, 23));
    mts_box(dc, 0, 0, w, S(3), RGB(226, 55, 68));
    if (!mts_open) {                                  /* closed: one line saying what F2 or F3 just did */
        mts_row(dc, mts_sel, S(9), w);
    } else {
        mts_words(dc, "CODE MODS", S(22), S(8), w - S(44), S(34), RGB(244, 244, 244), DT_SINGLELINE | DT_VCENTER);
        SelectObject(dc, small);
        snprintf(line, sizeof line, "%d of %d", mts_sel + 1, MTS_ROWS);
        mts_words(dc, line, S(22), S(8), w - S(44), S(34), RGB(120, 124, 134), DT_SINGLELINE | DT_VCENTER | DT_RIGHT);
        SelectObject(dc, big);
        y = S(46);
        for (i = mts_top; i < MTS_ROWS && i < mts_top + MTS_SHOWN; i++, y += S(32))
            mts_row(dc, i, y, w);
        y = S(46) + mts_shown() * S(32);
        mts_box(dc, S(22), y + S(6), w - S(44), 1, RGB(48, 52, 62));
        SelectObject(dc, small);
        mts_words(dc, mts_sets[set].about, S(22), y + S(14), w - S(44), S(40), RGB(184, 190, 202),
                  DT_WORDBREAK | DT_END_ELLIPSIS);
        if (mts_ran[set])
            snprintf(line, sizeof line, "Its code has run %u times since the game started.", (unsigned)mts_ran[set]);
        else
            snprintf(line, sizeof line, "%s", mts_patch_on[set] ? "On, and its code has not run yet." : "Off.");
        mts_words(dc, line, S(22), y + S(58), w - S(44), S(20), RGB(120, 124, 134), DT_SINGLELINE | DT_VCENTER);
        mts_words(dc, "F4 close     Up / Down move     Enter on / off     Left / Right change", S(22), y + S(82),
                  w - S(44), S(22), RGB(120, 124, 134), DT_SINGLELINE | DT_VCENTER);
    }
    SelectObject(dc, was);
    DeleteObject(big);
    DeleteObject(small);
}

static LRESULT CALLBACK mts_proc(HWND w, UINT m, WPARAM a, LPARAM b) {
    if (m == WM_PAINT) {
        PAINTSTRUCT ps;
        RECT r;
        HDC dc = BeginPaint(w, &ps), mem;
        HBITMAP bmp, old;
        GetClientRect(w, &r);
        mem = CreateCompatibleDC(dc);                 /* drawn off screen first, so the panel never flickers */
        bmp = CreateCompatibleBitmap(dc, r.right, r.bottom);
        old = (HBITMAP)SelectObject(mem, bmp);
        mts_paint(mem, r.right, r.bottom);
        BitBlt(dc, 0, 0, r.right, r.bottom, mem, 0, 0, SRCCOPY);
        SelectObject(mem, old);
        DeleteObject(bmp);
        DeleteDC(mem);
        EndPaint(w, &ps);
        return 0;
    }
    if (m == WM_ERASEBKGND)
        return 1;
    return DefWindowProcA(w, m, a, b);
}

static void mts_show(void) {
    static int made;
    POINT at = {0, 0};
    RECT rc;
    if (!made) {
        WNDCLASSA wc;
        memset(&wc, 0, sizeof wc);
        wc.lpfnWndProc = mts_proc;
        wc.hInstance = GetModuleHandleA(NULL);
        wc.lpszClassName = "MtsCodeMods";
        RegisterClassA(&wc);
        made = 1;
    }
    mts_game = mts_game_window();
    if (!mts_game || !GetClientRect(mts_game, &rc) || rc.bottom < 200)
        return;
    mts_scale = rc.bottom / 1080.0f;                  /* the panel keeps its size on the picture, 4K or 720p */
    if (mts_scale < 0.75f)
        mts_scale = 0.75f;
    if (!mts_panel) {
        mts_panel = CreateWindowExA(WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TRANSPARENT,
                                    "MtsCodeMods", "", WS_POPUP, 0, 0, 100, 100, NULL, NULL, GetModuleHandleA(NULL), NULL);
        if (!mts_panel)
            return;
        SetLayeredWindowAttributes(mts_panel, 0, 242, LWA_ALPHA);
    }
    ClientToScreen(mts_game, &at);
    SetWindowPos(mts_panel, HWND_TOPMOST, at.x + S(36), at.y + S(36), S(640), mts_height(), SWP_NOACTIVATE | SWP_SHOWWINDOW);
    InvalidateRect(mts_panel, NULL, FALSE);
    UpdateWindow(mts_panel);
}

static void mts_hide(void) {
    if (mts_panel)
        ShowWindow(mts_panel, SW_HIDE);
}

static void mts_block(int on) {                       /* the game ignores its pad and keys while the panel is open */
#if MTS_SEAMS
    if (on != mts_blocked)
        input_menu(on);
#endif
    mts_blocked = on;
}

static void mts_switch(int r, int to) {              /* to: 0 off, 1 on, -1 the other way */
    int set = mts_rows[r].set, now = to < 0 ? !mts_patch_on[set] : to;
    if (now == mts_patch_on[set])
        return;
    mts_patch_on[set] = (uint8_t)now;
    Beep(now ? 1047 : 392, 50);
    mts_save();
}

static void mts_turn(int r, int way) {               /* Left (-1) and Right (+1) */
    int k = mts_rows[r].dial;
    if (!k) {
        mts_switch(r, way > 0);
        return;
    }
    mts_set_dial(k, mts_dial_value[k] + way * mts_dials[k].step);
    if (!mts_patch_on[mts_rows[r].set])
        mts_switch(r, 1);                             /* turning a dial is asking for the mod */
    else
        mts_save();
}

enum { K_MENU, K_NEXT, K_FLIP, K_UP, K_DOWN, K_LEFT, K_RIGHT, K_ENTER, K_COUNT };

static DWORD WINAPI mts_keys(LPVOID unused) {
    static const int vk[K_COUNT] = {VK_F4, VK_F2, VK_F3, VK_UP, VK_DOWN, VK_LEFT, VK_RIGHT, VK_RETURN};
    int was[K_COUNT] = {0}, held[K_COUNT] = {0}, tick = 0, i;
    unsigned last = 0;
    (void)unused;
    for (;;) {
        MSG msg;
        DWORD pid = 0;
        int hit[K_COUNT], any = 0, pad_close = 0;
        uint64_t pad = 0;
        while (PeekMessageA(&msg, NULL, 0, 0, PM_REMOVE)) {
            TranslateMessage(&msg);
            DispatchMessageA(&msg);
        }
        Sleep(30);
        if (!(++tick % 100)) {                        /* about every three seconds: what has run, for the log */
            unsigned sum = 0;
            for (i = 0; i < MTS_SETS; i++)
                sum = sum * 31u + mts_ran[i] + mts_patch_on[i];
            if (sum != last) {
                last = sum;
                mts_write_log();
                if (mts_open)
                    mts_show();
            }
        }
        GetWindowThreadProcessId(GetForegroundWindow(), &pid);
        if (pid != GetCurrentProcessId()) {           /* another program is in front: no keys, no panel */
            memset(was, 0, sizeof was);
            memset(held, 0, sizeof held);
            if (mts_panel && IsWindowVisible(mts_panel))
                mts_hide();
            continue;
        }
#if MTS_SEAMS
        if (menu_is_open()) {                         /* the game's own F1 menu is up: it has the screen and the input */
            if (mts_open) {
                mts_open = 0;
                mts_blocked = 0;                      /* its closing gives the input back */
            }
            mts_toast = 0;
            mts_hide();
            memset(was, 0, sizeof was);
            continue;
        }
#endif
#if MTS_SEAMS
        if (mts_open) {                               /* the pad moves through the open panel too */
            int32_t lx = 0, ly = 0;
            pad = 0;
            if (input_pad_read(&pad, &lx, &ly)) {
                pad |= (uint64_t)(ly > 20000) << 13 | (uint64_t)(ly < -20000) << 15 |
                       (uint64_t)(lx < -20000) << 12 | (uint64_t)(lx > 20000) << 14;
                pad_close = (pad >> 10 & 3) != 0;     /* Plus or Minus (Options, Share) */
            } else {
                pad = 0;
            }
        }
#endif
        for (i = 0; i < K_COUNT; i++) {
            int down = (GetAsyncKeyState(vk[i]) & 0x8000) != 0;
            if (mts_open)
                down |= (i == K_UP && (pad >> 13 & 1)) || (i == K_DOWN && (pad >> 15 & 1)) || (i == K_LEFT && (pad >> 12 & 1)) ||
                        (i == K_RIGHT && (pad >> 14 & 1)) || (i == K_ENTER && (pad & 15));
            held[i] = down ? held[i] + 1 : 0;
            hit[i] = (down && !was[i]) || (i >= K_UP && i <= K_RIGHT && held[i] > 14 && !(held[i] % 3));   /* held: repeats */
            was[i] = down;
            any |= hit[i];
        }
        if (mts_open && mts_panel && !IsWindowVisible(mts_panel))
            mts_show();                               /* back from another program */
        if (pad_close && mts_open) {
            hit[K_MENU] = 1;
            any = 1;
        }
        if (!any) {
            if (!mts_open && mts_toast && !--mts_toast)
                mts_hide();
            continue;
        }
        if (hit[K_MENU]) {
            mts_open = !mts_open;
            mts_toast = 0;
            mts_block(mts_open);
            Beep(mts_open ? 880 : 587, 40);
            if (!mts_open) {
                mts_hide();
                mts_write_log();
                continue;
            }
        }
        if (!mts_open && !hit[K_NEXT] && !hit[K_FLIP])
            continue;                                 /* closed: only F2 and F3 do anything */
        if (hit[K_NEXT] && (mts_open || mts_toast))   /* F2: the next one (closed, the first press shows where you are) */
            mts_sel = (mts_sel + 1) % MTS_ROWS;
        if (mts_open && hit[K_DOWN])
            mts_sel = (mts_sel + 1) % MTS_ROWS;
        if (mts_open && hit[K_UP])
            mts_sel = (mts_sel + MTS_ROWS - 1) % MTS_ROWS;
        if (hit[K_FLIP] || (mts_open && hit[K_ENTER]))
            mts_switch(mts_sel, -1);
        if (mts_open && hit[K_LEFT])
            mts_turn(mts_sel, -1);
        if (mts_open && hit[K_RIGHT])
            mts_turn(mts_sel, 1);
        if (mts_sel < mts_top)
            mts_top = mts_sel;
        if (mts_sel >= mts_top + MTS_SHOWN)
            mts_top = mts_sel - MTS_SHOWN + 1;
        if (!mts_open)
            mts_toast = 90;                           /* closed: the line stays for about three seconds */
        mts_show();
    }
    return 0;
}
#endif
"""

TAIL = r"""
__attribute__((constructor)) static void mts_switches_init(void) {
    char line[256];
    FILE *f;
    int i;
    for (i = 0; i < MTS_SETS; i++) {
        mts_patch_on[i] = (uint8_t)(mts_sets[i].def != 0);
        mts_from[i] = "default";
    }
    for (i = 1; i <= MTS_DIALS; i++)
        mts_set_dial(i, mts_dials[i].def);
    f = fopen("{SWITCH_FILE}", "r");
    if (f) {
        while (fgets(line, sizeof line, f)) {
            char *eq = strchr(line, '=');
            if (!eq || line[0] == '#')
                continue;
            *eq = 0;
            if (!strncmp(line, "dial.", 5)) {
                for (i = 1; i <= MTS_DIALS; i++)
                    if (!strcmp(line + 5, mts_dials[i].name))
                        mts_set_dial(i, (float)atof(eq + 1));
                continue;
            }
            for (i = 0; i < MTS_SETS; i++)
                if (!strcmp(line, mts_sets[i].name)) {
                    mts_patch_on[i] = (uint8_t)(eq[1] == '1');
                    mts_from[i] = "{SWITCH_FILE}";
                }
        }
        fclose(f);
    }
    for (i = 0; i < MTS_SETS; i++) {
        const char *v = getenv(mts_sets[i].env);
        if (v && v[0]) {
            mts_patch_on[i] = (uint8_t)(v[0] == '1');
            mts_from[i] = "launch switch";
        }
    }
    mts_write_log();{START}
}
"""

START = r"""
#ifdef _WIN32
    CloseHandle(CreateThread(NULL, 0, mts_keys, NULL, 0, NULL));
#endif"""
