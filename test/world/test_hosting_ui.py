"""Launcher-side hosted flows with fake API calls; no server is contacted."""
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from world.hosting_ui import HostedLauncher
from world.session import SessionError


def write_private(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as output:
        json.dump(value, output)


def read_private(path):
    return json.loads(Path(path).read_text())


class HostingUiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.session = Mock(root=Path(self.tmp.name))
        self.hosted = HostedLauncher(self.session)
        self.owner = Mock()
        self.client = Mock()
        self.client.from_file.return_value = self.owner
        client_module = types.ModuleType('world.hosting_client')
        client_module.HostingClient = self.client
        client_module.write_private = write_private
        client_module.read_private = read_private
        session_module = types.ModuleType('world.hosting_session')
        session_module.HostedWorldSession = Mock(return_value=self.owner)
        self.patcher = patch.dict(sys.modules, {'world.hosting_client': client_module, 'world.hosting_session': session_module})
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        available_patch = patch('world.hosting_ui.available', return_value=True)
        ready_patch = patch.object(self.hosted, '_ready')
        available_patch.start(); ready_patch.start()
        self.addCleanup(available_patch.stop); self.addCleanup(ready_patch.stop)

    def test_create_retries_same_request_after_ambiguous_failure(self):
        world = {'id': '1234567890abcdef', 'name': 'Our Hoenn', 'trainer': 'May'}
        self.owner.create.side_effect = [ValueError('connection lost'), {'world': world, 'paths': {'profile': 'local'}}]
        with self.assertRaises(ValueError):
            self.hosted.create('Our Hoenn', 'May')
        pending = json.loads(self.hosted.pending.read_text())
        self.assertEqual(self.hosted.pending.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(SessionError):
            self.hosted.create('Different world', 'May')
        result = self.hosted.create('Our Hoenn', 'May')
        self.assertEqual(result, {'profile': 'local'})
        self.assertFalse(self.hosted.pending.exists())
        self.assertEqual(self.owner.create.call_args_list[0].kwargs['request_id'], pending['request_id'])
        self.assertEqual(self.owner.create.call_args_list[1].kwargs['request_id'], pending['request_id'])

    def test_list_refuses_unexpected_private_fields(self):
        self.owner.list.return_value = [{'id': '1234567890abcdef', 'name': 'World', 'trainer': 'May', 'token': 'secret'}]
        with self.assertRaises(ValueError):
            self.hosted.refresh()
        self.assertEqual(self.hosted.worlds, [])

    def test_join_uses_private_temporary_file_and_returns_only_paths(self):
        seen = {}
        def join(path, trainer):
            seen.update(path=path, text=path.read_text(), mode=path.stat().st_mode & 0o777, trainer=trainer)
            return {'world': {'id': '1234567890abcdef'}, 'paths': {'profile': 'local'}}
        self.owner.join.side_effect = join
        self.assertEqual(self.hosted.join('{"kind":"world-join"}', 'May'), {'profile': 'local'})
        self.assertEqual(seen['mode'], 0o600)
        self.assertFalse(seen['path'].exists())
        self.assertEqual(seen['trainer'], 'May')


if __name__ == '__main__':
    unittest.main()
