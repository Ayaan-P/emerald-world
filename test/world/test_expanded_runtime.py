"""Compiled RC4 runtime boundary tests, without building the game."""
from pathlib import Path
import re
import json
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
FLAGS = ['gcc', '-std=gnu11', '-DPORTABLE', '-DVER_64BIT', '-DUBFIX', '-DMODERN=1',
         '-iquote', str(ROOT / 'include'), '-iquote', str(ROOT / 'src'),
         '-fno-builtin', '-Wall', '-Werror']


def function(source, name):
    match = re.search(r'^\w[^\n]*\b' + re.escape(name) + r'\([^;]*?\)\n\{', source, re.M)
    if match is None:
        raise ValueError(name)
    start = match.start()
    brace = match.end() - 1
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


class ExpandedRuntimeTest(unittest.TestCase):
    def compile(self, folder, source, modules):
        c = Path(folder) / 'fixture.c'
        exe = Path(folder) / 'fixture'
        manifest = json.loads((ROOT / 'tools/expanded/coverage.json').read_text())
        ids = sorted({row['engine_id'] for row in manifest['species'] if row['status'] == 'native_selected'})
        source = source.replace('SELECTED_SPECIES', '(' + ' || '.join('s == ' + str(i) for i in ids) + ')')
        c.write_text(source)
        subprocess.run(FLAGS + [str(c)] + [str(ROOT / m) for m in modules]
                       + ['-o', str(exe)], check=True, cwd=ROOT)
        return exe

    def test_clamps_keep_only_selected_runtime_species(self):
        harness = '''#include "global.h"
#include "platform/expanded_species.h"
#undef NDEBUG
#include <assert.h>
bool8 WorldRules_Enabled(u32 rule) { (void)rule; return FALSE; }
int main(void) {
    unsigned int s;
    for (s = 0; s <= 65535; ++s) {
        bool8 selected = SELECTED_SPECIES;
        assert(ExpandedSpecies_Clamp(s) == (s <= SPECIES_EGG || selected ? s : SPECIES_NONE));
        assert(ExpandedSpecies_ClampIcon(s) == (s <= SPECIES_UNOWN_QMARK || selected ? s : SPECIES_OLD_UNOWN_J));
        assert(ExpandedSpecies_LegacyAnimSpecies(s) == (s > 0 && s < NUM_SPECIES ? s : SPECIES_BULBASAUR));
    }
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as folder:
            exe = self.compile(folder, harness, ['src/platform/expanded_species.c'])
            subprocess.run([str(exe)], check=True)

    def test_real_icon_bodies_accept_selected_and_clamp_reserved(self):
        source = (ROOT / 'src/pokemon_icon.c').read_text()
        harness = '''#include "global.h"
#include "platform/expanded_species.h"
#undef NDEBUG
#include <assert.h>
#define INVALID_ICON_SPECIES SPECIES_OLD_UNOWN_J
u16 GetUnownLetterByPersonality(u32 p) { (void)p; return 0; }
bool8 WorldRules_Enabled(u32 rule) { (void)rule; return FALSE; }
const u8 gMonIconPaletteIndices[SPECIES_TABLE_COUNT] = {[440]=3,[845]=4,[863]=5};
'''
        harness += function(source, 'GetIconSpecies') + '\n' + function(source, 'GetValidMonIconPalIndex')
        harness += '''
int main(void) {
    assert(GetIconSpecies(440, 0) == 440);
    assert(GetIconSpecies(845, 0) == 845);
    assert(GetIconSpecies(863, 0) == 863);
    assert(GetValidMonIconPalIndex(440) == 3);
    assert(GetValidMonIconPalIndex(845) == 4);
    assert(GetValidMonIconPalIndex(863) == 5);
    assert(GetIconSpecies(441, 0) == INVALID_ICON_SPECIES);
    assert(GetIconSpecies(65535, 0) == INVALID_ICON_SPECIES);
    assert(GetValidMonIconPalIndex(65535) == 0);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as folder:
            exe = self.compile(folder, harness, ['src/platform/expanded_species.c'])
            subprocess.run([str(exe)], check=True)

    def test_dex_restart_trainer_binding_and_legacy_memory(self):
        source = (ROOT / 'src/pokedex.c').read_text()
        harness = '''#include "global.h"
#include "pokedex.h"
#include "constants/pokedex.h"
#include "platform/expanded_species.h"
#undef abs
#include <stdlib.h>
#include <string.h>
#undef NDEBUG
#include <assert.h>
struct SaveBlock1 block1;
struct SaveBlock2 block2;
struct SaveBlock1 *gSaveBlock1Ptr = &block1;
struct SaveBlock2 *gSaveBlock2Ptr = &block2;
bool8 WorldRules_Enabled(u32 rule) { (void)rule; return FALSE; }
'''
        harness += function(source, 'GetSetPokedexFlag') + '\n' + function(source, 'GetNationalPokedexCount')
        harness += '''
int main(int argc, char **argv) {
    u8 seen[sizeof(block2.pokedex.seen)], owned[sizeof(block2.pokedex.owned)];
    u16 ids[] = {790, 808, 999};
    unsigned int i;
    u16 beforeSeen, beforeCaught;
    assert(argc == 5);
    block2.playerTrainerId[0] = atoi(argv[2]);
    memset(block2.pokedex.seen, 0x5a, sizeof(seen));
    memset(block2.pokedex.owned, 0x5a, sizeof(owned));
    memset(block1.seen1, 0x5a, sizeof(block1.seen1));
    memset(block1.seen2, 0x5a, sizeof(block1.seen2));
    memcpy(seen, block2.pokedex.seen, sizeof(seen));
    memcpy(owned, block2.pokedex.owned, sizeof(owned));
    ExpandedDex_Init(argv[1], atoi(argv[4]));
    if (argv[3][0] == 'p') {
        unsigned int seenMask = 0, caughtMask = 0;
        for (i = 0; i < 3; ++i) {
            seenMask |= GetSetPokedexFlag(ids[i], FLAG_GET_SEEN) << i;
            caughtMask |= GetSetPokedexFlag(ids[i], FLAG_GET_CAUGHT) << i;
        }
        printf("%u %u\\n", seenMask, caughtMask);
    } else if (argv[3][0] == 'w') {
        beforeSeen = GetNationalPokedexCount(FLAG_GET_SEEN);
        beforeCaught = GetNationalPokedexCount(FLAG_GET_CAUGHT);
        for (i = 0; i < 3; ++i) {
            assert(!GetSetPokedexFlag(ids[i], FLAG_GET_SEEN));
            GetSetPokedexFlag(ids[i], FLAG_SET_SEEN);
            assert(GetSetPokedexFlag(ids[i], FLAG_GET_SEEN));
            assert(!GetSetPokedexFlag(ids[i], FLAG_GET_CAUGHT));
            GetSetPokedexFlag(ids[i], FLAG_SET_CAUGHT);
            assert(GetSetPokedexFlag(ids[i], FLAG_GET_CAUGHT));
        }
        assert(GetNationalPokedexCount(FLAG_GET_SEEN) == beforeSeen + 3);
        assert(GetNationalPokedexCount(FLAG_GET_CAUGHT) == beforeCaught + 3);
    } else {
        for (i = 0; i < 3; ++i) {
            assert(GetSetPokedexFlag(ids[i], FLAG_GET_SEEN) == (argv[3][0] == 'r'));
            assert(GetSetPokedexFlag(ids[i], FLAG_GET_CAUGHT) == (argv[3][0] == 'r'));
        }
    }
    for (i = NATIONAL_DEX_COUNT + 1; i <= 65535; ++i)
        if (ExpandedSpecies_FromNationalDexNumber(i) == SPECIES_NONE)
            assert(!GetSetPokedexFlag(i, FLAG_SET_CAUGHT));
    assert(!GetSetPokedexFlag(0, FLAG_SET_SEEN));
    assert(!GetSetPokedexFlag(999, 255));
    assert(!memcmp(seen, block2.pokedex.seen, sizeof(seen)));
    assert(!memcmp(owned, block2.pokedex.owned, sizeof(owned)));
    ExpandedDex_Reset();
    if (argv[3][0] != 'p') {
        bool8 expected = argv[3][0] == 'w' || argv[3][0] == 'r';
        for (i = 0; i < 3; ++i)
            assert(GetSetPokedexFlag(ids[i], FLAG_GET_CAUGHT) == expected);
        block2.playerTrainerId[0] ^= 0x80;
        for (i = 0; i < 3; ++i) {
            assert(!GetSetPokedexFlag(ids[i], FLAG_GET_SEEN));
            assert(!GetSetPokedexFlag(ids[i], FLAG_GET_CAUGHT));
        }
    }
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as folder:
            exe = self.compile(folder, harness, ['src/platform/expanded_species.c',
                               'src/platform/expanded_dex.c', 'src/platform/native_save.c'])
            save = str(Path(folder) / 'mounted.sav')
            for trainer, mode, persist in [(1, 'w', 1), (1, 'r', 1), (2, 'n', 1), (1, 'r', 1)]:
                subprocess.run([str(exe), save, str(trainer), mode, str(persist)], check=True)
            # Explicit session-only mode must not read disk metadata.
            subprocess.run([str(exe), save, '1', 'n', '0'], check=True)
            sidecar = Path(save + '.expanded-dex')
            original = sidecar.read_bytes()
            self.assertEqual(len(original), 612)
            self.assertEqual(sidecar.stat().st_mode & 0o777, 0o600)
            # Corrupt newest slot: previous valid seen/caught state survives.
            damaged = bytearray(original)
            damaged[48 + 278] ^= 1
            sidecar.write_bytes(damaged)
            result = subprocess.run([str(exe), save, '1', 'p', '1'], check=True, capture_output=True, text=True)
            self.assertEqual(result.stdout.strip(), '7 3')
            # A partial first slot must not invalidate a complete second slot.
            for length in range(282):
                torn = bytearray(original)
                torn[48 + length:48 + 282] = bytes(282 - length)
                sidecar.write_bytes(torn)
                result = subprocess.run([str(exe), save, '1', 'p', '1'], check=True, capture_output=True, text=True)
                self.assertEqual(result.stdout.strip(), '7 3')
            sidecar.write_bytes(original[:48 + 282])
            subprocess.run([str(exe), save, '1', 'r', '1'], check=True)
            sidecar.write_bytes(original)
            sidecar.chmod(0o644)
            subprocess.run([str(exe), save, '1', 'n', '1'], check=True, capture_output=True)
            sidecar.chmod(0o600)
            import fcntl
            with sidecar.open('r+b') as locked:
                fcntl.flock(locked, fcntl.LOCK_EX | fcntl.LOCK_NB)
                subprocess.run([str(exe), save, '1', 'n', '1'], check=True, capture_output=True)
            alias = Path(folder) / 'alias.sav.expanded-dex'
            alias.symlink_to(sidecar)
            subprocess.run([str(exe), str(Path(folder) / 'alias.sav'), '1', 'n', '1'], check=True, capture_output=True)
            # New trainer records replace ownership, not merge old trainer bits.
            subprocess.run([str(exe), save, '2', 'w', '1'], check=True)
            subprocess.run([str(exe), save, '1', 'n', '1'], check=True)
            # Exercise the Windows session-only branch on this Linux host.
            c = Path(folder) / 'fixture.c'
            win_exe = Path(folder) / 'windows_branch'
            subprocess.run(FLAGS + ['-D_WIN32', str(c), str(ROOT / 'src/platform/expanded_species.c'),
                           str(ROOT / 'src/platform/expanded_dex.c'), '-o', str(win_exe)], check=True)
            subprocess.run([str(win_exe), save, '1', 'w', '1'], check=True)
            subprocess.run([str(win_exe), save, '1', 'n', '1'], check=True)

    def test_runtime_elevation_extern_matches_real_table(self):
        harness = '''#include "global.h"
#include "pokemon.h"
#include "sprite.h"
#include "data.h"
#include "data/pokemon_graphics/enemy_mon_elevation.h"
_Static_assert(sizeof(gEnemyMonElevation) == SPECIES_TABLE_COUNT, "runtime elevation bound");
int main(void) { return 0; }
'''
        with tempfile.TemporaryDirectory() as folder:
            exe = self.compile(folder, harness, [])
            subprocess.run([str(exe)], check=True)

    def test_species_table_entrypoints_reject_reserved_ids(self):
        source = (ROOT / 'src/pokemon.c').read_text()
        harness = '''#include "global.h"
#include "pokemon.h"
#include "platform/expanded_species.h"
#undef NDEBUG
#include <assert.h>
u8 gLastUsedAbility;
const struct SpeciesInfo gSpeciesInfo[SPECIES_TABLE_COUNT] = {
    [0] = {.abilities = {42, 43}, .genderRatio = MON_GENDERLESS, .noFlip = TRUE},
    [440] = {.abilities = {50, 51}, .genderRatio = MON_GENDERLESS},
    [845] = {.abilities = {52, 53}, .genderRatio = MON_GENDERLESS},
    [863] = {.abilities = {54, 55}, .genderRatio = MON_GENDERLESS},
};
bool8 WorldRules_Enabled(u32 rule) { (void)rule; return FALSE; }
'''
        harness += '\n'.join(function(source, n) for n in ['GetAbilityBySpecies',
                            'GetGenderFromSpeciesAndPersonality', 'IsMonSpriteNotFlipped'])
        harness += '''
int main(void) {
    unsigned int s;
    assert(GetAbilityBySpecies(441, 0) == 42);
    assert(GetAbilityBySpecies(440, 0) == 50);
    assert(GetAbilityBySpecies(845, 1) == 53);
    assert(GetAbilityBySpecies(863, 0) == 54);
    for (s = NUM_SPECIES + 1; s <= 65535; ++s) {
        if (!ExpandedSpecies_IsPlayable(s)) {
            assert(GetGenderFromSpeciesAndPersonality(s, 0) == MON_GENDERLESS);
            assert(GetAbilityBySpecies(s, 1) == 43);
            assert(IsMonSpriteNotFlipped(s));
        }
    }
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as folder:
            exe = self.compile(folder, harness, ['src/platform/expanded_species.c'])
            subprocess.run([str(exe)], check=True)

    def test_learnset_entrypoint_fails_closed_for_reserved_species(self):
        source = (ROOT / 'src/pokemon.c').read_text()
        harness = '''#include "global.h"
#include "pokemon.h"
#include "platform/expanded_species.h"
#include "constants/moves.h"
#undef NDEBUG
#include <assert.h>
static const u16 learnset[] = {(1 << 9) | MOVE_TACKLE, LEVEL_UP_END};
const u16 *const gLevelUpLearnsets[SPECIES_TABLE_COUNT] = {[440] = learnset, [845] = learnset, [863] = learnset};
bool8 WorldRules_Enabled(u32 rule) { (void)rule; return FALSE; }
'''
        harness += function(source, 'GetLevelUpMovesBySpecies')
        harness += '''
int main(void) {
    u16 moves[MAX_LEVEL_UP_MOVES];
    assert(GetLevelUpMovesBySpecies(441, moves) == 0);
    assert(GetLevelUpMovesBySpecies(65535, moves) == 0);
    assert(GetLevelUpMovesBySpecies(440, moves) == 1 && moves[0] == MOVE_TACKLE);
    assert(GetLevelUpMovesBySpecies(845, moves) == 1);
    assert(GetLevelUpMovesBySpecies(863, moves) == 1);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as folder:
            exe = self.compile(folder, harness, ['src/platform/expanded_species.c'])
            subprocess.run([str(exe)], check=True)

    def test_real_conversion_bodies_are_bounded(self):
        source = (ROOT / 'src/pokemon.c').read_text()
        tables = source[source.index('static const u16 sSpeciesToHoennPokedexNum'):source.index('// Assigns all species to the National')]
        tables += source[source.index('static const u16 sSpeciesToNationalPokedexNum'):source.index('// Assigns all Hoenn')]
        tables += source[source.index('static const u16 sHoennToNationalOrder'):source.index('static const u16 sHoennToNationalOrder') + source[source.index('static const u16 sHoennToNationalOrder'):].index('};') + 2]
        names = ['HoennPokedexNumToSpecies', 'NationalPokedexNumToSpecies', 'NationalToHoennOrder',
                 'SpeciesToNationalPokedexNum', 'SpeciesToHoennPokedexNum', 'HoennToNationalOrder', 'SpeciesToCryId']
        harness = '''#include "global.h"
#include "constants/pokedex.h"
#include "platform/expanded_species.h"
#undef NDEBUG
#include <assert.h>
#define SPECIES_TO_HOENN(name) [SPECIES_##name - 1] = HOENN_DEX_##name
#define SPECIES_TO_NATIONAL(name) [SPECIES_##name - 1] = NATIONAL_DEX_##name
#define HOENN_TO_NATIONAL(name) [HOENN_DEX_##name - 1] = NATIONAL_DEX_##name
const u16 gSpeciesIdToCryId[140] = {0};
bool8 WorldRules_Enabled(u32 rule) { (void)rule; return FALSE; }
'''
        harness += tables + '\n' + '\n'.join(function(source, n) for n in names)
        harness += '''
int main(void) {
    unsigned int s;
    assert(SpeciesToNationalPokedexNum(440) == 999);
    assert(SpeciesToNationalPokedexNum(845) == 790);
    assert(SpeciesToNationalPokedexNum(863) == 808);
    assert(NationalPokedexNumToSpecies(999) == 440);
    assert(NationalPokedexNumToSpecies(790) == 845);
    assert(NationalPokedexNumToSpecies(808) == 863);
    assert(SpeciesToNationalPokedexNum(SPECIES_TREECKO) == NATIONAL_DEX_TREECKO);
    for (s = 0; s <= 65535; ++s) {
        if (s >= NUM_SPECIES) {
            assert(SpeciesToHoennPokedexNum(s) == 0);
            if (!ExpandedSpecies_IsPlayable(s)) assert(SpeciesToNationalPokedexNum(s) == 0);
            assert(SpeciesToCryId(s) == 0);
        }
        if (s >= NUM_SPECIES) assert(HoennToNationalOrder(s) == 0);
    }
    assert(!ExpandedSpecies_IsPlayable(441));
    assert(!ExpandedSpecies_IsPlayable(65535));
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as folder:
            exe = self.compile(folder, harness, ['src/platform/expanded_species.c'])
            subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    unittest.main()
