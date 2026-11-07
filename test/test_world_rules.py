"""World-rule storage and authenticated admission; no sockets or player saves."""
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from world.world_rules import WorldRules
from world.server import WorldServer

class MemoryAuthority(WorldServer):
    def _queue(self, conn, text): conn['out'].extend(text.encode('ascii'))
    def _broadcast(self): pass

class RulesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.server = MemoryAuthority(self.root / 'socket', self.root / 'world')
        self.alice = self.server.create_identity('Alice')
        self.bob = self.server.create_identity('Bob')
    def tearDown(self):
        self.server.close()
        self.temp.cleanup()
    def conn(self, who, role):
        c = {'id': None, 'out': bytearray(), 'closing': False, 'state': None, 'seq': 0, 'sock': object()}
        suffix = ' ' + role if role else ''
        self.server._line(c, f'HELLO 1 {who["id"]} {who["token"]}{suffix}'.encode())
        return c
    def admin(self, request):
        c = {'out': bytearray(), 'closing': False}
        self.server._admin_line(c, json.dumps(request).encode())
        return json.loads(c['out'])
    def replace(self, revision=0, enabled=True, seed=7):
        return self.admin({'command':'world_rules','action':'replace','expected_revision':revision,
                           'rules':{'wild_shuffle':{'enabled':enabled,'seed':seed}}})
    def test_defaults_and_legacy_compatible(self):
        s = self.admin({'command':'world_rules','action':'status'})
        self.assertEqual(s['revision'],0)
        self.assertEqual(s['rules'], {'wild_shuffle': {'enabled': False, 'seed': 1}})
        legacy = self.conn(self.alice, 'SOCIALTRAVELCHATRALLY')
        self.assertIn(b'WELCOME', legacy['out'])
        self.assertNotIn(b'RULES ', legacy['out'])
        capable = self.conn(self.bob, 'SOCIALTRAVELCHATRALLYRULES1')
        self.assertIn(b'RULES 1 0 0 1\n', capable['out'])
    def test_world_rule_rejects_old_clients_and_does_not_expose_tokens(self):
        self.assertTrue(self.replace()['ok'])
        old = self.conn(self.alice, 'SOCIALTRAVELCHATRALLY')
        self.assertEqual(old['out'], b'ERROR RULES_REQUIRED\n')
        older = self.conn(self.alice, '')
        self.assertEqual(older['out'], b'ERROR RULES_REQUIRED\n')
        capable = self.conn(self.bob, 'SOCIALTRAVELCHATRALLYRULES1')
        self.assertIn(b'RULES 1 1 1 7\n', capable['out'])
        self.assertNotIn(self.bob['token'].encode(), capable['out'])
    def test_rules_are_private_to_world_durable_and_cas_guarded(self):
        self.assertTrue(self.replace()['ok'])
        self.assertFalse(self.replace()['ok'])
        self.assertFalse(self.replace(1, seed=21)['ok'])
        self.assertEqual(self.server.world_rules.status()['revision'], 1)
        other_db = sqlite3.connect(':memory:')
        try: self.assertEqual(WorldRules(other_db).status()['revision'], 0)
        finally: other_db.close()
        self.server.close()
        self.server = MemoryAuthority(self.root / 'socket', self.root / 'world')
        self.assertEqual(self.server.world_rules.status()['rules']['wild_shuffle'], {'enabled': True, 'seed': 7})
    def test_live_change_blocked_and_bad_capability_not_accepted(self):
        c = self.conn(self.alice, 'SOCIALRULES1')
        self.assertIn(b'WELCOME', c['out'])
        result = self.replace()
        self.assertFalse(result['ok'])
        self.assertIn('leave', result['error'])
        self.assertEqual(self.server.world_rules.status()['revision'],0)
        bad = self.conn(self.bob, 'CONTROLRULES1')
        self.assertIn(b'ERROR AUTH', bad['out'])
    def test_rule_change_and_legacy_admission_are_atomic(self):
        barrier = threading.Barrier(2)
        outcomes = {}
        def admit():
            barrier.wait()
            outcomes['client'] = self.conn(self.alice, 'SOCIAL')
        def change():
            barrier.wait()
            outcomes['change'] = self.replace()
        a = threading.Thread(target=admit)
        b = threading.Thread(target=change)
        a.start(); b.start(); a.join(); b.join()
        admitted = b'WELCOME' in outcomes['client']['out']
        enabled = outcomes['change']['ok']
        self.assertNotEqual(admitted, enabled)
        self.assertEqual(self.server.world_rules.requires_capability(), enabled)

    def test_schema_rejects_bool_seed_and_unknown_keys(self):
        self.assertFalse(self.replace(seed=True)['ok'])
        result = self.admin({'command':'world_rules','action':'replace','expected_revision':0,
                             'rules':{'wild_shuffle':{'enabled':True,'seed':1},'arbitrary':'x'}})
        self.assertFalse(result['ok'])
        self.assertEqual(self.server.world_rules.status()['revision'],0)
