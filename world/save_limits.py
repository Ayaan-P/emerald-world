"""Bound opaque save copying by engine; native loaders still validate format/ABI.

Expansion v1: 28-byte header + 128 KiB flash. PENSAV2 additionally carries an
8-byte length/CRC envelope and two bounded native-extension snapshots.
Keep these limits aligned with platform/save_file.h and save_extension.h.
"""
FLASH_BYTES = 131072
EXPANSION_HEADER_BYTES = 28
EXPANSION_EXTENSION_BYTES = 8 + 2 * (12 + 8192)
EXPANSION_SAVE_MAX = EXPANSION_HEADER_BYTES + FLASH_BYTES + 8 + EXPANSION_EXTENSION_BYTES


def save_size_limit(engine):
    if engine == 'vanilla':
        return FLASH_BYTES
    if engine == 'expansion-native':
        return EXPANSION_SAVE_MAX
    raise ValueError('Unsupported save engine')


def encoded_save_limit(engine):
    return 4 * ((save_size_limit(engine) + 2) // 3)


def save_size_label(engine):
    return '128 KiB' if engine == 'vanilla' else f'{save_size_limit(engine):,} bytes'
