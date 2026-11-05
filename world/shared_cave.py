"""Bounded, immutable generated cave geometry for an experimental authority.

The authenticated world server is the only distributor. No peer may publish a
map. The identity is an integrity hint for an authenticated channel, not an
independent signature or permission grant.
"""
from collections import deque
from hashlib import sha256

SIDE = 31
MAGIC = b'EWGMAP01'
MAGIC_PROFILE = b'EWGMAP02'
SIZE = len(MAGIC) + SIDE * SIDE
MAX_SIZE = SIZE + 1


class CaveError(ValueError):
    pass


class SharedCave:
    def __init__(self, blob):
        if type(blob) is not bytes:
            raise CaveError('invalid cave template')
        if len(blob) == SIZE and blob[:8] == MAGIC:
            self.profile = None
            cells = blob[8:]
        elif len(blob) == MAX_SIZE and blob[:8] == MAGIC_PROFILE and blob[8] <= 3:
            self.profile = blob[8]
            cells = blob[9:]
        else:
            raise CaveError('invalid cave template')
        if any(c not in (ord('.'), ord('#')) for c in cells):
            raise CaveError('invalid cave cell')
        rows = tuple(cells[y * SIDE:(y + 1) * SIDE] for y in range(SIDE))
        if (any(c != ord('#') for c in rows[0] + rows[-1])
                or any(row[0] != ord('#') or row[-1] != ord('#') for row in rows)):
            raise CaveError('open boundary')
        if any(rows[y][x] != ord('.') for x, y in ((1, 1), (29, 28), (29, 29))):
            raise CaveError('invalid entrance or exit')
        queue = deque([(1, 1)])
        seen = {(1, 1)}
        while queue:
            x, y = queue.popleft()
            for nx, ny in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)):
                if (0 <= nx < SIDE and 0 <= ny < SIDE and rows[ny][nx] == ord('.')
                        and (nx, ny) not in seen):
                    seen.add((nx, ny))
                    queue.append((nx, ny))
        if len(seen) != cells.count(b'.'):
            raise CaveError('disconnected cave')
        self._rows = rows
        self.identity = sha256(blob).hexdigest()

    def walkable(self, x, y):
        return type(x) is int and type(y) is int and 0 <= x < SIDE and 0 <= y < SIDE and self._rows[y][x] == ord('.')

    def frames(self):
        suffix = '' if self.profile is None else f' {self.profile}'
        frames = [f'CAVE BEGIN {self.identity}{suffix}']
        frames.extend(f'CAVE ROW {self.identity} {i} {row.decode("ascii")}' for i, row in enumerate(self._rows))
        frames.append(f'CAVE END {self.identity}')
        return '\n'.join(frames) + '\n'
