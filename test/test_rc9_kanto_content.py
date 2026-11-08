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

    def test_upstream_trainer_tables_and_saved_defeat_hooks(self):
        trainerproc = self.directory / 'trainerproc'
        self.run_command(['gcc', '-O1', 'tools/trainerproc/main.c', '-o', str(trainerproc)])
        table_dir = self.generated / 'data'
        table_dir.mkdir(exist_ok=True)
        for name in ('trainers', 'trainers_frlg', 'battle_partners'):
            party = f'src/data/{name}.party'
            data = self.run_command(['gcc', '-E', '-x', 'c', '-traditional-cpp', '-DEMERALD', party])
            result = subprocess.run([str(trainerproc), '-o', str(table_dir / f'{name}.h'), '-i', party, '-'],
                                    cwd=ENGINE, input=data, text=True, capture_output=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stderr)
        # The trainer definitions and table-selection guards are copied verbatim
        # from the real data translation unit; avoid unrelated graphic blobs.
        data_source = (ENGINE / 'src/data.c').read_text()
        tables = data_source.split('#if !TESTING\nconst struct Trainer gTrainers', 1)[1]
        tables = '#if !TESTING\nconst struct Trainer gTrainers' + tables.split('#include "data/trainer_approach_music.h"', 1)[0]
        prefix = '\n'.join(line for line in data_source.splitlines() if line.startswith('#include'))
        prefix = '\n'.join(line for line in prefix.splitlines() if not line.startswith('#include "data/'))
        source = self.directory / 'trainer-tables.c'
        source.write_text(prefix + '\n' + tables + '\nconst struct Trainer gBattlePartners[DIFFICULTY_COUNT][PARTNER_COUNT] = {\n#include "data/battle_partners.h"\n};\n')
        flags = [*self.flags, '-DEW_REGION_STATE=1', '-DEW_KANTO_CONTENT=1', *self.game_includes]
        data = self.run_command(['gcc', '-E', *flags, str(source)])
        result = subprocess.run([str(self.preproc), '-i', str(source), 'charmap.txt'], cwd=ENGINE,
                                input=data, text=True, capture_output=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        processed = self.directory / 'trainer-tables.i'
        processed.write_text(result.stdout)
        table_obj = self.directory / 'trainer-tables.o'
        self.run_command(['gcc', *self.flags, '-c', str(processed), '-o', str(table_obj)])
        # Compile the exact remaining lookup functions with only their headers,
        # avoiding unrelated graphics and generated Pokemon learnset blobs.
        def function(path, signature):
            text = (ENGINE / path).read_text()
            start = text.index(signature)
            opening = text.index('{', start)
            depth = 1
            end = opening + 1
            while depth:
                depth += (text[end] == '{') - (text[end] == '}')
                end += 1
            return text[start:end]
        consumers = self.directory / 'trainer-consumers.c'
        consumers.write_text('#include <assert.h>\n#include "global.h"\n#include "battle.h"\n'
                             '#include "battle_setup.h"\n#include "event_data.h"\n#include "battle_pyramid.h"\n#include "trainer_hill.h"\n'
                             + function('src/pokemon.c', 'u8 GetTrainerEncounterMusicId(u16 trainerOpponentId)') + '\n'
                             + function('src/battle_util.c', 'bool32 AreMultiPartiesFullTeams(void)') + '\n')
        consumer_obj = self.directory / 'trainer-consumers.o'
        self.run_command(['gcc', *flags, '-c', str(consumers), '-o', str(consumer_obj)])
        slides = self.directory / 'trainer-slides.c'
        slides.write_text('#include <assert.h>\n#include "src/trainer_slide.c"\n'
                          'void TestKantoSlides(void) {\n'
                          'gBattleTypeFlags = BATTLE_TYPE_TRAINER;\n'
                          'assert(!DoesTrainerHaveSlideMessage(DIFFICULTY_NORMAL, TRAINER_YOUNGSTER_BEN, 0));\n'
                          'assert(!DoesTrainerHaveSlideMessage(DIFFICULTY_NORMAL, 0xFFFF, 0));\n'
                          '}\n')
        slide_obj = self.directory / 'trainer-slides.o'
        data = self.run_command(['gcc', '-E', *flags, str(slides)])
        result = subprocess.run([str(self.preproc), '-i', str(slides), 'charmap.txt'], cwd=ENGINE,
                                input=data, text=True, capture_output=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        processed_slides = self.directory / 'trainer-slides.i'
        processed_slides.write_text(result.stdout)
        self.run_command(['gcc', *self.flags, '-c', str(processed_slides), '-o', str(slide_obj)])
        script_source = self.directory / 'trainer.s'
        root = (ENGINE / 'data/event_scripts.s').read_text().split('\t.section script_data', 1)[0]
        forest = (ENGINE / 'data/maps/ViridianForest_Frlg/scripts.inc').read_text()
        command = next(line for line in forest.splitlines() if 'trainerbattle_single TRAINER_BUG_CATCHER_RICK,' in line)
        script_source.write_text(root + '\n.section script_data, "aw", %progbits\nTestKantoTrainer::\n' + command
                                 + '\n\tend\nViridianForest_Text_RickIntro::\nViridianForest_Text_RickDefeat::\n\t.byte 0\n'
                                 + '\nTestKantoCheck::\n\tchecktrainerflag TRAINER_BUG_CATCHER_RICK\n\tend\n'
                                 + '\nTestKantoSet::\n\tsettrainerflag TRAINER_BUG_CATCHER_RICK\n\tend\n'
                                 + '\nTestKantoClear::\n\tcleartrainerflag TRAINER_BUG_CATCHER_RICK\n\tend\n')
        script_obj = self.directory / 'trainer-script.o'
        self.assemble(script_source, script_obj, 1)
        obj = self.directory / 'trainers.o'
        binary = self.directory / 'trainers'
        self.run_command(['gcc', *flags, '-c', 'tests/rc8/region_trainers.c', '-o', str(obj)])
        self.run_command(['gcc', *self.flags, '-DEW_REGION_STATE=1', '-DEW_KANTO_CONTENT=1',
                          '-Iplatform', '-idirafter', 'include', '-iquote', '.', *self.link,
                          str(obj), str(table_obj), str(script_obj), str(consumer_obj), str(slide_obj), *self.platform, '-o', str(binary)])
        self.assertIn('independent saved profiles passed', self.run_command([str(binary)]))

    def test_named_trainer_ids_preserve_default_and_firered(self):
        constants = (ENGINE / 'include/constants/opponents_frlg.h').read_text()
        names = re.findall(r'^#define\s+(TRAINER_\w+)\s+KANTO_TRAINER\(', constants, re.M)
        self.assertEqual(len(names), 623)
        source = self.directory / 'trainer-values.c'
        source.write_text('#include <stdio.h>\n#include "global.h"\nint main(void) {\n'
                          + ''.join(f'printf("%u\\n", {n});\n' for n in names)
                          + 'printf("%u %u %zu %zu\\n", TRAINERS_COUNT, MAX_TRAINERS_COUNT, sizeof(struct SaveBlock1), sizeof(struct SaveBlock3));\nreturn 0;}\n')
        results = []
        for version, enabled in (('FIRERED', 0), ('EMERALD', 0), ('EMERALD', 1)):
            binary = self.directory / f'trainer-values-{version}-{enabled}'
            flags = [f for f in self.flags if f != '-DEMERALD']
            self.run_command(['gcc', *flags, f'-D{version}', f'-DEW_REGION_STATE={enabled}',
                              f'-DEW_KANTO_CONTENT={enabled}', *self.game_includes, str(source), '-o', str(binary)])
            results.append(self.run_command([str(binary)]).splitlines())
        self.assertEqual(results[0][:-1], results[1][:-1])
        self.assertEqual(list(map(int, results[2][:-1])), [int(v) + 0x2000 for v in results[0][:-1]])
        self.assertEqual(results[1][-1], results[2][-1])
        self.assertEqual(results[2][-1], '855 864 15768 1574')

    def test_trainer_battle_consumers_compile_in_both_native_cohorts(self):
        # pokemon.c's lookup is exercised above. Its complete translation unit
        # additionally requires the full generated graphics/learnset build.
        for enabled in (0, 1):
            for source in ('src/difficulty.c', 'src/battle_setup.c',
                           'src/battle_util.c', 'src/trainer_slide.c'):
                flags = [*self.flags, f'-DEW_REGION_STATE={enabled}',
                         f'-DEW_KANTO_CONTENT={enabled}', *self.game_includes]
                data = self.run_command(['gcc', '-E', *flags, source])
                result = subprocess.run([str(self.preproc), '-i', source, 'charmap.txt'], cwd=ENGINE,
                                        input=data, text=True, capture_output=True, timeout=120)
                self.assertEqual(result.returncode, 0, result.stderr)
                processed = self.directory / 'syntax.i'
                processed.write_text(result.stdout)
                self.run_command(['gcc', *self.flags, '-fsyntax-only', str(processed)])

    def test_content_flag_requires_regional_state(self):
        result = subprocess.run(['python3', str(ROOT / 'scripts/build_expansion.py'), '--development', '--kanto-content'],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn('--kanto-content requires --regional-state', result.stderr)


if __name__ == '__main__':
    unittest.main()
