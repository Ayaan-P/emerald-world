"""Local React launcher bridge. The world service and game remain separate.

Build launcher-web first, then run ``python3 -m world.web_launcher``. The HTTP
listener is loopback-only and its per-launch capability stays in the browser
fragment, not in an HTTP request URL or server log.
"""
import argparse
import base64
import binascii
import hashlib
import hmac
import importlib.util
import json
import os
import re
from pathlib import Path
import secrets
import stat
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import subprocess

from .launcher import REPO
from .session import DesktopSession, SessionError
from .transport import read_invitation

DIST = REPO / 'launcher-web' / 'dist'
MAX_BODY = 180000
MAX_SAVE = 131072


class LauncherBridge:
    """Serialize access to the existing session; never return credentials."""
    def __init__(self, session, binary):
        self.session = session
        self.binary = Path(binary)
        self.remote_paths = None
        self.browser_input = None
        self.lock = threading.RLock()
        from .hosting_ui import HostedLauncher
        self.hosted = HostedLauncher(session)

    def offline_saves(self):
        """List private offline profiles without opening their save contents."""
        def private_dir(path, mask=0o077):
            try:
                info = path.lstat()
                return stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid() and not info.st_mode & mask
            except OSError:
                return False

        found = []
        from .world_library import _read_metadata
        for world in sorted(self.session.root.iterdir()):
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,48}', world.name) or world.name == 'Deleted':
                continue
            if not private_dir(world, 0o022):
                continue
            offline = world / '.offline'
            trainers = offline / 'trainers'
            if not private_dir(offline) or not private_dir(trainers):
                continue
            try:
                marker = (offline / '.offline-copy').lstat()
                if not stat.S_ISREG(marker.st_mode) or marker.st_uid != os.geteuid() or marker.st_nlink != 1 or marker.st_mode & 0o077:
                    continue
            except OSError:
                continue
            try:
                label = _read_metadata(world)['display_name']
            except (OSError, ValueError, TypeError, KeyError):
                label = world.name
            if label == world.name:
                label = ('Solo adventure' if world.name.startswith('solo-') else 'Offline adventure') + ' · ' + world.name[-4:]
            for trainer in sorted(trainers.iterdir()):
                if re.fullmatch(r'[A-Za-z0-9_-]{1,24}', trainer.name) and private_dir(trainer):
                    found.append({'world': world.name, 'trainer': trainer.name, 'name': label})
        return found

    def _start_offline(self, world, trainer, copy=False, seed_save=None):
        if self.session.state is not None or any(p.poll() is None for p, _ in self.session.games.values()):
            raise SessionError('Disconnect and close any running game before playing offline.')
        self.stop_browser_input()
        from scripts.linux_client import binary_ready, discover_display
        if not binary_ready(self.binary):
            raise SessionError('The native game is not built. Follow INSTALL_PC.md first.')
        if self.session.managed_display is None:
            self.session.start_display(discover_display())
        options = {'copy_online': copy}
        if seed_save is not None:
            options['seed_save'] = seed_save
        self.session.launch_offline(world, trainer, self.binary,
                                    self.session.managed_display.display, **options)

    def game_presence(self):
        """Read only fresh, sanitized telemetry from this launcher's own game."""
        trainer = self.session.remote_trainer
        game = self.session.games.get(trainer) if trainer else None
        if game is None or game[0].poll() is not None:
            return None
        try:
            path = game[1]['telemetry']
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, 'r') as source:
                info = os.fstat(source.fileno())
                if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                        or info.st_nlink != 1 or info.st_size > 65536 or not 0 <= time.time() - info.st_mtime <= 5):
                    raise ValueError('stale telemetry')
                value = json.loads(source.read(65537))
            if (not isinstance(value, dict) or value.get('trainer') != trainer
                    or type(value.get('connected')) is not bool
                    or type(value.get('revision')) is not int or value['revision'] < 0
                    or type(value.get('frame')) is not int or value['frame'] < 0):
                raise ValueError('invalid telemetry')
            nearby = None
            roster = value.get('roster')
            if value['connected'] and isinstance(roster, list) and len(roster) <= 8:
                nearby = []
                for peer in roster:
                    if (not isinstance(peer, dict) or not isinstance(peer.get('trainer'), str)
                            or not re.fullmatch(r'[A-Za-z0-9_-]{1,24}', peer['trainer'])
                            or peer.get('nearby') is not True
                            or type(peer.get('ready')) is not bool
                            or type(peer.get('rendered')) is not bool):
                        continue
                    nearby.append({'trainer': peer['trainer'], 'ready': peer['ready'], 'rendered': peer['rendered']})
            return {'state': 'connected' if value['connected'] else 'disconnected', 'nearby': nearby}
        except (OSError, ValueError, TypeError, KeyError, UnicodeError):
            return {'state': 'waiting', 'nearby': []}

    def snapshot(self):
        with self.lock:
            from .world_library import _read_metadata
            worlds = []
            for item in self.session.friend_worlds():
                key = item['name']
                try:
                    metadata = _read_metadata(self.session._world(key))
                    label, favorite = metadata['display_name'], 'favorite' in metadata['tags']
                except (OSError, ValueError, TypeError, KeyError):
                    label, favorite = key, False  # A bad local label must not hide a saved connection.
                if label == key and key.startswith('remote-'):
                    label = 'Friend’s world · ' + key[-4:]
                worlds.append({'key': key, 'name': label, 'trainer': item['trainer'], 'favorite': favorite})
            offline_world_key = None
            for game, (process, paths) in self.session.games.items():
                if not game.startswith('offline/') or process.poll() is not None:
                    continue
                try:
                    profile = Path(paths['profile'])
                    world = profile.parent.parent.parent
                    if (profile.name == game[8:] and profile.parent.name == 'trainers'
                            and profile.parent.parent.name == '.offline'
                            and world.parent == self.session.root
                            and re.fullmatch(r'[A-Za-z0-9_-]{1,48}', world.name)):
                        offline_world_key = world.name
                except (KeyError, TypeError, ValueError):
                    pass
            from scripts.linux_client import prerequisites
            setup = [{'name': name, 'ready': ready, 'help': help_text}
                     for name, ready, help_text in prerequisites(self.binary) if name != 'tkinter']
            return {'worlds': worlds, 'offline_saves': self.offline_saves(), 'presence': self.game_presence(), 'hosting': self.hosted.state(), 'setup': setup, 'connected': self.session.state is not None,
                    'trainer': self.session.remote_trainer,
                    'world_key': self.session.state.name if self.session.state is not None else None,
                    'offline_world_key': offline_world_key,
                    'games': [name for name, (process, _paths) in self.session.games.items()
                              if process.poll() is None], 'status': self.session.status}

    def stop_browser_input(self):
        if self.browser_input is not None:
            self.browser_input.close()
            self.browser_input = None

    def action(self, action, payload):
        with self.lock:
            if action in ('join', 'rejoin', 'host_create', 'host_resume', 'host_join'):
                if any(p.poll() is None for p, _ in self.session.games.values()):
                    raise SessionError('Close your running game before switching worlds.')
                if self.session.state is not None:
                    raise SessionError('Disconnect from your current world first.')
                self.stop_browser_input()
            if action.startswith('host_'):
                if not self.hosted.state()['available']:
                    raise SessionError('The hosted-world backend is not installed yet.')
                from .hosting_protocol import HostingError
                try:
                    if action == 'host_enroll':
                        self.hosted.enroll(payload.get('access'))
                    elif action == 'host_restore':
                        self.hosted.restore_profile(payload.get('profile'))
                    elif action == 'host_export':
                        backup = self.hosted.export_profile()
                        result = self.snapshot()
                        result['download'] = backup
                        result['download_kind'] = 'backup'
                        return result
                    elif action == 'host_refresh':
                        self.hosted.refresh()
                    elif action == 'host_create':
                        self.remote_paths = self.hosted.create(payload.get('name'), payload.get('trainer'))
                    elif action == 'host_ack':
                        self.hosted.acknowledge_create()
                    elif action == 'host_resume':
                        self.remote_paths = self.hosted.resume(payload.get('world'))
                    elif action == 'host_join':
                        self.remote_paths = self.hosted.join(payload.get('invitation'), payload.get('trainer'))
                    elif action == 'host_invite_account':
                        invitation = self.hosted.invite_owner()
                        result = self.snapshot()
                        result['download'] = invitation
                        result['download_kind'] = 'owner'
                        return result
                    elif action == 'host_invite':
                        invitation = self.hosted.invite(payload.get('world'))
                        result = self.snapshot()
                        result['download'] = invitation
                        result['download_kind'] = 'friend'
                        return result
                    else:
                        raise SessionError('Unknown hosted-world action.')
                except SessionError:
                    raise
                except HostingError as exc:
                    if action == 'host_invite_account' and exc.code == 'forbidden':
                        raise SessionError('This account cannot invite new owners. Ask the server owner for access.') from None
                    message = {'capacity': 'The host has no world slots available right now.',
                               'forbidden': 'The host rejected this access or invitation.',
                               'conflict': 'That trainer or request conflicts with an existing one.',
                               'unavailable': 'The hosted service is temporarily unavailable.'}.get(exc.code, 'The hosted service rejected that request.')
                    raise SessionError(message) from None
                except (OSError, ValueError):
                    raise SessionError('Could not complete the hosted-world request. Check your access file and connection, then retry.') from None
            elif action == 'join':
                raw = payload.get('invitation')
                if not isinstance(raw, str) or len(raw.encode('utf-8')) > 4096:
                    raise SessionError('Choose a valid invitation file.')
                with tempfile.TemporaryDirectory(prefix='emerald-invite-') as directory:
                    path = Path(directory) / 'invite.json'
                    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    with os.fdopen(fd, 'w') as out:
                        out.write(raw)
                    try:
                        invitation = read_invitation(path)
                    except (OSError, ValueError):
                        raise SessionError('Invalid invitation. Ask your host to share a fresh file privately.') from None
                    if invitation.get('version') != 1:
                        raise SessionError('This invitation needs the legacy launcher.')
                    endpoint = invitation['endpoint']
                    binding = json.dumps([endpoint['host'], endpoint['port'], invitation['pin'].lower()]).encode()
                    name = 'remote-' + hashlib.sha256(binding).hexdigest()[:16]
                    self.remote_paths = self.session.connect_remote(
                        name, path, (endpoint['host'], endpoint['port']), invitation['pin'])
            elif action == 'rejoin':
                name = payload.get('world')
                if not isinstance(name, str):
                    raise SessionError('Choose a saved world.')
                self.remote_paths = self.session.rejoin_friend(name)
            elif action == 'save_backup_info':
                return {'available': importlib.util.find_spec('world.save_backup') is not None}
            elif action == 'save_backup':
                if importlib.util.find_spec('world.save_backup') is None:
                    raise SessionError('Save backup support is not installed yet.')
                world, trainer, offline = payload.get('world'), payload.get('trainer'), payload.get('offline')
                if not isinstance(world, str) or not isinstance(trainer, str) or type(offline) is not bool:
                    raise SessionError('Choose a saved trainer profile.')
                if offline:
                    known = any(item['world'] == world and item['trainer'] == trainer for item in self.offline_saves())
                else:
                    known = any(item['name'] == world and item['trainer'] == trainer for item in self.session.friend_worlds())
                if not known:
                    raise SessionError('Choose an available saved trainer profile.')
                from .save_backup import backup_save
                try:
                    with tempfile.TemporaryDirectory(prefix='emerald-save-backup-') as directory:
                        destination = Path(directory) / 'trainer.sav'
                        backup_save(self.session._world(world), trainer, destination, offline=offline)
                        encoded = base64.b64encode(destination.read_bytes()).decode('ascii')
                except (OSError, ValueError):
                    raise SessionError('Could not back up this save. Close the game and check that the profile has a save.') from None
                return {'data': encoded, 'filename': 'emerald-trainer-backup.sav'}
            elif action == 'reconnect':
                self.stop_browser_input()
                if self.session.state is None or self.session.remote_trainer is None:
                    raise SessionError('Join a saved world first.')
                name = self.session.state.name
                if not any(item['name'] == name for item in self.session.friend_worlds()):
                    raise SessionError('This connection is no longer saved. Import a new invitation.')
                self.session.disconnect()
                self.remote_paths = None
                self.remote_paths = self.session.rejoin_friend(name)
            elif action == 'launch':
                if self.remote_paths is None or self.session.state is None:
                    raise SessionError('Join a world before launching your trainer.')
                from scripts.linux_client import binary_ready, discover_display
                if not binary_ready(self.binary):
                    raise SessionError('The native game is not built. Follow INSTALL_PC.md first.')
                if self.session.managed_display is None:
                    self.session.start_display(discover_display())
                self.session.launch(self.remote_paths, self.binary, self.session.managed_display.display)
            elif action == 'offline':
                world = payload.get('world')
                copy = payload.get('copy')
                if not isinstance(world, str) or type(copy) is not bool:
                    raise SessionError('Choose a saved world and offline mode.')
                selected = next((item for item in self.session.friend_worlds() if item['name'] == world), None)
                if selected is None:
                    raise SessionError('Choose a saved world.')
                self._start_offline(world, selected['trainer'], copy)
            elif action == 'solo_new':
                trainer = payload.get('trainer')
                if not isinstance(trainer, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,24}', trainer):
                    raise SessionError('Use 1 to 24 letters, numbers, underscores or hyphens for your trainer.')
                world = 'solo-' + secrets.token_hex(12)
                if os.path.lexists(self.session.root / world):
                    raise SessionError('Could not create a new adventure. Please try again.')
                seed = payload.get('seed')
                if seed is None:
                    self._start_offline(world, trainer)
                else:
                    if not isinstance(seed, str) or len(seed) > 174800:
                        raise SessionError('Choose a save file no larger than 128 KiB.')
                    try:
                        data = base64.b64decode(seed, validate=True)
                    except (ValueError, binascii.Error):
                        raise SessionError('That save file could not be read.') from None
                    if not 0 < len(data) <= MAX_SAVE:
                        raise SessionError('Choose a nonempty save file no larger than 128 KiB.')
                    with tempfile.TemporaryDirectory(prefix='emerald-save-') as directory:
                        path = Path(directory) / 'seed.sav'
                        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                        with os.fdopen(fd, 'wb') as output:
                            output.write(data)
                        self._start_offline(world, trainer, seed_save=path)
            elif action == 'solo_resume':
                world, trainer = payload.get('world'), payload.get('trainer')
                if not any(item['world'] == world and item['trainer'] == trainer for item in self.offline_saves()):
                    raise SessionError('Choose an existing offline adventure.')
                self._start_offline(world, trainer)
            elif action == 'leave':
                self.stop_browser_input()
                trainer = payload.get('game', self.session.remote_trainer)
                if not trainer:
                    raise SessionError('No connected trainer is selected.')
                self.session.leave_game(trainer)
            elif action == 'disconnect':
                self.stop_browser_input()
                self.session.disconnect()
                self.remote_paths = None
            elif action == 'favorite':
                name, favorite = payload.get('world'), payload.get('favorite')
                if not isinstance(name, str) or type(favorite) is not bool:
                    raise SessionError('Choose a saved world.')
                if not any(item['name'] == name for item in self.session.friend_worlds()):
                    raise SessionError('Choose a saved world.')
                from .world_library import _read_metadata
                try:
                    metadata = _read_metadata(self.session._world(name))
                    tags = [tag for tag in metadata['tags'] if tag != 'favorite']
                    if favorite:
                        tags.append('favorite')
                    self.session.rename_world(name, metadata['display_name'], tags)
                except (OSError, ValueError, KeyError, TypeError):
                    raise SessionError('Could not update favorites for that world.') from None
            elif action == 'rename':
                name, label = payload.get('world'), payload.get('label')
                if not isinstance(name, str) or not isinstance(label, str):
                    raise SessionError('Choose a world and a name.')
                if not any(item['name'] == name for item in self.session.friend_worlds()):
                    raise SessionError('Choose a saved world.')
                from .world_library import _read_metadata
                try:
                    tags = _read_metadata(self.session._world(name))['tags']
                    self.session.rename_world(name, label, tags)
                except (OSError, ValueError, KeyError, TypeError):
                    raise SessionError('Could not save that name. Use 1 to 80 characters.') from None
            elif action == 'forget':
                name = payload.get('world')
                if not isinstance(name, str):
                    raise SessionError('Choose a saved world.')
                self.session.forget_friend(name)
            elif action == 'screen_info':
                from .browser_input import BrowserInput
                return BrowserInput(self.session).info()
            elif action == 'screen_start':
                from .browser_input import BrowserInput
                self.stop_browser_input()
                control = BrowserInput(self.session)
                control.start()
                self.browser_input = control
                return {'active': True}
            elif action == 'screen_keys':
                if self.browser_input is None:
                    raise SessionError('Start the in-page view first.')
                self.browser_input.apply(payload.get('keys'))
                return {'active': True}
            elif action == 'screen_stop':
                self.stop_browser_input()
                return {'active': False}
            else:
                raise SessionError('Unknown launcher action.')
            return self.snapshot()


def handler_for(bridge, capability, port, dist=DIST):
    origin = f'http://127.0.0.1:{port}'
    host = f'127.0.0.1:{port}'

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass  # Invitations and capabilities never belong in logs.

        def common(self, status, content_type):
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()

        def authorized(self, post=False):
            supplied = self.headers.get('Authorization', '')
            request_origin = self.headers.get('Origin')
            return (self.headers.get('Host') == host
                    and (request_origin == origin if post else request_origin in (None, origin))
                    and hmac.compare_digest(supplied, 'Bearer ' + capability))

        def send_json(self, status, value):
            self.common(status, 'application/json; charset=utf-8')
            self.wfile.write(json.dumps(value).encode())

        def do_GET(self):
            if self.headers.get('Host') != host:
                self.send_error(403)
                return
            path = urlsplit(self.path).path
            if path in ('/api/state', '/api/instance'):
                if not self.authorized():
                    self.send_error(403)
                    return
                self.send_json(200, {'launcher': 1} if path == '/api/instance' else bridge.snapshot())
                return
            relative = 'index.html' if path == '/' else path.lstrip('/')
            root = Path(dist).resolve()
            target = (root / relative).resolve()
            if not target.is_relative_to(root) or not target.is_file():
                self.send_error(404)
                return
            suffixes = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
                        '.css': 'text/css; charset=utf-8', '.png': 'image/png', '.webp': 'image/webp', '.svg': 'image/svg+xml'}
            if target.suffix not in suffixes:
                self.send_error(404)
                return
            self.common(200, suffixes[target.suffix])
            self.wfile.write(target.read_bytes())

        def do_POST(self):
            if (urlsplit(self.path).path != '/api/action'
                    or self.headers.get('Transfer-Encoding') is not None
                    or not self.authorized(post=True)
                    or self.headers.get('Content-Type') != 'application/json'):
                self.send_error(403)
                return
            try:
                length = int(self.headers.get('Content-Length', '-1'))
                if not 0 <= length <= MAX_BODY:
                    raise ValueError
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict) or set(data) != {'action', 'payload'} or not isinstance(data['action'], str) or not isinstance(data['payload'], dict):
                    raise ValueError
                if data['action'] == 'quit' and not data['payload']:
                    with bridge.lock:
                        bridge.stop_browser_input()
                    self.send_json(200, {'status': 'Launcher is closing.'})
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                    return
                self.send_json(200, bridge.action(data['action'], data['payload']))
            except SessionError as exc:
                self.send_json(400, {'error': str(exc)})
            except (OSError, ValueError, TypeError, KeyError):
                self.send_json(400, {'error': 'Could not complete that action. Check the invitation, connection and launcher setup.'})

    return Handler


def install_shortcut(directory=None):
    """Install a distinct, idempotent user shortcut without replacing files."""
    from scripts.linux_client import exec_token
    directory = Path(directory or Path.home() / '.local/share/applications').absolute()
    if directory.resolve() != directory:
        raise ValueError('Application directory cannot contain symlinks.')
    # Validate all interpolated fields before creating anything.
    interpreter = Path(sys.executable).resolve()
    command = exec_token(interpreter) + ' -m world.web_launcher'
    exec_token(REPO)
    content = ('[Desktop Entry]\nType=Application\nName=Emerald World React (Experimental)\n'
               'Comment=Open the experimental Emerald World launcher\n'
               f'Exec={command}\nPath={REPO}\nTerminal=false\nCategories=Game;\n')
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = directory / 'emerald-world-react.desktop'
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    except FileExistsError:
        fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or stream.read(len(content.encode()) + 1) != content.encode()):
                raise ValueError('An existing shortcut was left unchanged.')
    else:
        with os.fdopen(fd, 'w') as output:
            output.write(content)
    return target


def open_browser(url):
    """Keep browser-provider diagnostics private, including failed open attempts."""
    try:
        result = subprocess.run(
            [sys.executable, '-c', 'import sys, webbrowser; sys.exit(0 if webbrowser.open(sys.stdin.read()) else 1)'],
            input=url, text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worlds-root', type=Path, default=Path.home() / '.local/share/emerald-world/worlds')
    parser.add_argument('--binary', type=Path)
    parser.add_argument('--install', action='store_true', help='add a separate user application shortcut')
    args = parser.parse_args(argv)
    if not (DIST / 'index.html').is_file():
        parser.error('Build launcher-web with npm ci and npm run build first.')
    if args.install:
        print(f'Installed experimental launcher shortcut: {install_shortcut()}')
        return 0
    from contextlib import ExitStack
    import signal
    from .launcher_instance import LauncherInstance, InstanceError
    from scripts.linux_client import discover_binary

    def interrupted(_signum, _frame):
        raise KeyboardInterrupt

    previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        with ExitStack() as cleanup:
            root = DesktopSession.create_root(args.worlds_root.absolute())
            instance = LauncherInstance(root)
            cleanup.callback(instance.close)
            if not instance.owner:
                if not open_browser(instance.existing_url()):
                    raise InstanceError('Could not open the running launcher in a browser. Retry the shortcut.')
                return 0
            session = DesktopSession(root)
            cleanup.callback(session.close)
            bridge = LauncherBridge(session, args.binary or discover_binary())
            cleanup.callback(bridge.stop_browser_input)
            capability = secrets.token_urlsafe(32)
            server = ThreadingHTTPServer(('127.0.0.1', 0), BaseHTTPRequestHandler)
            # Drain in-flight actions before closing their session and brokers.
            server.daemon_threads = False
            cleanup.callback(server.server_close)
            server.RequestHandlerClass = handler_for(bridge, capability, server.server_port)
            # Serve before opening the browser so concurrent shortcuts can probe
            # even while the desktop's browser opener is still starting.
            worker = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.1})
            worker.start()
            cleanup.callback(worker.join)
            cleanup.callback(server.shutdown)
            instance.publish(server.server_port, capability)
            if not open_browser(f'http://127.0.0.1:{server.server_port}/#{capability}'):
                raise InstanceError('Could not open the local launcher in a browser. Retry the shortcut.')
            worker.join()
    except KeyboardInterrupt:
        pass
    except (OSError, ValueError) as error:
        # Neither discovery data nor browser-provider text belongs in diagnostics.
        print(str(error) if isinstance(error, InstanceError) else
              'Could not start the launcher safely. Check worlds-root permissions and launcher setup.', file=sys.stderr)
        return 1
    finally:
        signal.signal(signal.SIGTERM, previous)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
