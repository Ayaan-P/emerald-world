"""Implemented encounter roots and emitted-edge closure are not gameplay proof."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('acquisition_import', ROOT / 'tools/expanded/import_species.py')
importer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(importer)


class AcquisitionCoverageTest(unittest.TestCase):
    def test_seven_exact_implemented_roots_preserve_first_three(self):
        expected = [
            ('MAP_ROUTE101', 'SPECIES_ZIGZAGOON', 'SPECIES_GIMMIGHOUL_ROAMING'),
            ('MAP_ROUTE101', 'SPECIES_WURMPLE', 'SPECIES_MELTAN'),
            ('MAP_ROUTE101', 'SPECIES_POOCHYENA', 'SPECIES_COSMOEM'),
            ('MAP_ROUTE102', 'SPECIES_RALTS', 'SPECIES_TYPE_NULL'),
            ('MAP_ROUTE103', 'SPECIES_ZIGZAGOON', 'SPECIES_TURTWIG'),
            ('MAP_ROUTE103', 'SPECIES_POOCHYENA', 'SPECIES_CHESPIN'),
            ('MAP_ROUTE103', 'SPECIES_MAGIKARP', 'SPECIES_ARROKUDA'),
        ]
        actual = getattr(importer, 'IMPLEMENTED_ACQUISITION_ROOTS', ())
        self.assertEqual([(r['map'], r['original_species'], r['species']) for r in actual], expected)
        runtime = (ROOT / 'src/platform/expanded_species.c').read_text()
        for map_name, original, species in expected:
            self.assertIn(map_name, runtime)
            self.assertIn(original, runtime)
            self.assertIn('return ' + species + ';', runtime)

    def test_closure_uses_only_emitted_edges_and_handles_cycles(self):
        closure = getattr(importer, 'acquisition_paths', None)
        self.assertTrue(callable(closure), 'requires generic emitted-edge closure')
        rows = [
            dict(name='ROOT', supported_evolutions=[dict(method='EVO_LEVEL', param=18, target='MIDDLE')]),
            dict(name='MIDDLE', supported_evolutions=[dict(method='EVO_LEVEL', param=32, target='FINAL')]),
            dict(name='FINAL', supported_evolutions=[dict(method='EVO_LEVEL', param=40, target='ROOT')]),
            dict(name='BLOCKED', supported_evolutions=[], unsupported_evolutions=[dict(target='UNSUPPORTED')]),
            dict(name='UNRELATED', supported_evolutions=[]),
        ]
        paths = closure(rows, [dict(species='ROOT', map='MAP_TEST')])
        self.assertEqual(list(paths), ['ROOT', 'MIDDLE', 'FINAL'])
        self.assertEqual([e['target'] for e in paths['FINAL']['evolutions']], ['MIDDLE', 'FINAL'])
        self.assertEqual(paths['FINAL']['root']['species'], 'ROOT')
        self.assertNotIn('UNSUPPORTED', paths)
        self.assertNotIn('UNRELATED', paths)

    def test_unsupported_descriptors_cannot_add_acquisition_paths(self):
        source = '''.evolutions = EVOLUTION(
            {EVO_LEVEL, 18, SPECIES_MIDDLE},
            {EVO_ITEM, ITEM_SUN_STONE, SPECIES_ITEM},
            {EVO_LEVEL, 32, SPECIES_RESERVED},
            {EVO_LEVEL, 40, SPECIES_CONDITIONAL, CONDITIONS({IF_MIN_OVERWORLD_FOG})}),'''
        mapping = {name: i for i, name in enumerate([
            'SPECIES_ROOT', 'SPECIES_MIDDLE', 'SPECIES_ITEM',
            'SPECIES_RESERVED', 'SPECIES_CONDITIONAL'], 440)}
        supported, unsupported = importer.classify_evolutions(
            source, mapping, set(), {'SPECIES_ROOT', 'SPECIES_MIDDLE', 'SPECIES_ITEM', 'SPECIES_CONDITIONAL'})
        self.assertEqual([e['target'] for e in supported], ['SPECIES_MIDDLE'])
        self.assertEqual(len(unsupported), 3)
        rows = [dict(name='SPECIES_ROOT', supported_evolutions=supported,
                     unsupported_evolutions=unsupported)]
        paths = importer.acquisition_paths(rows, [dict(species='SPECIES_ROOT')])
        self.assertEqual(set(paths), {'SPECIES_ROOT', 'SPECIES_MIDDLE'})


class StagedAcquisitionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import json
        from unittest.mock import patch
        donor = ROOT.parent / 'expansion-foundation/engines/expansion-native'
        cls.output = ROOT / 'build/rc4-catalog-final/test55/generated'
        cls.move_stage = ROOT / 'build/rc4-self-drop-move-catalog/generated'
        header = (cls.move_stage / 'include/constants/moves.h').read_text()
        read_text = Path.read_text
        def overlay(path, *args, **kwargs):
            if path == ROOT / 'include/constants/moves.h':
                return header
            return read_text(path, *args, **kwargs)
        with patch.object(Path, 'read_text', overlay):
            importer.generate(donor.resolve(), cls.output)
        cls.manifest = json.loads((cls.output / 'tools/expanded/coverage.json').read_text())
        cls.rows = {r['name']: r for r in cls.manifest['species']}

    def test_dependency_selected_not_arbitrary_playable_allowlist(self):
        expected = {n for n, r in self.rows.items() if r['engine_id'] >= 440 and not r['import_blockers']}
        self.assertEqual(set(self.manifest['playable_selection']), expected)
        for name in expected:
            row = self.rows[name]
            self.assertEqual(row['supported_slots'], [0, 1])
            self.assertFalse(row['hidden_ability_supported'])
            self.assertEqual(row['missing_level_up_moves'], [])
            self.assertEqual(row['missing_normal_abilities'], [])

    def test_transitive_turtle_family_and_data_only_species(self):
        paths = importer.acquisition_paths(self.manifest['species'])
        self.assertEqual(self.manifest['obtainable_selection'], list(paths))
        turtle = self.rows['SPECIES_TORTERRA']
        self.assertTrue(turtle['battle_supported'])
        self.assertTrue(turtle['obtainable'])
        self.assertEqual(turtle['acquisition_path']['root']['species'], 'SPECIES_TURTWIG')
        self.assertEqual([(e['source'], e['param'], e['target']) for e in turtle['acquisition_path']['evolutions']], [
            ('SPECIES_TURTWIG', 18, 'SPECIES_GROTLE'),
            ('SPECIES_GROTLE', 32, 'SPECIES_TORTERRA')])
        emitted = (self.output / 'src/data/pokemon/expanded/evolution.inc').read_text()
        for source in self.rows.values():
            for edge in source['supported_evolutions']:
                self.assertIn('{%s, %d, %s}' % (edge['method'], edge['param'], edge['target']), emitted)
        arro = self.rows['SPECIES_ARROKUDA']
        self.assertTrue(arro['battle_supported'])
        self.assertTrue(arro['obtainable'])
        self.assertEqual(arro['acquisition_path']['root']['species'], 'SPECIES_ARROKUDA')
        self.assertEqual(arro['acquisition_path']['root']['original_species'], 'SPECIES_MAGIKARP')
        self.assertEqual(arro['acquisition_path']['evolutions'], [])
        self.assertNotIn('acquisition_route', arro['unsupported_features'])
        self.assertEqual(len(self.manifest['playable_selection']), 11)
        self.assertEqual(len(self.manifest['obtainable_selection']), 10)
        barraskewda = self.rows['SPECIES_BARRASKEWDA']
        self.assertFalse(barraskewda['battle_supported'])
        self.assertFalse(barraskewda['obtainable'])
        self.assertIn('MOVE_THROAT_CHOP', barraskewda['missing_level_up_moves'])
        for name in ('SPECIES_KUBFU',):
            row = self.rows[name]
            self.assertTrue(row['battle_supported'])
            self.assertFalse(row['obtainable'])
            self.assertIsNone(row['acquisition_path'])
            self.assertIn('acquisition_route', row['unsupported_features'])
        for row in self.rows.values():
            self.assertEqual(row['obtainable'], row['name'] in paths)
            if row['status'] == 'reserved_not_playable':
                self.assertFalse(row['obtainable'])

    def test_every_id_matches_shared_baseline(self):
        import json
        baseline = json.loads((ROOT / 'tools/expanded/coverage.json').read_text())
        self.assertEqual(len(self.rows), 1670)
        self.assertEqual({r['name']: r['engine_id'] for r in baseline['species']},
                         {n: r['engine_id'] for n, r in self.rows.items()})

    def test_coverage_never_conflates_implemented_support_and_native_proof(self):
        self.assertIn('not native gameplay proof', self.manifest['acquisition_scope'])
        self.assertIn('staged output only', self.manifest['support_limits']['runtime'])
        self.assertEqual(self.manifest['implemented_acquisition_roots'], list(importer.IMPLEMENTED_ACQUISITION_ROOTS))
        for name in self.manifest['playable_selection']:
            self.assertIn('expanded_dex_persistence', self.rows[name]['unsupported_features'])
        # Unsupported level-up or conditional descriptors never become emitted edges.
        for row in self.rows.values():
            if row['obtainable'] and row['acquisition_path']['evolutions']:
                for edge in row['acquisition_path']['evolutions']:
                    actual = dict(edge)
                    source = actual.pop('source')
                    self.assertIn(actual, self.rows[source]['supported_evolutions'])


if __name__ == '__main__':
    unittest.main()
