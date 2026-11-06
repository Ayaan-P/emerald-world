"""Production C seams in disposable files, not native gameplay proof."""
from pathlib import Path
import os
import struct
import subprocess
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[2]
STAGED = ROOT / 'build/rc4-catalog-growth/generated'


class ExpandedDexV2Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.save = self.folder / 'mounted.sav'
        self.sidecar = Path(str(self.save) + '.expanded-dex')
        self.exe = self.compile(True)

    def compile(self, staged):
        # Overlay only the promoted data in a disposable tree. Production sources
        # are copied unchanged. The worktree's generated files are never edited.
        tree = self.folder / ('promoted' if staged else 'current')
        platform = tree / 'src/platform'
        data = tree / 'src/data/pokemon/expanded'
        platform.mkdir(parents=True, exist_ok=True)
        data.mkdir(parents=True, exist_ok=True)
        (platform / 'expanded_species.c').write_bytes((ROOT / 'src/platform/expanded_species.c').read_bytes())
        source = STAGED if staged else ROOT
        for name in ['dex_map.inc', 'playable_cases.inc']:
            (data / name).write_bytes((source / 'src/data/pokemon/expanded' / name).read_bytes())
        harness = tree / 'fixture.c'
        harness.write_text(r'''#include "global.h"
#include "pokedex.h"
#include "platform/expanded_species.h"
#include "platform/world_rules.h"
#include "constants/maps.h"
#undef abs
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#undef NDEBUG
#include <assert.h>
struct SaveBlock2 block;
struct SaveBlock2 *gSaveBlock2Ptr = &block;
static u32 rules;
bool8 WorldRules_Enabled(u32 rule) { return (rules & rule) != 0; }
int main(int argc, char **argv) {
    unsigned int n, s;
    struct SaveBlock2 before;
    assert(argc == 6);
    memset(&block, 0x5a, sizeof(block));
    memset(block.playerTrainerId, 0, 4);
    block.playerTrainerId[0] = atoi(argv[2]);
    before = block;
    ExpandedDex_Init(argv[1], atoi(argv[5]));
    if (!strcmp(argv[3], "encounter")) {
        for (s = 0; s <= 65535; ++s) {
            rules = 0;
            assert(ExpandedSpecies_ResolveEncounter(s, MAP_GROUP(MAP_ROUTE101), MAP_NUM(MAP_ROUTE101)) == s);
            assert(ExpandedSpecies_ResolveEncounter(s, MAP_GROUP(MAP_ROUTE102), MAP_NUM(MAP_ROUTE102)) == s);
        }
        rules = WORLD_RULE_EXPANDED_ROSTER;
        assert(ExpandedSpecies_ResolveEncounter(SPECIES_POOCHYENA, MAP_GROUP(MAP_ROUTE101), MAP_NUM(MAP_ROUTE101)) == SPECIES_COSMOEM);
        assert(ExpandedSpecies_ResolveEncounter(SPECIES_WURMPLE, MAP_GROUP(MAP_ROUTE101), MAP_NUM(MAP_ROUTE101)) == SPECIES_MELTAN);
        assert(ExpandedSpecies_ResolveEncounter(SPECIES_ZIGZAGOON, MAP_GROUP(MAP_ROUTE101), MAP_NUM(MAP_ROUTE101)) == SPECIES_GIMMIGHOUL_ROAMING);
#ifdef SPECIES_TYPE_NULL
        assert(ExpandedSpecies_ResolveEncounter(SPECIES_RALTS, MAP_GROUP(MAP_ROUTE102), MAP_NUM(MAP_ROUTE102)) == SPECIES_TYPE_NULL);
#else
        assert(ExpandedSpecies_ResolveEncounter(SPECIES_RALTS, MAP_GROUP(MAP_ROUTE102), MAP_NUM(MAP_ROUTE102)) == SPECIES_RALTS);
#endif
        return 0;
    }
    n = atoi(argv[4]);
    if (!strcmp(argv[3], "seen")) ExpandedDex_GetSetFlag(n, FLAG_SET_SEEN);
    if (!strcmp(argv[3], "caught")) ExpandedDex_GetSetFlag(n, FLAG_SET_CAUGHT);
    printf("%d %d\n", ExpandedDex_GetSetFlag(n, FLAG_GET_SEEN), ExpandedDex_GetSetFlag(n, FLAG_GET_CAUGHT));
    assert(!memcmp(&before, &block, sizeof(block)));
    ExpandedDex_Reset();
    assert(!memcmp(&before, &block, sizeof(block)));
    return 0;
}
''')
        exe = tree / 'fixture'
        flags = ['gcc', '-std=gnu11', '-DPORTABLE', '-DVER_64BIT', '-DUBFIX', '-DMODERN=1',
                 '-iquote', str(ROOT / 'include'), '-iquote', str(ROOT / 'src'),
                 '-include', str(source / 'include/constants/expanded_species.h'),
                 '-include', str(source / 'include/constants/expanded_pokedex.h'),
                 '-fno-builtin', '-Wall', '-Werror']
        subprocess.run(flags + [str(harness), str(platform / 'expanded_species.c'),
                       str(ROOT / 'src/platform/expanded_dex.c'), str(ROOT / 'src/platform/native_save.c'),
                       '-o', str(exe)], check=True)
        return exe

    def run_c(self, mode='get', dex=772, trainer=1, persist=1, exe=None):
        result = subprocess.run([str(exe or self.exe), str(self.save), str(trainer), mode,
                                 str(dex), str(persist)], check=True, capture_output=True, text=True)
        return result.stdout.strip()

    def legacy(self, trainer=1, sequence=4, seen=7, caught=3):
        raw = b'EDX1' + bytes([trainer, 0, 0, 0]) + struct.pack('<I', sequence)
        raw += bytes([1, 0, 0, 0, seen, caught, 0, 0])
        return raw + struct.pack('<I', zlib.crc32(raw))

    def test_fourth_species_persists_generic_national_index(self):
        self.assertEqual(self.run_c('seen'), '1 0')
        self.assertEqual(self.run_c('caught'), '1 1')
        self.assertEqual(self.run_c(), '1 1')
        self.assertEqual(self.sidecar.stat().st_mode & 0o777, 0o600)
        self.assertIn(b'EDX2', self.sidecar.read_bytes())


    def test_first_migration_write_has_recoverable_import_snapshot(self):
        self.sidecar.write_bytes(self.legacy() * 2)
        self.sidecar.chmod(0o600)
        self.run_c('seen')
        damaged = bytearray(self.sidecar.read_bytes())
        damaged[48 + 282 + 278] ^= 1
        self.sidecar.write_bytes(damaged)
        self.assertEqual(self.run_c(dex=790), '1 1')
        self.assertEqual(self.run_c(dex=999), '1 0')
        self.assertEqual(self.run_c(), '0 0')

    def test_v2_corruption_never_resurrects_legacy_trainer(self):
        self.sidecar.write_bytes(self.legacy() * 2)
        self.sidecar.chmod(0o600)
        self.run_c('seen', trainer=2)
        self.run_c('caught', trainer=2)
        damaged = bytearray(self.sidecar.read_bytes())
        damaged[48 + 278] ^= 1
        damaged[48 + 282 + 278] ^= 1
        self.sidecar.write_bytes(damaged)
        self.assertEqual(self.run_c(dex=790, trainer=1), '0 0')

    def test_legacy_recovery_and_newest_trainer_selection(self):
        older = self.legacy(trainer=1)
        newer = self.legacy(trainer=2, sequence=5, seen=1, caught=0)
        self.sidecar.write_bytes(older + newer)
        self.sidecar.chmod(0o600)
        self.assertEqual(self.run_c(dex=790), '0 0')
        self.assertEqual(self.run_c(dex=790, trainer=2), '1 0')
        damaged = bytearray(older + newer)
        damaged[44] ^= 1
        self.sidecar.write_bytes(damaged)
        self.assertEqual(self.run_c(dex=790), '1 1')
        self.sidecar.write_bytes(older)  # complete first slot, absent second
        self.assertEqual(self.run_c(dex=999), '1 0')

    def test_future_schema_is_session_only_and_not_overwritten(self):
        self.run_c('seen')
        data = bytearray(self.sidecar.read_bytes())
        data[48 + 282:48 + 286] = b'EDX3'
        struct.pack_into('<I', data, 48 + 282 + 278,
                         zlib.crc32(data[48 + 282:48 + 282 + 278]))
        self.sidecar.write_bytes(data)
        self.assertEqual(self.run_c(), '0 0')
        self.assertEqual(self.run_c('caught'), '0 1')
        self.assertEqual(self.sidecar.read_bytes(), data)

    def test_opt_in_encounters_and_unpromoted_headers(self):
        self.run_c('encounter')
        self.run_c('encounter', exe=self.compile(False))

    def test_legacy_import_is_explicit_and_trainer_bound(self):
        legacy = self.legacy() + self.legacy(sequence=5, seen=7, caught=7)
        self.sidecar.write_bytes(legacy)
        self.sidecar.chmod(0o600)
        for dex in [790, 808, 999]:
            self.assertEqual(self.run_c(dex=dex), '1 1')
        self.assertEqual(self.sidecar.read_bytes(), legacy)  # lazy, read-only import
        self.assertEqual(self.run_c(trainer=2, dex=790), '0 0')
        self.assertEqual(self.run_c('seen'), '1 0')
        self.assertEqual(self.sidecar.read_bytes()[:48], legacy)
        for dex in [790, 808, 999]:
            self.assertEqual(self.run_c(dex=dex), '1 1')
        self.assertEqual(self.run_c('caught', trainer=2), '0 1')
        self.assertEqual(self.run_c(trainer=1), '0 0')
        self.assertEqual(self.run_c(dex=790, trainer=2), '0 0')

    def test_corrupt_newest_slot_recovers_previous(self):
        self.run_c('seen')
        self.run_c('caught')
        original = self.sidecar.read_bytes()
        self.assertEqual(len(original), 612)
        for offset in [0, 12, 16, 278]:
            damaged = bytearray(original)
            damaged[48 + offset] ^= 1  # slot zero is newest after two writes
            self.sidecar.write_bytes(damaged)
            self.assertEqual(self.run_c(), '1 0')
            self.assertEqual(self.run_c(trainer=2), '0 0')
        # A complete slot zero survives a truncated second slot too.
        self.sidecar.write_bytes(original[:48 + 282])
        self.assertEqual(self.run_c(), '1 1')

    def test_disabled_persistence_reserved_ids_and_private_files(self):
        for dex in [0, 1, 771, 1025, 1026, 65535]:
            self.assertEqual(self.run_c('caught', dex=dex), '0 0')
        self.assertEqual(self.sidecar.read_bytes(), b'')
        self.run_c('caught')
        original = self.sidecar.read_bytes()
        self.assertEqual(self.run_c(persist=0), '0 0')
        self.assertEqual(self.run_c('seen', persist=0), '1 0')
        self.assertEqual(self.sidecar.read_bytes(), original)
        self.sidecar.chmod(0o644)
        self.assertEqual(self.run_c(), '0 0')
        self.sidecar.chmod(0o600)
        import fcntl
        with self.sidecar.open('r+b') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(self.run_c(), '0 0')
        target = self.folder / 'target'
        self.sidecar.rename(target)
        self.sidecar.symlink_to(target)
        self.assertEqual(self.run_c(), '0 0')
        self.assertEqual(target.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
