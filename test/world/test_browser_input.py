"""Browser input relay safety using fake processes and no X server."""
import subprocess
import time
import unittest
from unittest.mock import Mock

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


if __name__ == '__main__':
    unittest.main()
