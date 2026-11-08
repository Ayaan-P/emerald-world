"""Optional integration against the separately developed hosted client adapter.

The network and native game are not exercised by this test.
"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from world.hosting_ui import HostedLauncher, available, backup_available


@unittest.skipUnless(available(), 'hosted backend is not installed on this branch')
class HostedAdapterContract(unittest.TestCase):
    @unittest.skipUnless(backup_available(), 'profile backup module is not installed')
    def test_restore_and_backup_preserve_owner_without_network_or_overwrite(self):
        from world.hosting_client import HostingClient
        from world.session import SessionError
        with tempfile.TemporaryDirectory() as tmp:
            session = Mock(root=Path(tmp)); session.status = 'Ready'
            hosted = HostedLauncher(session)
            value = {'kind': 'host-profile', 'version': 1,
                     'endpoint': {'host': 'example.org', 'port': 8766},
                     'pin': 'a' * 64, 'token': 'b' * 64}
            with patch.object(HostingClient, '_request', side_effect=AssertionError('network forbidden')):
                hosted.restore_profile(json.dumps(value))
                self.assertTrue(hosted.enrolled())
                snapshot = hosted.state()
                self.assertEqual(snapshot['endpoint'], value['endpoint'])
                self.assertNotIn(value['token'], json.dumps(snapshot))
                self.assertNotIn(value['pin'], json.dumps(snapshot))
                self.assertEqual(json.loads(hosted.export_profile()), value)
                self.assertEqual(hosted.profile.stat().st_mode & 0o777, 0o600)
                changed = dict(value, token='c' * 64)
                with self.assertRaises(SessionError):
                    hosted.restore_profile(json.dumps(changed))
                self.assertEqual(json.loads(hosted.profile.read_text()), value)

    @unittest.skipUnless(backup_available(), 'profile backup module is not installed')
    def test_restore_refuses_orphaned_pending_request(self):
        from world.session import SessionError
        with tempfile.TemporaryDirectory() as tmp:
            session = Mock(root=Path(tmp)); hosted = HostedLauncher(session)
            hosted.pending.write_text('{}'); hosted.pending.chmod(0o600)
            with self.assertRaises(SessionError):
                hosted.restore_profile('{}')
            self.assertFalse(hosted.profile.exists())

    def test_enroll_create_and_issue_private_invitation(self):
        from world.hosting_client import HostingClient
        with tempfile.TemporaryDirectory() as tmp:
            session = Mock(root=Path(tmp))
            session.state = None
            session.status = 'Ready'
            session.connect_remote.return_value = {'profile': Path(tmp) / 'profile'}
            hosted = HostedLauncher(session)
            endpoint = {'host': 'example.org', 'port': 8766}
            access = {'kind': 'host-access', 'version': 1, 'endpoint': endpoint,
                      'pin': 'b' * 64, 'token': 'a' * 64}
            world = {'id': '1234567890abcdef', 'name': 'Our Hoenn', 'trainer': 'May'}
            native = {'version': 1, 'endpoint': {'host': 'example.org', 'port': 9001},
                      'pin': 'c' * 64, 'token': 'd' * 64, 'trainer': 'May'}
            invitation = {'kind': 'world-join', 'version': 1, 'endpoint': endpoint,
                          'pin': 'b' * 64, 'token': 'e' * 64, 'world_id': world['id']}
            def request(credentials, method, path, body=None):
                if path == '/v1/enroll':
                    return {'enrolled': True}
                if path == '/v1/worlds' and method == 'POST':
                    return {'world': world, 'invitation': native}
                if path.endswith('/invites'):
                    return invitation
                raise AssertionError('unexpected request')
            with patch.object(HostingClient, '_request', side_effect=request):
                hosted.enroll(json.dumps(access))
                self.assertTrue(hosted.enrolled())
                paths = hosted.create('Our Hoenn', 'May')
                self.assertEqual(paths, {'profile': Path(tmp) / 'profile'})
                hosted.acknowledge_create()
                self.assertEqual(json.loads(hosted.invite(world['id'])), invitation)
            self.assertNotIn('a' * 64, json.dumps(hosted.state()))
            self.assertNotIn('d' * 64, json.dumps(hosted.state()))
            self.assertEqual(hosted.profile.stat().st_mode & 0o777, 0o600)


if __name__ == '__main__':
    unittest.main()
