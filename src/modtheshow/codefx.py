"""The C for the manager's own effects, drawn over the game by the game's overlay: fire on the ball, fireworks, and
the streaks that set them off. It goes into the in-game menu's source (codemenu.MENU) when the menu is joined to the
game, because it draws with the same Dear ImGui the menu does.

Nothing here is the game's art or the game's effects. The flames, smoke, embers and fireworks are particles this file
simulates in the game's own space (feet, the way the game measures the field) and draws as soft discs, every frame.

What it reads from the game, all of it looked up in MLB The Show 26 1.0.15 (Switch):
  the ball        handed over by the code mod itself: its site sits at the start of the routine that releases the ball
                  (main+0x166a2a4), where the ball is in x0, and copies it to x16 for mts_tap. The ball's object on the
                  field hangs off it at +0x560, and that object's place in the world is three floats at +0xe0.
  the camera      a pointer at main+0x28f51f8 (the table's #global camera line; another game version has it somewhere
                  else and the manager looks it up). Its matrix is at +0x110 (rows: right, up, forward, where it stands) and
                  its two projection scales at +0x500. main+0x119e918 is the game's own world-to-screen routine and
                  this does the same sum: a point p is at  d = p - where the camera stands,  x = right.d, y = up.d,
                  z = forward.d,  in front of the camera when z > 0, and on screen at
                  (0.5 - 0.5 * scale_x * x / z,  0.5 - 0.5 * scale_y * y / z)  of the picture, from the top left.
  a swing         the On Fire and Fireworks mods each have a site on the routine every swing goes through
                  (main+0x167a6ac); how often it ran is how many swings there have been.
The field is measured from the pitching rubber: +z is towards the plate (60.5), +y is up, and a ball is let go around
z = 9. Speeds are feet per second, 1.4667 to the mph.
"""

FX = r"""
/* ================= effects: the manager's own particles, drawn over the game ================= */
#if MTS_SEAMS
#include <math.h>
#if defined(__has_include)
#if __has_include("layout.h")
#include "layout.h"
#elif __has_include("../layout.h")
#include "../layout.h"
#endif
#endif
#ifndef MOD_MAIN_BASE
#define MOD_MAIN_BASE 0x7000000000ull
#endif
#define MTS_G_CAMERA {G_CAMERA}                       /* in main: a pointer to the camera the game is showing; 0 unknown */
#define G_CAMERA (MOD_MAIN_BASE + MTS_G_CAMERA)
#define CAM_MATRIX 0x110                             /* right, up, forward, where it stands: four rows of four floats */
#define CAM_SCALE 0x500                              /* the projection's two scales */
#define BALL_NODE 0x560                              /* from the ball to its object on the field */
#define NODE_POS 0xe0                                /* that object's place: x, y, z in feet */
#define BALL_MPH 0x454                               /* two floats: the pitch's speed in mph; the first wins when set */
#define FPS_PER_MPH 1.4667f

extern void *mts_ig_back(void) __asm__("_ZN5ImGui21GetBackgroundDrawListEv");
extern void *mts_ig_viewport(void) __asm__("_ZN5ImGui15GetMainViewportEv");
extern void mts_ig_disc(void *list, const float *at, float r, uint32_t col, int parts)
    __asm__("_ZN10ImDrawList15AddCircleFilledERK6ImVec2fji");
extern void mts_ig_stroke(void *list, const float *a, const float *b, uint32_t col, float thick)
    __asm__("_ZN10ImDrawList7AddLineERK6ImVec2S2_jf");

enum { P_FLAME, P_SMOKE, P_EMBER, P_SPARK, P_FLASH };
typedef struct { float p[3], v[3], age, life, size, heat; uint8_t kind, tint, live; } MtsBit;
#define MTS_BITS 1200
static MtsBit mts_bits[MTS_BITS];
static int mts_bit_next;
typedef struct { float right[3], up[3], fwd[3], at[3], sx, sy; } MtsCam;

static struct {
    int set_fire, set_streak, set_works;             /* where the three mods are in the table, -1 when absent */
    int dial_from, dial_works, dial_speed, dial_break, dial_ev, set_speed, set_break, set_ev;
    uint64_t ball, node;
    float pos[3], vel[3], speed, top;                /* the ball now; top: the fastest it has been on this flight */
    float was[6][3], said;                           /* its last few places, and the mph the game gave this pitch */
    double was_at[6], moved_at, now;
    int was_n;
    int have_pos, pitch, burning, flights, lit;
    float away;                                      /* fastest the ball has left the plate since the last swing, mph */
    unsigned swings;
    double swing_at;
    int waiting, whiffs, hards, hot_arm, hot_bats;
    double hot_since, banner_until;
    const char *banner;
    volatile int ask_works;                          /* F6 */
    unsigned frames, cam_ok;
    float seen[3];                                   /* where the ball last was on screen (0..1) and how far off */
    float shown[3];                                  /* where the ball is this frame, between the game's own steps */
    float cam_at[3], cam_scale[2];
    uint32_t rng;
} fx = {.set_fire = -1, .set_streak = -1, .set_works = -1, .set_speed = -1, .set_break = -1, .set_ev = -1};

static int mts_peek(uint64_t at, void *out, size_t n) {      /* a bad pointer reads as nothing instead of a crash */
    SIZE_T got = 0;
    if (at < 0x10000ull)
        return 0;
    return ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(uintptr_t)at, out, n, &got) && got == n;
}

static float mts_rand(void) {                                /* 0..1 */
    fx.rng ^= fx.rng << 13;
    fx.rng ^= fx.rng >> 17;
    fx.rng ^= fx.rng << 5;
    return (fx.rng & 0xFFFFFF) / 16777216.0f;
}

static float mts_spread(void) { return mts_rand() * 2.0f - 1.0f; }

static int mts_set_named(const char *name) {
    int i;
    for (i = 0; i < MTS_SETS; i++)
        if (!strcmp(mts_sets[i].name, name))
            return i;
    return -1;
}

static int mts_dial_named(const char *name) {
    int i;
    for (i = 1; i <= MTS_DIALS; i++)
        if (!strcmp(mts_dials[i].name, name))
            return i;
    return 0;
}

static int mts_wants(int set) { return set >= 0 && mts_want[set]; }

static int mts_fx_wanted(void) { return mts_wants(fx.set_fire) || mts_wants(fx.set_streak) || mts_wants(fx.set_works); }

static int mts_cam_read(MtsCam *c) {
    uint64_t cam = 0;
    float m[16], s[2];
    if (!MTS_G_CAMERA || !mts_peek(G_CAMERA, &cam, 8) || !mts_peek(cam + CAM_MATRIX, m, sizeof m) ||
        !mts_peek(cam + CAM_SCALE, s, sizeof s))
        return 0;
    memcpy(c->right, m, 12);
    memcpy(c->up, m + 4, 12);
    memcpy(c->fwd, m + 8, 12);
    memcpy(c->at, m + 12, 12);
    c->sx = s[0];
    c->sy = s[1];
    return s[0] == s[0] && s[1] == s[1] && fabsf(s[0]) > 0.05f && fabsf(s[0]) < 50.0f && fabsf(s[1]) > 0.05f && fabsf(s[1]) < 50.0f;
}

/* a point in the world to the picture: out[0], out[1] are 0..1 from the top left, out[2] how far in front. 0 when it
   is behind the camera. */
static int mts_cam_see(const MtsCam *c, const float *p, float *out) {
    float d[3] = {p[0] - c->at[0], p[1] - c->at[1], p[2] - c->at[2]};
    float x = c->right[0] * d[0] + c->right[1] * d[1] + c->right[2] * d[2];
    float y = c->up[0] * d[0] + c->up[1] * d[1] + c->up[2] * d[2];
    float z = c->fwd[0] * d[0] + c->fwd[1] * d[1] + c->fwd[2] * d[2];
    if (!(z > 0.3f))
        return 0;
    out[0] = 0.5f - 0.5f * c->sx * x / z;
    out[1] = 0.5f - 0.5f * c->sy * y / z;
    out[2] = z;
    return 1;
}

static MtsBit *mts_bit(int kind, const float *p, float life, float size) {
    MtsBit *b = &mts_bits[mts_bit_next];
    mts_bit_next = (mts_bit_next + 1) % MTS_BITS;
    memset(b, 0, sizeof *b);
    memcpy(b->p, p, 12);
    b->kind = (uint8_t)kind;
    b->life = life;
    b->size = size;
    b->live = 1;
    return b;
}

/* ---- fire: what a burning ball gives off between where it was and where it is, over dt seconds */
static void mts_burn(const float *from, const float *to, const float *vel, float dt, float heat, int tint) {
    float n = dt * heat, k;
    int flames = (int)(n * 560.0f + mts_rand()), smoke = (int)(n * 70.0f + mts_rand()), embers = (int)(n * 60.0f + mts_rand());
    int i, j;
    if (flames > 70) flames = 70;
    if (smoke > 10) smoke = 10;
    if (embers > 10) embers = 10;
    for (i = 0; i < flames + smoke + embers; i++) {
        float at[3];
        MtsBit *b;
        k = mts_rand();
        for (j = 0; j < 3; j++)
            at[j] = from[j] + (to[j] - from[j]) * k;
        if (i < flames) {
            b = mts_bit(P_FLAME, at, 0.14f + 0.2f * mts_rand(), (0.22f + 0.2f * mts_rand()) * (0.8f + 0.25f * heat));
            for (j = 0; j < 3; j++)
                b->v[j] = vel[j] * 0.10f + mts_spread() * 2.6f;
        } else if (i < flames + smoke) {
            b = mts_bit(P_SMOKE, at, 0.8f + 0.7f * mts_rand(), 0.5f + 0.3f * mts_rand());
            for (j = 0; j < 3; j++)
                b->v[j] = vel[j] * 0.03f + mts_spread() * 1.4f;
        } else {
            b = mts_bit(P_EMBER, at, 0.35f + 0.5f * mts_rand(), 0.045f + 0.03f * mts_rand());
            for (j = 0; j < 3; j++)
                b->v[j] = vel[j] * 0.22f + mts_spread() * 10.0f;
        }
        b->heat = heat;
        b->tint = (uint8_t)tint;
    }
}

/* ---- fireworks: one shell bursting at a place in the world */
static void mts_shell(const float *at, int tint) {
    int i, j, n = 110;
    MtsBit *b = mts_bit(P_FLASH, at, 0.22f, 26.0f);
    b->tint = (uint8_t)tint;
    for (i = 0; i < n; i++) {
        float d[3], len, speed = 70.0f + 60.0f * mts_rand();
        do {                                                 /* a direction, evenly over the sphere */
            for (j = 0; j < 3; j++)
                d[j] = mts_spread();
            len = d[0] * d[0] + d[1] * d[1] + d[2] * d[2];
        } while (len > 1.0f || len < 0.01f);
        len = sqrtf(len);
        b = mts_bit(P_SPARK, at, 1.3f + 0.8f * mts_rand(), 2.2f + 1.4f * mts_rand());
        for (j = 0; j < 3; j++)
            b->v[j] = d[j] / len * speed;
        b->tint = (uint8_t)tint;
    }
}

static void mts_fireworks(const MtsCam *c, int shells) {     /* up where the camera is looking, and they stay there */
    float right = c->sx < 0 ? 1.0f : -1.0f, up = c->sy > 0 ? 1.0f : -1.0f;
    int i, j;
    for (i = 0; i < shells; i++) {
        float far_ = 300.0f + 160.0f * mts_rand(), at[3];
        float side = mts_spread() * 0.7f * far_ / fabsf(c->sx), high = (0.25f + 0.55f * mts_rand()) * far_ / fabsf(c->sy);
        for (j = 0; j < 3; j++)
            at[j] = c->at[j] + c->fwd[j] * far_ + c->right[j] * right * side + c->up[j] * up * high;
        mts_shell(at, 1 + (int)(mts_rand() * 5.99f));
    }
}

/* ---- every frame: move the particles and draw them, far ones first enough (smoke, then light) */
static uint32_t mts_tone(const MtsBit *b, float t, float *alpha) {
    static const uint8_t fire[5][3] = {{255, 246, 214}, {255, 206, 74}, {255, 130, 28}, {214, 52, 18}, {70, 26, 20}};
    static const uint8_t cold[5][3] = {{236, 250, 255}, {150, 220, 255}, {60, 150, 255}, {40, 70, 220}, {30, 30, 90}};
    static const uint8_t works[7][3] = {{255, 255, 255}, {255, 208, 90}, {255, 70, 60}, {90, 220, 255}, {120, 255, 140},
                                        {255, 110, 230}, {255, 255, 255}};
    const uint8_t (*ramp)[3] = b->tint == 9 ? cold : fire;
    float r, g, bl;
    if (b->kind == P_SMOKE) {
        float v = 46.0f + 40.0f * t;
        *alpha = 0.30f * (1.0f - t) * (t < 0.15f ? t / 0.15f : 1.0f);
        return ((uint32_t)v << 16) | ((uint32_t)v << 8) | (uint32_t)v;
    }
    if (b->kind == P_SPARK || b->kind == P_FLASH) {
        const uint8_t *c = works[b->tint % 7];
        float fade = b->kind == P_FLASH ? 1.0f - t : (t < 0.7f ? 1.0f : (1.0f - t) / 0.3f);
        float white = b->kind == P_FLASH ? 0.6f : (t < 0.12f ? 1.0f - t / 0.12f : 0.0f);
        *alpha = fade * (b->kind == P_FLASH ? 0.5f : 0.95f);
        r = c[0] + (255 - c[0]) * white;
        g = c[1] + (255 - c[1]) * white;
        bl = c[2] + (255 - c[2]) * white;
        return ((uint32_t)bl << 16) | ((uint32_t)g << 8) | (uint32_t)r;
    }
    {
        float f = (b->kind == P_EMBER ? 0.25f + t * 0.75f : t) * 4.0f;
        int i = (int)f;
        if (i > 3) i = 3;
        f -= i;
        r = ramp[i][0] + (ramp[i + 1][0] - ramp[i][0]) * f;
        g = ramp[i][1] + (ramp[i + 1][1] - ramp[i][1]) * f;
        bl = ramp[i][2] + (ramp[i + 1][2] - ramp[i][2]) * f;
        *alpha = b->kind == P_EMBER ? 1.0f - t * t : (t < 0.1f ? t / 0.1f : 1.0f - (t - 0.1f) / 0.9f) * 0.5f;
    }
    return ((uint32_t)bl << 16) | ((uint32_t)g << 8) | (uint32_t)r;
}

/* A disc that fades out towards its edge: rings laid over each other, each a little smaller, so the middle is the
   sum of them all. alpha is how solid the middle ends up. */
static void mts_soft(void *list, const float *at, float r, uint32_t rgb, float alpha, int fine) {
    int i, rings;
    float each;
    if (alpha <= 0.01f)
        return;
    if (alpha > 1.0f) alpha = 1.0f;
    if (r > 420.0f) r = 420.0f;
    if (r < 3.0f) {
        mts_ig_disc(list, at, r < 1.0f ? 1.0f : r, ((uint32_t)(alpha * 0.85f * 255.0f) << 24) | rgb, 8);
        return;
    }
    rings = fine ? (r < 40.0f ? 6 : 9) : r < 60.0f ? 3 : 4;  /* hundreds of flames overlap; the glow stands alone */
    each = 1.0f - powf(1.0f - alpha * 0.98f, 1.0f / rings);  /* so the rings add up to alpha in the middle */
    for (i = 0; i < rings; i++)
        mts_ig_disc(list, at, r * (1.0f - (float)i / rings * 0.86f), ((uint32_t)(each * 255.0f + 0.5f) << 24) | rgb,
                    r < 8.0f ? 10 : 0);
}

static void mts_bits_step(void *list, const MtsCam *c, float w, float h, float dt) {
    int pass, i, j;
    for (pass = 0; pass < 2; pass++)
        for (i = 0; i < MTS_BITS; i++) {
            MtsBit *b = &mts_bits[i];
            float see[3], at[2], t, alpha, px, grow;
            uint32_t rgb;
            if (!b->live || (b->kind == P_SMOKE) != (pass == 0))      /* smoke first, the light over it */
                continue;
            {
                float lift = b->kind == P_FLAME ? 15.0f : b->kind == P_SMOKE ? 5.0f : b->kind == P_FLASH ? 0.0f : -24.0f;
                float drag = b->kind == P_FLAME ? 3.5f : b->kind == P_SMOKE ? 1.8f : b->kind == P_SPARK ? 1.5f : 0.9f;
                b->age += dt;
                if (b->age >= b->life) {
                    b->live = 0;
                    continue;
                }
                b->v[1] += lift * dt;
                if (b->kind == P_FLAME || b->kind == P_SMOKE) {      /* the air is never still: a slow swirl */
                    b->v[0] += sinf(b->age * 19.0f + i * 1.7f) * 9.0f * dt;
                    b->v[2] += cosf(b->age * 16.0f + i * 2.3f) * 9.0f * dt;
                }
                for (j = 0; j < 3; j++) {
                    b->v[j] -= b->v[j] * drag * dt;
                    b->p[j] += b->v[j] * dt;
                }
            }
            if (!c || !mts_cam_see(c, b->p, see))
                continue;
            t = b->age / b->life;
            px = 0.5f * fabsf(c->sy) * h / see[2];             /* pixels to the foot at that distance */
            at[0] = see[0] * w;
            at[1] = see[1] * h;
            if (at[0] < -200.0f || at[0] > w + 200.0f || at[1] < -200.0f || at[1] > h + 200.0f)
                continue;
            rgb = mts_tone(b, t, &alpha);
            grow = b->kind == P_FLAME ? 0.7f + 1.5f * t - 1.3f * t * t : b->kind == P_SMOKE ? 1.0f + 2.6f * t :
                   b->kind == P_FLASH ? 0.4f + 1.6f * t : b->kind == P_SPARK ? 1.0f - 0.5f * t : 1.0f;
            if (b->kind == P_EMBER || b->kind == P_SPARK) {  /* a streak along the way it is going, then its head */
                float back[3], tail[3], to[2];
                float len = b->kind == P_SPARK ? 0.05f : 0.03f;
                for (j = 0; j < 3; j++)
                    back[j] = b->p[j] - b->v[j] * len;
                if (mts_cam_see(c, back, tail)) {
                    float thick = b->size * grow * px * (b->kind == P_SPARK ? 0.5f : 1.1f);
                    to[0] = tail[0] * w;
                    to[1] = tail[1] * h;
                    if (thick < 1.2f) thick = 1.2f;
                    if (thick > 14.0f) thick = 14.0f;
                    mts_ig_stroke(list, to, at, ((uint32_t)(alpha * 0.6f * 255.0f) << 24) | rgb, thick);
                }
            }
            mts_soft(list, at, b->size * grow * px * (b->kind == P_SPARK ? 0.5f : b->kind == P_EMBER ? 0.7f : 1.0f), rgb, alpha,
                     b->kind == P_FLASH);
        }
}

/* ---- the streaks */
static void mts_fx_dial(int set, int dial, float times) {    /* a mod's dial held at  its own value x times  while hot */
    float v;
    if (set < 0 || !dial)
        return;
    v = (mts_want[set] ? mts_dial_value[dial] : 1.0f) * times;
    mts_patch_on[set] = 1;
    memcpy(&mts_dial[dial], &v, sizeof v);
}

static void mts_fx_cool(int set, int dial) {                 /* and given back */
    if (set < 0 || !dial)
        return;
    mts_patch_on[set] = mts_want[set];
    memcpy(&mts_dial[dial], &mts_dial_value[dial], sizeof(float));
}

static void mts_fx_say(const char *words, double secs) {
    fx.banner = words;
    fx.banner_until = fx.now + secs;
}

static void mts_fx_swing(const MtsCam *c, int contact, float mph) {
    int streaks = mts_wants(fx.set_streak);
    float big = fx.dial_works ? mts_dial_value[fx.dial_works] : 108.0f;
    if (contact && mts_wants(fx.set_works) && mph >= big && c)
        mts_fireworks(c, 3);
    if (!streaks)
        return;
    if (!contact) {
        fx.whiffs++;
        fx.hards = 0;
        if (fx.hot_bats) {
            fx.hot_bats = 0;
            mts_fx_say("LINEUP COOLED OFF", 2.5);
        }
        if (fx.whiffs >= 3 && !fx.hot_arm) {
            fx.hot_arm = 1;
            fx.hot_since = fx.now;
            mts_fx_say("PITCHER ON FIRE", 4.0);
            if (c) mts_fireworks(c, 2);
        }
    } else {
        fx.whiffs = 0;
        if (fx.hot_arm) {
            fx.hot_arm = 0;
            mts_fx_say("PITCHER COOLED OFF", 2.5);
        }
        if (mph >= 98.0f) {
            if (++fx.hards >= 3 && !fx.hot_bats) {
                fx.hot_bats = 1;
                fx.hot_since = fx.now;
                mts_fx_say("LINEUP ON FIRE", 4.0);
                if (c) mts_fireworks(c, 2);
            }
        } else {
            fx.hards = 0;
            if (fx.hot_bats) {
                fx.hot_bats = 0;
                mts_fx_say("LINEUP COOLED OFF", 2.5);
            }
        }
    }
}

static void mts_fx_heat(void) {                              /* what being hot does, held for as long as it lasts */
    static int was_arm, was_bats;
    if (!mts_wants(fx.set_streak) || ((fx.hot_arm || fx.hot_bats) && fx.now - fx.hot_since > 420.0))
        fx.hot_arm = fx.hot_bats = fx.whiffs = fx.hards = 0;
    if (fx.hot_arm) {
        mts_fx_dial(fx.set_speed, fx.dial_speed, 1.12f);
        mts_fx_dial(fx.set_break, fx.dial_break, 1.5f);
    } else if (was_arm) {
        mts_fx_cool(fx.set_speed, fx.dial_speed);
        mts_fx_cool(fx.set_break, fx.dial_break);
    }
    if (fx.hot_bats)
        mts_fx_dial(fx.set_ev, fx.dial_ev, 1.25f);
    else if (was_bats)
        mts_fx_cool(fx.set_ev, fx.dial_ev);
    was_arm = fx.hot_arm;
    was_bats = fx.hot_bats;
    if (fx.set_fire >= 0)                                    /* the ball is followed whenever any effect wants it */
        mts_patch_on[fx.set_fire] = (uint8_t)mts_fx_wanted();
}

/* ---- where the ball is, how fast, and whether it is a pitch on its way in */
static void mts_ball_step(float dt) {
    float p[3], d[3], dist;
    int j;
    (void)dt;
    fx.ball = fx.set_fire >= 0 ? mts_tapv[fx.set_fire] : 0;
    if (!fx.ball || !mts_peek(fx.ball + BALL_NODE, &fx.node, 8) || !mts_peek(fx.node + NODE_POS, p, sizeof p) ||
        !(p[0] == p[0] && p[1] == p[1] && p[2] == p[2])) {
        fx.have_pos = fx.pitch = fx.burning = 0;
        return;
    }
    if (!fx.have_pos) {
        memcpy(fx.pos, p, 12);
        fx.moved_at = fx.now;
        fx.have_pos = 1;
        return;
    }
    for (j = 0; j < 3; j++)
        d[j] = p[j] - fx.pos[j];
    dist = sqrtf(d[0] * d[0] + d[1] * d[1] + d[2] * d[2]);
    if (dist < 0.004f) {                                      /* the game has not moved it since the last look */
        if (fx.now - fx.moved_at > 0.25) {
            fx.speed = 0.0f;
            fx.vel[0] = fx.vel[1] = fx.vel[2] = 0.0f;
            fx.pitch = fx.burning = 0;
        }
        return;
    }
    if (dist > 30.0f || fx.now - fx.moved_at > 0.3) {        /* put somewhere else, not flown there: a new start */
        fx.speed = fx.top = fx.said = 0.0f;
        fx.vel[0] = fx.vel[1] = fx.vel[2] = 0.0f;
        fx.pitch = fx.burning = fx.was_n = 0;
    }
    /* The game moves the ball in steps and this looks once a frame, so one step's timing can be a frame out. The way
       it is going is taken over the last few steps instead. */
    memmove(fx.was + 1, fx.was, sizeof fx.was - sizeof fx.was[0]);
    memmove(fx.was_at + 1, fx.was_at, sizeof fx.was_at - sizeof fx.was_at[0]);
    memcpy(fx.was[0], p, 12);
    fx.was_at[0] = fx.now;
    if (fx.was_n < 6)
        fx.was_n++;
    if (fx.was_n >= 3) {
        int old = fx.was_n - 1;
        float secs = (float)(fx.was_at[0] - fx.was_at[old]);
        if (secs > 0.001f) {
            for (j = 0; j < 3; j++)
                fx.vel[j] = (fx.was[0][j] - fx.was[old][j]) / secs;
            fx.speed = sqrtf(fx.vel[0] * fx.vel[0] + fx.vel[1] * fx.vel[1] + fx.vel[2] * fx.vel[2]);
        }
        if (fx.vel[2] > 60.0f && fx.vel[2] > 0.9f * fx.speed && p[2] > 2.0f && p[2] < 64.0f && fabsf(p[0]) < 8.0f) {
            if (!fx.pitch) {
                float mph[2] = {0.0f, 0.0f};
                fx.pitch = 1;
                fx.top = 0.0f;
                fx.flights++;
                mts_peek(fx.ball + BALL_MPH, mph, sizeof mph);
                fx.said = mph[0] > 0.0f ? mph[0] : mph[1];
                if (!(fx.said > 30.0f && fx.said < 135.0f))
                    fx.said = 0.0f;
                else if (fx.set_speed >= 0 && fx.dial_speed && mts_patch_on[fx.set_speed]) {
                    float times;                              /* the Pitch Speed mod is making it play faster */
                    memcpy(&times, &mts_dial[fx.dial_speed], sizeof times);
                    fx.said *= times;
                }
            }
        } else if (fx.pitch && (fx.vel[2] < 20.0f || p[2] >= 64.0f)) {
            fx.pitch = 0;
        }
        if (fx.speed > fx.top && fx.was_n >= 5)
            fx.top = fx.speed;
        if (fx.vel[2] < -8.0f && fx.speed / FPS_PER_MPH > fx.away)
            fx.away = fx.speed / FPS_PER_MPH;
    }
    memcpy(fx.pos, p, 12);
    fx.moved_at = fx.now;
}

static void mts_fx_frame(void) {                             /* the overlay's thread, once a frame */
    static LARGE_INTEGER freq, was;
    static int ready;
    LARGE_INTEGER t;
    MtsCam cam;
    const float *size;
    void *list, *view;
    float dt, w, h, last[3], est[3], gap = 0.0f;
    int have_cam, burn = 0, tint = 0, j;
    unsigned swings;
    if (!ready) {
        QueryPerformanceFrequency(&freq);
        QueryPerformanceCounter(&was);
        fx.rng = 0x9E3779B9u ^ (uint32_t)was.LowPart;
        fx.swings = (fx.set_streak >= 0 ? mts_ran[fx.set_streak] : 0) + (fx.set_works >= 0 ? mts_ran[fx.set_works] : 0);
        ready = 1;
        return;
    }
    QueryPerformanceCounter(&t);
    dt = (float)((double)(t.QuadPart - was.QuadPart) / (double)freq.QuadPart);
    was = t;
    fx.now += dt;
    if (dt > 0.1f) dt = 0.1f;
    mts_fx_heat();
    if (!mts_fx_wanted() && !fx.banner)
        return;
    list = mts_ig_back();
    view = mts_ig_viewport();
    if (!list || !view)
        return;
    size = (const float *)((const char *)view + 16);         /* ImGuiViewport: id, flags, pos, size */
    w = size[0];
    h = size[1];
    if (!(w > 100.0f && h > 100.0f))
        return;
    fx.frames++;
    have_cam = mts_cam_read(&cam);
    fx.cam_ok += (unsigned)have_cam;
    if (have_cam) {
        memcpy(fx.cam_at, cam.at, 12);
        fx.cam_scale[0] = cam.sx;
        fx.cam_scale[1] = cam.sy;
    }
    mts_ball_step(dt);
    /* the game moves the ball in steps; between them it is drawn a little further along the way it is going */
    memcpy(last, fx.shown, 12);
    for (j = 0; j < 3; j++) {
        float ahead = (float)(fx.now - fx.moved_at);
        est[j] = fx.pos[j] + fx.vel[j] * (ahead > 0.05f ? 0.05f : ahead);
        gap += (est[j] - last[j]) * (est[j] - last[j]);
    }
    memcpy(fx.shown, est, 12);
    if (gap > 14.0f * 14.0f)
        memcpy(last, est, 12);
    if (have_cam && fx.have_pos)
        mts_cam_see(&cam, est, fx.seen);

    /* a swing: was the ball hit? Known a moment later, from which way the ball is going. */
    swings = (fx.set_streak >= 0 ? mts_ran[fx.set_streak] : 0) + (fx.set_works >= 0 ? mts_ran[fx.set_works] : 0);
    if (swings != fx.swings) {
        fx.swings = swings;
        fx.swing_at = fx.now;
        fx.waiting = 1;
        fx.away = 0.0f;
    }
    if (fx.waiting && fx.now - fx.swing_at > 0.6) {
        fx.waiting = 0;
        mts_fx_swing(have_cam ? &cam : NULL, fx.away >= 12.0f, fx.away);
    }
    if (fx.ask_works) {
        fx.ask_works = 0;
        if (have_cam)
            mts_fireworks(&cam, 4);
    }

    /* does the ball burn right now? */
    if (fx.have_pos && fx.speed > 30.0f) {
        /* how fast: what the game gave the pitch, else what it has been seen doing */
        float from = fx.dial_from ? mts_dial_value[fx.dial_from] : 95.0f, mph = fx.said > 0.0f ? fx.said : fx.top / FPS_PER_MPH;
        if (fx.pitch && fx.hot_arm) {
            burn = 1;
            tint = 9;                                        /* a pitcher on fire throws blue flame */
        } else if (fx.pitch && mts_wants(fx.set_fire) && mph >= from - 0.5f) {
            burn = 1;
        } else if (!fx.pitch && fx.hot_bats && fx.vel[2] < 0.0f && fx.speed > 90.0f) {
            burn = 1;                                        /* a lineup on fire: the ball burns off the bat */
        }
        if (burn) {
            float heat = fx.hot_arm || fx.hot_bats ? 1.3f : 0.7f + (mph - from) / 14.0f;
            if (heat < 0.7f) heat = 0.7f;
            if (heat > 1.6f) heat = 1.6f;
            mts_burn(last, est, fx.vel, dt, heat, tint);
            if (!fx.burning)
                fx.lit++;
        }
    }
    fx.burning = burn;

    mts_bits_step(list, have_cam ? &cam : NULL, w, h, dt);
    if (burn && have_cam) {                                  /* the ball's own glow, over its flames */
        float see[3], at[2];
        if (mts_cam_see(&cam, est, see)) {
            float px = 0.5f * fabsf(cam.sy) * h / see[2], flick = 0.9f + 0.2f * mts_rand();
            at[0] = see[0] * w;
            at[1] = see[1] * h;
            mts_soft(list, at, 1.25f * px * flick, tint == 9 ? 0xFF9632u : 0x1E82FFu, 0.34f, 1);
            mts_soft(list, at, 0.55f * px * flick, tint == 9 ? 0xFFDC96u : 0x4ACEFFu, 0.6f, 1);
            mts_soft(list, at, 0.22f * px, 0xFFFFFFu, 0.9f, 1);
        }
    }
    if (fx.banner) {                                         /* the words, top centre */
        if (fx.now > fx.banner_until) {
            fx.banner = NULL;
        } else {
            float big = h / 1080.0f * 40.0f, wide = (float)strlen(fx.banner) * big * 0.52f;
            float left = fx.banner_until - (float)fx.now, a = left < 0.5f ? left / 0.5f : 1.0f;
            float at[2] = {(w - wide) * 0.5f, h * 0.085f}, lo[2] = {at[0] - big * 0.6f, at[1] - big * 0.25f};
            float hi[2] = {at[0] + wide + big * 0.6f, at[1] + big * 1.3f}, bar[2] = {lo[0], hi[1] - big * 0.12f};
            int cold = strstr(fx.banner, "PITCHER") != NULL, off = strstr(fx.banner, "COOLED") != NULL;
            uint32_t ink = off ? 0xC8C8C8u : cold ? 0xFFC850u : 0x32A0FFu;
            mts_ig_rect(list, lo, hi, ((uint32_t)(a * 200.0f) << 24) | 0x0C0C10u, big * 0.2f, 0);
            mts_ig_rect(list, bar, hi, ((uint32_t)(a * 255.0f) << 24) | ink, big * 0.06f, 0);
            mts_ig_text(list, NULL, big, at, ((uint32_t)(a * 255.0f) << 24) | 0xFFFFFFu, fx.banner, NULL, 0.0f, NULL);
        }
    }
}

static void mts_wake(int on);
static int mts_game_draws(void);

/* The effects are drawn on the frames the game's overlay lays out, and it lays none out while it has nothing of its
   own to show. So while an effect is wanted and no frames come, its fps readout is switched on, once. (F10 is that
   readout's own key: switching it off there puts the effects out with it, and on again brings them back.) */
static void mts_fx_tick(int f6) {                            /* the key thread, about thirty times a second */
    static int dry;
    if (f6 && mts_wants(fx.set_works)) {
        fx.ask_works = 1;
        Beep(1319, 40);
    }
    if (mts_fx_wanted()) {
        if (mts_game_draws() || !gfx_window_handle())        /* (not before the game has its window) */
            dry = 0;
        else if (++dry == 100)
            mts_wake(1);
    } else {
        dry = 0;
        if (!mts_open)
            mts_wake(0);
    }
}

static void mts_fx_log(FILE *f);

static void mts_fx_init(void) {                              /* once, when the key thread starts */
    fx.set_fire = mts_set_named("fireball");
    fx.set_streak = mts_set_named("on_fire");
    fx.set_works = mts_set_named("fireworks");
    fx.set_speed = mts_set_named("pitch_speed");
    fx.set_break = mts_set_named("pitch_break");
    fx.set_ev = mts_set_named("exit_velocity");
    fx.dial_from = mts_dial_named("fire_from");
    fx.dial_works = mts_dial_named("fireworks_from");
    fx.dial_speed = mts_dial_named("pitch_speed");
    fx.dial_break = mts_dial_named("pitch_break");
    fx.dial_ev = mts_dial_named("exit_velocity");
    mts_log_more = mts_fx_log;
}

static void mts_fx_log(FILE *f) {                            /* for telling what went wrong from one play session */
    fprintf(f, "fx frames=%u camera=%u ball=%s node=%s flights=%u lit=%u swings=%u\n", fx.frames, fx.cam_ok,
            fx.ball ? "found" : "none", fx.node ? "found" : "none", (unsigned)fx.flights, (unsigned)fx.lit, fx.swings);
    fprintf(f, "fx ball at %.1f %.1f %.1f going %.0f mph (fastest this flight %.0f, the game said %.0f), on screen at %.2f %.2f, %.0f ft off\n",
            (double)fx.pos[0], (double)fx.pos[1], (double)fx.pos[2], (double)(fx.speed / FPS_PER_MPH),
            (double)(fx.top / FPS_PER_MPH), (double)fx.said, (double)fx.seen[0], (double)fx.seen[1], (double)fx.seen[2]);
    fprintf(f, "fx camera at %.1f %.1f %.1f scale %.2f %.2f\n", (double)fx.cam_at[0], (double)fx.cam_at[1],
            (double)fx.cam_at[2], (double)fx.cam_scale[0], (double)fx.cam_scale[1]);
    fprintf(f, "fx streaks whiffs=%d hard=%d pitcher_hot=%d lineup_hot=%d\n", fx.whiffs, fx.hards, fx.hot_arm, fx.hot_bats);
}
#endif
"""
