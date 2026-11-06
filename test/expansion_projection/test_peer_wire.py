import ast
import re
import unittest
from pathlib import Path

source = Path(__file__).parents[2] / 'world' / 'expansion.py'
module = ast.parse(source.read_text())
function = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == 'serialize_peers')
scope = {'re': re}
exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), scope)
serialize_peers = scope['serialize_peers']

class TestPeerWire(unittest.TestCase):
    def test_snapshot(self):
        p = dict(group=0, num=1, x=12, y=9, facing=2, gfx=4, ready=0)
        self.assertEqual(serialize_peers({'peers': {'Pikachu': p}}), 'EWPEERS 1\nPikachu 0 1 12 9 2\n')
    def test_rejects_bad_wire(self):
        p = dict(group=0, num=1, x=12, y=9, facing=2)
        for peers in ({'x\ny': p}, {'x': dict(p, x=True)}, {'x': dict(p, facing=0)},
                      {'x': dict(p, x=32768)}, {str(i): p for i in range(9)}):
            with self.subTest(peers=peers), self.assertRaises(ValueError):
                serialize_peers({'peers': peers})
    def test_no_peers(self):
        self.assertEqual(serialize_peers({'peers': {}}), 'EWPEERS 1\n')

class TestCatalogBoundary(unittest.TestCase):
    def test_foreign_map_group_is_absent_not_aliased(self):
        # Exercise the real method without opening a world socket.
        import json, sys, tempfile, types
        from unittest.mock import patch
        method = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == 'ExpansionSession')
        method = next(n for n in method.body if isinstance(n, ast.FunctionDef) and n.name == '_publish_presence')
        ns = {'time': __import__('time'), 'json': json, 'ENGINE': 'expansion-native',
              '__package__': 'fake_world'}
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), 'exec'), ns)
        class Stop:
            calls = 0
            def wait(self, seconds):
                self.calls += 1
                return self.calls > 1
        class Client:
            def __init__(self):
                self.sock = self
                self.sent = []
                self.absent = []
            def sendall(self, data): self.sent.append(data)
            def send_state(self, *args): self.absent.append(args)
        pkg = types.ModuleType('fake_world'); pkg.__path__ = []
        catalog = types.ModuleType('fake_world.build_catalog')
        catalog.validate_coords = lambda *args: None
        with tempfile.TemporaryDirectory() as d, patch.dict(sys.modules, {'fake_world': pkg, 'fake_world.build_catalog': catalog}):
            profile = Path(d)
            for group, expected in [(0, 'field'), (34, 'absent'), (37, 'absent')]:
                (profile/'presence.json').write_text(json.dumps(dict(schema=1, engine='expansion-native', field=True,
                    group=group, num=0, x=1, y=1)))
                session = types.SimpleNamespace(paths={'profile': profile}, stop=Stop())
                client = Client()
                ns['_publish_presence'](session, client)
                self.assertEqual(bool(client.sent), expected == 'field')
                self.assertEqual(bool(client.absent), expected == 'absent')

if __name__ == '__main__':
    unittest.main()
