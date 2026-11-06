"""Exercise engine compatibility admission using in-memory connection stubs."""
import ast
from pathlib import Path
import re
import secrets
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
module = ast.parse((ROOT/'world'/'server.py').read_text())
cls = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == 'WorldServer')
methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in ('_line', '_link_line')]
scope = {'ID': re.compile(r'[A-Za-z0-9_-]{1,24}\Z'), 'HEX': re.compile(r'[0-9a-fA-F]{64}\Z'),
         'secrets': secrets}
exec(compile(ast.Module(body=methods, type_ignores=[]), 'server.py', 'exec'), scope)

class LinkEngineGateTests(unittest.TestCase):
    def setUp(self):
        self.messages = []
        self.token = 'a'*64
        class DB:
            def execute(inner, *args): return inner
            def fetchone(inner): return (self.token,)
        class Protocol:
            calls = []
            def process(inner, actor, raw, presence):
                inner.calls.append((actor,raw,presence)); return []
        self.server = SimpleNamespace(db=DB(), revision=0, peers={}, link_channels={}, connections={}, link_protocol=Protocol(),
            _queue=lambda conn, data: self.messages.append((conn, data)),
            _error=lambda conn, data: self.messages.append((conn, 'ERROR '+data)),
            _deliver_links=lambda output: None, _link_presence=lambda: {})
    def authenticate(self, name, role):
        presence = {'id':name, 'closing':False}
        self.server.peers[name] = presence
        conn = {'id':None, 'closing':False, 'sock':object()}
        raw = f'HELLO 1 {name} {self.token} {role}'.encode()
        scope['_line'](self.server, conn, raw)
        self.server.connections[conn['sock']] = conn
        return conn
    def test_expansion_and_vanilla_identify_without_changing_welcome(self):
        a=self.authenticate('Ash','LINKEXP1'); b=self.authenticate('May','LINK')
        self.assertEqual(a['link_engine'],'expansion-v1')
        self.assertEqual(b['link_engine'],'vanilla-v1')
        self.assertTrue(self.messages[0][1].endswith(' LINK\n'))
        self.assertTrue(self.messages[1][1].endswith(' LINK\n'))
    def test_incompatible_offer_fails_before_protocol_or_consent(self):
        a=self.authenticate('Ash','LINKEXP1'); self.authenticate('May','LINK')
        self.messages.clear()
        scope['_link_line'](self.server, a, b'L OFFER 1 May')
        self.assertEqual(self.messages,[(a,'L ERROR UNAVAILABLE\n')])
        self.assertEqual(self.server.link_protocol.calls,[])
        self.messages.clear()
        scope['_link_line'](self.server, a, b'T OFFER May')
        self.assertEqual(self.messages,[(a,'T ERROR UNAVAILABLE\n')])
    def test_same_engine_reaches_existing_consent_coordinator(self):
        a=self.authenticate('Ash','LINKEXP1'); self.authenticate('May','LINKEXP1')
        self.messages.clear()
        scope['_link_line'](self.server, a, b'L OFFER 1 May')
        self.assertEqual(len(self.server.link_protocol.calls),1)
        self.assertEqual(self.messages,[])
    def test_legacy_vanilla_pair_is_unchanged(self):
        a=self.authenticate('Ash','LINK'); self.authenticate('May','LINK')
        self.messages.clear()
        scope['_link_line'](self.server, a, b'L OFFER 1 May')
        self.assertEqual(len(self.server.link_protocol.calls),1)

if __name__ == '__main__': unittest.main()
