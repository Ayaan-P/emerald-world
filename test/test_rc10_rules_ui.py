"""V3 complete-document adapter, retaining owner guards and uncertain writes."""
import copy
import sqlite3
import threading
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from world.world_rules import WorldRules, GAMEPLAY_BITS
from world.rules_ui import options_snapshot, replace_options
from world.session import SessionError

class Rc10RulesUi(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:'); self.addCleanup(self.db.close)
        self.authority = WorldRules(self.db)
        self.key = 'e-localworld12'; self.worlds = [{'key': self.key}]
        self.server = SimpleNamespace(_closed=False, world_rules=self.authority, lock=threading.RLock(), peers={})
        self.session = SimpleNamespace(state=Path('/tmp')/self.key, server=self.server, _hosts={}, _world=lambda key: Path('/tmp')/key)

    def test_v3_snapshot_and_shuffle_edit_preserve_every_flag(self):
        original = self.authority.status()['rules']
        original.update(dict.fromkeys(GAMEPLAY_BITS, True))
        self.authority.replace(original, 0)
        before = options_snapshot(self.session, self.worlds)[self.key]
        self.assertEqual(before['status'], 'ready')
        self.assertEqual(before['version'], 3)
        rules = copy.deepcopy(before['rules']); rules['wild_shuffle']['seed'] = 13
        def save(unused, request, **kwargs):
            self.assertEqual(request['rules'], rules)
            return self.authority.replace(request['rules'], request['expected_revision'])
        with patch('world.rules_ui.admin_request', side_effect=save) as request:
            replace_options(self.session, self.worlds, 'expansion-native',
                {'world': self.key, 'expected_revision': 1, 'rules': rules, 'confirmed': True})
            request.assert_called_once()
        self.assertEqual(self.authority.status()['rules'], rules)
        self.assertTrue(all(rules[k] for k in GAMEPLAY_BITS))

    def test_v3_owner_live_revision_and_uncertain_write_guards(self):
        payload = {'world': self.key, 'expected_revision': 0, 'confirmed': True,
                   'rules': dict(self.authority.status()['rules'], mega_primal=True)}
        with patch('world.rules_ui.admin_request', side_effect=TimeoutError) as request:
            with self.assertRaisesRegex(SessionError, 'could not be confirmed'):
                replace_options(self.session, self.worlds, 'expansion-native', payload)
            request.assert_called_once(); request.reset_mock()
            for update in ({'world': '../other'}, {'confirmed': False}, {'expected_revision': 1}):
                with self.assertRaises(SessionError):
                    replace_options(self.session, self.worlds, 'expansion-native', payload | update)
            self.server.peers['arrived'] = {'closing': False}
            with self.assertRaisesRegex(SessionError, 'All players must leave'):
                replace_options(self.session, self.worlds, 'expansion-native', payload)
            request.assert_not_called()

if __name__ == '__main__': unittest.main()
