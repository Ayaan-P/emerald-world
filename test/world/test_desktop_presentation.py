"""Presentation-only checks. Never create a session or execute a native game."""
from concurrent.futures import Future
import unittest
from unittest.mock import Mock

from world.session import DesktopApp


class Value:
    def __init__(self, value=''):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class PresentationTests(unittest.TestCase):
    def test_empty_library_explains_how_to_start(self):
        app = DesktopApp.__new__(DesktopApp)
        app.library_details = Value()
        app.fields = {'world': Value()}
        app.library_cards = []
        app.show_world_details()
        self.assertIn('No saved worlds yet', app.library_details.get())
        self.assertIn('Create world', app.library_details.get())
        self.assertIn('Play', app.library_details.get())

    def test_busy_state_disables_inputs_and_restores_readonly_selectors(self):
        app = DesktopApp.__new__(DesktopApp)
        app.buttons = [Mock(), Mock()]
        editable, selector = Mock(), Mock()
        app.inputs = [(editable, 'normal'), (selector, 'readonly')]
        app.activity = Value()
        app.progress = Mock()
        self.assertTrue(hasattr(app, '_set_busy'), 'busy presentation helper is missing')
        app._set_busy(True)
        for control in app.buttons:
            control.state.assert_called_with(['disabled'])
        editable.configure.assert_called_with(state='disabled')
        selector.configure.assert_called_with(state='disabled')
        self.assertIn('Working', app.activity.get())
        app.progress.start.assert_called_once()
        app._set_busy(False)
        editable.configure.assert_called_with(state='normal')
        selector.configure.assert_called_with(state='readonly')
        app.progress.stop.assert_called_once()
        self.assertEqual(app.activity.get(), 'Connection and activity')

    def test_empty_friend_list_has_import_guidance(self):
        app = DesktopApp.__new__(DesktopApp)
        app.session = Mock()
        app.session.friend_worlds.return_value = []
        app.session.worlds.return_value = []
        app.friend_entry = {}
        app.world_entry = {}
        app.fields = {'friend_world': Value(), 'world': Value()}
        app.friend_hint = Value()
        app.refresh()
        self.assertIn('No saved friend connections', app.friend_hint.get())
        self.assertIn('Import', app.friend_hint.get())
        app.session.friend_worlds.return_value = [{'name': 'visit'}]
        app.refresh()
        self.assertEqual(app.fields['friend_world'].get(), 'visit')
        self.assertEqual(app.friend_hint.get(), '')

    def test_library_selection_cannot_change_world_while_busy(self):
        app = DesktopApp.__new__(DesktopApp)
        app.pending = Future()
        app.closing = False
        app.library_tree = Mock()
        app.library_tree.selection.return_value = ['another-world']
        app.fields = {'world': Value('current-world')}
        app.show_world_details = Mock()
        app.select_library_world()
        self.assertEqual(app.fields['world'].get(), 'current-world')
        app.pending = None
        app.select_library_world()
        self.assertEqual(app.fields['world'].get(), 'another-world')

    def test_close_immediately_locks_controls(self):
        app = DesktopApp.__new__(DesktopApp)
        app.message = Value()
        app._set_busy = Mock()
        app.close()
        app._set_busy.assert_called_once_with(True)
        self.assertTrue(app.closing)
        self.assertIn('Saves are kept', app.message.get())

    def test_invalid_remote_address_never_queues_connection(self):
        app = DesktopApp.__new__(DesktopApp)
        app.pending = None
        app.closing = False
        app.fields = {'remote': Value('missing-port')}
        app.message = Value()
        app.executor = Mock()
        app.submit(app.connect)
        app.executor.submit.assert_not_called()
        self.assertIn('HOST:PORT', app.message.get())

    def test_keyboard_focus_reveals_control_below_page_viewport(self):
        app = DesktopApp.__new__(DesktopApp)
        canvas, control = Mock(), Mock()
        canvas.winfo_rooty.return_value = 100
        canvas.winfo_height.return_value = 200
        canvas.canvasy.return_value = 0
        canvas.bbox.return_value = (0, 0, 600, 600)
        control.winfo_rooty.return_value = 380
        control.winfo_height.return_value = 20
        self.assertTrue(hasattr(app, '_reveal_control'), 'keyboard scrolling is missing')
        app._reveal_control(Mock(widget=control), canvas)
        canvas.yview_moveto.assert_called_once_with(100 / 600)
        canvas.reset_mock()
        control.winfo_rooty.return_value = 120
        app._reveal_control(Mock(widget=control), canvas)
        canvas.yview_moveto.assert_not_called()

    def test_mouse_wheel_is_scoped_to_page_and_leaves_selectors_alone(self):
        from types import SimpleNamespace
        app = DesktopApp.__new__(DesktopApp)
        canvas = Mock()
        app.page_canvases = {'Play': canvas}
        control = SimpleNamespace(master=canvas, winfo_class=lambda: 'TLabel')
        self.assertTrue(hasattr(app, '_scroll_page'), 'page wheel scrolling is missing')
        self.assertEqual(app._scroll_page(SimpleNamespace(widget=control, num=5, delta=0)), 'break')
        canvas.yview_scroll.assert_called_once_with(3, 'units')
        canvas.reset_mock()
        control.winfo_class = lambda: 'TCombobox'
        app._scroll_page(SimpleNamespace(widget=control, num=5, delta=0))
        canvas.yview_scroll.assert_not_called()

    def test_resize_wraps_all_help_to_available_width(self):
        app = DesktopApp.__new__(DesktopApp)
        page, canvas, label = Mock(), Mock(), Mock()
        app.page_notes = {page: [label]}
        self.assertTrue(hasattr(app, '_resize_page'), 'responsive help sizing is missing')
        app._resize_page(Mock(width=600), canvas, 7, page)
        canvas.itemconfigure.assert_called_once_with(7, width=600)
        label.configure.assert_called_once_with(wraplength=580)

    def test_status_keeps_full_text_and_does_not_reset_identical_updates(self):
        app = DesktopApp.__new__(DesktopApp)
        app.message = Value('Connection failed.\nCheck the trusted certificate pin.')
        app.status_text = Mock()
        app.last_status = None
        self.assertTrue(hasattr(app, '_render_status'), 'scrollable status renderer is missing')
        app._render_status()
        app.status_text.insert.assert_called_once_with('1.0', app.message.get())
        app.status_text.configure.assert_called_with(state='disabled')
        app.status_text.reset_mock()
        app._render_status()
        app.status_text.delete.assert_not_called()
        app.status_text.insert.assert_not_called()

    def test_closing_blocks_new_button_actions(self):
        app = DesktopApp.__new__(DesktopApp)
        app.pending = None
        app.closing = True
        app.session = Mock(status='Disconnected.')
        app.message = Value()
        operation = Mock()
        app.submit(operation)
        operation.assert_not_called()


class IsolatedTkTests(unittest.TestCase):
    """Opt in only on a disposable display owned by the test runner.

    EW_UI_TEST_DISPLAY=:N python3 -m unittest test.world.test_desktop_presentation
    The session is a strict mock. No native process or real invitation is used.
    """
    def setUp(self):
        import os
        import tempfile
        from pathlib import Path
        from world.session import DesktopSession
        display = os.environ.get('EW_UI_TEST_DISPLAY')
        if not display:
            self.skipTest('Set EW_UI_TEST_DISPLAY to an isolated Xvfb/Xephyr display you own')
        import tkinter as tk
        self.temp = tempfile.TemporaryDirectory(prefix='emerald-ui-')
        self.addCleanup(self.temp.cleanup)
        session = Mock(spec=DesktopSession)
        session.root = Path(self.temp.name)
        session.status = 'Disconnected. No world selected.'
        for method in ('worlds', 'world_library', 'friend_worlds', 'deleted_worlds', 'trainers'):
            getattr(session, method).return_value = []
        self.window = tk.Tk(screenName=display)
        self.addCleanup(self.window.destroy)
        self.app = DesktopApp(self.window, session, Path('/nonexistent/ui-test-game'), None)
        self.addCleanup(self.app.executor.shutdown, wait=True)
        self.window.after_cancel(self.app.after_id)
        self.app.after_id = None
        self.window.update()

    def test_controls_remain_reachable_and_busy_buttons_cannot_dispatch(self):
        from unittest.mock import patch
        app = self.app
        self.assertEqual([app.notebook.tab(tab, 'text') for tab in app.notebook.tabs()],
                         ['Play', 'Connect friends', 'Optional GM', 'Settings', 'World library', 'Host controls'])
        buttons = {button.cget('text'): button for button in app.buttons}
        routes = {'Create world': app.create, 'Host selected': app.host,
                  'Join local': app.join_local, 'Launch / resume trainer': app.launch,
                  'Import friend invitation': app.import_friend_invitation,
                  'Connect remote TLS': app.connect, 'Save trainer invitation': app.invite,
                  'Move to Deleted': app.delete_selected_world,
                  'Restore deleted world': app.restore_selected_world}
        with patch.object(app, 'submit') as submit:
            for label, operation in routes.items():
                buttons[label].invoke()
                submit.assert_called_with(operation)
            submit.reset_mock()
            app._set_busy(True)
            for button in app.buttons:
                self.assertTrue(button.instate(['disabled']))
                button.invoke()
            submit.assert_not_called()
            for entry, _ in app.inputs:
                self.assertTrue(entry.instate(['disabled']))
            app._set_busy(False)
            self.assertTrue(app.friend_entry.instate(['readonly']))
            self.assertTrue(app.deleted_entry.instate(['readonly']))
        app.session.launch.assert_not_called()
        app.session.connect_remote.assert_not_called()

    def test_pages_resize_and_status_preserves_long_error(self):
        app = self.app
        self.window.geometry('740x560')
        for index, canvas in enumerate(app.page_canvases.values()):
            app.notebook.select(index)
            self.window.update()
            self.assertGreater(canvas.winfo_width(), 500)
            self.assertGreater(canvas.winfo_height(), 100)
            canvas.yview_moveto(1.0)
            self.window.update()
            self.assertAlmostEqual(canvas.yview()[1], 1.0)
        text = 'Connection failed. Check the host and trusted pin.\n' * 30
        app.message.set(text)
        self.window.update()
        self.assertEqual(app.status_text.get('1.0', 'end-1c'), text)
        self.assertEqual(str(app.status_text.cget('state')), 'disabled')
        self.assertGreater(app.status_text.winfo_height(), 50)
        self.assertLess(app.status_text.winfo_y(), self.window.winfo_height())


if __name__ == '__main__':
    unittest.main()
