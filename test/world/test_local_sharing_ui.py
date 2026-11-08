"""Real invitation storage with substituted TLS listeners. Never opens sockets."""
import json
from pathlib import Path
import socket
import sqlite3
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from world.local_sharing_ui import sharing_snapshot, start_sharing, stop_sharing, export_friend
from world.server import WorldServer
from world.session import DesktopSession, SessionError
from world.web_launcher import LauncherBridge


class LocalSharingTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(socket, 'socket', side_effect=AssertionError('No socket tests')))
        temp = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(temp)
        self.world = self.root / 'e-localworld12'
        self.world.mkdir(mode=0o700)
        self.server = WorldServer.__new__(WorldServer)
        self.server.root = self.world
        self.server._closed = False
        self.server.lock = threading.RLock()
        self.server.db = sqlite3.connect(':memory:')
        self.addCleanup(self.server.db.close)
        self.server.db.execute('CREATE TABLE identities (id TEXT PRIMARY KEY, token TEXT, save_path TEXT)')
        self.session = DesktopSession(self.root, engine='expansion-native')
        self.session.state = self.world
        self.session.server = self.server
        self.session.remote_trainer = 'Owner'
        self.broker = SimpleNamespace(address=('192.168.1.20', 8765), _stop=threading.Event(),
                                      _thread=Mock(is_alive=Mock(return_value=True)), close=Mock())
        self.session.broker = self.broker
        self.session.sharing_pin = 'a' * 64
        self.worlds = [{'key': self.world.name}]
        self.invite = {'world': self.world.name, 'trainer': 'Friend', 'host': '192.168.1.20', 'port': 8765,
                       'existing': False, 'confirmed': True, 'reviewed_pin': 'a' * 64,
                       'reviewed_listener': {'host': '192.168.1.20', 'port': 8765}}
        self.start = {'world': self.world.name, 'listen_host': '192.168.1.20', 'port': 8765, 'confirmed': True}

    def test_snapshot_shows_listener_not_reachability_and_no_credentials(self):
        status = sharing_snapshot(self.session, self.worlds)[self.world.name]
        self.assertEqual(status, {'running': True, 'selected': True, 'configured': True, 'listening': True,
                                 'endpoint': {'host': '192.168.1.20', 'port': 8765}, 'pin': 'a' * 64})
        self.assertNotIn('token', json.dumps(status))
        self.assertNotIn('private-key', json.dumps(status))
        self.broker._thread.is_alive.return_value = False
        self.assertFalse(sharing_snapshot(self.session, self.worlds)[self.world.name]['listening'])

    def test_detached_host_status_remains_visible_but_actions_require_explicit_open(self):
        self.session._hosts[self.world.name] = (self.server, self.broker, self.session.sharing_pin)
        self.session.state = None
        self.session.server = self.session.broker = self.session.sharing_pin = None
        status = sharing_snapshot(self.session, self.worlds)[self.world.name]
        self.assertTrue(status['listening'])
        self.assertFalse(status['selected'])
        with self.assertRaisesRegex(SessionError, 'Open this local host'):
            export_friend(self.session, self.worlds, self.invite)

    def test_enable_validates_scope_confirmation_and_address_before_tls_creation(self):
        self.session.broker = None
        with patch.object(self.session, 'tls_material', return_value=('cert', 'key')) as tls, patch.object(self.session, 'share') as share:
            for payload in (self.start | {'confirmed': False}, self.start | {'world': 'remote-world'},
                            self.start | {'port': True}, self.start | {'port': 0}, self.start | {'port': 65536},
                            self.start | {'listen_host': 'host.example'}, self.start | {'listen_host': '224.0.0.1'},
                            self.start | {'listen_host': 'fe80::1%eth0'}, self.start | {'listen_host': '::ffff:224.0.0.1'}, self.start | {'cert': '/secret'}):
                with self.subTest(payload=payload), self.assertRaises(SessionError):
                    start_sharing(self.session, self.worlds, payload)
            tls.assert_not_called()
            share.assert_not_called()
            start_sharing(self.session, self.worlds, self.start)
            tls.assert_called_once()
            share.assert_called_once_with('cert', 'key', ('192.168.1.20', 8765))

    def test_existing_listener_is_never_replaced_by_enable(self):
        with patch.object(self.session, 'tls_material') as tls:
            with self.assertRaisesRegex(SessionError, 'already configured'):
                start_sharing(self.session, self.worlds, self.start)
            tls.assert_not_called()
        self.broker.close.assert_not_called()

    def test_stop_closes_only_selected_tls_broker_not_authority_or_local_game(self):
        process = Mock()
        self.session.games = {'Owner': (process, {})}
        other = Mock()
        self.session._hosts['other'] = (Mock(), other, 'b' * 64)
        stop_sharing(self.session, self.worlds, {'world': self.world.name, 'confirmed': True})
        self.broker.close.assert_called_once()
        self.assertIsNone(self.session.broker)
        self.assertIs(self.session.server, self.server)
        self.assertFalse(self.server._closed)
        process.terminate.assert_not_called()
        other.close.assert_not_called()

    def test_new_invitation_uses_actual_session_format_and_native_identity_without_save_writes(self):
        raw = export_friend(self.session, self.worlds, self.invite)
        invite = json.loads(raw)
        self.assertEqual(invite['endpoint'], self.invite['reviewed_listener'])
        self.assertEqual(invite['trainer'], 'Friend')
        self.assertEqual(invite['pin'], 'a' * 64)
        self.assertEqual(len(invite['token']), 64)
        self.assertEqual(self.server.db.execute('SELECT token FROM identities WHERE id=?', ('Friend',)).fetchone()[0], invite['token'])
        self.assertEqual(list(self.world.rglob('*.sav')), [])
        self.assertEqual(list(self.world.rglob('*.json')), [])

    def test_existing_identity_requires_explicit_reexport_and_keeps_same_credential(self):
        first = json.loads(export_friend(self.session, self.worlds, self.invite))
        with self.assertRaisesRegex(SessionError, 'already exists'):
            export_friend(self.session, self.worlds, self.invite)
        second = json.loads(export_friend(self.session, self.worlds, self.invite | {'existing': True}))
        self.assertEqual(first, second)
        with self.assertRaisesRegex(SessionError, 'does not exist'):
            export_friend(self.session, self.worlds, self.invite | {'trainer': 'New', 'existing': True})

    def test_owner_unknown_world_stale_listener_and_invalid_endpoint_are_rejected_before_identity(self):
        for changes in ({'trainer': 'Owner'}, {'world': 'hosted-remote'}, {'confirmed': False}, {'existing': 1},
                        {'host': '0.0.0.0'}, {'host': 'host/name'}, {'host': '::1'}, {'port': True},
                        {'trainer': '../path'}, {'reviewed_pin': 'b' * 64}, {'reviewed_listener': {'host': '192.168.1.20', 'port': 9876}}):
            with self.subTest(changes=changes), self.assertRaises(SessionError):
                export_friend(self.session, self.worlds, self.invite | changes)
        self.assertEqual(self.server.db.execute('SELECT count(*) FROM identities').fetchone()[0], 0)

    def test_loopback_listener_does_not_issue_misleading_remote_invitation(self):
        self.broker.address = ('127.0.0.1', 8765)
        payload = self.invite | {'reviewed_listener': {'host': '127.0.0.1', 'port': 8765}}
        with self.assertRaisesRegex(SessionError, 'only on this computer'):
            export_friend(self.session, self.worlds, payload)
        value = json.loads(export_friend(self.session, self.worlds, payload | {'host': '127.0.0.1'}))
        self.assertEqual(value['endpoint']['host'], '127.0.0.1')

    def test_lost_export_is_reported_uncertain_and_requires_existing_trainer_review(self):
        with patch('world.local_sharing_ui.read_invitation', side_effect=ValueError('fixture')):
            with self.assertRaisesRegex(SessionError, 'trainer may exist now'):
                export_friend(self.session, self.worlds, self.invite)
        self.assertIsNotNone(self.server.db.execute('SELECT 1 FROM identities WHERE id=?', ('Friend',)).fetchone())
        self.assertEqual(json.loads(export_friend(self.session, self.worlds, self.invite | {'existing': True}))['trainer'], 'Friend')

    def test_uppercase_pin_is_preserved_in_valid_native_invitation(self):
        self.session.sharing_pin = 'A' * 64
        value = json.loads(export_friend(self.session, self.worlds, self.invite))
        self.assertEqual(value['pin'].lower(), self.invite['reviewed_pin'])

    def test_failed_stop_keeps_broker_reference_for_explicit_refresh_and_recovery(self):
        self.broker.close.side_effect = OSError('fixture')
        with self.assertRaisesRegex(SessionError, 'shutdown could not be confirmed'):
            stop_sharing(self.session, self.worlds, {'world': self.world.name, 'confirmed': True})
        self.assertIs(self.session.broker, self.broker)
        self.assertIs(self.session.server, self.server)

    def test_mapped_ipv6_loopback_cannot_advertise_remote_access(self):
        self.broker.address = ('::ffff:127.0.0.1', 8765)
        payload = self.invite | {'reviewed_listener': {'host': self.broker.address[0], 'port': 8765}, 'host': 'world.example'}
        with self.assertRaisesRegex(SessionError, 'only on this computer'):
            export_friend(self.session, self.worlds, payload)

    def test_bridge_returns_private_download_only_on_explicit_invitation_action(self):
        bridge = LauncherBridge(self.session, '/no/game', engine='expansion-native')
        with patch.object(bridge, 'local_expeditions', return_value=self.worlds), patch.object(bridge, 'snapshot', side_effect=lambda: {'local_worlds': self.worlds}):
            result = bridge.action('local_invite', self.invite)
            self.assertEqual(result['download_kind'], 'local_friend')
            self.assertEqual(json.loads(result['download'])['trainer'], 'Friend')
            refreshed = bridge.action('local_share_refresh', {})
            self.assertNotIn('download', refreshed)


if __name__ == '__main__':
    unittest.main()
