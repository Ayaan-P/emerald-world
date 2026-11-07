"""RC10 versioned authority using production SQLite and disposable sockets."""
import copy
import json
from pathlib import Path
import socket
import sqlite3
import tempfile
import unittest
from world.world_rules import WorldRules, GAMEPLAY_BITS

NEW_BITS = {'mega_primal': 8, 'z_moves': 16, 'dynamax': 32, 'terastallization': 64,
            'expanded_species_pool': 128, 'pokemon_follower': 256}

class Rc10Authority(unittest.TestCase):
    def test_each_new_bit_has_durable_cas_and_versioned_admission(self):
        self.assertEqual({k: GAMEPLAY_BITS.get(k) for k in NEW_BITS}, NEW_BITS)
        for key, bit in NEW_BITS.items():
            with self.subTest(key=key), sqlite3.connect(':memory:') as db:
                a = WorldRules(db)
                initial = a.status()
                self.assertEqual(initial['version'], 3)
                self.assertTrue(all(initial['rules'][k] is False for k in GAMEPLAY_BITS))
                rules = dict(initial['rules'], **{key: True})
                a.replace(rules, 0)
                self.assertEqual(a.line(3), f'RULES 3 1 0 1 {bit}\n')
                for version in (0, 1, 2):
                    self.assertTrue(a.requires_capability(version))
                    with self.assertRaises(ValueError): a.line(version)
                self.assertFalse(a.requires_capability(3))
                self.assertEqual(WorldRules(db).status()['rules'], rules)
                with self.assertRaises(ValueError): a.replace(rules, 0)
                with self.assertRaises(ValueError): a.replace(dict(rules, unknown=True), 1)
                with self.assertRaises(ValueError): a.replace(dict(rules, **{key: 1}), 1)
                # An old editor may not reset invisible V3 flags.
                with self.assertRaises(ValueError): a.replace({'wild_shuffle': rules['wild_shuffle']}, 1)
                self.assertEqual(a.status()['revision'], 1)

    def test_v1_v2_rows_adapt_without_touching_progress_or_stored_bytes(self):
        for flags in ({}, {'reusable_tms': True, 'evolution_items_from_bag': False, 'party_exp_share': True}):
            with self.subTest(flags=flags), sqlite3.connect(':memory:') as db:
                a = WorldRules(db)
                db.execute('CREATE TABLE private_progress (value TEXT)')
                db.execute('INSERT INTO private_progress VALUES (?)', ('private fixture',))
                old = {'wild_shuffle': {'enabled': True, 'seed': 8}, **flags}
                encoded = json.dumps(old, indent=2)
                db.execute('UPDATE world_rules SET revision=6,value=?', (encoded,))
                db.commit()
                a = WorldRules(db)
                state = a.status()
                self.assertEqual(state['version'], 3)
                self.assertTrue(all(state['rules'][key] is False for key in NEW_BITS))
                self.assertEqual(a.line(2), f'RULES 2 6 1 8 {5 if flags else 0}\n')
                self.assertEqual(db.execute('SELECT revision,value FROM world_rules').fetchone(), (6, encoded))
                self.assertEqual(db.execute('SELECT value FROM private_progress').fetchone(), ('private fixture',))
                if not flags: self.assertEqual(a.line(1), 'RULES 1 6 1 8\n')
                for bad in ({**state['rules'], 'unknown': False}, {**old, 'dynamax': False}):
                    with self.assertRaises(ValueError): a.replace(bad, 6)

    def test_real_socket_v3_admission_old_clients_private_admin_and_live_guard(self):
        from world.server import WorldServer
        from world.client import admin_request
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            server = WorldServer(root/'sock', root/'world')
            identity = server.create_identity('Alice')
            server.start()
            try:
                request = {'command': 'world_rules', 'action': 'status'}
                state = admin_request(root/'sock', request)
                rules = {**state['rules'], **dict.fromkeys(GAMEPLAY_BITS, True)}
                request = {'command': 'world_rules', 'action': 'replace', 'expected_revision': 0, 'rules': rules}
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as public:
                    public.settimeout(3); public.connect(str(root/'sock'))
                    public.sendall(json.dumps(request).encode()+b'\n')
                    self.assertEqual(public.recv(1024), b'ERROR AUTH\n')
                self.assertTrue(admin_request(root/'sock', request)['ok'])
                for role in ('SOCIAL', 'SOCIALRULES1', 'SOCIALRULES2', 'SOCIALTRAVELCHATRALLYPEER32CAVE16RULES3'):
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                        client.settimeout(3); client.connect(str(root/'sock'))
                        client.sendall(f'HELLO 1 {identity["id"]} {identity["token"]} {role}\n'.encode())
                        with client.makefile('rb') as wire:
                            first = wire.readline()
                            if role.endswith('RULES3'):
                                self.assertTrue(first.startswith(b'WELCOME 1 Alice '), first)
                                self.assertEqual(wire.readline(), b'RULES 3 1 0 1 511\n')
                                request['expected_revision'] = 1
                                rejected = admin_request(root/'sock', request)
                                self.assertFalse(rejected['ok']); self.assertIn('leave', rejected['error'])
                            else: self.assertEqual(first, b'ERROR RULES_REQUIRED\n')
                self.assertEqual(server.world_rules.status()['revision'], 1)
                self.assertFalse(list(root.rglob('*.sav')))
            finally: server.close()

if __name__ == '__main__': unittest.main()
