"""GPU model viewer. Orbit with the left button, pan with right or middle, wheel to zoom, double-click to frame.

Two looks:
  Standard      textured, smooth-lit, fast on any GPU.
  High Quality  normal and roughness maps, physically based lighting, a soft shadow from the key light onto the
                model and a floor, filmic tone mapping, full-resolution textures and 8x anti-aliasing.
"""
import math

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QImage, QMatrix4x4, QSurfaceFormat, QVector3D
from PySide6.QtOpenGL import (QOpenGLBuffer, QOpenGLFramebufferObject, QOpenGLFramebufferObjectFormat, QOpenGLShader,
                              QOpenGLShaderProgram, QOpenGLTexture, QOpenGLVertexArrayObject)
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from . import theme

GL_FLOAT, GL_TRIANGLES, GL_LINES = 0x1406, 0x0004, 0x0001
GL_DEPTH_TEST = 0x0B71
GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT = 0x4000, 0x0100
GL_LEQUAL = 0x0203
GL_TEXTURE_2D, GL_TEXTURE0, GL_FRAMEBUFFER = 0x0DE1, 0x84C0, 0x8D40
STRIDE = 56   # pos3 nrm3 uv2 tan4 uvn2 (name/number uv)
SHADOW = 2048

VERT = """
attribute vec3 a_pos;
attribute vec3 a_nrm;
attribute vec2 a_uv;
attribute vec4 a_tan;
attribute vec2 a_uvn;
uniform mat4 u_mvp;
uniform mat4 u_model;
uniform mat4 u_light;
varying vec3 v_nrm;
varying vec3 v_pos;
varying vec2 v_uv;
varying vec4 v_tan;
varying vec4 v_lpos;
varying vec2 v_uvn;
void main() {
    v_uvn = a_uvn;
    v_nrm = (u_model * vec4(a_nrm, 0.0)).xyz;
    v_tan = vec4((u_model * vec4(a_tan.xyz, 0.0)).xyz, a_tan.w);
    v_pos = (u_model * vec4(a_pos, 1.0)).xyz;
    v_uv = a_uv;
    v_lpos = u_light * vec4(v_pos, 1.0);
    gl_Position = u_mvp * vec4(a_pos, 1.0);
}
"""

FRAG = """
varying vec3 v_nrm;
varying vec3 v_pos;
varying vec2 v_uv;
varying vec4 v_tan;
varying vec4 v_lpos;
varying vec2 v_uvn;
uniform sampler2D u_tex;
uniform sampler2D u_otex;
uniform float u_has_o;
uniform sampler2D u_ntex;
uniform sampler2D u_rtex;
uniform sampler2D u_shadow;
uniform vec3 u_color;
uniform vec3 u_eye;
uniform vec3 u_key;
uniform float u_textured;
uniform float u_cutout;
uniform float u_highlight;
uniform float u_hq;
uniform float u_has_n;
uniform float u_has_r;
uniform float u_metal;
uniform float u_rough;
uniform float u_shadow_on;
uniform float u_texel;

float unpack(vec4 c) { return dot(c, vec4(1.0, 1.0/255.0, 1.0/65025.0, 1.0/16581375.0)); }

float shadow_at(vec3 n) {
    if (u_shadow_on < 0.5) return 1.0;
    vec3 p = v_lpos.xyz / v_lpos.w * 0.5 + 0.5;
    if (p.x < 0.0 || p.x > 1.0 || p.y < 0.0 || p.y > 1.0 || p.z > 1.0) return 1.0;
    float bias = 0.0015 + 0.004 * (1.0 - max(dot(n, u_key), 0.0));
    float lit = 0.0;
    for (int x = -2; x <= 2; x++)
        for (int y = -2; y <= 2; y++) {
            float d = unpack(texture2D(u_shadow, p.xy + vec2(float(x), float(y)) * u_texel));
            lit += (p.z - bias > d) ? 0.0 : 1.0;
        }
    return lit / 25.0;
}

vec3 aces(vec3 x) {
    return clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0);
}

void main() {
    vec4 t = texture2D(u_tex, v_uv);
    if (u_cutout > 0.5 && t.a < 0.35) discard;
    vec3 base = mix(u_color, t.rgb, u_textured);
    if (u_has_o > 0.5 && v_uvn.x >= 0.0 && v_uvn.x <= 1.0 && v_uvn.y >= 0.0 && v_uvn.y <= 1.0) {
        vec4 o = texture2D(u_otex, v_uvn);
        base = mix(base, o.rgb, o.a);
    }
    vec3 n = v_nrm;
    if (dot(n, n) < 0.01) n = cross(dFdx(v_pos), dFdy(v_pos));
    n = normalize(n);
    vec3 v = normalize(u_eye - v_pos);
    if (dot(n, v) < 0.0) n = -n;

    if (u_hq < 0.5) {
        vec3 key = normalize(vec3(0.45, 0.85, 0.55));
        vec3 fill = normalize(vec3(-0.6, 0.3, -0.5));
        float d = max(dot(n, key), 0.0);
        float f = max(dot(n, fill), 0.0) * 0.35;
        float hemi = 0.5 + 0.5 * n.y;
        vec3 ambient = mix(vec3(0.20, 0.21, 0.25), vec3(0.42, 0.45, 0.52), hemi);
        float rim = pow(1.0 - max(dot(n, v), 0.0), 3.0) * 0.18;
        vec3 h = normalize(key + v);
        float spec = pow(max(dot(n, h), 0.0), 40.0) * 0.18;
        vec3 c = base * (ambient + d * vec3(1.0, 0.97, 0.92) * 0.85 + f) + spec + rim;
        c = mix(c, vec3(0.85, 0.20, 0.25), u_highlight * 0.35);
        gl_FragColor = vec4(pow(c, vec3(0.95)), 1.0);
        return;
    }

    // High Quality: tangent-space normal map, GGX specular, shadowed key light, sky/ground ambient
    if (u_has_n > 0.5 && dot(v_tan.xyz, v_tan.xyz) > 0.01) {
        vec3 tn = texture2D(u_ntex, v_uv).rgb * 2.0 - 1.0;
        tn.z = sqrt(max(1.0 - dot(tn.xy, tn.xy), 0.0));
        vec3 T = normalize(v_tan.xyz - n * dot(n, v_tan.xyz));
        vec3 B = cross(n, T) * (v_tan.w < 0.5 ? -1.0 : 1.0);
        n = normalize(T * tn.x + B * tn.y + n * tn.z);
    }
    vec3 albedo = pow(base, vec3(2.2));
    float rough = u_has_r > 0.5 ? clamp(texture2D(u_rtex, v_uv).r, 0.08, 1.0) : u_rough;
    float metal = u_metal;
    vec3 f0 = mix(vec3(0.04), albedo, metal);
    vec3 diffuse = albedo * (1.0 - metal);

    vec3 L = u_key;
    vec3 H = normalize(L + v);
    float NL = max(dot(n, L), 0.0), NV = max(dot(n, v), 0.001), NH = max(dot(n, H), 0.0), VH = max(dot(v, H), 0.0);
    float a = rough * rough, a2 = a * a;
    float D = a2 / (3.14159 * pow(NH * NH * (a2 - 1.0) + 1.0, 2.0));
    float k = (rough + 1.0) * (rough + 1.0) / 8.0;
    float G = (NL / (NL * (1.0 - k) + k)) * (NV / (NV * (1.0 - k) + k));
    vec3 F = f0 + (1.0 - f0) * pow(1.0 - VH, 5.0);
    vec3 spec = D * G * F / max(4.0 * NL * NV, 0.001);
    float sh = shadow_at(n);
    vec3 sun = vec3(1.0, 0.95, 0.88) * 3.2;
    vec3 direct = (diffuse / 3.14159 * (1.0 - F) + spec) * sun * NL * sh;

    vec3 fillL = normalize(vec3(-0.55, 0.35, -0.6));
    vec3 fill = diffuse * vec3(0.55, 0.62, 0.8) * 0.3 * max(dot(n, fillL), 0.0);
    float hemi = 0.5 + 0.5 * n.y;
    vec3 sky = mix(vec3(0.10, 0.09, 0.08), vec3(0.42, 0.48, 0.58), hemi);
    vec3 Fa = f0 + (max(vec3(1.0 - rough), f0) - f0) * pow(1.0 - NV, 5.0);
    vec3 ambient = diffuse * sky * 0.9 + Fa * sky * (1.0 - rough) * 0.6;
    float rim = pow(1.0 - NV, 4.0) * 0.12;

    vec3 c = direct + fill + ambient + rim;
    c = aces(c * 1.05);
    c = pow(c, vec3(1.0 / 2.2));
    c = mix(c, vec3(0.85, 0.20, 0.25), u_highlight * 0.35);
    gl_FragColor = vec4(c, 1.0);
}
"""

DEPTH_VERT = """
attribute vec3 a_pos;
attribute vec2 a_uv;
uniform mat4 u_mvp;
varying vec2 v_uv;
void main() { v_uv = a_uv; gl_Position = u_mvp * vec4(a_pos, 1.0); }
"""
DEPTH_FRAG = """
varying vec2 v_uv;
uniform sampler2D u_tex;
uniform float u_cutout;
vec4 pack(float d) {
    vec4 e = fract(d * vec4(1.0, 255.0, 65025.0, 16581375.0));
    return e - e.yzww * vec4(1.0/255.0, 1.0/255.0, 1.0/255.0, 0.0);
}
void main() {
    if (u_cutout > 0.5 && texture2D(u_tex, v_uv).a < 0.35) discard;
    gl_FragColor = pack(gl_FragCoord.z);
}
"""

FLOOR_VERT = """
attribute vec3 a_pos;
uniform mat4 u_mvp;
uniform mat4 u_light;
varying vec4 v_lpos;
varying vec3 v_pos;
void main() { v_pos = a_pos; v_lpos = u_light * vec4(a_pos, 1.0); gl_Position = u_mvp * vec4(a_pos, 1.0); }
"""
FLOOR_FRAG = """
varying vec4 v_lpos;
varying vec3 v_pos;
uniform sampler2D u_shadow;
uniform float u_texel;
uniform float u_radius;
uniform vec3 u_bg;
float unpack(vec4 c) { return dot(c, vec4(1.0, 1.0/255.0, 1.0/65025.0, 1.0/16581375.0)); }
void main() {
    vec3 p = v_lpos.xyz / v_lpos.w * 0.5 + 0.5;
    float lit = 0.0;
    for (int x = -2; x <= 2; x++)
        for (int y = -2; y <= 2; y++) {
            float d = unpack(texture2D(u_shadow, p.xy + vec2(float(x), float(y)) * u_texel * 1.5));
            lit += (p.z - 0.002 > d) ? 0.0 : 1.0;
        }
    lit /= 25.0;
    float fade = smoothstep(u_radius * 1.6, u_radius * 0.3, length(v_pos.xz));
    vec3 c = mix(u_bg, u_bg * 2.6 + vec3(0.05, 0.055, 0.07), fade * 0.85);
    c *= mix(1.0, 0.38, (1.0 - lit) * fade);
    gl_FragColor = vec4(c, 1.0);
}
"""

LINE_VERT = """
attribute vec3 a_pos;
uniform mat4 u_mvp;
void main() { gl_Position = u_mvp * vec4(a_pos, 1.0); }
"""
LINE_FRAG = """
uniform vec4 u_color;
void main() { gl_FragColor = u_color; }
"""


def available():
    """True when an OpenGL 2.1+ context can be made (not on some remote desktops / VMs)."""
    from PySide6.QtGui import QOffscreenSurface, QOpenGLContext
    try:
        ctx = QOpenGLContext()
        if not ctx.create():
            return False
        s = QOffscreenSurface()
        s.setFormat(ctx.format())
        s.create()
        ok = ctx.makeCurrent(s)
        if ok:
            ctx.doneCurrent()
        return bool(ok)
    except Exception:
        return False


class Mesh:
    """What the viewer draws: per-vertex data, triangles, and textures or a flat colour."""

    def __init__(self, pos, nrm, uv, tris, color='#c9c2b0', image=None, visible=True, cutout=False, tan=None,
                 normal_map=None, rough_map=None, metal=0.0, rough=0.6, uvn=None, overlay=None):
        self.pos, self.nrm, self.uv, self.tris, self.tan = pos, nrm, uv, tris, tan
        self.color, self.image, self.visible, self.cutout = QColor(color), image, visible, cutout
        self.normal_map, self.rough_map, self.metal, self.rough = normal_map, rough_map, metal, rough
        self.uvn, self.overlay = uvn, overlay
        self.otex = None
        self.has_o = False
        self.highlight = False
        self.vbo = self.tex = self.ntex = self.rtex = None
        self.count = 0
        self.has_tex = self.has_n = self.has_r = False


class ModelView3D(QOpenGLWidget):
    failed = Signal(str)

    def __init__(self, hq=False):
        super().__init__()
        fmt = QSurfaceFormat()
        fmt.setDepthBufferSize(24)
        fmt.setSamples(8 if hq else 4)
        self.setFormat(fmt)
        self.setMinimumHeight(320)
        self.hq = hq
        self.meshes = []
        self.message = 'Pick a model on the left'
        self.textured = True
        self.up = 'y'
        self.prog = None
        self._grid = self._floor = self._shadow = None
        self._drag = None
        self.center, self.radius, self.floor = np.zeros(3, np.float32), 1.0, 0.0
        self.show_floor = True
        self.walk = False
        self._scene = 0            # goes up whenever what is drawn changes (not the camera)
        self._shadow_for = None
        self.setFocusPolicy(Qt.StrongFocus)
        self.reset()

    # ---------------------------------------------------------- camera
    def set_walk(self, on):
        """Fly-through: the camera sits almost on the point it turns around, and WASD moves that point."""
        self.walk = on
        if on:
            self.dist = 0.02
            self.pitch = 0.05
            self.pan = QVector3D(0, float(self.radius * 0.02), float(self.radius * 0.25))
        else:
            self.reset()
        self.update()

    def keyPressEvent(self, e):
        k = e.key()
        moves = {Qt.Key_W: (0, 0, 1), Qt.Key_Up: (0, 0, 1), Qt.Key_S: (0, 0, -1), Qt.Key_Down: (0, 0, -1),
                 Qt.Key_A: (-1, 0, 0), Qt.Key_Left: (-1, 0, 0), Qt.Key_D: (1, 0, 0), Qt.Key_Right: (1, 0, 0),
                 Qt.Key_Q: (0, -1, 0), Qt.Key_E: (0, 1, 0)}
        if k not in moves:
            return super().keyPressEvent(e)
        dx, dy, dz = moves[k]
        view, eye = self._view()
        fwd = self.pan - eye
        fwd.setY(0)
        if fwd.length() < 1e-6:
            fwd = QVector3D(-math.sin(self.yaw), 0, -math.cos(self.yaw))
        fwd.normalize()
        right = QVector3D.crossProduct(fwd, QVector3D(0, 1, 0))
        step = self.radius * (0.04 if e.modifiers() & Qt.ShiftModifier else 0.01)
        self.pan = self.pan + (fwd * dz + right * dx + QVector3D(0, dy, 0)) * step
        self.update()
    def reset(self):
        self.yaw, self.pitch, self.dist, self.pan = 0.7, 0.32, 3.9, QVector3D(0, 0, 0)
        self.update()

    def _frame(self):
        pts = [m.pos for m in self.meshes if m.visible and len(m.pos)] or [m.pos for m in self.meshes if len(m.pos)]
        if not pts:
            self.center, self.radius, self.floor = np.zeros(3, np.float32), 1.0, 0.0
            return
        p = np.concatenate(pts)
        mn, mx = p.min(0), p.max(0)
        self.center = (mn + mx) / 2
        self.radius = float(np.linalg.norm(mx - mn) / 2) or 1.0
        self.floor = float(mn[1] if self.up == 'y' else mn[2])

    def _model(self):
        m = QMatrix4x4()
        if self.up == 'z':                      # the bat stands along z: turn it upright
            m.rotate(-90, 1, 0, 0)
        m.translate(-float(self.center[0]), -float(self.center[1]), -float(self.center[2]))
        return m

    def _view(self):
        eye = QVector3D(math.cos(self.pitch) * math.sin(self.yaw), math.sin(self.pitch),
                        math.cos(self.pitch) * math.cos(self.yaw)) * (self.dist * self.radius)
        v = QMatrix4x4()
        v.lookAt(eye + self.pan, self.pan, QVector3D(0, 1, 0))
        return v, eye + self.pan

    def _floor_y(self):
        return float(self.floor - (self.center[1] if self.up == 'y' else self.center[2]))

    @staticmethod
    def _key():
        k = QVector3D(0.45, 0.85, 0.55)
        k.normalize()
        return k

    def _light(self):
        """Orthographic view from the key light covering the model and the floor around it."""
        r = self.radius * 1.7
        v = QMatrix4x4()
        v.lookAt(self._key() * (r * 2.5), QVector3D(0, 0, 0), QVector3D(0, 1, 0))
        p = QMatrix4x4()
        p.ortho(-r, r, -r, r, r * 0.2, r * 5.0)
        return p * v

    # ---------------------------------------------------------- data
    def set_quality(self, hq):
        self.hq = hq
        self.update()

    def set_meshes(self, meshes, message='', up='y', keep_camera=False):
        self.makeCurrent()
        for m in self.meshes:
            self._free(m)
        self.doneCurrent()
        self.meshes = meshes
        self.message = message
        self.up = up
        self._scene += 1
        self._frame()
        if not keep_camera:
            self.reset()
        self.update()

    def release(self):
        """Frees everything on the GPU. Call before the window goes away, while the context still exists."""
        self.set_meshes([])
        blank = getattr(self, '_blank', None)
        if blank is not None and self.context() is not None:
            self.makeCurrent()
            blank.destroy()
            self._blank = None
            self._shadow = None
            self._shadow_for = None
            self.doneCurrent()

    def set_visible(self, i, on):
        if 0 <= i < len(self.meshes):
            self.meshes[i].visible = on
            self._scene += 1
            self.update()

    def set_highlight(self, i):
        for k, m in enumerate(self.meshes):
            m.highlight = k == i
        self.update()

    def set_textured(self, on):
        self.textured = on
        self._scene += 1
        self.update()

    def _free(self, m):
        blank = getattr(self, '_blank', None)
        for attr in ('vbo', 'tex', 'ntex', 'rtex', 'otex'):
            o = getattr(m, attr, None)
            if o is not None and o is not blank:
                o.destroy()
            setattr(m, attr, None)
        self._scene += 1

    def free_textures(self, m):
        blank = getattr(self, '_blank', None)
        for attr in ('tex', 'ntex', 'rtex', 'otex'):
            o = getattr(m, attr)
            if o is not None and o is not blank:
                o.destroy()
            setattr(m, attr, None)
        self._scene += 1

    def _texture(self, img):
        t = QOpenGLTexture(img)
        t.setMinMagFilters(QOpenGLTexture.LinearMipMapLinear, QOpenGLTexture.Linear)
        t.setWrapMode(QOpenGLTexture.Repeat)
        t.setMaximumAnisotropy(16.0)
        return t

    def _upload(self, m):
        t3 = m.tris.reshape(-1, 3)
        tris = t3[(t3 < len(m.pos)).all(1)].reshape(-1) if len(t3) else t3.reshape(-1)
        n = m.nrm if m.nrm is not None and len(m.nrm) == len(m.pos) else np.zeros_like(m.pos)
        uv = m.uv if m.uv is not None and len(m.uv) == len(m.pos) else np.zeros((len(m.pos), 2), np.float32)
        tan = m.tan if m.tan is not None and len(m.tan) == len(m.pos) else np.zeros((len(m.pos), 4), np.float32)
        uvn = m.uvn if m.uvn is not None and len(m.uvn) == len(m.pos) else np.full((len(m.pos), 2), -1.0, np.float32)
        data = np.hstack([m.pos[tris], n[tris], uv[tris], tan[tris], uvn[tris]]).astype(np.float32)
        m.count = len(tris)
        m.vbo = QOpenGLBuffer(QOpenGLBuffer.VertexBuffer)
        m.vbo.create()
        m.vbo.bind()
        m.vbo.allocate(data.tobytes(), data.nbytes)
        m.vbo.release()

    def _textures(self, m):
        ok = lambda q: isinstance(q, QImage) and not q.isNull()
        if m.tex is None:
            m.has_tex = ok(m.image)
            if m.has_tex:
                img = m.image
                if not m.cutout:
                    # alpha in game textures is a mask (team-colour tint, paint zones), not transparency:
                    # drop it so nothing turns black when the texture is uploaded premultiplied
                    img = img.convertToFormat(QImage.Format_RGBX8888)
                m.tex = self._texture(img)
            else:
                m.tex = self._blank
        if getattr(m, 'otex', None) is None:
            m.has_o = ok(m.overlay)
            if m.has_o:
                o = QOpenGLTexture(m.overlay)
                o.setMinMagFilters(QOpenGLTexture.LinearMipMapLinear, QOpenGLTexture.Linear)
                o.setWrapMode(QOpenGLTexture.ClampToEdge)
                m.otex = o
            else:
                m.otex = self._blank
        if m.ntex is None:
            m.has_n = ok(m.normal_map)
            m.ntex = self._texture(m.normal_map) if m.has_n else self._blank
        if m.rtex is None:
            m.has_r = ok(m.rough_map)
            m.rtex = self._texture(m.rough_map) if m.has_r else self._blank

    # ---------------------------------------------------------- GL
    def _program(self, vs, fs, attrs):
        p = QOpenGLShaderProgram(self)
        ok = p.addShaderFromSourceCode(QOpenGLShader.Vertex, vs) and p.addShaderFromSourceCode(QOpenGLShader.Fragment, fs)
        for i, a in enumerate(attrs):
            p.bindAttributeLocation(a, i)
        if not (ok and p.link()):
            raise RuntimeError(p.log())
        return p

    def initializeGL(self):
        try:
            self.vao = QOpenGLVertexArrayObject()
            self.vao.create()
            self.prog = self._program(VERT, FRAG, ['a_pos', 'a_nrm', 'a_uv', 'a_tan', 'a_uvn'])
            self.lines = self._program(LINE_VERT, LINE_FRAG, ['a_pos'])
            self.depth = self._program(DEPTH_VERT, DEPTH_FRAG, ['a_pos', 'a_uv'])
            self.floorp = self._program(FLOOR_VERT, FLOOR_FRAG, ['a_pos'])
            self._white = QImage(4, 4, QImage.Format_RGBA8888)
            self._white.fill(QColor('white'))
            # one stand-in for every map a mesh does not have, instead of a texture each
            self._blank = self._texture(self._white)
            self._locs.clear()
        except Exception as x:
            self.prog = None
            self.failed.emit(str(x))

    def resizeGL(self, w, h):
        pass

    _locs = {}

    @classmethod
    def _u(cls, prog, name, value):
        key = (id(prog), name)
        loc = cls._locs.get(key)
        if loc is None:
            loc = cls._locs[key] = prog.uniformLocation(name)
        if isinstance(value, bool):
            prog.setUniformValue1f(loc, 1.0 if value else 0.0)
        elif isinstance(value, float):
            prog.setUniformValue1f(loc, value)
        elif isinstance(value, int):
            prog.setUniformValue1i(loc, value)
        else:
            prog.setUniformValue(loc, value)

    def _attrs(self, prog, m, full=True):
        m.vbo.bind()
        prog.enableAttributeArray(0)
        prog.setAttributeBuffer(0, GL_FLOAT, 0, 3, STRIDE)
        if full:
            for loc, off, size in ((1, 12, 3), (2, 24, 2), (3, 32, 4), (4, 48, 2)):
                prog.enableAttributeArray(loc)
                prog.setAttributeBuffer(loc, GL_FLOAT, off, size, STRIDE)
        else:
            prog.enableAttributeArray(1)
            prog.setAttributeBuffer(1, GL_FLOAT, 24, 2, STRIDE)

    def _shadow_pass(self, f, vis, model):
        if self._shadow is None:
            fmt = QOpenGLFramebufferObjectFormat()
            fmt.setAttachment(QOpenGLFramebufferObject.Depth)
            self._shadow = QOpenGLFramebufferObject(SHADOW, SHADOW, fmt)
        self._shadow.bind()
        f.glViewport(0, 0, SHADOW, SHADOW)
        f.glClearColor(1, 1, 1, 1)
        f.glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        d = self.depth
        d.bind()
        self._u(d, 'u_mvp', self._light() * model)
        self._u(d, 'u_tex', 0)
        for m in vis:
            self._attrs(d, m, full=False)
            self._u(d, 'u_cutout', bool(self.textured and m.has_tex and m.cutout))
            m.tex.bind(0)
            f.glDrawArrays(GL_TRIANGLES, 0, m.count)
            m.vbo.release()
        d.release()
        self._shadow.release()
        f.glBindFramebuffer(GL_FRAMEBUFFER, self.defaultFramebufferObject())
        ratio = self.devicePixelRatioF()
        f.glViewport(0, 0, int(self.width() * ratio), int(self.height() * ratio))

    def paintGL(self):
        f = self.context().functions()
        bg = QColor(theme.BG)
        f.glClearColor(bg.redF(), bg.greenF(), bg.blueF(), 1)
        f.glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        if not self.prog:
            return
        vis = [m for m in self.meshes if m.visible and len(m.tris)]
        if not vis:
            return
        f.glEnable(GL_DEPTH_TEST)
        f.glDepthFunc(GL_LEQUAL)
        self.vao.bind()
        for m in vis:
            if m.vbo is None:
                self._upload(m)
            self._textures(m)
        model = self._model()
        if self.hq:
            # the light does not move with the camera, so the shadow map is only drawn again when the scene changes
            key = (self._scene, len(vis), sum(m.count for m in vis), self.textured, self.up, self.radius,
                   tuple(float(c) for c in self.center))
            if key != self._shadow_for or self._shadow is None:
                self._shadow_pass(f, vis, model)
                self._shadow_for = key
                f.glClearColor(bg.redF(), bg.greenF(), bg.blueF(), 1)
                f.glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        proj = QMatrix4x4()
        proj.perspective(50 if self.walk else 32, max(self.width(), 1) / max(self.height(), 1),
                         self.radius * (0.002 if self.walk else 0.02), self.radius * (14 if self.walk else 50))
        view, eye = self._view()
        p = self.prog
        p.bind()
        self._u(p, 'u_mvp', proj * view * model)
        self._u(p, 'u_model', model)
        self._u(p, 'u_light', self._light())
        self._u(p, 'u_eye', eye)
        self._u(p, 'u_key', self._key())
        self._u(p, 'u_hq', bool(self.hq))
        self._u(p, 'u_shadow_on', bool(self.hq))
        self._u(p, 'u_texel', 1.0 / SHADOW)
        for name, unit in (('u_tex', 0), ('u_ntex', 1), ('u_rtex', 2), ('u_shadow', 3), ('u_otex', 4)):
            self._u(p, name, unit)
        if self.hq:
            f.glActiveTexture(GL_TEXTURE0 + 3)
            f.glBindTexture(GL_TEXTURE_2D, self._shadow.texture())
            f.glActiveTexture(GL_TEXTURE0)
        last, bound = {}, {}
        for m in vis:
            self._attrs(p, m)
            c = m.color
            state = (('u_color', (c.redF(), c.greenF(), c.blueF())),
                     ('u_textured', bool(self.textured and m.has_tex)),
                     ('u_cutout', bool(self.textured and m.has_tex and m.cutout)),
                     ('u_highlight', bool(m.highlight)), ('u_has_n', bool(self.hq and m.has_n)),
                     ('u_has_r', bool(self.hq and m.has_r)), ('u_metal', float(m.metal)),
                     ('u_rough', float(m.rough)), ('u_has_o', bool(m.has_o)))
            for name, v in state:                 # only what differs from the mesh before
                if last.get(name) != v:
                    last[name] = v
                    self._u(p, name, QVector3D(*v) if isinstance(v, tuple) else v)
            for unit, t in ((0, m.tex), (1, m.ntex), (2, m.rtex), (4, m.otex)):
                if bound.get(unit) is not t:
                    bound[unit] = t
                    t.bind(unit)
            f.glDrawArrays(GL_TRIANGLES, 0, m.count)
            m.vbo.release()
        p.release()
        if not self.show_floor:
            pass
        elif self.hq:
            self._draw_floor(f, proj * view)
        else:
            self._draw_grid(f, proj * view)
        f.glActiveTexture(GL_TEXTURE0)
        self.vao.release()

    def _draw_floor(self, f, pv):
        r = self.radius * 3
        y = self._floor_y()
        data = np.array([(-r, y, -r), (r, y, -r), (r, y, r), (-r, y, -r), (r, y, r), (-r, y, r)], np.float32)
        if self._floor is None:
            self._floor = QOpenGLBuffer(QOpenGLBuffer.VertexBuffer)
            self._floor.create()
        self._floor.bind()
        self._floor.allocate(data.tobytes(), data.nbytes)
        fp = self.floorp
        fp.bind()
        self._u(fp, 'u_mvp', pv)
        self._u(fp, 'u_light', self._light())
        self._u(fp, 'u_texel', 1.0 / SHADOW)
        self._u(fp, 'u_radius', float(self.radius))
        bg = QColor(theme.BG)
        self._u(fp, 'u_bg', QVector3D(bg.redF(), bg.greenF(), bg.blueF()))
        self._u(fp, 'u_shadow', 3)
        f.glActiveTexture(GL_TEXTURE0 + 3)
        f.glBindTexture(GL_TEXTURE_2D, self._shadow.texture())
        fp.enableAttributeArray(0)
        fp.setAttributeBuffer(0, GL_FLOAT, 0, 3, 12)
        f.glDrawArrays(GL_TRIANGLES, 0, 6)
        fp.release()
        self._floor.release()

    def _draw_grid(self, f, pv):
        r = self.radius * 1.6
        step = r / 8
        y = self._floor_y()
        pts = []
        for k in range(-8, 9):
            pts += [(-r, y, k * step), (r, y, k * step), (k * step, y, -r), (k * step, y, r)]
        data = np.array(pts, np.float32)
        if self._grid is None:
            self._grid = QOpenGLBuffer(QOpenGLBuffer.VertexBuffer)
            self._grid.create()
        self._grid.bind()
        self._grid.allocate(data.tobytes(), data.nbytes)
        self.lines.bind()
        self._u(self.lines, 'u_mvp', pv)
        c = QColor(theme.LINE)
        self.lines.setUniformValue(self.lines.uniformLocation('u_color'), c.redF(), c.greenF(), c.blueF(), 1.0)
        self.lines.enableAttributeArray(0)
        self.lines.setAttributeBuffer(0, GL_FLOAT, 0, 3, 12)
        f.glDrawArrays(GL_LINES, 0, len(data))
        self.lines.release()
        self._grid.release()

    def paintEvent(self, e):
        super().paintEvent(e)
        if not any(m.visible and len(m.tris) for m in self.meshes) or not self.prog:
            from PySide6.QtGui import QPainter
            qp = QPainter(self)
            qp.setPen(QColor(theme.MUTED))
            msg = self.message if self.prog else 'This PC could not start the 3D preview (OpenGL).'
            qp.drawText(self.rect().adjusted(30, 0, -30, 0), Qt.AlignCenter | Qt.TextWordWrap, msg)
            qp.end()

    # ---------------------------------------------------------- mouse
    def mousePressEvent(self, e):
        self._drag = (e.position(), e.button(), self.yaw, self.pitch, QVector3D(self.pan))

    def mouseMoveEvent(self, e):
        if not self._drag:
            return
        p0, btn, y0, x0, pan0 = self._drag
        d = e.position() - p0
        if btn == Qt.LeftButton:
            self.yaw = y0 - d.x() * 0.008
            self.pitch = max(-1.52, min(1.52, x0 + d.y() * 0.008))
        else:
            view, _ = self._view()
            right = QVector3D(view.row(0).x(), view.row(0).y(), view.row(0).z())
            up = QVector3D(view.row(1).x(), view.row(1).y(), view.row(1).z())
            k = self.radius * self.dist / max(self.height(), 1) * 0.9
            self.pan = pan0 - right * (d.x() * k) + up * (d.y() * k)
        self.update()

    def mouseReleaseEvent(self, e):
        self._drag = None

    def mouseDoubleClickEvent(self, e):
        self.set_walk(self.walk)

    def wheelEvent(self, e):
        if self.walk:       # in fly-through the wheel moves forward and back
            view, eye = self._view()
            fwd = self.pan - eye
            if fwd.length() > 1e-6:
                fwd.normalize()
                self.pan = self.pan + fwd * (self.radius * 0.03 * (1 if e.angleDelta().y() > 0 else -1))
            self.update()
            return
        self.dist = max(0.3, min(30.0, self.dist * (0.88 if e.angleDelta().y() > 0 else 1 / 0.88)))
        self.update()

    def snapshot(self):
        return self.grabFramebuffer()


def pil_to_qimage(img):
    img = img.convert('RGBA')
    q = QImage(img.tobytes(), img.width, img.height, img.width * 4, QImage.Format_RGBA8888)
    return q.copy()


def tangents_from(t):
    """(n,4) tangent array from a decoded TANGENT attribute (xyz + handedness bits in w)."""
    if t is None:
        return None
    t = np.asarray(t, np.float32)
    out = np.zeros((len(t), 4), np.float32)
    out[:, :3] = t[:, :3]
    out[:, 3] = t[:, 3] if t.shape[1] > 3 else 1.0
    return out
