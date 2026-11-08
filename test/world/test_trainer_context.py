import json
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch
from world.trainer_context import author_context, build_reference, parse_parties


class TrainerContextTests(unittest.TestCase):
    def test_snapshot_progression_and_source(self):
        result = author_context('Help prepare for Roxanne in Rustboro')
        self.assertEqual(result['provenance']['revision'], 'db028d31a8e4fcb615e60414c7a870cba3263330')
        self.assertEqual(result['provenance']['git_blob_sha1'], 'fbe4a37f6dafa6b397902c9e3c01ce12848580f8')
        self.assertEqual(len(result['story_progression']), 8)
        self.assertEqual([m['level'] for m in result['matched_teams'][0]['party']], [12, 12, 15])
        self.assertEqual(result['matched_teams'][0]['party'][0]['species_and_item'], 'Geodude')
        self.assertEqual(result['story_progression'][6]['battle_format'], 'doubles')

    def test_bounded_selection_and_no_inferred_player_state(self):
        result = author_context('Rustboro Dewford Mauville Lavaridge Petalburg Fortree Mossdeep Sootopolis')
        self.assertEqual(len(result['matched_teams']), 3)
        self.assertEqual(result['matched_teams_omitted'], 5)
        self.assertLess(len(json.dumps(result)), 16000)
        self.assertNotIn('player', result)
        self.assertEqual(author_context('A bridge memorial')['matched_teams'], [])

    def test_native_default_moves_not_invented(self):
        rows = parse_parties('=== TRAINER_TEST ===\nName: TEST\nClass: Hiker\n\nGeodude\nLevel: 12\n')
        self.assertEqual(rows[0]['party'][0]['moves_source'], 'native_level_up_defaults')
        self.assertEqual(rows[0]['party'][0]['moves'], [])

    def test_unknown_conditional_and_duplicate_fail_closed(self):
        with self.assertRaises(ValueError):
            parse_parties('#if SOMETHING\n')
        fixture = '=== TRAINER_TEST ===\nName: TEST\n\nGeodude\nLevel: 12\n'
        with self.assertRaises(ValueError):
            parse_parties(fixture + fixture)
        with self.assertRaises(ValueError):
            build_reference(fixture, 'main')

    def test_gm_actual_author_path_includes_context(self):
        from world.gm import author_and_deploy
        seen = []
        def author(prompt):
            data = json.loads(prompt.split('Request and snapshot follow:\n', 1)[1])
            seen.append(data['inspection']['trainer_reference'])
            return {'source': "def update(context, state):\n    return {'state':state,'tiles':[],'objects':[]}\n",
                    'tests': 'def test_empty():\n    assert True\n'}
        def transport(socket, request, timeout):
            if request['command'] == 'inspect':
                return {'ok': True, 'players': [], 'objects': [], 'tiles': []}
            return {'ok': False, 'error': 'No deployment in this context fixture'}
        with tempfile.TemporaryDirectory() as directory:
            with patch('world.gm.admin_request', side_effect=transport):
                report = author_and_deploy(directory, 'unused', 'Wattson preparation', author)
            self.assertFalse(report['ok'])
            self.assertEqual(seen[0]['matched_teams'][0]['id'], 'TRAINER_WATTSON_1')
            saved = json.loads(Path(report['context_path']).read_text())
            self.assertEqual(saved['trainer_reference'], seen[0])



if __name__ == '__main__':
    unittest.main()
