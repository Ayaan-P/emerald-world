"""World library tests use only disposable, explicit roots."""
import tempfile
import unittest
from pathlib import Path


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ew-library-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_profile_parents_are_private_even_with_permissive_umask(self):
        import os
        from world.session import DesktopSession
        from world.server import WorldServer
        from world.launcher import prepare_profile
        previous = os.umask(0)
        try:
            session = DesktopSession(self.root)
            for key in ('authority', 'launcher'):
                path = session.create_world(key)
                if key == 'authority':
                    server = WorldServer(path/'transport/world.sock', path)
                    try:
                        server.create_identity('alice')
                    finally:
                        server.close()
                else:
                    prepare_profile(path, 'alice')
                self.assertEqual((path/'trainers').stat().st_mode & 0o077, 0)
                self.assertEqual((path/'trainers/alice').stat().st_mode & 0o077, 0)
            self.assertEqual(len(session.world_library()), 2)
        finally:
            os.umask(previous)

    def test_graphical_library_rename_delete_restore_buttons(self):
        import os
        if not os.environ.get('DISPLAY'):
            self.skipTest('No graphical desktop')
        try:
            import tkinter as tk
        except ImportError:
            self.skipTest('Tk runtime is not configured')
        from unittest.mock import patch
        from world.session import DesktopApp, DesktopSession
        session = DesktopSession(self.root)
        path = session.create_world('stable')
        (path/'owned-marker').write_bytes(b'keep every byte')
        window = tk.Tk()
        app = None
        try:
            app = DesktopApp(window, session, Path('/usr/bin/false'), None)
            window.update()
            buttons = {button.cget('text'): button for button in app.buttons}
            self.assertEqual(app.library_tree.get_children(), ('stable',))
            app.fields['world_label'].set('Weekend adventure')
            app.fields['world_tags'].set('friends, weekend')
            buttons['Rename / save tags'].invoke()
            window.update()
            self.assertEqual(app.library_tree.item('stable', 'text'), 'Weekend adventure (stable)')
            with patch('tkinter.messagebox.askyesno', return_value=False) as dialog:
                buttons['Move to Deleted'].invoke()
                self.assertEqual(dialog.call_count, 1)
            self.assertTrue(path.exists())
            with patch('tkinter.messagebox.askyesno', side_effect=[True, True]) as dialog:
                buttons['Move to Deleted'].invoke()
                self.assertEqual(dialog.call_count, 2)
            window.update()
            self.assertFalse(path.exists())
            self.assertEqual(app.library_tree.get_children(), ())
            tokens = app.deleted_entry.cget('values')
            self.assertEqual(len(tokens), 1)
            app.fields['deleted_world'].set(tokens[0])
            buttons['Restore deleted world'].invoke()
            window.update()
            self.assertEqual(app.library_tree.item('stable', 'text'), 'Weekend adventure (stable)')
            self.assertEqual((path/'owned-marker').read_bytes(), b'keep every byte')
            self.assertEqual(app.deleted_entry.cget('values'), '')
        finally:
            if app is not None:
                app.executor.shutdown(wait=True)
            session.close()
            window.destroy()

    def test_metadata_is_separate_from_identity_and_save_bytes(self):
        from world.session import DesktopSession
        session = DesktopSession(self.root)
        session.create_world('stable')
        profile = self.root/'stable/trainers/alice'
        profile.parent.mkdir(mode=0o700)
        profile.mkdir(mode=0o700)
        save = profile/'game.sav'
        save.write_bytes(b'not a validated save')
        session.rename_world('stable', 'A friendly world', ['weekend', 'friends'])
        card = session.world_library()[0]
        self.assertEqual(card['key'], 'stable')
        self.assertEqual(card['display_name'], 'A friendly world')
        self.assertEqual(card['tags'], ['weekend', 'friends'])
        self.assertIn('unavailable', card['trainers'][0]['party'].lower())
        self.assertEqual(card['trainers'][0]['name'], 'alice')
        self.assertEqual(save.read_bytes(), b'not a validated save')
        self.assertEqual(session.worlds()[0]['name'], 'stable')

    def test_recoverable_move_preserves_entire_world_and_refuses_collision(self):
        from world.session import DesktopSession
        session = DesktopSession(self.root)
        path = session.create_world('stable')
        (path/'private-marker').write_bytes(b'opaque bytes')
        session.rename_world('stable', 'Friendly', ['tag'])
        token = session.delete_world('stable')
        self.assertFalse(path.exists())
        deleted = session.deleted_worlds()
        self.assertEqual(deleted[0]['token'], token)
        self.assertEqual((self.root/'Deleted'/token/'private-marker').read_bytes(), b'opaque bytes')
        path.mkdir(mode=0o700)
        with self.assertRaises(ValueError):
            session.restore_world(token)
        path.rmdir()
        self.assertEqual(session.restore_world(token), path)
        self.assertEqual(session.world_library()[0]['display_name'], 'Friendly')
        self.assertEqual((path/'private-marker').read_bytes(), b'opaque bytes')

    def test_gui_delete_needs_two_separate_yes_answers(self):
        import sys
        from types import SimpleNamespace
        from unittest.mock import Mock, patch
        from world.session import DesktopApp, DesktopSession
        session = DesktopSession(self.root)
        session.create_world('stable')
        app = DesktopApp.__new__(DesktopApp)
        app.session, app.window = session, Mock()
        app.values = lambda: {'world': 'stable'}
        app.refresh = Mock()
        for answers in ([False], [True, False]):
            dialog = Mock(side_effect=answers)
            with patch.dict(sys.modules, {'tkinter': SimpleNamespace(messagebox=SimpleNamespace(askyesno=dialog))}):
                app.delete_selected_world()
            self.assertTrue((self.root/'stable').exists())
            self.assertEqual(dialog.call_count, len(answers))
        dialog = Mock(side_effect=[True, True])
        with patch.dict(sys.modules, {'tkinter': SimpleNamespace(messagebox=SimpleNamespace(askyesno=dialog))}):
            app.delete_selected_world()
        self.assertFalse((self.root/'stable').exists())
        self.assertEqual(dialog.call_count, 2)
        self.assertEqual(len(session.deleted_worlds()), 1)

    def test_capacity_32_and_reserved_deleted_name(self):
        from world.session import DesktopSession
        session = DesktopSession(self.root)
        with self.assertRaises(ValueError):
            session.create_world('Deleted')
        for number in range(32):
            session.create_world('world' + str(number))
        self.assertEqual(len(session.world_library()), 32)
        with self.assertRaises(ValueError):
            session.create_world('overflow')

    def test_launcher_exposes_library_details_delete_and_restore(self):
        import sys
        from types import SimpleNamespace
        from unittest.mock import Mock, MagicMock, patch
        from world.session import DesktopApp, DesktopSession
        class Variable:
            def __init__(self, value=''):
                self.value = value
            def get(self):
                return self.value
            def set(self, value):
                self.value = value
            def trace_add(self, *args):
                return 'mock-trace'
        widgets = []
        def widget(*args, **kwargs):
            result = MagicMock()
            result.options = kwargs
            widgets.append(result)
            return result
        ttk = SimpleNamespace(**{name: widget for name in
            ('Frame', 'Label', 'Notebook', 'Combobox', 'Entry', 'Button', 'Treeview', 'Scrollbar', 'Style', 'Progressbar')})
        fake = SimpleNamespace(StringVar=Variable, Canvas=widget, Text=widget, ttk=ttk,
                               filedialog=Mock(), font=SimpleNamespace(nametofont=Mock()))
        session = DesktopSession(self.root)
        session.create_world('stable')
        with patch.dict(sys.modules, {'tkinter': fake}):
            app = DesktopApp(Mock(), session, Path('/usr/bin/false'), None)
            try:
                labels = {item.options.get('text') for item in widgets}
                self.assertTrue({'Rename / save tags', 'Move to Deleted', 'Restore deleted world'} <= labels)
                self.assertTrue({'1. Choose your world', '2. Host or join', '3. Play as your trainer',
                                 'Import friend invitation', 'Connect remote TLS'} <= labels)
                self.assertEqual(set(app.page_canvases),
                                 {'Play', 'Connect friends', 'Optional GM', 'Settings', 'World library'})
                self.assertEqual(len(app.inputs), len(app.fields))
                self.assertTrue(hasattr(app, 'play_canvas'))
                self.assertIn('world_label', app.fields)
                self.assertIn('world_tags', app.fields)
                self.assertIn('deleted_world', app.fields)
                self.assertIn('stable', app.library_details.get())
                self.assertIn('unavailable', app.library_details.get().lower())
            finally:
                app.executor.shutdown(wait=True)

    def test_delete_refuses_real_cross_process_authority_game_and_gm_locks(self):
        import subprocess
        import sys
        from world.session import DesktopSession
        session = DesktopSession(self.root)
        path = session.create_world('stable')
        for relative in ('world.lock', '.profile-locks/alice.lock', 'gm/.runtime.lock', 'gm/.lock'):
            lock = path/relative
            lock.parent.mkdir(mode=0o700, exist_ok=True)
            child = subprocess.Popen([sys.executable, '-c',
                'import fcntl,sys; f=open(sys.argv[1],"a"); fcntl.flock(f,fcntl.LOCK_EX); print("ready",flush=True); sys.stdin.read()', str(lock)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
            try:
                self.assertEqual(child.stdout.readline().strip(), 'ready')
                with self.assertRaises(ValueError):
                    session.delete_world('stable')
                self.assertTrue(path.exists())
            finally:
                child.communicate(timeout=5)
        session.host('stable')
        try:
            with self.assertRaises(ValueError):
                session.delete_world('stable')
        finally:
            session.close()

    def test_symlink_and_hardlinked_metadata_fail_closed(self):
        import os
        from world.session import DesktopSession
        session = DesktopSession(self.root)
        path = session.create_world('stable')
        outside = self.root/'outside'
        outside.write_bytes(b'untouched')
        marker = path/'.library.json'
        marker.symlink_to(outside)
        with self.assertRaises((ValueError, OSError)):
            session.rename_world('stable', 'New', [])
        with self.assertRaises((ValueError, OSError)):
            session.delete_world('stable')
        self.assertEqual(outside.read_bytes(), b'untouched')
        marker.unlink()
        os.link(outside, marker)
        with self.assertRaises((ValueError, OSError)):
            session.rename_world('stable', 'New', [])
        marker.unlink()
        (self.root/'Deleted').rmdir()
        (self.root/'Deleted').symlink_to(self.root)
        with self.assertRaises((ValueError, OSError)):
            session.delete_world('stable')
        self.assertTrue(path.exists())

    def test_rename_failure_keeps_original_metadata_and_private_mode(self):
        from unittest.mock import patch
        from world.session import DesktopSession
        session = DesktopSession(self.root)
        session.create_world('stable')
        session.rename_world('stable', 'Before', ['original'])
        metadata = self.root/'stable/.library.json'
        original = metadata.read_bytes()
        with patch('world.world_library.os.replace', side_effect=OSError('failed')):
            with self.assertRaises(OSError):
                session.rename_world('stable', 'After', [])
        self.assertEqual(metadata.read_bytes(), original)
        self.assertEqual(metadata.stat().st_mode & 0o777, 0o600)
        self.assertEqual(list(metadata.parent.glob('.library-*')), [])

    def test_switching_keeps_each_existing_profile_and_requires_disconnect(self):
        from world.session import DesktopSession
        session = DesktopSession(self.root)
        for key in ('one', 'two'):
            session.create_world(key)
            session.host(key)
            paths = session.local_profile('alice')
            paths['save'].write_bytes(key.encode())
            session.close()
        session.host('one')
        try:
            with self.assertRaises(ValueError):
                session.host('two')
            self.assertEqual(session.local_profile('alice')['save'].read_bytes(), b'one')
        finally:
            session.close()
        session.host('two')
        try:
            self.assertEqual(session.local_profile('alice')['save'].read_bytes(), b'two')
        finally:
            session.close()

    def test_gui_launch_refuses_selected_world_different_from_connected_world(self):
        from unittest.mock import Mock
        from world.session import DesktopApp, DesktopSession
        session = DesktopSession(self.root)
        session.create_world('one')
        session.create_world('two')
        session.host('one')
        app = DesktopApp.__new__(DesktopApp)
        app.session = session
        try:
            value = {'world': 'two', 'trainer': 'alice', 'ai_trainer': 'hermes', 'seed': ''}
            with self.assertRaisesRegex(ValueError, 'selected|Disconnect'):
                app._launch(value, None)
            with self.assertRaisesRegex(ValueError, 'selected|Disconnect'):
                app._launch_ai(value, None)
            self.assertFalse((self.root/'one/trainers/alice').exists())
        finally:
            session.close()

    def test_metadata_rejects_unsafe_root_ownership_and_permissions(self):
        import os
        from unittest.mock import patch
        from world.session import DesktopSession
        session = DesktopSession(self.root)
        session.create_world('stable')
        self.root.chmod(0o777)
        with self.assertRaises(ValueError):
            session.rename_world('stable', 'Unsafe', [])
        self.root.chmod(0o700)
        with patch('world.world_library.os.geteuid', return_value=os.geteuid() + 1):
            with self.assertRaises(ValueError):
                session.rename_world('stable', 'Wrong owner', [])
        self.assertFalse((self.root/'stable/.library.json').exists())
        session.rename_world('stable', 'Safe', [])
        self.assertEqual(session.world_library()[0]['display_name'], 'Safe')

    def test_delete_fails_closed_when_tree_cannot_be_scanned(self):
        from unittest.mock import patch
        from world.session import DesktopSession
        session = DesktopSession(self.root)
        path = session.create_world('stable')
        with patch('world.world_library.os.scandir', side_effect=PermissionError('denied')):
            with self.assertRaises((ValueError, OSError)):
                session.delete_world('stable')
        self.assertTrue(path.exists())


if __name__ == '__main__':
    unittest.main()
