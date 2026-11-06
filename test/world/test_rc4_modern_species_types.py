"""Compile the production type resolver against legacy table types and real policy."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
# Expansion bb3fd057061cdd7e6a9e79b76abb41924ee44ecc, P_UPDATED_TYPES >= GEN_6.
# Includes family macros as well as direct MON_TYPES declarations.
FAIRY = {
    'CLEFFA': ('FAIRY', 'FAIRY'), 'CLEFAIRY': ('FAIRY', 'FAIRY'),
    'CLEFABLE': ('FAIRY', 'FAIRY'), 'IGGLYBUFF': ('NORMAL', 'FAIRY'),
    'JIGGLYPUFF': ('NORMAL', 'FAIRY'), 'WIGGLYTUFF': ('NORMAL', 'FAIRY'),
    'TOGEPI': ('FAIRY', 'FAIRY'), 'TOGETIC': ('FAIRY', 'FLYING'),
    'AZURILL': ('NORMAL', 'FAIRY'), 'MARILL': ('WATER', 'FAIRY'),
    'AZUMARILL': ('WATER', 'FAIRY'), 'SNUBBULL': ('FAIRY', 'FAIRY'),
    'GRANBULL': ('FAIRY', 'FAIRY'), 'MR_MIME': ('PSYCHIC', 'FAIRY'),
    'RALTS': ('PSYCHIC', 'FAIRY'), 'KIRLIA': ('PSYCHIC', 'FAIRY'),
    'GARDEVOIR': ('PSYCHIC', 'FAIRY'), 'MAWILE': ('STEEL', 'FAIRY'),
}


class ModernSpeciesTypesTests(unittest.TestCase):
    def test_runtime_consumers_use_resolver_without_changing_rom_branch(self):
        consumers = {
            'src/pokemon.c': 2,
            'src/battle_main.c': 4,
            'src/battle_script_commands.c': 4,
            'src/platform/world_coop.c': 2,
            'src/pokemon_summary_screen.c': 2,
        }
        for name, count in consumers.items():
            with self.subTest(source=name):
                source = (ROOT / name).read_text()
                self.assertEqual(source.count('ModernSpeciesTypes_GetType('), count)
                self.assertIn('#include "platform/modern_species_types.h"', source)
        # Keep the resolver translation unit empty for the ROM build.
        source = (ROOT / 'src/platform/modern_species_types.c').read_text()
        result = subprocess.run(['cc', '-E', '-P', '-x', 'c', '-'], input=source,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), '')

    def test_production_resolver_preserves_legacy_and_retypes_both_slots(self):
        resolver = ROOT / 'src/platform/modern_species_types.c'
        self.assertTrue(resolver.exists(), 'missing native world-gated species type resolver')
        text = (ROOT / 'src/data/pokemon/species_info.h').read_text()
        entries = re.findall(r'\[(SPECIES_\w+)\]\s*=\s*\{.*?\.types\s*=\s*\{\s*(TYPE_\w+)\s*,\s*(TYPE_\w+)\s*\}', text, re.S)
        self.assertGreater(len(entries), 380)
        fixture = '\n'.join(f'[{s}] = {{.types = {{{a}, {b}}}}},' for s, a, b in entries)
        checks = '\n'.join(
            f'assert(ModernSpeciesTypes_GetType(SPECIES_{s}, {i}) == '
            f'(modern ? TYPE_{t} : gSpeciesInfo[SPECIES_{s}].types[{i}]));'
            for s, types in FAIRY.items() for i, t in enumerate(types))
        unchanged = '\n'.join(
            f'assert(ModernSpeciesTypes_GetType({s}, {i}) == gSpeciesInfo[{s}].types[{i}]);'
            for s, _, _ in entries if s.removeprefix('SPECIES_') not in FAIRY for i in (0, 1))
        source = '''
#include "global.h"
#include "pokemon.h"
#include "constants/species.h"
#include "constants/pokemon.h"
#include "platform/modern_species_types.h"
#include "platform/world_rules.h"
#include "constants/battle.h"
#undef NDEBUG
#include <assert.h>
#include <stdlib.h>
const struct SpeciesInfo gSpeciesInfo[NUM_SPECIES] = {
''' + fixture + '''
};
u32 gBattleTypeFlags;
const u8 gTypeEffectiveness[336] = {0};
static bool8 nativeLink;
bool8 NativeLink_IsActive(void) { return nativeLink; }
int main(int argc, char **argv) {
    unsigned mask, context, linked;
    const u32 contexts[] = {0, BATTLE_TYPE_RECORDED, BATTLE_TYPE_RECORDED_LINK, BATTLE_TYPE_LINK};
    int modern;
    assert(argc == 3);
    mask = atoi(argv[1]);
    assert(WorldRules_Init(argv[2]));
    for (context = 0; context < ARRAY_COUNT(contexts); context++) {
      for (linked = 0; linked < 2; linked++) {
        gBattleTypeFlags = contexts[context];
        nativeLink = linked;
        modern = (mask & 4) && !(gBattleTypeFlags & (BATTLE_TYPE_RECORDED | BATTLE_TYPE_RECORDED_LINK))
            && (!(gBattleTypeFlags & BATTLE_TYPE_LINK) || nativeLink);
''' + checks + unchanged + '''
      }
    }
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='rc4-species-types-') as directory:
            c = Path(directory) / 'probe.c'
            exe = Path(directory) / 'probe'
            c.write_text(source)
            result = subprocess.run(['cc', '-std=gnu99', '-Wall', '-Wextra', '-Werror',
                                     '-DPORTABLE', '-DVER_64BIT', '-DMEGA_FEATURE_READY=1',
                                     '-iquote', 'include', str(c), str(resolver),
                                     'src/platform/world_rules.c', 'src/platform/expanded_moves.c', '-o', str(exe)],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            for mask in (0, 1, 4, 16, 31):
                with self.subTest(mask=mask):
                    wire = f'1:{mask}:' + '0' * 64
                    result = subprocess.run([str(exe), str(mask), wire], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
