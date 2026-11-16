"""The C the manager adds to the game when it is rebuilt with code mods: the switches, the dials, the counters and the
in-game menu. codemods.switch_source fills the {PLACEHOLDERS} in.

Three strengths, tried in this order by codemods.rebuild until one builds:
  2  the menu, joined to the game: the game's own overlay draws the panel (so it shows in fullscreen), the game
     ignores the pad and keys while it is open, and it stands down while the game's F1 menu is up
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
uint8_t mts_patch_on[MTS_SETS + 1];        /* what the patched code reads */
uint32_t mts_dial[16];                     /* the bits of each dial's number, read by the patched code; 0 is unused */
volatile uint32_t mts_ran[MTS_SETS + 1];   /* how many times each set's code has run since the game started */
/* A site that starts with  mov x16, xN  hands that register over here each time it runs (codemods.wire_chunk): the
   way a mod's own drawing code gets hold of something the game only has in a register, like the ball. */
volatile uint64_t mts_tapv[MTS_SETS + 1];
void mts_tap(int set, uint64_t value) { mts_tapv[set] = value; }
/* What the player chose. The same as mts_patch_on, except while an effect holds a mod on for a while (a streak). */
static uint8_t mts_want[MTS_SETS + 1];
__attribute__((unused)) static void (*mts_log_more)(FILE *f);

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
static volatile unsigned mts_seen[3];        /* the menu: times opened, frames the game drew it, times a window did */
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
        fprintf(f, "%s=%d\n", mts_sets[i].name, mts_want[i]);
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
        fprintf(f, "%s=%d (%s)\n", mts_sets[i].name, mts_want[i], mts_from[i]);
    for (i = 1; i <= MTS_DIALS; i++)
        fprintf(f, "dial %s=%.3f\n", mts_dials[i].name, (double)mts_dial_value[i]);
    for (i = 0; i < MTS_SETS; i++)
        fprintf(f, "ran %s=%u\n", mts_sets[i].name, (unsigned)mts_ran[i]);
    fprintf(f, "menu opened=%u game_drew=%u window_shown=%u\n", mts_seen[0], mts_seen[1], mts_seen[2]);
    if (mts_log_more)
        mts_log_more(f);
    fclose(f);
}
"""

MENU = r"""
#ifdef _WIN32
#include <windows.h>

/* The in-game menu: a small panel over the game's picture.
     F4                 open and close
     Up / Down          move                      (F2 moves down too)
     Enter              switch the mod on or off  (F3 too)
     Left / Right       turn a dial; on a mod without one, off and on
     F6                 fireworks, when that mod is on
   F2 and F3 also work with the panel closed, the way they always did: a line shows what they did.
   Every change takes effect at once and is saved for the next start.

   Who draws it. The game's own overlay (its F1 menu and performance readout, Dear ImGui into the swapchain) is asked
   to call back once a frame, and the panel is drawn there, so it shows in fullscreen like the game's own menu. If
   that overlay is not drawing (nothing of its own to show), opening the panel wakes its fps readout for as long as
   the panel is up. Without any of that (MTS_SEAMS 0, or no frames arrive) the panel is a window on top of the game,
   which works when the game is not fullscreen. */
#if MTS_SEAMS
/* the recomp runtime's own seams (runtime/gfx/input.h, input_win.h, ui/menu.h) and the Dear ImGui 1.91 it links */
extern HWND gfx_window_handle(void);
extern int menu_is_open(void);                 /* the game's F1 menu */
extern void menu_perf_cycle(void);             /* its F10: performance readout off, fps, full */
extern void input_block(int on);               /* 1: the game gets no input; 0: again, once everything is let go */
typedef struct { uint32_t id; int type; uint32_t owner; void (*call)(void *ctx, void *hook); void *user; } MtsHook;
extern void *mts_ig_context(void) __asm__("_ZN5ImGui17GetCurrentContextEv");
extern uint32_t mts_ig_add_hook(void *ctx, const MtsHook *hook) __asm__("_ZN5ImGui14AddContextHookEP12ImGuiContextPK16ImGuiContextHook");
extern void *mts_ig_front(void) __asm__("_ZN5ImGui21GetForegroundDrawListEv");
extern void mts_ig_rect(void *list, const float *a, const float *b, uint32_t col, float round, int flags)
    __asm__("_ZN10ImDrawList13AddRectFilledERK6ImVec2S2_jfi");
extern void mts_ig_text(void *list, void *font, float size, const float *pos, uint32_t col, const char *from,
                        const char *to, float wrap, const float *clip)
    __asm__("_ZN10ImDrawList7AddTextEP6ImFontfRK6ImVec2jPKcS6_fPK6ImVec4");
#endif

#define MTS_SHOWN 12
static HWND mts_game, mts_panel;
static int mts_open, mts_sel, mts_top, mts_toast, mts_blocked, mts_waited;
__attribute__((unused)) static int mts_nudged;
static volatile DWORD mts_drawn_at;            /* when the game's overlay last called back */
static float mts_scale = 1.0f;
#define S(x) ((int)((x) * mts_scale + 0.5f))

/* one way of drawing: a filled box, and words in a box (size in pixels; wrap 1 breaks lines, 0 keeps one line) */
typedef struct {
    void (*box)(void *to, int x, int y, int w, int h, COLORREF c);
    void (*words)(void *to, const char *t, int x, int y, int w, int h, COLORREF c, int size, int wrap);
    void *to;
} MtsPen;

static void mts_row(const MtsPen *p, int r, int y, int w) {
    char v[48];
    int set = mts_rows[r].set, dial = mts_rows[r].dial, own = mts_rows[r].own;
    int sel = r == mts_sel, on = mts_want[set], h = S(30), x = own ? S(22) : S(44);
    COLORREF name = on ? RGB(244, 244, 244) : RGB(150, 154, 164);
    if (sel)
        p->box(p->to, S(8), y, w - S(16), h, RGB(44, 48, 58));
    p->words(p->to, own ? mts_sets[set].title : mts_dials[dial].title, x, y, w - x - S(270), h, name, S(17), 0);
    if (dial) {
        snprintf(v, sizeof v, sel ? "<  %.2f  >" : "%.2f", (double)mts_dial_value[dial]);
        p->words(p->to, v, w - S(250), y, S(140), h, on ? RGB(255, 210, 74) : RGB(150, 154, 164), S(17), 0);
    } else if (own && mts_ran[set]) {
        snprintf(v, sizeof v, "used %u", (unsigned)mts_ran[set]);
        p->words(p->to, v, w - S(250), y, S(140), h, RGB(120, 124, 134), S(14), 0);
    }
    if (own)
        p->words(p->to, on ? "ON" : "OFF", w - S(78), y, S(60), h, on ? RGB(64, 200, 110) : RGB(120, 124, 134), S(17), 0);
}

static int mts_shown(void) {
    return MTS_ROWS < MTS_SHOWN ? MTS_ROWS : MTS_SHOWN;
}

static int mts_height(void) {
    return mts_open ? S(48) + mts_shown() * S(32) + S(112) : S(46);
}

static void mts_draw(const MtsPen *p, int w, int h) {
    char line[96];
    int i, y, set = mts_rows[mts_sel].set;
    p->box(p->to, 0, 0, w, h, RGB(16, 18, 23));
    p->box(p->to, 0, 0, w, S(3), RGB(226, 55, 68));
    if (!mts_open) {                                  /* closed: one line saying what F2 or F3 just did */
        mts_row(p, mts_sel, S(9), w);
        return;
    }
    p->words(p->to, "CODE MODS", S(22), S(8), S(300), S(34), RGB(244, 244, 244), S(17), 0);
    snprintf(line, sizeof line, "%d of %d", mts_sel + 1, MTS_ROWS);
    p->words(p->to, line, w - S(110), S(8), S(90), S(34), RGB(120, 124, 134), S(14), 0);
    y = S(46);
    for (i = mts_top; i < MTS_ROWS && i < mts_top + MTS_SHOWN; i++, y += S(32))
        mts_row(p, i, y, w);
    y = S(46) + mts_shown() * S(32);
    p->box(p->to, S(22), y + S(6), w - S(44), 1, RGB(48, 52, 62));
    p->words(p->to, mts_sets[set].about, S(22), y + S(14), w - S(44), S(40), RGB(184, 190, 202), S(14), 1);
    if (mts_ran[set])
        snprintf(line, sizeof line, "Its code has run %u times since the game started.", (unsigned)mts_ran[set]);
    else
        snprintf(line, sizeof line, "%s", mts_want[set] ? "On, and its code has not run yet." : "Off.");
    p->words(p->to, line, S(22), y + S(58), w - S(44), S(20), RGB(120, 124, 134), S(14), 0);
    p->words(p->to, "F4 close     Up / Down move     Enter on / off     Left / Right change", S(22), y + S(82),
             w - S(44), S(22), RGB(120, 124, 134), S(14), 0);
}

static void mts_measure(HWND game) {                  /* the panel keeps its size on the picture, 4K or 720p */
    RECT rc;
    if (game && GetClientRect(game, &rc) && rc.bottom >= 200) {
        mts_scale = rc.bottom / 1080.0f;
        if (mts_scale < 0.75f)
            mts_scale = 0.75f;
    }
}

{FX}
/* ---- drawn by the game's overlay */
#if MTS_SEAMS
static void *mts_hooked;                              /* the overlay's context the callback is on */

static void mts_ig_box(void *to, int x, int y, int w, int h, COLORREF c) {
    float a[2] = {(float)(S(36) + x), (float)(S(36) + y)}, b[2] = {a[0] + w, a[1] + h};
    mts_ig_rect(to, a, b, 0xF4000000u | (uint32_t)c, 0.0f, 0);
}

static void mts_ig_words(void *to, const char *t, int x, int y, int w, int h, COLORREF c, int size, int wrap) {
    float at[2] = {(float)(S(36) + x), (float)(S(36) + y) + (wrap ? 0.0f : (h - size) * 0.5f - 1.0f)};
    float clip[4] = {(float)(S(36) + x), (float)(S(36) + y), (float)(S(36) + x + w), (float)(S(36) + y + h)};
    if (t && t[0])
        mts_ig_text(to, NULL, (float)size, at, 0xFF000000u | (uint32_t)c, t, NULL, wrap ? (float)w : 0.0f, clip);
}

static void mts_ig_frame(void *ctx, void *hook) {     /* the overlay's thread, once for every frame it lays out */
    MtsPen pen = {mts_ig_box, mts_ig_words, NULL};
    (void)ctx;
    (void)hook;
    mts_drawn_at = GetTickCount();
    mts_fx_frame();
    if (!mts_open && !mts_toast)
        return;
    pen.to = mts_ig_front();
    if (!pen.to)
        return;
    mts_measure(gfx_window_handle());
    mts_draw(&pen, S(640), mts_height());
    mts_seen[1]++;
}

static void mts_hook(void) {                          /* asks the overlay to call back; again if it was rebuilt */
    void *ctx = mts_ig_context();
    if (ctx && ctx != mts_hooked) {
        MtsHook hook = {0, 1 /* after NewFrame */, 0, mts_ig_frame, NULL};
        mts_ig_add_hook(ctx, &hook);
        mts_hooked = ctx;
    }
}
#endif

static int mts_game_draws(void) {                     /* the overlay called back within the last third of a second */
    return mts_drawn_at && GetTickCount() - mts_drawn_at < 350;
}

/* ---- drawn as a window on top of the game */
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

static void mts_gdi_box(void *to, int x, int y, int w, int h, COLORREF c) {
    RECT r = {x, y, x + w, y + h};
    HBRUSH b = CreateSolidBrush(c);
    FillRect((HDC)to, &r, b);
    DeleteObject(b);
}

static void mts_gdi_words(void *to, const char *t, int x, int y, int w, int h, COLORREF c, int size, int wrap) {
    RECT r = {x, y, x + w, y + h};
    HFONT f = CreateFontA(-size, 0, 0, 0, size >= S(16) ? FW_SEMIBOLD : FW_NORMAL, 0, 0, 0, DEFAULT_CHARSET, 0, 0,
                          CLEARTYPE_QUALITY, 0, "Segoe UI");
    HFONT was = (HFONT)SelectObject((HDC)to, f);
    SetBkMode((HDC)to, TRANSPARENT);
    SetTextColor((HDC)to, c);
    DrawTextA((HDC)to, t, -1, &r, (wrap ? DT_WORDBREAK : DT_SINGLELINE | DT_VCENTER) | DT_END_ELLIPSIS | DT_NOPREFIX);
    SelectObject((HDC)to, was);
    DeleteObject(f);
}

static LRESULT CALLBACK mts_proc(HWND w, UINT m, WPARAM a, LPARAM b) {
    if (m == WM_PAINT) {
        PAINTSTRUCT ps;
        RECT r;
        HDC dc = BeginPaint(w, &ps), mem;
        HBITMAP bmp, old;
        MtsPen pen = {mts_gdi_box, mts_gdi_words, NULL};
        GetClientRect(w, &r);
        mem = CreateCompatibleDC(dc);                 /* drawn off screen first, so the panel never flickers */
        bmp = CreateCompatibleBitmap(dc, r.right, r.bottom);
        old = (HBITMAP)SelectObject(mem, bmp);
        pen.to = mem;
        mts_draw(&pen, r.right, r.bottom);
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

static void mts_hide(void) {
    if (mts_panel && IsWindowVisible(mts_panel))
        ShowWindow(mts_panel, SW_HIDE);
}

static void mts_show(void) {
    static int made;
    POINT at = {0, 0};
    if (mts_game_draws()) {                           /* the game is drawing the panel itself: no window needed */
        mts_hide();
        return;
    }
#if MTS_SEAMS
    if (mts_open && mts_waited < 16)
        return;                                       /* just opened: give the game's overlay half a second first */
#endif
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
    if (!mts_game)
        return;
    mts_measure(mts_game);
    if (!mts_panel) {
        mts_panel = CreateWindowExA(WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TRANSPARENT,
                                    "MtsCodeMods", "", WS_POPUP, 0, 0, 100, 100, NULL, NULL, GetModuleHandleA(NULL), NULL);
        if (!mts_panel)
            return;
        SetLayeredWindowAttributes(mts_panel, 0, 242, LWA_ALPHA);
    }
    ClientToScreen(mts_game, &at);
    if (!IsWindowVisible(mts_panel))
        mts_seen[2]++;
    SetWindowPos(mts_panel, HWND_TOPMOST, at.x + S(36), at.y + S(36), S(640), mts_height(), SWP_NOACTIVATE | SWP_SHOWWINDOW);
    InvalidateRect(mts_panel, NULL, FALSE);
    UpdateWindow(mts_panel);
}

static void mts_block(int on) {                       /* the game ignores its pad and keys while the panel is open */
#if MTS_SEAMS
    if (on != mts_blocked)
        input_block(on);
#endif
    mts_blocked = on;
}

static void mts_wake(int on) {
    /* on: the panel is up and the game's overlay is not drawing, so its fps readout is switched on to get it going.
       off: the readout goes back to off (it steps off, fps, full, so two more steps), unless an effect needs it. */
#if MTS_SEAMS
    if (!on && mts_fx_wanted())
        return;
    if (on && !mts_nudged && !mts_game_draws()) {
        menu_perf_cycle();
        mts_nudged = 1;
    } else if (!on && mts_nudged) {
        menu_perf_cycle();
        menu_perf_cycle();
        mts_nudged = 0;
    }
#else
    (void)on;
#endif
}

static void mts_switch(int r, int to) {              /* to: 0 off, 1 on, -1 the other way */
    int set = mts_rows[r].set, now = to < 0 ? !mts_want[set] : to;
    if (now == mts_want[set])
        return;
    mts_want[set] = mts_patch_on[set] = (uint8_t)now;
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
    if (!mts_want[mts_rows[r].set])
        mts_switch(r, 1);                             /* turning a dial is asking for the mod */
    else
        mts_save();
}

enum { K_MENU, K_NEXT, K_FLIP, K_UP, K_DOWN, K_LEFT, K_RIGHT, K_ENTER, K_WORKS, K_COUNT };

static DWORD WINAPI mts_keys(LPVOID unused) {
    static const int vk[K_COUNT] = {VK_F4, VK_F2, VK_F3, VK_UP, VK_DOWN, VK_LEFT, VK_RIGHT, VK_RETURN, VK_F6};
    int was[K_COUNT] = {0}, held[K_COUNT] = {0}, tick = 0, i;
    unsigned last = 0;
    (void)unused;
#if MTS_SEAMS
    mts_fx_init();
#endif
    for (;;) {
        MSG msg;
        DWORD pid = 0;
        int hit[K_COUNT], any = 0;
        while (PeekMessageA(&msg, NULL, 0, 0, PM_REMOVE)) {
            TranslateMessage(&msg);
            DispatchMessageA(&msg);
        }
        Sleep(30);
#if MTS_SEAMS
        mts_hook();
#endif
        if (!(++tick % 100)) {                        /* about every three seconds: what has run, for the log */
            unsigned sum = mts_seen[0] * 7u + mts_seen[2] + mts_seen[1] / 600u;
            for (i = 0; i < MTS_SETS; i++)
                sum = sum * 31u + mts_ran[i] + mts_want[i];
            if (sum != last) {
                last = sum;
                mts_write_log();
            }
        }
        GetWindowThreadProcessId(GetForegroundWindow(), &pid);
        if (pid != GetCurrentProcessId()) {           /* another program is in front: no keys, no panel */
            memset(was, 0, sizeof was);
            memset(held, 0, sizeof held);
            mts_hide();
            continue;
        }
#if MTS_SEAMS
        if (menu_is_open()) {                         /* the game's own F1 menu is up: it has the screen and the input */
            if (mts_open) {
                mts_open = 0;
                mts_blocked = 0;                      /* its closing gives the input back */
                mts_wake(0);
            }
            mts_toast = 0;
            mts_hide();
            memset(was, 0, sizeof was);
            continue;
        }
#endif
        for (i = 0; i < K_COUNT; i++) {
            int down = (GetAsyncKeyState(vk[i]) & 0x8000) != 0;
            held[i] = down ? held[i] + 1 : 0;
            hit[i] = (down && !was[i]) || (i >= K_UP && i <= K_RIGHT && held[i] > 14 && !(held[i] % 3));   /* held: repeats */
            was[i] = down;
            any |= hit[i];
        }
#if MTS_SEAMS
        mts_fx_tick(hit[K_WORKS]);
#endif
        if (mts_open) {
            /* who draws it is settled a moment after it opens: the game's overlay if it is calling back, woken up if
               it was asleep, and the window on top of the game if neither gets a frame */
            if (++mts_waited == 8)
                mts_wake(1);
            if (mts_waited >= 16 && (mts_waited % 8) == 0)
                mts_show();
        }
        if (!any) {
            if (!mts_open && mts_toast && !--mts_toast)
                mts_hide();
            continue;
        }
        if (hit[K_MENU]) {
            mts_open = !mts_open;
            mts_toast = 0;
            mts_waited = 0;
            mts_block(mts_open);
            Beep(mts_open ? 880 : 587, 40);
            if (mts_open) {
                mts_seen[0]++;
            } else {
                mts_hide();
                mts_wake(0);
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
        mts_want[i] = mts_patch_on[i] = (uint8_t)(mts_sets[i].def != 0);
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
                    mts_want[i] = mts_patch_on[i] = (uint8_t)(eq[1] == '1');
                    mts_from[i] = "{SWITCH_FILE}";
                }
        }
        fclose(f);
    }
    for (i = 0; i < MTS_SETS; i++) {
        const char *v = getenv(mts_sets[i].env);
        if (v && v[0]) {
            mts_want[i] = mts_patch_on[i] = (uint8_t)(v[0] == '1');
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
