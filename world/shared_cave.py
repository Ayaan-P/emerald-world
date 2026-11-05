"""Bounded, immutable generated cave geometry for an experimental authority.

The authenticated world server is the only distributor. No peer may publish a
map. The identity is an integrity hint for an authenticated channel, not an
independent signature or permission grant.
"""
from collections import deque
from hashlib import sha256
from .cave_species import SPECIES

SIDE = 31
MAGIC = b'EWGMAP01'
MAGIC_PROFILE = b'EWGMAP02'
MAGIC_WILDLIFE = b'EWGMAP03'
MAGIC_LARGE = b'EWGMAP04'
MAGIC_LARGE_WILDLIFE = b'EWGMAP05'
LARGE_SIDE = 63
SIZE = len(MAGIC) + SIDE * SIDE
PROFILE_SIZE = SIZE + 1
WILDLIFE_BYTES = 37
WILDLIFE_SIZE = PROFILE_SIZE + WILDLIFE_BYTES
LARGE_SIZE = 8 + LARGE_SIDE * LARGE_SIDE
MAX_SIZE = LARGE_SIZE + 1 + WILDLIFE_BYTES


class CaveError(ValueError):
    pass


class SharedCave:
    def __init__(self, blob):
        if type(blob) is not bytes:
            raise CaveError('invalid cave template')
        self.wildlife = None
        self.version = 1
        self.side = SIDE
        if len(blob) == SIZE and blob[:8] == MAGIC:
            self.profile = None
            cells = blob[8:]
        elif len(blob) == PROFILE_SIZE and blob[:8] == MAGIC_PROFILE and blob[8] <= 3:
            self.version = 2
            self.profile = blob[8]
            cells = blob[9:]
        elif ((len(blob) == WILDLIFE_SIZE and blob[:8] == MAGIC_WILDLIFE)
              or (len(blob) == MAX_SIZE and blob[:8] == MAGIC_LARGE_WILDLIFE)) and blob[8] <= 3:
            self.version = 5 if blob[:8] == MAGIC_LARGE_WILDLIFE else 3
            if self.version == 5: self.side = LARGE_SIDE
            self.profile = blob[8]
            self.wildlife = blob[9:9 + WILDLIFE_BYTES]
            if not 1 <= self.wildlife[0] <= 100:
                raise CaveError('invalid wildlife rate')
            for i in range(12):
                offset = 1 + i * 3
                species = int.from_bytes(self.wildlife[offset:offset + 2], 'little')
                if species not in SPECIES.values() or not 1 <= self.wildlife[offset + 2] <= 100:
                    raise CaveError('invalid wildlife slot')
            cells = blob[9 + WILDLIFE_BYTES:]
        elif len(blob) == LARGE_SIZE and blob[:8] == MAGIC_LARGE:
            self.version = 4
            self.profile = None
            self.side = LARGE_SIDE
            cells = blob[8:]
        else:
            raise CaveError('invalid cave template')
        if any(c not in (ord('.'), ord('#')) for c in cells):
            raise CaveError('invalid cave cell')
        rows = tuple(cells[y * self.side:(y + 1) * self.side] for y in range(self.side))
        if (any(c != ord('#') for c in rows[0] + rows[-1])
                or any(row[0] != ord('#') or row[-1] != ord('#') for row in rows)):
            raise CaveError('open boundary')
        if any(rows[y][x] != ord('.') for x, y in ((1, 1), (self.side - 2, self.side - 3), (self.side - 2, self.side - 2))):
            raise CaveError('invalid entrance or exit')
        queue = deque([(1, 1)])
        seen = {(1, 1)}
        while queue:
            x, y = queue.popleft()
            for nx, ny in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)):
                if (0 <= nx < self.side and 0 <= ny < self.side and rows[ny][nx] == ord('.')
                        and (nx, ny) not in seen):
                    seen.add((nx, ny))
                    queue.append((nx, ny))
        if len(seen) != cells.count(b'.'):
            raise CaveError('disconnected cave')
        self._rows = rows
        self.identity = sha256(blob).hexdigest()

    def walkable(self, x, y):
        return type(x) is int and type(y) is int and 0 <= x < self.side and 0 <= y < self.side and self._rows[y][x] == ord('.')

    def frames(self):
        suffix = '' if self.profile is None else f' {self.profile}'
        if self.version == 3: suffix += ' 3'
        if self.version == 4: suffix = ' LARGE'
        if self.version == 5: suffix += ' 5'
        frames = [f'CAVE BEGIN {self.identity}{suffix}']
        if self.wildlife is not None:
            frames.append(f'CAVE WILD {self.identity} {self.wildlife.hex()}')
        frames.extend(f'CAVE ROW {self.identity} {i} {row.decode("ascii")}' for i, row in enumerate(self._rows))
        frames.append(f'CAVE END {self.identity}')
        return '\n'.join(frames) + '\n'
