"""Model engine checks that need no game files: vertex formats, chunk padding, OBJ reading."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import numpy as np  # noqa: E402

from modtheshow import modellib  # noqa: E402

LAYOUT = """<InputLayout name="Test">
 <BufferDesc name="Positions">
  <AttributeDesc name="Position" semantic="POSITION">
   <ComponentDesc format="kFloat_16"/><ComponentDesc format="kFloat_16"/>
   <ComponentDesc format="kFloat_16"/><ComponentDesc format="kFloat_16"/>
  </AttributeDesc>
  <AttributeDesc name="Color" semantic="COLOR">
   <ComponentDesc format="kFP_0_0_8"/><ComponentDesc format="kFP_0_0_8"/>
   <ComponentDesc format="kFP_0_0_8"/><ComponentDesc format="kFP_0_0_8"/>
  </AttributeDesc>
 </BufferDesc>
 <BufferDesc name="VertexData">
  <AttributeDesc name="Normal" semantic="NORMAL">
   <ComponentDesc format="kFP_1_0_9"/><ComponentDesc format="kFP_1_0_9"/>
   <ComponentDesc format="kFP_1_0_9"/><ComponentDesc format="kFP_0_0_2"/>
  </AttributeDesc>
  <AttributeDesc name="UV" semantic="TEXCOORD">
   <ComponentDesc format="kFloat_32"/><ComponentDesc format="kFloat_32"/>
  </AttributeDesc>
 </BufferDesc>
</InputLayout>"""


def test_layout_and_formats():
    name, bufs = modellib.parse_layout(LAYOUT)
    assert name == 'Test'
    assert [b.stride for b in bufs] == [12, 12]
    rng = np.random.default_rng(1)
    n = 50
    pos = np.column_stack([rng.uniform(-2, 2, (n, 3)), np.ones(n)])
    col = rng.uniform(0, 1, (n, 4))
    nrm = rng.normal(size=(n, 3))
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
    nrm = np.column_stack([nrm, rng.integers(0, 4, n)])
    uv = rng.uniform(0, 1, (n, 2))
    s0 = np.zeros((n, 12), np.uint8)
    s1 = np.zeros((n, 12), np.uint8)
    bufs[0].attrs[0].encode(pos, s0, 12)
    bufs[0].attrs[1].encode(col, s0, 12)
    bufs[1].attrs[0].encode(nrm, s1, 12)
    bufs[1].attrs[1].encode(uv, s1, 12)
    assert np.abs(bufs[0].attrs[0].decode(s0.tobytes(), 12, n) - pos).max() < 2e-3
    assert np.abs(bufs[0].attrs[1].decode(s0.tobytes(), 12, n) - col).max() < 3e-3
    got = bufs[1].attrs[0].decode(s1.tobytes(), 12, n)
    assert np.abs(got[:, :3] - nrm[:, :3]).max() < 3e-3
    assert (got[:, 3] == nrm[:, 3]).all()
    assert np.abs(bufs[1].attrs[1].decode(s1.tobytes(), 12, n) - uv).max() < 1e-6


def test_chunk_padding():
    # vertex data always gets 1-16 zero bytes, index data 0-15, then 0xAD up to an aligned next data start
    for size in (1, 15, 16, 17, 255, 256, 1000):
        for tag in (b'VOID_VBO', b'VOID_EBO'):
            at = 0x1F0
            c = modellib._chunk(tag, 1, b'\x11' * size, at, 0x100)
            zeros = (-size % 16) if tag == b'VOID_EBO' else 16 - size % 16
            body = c[0x10:]
            assert body[size:size + zeros] == b'\0' * zeros
            assert set(body[size + zeros:]) <= {0xAD}
            assert (at + len(c) + 0x10) % 0x100 == 0


def test_read_obj():
    d = tempfile.mkdtemp()
    p = os.path.join(d, 'q.obj')
    with open(p, 'w') as f:
        f.write('v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nvt 0 0\nvt 1 0\nvt 1 1\nvt 0 1\nf 1/1 2/2 3/3 4/4\n')
    P, N, T, tris = modellib.read_obj(p)
    assert P.shape == (4, 3) and tris.shape == (2, 3)
    assert np.allclose(N, [0, 0, 1])
    assert np.allclose(T[2], [1, 0])          # v flipped into the game's convention
    t = modellib._tangents(P, N, T, tris)
    assert np.allclose(np.abs(t[:, 0]), 1, atol=1e-5)


if __name__ == '__main__':
    test_layout_and_formats()
    test_chunk_padding()
    test_read_obj()
    print('model tests passed')
