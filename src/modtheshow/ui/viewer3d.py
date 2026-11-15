"""GPU model viewer: textured, smooth-lit, full detail. Orbit with the left button, pan with right or middle, wheel to
zoom, double-click to frame the model again."""
import math

import numpy as np
from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMatrix4x4, QSurfaceFormat, QVector3D
from PySide6.QtOpenGL import (QOpenGLBuffer, QOpenGLShader, QOpenGLShaderProgram, QOpenGLTexture,
                              QOpenGLVertexArrayObject)
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from . import theme

GL_FLOAT, GL_TRIANGLES, GL_LINES = 0x1406, 0x0004, 0x0001
GL_DEPTH_TEST, GL_CULL_FACE, GL_BLEND, GL_MULTISAMPLE = 0x0B71, 0x0B44, 0x0BE2, 0x809D
GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT = 0x4000, 0x0100
GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA, GL_LEQUAL = 0x0302, 0x0303, 0x0203

VERT = """
attribute vec3 a_pos;
attribute vec3 a_nrm;
attribute vec2 a_uv;
uniform mat4 u_mvp;
uniform mat4 u_model;
varying vec3 v_nrm;
varying vec3 v_pos;
varying vec2 v_uv;
void main() {
    v_nrm = (u_model * vec4(a_nrm, 0.0)).xyz;
    v_pos = (u_model * vec4(a_pos, 1.0)).xyz;
    v_uv = a_uv;
    gl_Position = u_mvp * vec4(a_pos, 1.0);
}
"""

FRAG = """
varying vec3 v_nrm;
varying vec3 v_pos;
varying vec2 v_uv;
uniform sampler2D u_tex;
uniform vec3 u_color;
uniform vec3 u_eye;
uniform float u_textured;
uniform float u_cutout;
uniform float u_highlight;
void main() {
    vec4 t = texture2D(u_tex, v_uv);
    if (u_cutout > 0.5 && t.a < 0.35) discard;
    vec3 base = mix(u_color, t.rgb, u_textured);
    vec3 n = v_nrm;
    if (dot(n, n) < 0.01) n = cross(dFdx(v_pos), dFdy(v_pos));
    n = normalize(n);
    vec3 v = normalize(u_eye - v_pos);
    if (dot(n, v) < 0.0) n = -n;
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
    """What the viewer draws: positions/normals/uvs per vertex, triangles, and a texture or a flat colour."""

    def __init__(self, pos, nrm, uv, tris, color='#c9c2b0', image=None, visible=True, cutout=False):
        self.pos, self.nrm, self.uv, self.tris = pos, nrm, uv, tris
        self.color, self.image, self.visible, self.cutout = QColor(color), image, visible, cutout
        self.highlight = False
        self.vbo = self.tex = None
        self.count = 0


class ModelView3D(QOpenGLWidget):
    failed = Signal(str)

    def __init__(self):
        super().__init__()
        fmt = QSurfaceFormat()
        fmt.setDepthBufferSize(24)
        fmt.setSamples(4)
        self.setFormat(fmt)
        self.setMinimumHeight(320)
        self.meshes = []
        self._pending = None
        self.message = 'Pick a model on the left'
        self.textured = True
        self.up = 'y'
        self.prog = self.lines = None
        self._grid = None
        self._drag = None
        self.center, self.radius, self.floor = np.zeros(3, np.float32), 1.0, 0.0
        self.reset()

    # ---------------------------------------------------------- camera
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

    # ---------------------------------------------------------- data
    def set_meshes(self, meshes, message='', up='y', keep_camera=False):
        self.makeCurrent()
        for m in self.meshes:
            self._free(m)
        self.doneCurrent()
        self.meshes = meshes
        self.message = message
        self.up = up
        self._frame()
        if not keep_camera:
            self.reset()
        self.update()

    def set_visible(self, i, on):
        if 0 <= i < len(self.meshes):
            self.meshes[i].visible = on
            self.update()

    def set_highlight(self, i):
        for k, m in enumerate(self.meshes):
            m.highlight = k == i
        self.update()

    def set_textured(self, on):
        self.textured = on
        self.update()

    def _free(self, m):
        if m.vbo:
            m.vbo.destroy()
        if m.tex:
            m.tex.destroy()
        m.vbo = m.tex = None

    def _upload(self, m):
        t3 = m.tris.reshape(-1, 3)
        tris = t3[(t3 < len(m.pos)).all(1)].reshape(-1) if len(t3) else t3.reshape(-1)
        n = m.nrm if m.nrm is not None and len(m.nrm) == len(m.pos) else np.zeros_like(m.pos)
        uv = m.uv if m.uv is not None and len(m.uv) == len(m.pos) else np.zeros((len(m.pos), 2), np.float32)
        data = np.hstack([m.pos[tris], n[tris], uv[tris]]).astype(np.float32)
        m.count = len(tris)
        m.vbo = QOpenGLBuffer(QOpenGLBuffer.VertexBuffer)
        m.vbo.create()
        m.vbo.bind()
        m.vbo.allocate(data.tobytes(), data.nbytes)
        m.vbo.release()
        img = m.image if isinstance(m.image, QImage) and not m.image.isNull() else self._white
        m.tex = QOpenGLTexture(img.mirrored(False, False))
        m.tex.setMinMagFilters(QOpenGLTexture.LinearMipMapLinear, QOpenGLTexture.Linear)
        m.tex.setWrapMode(QOpenGLTexture.Repeat)
        m.has_tex = img is not self._white

    # ---------------------------------------------------------- GL
    def initializeGL(self):
        try:
            self.vao = QOpenGLVertexArrayObject()
            self.vao.create()
            self.prog = QOpenGLShaderProgram(self)
            ok = (self.prog.addShaderFromSourceCode(QOpenGLShader.Vertex, VERT) and
                  self.prog.addShaderFromSourceCode(QOpenGLShader.Fragment, FRAG))
            self.prog.bindAttributeLocation('a_pos', 0)
            self.prog.bindAttributeLocation('a_nrm', 1)
            self.prog.bindAttributeLocation('a_uv', 2)
            ok = ok and self.prog.link()
            self.lines = QOpenGLShaderProgram(self)
            ok = ok and self.lines.addShaderFromSourceCode(QOpenGLShader.Vertex, LINE_VERT) and \
                self.lines.addShaderFromSourceCode(QOpenGLShader.Fragment, LINE_FRAG)
            self.lines.bindAttributeLocation('a_pos', 0)
            ok = ok and self.lines.link()
            if not ok:
                raise RuntimeError(self.prog.log() + self.lines.log())
            self._white = QImage(4, 4, QImage.Format_RGBA8888)
            self._white.fill(QColor('white'))
        except Exception as x:
            self.prog = None
            self.failed.emit(str(x))

    def resizeGL(self, w, h):
        pass

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
        proj = QMatrix4x4()
        proj.perspective(32, max(self.width(), 1) / max(self.height(), 1), self.radius * 0.02, self.radius * 50)
        view, eye = self._view()
        model = self._model()
        mvp = proj * view * model
        self.prog.bind()
        self.prog.setUniformValue(self.prog.uniformLocation('u_mvp'), mvp)
        self.prog.setUniformValue(self.prog.uniformLocation('u_model'), model)
        self.prog.setUniformValue(self.prog.uniformLocation('u_tex'), int(0))
        self.prog.setUniformValue(self.prog.uniformLocation('u_eye'), eye)
        for m in vis:
            if m.vbo is None:
                self._upload(m)
            m.vbo.bind()
            self.prog.enableAttributeArray(0)
            self.prog.enableAttributeArray(1)
            self.prog.enableAttributeArray(2)
            self.prog.setAttributeBuffer(0, GL_FLOAT, 0, 3, 32)
            self.prog.setAttributeBuffer(1, GL_FLOAT, 12, 3, 32)
            self.prog.setAttributeBuffer(2, GL_FLOAT, 24, 2, 32)
            c = m.color
            self.prog.setUniformValue(self.prog.uniformLocation('u_color'), QVector3D(c.redF(), c.greenF(), c.blueF()))
            self.prog.setUniformValue1f(self.prog.uniformLocation('u_textured'), 1.0 if (self.textured and m.has_tex) else 0.0)
            self.prog.setUniformValue1f(self.prog.uniformLocation('u_cutout'), 1.0 if (self.textured and m.has_tex and m.cutout) else 0.0)
            self.prog.setUniformValue1f(self.prog.uniformLocation('u_highlight'), 1.0 if m.highlight else 0.0)
            m.tex.bind(0)
            f.glDrawArrays(GL_TRIANGLES, 0, m.count)
            m.tex.release()
            m.vbo.release()
        self.prog.release()
        self._draw_grid(f, proj * view)
        self.vao.release()

    def _draw_grid(self, f, pv):
        r = self.radius * 1.6
        step = r / 8
        y = (self.floor - (self.center[1] if self.up == 'y' else self.center[2]))
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
        self.lines.setUniformValue(self.lines.uniformLocation('u_mvp'), pv)
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
        self.reset()

    def wheelEvent(self, e):
        self.dist = max(0.3, min(30.0, self.dist * (0.88 if e.angleDelta().y() > 0 else 1 / 0.88)))
        self.update()

    def snapshot(self):
        return self.grabFramebuffer()


def pil_to_qimage(img):
    img = img.convert('RGBA')
    q = QImage(img.tobytes(), img.width, img.height, img.width * 4, QImage.Format_RGBA8888)
    return q.copy()


_ = QPointF   # keep the import list stable for PyInstaller's analysis
