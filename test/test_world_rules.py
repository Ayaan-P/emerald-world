"""World-rule storage and authenticated admission; no sockets or player saves."""
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from world.server import WorldServer
from world.world_rules import DEFAULT_RULES

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
        self.assertTrue(s['ok'], s)
        self.assertEqual(s['revision'],0)
        self.assertEqual(s['rules'], DEFAULT_RULES)
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
        from world.world_rules import WorldRules
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

    def test_rules_capability_composes_with_current_peer_and_cave_roles(self):
        self.assertTrue(self.replace()['ok'])
        c = self.conn(self.alice, 'SOCIALTRAVELCHATRALLYPEER32CAVE16RULES1')
        self.assertIn(b'RULES 1 1 1 7\n', c['out'])
        self.assertEqual(c['peer_limit'], 32)
        for flag in ('chat', 'travel', 'cave_xl', 'cave_expansion', 'rules_capable'):
            self.assertTrue(c[flag], flag)

    def test_enabled_rules_do_not_bypass_authentication_or_host_bans(self):
        self.assertTrue(self.replace()['ok'])
        invalid = dict(self.alice, token='0' * 64)
        self.assertEqual(self.conn(invalid, 'SOCIALRULES1')['out'], b'ERROR AUTH\n')
        self.assertTrue(self.admin({'command': 'host_controls', 'action': 'remove',
                                    'trainer': 'Alice'})['ok'])
        self.assertEqual(self.conn(self.alice, 'SOCIALRULES1')['out'], b'ERROR REMOVED\n')
        self.assertEqual(self.server.peers, {})

    def test_rule_refusal_does_not_replace_mechanic_error(self):
        self.server._record_error(ValueError('existing mechanic diagnostic'))
        self.conn(self.alice, 'SOCIALRULES1')
        self.assertFalse(self.replace()['ok'])
        self.assertEqual(self.server.module_error, 'existing mechanic diagnostic')

    def test_v2_defaults_persistence_mask_and_capability_admission(self):
        state = self.admin({'command': 'world_rules', 'action': 'status'})
        self.assertEqual(state['version'], 3)
        for key in ('reusable_tms', 'evolution_items_from_bag', 'party_exp_share'):
            self.assertIs(state['rules'][key], False)
        rules = dict(state['rules'], reusable_tms=True, evolution_items_from_bag=True,
                     party_exp_share=True)
        result = self.admin({'command': 'world_rules', 'action': 'replace',
                             'expected_revision': 0, 'rules': rules})
        self.assertTrue(result['ok'], result)
        self.assertEqual(self.conn(self.alice, 'SOCIALRULES1')['out'], b'ERROR RULES_REQUIRED\n')
        self.assertEqual(self.conn(self.alice, 'SOCIAL')['out'], b'ERROR RULES_REQUIRED\n')
        c = self.conn(self.bob, 'SOCIALTRAVELCHATRALLYPEER32CAVE16RULES2')
        self.assertIn(b'RULES 2 1 0 1 7\n', c['out'])
        self.assertTrue(c['cave_expansion'])
        self.server.close()
        self.server = MemoryAuthority(self.root / 'socket', self.root / 'world')
        self.assertEqual(self.server.world_rules.status()['rules'], rules)

    def test_v2_each_mask_bit_strict_schema_and_live_revision_guards(self):
        from world.world_rules import WorldRules
        defaults = self.server.world_rules.status()['rules']
        for key, bit in (('reusable_tms', 1), ('evolution_items_from_bag', 2), ('party_exp_share', 4)):
            with self.subTest(key=key), sqlite3.connect(':memory:') as db:
                authority = WorldRules(db)
                rules = dict(defaults, **{key: True})
                authority.replace(rules, 0)
                self.assertEqual(authority.line(2), f'RULES 2 1 0 1 {bit}\n')
                self.assertTrue(authority.requires_capability(1))
                self.assertFalse(authority.requires_capability(2))
                with self.assertRaises(ValueError): authority.line(1)
                for bad in (0, 1, None, 'true', [], {}):
                    with self.assertRaises(ValueError): authority.replace(dict(rules, **{key: bad}), 1)
                with self.assertRaises(ValueError): authority.replace(rules, True)
                with self.assertRaises(ValueError): authority.replace(rules, 0)
                with self.assertRaises(ValueError): authority.replace(dict(rules, unsupported=True), 1)
                with self.assertRaises(ValueError): authority.replace({'wild_shuffle': defaults['wild_shuffle'], key: True}, 1)
                self.assertEqual(authority.status()['revision'], 1)
        c = self.conn(self.alice, 'SOCIALRULES2')
        self.assertIn(b'RULES 2 0 0 1 0\n', c['out'])
        result = self.admin({'command': 'world_rules', 'action': 'replace',
                             'expected_revision': 0, 'rules': dict(defaults, party_exp_share=True)})
        self.assertFalse(result['ok'])
        self.assertIn('leave', result['error'])
        self.assertEqual(self.server.world_rules.status()['revision'], 0)

    def test_v1_stored_document_is_adapted_without_rewriting_original(self):
        from world.world_rules import WorldRules
        with sqlite3.connect(':memory:') as db:
            WorldRules(db)
            original = '{"wild_shuffle": {"enabled": true, "seed": 8}}'
            db.execute('UPDATE world_rules SET revision=6, value=?', (original,))
            db.commit()
            authority = WorldRules(db)
            self.assertEqual(authority.status()['version'], 3)
            self.assertEqual(authority.line(1), 'RULES 1 6 1 8\n')
            self.assertEqual(authority.line(2), 'RULES 2 6 1 8 0\n')
            self.assertEqual(db.execute('SELECT revision, value FROM world_rules').fetchone(), (6, original))
            db.execute('UPDATE world_rules SET value=?', ('{"party_exp_share":1}',))
            db.commit()
            with self.assertRaises(ValueError): WorldRules(db)

    def test_v2_real_private_admin_socket_and_public_admission(self):
        import socket
        from world.client import admin_request
        self.server.close()
        self.server = WorldServer(self.root / 'socket', self.root / 'world').start()
        state = admin_request(self.root / 'socket', {'command': 'world_rules', 'action': 'status'})
        request = {'command': 'world_rules', 'action': 'replace', 'expected_revision': 0,
                   'rules': dict(state['rules'], reusable_tms=True, party_exp_share=True)}
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as public:
            public.settimeout(3)
            public.connect(str(self.root / 'socket'))
            public.sendall(json.dumps(request).encode() + b'\n')
            self.assertEqual(public.recv(1024), b'ERROR AUTH\n')
        self.assertEqual(admin_request(self.root / 'socket', {'command': 'world_rules', 'action': 'status'})['revision'], 0)
        self.assertTrue(admin_request(self.root / 'socket', request)['ok'])
        for role, expected in (('SOCIALRULES1', b'ERROR RULES_REQUIRED\n'),
                               ('SOCIALRULES2', b'RULES 2 1 0 1 5\n')):
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(3)
                client.connect(str(self.root / 'socket'))
                client.sendall(f'HELLO 1 {self.alice["id"]} {self.alice["token"]} {role}\n'.encode())
                with client.makefile('rb') as wire:
                    first = wire.readline()
                    if role.endswith('RULES2'):
                        self.assertTrue(first.startswith(b'WELCOME 1 Alice '))
                        self.assertEqual(wire.readline(), expected)
                        request['expected_revision'] = 1
                        self.assertFalse(admin_request(self.root / 'socket', request)['ok'])
                    else:
                        self.assertEqual(first, expected)
        self.assertFalse(list((self.root / 'world').rglob('*.sav')))

    def test_schema_rejects_bool_seed_and_unknown_keys(self):
        self.assertFalse(self.replace(seed=True)['ok'])
        result = self.admin({'command':'world_rules','action':'replace','expected_revision':0,
                             'rules':{'wild_shuffle':{'enabled':True,'seed':1},'arbitrary':'x'}})
        self.assertFalse(result['ok'])
        self.assertEqual(self.server.world_rules.status()['revision'],0)
