"""MLB The Show 26 models (IFF0MODL).

A model is two files: NAME.MOD holds the description (vertex layout XML, mesh names,
materials, per-mesh draw records, bounds) and NAME.0.MOD holds the GPU buffers
(one VOID_VBO chunk per vertex stream and one VOID_EBO of 16-bit indices).

Every chunk is an 8-byte tag, a u32, a u32 size; the next chunk starts at
offset + 0x10 + size. Buffer data starts on a 256-byte boundary, is zero padded to
16 bytes and then filled with 0xAD up to the next chunk.

Static models (bats, balls, stadium props) are fully supported: read, export OBJ,
edit vertices in place, or replace a mesh with new geometry of any size.
Skinned models (shoes, gloves, pads) are listed but not editable yet.
"""
import re
import struct
import xml.etree.ElementTree as ET

import numpy as np

TAG = re.compile(rb'(VOID|INT0|STRG|CLAS|IFF0|SPHR)[A-Z0-9_]{4}')
PAD = 0xAD

# component format -> (bytes, kind). Packed 10:10:10:2 formats are handled per attribute.
SCALAR = {'kFloat_32': (4, 'f4'), 'kFloat_16': (2, 'f2'), 'kFP_0_0_8': (1, 'un8'),
          'kUInt_8': (1, 'u1'), 'kSInt_8': (1, 's1'), 'kUInt_16': (2, 'u2'), 'kSInt_16': (2, 's2'),
          'kFP_0_0_16': (2, 'un16'), 'kFP_1_0_15': (2, 'sn16'), 'kFP_1_0_7': (1, 'sn8')}
PACKED = {'kFP_1_0_9', 'kFP_0_0_10', 'kFP_0_0_2', 'kFP_1_0_1'}


class ModelError(Exception):
    pass


def chunks(d):
    out = {}
    for mm in TAG.finditer(d):
        o = mm.start()
        if o % 16:
            continue
        a, sz = struct.unpack_from('<II', d, o + 8)
        out.setdefault(mm.group().decode(), []).append((o, a, sz))
    return out


def _strings(d, o, sz):
    return [s.decode('latin1') for s in d[o + 0x10:o + 0x10 + sz].split(b'\0')
            if s and s.strip(b'\xad')]


# ------------------------------------------------------------------ layout
class Attribute:
    def __init__(self, name, semantic, comps, offset):
        self.name, self.semantic, self.comps, self.offset = name, semantic, comps, offset
        self.known = all(c in SCALAR or c in PACKED for c in comps)
        self.packed = comps[0] in PACKED
        self.size = (4 if self.packed else sum(SCALAR[c][0] for c in comps)) if self.known else 0
        self.base = semantic.rstrip('0123456789') if semantic else semantic

    def decode(self, buf, stride, n):
        raw = np.frombuffer(buf, np.uint8, n * stride).reshape(n, stride)[:, self.offset:self.offset + self.size]
        raw = np.ascontiguousarray(raw)
        if self.packed:
            v = raw.view('<u4')[:, 0]
            out = []
            for k, (c, shift, bits) in enumerate(zip(self.comps, (0, 10, 20, 30), (10, 10, 10, 2))):
                q = ((v >> shift) & ((1 << bits) - 1)).astype(np.int32)
                if c.startswith('kFP_1'):
                    half = 1 << (bits - 1)
                    q = np.where(q >= half, q - (1 << bits), q)
                    out.append(q / float(half - 1) if bits > 2 else q.astype(np.float32))
                else:
                    out.append(q / float((1 << bits) - 1) if bits > 2 else q.astype(np.float32))
            return np.stack(out, 1).astype(np.float32)
        cols, o = [], 0
        for c in self.comps:
            nb, kind = SCALAR[c]
            seg = raw[:, o:o + nb].copy()
            if kind == 'f4': x = seg.view('<f4')[:, 0]
            elif kind == 'f2': x = seg.view('<f2')[:, 0].astype(np.float32)
            elif kind == 'un8': x = seg[:, 0] / 255.0
            elif kind == 'sn8': x = np.maximum(seg.view(np.int8)[:, 0] / 127.0, -1)
            elif kind == 'u1': x = seg[:, 0].astype(np.float32)
            elif kind == 's1': x = seg.view(np.int8)[:, 0].astype(np.float32)
            elif kind == 'u2': x = seg.view('<u2')[:, 0].astype(np.float32)
            elif kind == 's2': x = seg.view('<i2')[:, 0].astype(np.float32)
            elif kind == 'un16': x = seg.view('<u2')[:, 0] / 65535.0
            elif kind == 'sn16': x = np.maximum(seg.view('<i2')[:, 0] / 32767.0, -1)
            cols.append(np.asarray(x, np.float32))
            o += nb
        return np.stack(cols, 1)

    def encode(self, values, out, stride):
        """Write float values (n, comps) into the interleaved uint8 array `out` (n, stride)."""
        v = np.asarray(values, np.float32)
        n = len(v)
        if self.packed:
            word = np.zeros(n, np.uint32)
            for k, (c, shift, bits) in enumerate(zip(self.comps, (0, 10, 20, 30), (10, 10, 10, 2))):
                x = v[:, k] if k < v.shape[1] else np.zeros(n, np.float32)
                if bits > 2:
                    if c.startswith('kFP_1'):
                        half = 1 << (bits - 1)
                        q = np.round(np.clip(x, -1, 1) * (half - 1)).astype(np.int32)
                    else:
                        q = np.round(np.clip(x, 0, 1) * ((1 << bits) - 1)).astype(np.int32)
                else:
                    q = np.round(x).astype(np.int32)
                word |= (q.astype(np.uint32) & np.uint32((1 << bits) - 1)) << np.uint32(shift)
            out[:, self.offset:self.offset + 4] = word.view(np.uint8).reshape(n, 4)
            return
        o = self.offset
        for k, c in enumerate(self.comps):
            nb, kind = SCALAR[c]
            x = v[:, k] if k < v.shape[1] else np.zeros(n, np.float32)
            if kind == 'f4': b = x.astype('<f4')
            elif kind == 'f2': b = x.astype('<f2')
            elif kind == 'un8': b = np.round(np.clip(x, 0, 1) * 255).astype(np.uint8)
            elif kind == 'sn8': b = np.round(np.clip(x, -1, 1) * 127).astype(np.int8)
            elif kind == 'u1': b = np.round(x).astype(np.uint8)
            elif kind == 's1': b = np.round(x).astype(np.int8)
            elif kind == 'u2': b = np.round(x).astype('<u2')
            elif kind == 's2': b = np.round(x).astype('<i2')
            elif kind == 'un16': b = np.round(np.clip(x, 0, 1) * 65535).astype('<u2')
            elif kind == 'sn16': b = np.round(np.clip(x, -1, 1) * 32767).astype('<i2')
            out[:, o:o + nb] = b.view(np.uint8).reshape(n, nb)
            o += nb


class Buffer:
    def __init__(self, name, attrs):
        self.name, self.attrs = name, attrs
        self.known = all(a.known for a in attrs)
        self.stride = sum(a.size for a in attrs)

    def find(self, semantic, nth=0):
        hits = [a for a in self.attrs if a.known and a.base == semantic]
        return hits[nth] if len(hits) > nth else None


def parse_layouts(xml):
    """Every <InputLayout> in a model, in order: [(name, [Buffer])]."""
    out = []
    for block in re.findall(r'<InputLayout.*?</InputLayout>', xml, re.S):
        out.append(parse_layout(block))
    return out


def parse_layout(xml):
    xml = xml[xml.find('<InputLayout'):]
    xml = xml[:xml.find('</InputLayout>') + len('</InputLayout>')]
    root = ET.fromstring(xml)
    bufs = []
    for b in root.findall('BufferDesc'):
        attrs, off = [], 0
        for a in b.findall('AttributeDesc'):
            comps = [c.get('format') for c in a.findall('ComponentDesc')]
            at = Attribute(a.get('name'), a.get('semantic'), comps, off)
            attrs.append(at)
            off += at.size
        bufs.append(Buffer(b.get('name'), attrs))
    return root.get('name'), bufs


# ------------------------------------------------------------------ model
class Model:
    """Open with the bytes of NAME.MOD and NAME.0.MOD."""

    def __init__(self, desc, gpu):
        self.m, self.g = desc, gpu
        cm, cg = chunks(desc), chunks(gpu)
        self.cm, self.cg = cm, cg
        if 'STRGINLA' not in cm or 'VOID_VBO' not in cg:
            raise ModelError('not a standard model (no vertex layout)')
        o, _, sz = cm['STRGINLA'][0]
        self.layouts = parse_layouts(desc[o + 0x10:o + 0x10 + sz].replace(b'\xad', b'').replace(b'\0', b'').decode('latin1'))
        if not self.layouts:
            raise ModelError('no vertex layout')
        self.layout_name, self.buffers = self.layouts[0]
        self.names = []
        if 'STRGDGRP' in cm:
            self.names = [p.split('|')[1] for p in _strings(desc, cm['STRGDGRP'][0][0], cm['STRGDGRP'][0][2]) if '|' in p]
        self.textures = _strings(desc, cm['STRGTEXN'][0][0], cm['STRGTEXN'][0][2]) if 'STRGTEXN' in cm else []
        o, nvbo, _ = cm['CLAS_VBO'][0]
        raw = [struct.unpack_from('<III', desc, o + 0x10 + k * 0x40) for k in range(nvbo)]
        # the stride field carries the layout in its high 16 bits when a model has several layouts
        self.vbo_info = [(n, idx, st & 0xFFFF) for n, idx, st in raw]
        self.vmap = {(st >> 16, idx): k for k, (n, idx, st) in enumerate(raw)}
        self._cache = {}
        self.vbo_data = [(o + 0x10, a) for o, a, sz in cg['VOID_VBO']]
        self.skinned = any(b.find('BLENDINDICES') for b in self.buffers) or len(self.vbo_info) != len(self.buffers) \
            or not all(b.known for b in self.buffers) or len(self.layouts) > 1
        self.ebos = [(o + 0x10, n) for o, n, _ in cg['VOID_EBO']]     # one index buffer per vertex layout
        self.ebo_off, self.nidx = self.ebos[0]
        self.draws = []
        n = cm['INT0DRBL'][0][1]
        base = cm['VOIDDRBL'][0][0] + 0x10
        offs = [struct.unpack_from('<I', desc, cm['INT0DRBL'][0][0] + 0x10 + i * 0x10 + 8)[0] for i in range(n)]
        for i, rel in enumerate(offs):
            r = base + rel
            ns, blocks, lod_at, _lod_end = struct.unpack_from('<HHHH', desc, r + 0x28)
            vcount = struct.unpack_from('<I', desc, r + 0x0C)[0]
            icount, istart = struct.unpack_from('<II', desc, r + lod_at)      # LOD 0: the full-detail mesh
            vbases = [struct.unpack_from('<I', desc, r + blocks + 4 + k * 0x18)[0] for k in range(ns)]
            lods = max(1, struct.unpack_from('<H', desc, r + 0x08)[0]) if blocks != 0x38 else 1
            end = base + (offs[i + 1] if i + 1 < len(offs) else cm['VOIDDRBL'][0][2])
            self.draws.append(dict(rec=r, streams=ns, vcount=vcount, icount=icount, istart=istart, vbases=vbases,
                                   lods=lods, layout=self._draw_layout(r, end, ns, vbases, vcount),
                                   name=self.names[i] if i < len(self.names) else f'mesh{i}'))
        self._name_groups()
        self.editable = not self.skinned and all(d['streams'] == len(self.buffers) and d['lods'] == 1 for d in self.draws)
        self.materials = self._materials()

    def _name_groups(self):
        """Names belong to draw groups (count, first mesh); a group can span several meshes."""
        if 'INT0DGRP' not in self.cm or not self.names:
            return
        o, n, _ = self.cm['INT0DGRP'][0]
        for g in range(min(n, len(self.names))):
            cnt, _pad, first = struct.unpack_from('<III', self.m, o + 0x10 + g * 0x10)
            if cnt > 64 or first + cnt > len(self.draws):
                return
            for k in range(cnt):
                self.draws[first + k]['name'] = self.names[g] + (f' ({k + 1})' if cnt > 1 else '')

    def _draw_layout(self, r, end, ns, vbases, vcount):
        """Which vertex layout a mesh uses. Its per-stream records hold each stream's stride times 8."""
        if len(self.layouts) == 1:
            return 0
        strides = []
        for o in range(r + 0x40, min(end, len(self.m)) - 8, 4):
            if self.m[o:o + 4] == b'\x14\0\0\0':
                s8 = struct.unpack_from('<H', self.m, o + 6)[0]
                if s8 and s8 % 8 == 0:
                    strides.append(s8 // 8)
        best, score = 0, -1
        for L, (_, bufs) in enumerate(self.layouts):
            want = [self.vbo_info[self.vmap[(L, k)]][2] for k in range(len(bufs)) if (L, k) in self.vmap]
            fits = all((L, k) in self.vmap and vbases[k] + vcount <= self.vbo_info[self.vmap[(L, k)]][0]
                       for k in range(min(2, ns, len(vbases))))
            match = sum(1 for a, b in zip(strides, want) if a == b) if strides else 0
            sc = (len(bufs) == ns) * 4 + fits * 2 + match * 3
            if sc > score:
                best, score = L, sc
        return best

    def _materials(self):
        """One dict per mesh: {param hash: texture name} for every texture the mesh's material uses."""
        cm, m = self.cm, self.m
        if 'VOIDPRMS' not in cm or 'INT0MREF' not in cm:
            return [{} for _ in self.draws]
        po = cm['VOIDPRMS'][0][0] + 0x20
        mo, count, _ = cm['INT0MREF'][0]
        out = []
        for i in range(count):
            _h, _a, n, _b, start = struct.unpack_from('<IIIII', m, mo + 0x10 + i * 0x18)
            params = {}
            for j in range(start, start + n):
                e = po + j * 0x28
                if e + 0x28 > len(m):
                    break
                h, = struct.unpack_from('<I', m, e)
                v, = struct.unpack_from('<I', m, e + 0x10)
                typ, = struct.unpack_from('<I', m, e + 0x18)
                if typ == 0x12345 and v < len(self.textures) and self.textures[v]:
                    params[h] = self.textures[v]
            out.append(params)
        while len(out) < len(self.draws):
            out.append({})
        return out

    def material_maps(self, i):
        """{'color', 'normal', 'rough', 'metal'} texture names for mesh i (None where there isn't one)."""
        color = self.color_texture(i)
        names = list((self.materials[i] if i < len(self.materials) else {}).values())
        out = {'color': color, 'normal': None, 'rough': None, 'metal': None}
        base = None
        if color:
            base = re.sub(r'([-_](base_?)?colou?r|_c|-c)$', '', color, flags=re.I).lower()
        keys = {'normal': r'normal', 'rough': r'rough', 'metal': r'metal'}
        for slot, pat in keys.items():
            cands = [n for n in names if re.search(pat, n, re.I) and not re.search(r'flat|tar\d|^gray|^grey', n, re.I)]
            if base:
                same = sorted((n for n in cands if n.lower().startswith(base)), key=len)
                cands = same or cands
            if cands:
                out[slot] = cands[0]
        return out

    def color_texture(self, i):
        """Best guess at the colour (albedo) texture of mesh i, or None."""
        params = self.materials[i] if i < len(self.materials) else {}
        names = list(params.values())
        def bad(n):
            n = n.lower()
            return re.search(r'normal|rough|metalness|metallic|spec|emiss|_ao\b|-ao\b|mask|lightmap|tar\d', n) is not None or \
                re.fullmatch(r'(gray|grey)_?\d+|f{6}|0{6}|flatnormalmap|black|white', n) is not None
        for key in (0xD5DBE45D, 0x61E0008D):
            if key in params and not bad(params[key]):
                return params[key]
        for n in names:
            if re.search(r'(base_?)?colou?r|diffuse|albedo|_d$|-c$', n.lower()) and not bad(n):
                return n
        for n in names:
            if not bad(n):
                return n
        return None

    @classmethod
    def open(cls, desc_path, gpu_path):
        with open(desc_path, 'rb') as f: d = f.read()
        with open(gpu_path, 'rb') as f: g = f.read()
        return cls(d, g)

    # -- reading
    def stream(self, k):
        n, idx, stride = self.vbo_info[k]
        off, _ = self.vbo_data[k]
        return self.g[off:off + n * stride], n, stride

    def attribute(self, semantic, nth=0, layout=0):
        """(values for every vertex, buffer index) for the nth attribute with this semantic in a layout."""
        seen = 0
        _, bufs = self.layouts[layout]
        for k, b in enumerate(bufs):
            entry = self.vmap.get((layout, k))
            if entry is None:
                continue
            for a in b.attrs:
                if a.known and a.base == semantic:
                    if seen == nth:
                        key = (entry, a.offset, semantic)
                        if key not in self._cache:
                            buf, n, stride = self.stream(entry)
                            self._cache[key] = a.decode(buf, stride, n)
                        return self._cache[key], k
                    seen += 1
        return None, None

    def indices(self, layout=0):
        off, n = self.ebos[layout] if layout < len(self.ebos) else self.ebos[0]
        return np.frombuffer(self.g, '<u2', n, off)

    def mesh(self, i):
        """positions (n,3), normals (n,3), uvs (n,2), triangles (m,3) for mesh i (vertex indices local to the mesh)."""
        dr = self.draws[i]
        tris = self.indices(dr['layout'])[dr['istart']:dr['istart'] + dr['icount'] // 3 * 3].astype(np.int64).reshape(-1, 3)
        count = max(dr['vcount'], int(tris.max()) + 1 if len(tris) else 0)
        def part(semantic, width):
            vals, k = self.attribute(semantic, layout=dr['layout'])
            if vals is None:
                return None
            vb = dr['vbases'][k] if k < len(dr['vbases']) else (dr['vbases'][0] if dr['vbases'] else 0)
            return vals[vb:vb + count, :width]
        p = part('POSITION', 3)
        n = part('NORMAL', 3)
        t = part('TEXCOORD', 2)
        if len(tris):
            tris = tris[(tris < len(p)).all(1)]
        if n is None or len(n) != len(p):
            n = np.zeros_like(p)
        if t is None or len(t) != len(p):
            t = np.zeros((len(p), 2), np.float32)
        return p, n, t, tris

    def extra_uv(self, i, semantic):
        """Another per-vertex attribute of mesh i by semantic (e.g. TEXCOORD_UV_PLAYER_NUMBER), or None."""
        dr = self.draws[i]
        vals, k = self.attribute(semantic, layout=dr['layout'])
        if vals is None:
            return None
        p, _, _, _ = self.mesh(i)
        vb = dr['vbases'][k] if k < len(dr['vbases']) else 0
        v = vals[vb:vb + len(p), :2]
        return v if len(v) == len(p) else None

    def tangents(self, i):
        """(n,4) tangents for mesh i (xyz + handedness), or None."""
        dr = self.draws[i]
        vals, k = self.attribute('TANGENT', layout=dr['layout'])
        if vals is None:
            return None
        p, _, _, tris = self.mesh(i)
        vb = dr['vbases'][k] if k < len(dr['vbases']) else 0
        t = vals[vb:vb + len(p)]
        if len(t) != len(p):
            return None
        out = np.zeros((len(t), 4), np.float32)
        out[:, :3] = t[:, :3]
        out[:, 3] = t[:, 3] if t.shape[1] > 3 else 1.0
        return out

    def bounds(self):
        pts = []
        for L in range(len(self.layouts)):
            pos, _ = self.attribute('POSITION', layout=L)
            if pos is not None:
                pts.append(pos[:, :3])
        p = np.concatenate(pts)
        return p.min(0), p.max(0)

    def write_obj(self, path, meshes=None):
        with open(path, 'w', encoding='utf-8') as f:
            f.write('# exported by Mod the Show Manager\n')
            base = 1
            for i, dr in enumerate(self.draws):
                if meshes is not None and i not in meshes:
                    continue
                p, n, t, tris = self.mesh(i)
                f.write(f'o {dr["name"]}\n')
                f.writelines('v %.6f %.6f %.6f\n' % tuple(v) for v in p)
                f.writelines('vt %.6f %.6f\n' % (u[0], 1 - u[1]) for u in t)
                f.writelines('vn %.5f %.5f %.5f\n' % tuple(v) for v in n)
                for a, b, c in tris + base:
                    f.write(f'f {a}/{a}/{a} {b}/{b}/{b} {c}/{c}/{c}\n')
                base += len(p)


# ------------------------------------------------------------------ editing
class Editor:
    """Change meshes of a static model and write both files back."""

    def __init__(self, model):
        if not model.editable:
            raise ModelError('this model is skinned or uses a layout that cannot be edited yet')
        self.mdl = model
        M = model
        streams = [np.frombuffer(M.stream(k)[0], np.uint8).reshape(-1, M.vbo_info[k][2]) for k in range(len(M.buffers))]
        idx = M.indices()
        self.parts = []
        for dr in M.draws:
            vb = dr['vbases'][0]
            self.parts.append(dict(
                streams=[s[vb:vb + dr['vcount']].copy() for s in streams],
                idx=idx[dr['istart']:dr['istart'] + dr['icount']].copy(), dirty=False))
        pos, _ = M.attribute('POSITION')
        self.posw = None
        if pos.shape[1] > 3 and np.ptp(pos[:, 2]) > 0:
            fit = np.polyfit(pos[:, 2], pos[:, 3], 1)
            if np.abs(np.polyval(fit, pos[:, 2]) - pos[:, 3]).max() < 0.02:
                self.posw = fit          # bats keep the length axis in w
        self.posw_const = float(np.median(pos[:, 3])) if pos.shape[1] > 3 else 1.0

    def get(self, i, semantic, nth=0):
        seen = 0
        for k, b in enumerate(self.mdl.buffers):
            for a in b.attrs:
                if a.known and a.base == semantic:
                    if seen == nth:
                        s = self.parts[i]['streams'][k]
                        return a.decode(s.tobytes(), b.stride, len(s))
                    seen += 1
        return None

    def put(self, i, semantic, values, nth=0):
        seen = 0
        for k, b in enumerate(self.mdl.buffers):
            for a in b.attrs:
                if a.known and a.base == semantic:
                    if seen == nth:
                        a.encode(values, self.parts[i]['streams'][k], b.stride)
                        self.parts[i]['dirty'] = True
                        return
                    seen += 1

    def set_positions(self, i, xyz):
        """Move the vertices of mesh i (same vertex count). Keeps w where the game uses it."""
        old = self.get(i, 'POSITION')
        new = old.copy()
        new[:, :3] = xyz
        self.put(i, 'POSITION', new)

    def replace(self, i, positions, normals, uvs, tris):
        """Give mesh i brand new geometry (any size up to 65535 vertices)."""
        positions = np.asarray(positions, np.float32)
        normals = np.asarray(normals, np.float32)
        uvs = np.asarray(uvs, np.float32)
        tris = np.asarray(tris, np.int64).reshape(-1, 3)
        n = len(positions)
        if n == 0 or n > 65535:
            raise ModelError(f'a mesh needs 1 to 65535 vertices (this one has {n})')
        if tris.max() >= n:
            raise ModelError('a face points at a vertex that does not exist')
        old = self.parts[i]['streams']
        tangents = _tangents(positions, normals, uvs, tris)
        streams = []
        for k, b in enumerate(self.mdl.buffers):
            s = np.zeros((n, b.stride), np.uint8)
            # start from the first old vertex so attributes we do not set keep sane values
            if len(old[k]):
                s[:] = old[k][0]
            uv_seen = 0
            for a in b.attrs:
                if a.base == 'POSITION':
                    w = np.polyval(self.posw, positions[:, 2]) if self.posw is not None else np.full(n, self.posw_const)
                    a.encode(np.column_stack([positions, w]), s, b.stride)
                elif a.base == 'NORMAL':
                    flag = a.decode(old[k][:1].tobytes(), b.stride, 1)[0, 3:] if len(old[k]) and len(a.comps) > 3 else []
                    a.encode(np.column_stack([normals] + ([np.full((n, 1), flag[0])] if len(flag) else [])), s, b.stride)
                elif a.base == 'TANGENT':
                    a.encode(np.column_stack([tangents, np.ones(n)]) if a.name != 'TanFlip' or len(a.comps) == 4 else tangents, s, b.stride)
                elif a.base == 'TEXCOORD':
                    if uv_seen == 0:
                        a.encode(uvs, s, b.stride)
                    uv_seen += 1
                elif a.base == 'COLOR':
                    a.encode(np.ones((n, len(a.comps))), s, b.stride)
            streams.append(s)
        self.parts[i] = dict(streams=streams, idx=tris.astype(np.uint16).reshape(-1), dirty=True)

    def hide(self, i):
        """Collapse mesh i to a single degenerate triangle."""
        s = [st[:1].copy() for st in self.parts[i]['streams']]
        self.parts[i] = dict(streams=s, idx=np.zeros(3, np.uint16), dirty=True)

    def save(self):
        """Return (desc bytes, gpu bytes)."""
        M = self.mdl
        m = bytearray(M.m)
        vb = ib = 0
        dnfo = M.cm['VOIDDNFO'][0][0] + 0x20 if 'VOIDDNFO' in M.cm else None
        for i, (dr, pt) in enumerate(zip(M.draws, self.parts)):
            r = dr['rec']
            vc, ic = len(pt['streams'][0]), len(pt['idx'])
            struct.pack_into('<I', m, r + 0x0C, vc)
            struct.pack_into('<II', m, r + 0x30, ic, ib)
            ns = dr['streams']
            for k in range(ns):
                struct.pack_into('<I', m, r + 0x3C + k * 0x18, vb)
                q = r + 0x80 + k * 0x1C
                struct.pack_into('<I', m, q, vb * M.vbo_info[k][2])
                struct.pack_into('<I', m, q + 0x14, vc)
                struct.pack_into('<I', m, q + 0x18, int(vc).bit_length())
            if pt['dirty'] and dnfo is not None:
                p = self.get(i, 'POSITION')[:, :3]
                mn, mx = p.min(0), p.max(0)
                c = (mn + mx) / 2
                struct.pack_into('<10f', m, dnfo + i * 0x28, *mn, *mx, *c, float(np.linalg.norm(p - c, axis=1).max()))
            vb += vc
            ib += ic
        if vb > 65535 * 64:
            raise ModelError('model is too big')
        o = M.cm['CLAS_VBO'][0][0]
        for k in range(len(M.vbo_info)):
            struct.pack_into('<I', m, o + 0x10 + k * 0x40, vb)
        struct.pack_into('<I', m, M.cm['CLAS_EBO'][0][0] + 0x18, ib)

        g, cg = M.g, M.cg
        def raw(name):
            o, a, sz = cg[name][0]
            return bytearray(g[o:o + 0x10 + sz])
        clas_vbo = raw('CLAS_VBO')
        for k in range(len(M.vbo_info)):
            struct.pack_into('<I', clas_vbo, 0x10 + k * 0x40, vb)
        clas_ebo = raw('CLAS_EBO')
        struct.pack_into('<I', clas_ebo, 0x18, ib)
        data = [np.concatenate([p['streams'][k] for p in self.parts]).tobytes() for k in range(len(M.buffers))]
        idx = np.concatenate([p['idx'] for p in self.parts]).astype('<u2').tobytes()
        # keep the original chunk order of the GPU file
        order = sorted([(o, 'VBO', k) for k, (o, a, sz) in enumerate(cg['VOID_VBO'])] +
                       [(cg['CLAS_VBO'][0][0], 'CLAS_VBO', 0), (cg['CLAS_EBO'][0][0], 'CLAS_EBO', 0),
                        (cg['VOID_EBO'][0][0], 'EBO', 0)])
        out = bytearray(g[:0x10]) + raw('VOID_PAD')
        last = order[-1]
        for o, kind, k in order:
            if kind == 'CLAS_VBO': out += clas_vbo
            elif kind == 'CLAS_EBO': out += clas_ebo
            elif kind == 'EBO': out += _chunk(b'VOID_EBO', ib, idx, len(out), 0x10 if (o, kind, k) == last else 0x100)
            else: out += _chunk(b'VOID_VBO', vb, data[k], len(out), 0x10 if (o, kind, k) == last else 0x100)
        out += g[cg['IFF0VERS'][0][0]:]
        struct.pack_into('<I', out, 0x0C, len(out) - 0x10)
        return bytes(m), bytes(out)


def _chunk(tag, a, payload, at, align):
    # vertex buffers always get 1-16 zero bytes, the index buffer 0-15
    zeros = (-len(payload) % 16) if tag == b'VOID_EBO' else 16 - len(payload) % 16
    body = payload + b'\0' * zeros
    end = at + 0x10 + len(body)
    nxt = ((end + 0x10 + align - 1) // align) * align - 0x10
    body += bytes([PAD]) * (nxt - end)
    return tag + struct.pack('<II', a, len(body)) + body


def _tangents(p, n, uv, tris):
    t = np.zeros_like(p)
    v0, v1, v2 = p[tris[:, 0]], p[tris[:, 1]], p[tris[:, 2]]
    w0, w1, w2 = uv[tris[:, 0]], uv[tris[:, 1]], uv[tris[:, 2]]
    e1, e2, d1, d2 = v1 - v0, v2 - v0, w1 - w0, w2 - w0
    r = d1[:, 0] * d2[:, 1] - d2[:, 0] * d1[:, 1]
    r = np.where(np.abs(r) < 1e-12, 1e-12, r)
    f = (e1 * d2[:, 1:2] - e2 * d1[:, 1:2]) / r[:, None]
    for k in range(3):
        np.add.at(t, tris[:, k], f)
    t -= n * (t * n).sum(1, keepdims=True)
    ln = np.linalg.norm(t, axis=1, keepdims=True)
    bad = ln[:, 0] < 1e-9
    if bad.any():   # pick any direction perpendicular to the normal
        alt = np.cross(n[bad], np.array([0, 0, 1.0]))
        alt[np.linalg.norm(alt, axis=1) < 1e-6] = [1, 0, 0]
        t[bad] = alt
        ln = np.linalg.norm(t, axis=1, keepdims=True)
    return t / ln


def read_obj(path):
    """Read a Wavefront OBJ into positions, normals, uvs, triangles (one mesh, all objects merged)."""
    vs, vts, vns, faces = [], [], [], []
    with open(path, encoding='utf-8', errors='ignore') as f:
        for line in f:
            s = line.split()
            if not s:
                continue
            if s[0] == 'v': vs.append([float(x) for x in s[1:4]])
            elif s[0] == 'vt': vts.append([float(x) for x in s[1:3]])
            elif s[0] == 'vn': vns.append([float(x) for x in s[1:4]])
            elif s[0] == 'f':
                corners = []
                for c in s[1:]:
                    a = (c.split('/') + ['', ''])[:3]
                    def ix(x, count):
                        if not x: return None
                        i = int(x)
                        return i - 1 if i > 0 else count + i
                    corners.append((ix(a[0], len(vs)), ix(a[1], len(vts)), ix(a[2], len(vns))))
                for k in range(1, len(corners) - 1):
                    faces.append((corners[0], corners[k], corners[k + 1]))
    if not faces:
        raise ModelError('the OBJ has no faces')
    vs = np.array(vs, np.float32)
    vts = np.array(vts, np.float32) if vts else np.zeros((1, 2), np.float32)
    vns = np.array(vns, np.float32) if vns else None
    key, P, T, N, tris = {}, [], [], [], []
    for face in faces:
        tri = []
        for c in face:
            if c not in key:
                key[c] = len(P)
                P.append(vs[c[0]])
                T.append(vts[c[1]] if c[1] is not None else (0, 0))
                N.append(vns[c[2]] if vns is not None and c[2] is not None else (0, 0, 0))
            tri.append(key[c])
        tris.append(tri)
    P, T, N, tris = np.array(P, np.float32), np.array(T, np.float32), np.array(N, np.float32), np.array(tris)
    if not np.any(N):
        fn = np.cross(P[tris[:, 1]] - P[tris[:, 0]], P[tris[:, 2]] - P[tris[:, 0]])
        for k in range(3):
            np.add.at(N, tris[:, k], fn)
    N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
    T[:, 1] = 1 - T[:, 1]
    return P, N, T, tris


def gpu_path(desc_rel):
    """NSW/OBJECTS/G4GAMEBAT.MOD -> NSW/OBJECTS/G4GAMEBAT.0.MOD"""
    return desc_rel[:-4] + '.0.MOD'


def is_model(rel):
    r = rel.upper()
    return r.endswith('.MOD') and not re.search(r'\.\d+\.MOD$', r)
