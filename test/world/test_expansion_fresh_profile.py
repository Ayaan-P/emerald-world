"""First remote Expansion profiles must initialize under the world move barrier."""
import tempfile
import unittest
from pathlib import Path
from world.launcher import ProfileLock
from world.world_library import WorldActivityLock


class FreshExpansionProfile(unittest.TestCase):
    def test_first_remote_profile_creates_engine_parents(self):
        with tempfile.TemporaryDirectory() as directory:
            world = Path(directory) / 'hosted-0123456789abcdef'
            world.mkdir(mode=0o700)
            with ProfileLock(world, 'snky', engine='expansion-native'):
                self.assertTrue((world / 'engines/expansion-native/.profile-locks/snky.lock').is_file())
                with self.assertRaises(ValueError):
                    WorldActivityLock(world, exclusive=True)


if __name__ == '__main__':
    unittest.main()
