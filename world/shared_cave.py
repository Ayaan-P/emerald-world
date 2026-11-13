"""Bounded, immutable generated cave geometry for an experimental authority.

The authenticated world server is the only distributor. No peer may publish a
map. The identity is an integrity hint for an authenticated channel, not an
independent signature or permission grant.
"""
from collections import deque
from hashlib import sha256
from .species_cohort import contains_species_id

SIDE = 31
MAGIC = b'EWGMAP01'
MAGIC_PROFILE = b'EWGMAP02'
MAGIC_WILDLIFE = b'EWGMAP03'
MAGIC_LARGE = b'EWGMAP04'
MAGIC_LARGE_WILDLIFE = b'EWGMAP05'
MAGIC_WILDS = b'EWGMAP06'
MAGIC_GUIDED_WILDS = b'EWGMAP07'
MAGIC_CAST_WILDS = b'EWGMAP08'
MAGIC_EVENT_WILDS = b'EWGMAP09'
MAGIC_XL_WILDS = b'EWGMAP0A'
MAGIC_XL_PAINT = b'EWGMAP1A'
XL_SIDE = 127
XL_SIZE = 8 + XL_SIDE * XL_SIDE
MAGIC_EXPANSION_WILDLIFE = b'EWGMAP10'
MAGIC_EXPANSION_LARGE_WILDLIFE = b'EWGMAP11'
LARGE_SIDE = 63
SIZE = len(MAGIC) + SIDE * SIDE
PROFILE_SIZE = SIZE + 1
WILDLIFE_BYTES = 37
WILDLIFE_SIZE = PROFILE_SIZE + WILDLIFE_BYTES
LARGE_SIZE = 8 + LARGE_SIDE * LARGE_SIDE
LARGE_WILDLIFE_SIZE = LARGE_SIZE + 1 + WILDLIFE_BYTES
GUIDE_BYTES = 59
CAST_BYTES = 184
EVENT_BYTES = 1466
MAX_SIZE = max(XL_SIZE, LARGE_SIZE + CAST_BYTES + EVENT_BYTES)
EVENT_SIZE = LARGE_SIZE + CAST_BYTES + EVENT_BYTES


class CaveError(ValueError):
    pass


class SharedCave:
    def __init__(self, blob):
        if type(blob) is not bytes:
            raise CaveError('invalid cave template')
        self.palette = None
        self.wildlife = None
        self.guide = None
        self.cast = None
        self.events = None
        self.version = 1
        self.cohort = 'vanilla'
        self.side = SIDE
        if len(blob) == SIZE and blob[:8] == MAGIC:
            self.profile = None
            cells = blob[8:]
        elif len(blob) == PROFILE_SIZE and blob[:8] == MAGIC_PROFILE and blob[8] <= 3:
            self.version = 2
            self.profile = blob[8]
            cells = blob[9:]
        elif ((len(blob) == WILDLIFE_SIZE and blob[:8] == MAGIC_WILDLIFE)
              or (len(blob) == LARGE_WILDLIFE_SIZE and blob[:8] in (MAGIC_LARGE_WILDLIFE, MAGIC_EXPANSION_LARGE_WILDLIFE))
              or (len(blob) == WILDLIFE_SIZE and blob[:8] == MAGIC_EXPANSION_WILDLIFE)) and blob[8] <= 3:
            self.version = 5 if blob[:8] in (MAGIC_LARGE_WILDLIFE, MAGIC_EXPANSION_LARGE_WILDLIFE) else 3
            if blob[:8] == MAGIC_EXPANSION_WILDLIFE:
                self.cohort = 'expansion-native'
            elif blob[:8] == MAGIC_EXPANSION_LARGE_WILDLIFE:
                self.cohort = 'expansion-native'; self.version = 11
            if self.version in (5, 11): self.side = LARGE_SIDE
            if self.cohort == 'expansion-native': self.version = 10 if self.side == SIDE else 11
            self.profile = blob[8]
            self.wildlife = blob[9:9 + WILDLIFE_BYTES]
            if not 1 <= self.wildlife[0] <= 100:
                raise CaveError('invalid wildlife rate')
            for i in range(12):
                offset = 1 + i * 3
                species = int.from_bytes(self.wildlife[offset:offset + 2], 'little')
                if not contains_species_id(species, self.cohort) or not 1 <= self.wildlife[offset + 2] <= 100:
                    raise CaveError('invalid wildlife slot')
            cells = blob[9 + WILDLIFE_BYTES:]
        elif len(blob) == XL_SIZE and blob[:8] == MAGIC_XL_WILDS:
            self.version = 16; self.side = XL_SIDE; self.profile = None
            cells = blob[8:]
        elif len(blob) == XL_SIZE and blob[:8] == MAGIC_XL_PAINT:
            self.version = 17; self.side = XL_SIDE; self.profile = None
            self.palette = blob[8:]
            if any(c not in b'#.tsgr' for c in self.palette): raise CaveError('invalid outdoor palette')
            if any(self.palette[y*XL_SIDE+x] != ord('.') for x,y in ((1,1),(125,124),(125,125))): raise CaveError('invalid entrance or exit')
            cells = bytes(ord('#') if c in b'#r' else ord('.') for c in self.palette)
        elif len(blob) == EVENT_SIZE and blob[:8] == MAGIC_EVENT_WILDS:
            from .wilds_events import validate_wire
            self.version = 9; self.side = LARGE_SIDE; self.profile = None
            self.events = blob[8:8 + EVENT_BYTES];self.cast = blob[8 + EVENT_BYTES:8 + EVENT_BYTES + CAST_BYTES];cells = blob[8 + EVENT_BYTES + CAST_BYTES:]
            try: validate_wire(self.events, self.cast, cells)
            except ValueError as exc: raise CaveError(str(exc)) from None
        elif len(blob) == LARGE_SIZE + CAST_BYTES and blob[:8] == MAGIC_CAST_WILDS:
            from .wilds_cast import validate_wire
            self.version = 8; self.side = LARGE_SIDE; self.profile = None
            self.cast = blob[8:8 + CAST_BYTES]; cells = blob[8 + CAST_BYTES:]
            try: validate_wire(self.cast, cells)
            except ValueError as exc: raise CaveError(str(exc)) from None
        elif len(blob) == LARGE_SIZE + GUIDE_BYTES and blob[:8] == MAGIC_GUIDED_WILDS:
            from .wilds_guide import validate_wire
            self.version = 7; self.side = LARGE_SIDE; self.profile = None
            self.guide = blob[8:8 + GUIDE_BYTES]; cells = blob[8 + GUIDE_BYTES:]
            try: validate_wire(self.guide, cells)
            except ValueError as exc: raise CaveError(str(exc)) from None
        elif len(blob) == LARGE_SIZE and blob[:8] in (MAGIC_LARGE, MAGIC_WILDS):
            self.version = 6 if blob[:8] == MAGIC_WILDS else 4
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
        return type(x) is int and type(y) is int and 0 <= x < self.side and 0 <= y < self.side and (self.version != 7 or (x,y) != (2,1)) and (self.version not in (8,9) or (x,y) not in ((2,1),(20,20),(40,40))[:self.cast[0]]) and self._rows[y][x] == ord('.')

    def frames(self, terrain=None, terrain_large=False):
        suffix = '' if self.profile is None else f' {self.profile}'
        if self.version in (3, 10): suffix += f' {self.version}'
        if self.version == 4: suffix = ' LARGE'
        if self.version in (5, 11): suffix += f' {self.version}'
        if self.version == 6: suffix = ' WILDS'
        if self.version == 7: suffix = ' GUIDE'
        if self.version == 8: suffix = ' CAST'
        if self.version == 9: suffix = ' EVENTS'
        if self.version == 16: suffix = ' XLWILDS'
        if self.version == 17: suffix = ' XLPAINT'
        frames = [f'CAVE BEGIN {self.identity}{suffix}']
        if self.wildlife is not None:
            frames.append(f'CAVE WILD {self.identity} {self.wildlife.hex()}')
        if self.cast is not None:
            frames.append(f'CAVE CAST {self.identity} {self.cast.hex()}')
        if self.events is not None:
            for index in range(6):
                frames.append(f'CAVE EVENTS {self.identity} {index} {self.events[index*256:(index+1)*256].hex()}')
        if self.guide is not None:
            frames.append(f'CAVE GUIDE {self.identity} {self.guide.hex()}')
        if terrain is not None:
            revision,payload=terrain
            from .shared_terrain import frames as terrain_frames
            frames.extend(terrain_frames(self.identity,revision,payload,terrain_large).splitlines())
        rows = (tuple(self.palette[i*self.side:(i+1)*self.side] for i in range(self.side)) if self.palette is not None else self._rows)
        frames.extend(f'CAVE ROW {self.identity} {i} {row.decode("ascii")}' for i, row in enumerate(rows))
        frames.append(f'CAVE END {self.identity}')
        return '\n'.join(frames) + '\n'
