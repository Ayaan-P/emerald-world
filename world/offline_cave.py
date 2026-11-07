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


def encode_wildlife(proposal, profile, rate, wildlife, *, cohort='vanilla'):
    """Build a V3 cave with 12 weighted native encounter slots."""
    from .species_cohort import species_id
    if type(rate) is not int or not 1 <= rate <= 100:
        raise ValueError('encounter rate must be 1..100')
    if type(wildlife) is not list or len(wildlife) != 12:
        raise ValueError('wildlife must contain exactly 12 slots')
    metadata = bytearray([rate])
    for slot in wildlife:
        if type(slot) is not dict or set(slot) != {'species', 'level'}:
            raise ValueError('each wildlife slot needs species and level')
        name, level = slot['species'], slot['level']
        if type(name) is not str or type(level) is not int or not 1 <= level <= 100:
            raise ValueError('invalid wildlife species or level')
        metadata.extend(species_id(name, cohort).to_bytes(2, 'little'))
        metadata.append(level)
    v2 = encode_profile(proposal, profile)
    magic = b'EWGMAP10' if cohort == 'expansion-native' else b'EWGMAP03'
    return magic + v2[8:9] + bytes(metadata) + v2[9:]
