"""Actual C sprite contracts for the selected RC4 roster. No game build needed."""
from pathlib import Path
import subprocess
import json
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
FLAGS = ['gcc', '-std=gnu11', '-DPORTABLE', '-DVER_64BIT', '-DUBFIX', '-DMODERN=1',
         '-iquote', str(ROOT / 'include'), '-iquote', str(ROOT / 'src'),
         '-fno-builtin', '-Wall', '-Werror', '-ffunction-sections', '-fdata-sections']


class ExpandedSpriteContractTest(unittest.TestCase):
    def compile_run(self, source, modules=()):
        with tempfile.TemporaryDirectory() as folder:
            c = Path(folder) / 'fixture.c'
            exe = Path(folder) / 'fixture'
            manifest = json.loads((ROOT / 'tools/expanded/coverage.json').read_text())
            ids = sorted({row['engine_id'] for row in manifest['species'] if row['status'] == 'native_selected'})
            source = source.replace('SELECTED_SPECIES', '(' + ' || '.join('s == ' + str(i) for i in ids) + ')')
            c.write_text(source)
            result = subprocess.run(FLAGS + [str(c)] + [str(ROOT / m) for m in modules]
                                    + ['-Wl,--gc-sections', '-o', str(exe)],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(exe)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def check_animations(self, path):
        source = '''#include "global.h"
#include "sprite.h"
#undef NDEBUG
#include <assert.h>
'''
        source += '#include "' + str(path) + '"\n'
        source += 'int main(void) {\n'
        symbols = re.findall(r'sExpanded(\w+)Anims\[\]', path.read_text())
        manifest = json.loads((path.parents[4] / 'tools/expanded/coverage.json').read_text())
        self.assertEqual(len(symbols), len(manifest['playable_selection']))
        self.assertEqual(len(symbols), len(set(symbols)))
        for symbol in symbols:
            table = 'sExpanded' + symbol + 'Anims'
            source += f'''_Static_assert(ARRAY_COUNT({table}) == 2, "{symbol}: idle and entrance slots required");
for (unsigned int anim = 0; anim < ARRAY_COUNT({table}); ++anim) {{
    assert({table}[anim][0].frame.imageValue == 0);
    assert({table}[anim][0].frame.duration > 0);
    assert({table}[anim][1].type == -1);
}}
'''
        source += 'return 0; }\n'
        self.compile_run(source)

    def test_checked_in_static_sprites_have_idle_and_entrance(self):
        self.check_animations(ROOT / 'src/data/pokemon/expanded/animations.inc')

    def test_real_decompress_entrypoints_allow_only_selected_expanded_ids(self):
        source = r'''#include "global.h"
#include "pokemon.h"
#include "decompress.h"
#include "platform/expanded_species.h"
#undef NDEBUG
#include <assert.h>
static const u32 fallback, supplied, unownFront, unownBack;
const struct CompressedSpriteSheet gMonFrontPicTable[SPECIES_TABLE_COUNT] = {
    [0] = {.data = &fallback}, [SPECIES_UNOWN] = {.data = &unownFront}
};
const struct CompressedSpriteSheet gMonBackPicTable[SPECIES_TABLE_COUNT] = {
    [SPECIES_UNOWN] = {.data = &unownBack}
};
static const u32 *loaded;
void LZ77UnCompWram(const u32 *src, void *dest) { (void)dest; loaded = src; }
void DrawSpindaSpots(u16 species, u32 personality, u8 *dest, bool8 front)
{ (void)species; (void)personality; (void)dest; (void)front; }
#undef CpuSet
void CpuSet(const void *src, void *dest, u32 control)
{ (void)src; (void)dest; (void)control; }
bool8 WorldRules_Enabled(u32 rule) { (void)rule; return FALSE; }
int main(void) {
    const struct CompressedSpriteSheet pic = {.data = &supplied};
    void (*plain[])(const struct CompressedSpriteSheet *, void *, s32) = {
        DecompressPicFromTable, DecompressPicFromTable_2, DecompressPicFromTable_DontHandleDeoxys
    };
    void (*special[])(const struct CompressedSpriteSheet *, void *, s32, u32, bool8) = {
        LoadSpecialPokePic, LoadSpecialPokePic_2, LoadSpecialPokePic_DontHandleDeoxys
    };
    _Static_assert(NUM_SPECIES == 412, "legacy save ABI");
    /* Include 16-bit truncation aliases for every selected species. */
    for (s32 s = 0; s <= 65536 + SPECIES_TABLE_COUNT; ++s) {
        bool8 accepted = s <= NUM_SPECIES || SELECTED_SPECIES;
        for (unsigned int i = 0; i < ARRAY_COUNT(plain); ++i) {
            plain[i](&pic, NULL, s);
            assert(loaded == (accepted ? &supplied : &fallback));
            for (unsigned int front = 0; front <= 1; ++front) {
                special[i](&pic, NULL, s, 0, front);
                assert(loaded == (s == SPECIES_UNOWN ? (front ? &unownFront : &unownBack)
                                                   : accepted ? &supplied : &fallback));
            }
        }
    }
    return 0;
}
'''
        self.compile_run(source, ['src/decompress.c', 'src/platform/expanded_species.c'])

    def test_regenerated_static_sprites_have_idle_and_entrance(self):
        donor = ROOT.parent / 'expansion-foundation/engines/expansion-native'
        with tempfile.TemporaryDirectory() as folder:
            subprocess.run([sys.executable, str(ROOT / 'tools/expanded/import_species.py'),
                            '--donor', str(donor), '--output', folder], cwd=ROOT, check=True,
                           capture_output=True, text=True)
            generated = Path(folder) / 'src/data/pokemon/expanded/animations.inc'
            self.check_animations(generated)
            self.assertEqual(generated.read_bytes(),
                             (ROOT / 'src/data/pokemon/expanded/animations.inc').read_bytes())


if __name__ == '__main__':
    unittest.main()
