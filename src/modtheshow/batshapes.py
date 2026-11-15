"""Reshape the game bat (NSW/OBJECTS/G4GAMEBAT) into other kinds of bat.

Every bat mesh keeps its topology and UVs, so the game's bat textures, logos and grip
tape still line up. Each bat is scaled around its long axis (z) to a new radius
profile, and its tape grips follow the same scale. Normals are transformed with the
inverse transpose of the deformation, so lighting stays right.
"""
import numpy as np

BAT = 'NSW/OBJECTS/G4GAMEBAT.MOD'
IN = 1 / 12.0      # the bat model is in feet

# radius in inches along the bat, knob (0) to end cap (1)
PRESETS = {
    'Wiffle Bat': ([0.0, 0.012, 0.03, 0.045, 0.40, 0.62, 0.95, 0.985, 1.0],
                   [0.62, 0.70, 0.62, 0.48, 0.50, 0.74, 0.76, 0.66, 0.30]),
    'Big Barrel Toy Bat': ([0.0, 0.015, 0.04, 0.06, 0.32, 0.55, 0.93, 0.98, 1.0],
                           [0.80, 0.90, 0.80, 0.62, 0.66, 1.75, 1.95, 1.70, 0.60]),
    'Fungo Bat': ([0.0, 0.012, 0.03, 0.05, 0.45, 0.72, 0.96, 0.99, 1.0],
                  [0.62, 0.68, 0.58, 0.44, 0.47, 0.88, 0.98, 0.88, 0.40]),
}

GROUPS = [('bat', ['batGrip_Cross', 'batGrip_spiral']),
          ('bat_Axe', ['batGrip_Cross_Axe', 'batGrip_spiral_Axe']),
          ('bat_noCup', []), ('bat_college', []), ('bat_collegeRing', []), ('bat_Torpedo', [])]


def _profile(p):
    z, r = p[:, 2], np.hypot(p[:, 0], p[:, 1])
    bins = np.linspace(z.min(), z.max(), 160)
    idx = np.clip(np.digitize(z, bins) - 1, 0, len(bins) - 2)
    rmax = np.zeros(len(bins) - 1)
    np.maximum.at(rmax, idx, r)
    zc = (bins[:-1] + bins[1:]) / 2
    ok = rmax > 1e-4
    rmax = np.interp(zc, zc[ok], rmax[ok])
    rmax = np.convolve(np.pad(rmax, 2, mode='edge'), np.ones(5) / 5, 'valid')
    return zc, rmax


def _reshape(ed, i, prof, z0, z1, preset, thickness):
    xs, rs = PRESETS[preset]
    zc, r0 = prof
    target = np.interp(np.clip((zc - z0) / (z1 - z0), 0, 1), xs, rs) * IN * thickness
    f_bins = target / np.maximum(r0, 1e-4)
    df_bins = np.gradient(f_bins, zc)
    pos = ed.get(i, 'POSITION')
    p = pos[:, :3]
    f = np.interp(p[:, 2], zc, f_bins)
    df = np.interp(p[:, 2], zc, df_bins)
    new = pos.copy()
    new[:, 0] *= f
    new[:, 1] *= f
    ed.put(i, 'POSITION', new)
    n = ed.get(i, 'NORMAL')
    if n is not None:
        n2 = n.copy()
        v = np.stack([n[:, 0] / f, n[:, 1] / f, n[:, 2] - df * (p[:, 0] * n[:, 0] + p[:, 1] * n[:, 1]) / f], 1)
        v /= np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9)
        n2[:, :3] = v
        ed.put(i, 'NORMAL', n2)


def apply(editor, preset, thickness=1.0):
    """Reshape every bat in an Editor opened on G4GAMEBAT."""
    names = {d['name']: i for i, d in enumerate(editor.mdl.draws)}
    for bat, grips in GROUPS:
        if bat not in names:
            continue
        bi = names[bat]
        p = editor.get(bi, 'POSITION')[:, :3]
        z0, z1 = p[:, 2].min(), p[:, 2].max()
        prof = _profile(p)
        for g in grips:
            if g in names:
                _reshape(editor, names[g], prof, z0, z1, preset, thickness)
        _reshape(editor, bi, prof, z0, z1, preset, thickness)
