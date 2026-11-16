"""Round-trip the LE90 writer on a small synthetic database."""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from modtheshow import rosters as R  # noqa: E402


def field(name, size):
    return name.encode().ljust(22, b'\0') + struct.pack('<5H', 0, 1, size, size, 0)


def build():
    desc = b'D_TEAM_PROF'.ljust(16, b'\0') + struct.pack('<II', 4 + 32 * 2, 2) + field('CITY_NAME', 20) + \
        field('SHORT_NAME', 5)
    data = b'D_TEAM_PROF'.ljust(16, b'\0') + struct.pack('<I', 2)
    for city, short in ((b'Phoenix', b'PHX'), (b'Tucson', b'TUC')):
        data += city.ljust(20, b'\0') + short.ljust(5, b'\0')
    return b'LE906\x01\x00\x00[DESC]' + desc + b'[DATA]' + data


def test_round_trip():
    db = R.LE90(build())
    t = db.tables['D_TEAM_PROF']
    assert [r.text('CITY_NAME') for r in t] == ['Phoenix', 'Tucson']
    db.put(t[1], 'CITY_NAME', 'Sedona')
    again = R.LE90(db.bytes())
    assert again.tables['D_TEAM_PROF'][1].text('CITY_NAME') == 'Sedona'
    assert len(db.bytes()) == len(build())


if __name__ == '__main__':
    test_round_trip()
    print('ok')
