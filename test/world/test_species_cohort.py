"""Cohort selection, native-ID identity and legacy compatibility regressions."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from world import author_cave, cave_blueprint, large_cave, offline_cave
from world.shared_cave import SharedCave
from world import species_cohort
from test_shared_generated_cave import MemoryAuthority

PROPOSAL = cave_blueprint.proposal_from_blueprint({
    'rooms': [[2, 2, 12, 12], [16, 16, 12, 12]], 'links': [[0, 1]],
    'entrance_room': 0, 'exit_room': 1, 'style': 'organic', 'seed': 42})


class SpeciesCohortTests(unittest.TestCase):
    def test_canonical_native_export_is_based_on_enabled_species_info(self):
        from scripts.export_expansion_species_catalogue import export_catalogue
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'catalogue.json'
            data = export_catalogue(species_cohort.ENGINE_ROOT, output)
            species = data['species']
            self.assertEqual(species['TREECKO'], 252)
            self.assertEqual(species['TURTWIG'], 387)
            self.assertNotIn('EGG', species)
            self.assertGreater(len(species), 386)
            self.assertEqual(json.loads(output.read_text()), data)

    def test_legacy_numeric_namespace_is_preserved_and_not_mixed(self):
        with patch.object(species_cohort, 'CATALOGUE_PATH', Path('world/expansion_species.json')):
            species_cohort.catalogue.cache_clear()
            self.assertEqual(species_cohort.species_id('TREECKO', 'vanilla'), 277)
            self.assertEqual(species_cohort.species_id('TREECKO', 'expansion-native'), 252)
            self.assertEqual(species_cohort.species_id('TURTWIG', 'expansion-native'), 387)
            with self.assertRaises(ValueError):
                species_cohort.species_id('TURTWIG', 'vanilla')
            legacy = offline_cave.encode_wildlife(PROPOSAL, 'ice', 25,
                [{'species': 'TREECKO', 'level': 5}] * 12)
            modern = offline_cave.encode_wildlife(PROPOSAL, 'ice', 25,
                [{'species': 'TREECKO', 'level': 5}] * 12, cohort='expansion-native')
            self.assertEqual(legacy[:8], b'EWGMAP03')
            self.assertEqual(int.from_bytes(legacy[10:12], 'little'), 277)
            self.assertEqual(modern[:8], b'EWGMAP10')
            self.assertEqual(int.from_bytes(modern[10:12], 'little'), 252)
            self.assertEqual(SharedCave(legacy).cohort, 'vanilla')
            self.assertEqual(SharedCave(modern).cohort, 'expansion-native')
            wrong_identity = modern[:10] + (277).to_bytes(2, 'little') + modern[12:]
            self.assertNotEqual(SharedCave(wrong_identity).wildlife, SharedCave(modern).wildlife)
            # The catalogue prevents authoring this ID as Treecko in Expansion; raw IDs
            # that coincide with another enabled native species remain valid native data.
            species_cohort.catalogue.cache_clear()

    def test_modern_omission_and_cross_cohort_ids_are_rejected(self):
        modern_turtwig = offline_cave.encode_wildlife(PROPOSAL, 'ice', 25,
            [{'species': 'TURTWIG', 'level': 5}] * 12, cohort='expansion-native')
        self.assertEqual(int.from_bytes(modern_turtwig[10:12], 'little'), 387)
        with self.assertRaises(ValueError):
            offline_cave.encode_wildlife(PROPOSAL, 'ice', 25,
                [{'species': 'TURTWIG', 'level': 5}] * 12, cohort='vanilla')
        modern = offline_cave.encode_wildlife(PROPOSAL, 'ice', 25,
            [{'species': 'TREECKO', 'level': 5}] * 12, cohort='expansion-native')
        wrong = modern[:10] + (277).to_bytes(2, 'little') + modern[12:]
        self.assertNotEqual(SharedCave(wrong).wildlife, SharedCave(modern).wildlife)
        # Numeric namespaces overlap: cohort identity disambiguates their meaning, while
        # name-to-ID resolution must remain anchored to the selected canonical roster.

    def test_authoring_prompt_and_decode_use_selected_enabled_cohort(self):
        exp_prompt = author_cave.prompt_for('icy forest', custom_wildlife=True, large=True,
                                             cohort='expansion-native')
        vanilla_prompt = author_cave.prompt_for('icy forest', custom_wildlife=True, large=True)
        self.assertIn('TURTWIG', exp_prompt)
        self.assertNotIn('TURTWIG', vanilla_prompt)

        def decode(name, cohort):
            blueprint = {'rooms': [[2, 2, 12, 12], [16, 16, 12, 12]], 'links': [[0, 1]],
                         'entrance_room': 0, 'exit_room': 1, 'style': 'organic', 'seed': 42,
                         'corridor_width': 2, 'encounter_profile': 'ice', 'encounter_rate': 25,
                         'wildlife': [{'species': name, 'level': 5}] * 12}
            events = [
                {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': json.dumps(blueprint)}},
                {'type': 'turn.completed'},
            ]
            return author_cave.decode_blueprint_events('\n'.join(map(json.dumps, events)),
                custom_wildlife=True, large=True, cohort=cohort)

        _, profile, rate, roster = decode('TREECKO', 'expansion-native')  # type: ignore[assignment]
        blob = large_cave.encode_wildlife(
            {'rows': ['#' * 63] + ['#' + '.' * 61 + '#' for _ in range(61)] + ['#' * 63],
             'spawn': [1, 1], 'exit': [61, 61]}, profile, rate, roster, cohort='expansion-native')
        self.assertEqual(blob[:8], b'EWGMAP11')
        self.assertEqual(int.from_bytes(blob[10:12], 'little'), 252)
        _, _, _, turtwig = decode('TURTWIG', 'expansion-native')  # type: ignore[assignment]
        modern = large_cave.encode_wildlife(
            {'rows': ['#' * 63] + ['#' + '.' * 61 + '#' for _ in range(61)] + ['#' * 63],
             'spawn': [1, 1], 'exit': [61, 61]}, 'ice', 25, turtwig, cohort='expansion-native')
        self.assertEqual(int.from_bytes(modern[10:12], 'little'), 387)
        with self.assertRaises(ValueError):
            large_cave.encode_wildlife(
                {'rows': ['#' * 63] + ['#' + '.' * 61 + '#' for _ in range(61)] + ['#' * 63],
                 'spawn': [1, 1], 'exit': [61, 61]}, 'ice', 25, turtwig, cohort='vanilla')

    def test_expansion_v10_native_wire_digest_and_admission(self):
        code = r'''
#include <stdio.h>
#include <string.h>
#include "global.h"
#include "platform/world_cave_wire.h"
int main(void){char line[512];struct WorldCaveWire w={0};int result=0;
 while(fgets(line,sizeof(line),stdin)){char *tokens[5],*save,*p;unsigned n=0;
 line[strcspn(line,"\n")]=0;for(p=strtok_r(line," ",&save);p&&n<5;p=strtok_r(NULL," ",&save))tokens[n++]=p;
 result=WorldCaveWire_Feed(&w,n,(const char *const*)tokens);if(result<0){fprintf(stderr,"rejected n=%u t0=%s t1=%s version=%u\\n",n,tokens[0],n>1?tokens[1]:"",w.version);return 2;}}
 return result==1 && (w.version==10 || w.version==11) && w.wildlifeSeen ? 0 : 3;}
'''
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'global.h').write_text('#include <stdint.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef int bool8;\n#define TRUE 1\n#define FALSE 0\n')
            source = species_cohort.ENGINE_ROOT / 'src/world/world_cave_wire.c'
            header = species_cohort.ENGINE_ROOT / 'include/platform/world_cave_wire.h'
            (root / 'test.c').write_text(code)
            exe = root / 'test'
            build = subprocess.run(['cc', '-std=gnu99', '-Wall', '-Wextra', '-Werror', '-DPORTABLE',
                '-DGENERATED_CAVE_PROFILES=1', '-DGENERATED_CAVE_WILDLIFE=1', '-DGENERATED_MAP_LARGE=1',
                '-iquote', str(root), '-iquote', str(header.parent.parent), str(source), str(root / 'test.c'),
                '-o', str(exe)], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            for version, wildlife in ((10, offline_cave.encode_wildlife(PROPOSAL, 'ice', 25,
                    [{'species': 'TREECKO', 'level': 5}] * 12, cohort='expansion-native')),
                (11, __import__('world.large_cave', fromlist=['encode_wildlife']).encode_wildlife(
                    {'rows': ['#' * 63] + ['#' + '.' * 61 + '#' for _ in range(61)] + ['#' * 63],
                     'spawn': [1, 1], 'exit': [61, 61]}, 'ice', 25,
                    [{'species': 'TURTWIG', 'level': 5}] * 12, cohort='expansion-native'))):
                cave = SharedCave(wildlife)
                self.assertEqual(cave.version, version)
                result = subprocess.run([str(exe)], input=cave.frames(), capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr or str(result.returncode))

    def test_authority_segregates_expansion_wildlife_from_legacy_clients(self):
        import tempfile
        modern = offline_cave.encode_wildlife(PROPOSAL, 'ice', 25,
            [{'species': 'TREECKO', 'level': 5}] * 12, cohort='expansion-native')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            server = MemoryAuthority(root / 'socket', root / 'world', cave_template=modern)
            try:
                old_identity = server.create_identity('Alice')
                current_identity = server.create_identity('Bob')
                def connect(identity, role):
                    conn = {'id': None, 'out': bytearray(), 'closing': False, 'state': None, 'seq': 0, 'sock': object()}
                    hello = f"HELLO 1 {identity['id']} {identity['token']} {role}"
                    server._line(conn, hello.encode())
                    self.assertIn(b'WELCOME 1', conn['out']); conn['out'].clear()
                    return conn
                old = connect(old_identity, 'SOCIALTRAVELCHATRALLYCAVE9')
                current = connect(current_identity, 'SOCIALTRAVELCHATRALLYCAVE10')
                server._line(old, b'CAVE GET')
                self.assertEqual(old['out'], b'CAVE NONE\n')
                server._line(current, b'CAVE GET')
                self.assertIn(b' 10\n', current['out'])
            finally:
                server.close()


if __name__ == '__main__':
    unittest.main()
