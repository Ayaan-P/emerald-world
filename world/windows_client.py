"""Remote-only Windows guest. Native game files stay in a held local profile.

The loopback capability is not a Windows sandbox. Certificate pinning uses the
same explicit leaf-DER trust anchor and EWTR1 framing as world.transport.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import socket
import stat
import subprocess
import sys
import threading
import time

from .transport import ClientBroker

_HEX = re.compile(r'[0-9a-fA-F]{64}\Z')


class LoopbackGateway(ClientBroker):
    """Bounded IPv4 loopback endpoint. Authenticate before making any TLS dial.

    start() returns self, address is (127.0.0.1, ephemeral_port), close() joins
    workers. A closed instance cannot restart. Make a fresh instance to rejoin.
    """
    def __init__(self, remote, *, fingerprint, local_token, auth_timeout=5, max_clients=8, **limits):
        # One local native guest needs a small bounded gateway, not the public
        # authority's larger population limit.
        if type(max_clients) is not int or not 1 <= max_clients <= 8:
            raise ValueError('local gateway max_clients must be within eight')
        if not isinstance(local_token, str) or not _HEX.fullmatch(local_token):
            raise ValueError('invalid local capability')
        if not 0 < auth_timeout <= 5:
            raise ValueError('authentication deadline must be within five seconds')
        super().__init__('', remote, fingerprint=fingerprint, max_clients=max_clients, **limits)
        self.local_token = local_token
        self.auth_timeout = auth_timeout
        self.address = None

    def start(self):
        if self._listener is not None or self._stop.is_set():
            raise RuntimeError('gateway cannot be restarted')
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            listener.bind(('127.0.0.1', 0))
            listener.listen(self.max_clients)
            self.address = listener.getsockname()
            return self._start(listener)
        except BaseException:
            listener.close()
            raise

    def _pair(self, local, owned):
        expected = b'EWLOCAL1 ' + self.local_token.encode('ascii') + b'\n'
        deadline = time.monotonic() + self.auth_timeout
        received = bytearray()
        while len(received) < len(expected):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('local authentication expired')
            local.settimeout(remaining)
            data = local.recv(len(expected) - len(received))
            if not data:
                raise ValueError('local authentication failed')
            received.extend(data)
        # Only compare the complete bounded header. Prefix rejection leaks a
        # byte-at-a-time oracle for the local capability.
        if time.monotonic() >= deadline:
            raise TimeoutError('local authentication expired')
        if not hmac.compare_digest(received, expected):
            raise ValueError('local authentication failed')
        return super()._pair(local, owned)


def _invitation(path):
    from .transport import read_invitation
    return read_invitation(path)


def _unsafe_profile_path(path, *, directory=False):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    # Junctions and other Windows reparse points are not necessarily symlinks.
    if (stat.S_ISLNK(info.st_mode)
            or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
        return True
    if directory:
        return not stat.S_ISDIR(info.st_mode)
    return not stat.S_ISREG(info.st_mode) or info.st_nlink != 1


class _ProfileLock:
    """Held kernel lock. The stable lock file is deliberately never unlinked."""
    def __init__(self, directory):
        self.stream = None
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = directory / 'profile.lock'
        if _unsafe_profile_path(path):
            raise RuntimeError('unsafe profile lock')
        stream = path.open('a+b')
        try:
            if os.name == 'nt':
                import msvcrt
                if os.fstat(stream.fileno()).st_size == 0:
                    stream.write(b'\0')
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.stream = stream
        except OSError:
            stream.close()
            raise RuntimeError('profile is already in use') from None

    def close(self):
        if self.stream is not None:
            stream, self.stream = self.stream, None
            if os.name == 'nt':
                import msvcrt
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            stream.close()


def locate_game(*, root=None):
    """Resolve the one-directory bundle first. Never search PATH or user files."""
    frozen = bool(getattr(sys, 'frozen', False))
    base = Path(root) if root is not None else (
        Path(sys.executable).parent if frozen else Path(__file__).resolve().parent.parent)
    candidates = [base/'game/pokeemerald64.exe']
    if not frozen:
        candidates += [base/'build/windows/pokeemerald64.exe', base/'pokeemerald64.exe']
    for candidate in candidates:
        if candidate.is_file():
            return candidate.absolute()
    raise ValueError('packaged game is missing')


def _request_child_close(child):
    """Ask SDL's own window to close before using termination as a fallback."""
    if os.name != 'nt':
        child.terminate()
        return
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.PostMessageW.restype = wintypes.BOOL

    @callback_type
    def visit(hwnd, parameter):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == child.pid:
            user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE, no focus change.
        return True
    user32.EnumWindows(visit, 0)


class WindowsGuestSession:
    """One invitation, own files, one native child and a held profile lock.

    data_root overrides LOCALAPPDATA/EmeraldWorld for isolated tests. prepare()
    creates the profile/config and gateway without starting a game. start()
    launches the normal interactive child. close() stops child before unlocking.
    """
    def __init__(self, host, port, pin, invitation, *, data_root=None, binary=None, engine='vanilla'):
        if engine not in ('vanilla', 'expansion-native'):
            raise ValueError('unsupported engine')
        if engine == 'expansion-native' and binary is None:
            raise ValueError('Expansion requires its verified engine, no legacy fallback')
        self.engine = engine
        if type(pin) is not str or not _HEX.fullmatch(pin):
            raise ValueError('invalid certificate pin')
        if (type(host) is not str or not host or len(host) > 253
                or any(c.isspace() or ord(c) < 32 for c in host)
                or type(port) is not int or not 1 <= port <= 65535):
            raise ValueError('invalid host or port')
        identity = _invitation(invitation)
        if data_root is None:
            local = os.environ.get('LOCALAPPDATA')
            if not local:
                raise ValueError('LOCALAPPDATA is not available')
            data_root = Path(local) / 'EmeraldWorld'
        self.remote = (host, port)
        self.pin = pin.lower()
        self.trainer = identity['trainer']
        self._token = identity['token']
        self.binary = Path(binary).absolute() if binary is not None else None
        # Windows case folding and reserved device names must not merge exact
        # server identities. Neither digest contains either invitation capability.
        namespace = hashlib.sha256(json.dumps([host, port, self.pin],
                                              separators=(',', ':')).encode('utf-8')).hexdigest()
        trainer_directory = hashlib.sha256(self.trainer.encode('ascii')).hexdigest()
        # The caller's data root is trusted, including Windows short-name or
        # junction aliases. Resolve only that boundary, never an untrusted child.
        boundary = Path(data_root).resolve()
        if self.engine == 'expansion-native':
            boundary = boundary / 'expansion-native'
        profile = boundary / namespace / trainer_directory
        self.paths = {'profile': profile, 'save': profile/'game.sav',
                      'settings': profile/'pokeemerald.ini', 'config': profile/'world.conf',
                      'telemetry': profile/'telemetry.json'}
        self._guard = threading.RLock()
        self._profile_lock = self.gateway = self.child = None

    def prepare(self):
        with self._guard:
            if self._profile_lock is not None:
                return self
            profile = self.paths['profile']
            if (any(_unsafe_profile_path(path, directory=True)
                    for path in (profile.parent, profile))
                    or profile.resolve() != profile):
                raise ValueError('unsafe profile directory')
            self._profile_lock = _ProfileLock(profile)
            try:
                for path in self.paths.values():
                    if _unsafe_profile_path(path, directory=(path == profile)):
                        raise ValueError('unsafe profile file')
                telemetry = self.paths['telemetry'].as_posix()
                if ('\n' in telemetry or '\r' in telemetry
                        or len(telemetry.encode('utf-8')) >= 1024):
                    raise ValueError('unsupported telemetry path')
                self.gateway = LoopbackGateway(self.remote, fingerprint=self.pin,
                                               local_token=secrets.token_hex(32)).start()
                text = (f'loopback_port {self.gateway.address[1]}\n'
                        f'loopback_token {self.gateway.local_token}\n'
                        f'trainer {self.trainer}\ntoken {self._token}\n'
                        f'telemetry {telemetry}\n')
                temporary = profile / ('config-' + secrets.token_hex(8) + '.tmp')
                try:
                    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
                        stream.write(text)
                    os.replace(temporary, self.paths['config'])
                finally:
                    temporary.unlink(missing_ok=True)
                return self
            except BaseException:
                self.close()
                raise

    def game_args(self):
        if self._profile_lock is None or self.gateway is None:
            raise RuntimeError('prepare profile before constructing game arguments')
        binary = self.binary if self.binary is not None else locate_game()
        if not binary.is_file():
            raise ValueError('packaged game is missing')
        if self.engine == 'expansion-native':
            return [str(binary), '--data-dir', str(self.paths['profile']),
                    '--save', str(self.paths['save']),
                    '--rtc-offset', str(self.paths['profile']/'clock.rtc')]
        return [str(binary), '--save', str(self.paths['save']),
                '--config', str(self.paths['settings']), '--world-config', str(self.paths['config'])]

    def game_environment(self):
        if self.engine != 'expansion-native':
            return None
        # Do not inherit agent/replay/offline world controls from the launcher.
        env = {k: v for k, v in os.environ.items() if not k.startswith('EW_')}
        env['EW_WORLD_CONFIG'] = str(self.paths['config'])
        env['EW_WORLD_HEADLESS'] = '0'
        return env

    def start(self):
        with self._guard:
            if self.child is not None:
                raise RuntimeError('disconnect before joining again')
            try:
                self.prepare()
                command = self.game_args()
                self.paths['telemetry'].unlink(missing_ok=True)
                self._started_ns = time.time_ns()
                # No agent controls, dummy SDL drivers, shell or hidden-window flags.
                self.child = subprocess.Popen(command, cwd=str(self.paths['profile']),
                                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                              stderr=subprocess.DEVNULL, shell=False, env=self.game_environment())
            except (OSError, ValueError, RuntimeError):
                self.close()
                raise RuntimeError('could not launch game') from None
            return self

    def status(self):
        """One fresh own-file read. Atomic rename failures are retried next poll.

        A live process or TCP tunnel is not evidence of an online WORLD session.
        Only fresh, correctly typed native telemetry can say online.
        """
        child = self.child
        result = {'state': 'stopped', 'trainer': self.trainer}
        if child is None or child.poll() is not None:
            return result
        result['state'] = 'waiting'
        try:
            with self.paths['telemetry'].open('rb') as stream:
                info = os.fstat(stream.fileno())
                raw = stream.read(262145)
            if (len(raw) > 262144 or info.st_mtime_ns < self._started_ns
                    or not 0 <= time.time_ns() - info.st_mtime_ns <= 3_000_000_000):
                return result
            data = json.loads(raw)
            if (type(data) is not dict or data.get('trainer') != self.trainer
                    or type(data.get('connected')) is not bool
                    or type(data.get('frame')) is not int or data['frame'] < 0):
                return result
            result['state'] = 'online' if data['connected'] else 'connecting'
            result['frame'] = data['frame']
        except (OSError, ValueError, TypeError):
            pass
        return result

    def close(self):
        with self._guard:
            if self.child is not None:
                if self.child.poll() is None:
                    try:
                        _request_child_close(self.child)
                    except OSError:
                        # The process may have exited between poll and WM_CLOSE.
                        pass
                    try:
                        self.child.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        self.child.terminate()
                        try:
                            self.child.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            self.child.kill()
                            self.child.wait(timeout=3)
                else:
                    self.child.wait()
                self.child = None
            if self.gateway is not None:
                self.gateway.close()
                self.gateway = None
            if self._profile_lock is not None:
                self._profile_lock.close()
                self._profile_lock = None


class GuestController:
    """Serial background lifecycle and telemetry IO. Tk never waits on a socket."""
    def __init__(self):
        import queue
        self._queue = queue.Queue(maxsize=1)
        self._lock = threading.Lock()
        self._shutdown = threading.Event()
        self.closed = threading.Event()
        self._busy = False
        self._state = {'state': 'stopped'}
        self._session = None
        self._thread = threading.Thread(target=self._run, name='world-guest-ui', daemon=True)
        self._thread.start()

    def submit(self, action, settings=None):
        if action not in ('join', 'rejoin', 'disconnect'):
            raise ValueError('invalid guest action')
        with self._lock:
            if (self._busy or self._shutdown.is_set() or self.closed.is_set()
                    or not self._thread.is_alive()):
                return False
            self._busy = True
            self._state = {'state': 'working'}
            self._queue.put_nowait((action, settings))
        return True

    def snapshot(self):
        with self._lock:
            return dict(self._state, busy=self._busy)

    def shutdown(self):
        self._shutdown.set()

    def _publish(self, state):
        with self._lock:
            self._state = state

    def _run(self):
        import queue
        cleanup_pending = False
        try:
            while not self._shutdown.is_set():
                try:
                    action, settings = self._queue.get(timeout=.2)
                except queue.Empty:
                    if self._session is not None and not cleanup_pending:
                        try:
                            state = self._session.status()
                            if state['state'] == 'stopped':
                                cleanup_pending = True
                                self._session.close()
                                self._session = None
                                cleanup_pending = False
                            self._publish(state)
                        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
                            self._publish({'state': 'error', 'message':
                                           'Could not read game status or finish cleanup. '
                                           'Use Disconnect to retry cleanup before joining again.'})
                    continue
                try:
                    if action in ('rejoin', 'disconnect') and self._session is not None:
                        cleanup_pending = True
                        self._session.close()
                        self._session = None
                        cleanup_pending = False
                    if action in ('join', 'rejoin'):
                        if self._session is not None:
                            raise RuntimeError('disconnect before joining again')
                        self._session = WindowsGuestSession(*settings)
                        self._session.start()
                    self._publish(self._session.status() if self._session else {'state': 'stopped'})
                except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
                    self._publish({'state': 'error', 'message':
                                   'Could not join or disconnect. Check host, pin, invitation and profile. '
                                   'Use Disconnect to retry cleanup before joining again.'})
                finally:
                    with self._lock:
                        self._busy = False
        except Exception:
            # Unexpected worker failures must not strand accepted UI commands or
            # expose exception text, which can include invitation capabilities.
            self._publish({'state': 'error', 'message':
                           'Guest controls stopped unexpectedly. Close this window and reopen it.'})
        finally:
            with self._lock:
                self._shutdown.set()
                self._busy = False
            # Never signal closed (and let Tk exit) while a child may hold a save.
            while self._session is not None:
                try:
                    self._session.close()
                    self._session = None
                except (OSError, RuntimeError, subprocess.TimeoutExpired):
                    self._publish({'state': 'error', 'message': 'Waiting for the game to close.'})
                    time.sleep(.25)
            self.closed.set()


class GuestWindow:
    """Remote guest controls only. All Tk calls stay on the Tk thread."""
    def __init__(self, root, controller):
        import tkinter as tk
        from tkinter import ttk
        self.root, self.controller = root, controller
        self.closing = False
        root.title('Emerald World')
        root.columnconfigure(1, weight=1)
        self.values = {}
        for row, (name, default) in enumerate((('Host', ''), ('Port', '8765'),
                                                ('Pin', ''), ('Invitation', ''))):
            ttk.Label(root, text=name).grid(row=row, column=0, padx=8, pady=5, sticky='w')
            variable = tk.StringVar(master=root, value=default)
            self.values[name] = variable
            ttk.Entry(root, textvariable=variable, width=64).grid(
                row=row, column=1, padx=8, pady=5, sticky='ew')
        ttk.Button(root, text='Import invitation', command=self.import_invitation).grid(row=3, column=2, padx=8)
        self.buttons = []
        for column, (name, callback) in enumerate((('Join', lambda: self.join('join')),
                                                 ('Rejoin', lambda: self.join('rejoin')),
                                                 ('Disconnect', self.disconnect))):
            button = ttk.Button(root, text=name, command=callback)
            button.grid(row=4, column=column, padx=8, pady=8)
            self.buttons.append(button)
        self.status_text = tk.StringVar(master=root, value='Disconnected')
        ttk.Label(root, textvariable=self.status_text, wraplength=600).grid(
            row=5, column=0, columnspan=3, padx=8, pady=8, sticky='w')
        ttk.Label(root, text=('Use your own save. Invitations contain a private WORLD token.\n'
                              'A bundled TLS pin is trustworthy only when the invitation came from your host through a trusted channel.'),
                  wraplength=600).grid(
            row=6, column=0, columnspan=3, padx=8, pady=8, sticky='w')
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.tick()

    def pick_invitation(self):
        """Select a legacy file without changing manually entered connection fields."""
        from tkinter import filedialog
        path = filedialog.askopenfilename(parent=self.root, title='Choose WORLD invitation',
                                          filetypes=[('Invitation JSON', '*.json')])
        if path:
            self.values['Invitation'].set(path)

    def import_invitation(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(parent=self.root, title='Choose WORLD invitation',
                                          filetypes=[('Invitation JSON', '*.json')])
        if path:
            try:
                invitation = _invitation(path)
            except ValueError:
                self.status_text.set('Invalid invitation. Choose a small invitation JSON file from your host.')
                return
            if 'endpoint' in invitation:
                self.values['Host'].set(invitation['endpoint']['host'])
                self.values['Port'].set(str(invitation['endpoint']['port']))
                self.values['Pin'].set(invitation['pin'])
            self.values['Invitation'].set(path)
            self.status_text.set('Invitation imported. Trust its pin only if received from your host through a trusted channel.'
                                 if 'endpoint' in invitation else
                                 'Legacy invitation selected. Enter the host, port and independently trusted TLS pin.')

    def join(self, action):
        try:
            # Do not strip or reparse tokens or pins into a different credential.
            settings = (self.values['Host'].get(), int(self.values['Port'].get()),
                        self.values['Pin'].get(), self.values['Invitation'].get())
        except ValueError:
            self.status_text.set('Enter a valid port.')
            return
        self.controller.submit(action, settings)

    def disconnect(self):
        self.controller.submit('disconnect')

    def close(self):
        self.closing = True
        self.controller.shutdown()

    def tick(self):
        snapshot = self.controller.snapshot()
        labels = {'stopped': 'Disconnected', 'working': 'Working...',
                  'waiting': 'Waiting for fresh game telemetry', 'connecting': 'Connecting to WORLD',
                  'online': 'Online', 'error': 'Connection failed'}
        text = snapshot.get('message') or labels.get(snapshot['state'], 'Waiting')
        if 'trainer' in snapshot:
            text += ' | Trainer ' + snapshot['trainer']
        if 'frame' in snapshot:
            text += ' | Frame ' + str(snapshot['frame'])
        self.status_text.set(text)
        for button in self.buttons:
            button.configure(state='disabled' if snapshot['busy'] or self.closing else 'normal')
        if self.closing and self.controller.closed.is_set():
            self.root.destroy()
            return
        self.root.after(200, self.tick)


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='Emerald World remote Windows guest')
    parser.add_argument('--self-test', action='store_true', help='check packaged game and Tk without launching a game')
    args = parser.parse_args(argv)
    if args.self_test:
        root = None
        result = {'ok': False, 'engine': False, 'tk': False}
        try:
            locate_game()
            result['engine'] = True
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            root.update()
            result['tk'] = True
            result['ok'] = True
        except Exception:
            # Errors may contain paths or user-controlled strings. Emit only flags.
            pass
        finally:
            if root is not None:
                try:
                    root.destroy()
                except Exception:
                    result['ok'] = False
        print(json.dumps(result, sort_keys=True))
        return 0 if result['ok'] else 1
    import tkinter as tk
    root = tk.Tk()
    controller = GuestController()
    try:
        GuestWindow(root, controller)
        root.mainloop()
    finally:
        controller.shutdown()
        controller.closed.wait()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
