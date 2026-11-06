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

if __name__ == '__main__':
    unittest.main()
