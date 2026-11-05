"""Versioned, bounded offline cave templates with curated encounter profiles."""
from .shared_cave import SharedCave

PROFILES = {'granite': 0, 'meteor': 1, 'ice': 2, 'victory': 3}


def encode_profile(proposal, profile):
    if type(profile) is not str or profile not in PROFILES:
        raise ValueError('invalid encounter profile')
    if type(proposal) is not dict or set(proposal) != {'rows', 'spawn', 'exit'}:
        raise ValueError('invalid cave proposal')
    for key, expected in (('spawn', [1, 1]), ('exit', [29, 29])):
        value = proposal[key]
        if type(value) is not list or value != expected or any(type(n) is not int for n in value):
            raise ValueError('invalid cave endpoints')
    rows = proposal['rows']
    if type(rows) is not list or len(rows) != 31 or any(type(row) is not str or len(row) != 31 for row in rows):
        raise ValueError('invalid cave rows')
    try:
        cells = ''.join(rows).encode('ascii')
    except UnicodeEncodeError as error:
        raise ValueError('invalid cave rows') from error
    SharedCave(b'EWGMAP01' + cells)
    return b'EWGMAP02' + bytes([PROFILES[profile]]) + cells
