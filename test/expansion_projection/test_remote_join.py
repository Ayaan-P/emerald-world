"""Exercise Expansion remote routing without creating a socket."""
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from world import expansion

class RemoteJoinTests(unittest.TestCase):
    def args(self, root, **changes):
        values = dict(state_dir=Path(root), trainer='Ash', command='join', binary=None,
            display=None, replay=None, frames=None, print_command=False, remote='example.org:1234',
            invitation=Path(root)/'invite.json', pin='a'*64, seed_save=None, copy_online=False,
            agent_control=False, test_input=None, bootstrap=None)
        values.update(changes)
        return types.SimpleNamespace(**values)

    def test_authenticated_broker_uses_expansion_profile_and_closes(self):
        events = []
        class Broker:
            def __init__(self, root): events.append(('root', root))
            def __enter__(self): return self
            def __exit__(self, *args): events.append(('closed',))
            def connect_remote(self, name, invitation, remote, pin):
                events.append(('connect', name, remote, pin))
                return expected
        transport = types.ModuleType('world.transport')
        transport._endpoint = lambda _: ('example.org', 1234)
        transport.read_invitation = lambda _: {'trainer': 'Ash'}
        sess = types.ModuleType('world.session'); sess.DesktopSession = Broker
        with tempfile.TemporaryDirectory() as d, patch.dict(sys.modules, {'world.transport': transport, 'world.session': sess}):
            args = self.args(d)
            expected = expansion.ExpansionSession(Path(d), 'Ash').paths
            def fake_run(instance, binary, display, **kw):
                events.append(('run', instance.paths, kw))
                return 0
            with patch.object(expansion.ExpansionSession, 'run', fake_run):
                self.assertEqual(expansion.run(args), 0)
        self.assertEqual(events[0], ('root', Path(d)/'engines'))
        self.assertEqual(events[1][1:3], ('expansion-native', ('example.org',1234)))
        self.assertEqual(events[2][1], expected)
        self.assertTrue(events[2][2]['prepared_remote'])
        self.assertEqual(events[3], ('closed',))

    def test_prepared_remote_profile_is_not_replaced(self):
        import contextlib, io
        with tempfile.TemporaryDirectory() as d:
            session = expansion.ExpansionSession(Path(d), 'Ash')
            session.paths['profile'].mkdir(parents=True)
            (session.state/'remote.json').write_text('{}')
            session.paths['config'].write_text('existing invitation')
            class Lock:
                def __init__(self, *args): self.paths = session.paths
                def __enter__(self): return self
                def __exit__(self, *args): pass
            with patch.object(expansion, 'ProfileLock', Lock), \
                 patch.object(expansion, '_prepare_profile') as prepare, \
                 patch.object(expansion, 'game_command', return_value=['--','game']), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(session.run(binary=Path(d)/'game', print_command=True, prepared_remote=True), 0)
            prepare.assert_not_called()
            self.assertEqual(session.paths['config'].read_text(), 'existing invitation')

    def test_wrong_trainer_rejected_before_connect(self):
        transport = types.ModuleType('world.transport')
        transport._endpoint = lambda _: ('example.org',1234)
        transport.read_invitation = lambda _: {'trainer':'SomeoneElse'}
        with tempfile.TemporaryDirectory() as d, patch.dict(sys.modules, {'world.transport':transport}):
            with self.assertRaisesRegex(ValueError, 'trainer must match'):
                expansion.run(self.args(d))
            self.assertFalse((Path(d)/'engines').exists())

    def test_partial_remote_configuration_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, 'requires --remote'):
                expansion.run(self.args(d, pin=None))

if __name__ == '__main__': unittest.main()
