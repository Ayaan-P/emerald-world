"""Private progress travels on the existing authenticated CONTROL connection."""
from pathlib import Path
import tempfile
import unittest
from world.client import IntentClient, WorldClient
from world.server import WorldServer


class PlayerActivityControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ew-product-')
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.path = str(root/'sock')
        self.server = WorldServer(self.path, root/'state')
        self.addCleanup(self.server.close)
        self.alice = self.server.create_identity('Alice')
        self.server.create_identity('Bob')
        self.server.start()

    def test_read_is_own_only_without_displacing_native_or_creating_gm_work(self):
        with WorldClient(self.path, 'Alice', self.alice['token']) as native:
            native.snapshot()
            presence = self.server.peers['Alice']
            with IntentClient(self.path, 'Alice', self.alice['token']) as control:
                result = control._request({'command': 'player_activity'})
                self.assertTrue(result['ok'], result)
                self.assertEqual(result['activity']['trainer'], 'Alice')
                self.assertIsNone(result['activity']['survey'])
                self.assertIs(self.server.peers['Alice'], presence)
                self.assertFalse((self.server.root/'gm').exists())
                rejected = control._request({'command': 'player_activity', 'trainer': 'Bob'})
                self.assertFalse(rejected['ok'])
                self.assertNotIn('Bob', str(rejected))
            self.assertIs(self.server.peers['Alice'], presence)


if __name__ == '__main__':
    unittest.main()
