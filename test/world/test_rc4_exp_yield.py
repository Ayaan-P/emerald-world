"""Readonly SpeciesInfo width and the actual EXP expression, not a game build."""
from pathlib import Path
import json
import re
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build/rc4-exp-yield'
STAGE = ROOT / 'build/rc4-acquisition-coverage/test55/generated'


class ExpYieldTest(unittest.TestCase):
    def compile_run(self, source, portable=True):
        OUT.mkdir(parents=True, exist_ok=True)
        for compiler in [c for c in ('gcc', 'clang') if shutil.which(c)]:
            stem = OUT / (self._testMethodName + ('-portable-' if portable else '-gba-header-') + compiler)
            cfile = stem.with_suffix('.c')
            exe = stem.with_suffix('.exe')
            cfile.write_text('''#include "global.h"
#include "pokemon.h"
#undef NDEBUG
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
''' + source)
            command = [compiler, '-std=gnu11', '-DVER_64BIT', '-DUBFIX', '-DMODERN=1',
                       '-iquote', str(ROOT / 'include'), '-fno-builtin', '-Wall', '-Wextra', '-Werror',
                       str(cfile), '-o', str(exe)]
            if portable:
                command.insert(2, '-DPORTABLE')
            stem.with_suffix('.command.json').write_text(json.dumps(command, indent=2))
            result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
            stem.with_suffix('.compile.log').write_text(result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(exe)], cwd=OUT, text=True, capture_output=True)
            stem.with_suffix('.log').write_text(result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            print(compiler + ': ' + self._testMethodName + ': ' + result.stdout.strip())

    def test_legacy_yields_and_saved_abi_native_and_gba(self):
        legacy = (ROOT / 'src/data/pokemon/species_info.h').read_text()
        values = [int(v) for v in re.findall(r'\.expYield\s*=\s*(\d+)', legacy)]
        self.assertTrue(values)
        self.assertLessEqual(max(values), 255)
        rows = ','.join('{.expYield = ' + str(v) + '}' for v in values)
        expected = ','.join(map(str, values))
        for portable in (True, False):
            self.compile_run('''static const struct SpeciesInfo rows[] = {''' + rows + '''};
static const u8 expected[] = {''' + expected + '''};
int main(void) {
    _Static_assert(sizeof(struct Pokemon) == 100, "saved party ABI");
    _Static_assert(sizeof(struct BoxPokemon) == 80, "saved box ABI");
    assert(sizeof(rows[0].expYield) == ''' + ('2' if portable else '1') + ''');
    for (unsigned i = 0; i < sizeof(expected); i++) assert(rows[i].expYield == expected[i]);
    printf("legacy yields retained=%zu, expYield width=%zu, saved ABI80/100 PASS\\n",
           sizeof(expected), sizeof(rows[0].expYield));
    return 0;
}
''', portable=portable)

    def test_native_field_bounds_and_existing_exp_local_capacity(self):
        commands = (ROOT / 'src/battle_script_commands.c').read_text()
        match = re.search(r'calculatedExp = gSpeciesInfo\[[^;]+;', commands)
        assert match is not None
        # The unchanged u16 EXP local handles every yield through 4587 at
        # levels 1..100. Full u16 catalog storage is wider than that formula's
        # output contract; do not claim arbitrary 65535-yield level100 support.
        self.compile_run('''static struct SpeciesInfo fixtureInfo[1];
#define gSpeciesInfo fixtureInfo
static struct {u16 species; u8 level;} gBattleMons[1];
static u8 gBattlerFainted;
static u16 productionExp(void) { u16 calculatedExp;
''' + match[0] + '''
return calculatedExp; }
int main(void) {
    for (unsigned yield = 0; yield <= UINT16_MAX; yield++) {
        fixtureInfo[0].expYield = yield;
        assert(fixtureInfo[0].expYield == yield);
        gBattleMons[0].level = 7;
        assert(productionExp() == yield);
    }
    unsigned maxSafe = UINT16_MAX * UINT32_C(7) / 100;
    for (unsigned yield = 0; yield <= maxSafe; yield++) {
        fixtureInfo[0].expYield = yield;
        for (unsigned level = 1; level <= 100; level++) {
            gBattleMons[0].level = level;
            uint32_t expected = (uint32_t)yield * level / 7;
            assert(expected <= UINT16_MAX);
            assert(productionExp() == expected);
        }
    }
    printf("u16 field0..65535 retained; original EXP local safe yield0..%u level1..100 PASS\\n", maxSafe);
    return 0;
}
''')

    def test_native_actual_staged_torterra_263_and_production_formula(self):
        staged = (STAGE / 'src/data/pokemon/expanded/species_info.inc').read_text()
        row = staged.split('[SPECIES_TORTERRA] = {', 1)[1].split('}', 1)[0]
        match = re.search(r'\.expYield\s*=\s*(\d+)', row)
        assert match is not None
        value = int(match[1])
        self.assertEqual(value, 263)
        commands = (ROOT / 'src/battle_script_commands.c').read_text()
        match = re.search(r'calculatedExp = gSpeciesInfo\[[^;]+;', commands)
        assert match is not None
        assignment = match[0]
        self.assertIn('u16 calculatedExp;', commands)
        self.compile_run('''const struct SpeciesInfo gSpeciesInfo[] = {{.expYield = ''' + str(value) + '''}};
static struct {u16 species; u8 level;} gBattleMons[1];
static u8 gBattlerFainted;
static u16 productionExp(void) {
    u16 calculatedExp;
    ''' + assignment + '''
    return calculatedExp;
}
int main(void) {
    assert(sizeof(gSpeciesInfo[0].expYield) == 2);
    assert(gSpeciesInfo[0].expYield == 263);
    for (unsigned level = 1; level <= 100; level++) {
        gBattleMons[0].level = level;
        uint32_t expected = UINT32_C(263) * level / 7;
        assert(expected <= UINT16_MAX);
        assert(productionExp() == expected);
    }
    printf("actual Torterra expYield=%u width=%zu; production formula levels 1..100 PASS\\n",
           gSpeciesInfo[0].expYield, sizeof(gSpeciesInfo[0].expYield));
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
