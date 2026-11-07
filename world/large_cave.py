"""Bounded, offline-only large native cave format (no generated code)."""
from collections import deque

SIDE = 63
MAGIC = b'EWGMAP04'

def encode(proposal):
    if type(proposal) is not dict or set(proposal) != {'rows', 'spawn', 'exit'}:
        raise ValueError('invalid proposal')
    if proposal['spawn'] != [1, 1] or proposal['exit'] != [61, 61]:
        raise ValueError('invalid endpoints')
    if any(type(n) is not int for key in ('spawn', 'exit') for n in proposal[key]):
        raise ValueError('invalid coordinate')
    rows = proposal['rows']
    if type(rows) is not list or len(rows) != SIDE or any(type(r) is not str or len(r) != SIDE or set(r) - {'.', '#'} for r in rows):
        raise ValueError('invalid rows')
    if any(c != '#' for c in rows[0] + rows[-1]) or any(r[0] != '#' or r[-1] != '#' for r in rows):
        raise ValueError('open boundary')
    if any(rows[y][x] != '.' for x,y in ((1,1), (61,60), (61,61))):
        raise ValueError('invalid entrance or exit')
    seen={(1,1)}; queue=deque([(1,1)])
    while queue:
        x,y=queue.popleft()
        for nx,ny in ((x,y-1),(x+1,y),(x,y+1),(x-1,y)):
            if 0 <= nx < SIDE and 0 <= ny < SIDE and rows[ny][nx] == '.' and (nx,ny) not in seen:
                seen.add((nx,ny));queue.append((nx,ny))
    if len(seen) != sum(row.count('.') for row in rows):
        raise ValueError('disconnected cave')
    return MAGIC + ''.join(rows).encode('ascii')


def encode_wildlife(proposal, profile, rate, wildlife, *, cohort='vanilla'):
    """Combine large geometry with a bounded 12-slot native wildlife table."""
    from .offline_cave import PROFILES
    from .species_cohort import species_id
    if type(profile) is not str or profile not in PROFILES:
        raise ValueError('invalid visual profile')
    if type(rate) is not int or not 1 <= rate <= 100:
        raise ValueError('invalid encounter rate')
    if type(wildlife) is not list or len(wildlife) != 12:
        raise ValueError('wildlife must contain 12 slots')
    metadata=bytearray([rate])
    for slot in wildlife:
        if type(slot) is not dict or set(slot) != {'species','level'}:
            raise ValueError('invalid wildlife slot')
        name,level=slot['species'],slot['level']
        if type(name) is not str or type(level) is not int or not 1 <= level <= 100:
            raise ValueError('invalid wildlife species or level')
        metadata.extend(species_id(name, cohort).to_bytes(2,'little'));metadata.append(level)
    magic = b'EWGMAP11' if cohort == 'expansion-native' else b'EWGMAP05'
    return magic + bytes([PROFILES[profile]]) + bytes(metadata) + encode(proposal)[8:]
