"""Execute upstream regional bytecode with the actual interpreter/save hooks.

This is source and host integration, not a full game or a travel playthrough.
No renderer, game sockets, installation or human profiles are used.
"""
from pathlib import Path
import re
import subprocess
import unittest
from test import test_rc7_region_state as state

ENGINE = state.ENGINE
ROOT = state.ROOT


class KantoContent(state.RegionStateIntegration):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.constants = cls.generated / 'constants'
        cls.preproc = cls.directory / 'preproc'
        cls.run_command(['g++', '-std=c++11', '-O1',
                         *[f'tools/preproc/{n}.cpp' for n in
                           ('asm_file', 'c_file', 'charmap', 'preproc', 'string_parser', 'utf8', 'io')],
                         '-o', str(cls.preproc)])
        cls.run_command([str(cls.directory / 'jsonproc'), 'src/data/heal_locations.json',
                         'src/data/heal_locations.constants.json.txt', str(cls.constants / 'heal_locations.h')])
        cls.run_command([str(cls.directory / 'mapjson'), 'layouts', 'combined',
                         'data/layouts/layouts.json', str(cls.directory / 'asm'), str(cls.constants)])
        cls.run_command([str(cls.directory / 'mapjson'), 'event_constants', 'emerald',
                         *map(str, sorted((ENGINE / 'data/maps').glob('*/map.json'))),
                         str(cls.constants / 'map_event_ids.h')])
        # The upstream generator writes to its working directory. Keep all
        # generated headers here instead of modifying the source checkout.
        (cls.directory / 'data').symlink_to(ENGINE / 'data', target_is_directory=True)
        subprocess.run(['python3', str(ENGINE / 'tools/misc/make_scr_cmd_constants.py')],
                       cwd=cls.directory, check=True, capture_output=True, text=True)
        cls.asm_flags = ['-DMODERN=1', '-DPLATFORM_NATIVE=1', '-DPORTABLE=1', '-DEMERALD',
                         '-DTESTING=0', f'-I{cls.generated}', f'-I{cls.constants}', '-Iinclude']

    @classmethod
    def assemble(cls, source, output, enabled):
        data = cls.run_command([str(cls.preproc), '-s', str(source), 'charmap.txt'])
        commands = [
            ['gcc', '-E', '-x', 'assembler-with-cpp', *cls.asm_flags,
             f'-DEW_REGION_STATE={enabled}', f'-DEW_KANTO_CONTENT={enabled}', '-'],
            [str(cls.preproc), '-ie', str(source), 'charmap.txt'],
            ['python3', '-I', 'platform/build_glue/asm_filter.py', '--pointer-size', '8'],
        ]
        for command in commands:
            result = subprocess.run(command, cwd=ENGINE, input=data, capture_output=True,
                                    text=True, timeout=120)
            if result.returncode:
                raise AssertionError(result.stderr)
            data = result.stdout
        result = subprocess.run(['as', '--64', '--noexecstack', '--defsym', 'MODERN=1',
                                 '--defsym', 'EMERALD=1', '--defsym', 'PLATFORM_NATIVE=1',
                                 '--defsym', 'NATIVE_POINTER_SIZE_8=1', '-o', str(output)],
                                cwd=ENGINE, input=data, text=True, capture_output=True, timeout=120)
        if result.returncode:
            raise AssertionError(result.stderr)
        if result.stderr:
            raise AssertionError('Unexpected assembler warning: ' + result.stderr)

    def test_full_combined_script_object(self):
        self.run_command(['python3', '-I', 'platform/build_glue/asm_filter.py', '--self-test'])
        for enabled in (0, 1):
            obj = self.directory / f'full-scripts-{enabled}.o'
            self.assemble(ENGINE / 'data/event_scripts.s', obj, enabled)
            symbols = self.run_command(['nm', '--defined-only', str(obj)])
            self.assertIn('LittlerootTown_MapScripts', symbols)
            self.assertEqual('PalletTown_Frlg_MapScripts' in symbols, bool(enabled))

    def test_upstream_entry_scripts_and_save_roundtrip(self):
        root = (ENGINE / 'data/event_scripts.s').read_text().split('\t.section script_data', 1)[0]
        root += '\n.section script_data, "aw", %progbits\n'
        defaults = (ENGINE / 'data/scripts/new_game.inc').read_text().split('EventScript_ResetAllMapFlagsFrlg::', 1)[1]
        root += 'EventScript_ResetAllMapFlagsFrlg::' + defaults
        pallet = (ENGINE / 'data/maps/PalletTown_Frlg/scripts.inc').read_text()
        root += pallet.split('PalletTown_Frlg_MapScripts::', 1)[0]
        root += 'PalletTown_OnTransition::' + pallet.split('PalletTown_OnTransition::', 1)[1].split('PalletTown_OnFrame::', 1)[0]
        common = (ENGINE / 'data/event_scripts.s').read_text()
        # The shared no-op return is taken verbatim, not an interpreter stub.
        nop = re.search(r'Common_EventScript_NopReturn::\s*\n\s*return\b', common)
        self.assertIsNotNone(nop)
        root += '\n' + nop[0] + '\n'
        root += ('\nTestMapScripts::\n\tmap_script MAP_SCRIPT_ON_TRANSITION, PalletTown_OnTransition\n\t.byte 0\n'
                 '\nTestCompareRegional::\n\tcompare VAR_MAP_SCENE_PALLET_TOWN_OAK, VAR_MAP_SCENE_VIRIDIAN_CITY_OLD_MAN\n\tend\n')
        source = self.directory / 'selected.s'
        source.write_text(root)
        script = self.directory / 'selected.o'
        self.assemble(source, script, 1)
        obj = self.directory / 'story.o'
        binary = self.directory / 'story'
        self.run_command(['gcc', *self.flags, '-DEW_REGION_STATE=1', '-DEW_KANTO_CONTENT=1',
                          *self.game_includes, '-c', 'tests/rc8/region_content.c', '-o', str(obj)])
        self.run_command(['gcc', *self.flags, '-DEW_REGION_STATE=1', '-DEW_KANTO_CONTENT=1',
                          '-Iplatform', '-idirafter', 'include', '-iquote', '.', *self.link,
                          str(obj), str(script), *self.platform, '-o', str(binary)])
        self.assertIn('trainer isolation passed', self.run_command([str(binary)]))

    def test_named_flag_mappings_match_original_firered_ids(self):
        flags = (ENGINE / 'include/constants/flags.h').read_text()
        names = re.findall(r'^#define\s+(FLAG_\w+)\s+KANTO_SCENE_FLAG\(', flags, re.M)
        self.assertEqual(len(names), 762)
        source = self.directory / 'flag-values.c'
        source.write_text('#include <stdio.h>\n#include "constants/global.h"\n#include "constants/flags.h"\n'
                          'int main(void) {\n' + ''.join(f'printf("%u\\n", {n});\n' for n in names) + 'return 0;}\n')
        values = []
        for version, enabled in (('FIRERED', 0), ('EMERALD', 1)):
            binary = self.directory / f'flag-values-{version}'
            self.run_command(['gcc', '-std=gnu17', '-DPORTABLE=1', f'-D{version}',
                              f'-DEW_REGION_STATE={enabled}', '-iquote', 'include',
                              str(source), '-o', str(binary)])
            values.append(list(map(int, self.run_command([str(binary)]).split())))
        self.assertEqual(values[1], [v + 0x1000 for v in values[0]])
        self.assertLess(max(values[1]), 0x1FFF)

    def test_named_variable_mappings_preserve_original_ids(self):
        variables = (ENGINE / 'include/constants/vars_frlg.h').read_text()
        names = re.findall(r'^#define\s+(VAR_\w+)\s+KANTO_SCENE_VAR\(', variables, re.M)
        self.assertEqual(len(names), 211)
        source = self.directory / 'var-values.c'
        source.write_text('#include <stdio.h>\n#include "constants/vars.h"\n'
                          'int main(void) {\n' + ''.join(f'printf("%u\\n", {n});\n' for n in names) + 'return 0;}\n')
        values = []
        for enabled in (0, 1):
            binary = self.directory / f'var-values-{enabled}'
            self.run_command(['gcc', '-std=gnu17', '-DPORTABLE=1', '-DEMERALD',
                              f'-DEW_REGION_STATE={enabled}', '-iquote', 'include',
                              str(source), '-o', str(binary)])
            values.append(list(map(int, self.run_command([str(binary)]).split())))
        self.assertEqual(values[1], [v + 0x1000 for v in values[0]])
        self.assertLess(max(values[1]), 0x5100)

    def test_both_tileset_cohorts_are_selected(self):
        for name, hoenn, kanto in (
                ('headers', 'gTileset_Petalburg', 'gTileset_General_Frlg'),
                ('graphics', 'gTilesetTiles_Petalburg', 'gTilesetTiles_General_Frlg'),
                ('metatiles', 'gMetatiles_Petalburg', 'gMetatiles_General_Frlg')):
            for enabled in (0, 1):
                source = self.directory / 'tilesets.c'
                source.write_text('#include "global.h"\n#include "src/data/tilesets/' + name + '.h"\n')
                result = self.run_command(['gcc', '-E', *self.flags, f'-DEW_REGION_STATE={enabled}',
                                           f'-DEW_KANTO_CONTENT={enabled}', *self.game_includes, str(source)])
                self.assertRegex(result, r'\b' + hoenn + r'\s*(?:\[.*?\])?\s*=')
                self.assertEqual(bool(re.search(r'\b' + kanto + r'\s*(?:\[.*?\])?\s*=', result)), bool(enabled))

    def test_content_flag_requires_regional_state(self):
        result = subprocess.run(['python3', str(ROOT / 'scripts/build_expansion.py'), '--development', '--kanto-content'],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn('--kanto-content requires --regional-state', result.stderr)


if __name__ == '__main__':
    unittest.main()
