"""World-options UI contract checks. All admin requests are replaced in process."""
import copy
import importlib.util
import json
from pathlib import Path
import sqlite3
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from world.rules_ui import options_snapshot, replace_options
from world.world_rules import DEFAULT_RULES
from world.session import SessionError
from world.web_launcher import LauncherBridge


class RulesUiTests(unittest.TestCase):
    def setUp(self):
        self.key = 'e-localworld12'
        self.worlds = [{'key': self.key, 'name': 'Cave lab'}]
        self.status = {'ok': True, 'version': 2, 'revision': 4,
                       'rules': {'wild_shuffle': {'enabled': False, 'seed': 1}, **dict.fromkeys(('reusable_tms', 'evolution_items_from_bag', 'party_exp_share'), False)}}
        self.authority = Mock()
        self.authority.status.side_effect = lambda: copy.deepcopy(self.status)
        self.server = SimpleNamespace(_closed=False, world_rules=self.authority,
                                      lock=threading.RLock(), peers={})
        self.session = SimpleNamespace(state=Path('/tmp') / self.key,
            server=self.server, _hosts={}, _world=Mock(return_value=Path('/tmp') / self.key))
        self.payload = {'world': self.key, 'expected_revision': 4, 'confirmed': True,
                        'rules': {'wild_shuffle': {'enabled': True, 'seed': 12}, **dict.fromkeys(('reusable_tms', 'evolution_items_from_bag', 'party_exp_share'), False)}}
        self.saved = {'ok': True, 'version': 2, 'revision': 5, 'rules': self.payload['rules']}
        self.admin = self.enterContext(patch('world.rules_ui.admin_request', return_value=self.saved))

    def replace(self, payload=None, engine='expansion-native'):
        return replace_options(self.session, self.worlds, engine, self.payload if payload is None else payload)

    def test_snapshot_reads_only_existing_authority_without_writes_or_admin_requests(self):
        value = options_snapshot(self.session, self.worlds)[self.key]
        self.assertEqual(value, {key: val for key, val in self.status.items() if key != 'ok'} | {'status': 'ready', 'players': 0})
        value['rules']['wild_shuffle']['seed'] = 20
        self.assertEqual(self.status['rules']['wild_shuffle']['seed'], 1)
        self.authority.replace.assert_not_called()
        self.admin.assert_not_called()

    def test_detached_local_host_is_readable_and_editable_without_changing_selection(self):
        self.session._hosts[self.key] = (self.server, None, None)
        self.session.state, self.session.server = Path('/tmp/hosted-remote'), None
        self.assertEqual(options_snapshot(self.session, self.worlds)[self.key]['status'], 'ready')
        self.replace()
        self.assertEqual(self.session.state.name, 'hosted-remote')
        self.admin.assert_called_once()

    def test_closed_stopped_and_older_hosts_never_get_invented_defaults(self):
        for server, expected in ((None, 'stopped'), (SimpleNamespace(_closed=True), 'stopped'),
                                 (SimpleNamespace(_closed=False), 'unsupported')):
            with self.subTest(expected=expected):
                self.session.server = server
                self.assertEqual(options_snapshot(self.session, self.worlds), {self.key: {'status': expected}})
                with self.assertRaises(SessionError):
                    self.replace()
        self.admin.assert_not_called()

    def test_unknown_or_malformed_schema_fails_closed(self):
        candidates = [self.status | {'version': 1}, self.status | {'version': True},
            self.status | {'revision': True}, self.status | {'revision': -1},
            self.status | {'rules': {'wild_shuffle': {'enabled': False, 'seed': True}}},
            self.status | {'rules': {'wild_shuffle': {'enabled': False, 'seed': 21}}},
            self.status | {'rules': self.status['rules'] | {'mega': True}}, None]
        for status in candidates:
            with self.subTest(status=status):
                self.authority.status.side_effect = lambda: status
                self.assertEqual(options_snapshot(self.session, self.worlds)[self.key], {'status': 'incompatible'})
                with self.assertRaises(SessionError):
                    self.replace()
        self.admin.assert_not_called()

    def test_read_error_does_not_expose_private_paths(self):
        self.authority.status.side_effect = RuntimeError('/private/world/secret')
        self.assertEqual(options_snapshot(self.session, self.worlds)[self.key], {'status': 'error'})

    def test_only_explicitly_reviewed_exact_known_changes_can_be_sent(self):
        cases = [self.payload | {'confirmed': False}, self.payload | {'confirmed': 1},
            self.payload | {'extra': True}, self.payload | {'expected_revision': True},
            self.payload | {'expected_revision': 2147483647},
            self.payload | {'rules': {'wild_shuffle': {'enabled': 1, 'seed': 1}}},
            self.payload | {'rules': {'wild_shuffle': {'enabled': True, 'seed': 0}}},
            self.payload | {'rules': {'wild_shuffle': {'enabled': True, 'seed': 1, 'debug': True}}},
            self.payload | {'rules': self.payload['rules'] | {'tera': True}}, None]
        for payload in cases:
            with self.subTest(payload=payload), self.assertRaises(SessionError):
                replace_options(self.session, self.worlds, 'expansion-native', payload)
        self.admin.assert_not_called()

    def test_remote_unknown_and_arbitrary_paths_cannot_be_administered(self):
        for key in ('hosted-remote', '../localworld12', '/tmp/admin.sock', None, {}, 'unknown'):
            with self.subTest(key=key), self.assertRaises(SessionError):
                self.replace(self.payload | {'world': key})
        self.admin.assert_not_called()
        self.session._world.assert_not_called()

    def test_revision_and_live_players_are_checked_without_disconnect(self):
        with self.assertRaisesRegex(SessionError, 'changed'):
            self.replace(self.payload | {'expected_revision': 3})
        self.server.peers = {'trainer': {'closing': False}}
        with self.assertRaisesRegex(SessionError, 'All players must leave'):
            self.replace()
        self.admin.assert_not_called()

    def test_replacement_uses_existing_private_atomic_admin_contract_and_engine_namespace(self):
        self.server.peers = {'leaving': {'closing': True}}
        self.replace()
        self.admin.assert_called_once_with('', {'command': 'world_rules', 'action': 'replace',
            'expected_revision': 4, 'rules': self.payload['rules']},
            admin_path=Path('/tmp') / self.key / 'engines/expansion-native/admin.sock')
        self.authority.replace.assert_not_called()
        self.admin.reset_mock()
        self.replace(engine='vanilla')
        self.assertEqual(self.admin.call_args.kwargs['admin_path'], Path('/tmp') / self.key / 'admin.sock')

    def test_unchanged_default_never_writes_or_bumps_revision(self):
        self.replace(self.payload | {'rules': copy.deepcopy(self.status['rules'])})
        self.admin.assert_not_called()

    def test_server_admission_and_revision_races_are_not_retried(self):
        for error, expected in [('world rules changed; refresh and retry', 'changed'),
                ('All players must leave before changing world rules.', 'All players must leave'),
                ('private /path/token', 'host rejected'), ([], 'host rejected')]:
            with self.subTest(error=error):
                self.admin.reset_mock()
                self.admin.return_value = {'ok': False, 'error': error}
                with self.assertRaisesRegex(SessionError, expected):
                    self.replace()
                self.admin.assert_called_once()

    def test_timeout_malformed_and_unexpected_replies_are_uncertain_not_retried(self):
        for response in (None, {}, self.saved | {'revision': 6}, self.saved | {'rules': self.status['rules']}):
            self.admin.reset_mock()
            self.admin.return_value = response
            with self.assertRaisesRegex(SessionError, 'could not be confirmed'):
                self.replace()
            self.admin.assert_called_once()
        self.admin.side_effect = TimeoutError('private socket path')
        with self.assertRaisesRegex(SessionError, 'Refresh world options'):
            self.replace()

    def test_bridge_routes_replace_and_refresh_without_opening_or_launching_world(self):
        session = Mock(engine='expansion-native', root=Path('/tmp/unused-rules-ui'))
        bridge = LauncherBridge(session, '/no/game', engine='expansion-native')
        with patch.object(bridge, 'local_expeditions', return_value=self.worlds), patch.object(bridge, 'snapshot', return_value={}) as snapshot, patch('world.rules_ui.replace_options') as replace:
            self.assertEqual(bridge.action('rules_replace', self.payload), {})
            replace.assert_called_once_with(session, self.worlds, 'expansion-native', self.payload)
            bridge.action('rules_refresh', {})
            self.assertEqual(snapshot.call_count, 2)
            self.assertEqual(replace.call_count, 1)
        session.host.assert_not_called()
        session.disconnect.assert_not_called()
        session.launch.assert_not_called()


@unittest.skipUnless(importlib.util.find_spec('world.world_rules'), 'World-rules authority is not installed on this branch')
class RulesAuthorityCompatibilityTests(unittest.TestCase):
    def test_v2_document_is_readable_and_shuffle_edit_preserves_all_gameplay_flags(self):
        flags = {'reusable_tms': True, 'evolution_items_from_bag': False, 'party_exp_share': True}
        self.server.world_rules.replace({'wild_shuffle': {'enabled': False, 'seed': 7}, **flags}, 0)
        before = options_snapshot(self.session, self.worlds)['e-localworld12']
        self.assertEqual(before['status'], 'ready')
        self.assertEqual(before['version'], 3)
        rules = copy.deepcopy(before['rules'])
        rules['wild_shuffle']['seed'] = 13
        replace_options(self.session, self.worlds, 'expansion-native',
                        dict(self.payload, expected_revision=1, rules=rules))
        self.assertEqual(self.server.world_rules.status()['rules'], rules)
        self.assertEqual({key: rules[key] for key in flags}, flags)
        self.assertEqual(self.server.world_rules.status()['revision'], 2)

    """Runs against the real optional authority when it is integrated, without sockets."""
    def setUp(self):
        from world.world_rules import WorldRules
        from world.server import WorldServer
        database = sqlite3.connect(':memory:')
        self.addCleanup(database.close)
        self.server = WorldServer.__new__(WorldServer)
        self.server._closed = False
        self.server.lock = threading.RLock()
        self.server.peers = {}
        self.server.world_rules = WorldRules(database)
        self.server._queue = lambda conn, text: conn['out'].extend(text.encode())
        self.server._record_error = Mock()
        self.session = SimpleNamespace(state=Path('/tmp/e-localworld12'), server=self.server,
            _hosts={}, _world=lambda key: Path('/tmp') / key)
        self.worlds = [{'key': 'e-localworld12'}]
        self.payload = {'world': 'e-localworld12', 'expected_revision': 0, 'confirmed': True,
                        'rules': {'wild_shuffle': {'enabled': True, 'seed': 20}, **{key: value for key, value in DEFAULT_RULES.items() if key != 'wild_shuffle'}}}
        self.request = self.enterContext(patch('world.rules_ui.admin_request', side_effect=self.admin))

    def admin(self, unused, request, **kwargs):
        conn = {'out': bytearray(), 'closing': False}
        self.server._admin_line(conn, json.dumps(request).encode())
        return json.loads(conn['out'])

    def test_real_authority_read_review_replace_and_refresh(self):
        before = options_snapshot(self.session, self.worlds)['e-localworld12']
        self.assertEqual(before['rules'], {'wild_shuffle': {'enabled': False, 'seed': 1}, **{key: value for key, value in DEFAULT_RULES.items() if key != 'wild_shuffle'}})
        replace_options(self.session, self.worlds, 'expansion-native', self.payload)
        after = options_snapshot(self.session, self.worlds)['e-localworld12']
        self.assertEqual(after['revision'], 1)
        self.assertEqual(after['rules'], self.payload['rules'])
        self.assertEqual(self.server.world_rules.line(), 'RULES 1 1 1 20\n')
        self.request.assert_called_once()

    def test_real_authority_blocks_a_player_arriving_after_ui_preflight(self):
        def race(*args, **kwargs):
            self.server.peers['arrived'] = {'closing': False}
            return self.admin(*args, **kwargs)
        self.request.side_effect = race
        with self.assertRaisesRegex(SessionError, 'All players must leave'):
            replace_options(self.session, self.worlds, 'expansion-native', self.payload)
        self.assertEqual(self.server.world_rules.status()['revision'], 0)

    def test_real_authority_blocks_an_edit_arriving_after_ui_preflight(self):
        def race(*args, **kwargs):
            self.server.world_rules.replace({'wild_shuffle': {'enabled': False, 'seed': 5}}, 0)
            return self.admin(*args, **kwargs)
        self.request.side_effect = race
        with self.assertRaisesRegex(SessionError, 'changed'):
            replace_options(self.session, self.worlds, 'expansion-native', self.payload)
        self.assertEqual(self.server.world_rules.status()['rules']['wild_shuffle']['seed'], 5)


if __name__ == '__main__':
    unittest.main()
