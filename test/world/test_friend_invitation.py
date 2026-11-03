"""Disposable friend invitations. No external network or real credentials."""
import json
from pathlib import Path
import tempfile
import unittest

from world.windows_client import _invitation


class InvitationTests(unittest.TestCase):
    def setUp(self):
        # Dialog interaction is mocked, not a graphical-runtime acceptance test.
        try:
            import tkinter.filedialog
        except ImportError:
            import sys
            import types
            from unittest.mock import Mock, patch
            tk = types.ModuleType('tkinter')
            dialogs = types.ModuleType('tkinter.filedialog')
            setattr(dialogs, 'askopenfilename', Mock())
            setattr(dialogs, 'asksaveasfilename', Mock())
            setattr(tk, 'filedialog', dialogs)
            modules = patch.dict(sys.modules, {'tkinter': tk, 'tkinter.filedialog': dialogs})
            modules.start()
            self.addCleanup(modules.stop)

    def test_linux_graphical_import_populates_join_form_without_connecting(self):
        import os
        if not os.environ.get('DISPLAY'):
            self.skipTest('graphical task display required')
        import tkinter as tk
        from world.session import DesktopApp, DesktopSession
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root/'invite.json'
            path.write_text(json.dumps({'version': 1, 'endpoint': {'host': 'host.example', 'port': 8765},
                                        'pin': 'b'*64, 'trainer': 'friend', 'token': 'a'*64}))
            session = DesktopSession(DesktopSession.create_root(root/'worlds'))
            window = tk.Tk()
            app = None
            try:
                app = DesktopApp(window, session, Path('/usr/bin/false'), None)
                app.import_friend_invitation(path)
                window.update()
                self.assertEqual(app.fields['remote'].get(), 'host.example:8765')
                self.assertEqual(app.fields['trainer'].get(), 'friend')
                self.assertEqual(app.fields['invitation'].get(), str(path))
                self.assertEqual(app.notebook.index(app.notebook.select()), 1)
                self.assertIsNone(session.state)
            finally:
                if app is not None:
                    app.executor.shutdown(wait=True)
                session.close()
                window.destroy()

    def test_linux_import_preserves_settings_on_invalid_or_connected(self):
        from unittest.mock import Mock
        from world.session import DesktopApp, SessionError
        app = DesktopApp.__new__(DesktopApp)
        app.session = Mock(state=None)
        app.notebook = Mock()
        app.message = Mock()
        app.fields = {key: Mock() for key in ('world', 'remote', 'pin', 'trainer', 'invitation')}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'invite.json'
            path.write_text(json.dumps({'version': 1, 'endpoint': {'host': 'host.example', 'port': 8765},
                                        'pin': 'b'*64, 'trainer': 'friend', 'token': 'a'*64}))
            app.import_friend_invitation(path)
            app.fields['remote'].set.assert_called_once_with('host.example:8765')
            app.fields['trainer'].set.assert_called_once_with('friend')
            self.assertTrue(app.fields['world'].set.call_args[0][0].startswith('remote-'))
            app.notebook.select.assert_called_once_with(1)
            for variable in app.fields.values():
                variable.reset_mock()
            path.write_text('invalid')
            with self.assertRaises(SessionError):
                app.import_friend_invitation(path)
            for variable in app.fields.values():
                variable.set.assert_not_called()
            app.session.state = Path(tmp)
            with self.assertRaises(SessionError):
                app.import_friend_invitation(path)

    def test_versioned_bundle_and_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'invite.json'
            legacy = {'trainer': 'friend', 'token': 'a'*64}
            bundle = dict(legacy, version=1, endpoint={'host': 'host.example', 'port': 8765}, pin='b'*64)
            for value in (legacy, bundle):
                path.write_text(json.dumps(value))
                self.assertEqual(_invitation(path), value)

    def test_malformed_and_bounded(self):
        from copy import deepcopy
        valid = {'version': 1, 'endpoint': {'host': 'host.example', 'port': 8765},
                 'pin': 'b'*64, 'trainer': 'friend', 'token': 'a'*64}
        bad = []
        for field, values in {'version': [True, 2, '1', None], 'pin': ['', 'b'*65, 1],
                              'trainer': ['', '../friend', 'a'*25, 1], 'token': ['', 'x'*64, None],
                              'endpoint': [None, [], {'host': 'host.example', 'port': 1, 'extra': 1}]}.items():
            for value in values:
                candidate = deepcopy(valid)
                candidate[field] = value
                bad.append(candidate)
        for field, values in {'host': ['', '0.0.0.0', '::', '::ffff:0.0.0.0', 'https://host', 'host:8765', 'a b',
                                        'a'*254, 'a'*64+'.example', 'host\n', '[::1]', '%bad', 1],
                              'port': [True, 0, -1, 65536, '8765', 1.5]}.items():
            for value in values:
                candidate = deepcopy(valid)
                candidate['endpoint'][field] = value
                bad.append(candidate)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'invite.json'
            for value in bad:
                path.write_text(json.dumps(value))
                with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'invalid invitation'):
                    _invitation(path)
            for raw in (' '*4097, '{"trainer":"friend","trainer":"other","token":"'+'a'*64+'"}',
                        '['*1500, '{"version":NaN}'):
                path.write_text(raw)
                with self.assertRaises(ValueError):
                    _invitation(path)

    def test_import_updates_endpoint_and_selects_file_without_joining(self):
        from unittest.mock import Mock, patch
        from world.windows_client import GuestWindow
        window = GuestWindow.__new__(GuestWindow)
        window.root = Mock()
        window.controller = Mock()
        window.status_text = Mock()
        window.values = {name: Mock() for name in ('Host', 'Port', 'Pin', 'Invitation')}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'invite.json'
            path.write_text(json.dumps({'version': 1, 'endpoint': {'host': 'host.example', 'port': 1234},
                                        'pin': 'b'*64, 'trainer': 'friend', 'token': 'a'*64}))
            with patch('tkinter.filedialog.askopenfilename', return_value=str(path)):
                window.import_invitation()
            for name, value in [('Host', 'host.example'), ('Port', '1234'), ('Pin', 'b'*64), ('Invitation', str(path))]:
                window.values[name].set.assert_called_once_with(value)
            window.controller.submit.assert_not_called()
            for variable in window.values.values():
                variable.reset_mock()
            path.write_text('invalid')
            with patch('tkinter.filedialog.askopenfilename', return_value=str(path)):
                window.import_invitation()
            for variable in window.values.values():
                variable.set.assert_not_called()

    def test_legacy_import_preserves_manual_connection_and_cancel_is_noop(self):
        from unittest.mock import Mock, patch
        from world.windows_client import GuestWindow
        window = GuestWindow.__new__(GuestWindow)
        window.root = Mock()
        window.status_text = Mock()
        window.values = {name: Mock() for name in ('Host', 'Port', 'Pin', 'Invitation')}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'legacy.json'
            path.write_text(json.dumps({'trainer': 'friend', 'token': 'a'*64}))
            with patch('tkinter.filedialog.askopenfilename', return_value=str(path)):
                window.import_invitation()
            window.values['Invitation'].set.assert_called_once_with(str(path))
            for name in ('Host', 'Port', 'Pin'):
                window.values[name].set.assert_not_called()
            for variable in window.values.values():
                variable.reset_mock()
            with patch('tkinter.filedialog.askopenfilename', return_value=''):
                window.import_invitation()
            for variable in window.values.values():
                variable.set.assert_not_called()

    def test_real_linux_export_connects_both_guests_over_local_tls(self):
        import hashlib
        import shutil
        import socket
        import ssl
        from world.session import DesktopSession
        from world.windows_client import WindowsGuestSession
        if not shutil.which('openssl'):
            self.skipTest('local TLS fixture requires openssl')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with DesktopSession(root) as host, DesktopSession(root) as linux_guest:
                host.create_world('host')
                host.host('host')
                cert, key = host.tls_material()
                address = host.share(cert, key, ('127.0.0.1', 0))
                path = root/'friend.json'
                # Loopback is deliberate and explicit in this isolated fixture.
                host.export_invitation('friend', path, address)
                bundle = _invitation(path)
                self.assertEqual(bundle['pin'], hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert.read_text())).hexdigest())
                self.assertNotIn(str(key), path.read_text())
                paths = linux_guest.connect_remote('guest', path, address, bundle['pin'])
                self.assertEqual(paths['profile'].name, 'friend')
                windows = WindowsGuestSession(bundle['endpoint']['host'], bundle['endpoint']['port'],
                                              bundle['pin'], path, data_root=root/'windows')
                try:
                    windows.prepare()
                    with socket.create_connection(windows.gateway.address, timeout=3) as native:
                        native.sendall(('EWLOCAL1 ' + windows.gateway.local_token + '\nHELLO 1 friend '
                                        + bundle['token'] + ' SOCIAL\n').encode('ascii'))
                        self.assertTrue(native.recv(4096).startswith(b'WELCOME '))
                finally:
                    windows.close()

    def test_host_gui_exports_the_explicit_advertised_address(self):
        from unittest.mock import Mock, patch
        from world.session import DesktopApp
        app = DesktopApp.__new__(DesktopApp)
        app.window = Mock()
        app.session = Mock(root=Path('/explicit/worlds'))
        app.values = Mock(return_value={'advertised': 'host.example:4321', 'invite_trainer': 'friend'})
        with patch('tkinter.filedialog.asksaveasfilename', return_value='/explicit/friend.json'):
            app.invite()
        app.session.export_invitation.assert_called_once_with('friend', '/explicit/friend.json', ('host.example', 4321))

    def test_import_button_and_permanent_trust_disclosure(self):
        import types
        from unittest.mock import Mock, patch
        from world.windows_client import GuestWindow
        class Variable:
            def __init__(self, **kwargs):
                self.value = kwargs.get('value', '')
            def get(self):
                return self.value
            def set(self, value):
                self.value = value
        ttk = Mock()
        controller = Mock()
        controller.snapshot.return_value = {'state': 'stopped', 'busy': False}
        with patch.dict('sys.modules', {'tkinter': types.SimpleNamespace(StringVar=Variable, ttk=ttk)}):
            window = GuestWindow(Mock(), controller)
        self.assertTrue(any(call.kwargs.get('text') == 'Import invitation'
                            and call.kwargs.get('command') == window.import_invitation
                            for call in ttk.Button.call_args_list))
        labels = ' '.join(call.kwargs.get('text', '') for call in ttk.Label.call_args_list)
        self.assertIn('TLS pin', labels)
        self.assertIn('trusted channel', labels)

    def test_export_requires_advertised_address_and_roundtrips(self):
        from unittest.mock import Mock
        from world.session import DesktopSession
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session = DesktopSession(root)
            session.state = root/'world'
            session.server = Mock()
            session.server.create_identity.return_value = {'token': 'a'*64}
            session.broker = Mock(address=('0.0.0.0', 8765))
            session.sharing_pin = 'b'*64
            path = root/'invite.json'
            with self.assertRaisesRegex(ValueError, 'advertis'):
                session.export_invitation('friend', path)
            session.server.create_identity.assert_not_called()
            self.assertFalse(path.exists())
            session.export_invitation('friend', path, ('host.example', 1234))
            value = _invitation(path)
            self.assertEqual(value, {'version': 1, 'endpoint': {'host': 'host.example', 'port': 1234},
                                     'pin': 'b'*64, 'trainer': 'friend', 'token': 'a'*64})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(ValueError):
                session.export_invitation('friend', path, ('host.example', 1234))
            for host in ('0.0.0.0', '::'):
                with self.assertRaises(ValueError):
                    session.export_invitation('other', root/'bad.json', (host, 8765))
            for host in ('127.0.0.1', '::1', 'localhost'):
                session.broker.address = (host, 8765)
                with self.assertRaisesRegex(ValueError, 'advertis'):
                    session.export_invitation('other', root/'bad.json')
            session.broker.address = ('192.0.2.1', 8765)
            session.export_invitation('other', root/'auto.json')
            self.assertEqual(_invitation(root/'auto.json')['endpoint']['host'], '192.0.2.1')


if __name__ == '__main__':
    unittest.main()
