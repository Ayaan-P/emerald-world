"""Local React launcher bridge. The world service and game remain separate.

Build launcher-web first, then run ``python3 -m world.web_launcher``. The HTTP
listener is loopback-only and its per-launch capability stays in the browser
fragment, not in an HTTP request URL or server log.
"""
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import webbrowser

from .launcher import REPO
from .session import DesktopSession, SessionError
from .transport import read_invitation

DIST = REPO / 'launcher-web' / 'dist'
MAX_BODY = 32768


class LauncherBridge:
    """Serialize access to the existing session; never return credentials."""
    def __init__(self, session, binary):
        self.session = session
        self.binary = Path(binary)
        self.remote_paths = None
        self.lock = threading.RLock()

    def snapshot(self):
        with self.lock:
            labels = {item['key']: item['display_name'] for item in self.session.world_library()}
            worlds = []
            for item in self.session.friend_worlds():
                key = item['name']
                label = labels.get(key, key)
                if label == key and key.startswith('remote-'):
                    label = 'Friend’s world · ' + key[-4:]
                worlds.append({'key': key, 'name': label, 'trainer': item['trainer']})
            return {'worlds': worlds, 'connected': self.session.state is not None,
                    'trainer': self.session.remote_trainer,
                    'games': [name for name, (process, _paths) in self.session.games.items()
                              if process.poll() is None], 'status': self.session.status}

    def action(self, action, payload):
        with self.lock:
            if action == 'join':
                raw = payload.get('invitation')
                if not isinstance(raw, str) or len(raw.encode('utf-8')) > 4096:
                    raise SessionError('Choose a valid invitation file.')
                with tempfile.TemporaryDirectory(prefix='emerald-invite-') as directory:
                    path = Path(directory) / 'invite.json'
                    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    with os.fdopen(fd, 'w') as out:
                        out.write(raw)
                    invitation = read_invitation(path)
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
            elif action == 'launch':
                if self.remote_paths is None or self.session.state is None:
                    raise SessionError('Join a world before launching your trainer.')
                from scripts.linux_client import binary_ready, discover_display
                if not binary_ready(self.binary):
                    raise SessionError('The native game is not built. Follow INSTALL_PC.md first.')
                if self.session.managed_display is None:
                    self.session.start_display(discover_display())
                self.session.launch(self.remote_paths, self.binary, self.session.managed_display.display)
            elif action == 'leave':
                trainer = self.session.remote_trainer
                if not trainer:
                    raise SessionError('No connected trainer is selected.')
                self.session.leave_game(trainer)
            elif action == 'disconnect':
                self.session.disconnect()
                self.remote_paths = None
            elif action == 'forget':
                name = payload.get('world')
                if not isinstance(name, str):
                    raise SessionError('Choose a saved world.')
                self.session.forget_friend(name)
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
            if path == '/api/state':
                if not self.authorized():
                    self.send_error(403)
                    return
                self.send_json(200, bridge.snapshot())
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
                if not isinstance(data, dict) or set(data) != {'action', 'payload'} or not isinstance(data['payload'], dict):
                    raise ValueError
                if data['action'] == 'quit' and not data['payload']:
                    self.send_json(200, {'status': 'Launcher is closing.'})
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                    return
                self.send_json(200, bridge.action(data['action'], data['payload']))
            except SessionError as exc:
                self.send_json(400, {'error': str(exc)})
            except (OSError, ValueError, TypeError, KeyError):
                self.send_json(400, {'error': 'Could not complete that action. Check the invitation, connection and launcher setup.'})

    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worlds-root', type=Path, default=Path.home() / '.local/share/emerald-world/worlds')
    parser.add_argument('--binary', type=Path)
    args = parser.parse_args(argv)
    if not (DIST / 'index.html').is_file():
        parser.error('Build launcher-web with npm ci and npm run build first.')
    from scripts.linux_client import discover_binary
    session = DesktopSession(DesktopSession.create_root(args.worlds_root.absolute()))
    bridge = LauncherBridge(session, args.binary or discover_binary())
    capability = secrets.token_urlsafe(32)
    # Bind first, then create a handler with the actual ephemeral port.
    server = ThreadingHTTPServer(('127.0.0.1', 0), BaseHTTPRequestHandler, bind_and_activate=True)
    server.RequestHandlerClass = handler_for(bridge, capability, server.server_port)
    try:
        if not webbrowser.open(f'http://127.0.0.1:{server.server_port}/#{capability}'):
            raise RuntimeError('Could not open the local launcher in a browser.')
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        with bridge.lock:
            session.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
