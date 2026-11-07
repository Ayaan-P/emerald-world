"""Native diagnostics must see only their optional read-only symbol companion."""
from pathlib import Path
import tempfile
import unittest
from world.launcher import game_command, profile_paths


class NativeSymbolMountTests(unittest.TestCase):
    def command(self, root, binary, engine):
        return game_command(binary, root, profile_paths(root, 'alice', engine=engine),
                            agent_control=True, online=False, engine=engine)

    def test_regular_companion_is_allowlisted_readonly(self):
        for engine in ('vanilla', 'expansion-native'):
            with self.subTest(engine=engine), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                binary = root / 'game'
                binary.write_bytes(b'fixture only; not executed')
                symbols = root / 'game.symbols'
                symbols.write_text('0000000040000000 T example\n')
                command = self.command(root, binary, engine)
                mounts = [command[i:i + 3] for i, arg in enumerate(command) if arg == '--ro-bind']
                self.assertIn(['--ro-bind', str(symbols), str(symbols)], mounts)
                self.assertNotIn(['--ro-bind', str(root), str(root)], mounts)
                self.assertNotIn(['--bind', str(symbols), str(symbols)], [command[i:i + 3] for i in range(len(command))])

    def test_missing_companion_remains_optional(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            binary = root / 'game'
            binary.touch()
            self.assertNotIn(str(root / 'game.symbols'), self.command(root, binary, 'expansion-native'))

    def test_symlink_companion_does_not_expose_its_target(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            binary = root / 'game'
            binary.touch()
            unrelated = root / 'unrelated.txt'
            unrelated.write_text('not native symbol metadata')
            companion = root / 'game.symbols'
            companion.symlink_to(unrelated)
            command = self.command(root, binary, 'expansion-native')
            self.assertNotIn(str(companion), command)
            self.assertNotIn(str(unrelated), command)


if __name__ == '__main__':
    unittest.main()
