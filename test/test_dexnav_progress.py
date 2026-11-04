"""Parent-only RC3 codec tests. Compiles exact pure C helpers, never game/profile I/O.

Not executed by the DexNav implementation worker. Requires only the native C
compiler already used by this project, no Python package dependencies.
"""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def c_function(source, name):
    match = re.search(r'static\s+\w+\s+' + name + r'\([^;{]*\)\s*\{', source)
    if match is None:
        raise AssertionError('Missing real C helper: ' + name)
    end = match.end()
    depth = 1
    while depth:
        if source[end] == '{':
            depth += 1
        elif source[end] == '}':
            depth -= 1
        end += 1
    return source[match.start():end]


class DexNavProgressTests(unittest.TestCase):
    def test_actual_c_codec_and_journal_recovery(self):
        source = (ROOT / 'src/platform/dexnav_native.c').read_text()
        header = (ROOT / 'include/dexnav.h').read_text()
        enum_match = re.search(r'enum EncounterType\s*\{.*?\};', header, re.S)
        mask_match = re.search(r'^#define DEXNAV_MASK_SPECIES\s+\S+', header, re.M)
        assert enum_match is not None and mask_match is not None
        enum = enum_match.group()
        mask = mask_match.group()
        prelude = '''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "constants/species.h"
typedef uint8_t u8;
typedef uint16_t u16;
typedef int16_t s16;
typedef uint32_t u32;
typedef uint8_t bool8;
#define FALSE 0
#define PROGRESS_SIZE (16 + NUM_SPECIES)
'''
        actual_helpers = '\n'.join(c_function(source, name) for name in
                                   ('ProgressChecksum', 'ValidProgress', 'ProgressSequence', 'NewestProgressSlot'))
        harness = r'''
static void Seal(u8 *record)
{
    u16 sum = ProgressChecksum(record);
    record[PROGRESS_SIZE - 2] = sum & 255;
    record[PROGRESS_SIZE - 1] = sum >> 8;
}
static void Record(u8 *record, u16 species, u16 sequence)
{
    memset(record, 0, PROGRESS_SIZE);
    memcpy(record, "DNV2", 4);
    record[8] = NUM_SPECIES & 255; record[9] = NUM_SPECIES >> 8;
    record[10] = species & 255; record[11] = species >> 8;
    record[12] = sequence & 255; record[13] = sequence >> 8;
    record[14 + SPECIES_TREECKO] = 5;
    Seal(record);
}
int main(void)
{
    u8 journal[2][PROGRESS_SIZE] = {{0}};
    assert(NewestProgressSlot(journal) == 255);
    Record(journal[0], SPECIES_TREECKO, 65535);
    assert(ValidProgress(journal[0]));
    assert(ProgressSequence(journal[0]) == 65535);
    assert(NewestProgressSlot(journal) == 0);
    Record(journal[1], (ENCOUNTER_TYPE_WATER << 14) | SPECIES_WINGULL, 0);
    assert(NewestProgressSlot(journal) == 1); /* sequence wraps */
    journal[1][14 + SPECIES_TREECKO] ^= 1;
    assert(!ValidProgress(journal[1]));
    assert(NewestProgressSlot(journal) == 0); /* torn latest commit */
    Record(journal[1], NUM_SPECIES, 1);
    assert(!ValidProgress(journal[1])); /* bounds, not checksum */
    Record(journal[1], (ENCOUNTER_TYPE_HIDDEN << 14) | SPECIES_TREECKO, 1);
    assert(!ValidProgress(journal[1])); /* no hidden provider at compatibility stage */
    Record(journal[1], SPECIES_NONE, 1);
    assert(ValidProgress(journal[1]));
    journal[1][8] ^= 1; Seal(journal[1]);
    assert(!ValidProgress(journal[1])); /* species ABI mismatch */
    Record(journal[1], SPECIES_TREECKO, 1);
    journal[1][0] ^= 1; Seal(journal[1]);
    assert(!ValidProgress(journal[1])); /* unknown format */
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='dexnav-codec-') as directory:
            path = Path(directory)
            (path / 'codec.c').write_text(prelude + enum + '\n' + mask + '\n' + actual_helpers + harness)
            subprocess.run([os.environ.get('CC', 'cc'), '-std=c99', '-Wall', '-Wextra', '-Werror',
                            '-I', str(ROOT / 'include'), str(path / 'codec.c'), '-o', str(path / 'codec')], check=True)
            subprocess.run([str(path / 'codec')], check=True)


if __name__ == '__main__':
    unittest.main()
