"""Opt-in browser-key relay to one owned game's dedicated X11 display.

Pixels remain in the browser's user-approved screen capture. This helper never
accesses the host desktop display, accepts no commands or paths from the browser,
and releases injected keys after a short lease or on shutdown.
"""
import os
import re
import shutil
import subprocess
import threading
import time

from .session import SessionError

KEYS = {**{f'Key{chr(code)}': chr(code).lower() for code in range(ord('A'), ord('Z') + 1)},
        **{f'Digit{digit}': str(digit) for digit in range(10)},
        'ArrowUp': 'Up', 'ArrowDown': 'Down', 'ArrowLeft': 'Left', 'ArrowRight': 'Right',
        'Enter': 'Return', 'Space': 'space', 'Backspace': 'BackSpace', 'Tab': 'Tab', 'Escape': 'Escape',
        'ShiftLeft': 'Shift_L', 'ShiftRight': 'Shift_R',
        'ControlLeft': 'Control_L', 'ControlRight': 'Control_R',
        'Comma': 'comma', 'Period': 'period', 'Slash': 'slash', 'Backslash': 'backslash',
        'Minus': 'minus', 'Equal': 'equal', 'BracketLeft': 'bracketleft', 'BracketRight': 'bracketright'}
MAX_HELD = 12
LEASE_SECONDS = 0.6


class BrowserInput:
    def __init__(self, session, *, runner=subprocess.run, which=shutil.which, clock=time.monotonic):
        self.session, self.runner, self.which, self.clock = session, runner, which, clock
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.thread = None
        self.game = self.process = self.display = self.window = self.title = None
        self.held = set()
        self.expires = 0.0

    def info(self):
        if not self.which('xdotool') or not self.which('xwininfo'):
            return {'available': False, 'reason': 'Install xdotool and xwininfo to use the in-page controls.'}
        display = getattr(self.session.managed_display, 'display', None)
        if not isinstance(display, str) or not re.fullmatch(r':(?:9[0-9]|1[0-9]{2})', display):
            return {'available': False, 'reason': 'Launch a game in its dedicated window first.'}
        live = [(name, process) for name, (process, _) in self.session.games.items() if process.poll() is None]
        if len(live) != 1 or live[0][0] in self.session.agent_games:
            return {'available': False, 'reason': 'Open one human-controlled game before using the in-page view.'}
        return {'available': True, 'reason': ''}

    def _run(self, command):
        env = {'DISPLAY': self.display, 'PATH': '/usr/bin:/bin', 'LANG': 'C'}
        try:
            result = self.runner(command, env=env, check=True, capture_output=True, text=True, timeout=2)
            if len(result.stdout) > 131072:
                raise ValueError('display response too large')
            return result.stdout.strip()
        except (OSError, TypeError, ValueError, subprocess.SubprocessError):
            raise SessionError('The game window could not accept browser controls.') from None

    def _valid_window(self):
        if self.process is None or self.process.poll() is not None:
            raise SessionError('The game is no longer running.')
        name = self._run([self.which('xdotool'), 'getwindowname', self.window])
        if name != self.title:
            raise SessionError('The game window changed. Reconnect the in-page view.')

    def start(self):
        with self.lock:
            if self.thread is not None and self.thread.is_alive():
                raise SessionError('The in-page controls are already active.')
            status = self.info()
            if not status['available']:
                raise SessionError(status['reason'])
            live = [(name, process) for name, (process, _) in self.session.games.items() if process.poll() is None]
            if len(live) != 1:
                raise SessionError('The game stopped before the in-page view started.')
            self.game, self.process = live[0]
            self.display = self.session.managed_display.display
            trainer = 'Local trainer' if self.game.startswith('offline/') else self.game
            self.title = f'Emerald World | {trainer} | Human'
            output = self._run([self.which('xwininfo'), '-root', '-tree'])
            matches = []
            for line in output.splitlines():
                match = re.match(r'^\s*(0x[0-9a-fA-F]+)\s+"([^"]*)"', line)
                if match and match.group(2) == self.title:
                    matches.append(match.group(1))
            if len(matches) != 1:
                raise SessionError('Could not identify one matching game window. Keep the game open and retry.')
            self.window = matches[0]
            self._valid_window()
            self._run([self.which('xdotool'), 'windowfocus', '--sync', self.window])
            self.stop_event.clear()
            self.held.clear(); self.expires = 0.0
            self.thread = threading.Thread(target=self._watch, name='browser-input-lease', daemon=True)
            self.thread.start()

    def _release(self):
        # Attempt each key independently so one failed release doesn't prevent others.
        held, self.held = self.held, set()
        for key in sorted(held):
            try:
                self._run([self.which('xdotool'), 'keyup', KEYS[key]])
            except SessionError:
                pass
        self.expires = 0.0

    def apply(self, keys):
        if (not isinstance(keys, list) or len(keys) > MAX_HELD
                or any(not isinstance(key, str) or key not in KEYS for key in keys)
                or len(set(keys)) != len(keys)):
            raise SessionError('Invalid game controls.')
        if any(key in keys for key in ('ControlLeft', 'ControlRight')) and any(key in keys for key in ('KeyR', 'KeyP')):
            raise SessionError('Reset and pause shortcuts are unavailable in the in-page view.')
        with self.lock:
            if self.thread is None or not self.thread.is_alive():
                raise SessionError('Start the in-page view first.')
            try:
                self._valid_window()
                self._run([self.which('xdotool'), 'windowfocus', '--sync', self.window])
                target = set(keys)
                modifiers = {'ShiftLeft', 'ShiftRight', 'ControlLeft', 'ControlRight'}
                for key in sorted(self.held - target, key=lambda item: item in modifiers):
                    self._run([self.which('xdotool'), 'keyup', KEYS[key]])
                    self.held.remove(key)
                for key in sorted(target - self.held, key=lambda item: item not in modifiers):
                    # Track before issuing keydown so failures still attempt release.
                    self.held.add(key)
                    self._run([self.which('xdotool'), 'keydown', KEYS[key]])
                self.expires = self.clock() + LEASE_SECONDS if self.held else 0.0
            except SessionError:
                self._release()
                raise

    def _watch(self):
        while not self.stop_event.wait(0.1):
            with self.lock:
                try:
                    exited = self.process is None or self.process.poll() is not None
                except Exception:
                    exited = True
                if exited:
                    self._release()
                    return
                if self.held and self.clock() >= self.expires:
                    self._release()

    def close(self):
        self.stop_event.set()
        with self.lock:
            self._release()
            thread, self.thread = self.thread, None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=3)
