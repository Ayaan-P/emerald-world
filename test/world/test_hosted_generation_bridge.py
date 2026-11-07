import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from world.session import DesktopSession
from world.web_launcher import LauncherBridge


class HostedGenerationBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ew-hg-')
        self.addCleanup(self.tmp.cleanup)
        self.session = DesktopSession(Path(self.tmp.name), engine='expansion-native')
        self.addCleanup(self.session.close)
        self.bridge = LauncherBridge(self.session, Path('/nonexistent/game'), engine='expansion-native')
        self.bridge.hosted._ready = lambda: None
        self.client = Mock()
        self.client.list.return_value = [{'id': 'a'*16, 'name': 'beta', 'trainer': 'snky'}]
        self.client.generated_areas.return_value = {
            'cave_authoring': True, 'wilds_authoring': True, 'guided_wilds_authoring': True,
            'cast_wilds_authoring': True, 'xl_wilds_authoring': True,
            'cave_persistent': True, 'area_archive': True,
            'generated_areas': [], 'active_generated_area': None}
        p = patch('world.hosting_client.HostingClient.from_file', return_value=self.client)
        p.start()
        self.addCleanup(p.stop)

    def test_select_hosted_authoring_without_connect_or_game_switch(self):
        state = self.bridge.action('host_select_area', {'world': 'a'*16})
        self.assertIsNone(self.session.state)
        self.assertTrue(state['area_authoring'])
        self.assertEqual(state['area_world_key'], 'hosted-'+'a'*16)
        self.assertIsNone(state['world_key'])
        self.assertEqual(state['hosted_area_world']['name'], 'beta')
        self.assertTrue(state['cave_authoring'])

    def test_confirmation_precedes_model_and_publication(self):
        self.bridge.action('host_select_area', {'world': 'a'*16})
        with patch('world.author_cave.author', return_value=({}, b'fixture')) as author:
            with self.assertRaises(ValueError):
                self.bridge.action('author_cave', {'world': 'hosted-'+'a'*16, 'theme': 'forest'})
            author.assert_not_called()
            self.bridge.action('author_cave', {'world': 'hosted-'+'a'*16,
                'theme': 'forest', 'kind': 'cave', 'confirmed': True})
            author.assert_called_once_with('forest', large=True, custom_wildlife=True, cohort='expansion-native')
        self.client.publish_generated_area.assert_called_once_with('a'*16, b'fixture', label='forest')

    def test_occupancy_prevents_model_cost(self):
        self.bridge.action('host_select_area', {'world': 'a'*16})
        self.client.generated_areas.return_value['active_generated_area'] = {'occupants': 1}
        with patch('world.author_cave.author') as author:
            with self.assertRaisesRegex(ValueError, 'leave'):
                self.bridge.action('author_cave', {'world': 'hosted-'+'a'*16,
                    'theme': 'forest', 'kind': 'cave', 'confirmed': True})
            author.assert_not_called()


if __name__ == '__main__':
    unittest.main()
