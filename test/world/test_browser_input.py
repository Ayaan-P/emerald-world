"""Browser input relay safety using fake processes and no X server."""
import subprocess
import time
import unittest
from unittest.mock import Mock, patch
import threading

from world.web_launcher import LauncherBridge

from world.browser_input import BrowserInput
from world.session import SessionError


class FakeRunner:
    def __init__(self):
        self.calls = []
        self.title = 'Emerald World | May | Human'
        self.tree = f'  0x1234 "{self.title}": ("game" "game") 480x320+0+0'
    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        if command[0].endswith('xwininfo'):
            output = self.tree
        elif command[1] == 'getwindowname':
            output = self.title
        else:
            output = ''
        return subprocess.CompletedProcess(command, 0, output, '')


class BrowserInputTests(unittest.TestCase):
    def setUp(self):
        self.process = Mock(); self.process.poll.return_value = None
        self.session = Mock()
        self.session.managed_display = Mock(display=':95')
        self.session.games = {'May': (self.process, {})}
        self.session.agent_games = set()
        self.runner = FakeRunner()
        self.control = BrowserInput(self.session, runner=self.runner, which=lambda name: '/usr/bin/' + name)
        self.addCleanup(self.control.close)

    def test_only_the_dedicated_matching_human_window_is_targeted(self):
        self.control.start()
        self.control.apply(['ArrowUp', 'KeyZ'])
        commands = [entry[0][1:] for entry in self.runner.calls]
        self.assertIn(['windowfocus', '--sync', '0x1234'], commands)
        self.assertIn(['keydown', 'Up'], commands)
        self.assertIn(['keydown', 'z'], commands)
        self.assertTrue(all(entry[1]['env']['DISPLAY'] == ':95' for entry in self.runner.calls))
        self.control.close()
        commands = [entry[0][1:] for entry in self.runner.calls]
        self.assertIn(['keyup', 'Up'], commands)
        self.assertIn(['keyup', 'z'], commands)

    def test_invalid_keys_and_reset_chords_are_rejected(self):
        self.control.start()
        for keys in (['NotAKey'], ['KeyA', 'KeyA'], ['ControlLeft', 'KeyR'], ['ControlRight', 'KeyP']):
            with self.assertRaises(SessionError):
                self.control.apply(keys)
        self.assertFalse(self.control.held)

    def test_lease_expires_and_releases_held_keys(self):
        self.control.start(); self.control.apply(['KeyZ'])
        self.control.expires = self.control.clock() - 1
        deadline = time.monotonic() + 2
        while self.control.held and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertFalse(self.control.held)
        self.assertIn(['keyup', 'z'], [entry[0][1:] for entry in self.runner.calls])

    def test_rejects_host_display_multiple_games_and_agent_control(self):
        self.session.managed_display.display = ':0'
        self.assertFalse(self.control.info()['available'])
        self.session.managed_display.display = ':95'
        other = Mock(); other.poll.return_value = None
        self.session.games['other'] = (other, {})
        self.assertFalse(self.control.info()['available'])
        self.session.games.pop('other'); self.session.agent_games.add('May')
        self.assertFalse(self.control.info()['available'])

    def test_rejects_ambiguous_or_changed_window(self):
        self.runner.tree += '\n  0x5678 "Emerald World | May | Human": 480x320+0+0'
        with self.assertRaises(SessionError):
            self.control.start()
        self.runner.tree = '  0x1234 "Emerald World | May | Human": 480x320+0+0'
        self.control.start(); self.runner.title = 'Unexpected window'
        with self.assertRaises(SessionError):
            self.control.apply(['KeyZ'])
        self.assertFalse(self.control.held)


class BrowserInputOwnershipTests(unittest.TestCase):
    def setUp(self):
        # No processes or display are opened by these lifecycle regressions.
        self.bridge = LauncherBridge.__new__(LauncherBridge)
        self.bridge.lock = threading.RLock()
        self.bridge.session = Mock()
        self.bridge.browser_input = None
        self.bridge.browser_input_session = None
        factory = patch('world.browser_input.BrowserInput')
        self.factory = factory.start()
        self.addCleanup(factory.stop)
        self.old, self.new = Mock(), Mock()
        self.factory.side_effect = [self.old, self.new]

    def test_late_old_stop_and_keys_cannot_affect_replacement_relay(self):
        first = self.bridge.action('screen_start', {})
        second = self.bridge.action('screen_start', {})
        self.assertNotEqual(first['session'], second['session'])
        self.old.close.assert_called_once()
        self.bridge.action('screen_stop', {'session': first['session']})
        self.new.close.assert_not_called()
        with self.assertRaises(SessionError):
            self.bridge.action('screen_keys', {'session': first['session'], 'keys': ['KeyZ']})
        self.new.apply.assert_not_called()
        self.bridge.action('screen_keys', {'session': second['session'], 'keys': ['KeyZ']})
        self.new.apply.assert_called_once_with(['KeyZ'])
        self.bridge.action('screen_stop', {'session': second['session']})
        self.new.close.assert_called_once()
        self.assertIsNone(self.bridge.browser_input_session)

    def test_unscoped_stop_and_keys_never_control_current_relay(self):
        current = self.bridge.action('screen_start', {})
        self.bridge.action('screen_stop', {})
        self.old.close.assert_not_called()
        with self.assertRaises(SessionError):
            self.bridge.action('screen_keys', {'keys': ['KeyZ']})
        self.old.apply.assert_not_called()
        self.bridge.action('screen_stop', {'session': current['session']})
        self.old.close.assert_called_once()

    def test_failed_replacement_clears_previous_owner_and_closes_partial_relay(self):
        current = self.bridge.action('screen_start', {})
        self.new.start.side_effect = SessionError('Window closed')
        with self.assertRaises(SessionError):
            self.bridge.action('screen_start', {})
        self.old.close.assert_called_once()
        self.new.close.assert_called_once()
        self.assertIsNone(self.bridge.browser_input)
        self.assertIsNone(self.bridge.browser_input_session)
        self.bridge.action('screen_stop', {'session': current['session']})


if __name__ == '__main__':
    unittest.main()
