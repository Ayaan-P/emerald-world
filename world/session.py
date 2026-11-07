"""Explicit-root desktop sessions. No personal save or HOME discovery."""
import argparse
import json
from pathlib import Path
import re
import subprocess

from .launcher import REPO, discover_worlds, game_command, prepare_profile


class SessionError(ValueError):
    """A fixed, user-facing session prerequisite error, never provider text."""


class DesktopSession:
    @staticmethod
    def create_root(worlds_root):
        root = Path(worlds_root)
        if not root.is_absolute() or root.resolve() != root:
            raise ValueError('choose an absolute worlds root without symlinks')
        root.mkdir(parents=True, mode=0o700, exist_ok=True)
        if not root.is_dir():
            raise ValueError('worlds root must be a directory')
        return root

    def __init__(self, worlds_root):
        root = Path(worlds_root)
        if not root.is_absolute() or root.resolve() != root or not root.is_dir():
            raise ValueError('choose an existing absolute worlds root without symlinks')
        self.root = root
        self.state = None
        self.server = None
        self.broker = None
        self.remote_trainer = None
        self.sharing_pin = None
        # Remote brokers are connections, never ownership of dedicated worlds.
        self._hosts = {}
        self.games = {}
        self.game_locks = {}
        self.agent_games = set()
        self.managed_display = None
        self.intents = {}
        self.gm_thread = None
        self.gm_stop = None
        self.gm_error = None
        self.status = 'Choose a world to host or join.'

    def worlds(self):
        return discover_worlds(self.root)

    def world_library(self):
        from .world_library import cards
        return cards(self.root, self.worlds())

    def friend_worlds(self):
        from .friend_worlds import worlds
        return worlds(self.root)

    def rejoin_friend(self, name):
        from .friend_worlds import read, BOOKMARK
        if self.state is not None:
            raise SessionError('Disconnect before rejoining a saved friend world.')
        path = self._world(name)
        invitation = read(path)
        endpoint = invitation['endpoint']
        return self.connect_remote(name, path/BOOKMARK,
                                   (endpoint['host'], endpoint['port']), invitation['pin'])

    def forget_friend(self, name):
        from .friend_worlds import forget
        path = self._world(name)
        if self.state == path:
            raise SessionError('Disconnect before forgetting this friend world.')
        forget(path)
        self.status = 'Friend connection forgotten. Private trainer progress is unchanged.'

    def rename_world(self, name, display_name, tags):
        from .world_library import rename
        rename(self.root, name, display_name, tags)
        self.status = 'World label saved. Stable world key and trainer saves are unchanged.'

    def delete_world(self, name):
        from .world_library import delete
        path = self._world(name)
        if name in self.hosted_worlds():
            raise SessionError('Explicitly shut down this local world before deletion.')
        if self.state == path:
            raise SessionError('Disconnect this world before moving it to Deleted.')
        if any(process.poll() is None and paths['profile'].is_relative_to(path)
               for process, paths in self.games.values()):
            raise SessionError('Stop this world\'s native games before deletion.')
        token = delete(self.root, name)
        self.status = 'World moved to Deleted. Use Restore deleted world to recover it.'
        return token

    def deleted_worlds(self):
        from .world_library import deleted
        return deleted(self.root)

    def restore_world(self, token):
        from .world_library import restore
        path = restore(self.root, token, len(self.worlds()))
        self.status = 'World restored. Its stable key and trainer saves are unchanged.'
        return path

    def _world(self, name):
        if name == 'Deleted' or not re.fullmatch(r'[A-Za-z0-9_-]{1,48}', name):
            raise ValueError('world key must be 1..48 letters, digits, _ or - and cannot be Deleted')
        path = self.root / name
        if path.resolve() != path:
            raise ValueError('world cannot be a symlink')
        from .launcher import require_online_state
        require_online_state(path)
        return path

    def create_world(self, name):
        from .server import WorldServer
        from .world_library import CAPACITY
        if name == 'Deleted' or len(self.worlds()) >= CAPACITY:
            raise SessionError('Choose a world key other than Deleted. The library holds at most 32 worlds.')
        path = self._world(name)
        from .world_library import WorldActivityLock
        with WorldActivityLock(path):
            if path.exists():
                raise ValueError('world already exists; select it to resume')
            path.mkdir(mode=0o700)
            server = WorldServer(path/'transport/world.sock', path)
            server.close()
            return path

    def host(self, name):
        from .server import WorldServer
        if self.state is not None:
            raise ValueError('disconnect before changing worlds')
        path = self._world(name)
        if name in self._hosts:
            self.server, self.broker, self.sharing_pin = self._hosts.pop(name)
            self.state = path
            self.status = 'Hosting ' + name + ' (existing local world)'
            return
        from .world_library import WorldActivityLock
        with WorldActivityLock(path):
            if not any(item['path'] == str(path) for item in self.worlds()):
                raise ValueError('select an existing world')
            server = WorldServer(path/'transport/world.sock', path, persist_generated_cave=True, archive_generated_areas=True)
            try:
                server.start()
            except BaseException:
                server.close()
                raise
            self.server, self.state = server, path
            self.status = 'Hosting ' + name

    def join_local(self, name):
        from .launcher import admin
        if self.state is not None:
            raise ValueError('disconnect before changing worlds')
        path = self._world(name)
        if not any(item['path'] == str(path) for item in self.worlds()):
            raise ValueError('select an existing world')
        if not admin(path/'transport/world.sock', {'command': 'inspect'}).get('ok'):
            raise ValueError('world is not available')
        self.state = path
        self.status = 'Joined local world ' + name

    def local_profile(self, trainer, seed_save=None):
        if self.state is None or (self.broker is not None and self.server is None):
            raise ValueError('host or join a local world first')
        return prepare_profile(self.state, trainer, seed_save)

    def tls_material(self):
        import os
        import shutil
        if self.server is None:
            raise SessionError('Host a world in Play before sharing it.')
        directory = self.state/'tls'
        if directory.resolve() != directory:
            raise SessionError('TLS identity directory cannot be a symlink.')
        directory.mkdir(mode=0o700, exist_ok=True)
        directory.chmod(0o700)
        cert, key = directory/'certificate.pem', directory/'private-key.pem'
        if cert.is_symlink() or key.is_symlink():
            raise SessionError('TLS identity files cannot be symlinks.')
        if cert.exists() and key.exists():
            key.chmod(0o600)
            return cert, key
        if cert.exists() or key.exists():
            raise SessionError('Incomplete TLS identity. Select an explicit matching certificate and key in Settings.')
        if not shutil.which('openssl'):
            raise SessionError('OpenSSL is unavailable. Select an existing TLS certificate and key in Settings.')
        # Exclusively reserve the files before invoking openssl. Identity is
        # persistent and remains outside every native game mount.
        for path in (cert, key):
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            os.close(fd)
        try:
            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                            '-keyout', str(key), '-out', str(cert), '-days', '3650',
                            '-subj', '/CN=Emerald World'], check=True, timeout=20,
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError):
            cert.unlink(missing_ok=True)
            key.unlink(missing_ok=True)
            raise SessionError('Could not create a TLS identity. Select a certificate and key explicitly in Settings.') from None
        return cert, key

    def share(self, cert, key, listen=('127.0.0.1', 8765)):
        from .transport import HostBroker
        if self.server is None or self.broker is not None:
            raise ValueError('host a world before enabling TLS, and enable it only once')
        for material in (cert, key):
            if any(Path(material).resolve().is_relative_to(self.state/part)
                   for part in ('trainers', 'transport')):
                raise ValueError('TLS files must stay outside game-visible directories')
        import hashlib
        import ssl
        pin = hashlib.sha256(ssl.PEM_cert_to_DER_cert(Path(cert).read_text())).hexdigest()
        broker = HostBroker(self.state/'transport/world.sock', cert, key, listen)
        try:
            broker.start()
        except BaseException:
            broker.close()
            raise
        self.broker = broker
        self.sharing_pin = pin
        self.status = f'Hosting TLS at {broker.address[0]}:{broker.address[1]}'
        return broker.address

    def export_invitation(self, trainer, destination, advertised_address=None):
        """Export one friend file. Never guess a friend's address from loopback."""
        import ipaddress
        if self.server is None or self.broker is None or self.sharing_pin is None:
            raise SessionError('Enable secure sharing before exporting a friend invitation.')
        if advertised_address is None:
            host, port = self.broker.address
            try:
                address = ipaddress.ip_address(host)
                local = address.is_unspecified or address.is_loopback
            except ValueError:
                local = host.lower().rstrip('.') == 'localhost'
            if local:
                raise SessionError('Enter an explicit advertised address reachable by your friend.')
            advertised_address = (host, port)
        if type(advertised_address) not in (tuple, list) or len(advertised_address) != 2:
            raise SessionError('Enter an explicit advertised address and port.')
        connection = {'version': 1,
                      'endpoint': {'host': advertised_address[0], 'port': advertised_address[1]},
                      'pin': self.sharing_pin}
        from .transport import validate_invitation
        validate_invitation(dict(connection, trainer=trainer, token='0'*64))
        self.invite(trainer, destination, connection=connection)
        self.status = ('Friend invitation saved. Send it privately through a trusted channel. '
                       'Its bundled TLS pin is only trustworthy when received from you through that channel.')

    def invite(self, trainer, destination, *, connection=None):
        import os
        if self.server is None:
            raise ValueError('only the host can issue trainer credentials')
        # Validate paths before the identity service creates the directory.
        from .launcher import profile_paths
        profile_paths(self.state, trainer)
        destination = Path(destination).absolute()
        if destination.resolve().is_relative_to(self.state/'transport') or destination.resolve().is_relative_to(self.state/'trainers'):
            raise ValueError('keep invitations outside game-visible directories')
        if destination.exists() or destination.is_symlink():
            raise ValueError('refusing to replace an existing invitation')
        identity = self.server.create_identity(trainer)
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as output:
            json.dump(dict(connection or {}, trainer=trainer, token=identity['token']), output)
        self.status = 'Trainer invitation saved. Share it privately. Verify the TLS pin separately.'

    def connect_remote(self, name, invitation, remote, fingerprint):
        import os
        from .launcher import profile_paths
        from .transport import ClientBroker
        if self.state is not None:
            raise ValueError('disconnect before changing worlds')
        from .transport import read_invitation, validate_invitation
        identity = read_invitation(invitation)
        remembered = validate_invitation({'version': 1, 'trainer': identity['trainer'],
            'token': identity['token'], 'endpoint': {'host': remote[0], 'port': remote[1]},
            'pin': fingerprint})
        path = self._world(name)
        from .world_library import WorldActivityLock
        with WorldActivityLock(path):
            paths = profile_paths(path, identity['trainer'])
            if (path/'world.sqlite3').exists():
                raise ValueError('remote saves need a separate local world name')
            marker = path/'remote.json'
            binding = {'host': remote[0], 'port': remote[1], 'pin': fingerprint.lower()}
            if marker.is_symlink() or (marker.exists() and json.loads(marker.read_text()) != binding):
                raise ValueError('this save directory belongs to a different remote host')
            path.mkdir(mode=0o700, exist_ok=True)
            transport = path/'transport'
            if transport.resolve() != transport:
                raise ValueError('transport cannot be a symlink')
            from .launcher import ProfileLock
            with ProfileLock(path, identity['trainer']):
                broker = ClientBroker(transport/'world.sock', remote, fingerprint=fingerprint,
                                      handshake_timeout=3)
                try:
                    try:
                        broker.start()
                    except BlockingIOError:
                        raise SessionError('This connection is already owned by another launcher. '
                                           'Disconnect there or use Quit in that launcher, then retry. '
                                           'If it is an older launcher, close its process before retrying. '
                                           'Do not delete socket or lock files.') from None
                    # Control role checks credentials without occupying native presence.
                    from .client import IntentClient
                    with IntentClient(broker.socket_path, identity['trainer'], identity['token'], timeout=4):
                        pass
                    paths['profile'].parent.mkdir(mode=0o700, exist_ok=True)
                    paths['profile'].mkdir(mode=0o700, exist_ok=True)
                    config = (f'socket {transport}/world.sock\ntrainer {identity["trainer"]}\n'
                              f'token {identity["token"]}\ntelemetry {paths["telemetry"]}\n')
                    if paths['config'].exists() and paths['config'].read_text() != config:
                        raise ValueError('trainer profile belongs to a different invitation')
                    fd = os.open(paths['config'], os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
                    with os.fdopen(fd, 'w') as output:
                        output.write(config)
                    paths['config'].chmod(0o600)
                    if not paths['settings'].exists():
                        paths['settings'].write_text('[video]\nscale=2\n')
                    marker.write_text(json.dumps(binding))
                    from .friend_worlds import remember
                    remember(path, remembered)
                except BaseException:
                    broker.close()
                    raise
            self.state, self.broker = path, broker
            self.remote_trainer = identity['trainer']
            self.status = 'TLS verified. Trainer authenticated. Launch the native game to play.'
            return paths

    def start_display(self, display):
        from .launcher import ManagedDisplay
        if self.managed_display is not None:
            raise SessionError('This session already owns a game display. Disconnect before replacing it.')
        managed = ManagedDisplay(display)
        try:
            managed.start()
        except ValueError as exc:
            raise SessionError(str(exc)) from None
        self.managed_display = managed
        self.status = f'Game display {display} ready. Return to Play and launch your trainer.'
        return display

    def launch_offline(self, world, trainer, binary=REPO/'build/pokeemerald64', display=':93', copy_online=False, *, seed_save=None):
        from .offline import offline_profile
        state = self._world(world)
        # Snapshot preparation and native play acquire the same destination lock.
        # A competing start between them fails closed instead of sharing a save.
        try:
            with offline_profile(state, trainer, seed_save=seed_save, copy_online=copy_online) as paths:
                offline_paths = dict(paths)
        except ValueError as exc:
            raise SessionError(str(exc)) from None
        except OSError:
            raise SessionError('Offline copy could not be prepared. Stop its online game before copying and use Resume for an existing copy.') from None
        return self.launch(offline_paths, binary, display, _offline_state=state/'.offline')

    def launch(self, paths, binary=REPO/'build/pokeemerald64', display=':93', agent_control=False, *, _offline_state=None):
        from .launcher import ProfileLock, profile_paths
        state = _offline_state if _offline_state is not None else self.state
        if state is None:
            raise ValueError('connect to a world first')
        offline = _offline_state is not None
        if offline and (state.name != '.offline' or agent_control):
            raise ValueError('Choose a separate human offline profile.')
        trainer = paths['profile'].name
        if paths != profile_paths(state, trainer):
            raise ValueError('profile must belong to the selected world')
        if not offline and self.remote_trainer is not None and trainer != self.remote_trainer:
            raise SessionError('Trainer must match this session\'s assigned invitation.')
        key = 'offline/' + trainer if offline else trainer
        if key in self.games and self.games[key][0].poll() is None:
            raise ValueError('this trainer already has a running game')
        if key in self.game_locks:
            self.game_locks.pop(key).close()
        import os
        import shutil
        command = (game_command(binary, state, paths, display, online=False) if offline else
                   game_command(binary, state, paths, display, agent_control=True) if agent_control else
                   game_command(binary, state, paths, display))
        if not shutil.which('bwrap'):
            raise SessionError('Bubblewrap is required to isolate the native game.')
        if not Path(binary).is_file() or not os.access(binary, os.X_OK):
            raise SessionError('Native game binary is missing or not executable. Select a built game binary.')
        if display and not Path('/tmp/.X11-unix/X' + display[1:]).is_socket():
            raise SessionError('Dedicated Xephyr display is missing. Start Xephyr :93 or select an existing dedicated display.')
        if offline:
            from .offline import OfflineGameLock
            lock = OfflineGameLock(state.parent, trainer)
        else:
            lock = ProfileLock(state, trainer)
        try:
            if agent_control:
                from .launcher import check_player_endpoint
                check_player_endpoint(paths)
            logfile = paths['profile']/'native.log'
            if logfile.is_symlink():
                raise SessionError('Native log cannot be a symlink.')
            paths['telemetry'].unlink(missing_ok=True)
            # Validate the opened inode before truncation. A hardlinked log
            # must never erase a save, and a FIFO must not block the UI thread.
            import stat
            try:
                fd = os.open(logfile, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
            except OSError as exc:
                raise SessionError('Native log cannot be opened safely.') from exc
            with os.fdopen(fd, 'wb') as output:
                info = os.fstat(output.fileno())
                if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                        or info.st_uid != os.geteuid()):
                    raise SessionError('Native log must be an owned single-link regular file.')
                os.ftruncate(output.fileno(), 0)
                process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                           stdout=output, stderr=subprocess.STDOUT)
        except BaseException:
            lock.close()
            raise
        self.games[key] = (process, paths)
        self.game_locks[key] = lock
        self.agent_games.discard(key)
        if agent_control:
            self.agent_games.add(key)
        # Release even when no UI poll runs. The descriptor is CLOEXEC and is
        # never exposed inside the native sandbox, nor is its directory mounted.
        import threading
        def reap():
            process.wait()
            if process.poll() is not None:
                lock.close()
        try:
            threading.Thread(target=reap, name='native-profile-lock', daemon=True).start()
        except BaseException:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            lock.close()
            self.games.pop(key)
            self.game_locks.pop(key)
            raise
        self.status = (f'{trainer}: Offline play. This separate save never merges into online progress.' if offline else
                       f'{trainer}: AI-controlled trainer launched. Native control status appears below.' if agent_control
                       else f'{trainer} starting. Use the native game window to play.')
        return process

    def author_shared_cave(self, theme, *, wilds=False, guide=False, cast=False, xl=False, cohort='vanilla'):
        """Explicit local-host action; never display provider or credential text."""
        from .author_cave import MAX_THEME, author
        if cohort not in ('vanilla', 'expansion-native'):
            raise SessionError('Choose a supported species cohort.')
        if type(xl) is not bool or (xl and (not wilds or guide or cast)) or type(wilds) is not bool or type(guide) is not bool or type(cast) is not bool or ((guide or cast) and not wilds) or (guide and cast):
            raise SessionError('Choose a cave or outdoor area.')
        if type(theme) is not str or not theme.strip() or len(theme.encode('utf-8')) > MAX_THEME:
            raise SessionError('Enter an area description of at most 2,000 UTF-8 bytes.')
        server, state = self.server, self.state
        if server is None or state is None or getattr(server, '_closed', True) or (server.wilds_map if wilds else server.cave_map) is None:
            raise SessionError('Host a compatible local world before generating an area.')
        with server.lock:
            if any(peer.get('in_generated_cave') or
                   (peer.get('state') is not None and tuple(peer['state'][:2]) in (server.cave_map, server.wilds_map))
                   for peer in server.peers.values() if not peer.get('closing')):
                raise SessionError('Everyone must leave the active generated area before you generate another.')
        try:
            if xl:
                _, blob = author(theme, large=True, wilds=True, xl=True)
            elif cast:
                _, blob = author(theme, large=True, wilds=True, cast=True)
            elif guide:
                _, blob = author(theme, large=True, wilds=True, guide=True)
            elif wilds:
                _, blob = author(theme, large=True, wilds=True)
            else:
                _, blob = author(theme, large=True, custom_wildlife=True, cohort=cohort)
        except (OSError, ValueError, TypeError, TimeoutError, UnicodeError):
            raise SessionError('Area generation failed before publication. Check the supported model CLI version, login and configuration. A new attempt may incur another charge.') from None
        if self.server is not server or self.state != state or getattr(server, '_closed', True):
            raise SessionError('The hosted world changed during generation. Nothing was published to the new session.')
        try:
            label = ' '.join(''.join(' ' if ord(c) < 32 or ord(c) == 127 else c for c in theme).split())[:80]
            identity = server._replace_cave(blob, label=label or ('Outdoor area' if wilds else 'Cave'))
        except (OSError, ValueError):
            raise SessionError('The generated area could not be activated. Check that everyone has left the current area before trying again.') from None
        self.status = (('Generated outdoor area' if wilds else 'Generated cave') + ' installed for compatible players. ' +
                       ('It will persist when this world restarts.' if server.persist_generated_cave else
                        'It lasts for this host session unless persistence is enabled.'))
        return identity

    def list_generated_areas(self):
        if self.server is None or self.state is None:
            raise SessionError('Host a local world to view its saved generated areas.')
        try:
            return self.server.list_generated_areas()
        except (OSError, ValueError):
            raise SessionError('Saved generated areas are unavailable for this host.') from None

    def activate_generated_area(self, identity, *, expected_server=None, expected_state=None):
        if self.server is None or self.state is None:
            raise SessionError('Host a local world to select a generated area.')
        if expected_server is not None and (self.server is not expected_server or self.state != expected_state):
            raise SessionError('The hosted world changed. Refresh saved areas and choose again.')
        try:
            result = self.server.activate_generated_area(identity)
        except (OSError, ValueError):
            raise SessionError('Could not activate the area. Check that everyone has left and try again.') from None
        self.status = 'Saved generated area activated for compatible players.'
        return result

    def _gm_queue(self):
        from .runtime_gm import IntentQueue
        if self.server is None or self.state is None:
            raise ValueError('GM controls are available only in the hosting session')
        directory = self.state/'gm'
        if directory.resolve() != directory:
            raise ValueError('GM state cannot be a symlink')
        return IntentQueue(self.state)

    def start_gm(self):
        import threading
        from .runtime_gm import MODEL, RuntimeGM
        queue = self._gm_queue()
        queue.close()
        if self.gm_thread is not None and self.gm_thread.is_alive():
            raise ValueError('runtime GM is already running')
        self.gm_stop = threading.Event()
        ready = threading.Event()
        self.gm_error = None
        def work():
            try:
                with RuntimeGM(self.state, str(self.state/'transport/world.sock'), model=MODEL,
                               timeout=30, poll_interval=1) as runtime:
                    ready.set()
                    runtime.run(self.gm_stop)
            except Exception as exc:
                self.gm_error = type(exc).__name__
            finally:
                ready.set()
        self.gm_thread = threading.Thread(target=work, name='desktop-luna-gm', daemon=True)
        self.gm_thread.start()
        if not ready.wait(5) or self.gm_error:
            self.stop_gm()
            raise ValueError('runtime GM could not acquire its host authority')
        self.status = 'Luna developer GM enabled. Player intentions are optional.'

    def stop_gm(self):
        if self.gm_stop is not None:
            self.gm_stop.set()
        if self.gm_thread is not None:
            # Runtime's existing author lifecycle bounds each call to 30 seconds
            # and kills its owned author process group before returning.
            self.gm_thread.join()
        self.status = 'Luna developer GM stopped. Queued requests and outcomes are kept.'

    def _intent_client(self, trainer):
        from .client import IntentClient
        from .launcher import profile_paths
        if self.state is None:
            raise SessionError('Connect to a world before submitting an intention.')
        paths = profile_paths(self.state, trainer)
        if not paths['config'].exists() and (self.server is not None or self.broker is None):
            paths = self.local_profile(trainer)
        if paths['config'].stat().st_size > 4096:
            raise SessionError('Trainer connection configuration is invalid.')
        fields = dict(line.split(' ', 1) for line in paths['config'].read_text().splitlines())
        if (fields.get('trainer') != trainer or fields.get('socket') != str(self.state/'transport/world.sock')
                or not re.fullmatch(r'[0-9a-fA-F]{64}', fields.get('token', ''))):
            raise SessionError('Choose a trainer provisioned for this connection.')
        return IntentClient(fields['socket'], trainer, fields['token'], timeout=3)

    @staticmethod
    def _intent_result(result, identifier, trainer):
        request = result.get('request')
        if (result.get('ok') is not True or not isinstance(request, dict)
                or request.get('id') != identifier or request.get('player') != trainer
                or request.get('status') not in ('queued', 'running', 'succeeded', 'failed', 'interrupted')):
            raise SessionError('Host rejected the intention request. Check connection, text length and queue limits.')
        return request

    def submit_intent(self, trainer, text):
        with self._intent_client(trainer) as client:
            result = client.submit_intent(text)
            identifier = result.get('id')
            if not isinstance(identifier, str) or not re.fullmatch(r'net-[0-9a-f]{64}', identifier):
                raise SessionError('Host did not accept the intention. Check text length and queue limits.')
            # Verify the exact durable target over the authenticated control role.
            request = self._intent_result(client.intent_status(identifier), identifier, trainer)
        self.intents[identifier] = request
        self.status = f'Intention queued as {identifier}. The host controls the Luna worker.'
        return identifier

    def intent_status(self, identifier):
        previous = self.intents.get(identifier)
        if previous is None:
            raise SessionError('Select an intention submitted in this session.')
        trainer = previous['player']
        with self._intent_client(trainer) as client:
            request = self._intent_result(client.intent_status(identifier), identifier, trainer)
        self.intents[identifier] = request
        return request

    def refresh_intents(self):
        for identifier in list(self.intents)[-3:]:
            self.intent_status(identifier)

    def gm_status(self):
        if self.server is None:
            return {'remote': True, 'requests': list(self.intents.values())} if self.intents else {}
        if self.state is None or not (self.state/'gm/runtime.sqlite3').exists():
            return {}
        queue = self._gm_queue()
        try:
            return queue.status()
        finally:
            queue.close()

    def trainers(self):
        if self.state is None:
            return []
        directory = self.state/'trainers'
        return sorted(p.name for p in directory.iterdir()
                      if p.is_dir() and not p.is_symlink()
                      and re.fullmatch(r'[A-Za-z0-9_-]{1,24}', p.name)) if directory.is_dir() else []

    def connection_status(self):
        if self.state is None:
            return {'connected': False, 'players': []}
        try:
            if self.server is not None or self.broker is None:
                from .launcher import admin
                value = admin(self.state/'transport/world.sock', {'command': 'inspect'})
                return {'connected': value.get('ok') is True,
                        'players': [p['id'] for p in value.get('players', [])]}
            # Control role must never evict the native trainer presence.
            if self.remote_trainer is None:
                return {'connected': False, 'players': []}
            with self._intent_client(self.remote_trainer):
                pass
            return {'connected': True, 'players': [], 'remote': True}
        except (OSError, ValueError, ConnectionError):
            return {'connected': False, 'players': []}

    def poll(self):
        lines = [self.status]
        if self.hosted_worlds():
            lines.append('Local worlds owned by this launcher: ' + ', '.join(self.hosted_worlds()) + '. Disconnect does not shut them down.')
        if self.state is not None:
            connection = self.connection_status()
            if connection.get('remote'):
                lines.append('Remote TLS host reachable. Trainer authenticated. Player visibility appears in the native game.')
            elif connection['connected']:
                lines.append('Online trainers: ' + (', '.join(connection['players']) or 'none yet. Launch a trainer to enter.'))
            else:
                if self.remote_trainer is not None:
                    retry = ('Retry with Disconnect, then Connect remote TLS using the same invitation '
                             'and local world name. Do not host a replacement world.')
                elif self.server is None:
                    retry = ('Retry with Join local after the original host returns, '
                             'or keep the native field game open while it reconnects.')
                else:
                    retry = 'Retry with Disconnect, then Host selected for this same world.'
                lines.append('Host unavailable. Saves kept. ' + retry)
                lines.append('A world connection returning does not recover an interrupted native battle or trade.')
        gm = self.gm_status()
        if gm:
            if gm.get('remote'):
                lines.append('Intention status from the host:')
            else:
                runtime = gm.get('runtime') or {}
                lines.append('Luna GM: ' + str(runtime.get('state', 'not started')))
            for request in gm.get('requests', [])[-3:]:
                lines.append(f'Intent {request["id"][:12]}: {request["status"]}')
        if self.gm_error:
            lines.append('Luna GM stopped after a runtime error. Check configuration and retry explicitly.')
        for trainer, (process, paths) in self.games.items():
            code = process.poll()
            if code is not None:
                if trainer in self.game_locks:
                    self.game_locks[trainer].close()
                lines.append(f'{trainer} exited {code}. Save kept. Details: {paths["profile"]}/native.log')
                continue
            if trainer.startswith('offline/'):
                lines.append(f'{trainer[8:]}: offline. No world connection or multiplayer actions. Online progress is unchanged.')
                continue
            if trainer in self.agent_games:
                from .launcher import player_endpoint
                import os
                import shlex
                import stat
                import time
                try:
                    endpoint = player_endpoint(paths)
                    directory = paths['profile'].stat()
                    socket_info = endpoint.lstat()
                    if (directory.st_uid != os.geteuid() or directory.st_mode & 0o077
                            or not stat.S_ISSOCK(socket_info.st_mode)
                            or socket_info.st_uid != os.geteuid()
                            or socket_info.st_nlink != 1 or socket_info.st_mode & 0o077):
                        raise ValueError('unsafe player endpoint')
                    # Launch removes old telemetry before spawning this tracked
                    # child. Read only its fresh public file, never connect to
                    # the exclusive player socket, even when it appears idle.
                    telemetry = paths['telemetry']
                    if telemetry.resolve() != telemetry:
                        raise ValueError('telemetry cannot be a symlink')
                    fd = os.open(telemetry, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                    with os.fdopen(fd) as source:
                        info = os.fstat(source.fileno())
                        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                                or info.st_size > 65536
                                or not 0 <= time.time() - info.st_mtime <= 5):
                            raise ValueError('stale or invalid telemetry')
                        value = json.loads(source.read(65537))
                    if (not isinstance(value, dict) or value.get('trainer') != trainer
                            or type(value.get('connected')) is not bool
                            or type(value.get('ready')) is not bool
                            or type(value.get('revision')) is not int or value['revision'] < 0
                            or type(value.get('frame')) is not int or value['frame'] < 0):
                        raise ValueError('invalid native telemetry')
                    lines.append(f'{trainer}: AI control ready. Native endpoint available to its controller: {endpoint}')
                    lines.append('One controller only. Keep your existing SDK or MCP connection while attached.')
                    code = f'from world.player import PlayerClient; print(PlayerClient({str(endpoint)!r}).observe())'
                    lines.append('SDK: ' + shlex.join(['env', f'PYTHONPATH={REPO}', 'python3', '-c', code]))
                    lines.append('MCP: ' + shlex.join(['python3', str(REPO/'world/player_mcp.py'), '--endpoint', str(endpoint)]))
                except (OSError, ValueError):
                    lines.append(f'{trainer}: AI control starting. Waiting for fresh native telemetry and a private player endpoint.')
            try:
                import os
                import stat
                import time
                telemetry = paths['telemetry']
                fd = os.open(telemetry, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                with os.fdopen(fd) as source:
                    info = os.fstat(source.fileno())
                    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                            or info.st_size > 65536
                            or not 0 <= time.time() - info.st_mtime <= 5):
                        raise ValueError('stale or invalid native telemetry')
                    value = json.loads(source.read(65537))
                if (not isinstance(value, dict) or value.get('trainer') != trainer
                        or type(value.get('connected')) is not bool
                        or type(value.get('revision')) is not int or value['revision'] < 0
                        or type(value.get('frame')) is not int or value['frame'] < 0):
                    raise ValueError('invalid telemetry')
                lines.append(f'{trainer}: ' + ('connected' if value.get('connected') else 'connecting or disconnected')
                             + f', revision {value.get("revision", "?")}')
                peers = value.get('peers', [])
                roster = value.get('roster')
                if value['connected'] and isinstance(roster, list) and len(roster) <= 8:
                    public = []
                    for peer in roster:
                        if (not isinstance(peer, dict) or not isinstance(peer.get('trainer'), str)
                                or not re.fullmatch(r'[A-Za-z0-9_-]{1,24}', peer['trainer'])
                                or peer.get('nearby') is not True
                                or type(peer.get('ready')) is not bool
                                or type(peer.get('rendered')) is not bool):
                            continue
                        label = 'available' if peer['ready'] else 'busy, not inviteable'
                        if not peer['rendered']:
                            label += ', roster only (field sprite capacity)'
                        public.append(peer['trainer'] + ' (' + label + ')')
                    if public:
                        lines.append('Nearby world roster: ' + ', '.join(public))
                if isinstance(peers, list) and len(peers) <= 64:
                    nearby = sorted({p['trainer'] for p in peers if isinstance(p, dict)
                                     and isinstance(p.get('trainer'), str)
                                     and re.fullmatch(r'[A-Za-z0-9_-]{1,24}', p['trainer'])
                                     and p.get('visible') is True})
                    if value['connected'] and nearby:
                        lines.append('Nearby trainers: ' + ', '.join(nearby))
            except (OSError, ValueError):
                lines.append(f'{trainer}: starting, waiting for native connection state')
        return '\n'.join(lines)

    def hosted_worlds(self):
        names = set(self._hosts)
        if self.server is not None and self.state is not None:
            names.add(self.state.name)
        return sorted(names)

    def leave_game(self, trainer):
        """Leave only a child launched here; never another human's process."""
        if trainer not in self.games:
            raise SessionError('Choose a game launched by this launcher.')
        process, _ = self.games.pop(trainer)
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        lock = self.game_locks.pop(trainer, None)
        if lock is not None:
            lock.close()
        self.agent_games.discard(trainer)
        self.status = 'Left game. Save kept. The world is still running.'

    def shutdown_world(self, name):
        """Explicit LOCAL ownership operation. Never send remote shutdown."""
        if self.server is not None and self.state is not None and self.state.name == name:
            self.disconnect()
        owned = self._hosts.pop(name, None)
        if owned is None:
            raise SessionError('Only a local world hosted by this launcher can be shut down. Dedicated remote worlds are independent.')
        server, broker, _ = owned
        if broker is not None:
            broker.close()
        server.close()
        self.status = 'Local world shut down explicitly. Saves kept.'

    def disconnect(self):
        """Detach clients, preserving localhost hosting until explicit shutdown."""
        if self.server is not None and self.state is not None:
            self._hosts[self.state.name] = (self.server, self.broker, self.sharing_pin)
            self.server = self.broker = None
        self.stop_gm()
        for process, _ in self.games.values():
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        self.games.clear()
        self.agent_games.clear()
        for lock in self.game_locks.values():
            lock.close()
        self.game_locks.clear()
        if self.managed_display is not None:
            self.managed_display.close()
            self.managed_display = None
        self.intents.clear()
        if self.broker is not None:
            self.broker.close()
            self.broker = None
        self.state = None
        self.remote_trainer = None
        self.sharing_pin = None
        self.status = ('Disconnected. Saves kept. Local worlds still hosting: ' + ', '.join(self.hosted_worlds())
                       if self._hosts else 'Disconnected. Saves kept. Dedicated remote world unchanged.')

    def close(self):
        """Final owner teardown after explicit launcher-exit confirmation."""
        self.disconnect()
        for name in list(self._hosts):
            self.shutdown_world(name)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class DesktopApp:
    """Tk view with serialized background operations and native game windows."""
    def __init__(self, window, session, binary, display):
        import tkinter as tk
        from tkinter import ttk, filedialog
        from concurrent.futures import ThreadPoolExecutor
        self.window, self.session = window, session
        self.binary, self.display = binary, display
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='desktop-session')
        self.pending = None
        self.pending_kind = None
        self.poll_future = None
        self.next_poll = 0
        self.after_id = None
        self.closing = False
        self.remote_paths = None
        self.buttons = []
        self.inputs = []
        self.fields = {}
        self.generated_area_ids = {}
        self.generated_area_owner = None
        window.title('Emerald World')
        window.protocol('WM_DELETE_WINDOW', self.close)
        window.geometry('900x760')
        window.minsize(740, 560)
        from tkinter import font as tkfont
        family = tkfont.nametofont('TkDefaultFont').actual('family')
        style = ttk.Style(window)
        # Keep the desktop theme and its focus/disabled states. Only establish
        # typography and spacing, rather than painting over native controls.
        style.configure('Title.TLabel', font=(family, 20, 'bold'))
        style.configure('Section.TLabel', font=(family, 12, 'bold'))
        style.configure('TButton', padding=(12, 7))
        style.configure('TNotebook.Tab', padding=(12, 7))
        style.configure('Treeview', rowheight=28)
        frame = ttk.Frame(window, padding=18)
        frame.grid(sticky='nsew')
        window.columnconfigure(0, weight=1)
        window.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)
        self.root_label = tk.StringVar(value='Worlds folder: ' + str(session.root))
        ttk.Label(frame, text='Emerald World', style='Title.TLabel').grid(row=0, column=0, sticky='w')
        root_label = ttk.Label(frame, textvariable=self.root_label, wraplength=820)
        root_label.grid(row=1, column=0, sticky='w', pady=(4, 0))
        self.notebook = ttk.Notebook(frame)
        self.notebook.grid(row=2, column=0, sticky='nsew', pady=(16, 12))
        pages = {}
        self.page_canvases = {}
        canvas_for_page = {}
        self.page_notes = {}
        for title in ('Play', 'Connect friends', 'Optional GM', 'Settings', 'World library'):
            outer = ttk.Frame(self.notebook, padding=12)
            self.notebook.add(outer, text=title)
            outer.columnconfigure(0, weight=1)
            outer.rowconfigure(0, weight=1)
            canvas = tk.Canvas(outer, width=760, height=400, highlightthickness=0,
                               background=style.lookup('TFrame', 'background'))
            canvas.grid(row=0, column=0, sticky='nsew')
            scroll = ttk.Scrollbar(outer, orient='vertical', command=canvas.yview)
            scroll.grid(row=0, column=1, sticky='ns', padx=(8, 0))
            canvas.configure(yscrollcommand=scroll.set)
            page = ttk.Frame(canvas)
            page.columnconfigure(1, weight=1)
            content = canvas.create_window((0, 0), window=page, anchor='nw')
            page.bind('<Configure>', lambda event, c=canvas: c.configure(scrollregion=c.bbox('all')))
            canvas.bind('<Configure>', lambda event, c=canvas, item=content, p=page:
                        self._resize_page(event, c, item, p))
            pages[title] = page
            self.page_canvases[title] = canvas
            canvas_for_page[page] = canvas
            self.page_notes[page] = []
        self.play_canvas = self.page_canvases['Play']
        page, row = pages['Play'], 0
        def heading(text):
            nonlocal row
            ttk.Label(page, text=text, style='Section.TLabel').grid(
                row=row, column=0, columnspan=3, sticky='w', pady=(16 if row else 0, 6))
            row += 1
        def note(text):
            nonlocal row
            label = ttk.Label(page, text=text, wraplength=700, justify='left')
            label.grid(row=row, column=0, columnspan=3, sticky='ew', pady=(0, 10))
            self.page_notes[page].append(label)
            row += 1
        def field(key, label, value='', browse=False):
            nonlocal row
            ttk.Label(page, text=label).grid(row=row, column=0, sticky='w', padx=(0, 12))
            variable = tk.StringVar(value=value)
            self.fields[key] = variable
            state = 'readonly' if key in ('deleted_world', 'friend_world', 'generated_area') else 'normal'
            entry = (ttk.Combobox(page, textvariable=variable, width=30, state=state)
                     if key in ('world', 'trainer', 'deleted_world', 'friend_world', 'generated_area') else
                     ttk.Entry(page, textvariable=variable, width=30))
            entry.grid(row=row, column=1, sticky='ew', pady=5)
            self.inputs.append((entry, state))
            entry.bind('<FocusIn>', lambda event, c=canvas_for_page[page]: self._reveal_control(event, c))
            if browse:
                def choose():
                    selected = filedialog.askopenfilename(parent=window, initialdir=str(self.session.root))
                    if selected:
                        variable.set(selected)
                button = ttk.Button(page, text='Browse…', command=choose)
                button.grid(row=row, column=2, padx=(8, 0))
                self.buttons.append(button)
                button.bind('<FocusIn>', lambda event, c=canvas_for_page[page]: self._reveal_control(event, c))
            row += 1
            return entry
        def actions(items):
            nonlocal row
            bar = ttk.Frame(page)
            bar.grid(row=row, column=0, columnspan=3, sticky='w', pady=(6, 12))
            for index, (label, operation) in enumerate(items):
                button = ttk.Button(bar, text=label, command=lambda op=operation: self.submit(op))
                button.grid(row=index // 3, column=index % 3, sticky='w', padx=(0, 8), pady=3)
                self.buttons.append(button)
                button.bind('<FocusIn>', lambda event, c=canvas_for_page[page]: self._reveal_control(event, c))
            row += 1
        heading('1. Choose your world')
        note('Choose a saved world, or enter a new key and create one. Keys use letters, digits, _ or -. Rename worlds and manage saves in World library.')
        self.world_entry = field('world', 'World key')
        self.world_entry.bind('<<ComboboxSelected>>', self.show_world_details)
        actions([('Create world', self.create), ('Refresh worlds', self.refresh)])
        heading('2. Host or join')
        note('Host starts the selected world on this computer. Join local uses a world already hosted here. For a friend on another computer, open Connect friends. Disconnect before switching worlds.')
        actions([('Host selected', self.host), ('Join local', self.join_local)])
        heading('3. Play as your trainer')
        note('Choose a trainer to resume, or type a new name. Each human keeps their own team, bag and save.')
        self.trainer_entry = field('trainer', 'Human trainer', 'alice')
        actions([('Launch / resume trainer', self.launch), ('Leave game', self.leave_game), ('Disconnect', self.disconnect)])
        actions([('Shut down local world', self.shutdown_world)])
        note('Save in the native menu before leaving. Leave game stops only your selected game. Disconnect leaves local hosting running. Shut down local world is explicit and affects everyone connected here. Remote dedicated worlds are never owned or stopped by this launcher.')
        heading('Offline play')
        note('Offline play uses a separate save and never merges progress back. Choose a saved world and trainer above. Copying requires that trainer’s online game to be stopped. Resuming needs no host or invitation.')
        actions([('Play offline / resume copy', self.launch_offline), ('Copy online and play offline', self.copy_offline)])
        heading('AI-controlled trainer')
        note('An AI trainer is a separate player for Hermes or another external agent, not the optional Luna GM. No agent attaches to your human game. After launch, copy the verified endpoint and SDK command from connection details below. Remote AI players need their own trainer invitation and TLS connection.')
        field('ai_trainer', 'AI trainer name', 'hermes')
        actions([('Launch AI-controlled trainer', self.launch_ai)])

        page, row = pages['Connect friends'], 0
        heading('Join a friend')
        note('Get a private invitation from your host through a trusted channel. Only trust its bundled certificate pin when you trust that source. Import fills in connection details but does not connect.')
        actions([('Import friend invitation', self.import_friend_invitation)])
        note('For a legacy invitation, choose a separate local world key in Play and enter the host address and trusted pin below. After connecting, return to Play and launch your assigned trainer.')
        field('remote', 'Host address (HOST:PORT)', '127.0.0.1:8765')
        field('pin', 'Trusted SHA256 certificate pin')
        field('invitation', 'Private trainer invitation', browse=True)
        actions([('Connect remote TLS', self.connect)])
        heading('Rejoin a saved friend')
        note('Successful connections are remembered privately here. Rejoin uses the same trusted certificate and trainer. Forget removes only the saved connection, not your progress.')
        self.friend_entry = field('friend_world', 'Saved friend world')
        self.friend_hint = tk.StringVar()
        hint = ttk.Label(page, textvariable=self.friend_hint, wraplength=700)
        hint.grid(row=row, column=0, columnspan=3, sticky='ew', pady=(0, 6))
        self.page_notes[page].append(hint)
        row += 1
        actions([('Rejoin saved friend', self.rejoin_friend), ('Forget saved friend', self.forget_friend)])
        heading('Invite someone to your world')
        note('First host a world in Play, then enable secure sharing. Export one private invitation per friend and send it through a trusted channel. Its bundled TLS pin is trustworthy only when received from you through that channel.')
        note('For wildcard or local listeners, enter an explicit advertised address reachable by your friend. No relay is provided.')
        field('listen', 'Listen address', '127.0.0.1:8765')
        field('advertised', 'Advertised address (HOST:PORT)')
        field('invite_trainer', 'Friend trainer name', 'bob')
        actions([('Enable secure sharing', self.share), ('Save trainer invitation', self.invite)])

        page, row = pages['Optional GM'], 0
        heading('Optional Luna GM')
        note('The adventure and multiplayer work without enabling the GM. Only the host can start Luna. Model: openai-codex/gpt-6-luna.')
        actions([('Start Luna GM (host)', self.start_gm), ('Stop GM (host)', self.stop_gm)])
        field('intent', 'Player intention (optional)')
        actions([('Submit intention', self.submit_intent), ('Refresh intent status', self.refresh_intents)])
        heading('Generate a shared area')
        note('Host a local world, then describe a 63×63 cave or outdoor area. Generating sends your description to the configured model provider and may incur charges. It replaces the current generated area only when everyone has left and persists across local host restarts. Compatible experimental clients are required.')
        field('cave_theme', 'Area description')
        actions([('Generate shared cave', self.generate_cave), ('Generate Expansion species cave', self.generate_expansion_cave), ('Generate shared wilds', self.generate_wilds), ('Wilds with guide', self.generate_guided_wilds), ('Wilds with cast', self.generate_cast_wilds)])
        note('Generated areas and the first 80 characters of their description are saved in this local world. Refresh the list to revisit one; everyone must leave the current generated area before switching.')
        self.generated_area_entry = field('generated_area', 'Saved generated area')
        actions([('Refresh saved areas', self.refresh_generated_areas), ('Activate saved area', self.activate_generated_area)])
        page, row = pages['Settings'], 0
        heading('Game display')
        note('A dedicated nested Xephyr display keeps the native game away from your desktop X socket. Start a new display here, or explicitly select an existing dedicated display. Existing displays are never stopped by this launcher.')
        field('display', 'Dedicated game display', display or '')
        actions([('Start dedicated game display', self.start_display)])
        heading('Files and saves')
        field('binary', 'Native game binary', str(binary), browse=True)
        field('seed', 'Seed save for NEW trainer', browse=True)
        note('Seed saves are optional. They are copied only when explicitly selected and never overwrite an existing trainer. Leave blank to start a new adventure or resume. Your personal HOME is never mounted into the native game.')
        actions([('Choose worlds folder', self.choose_root)])
        heading('TLS files (optional)')
        note('Leave both blank to use the host’s generated TLS material, or select an existing certificate and its matching private key.')
        field('cert', 'Existing TLS certificate', browse=True)
        field('key', 'Matching TLS private key', browse=True)

        page, row = pages['World library'], 0
        heading('Your saved worlds')
        note('Up to 32 worlds. Select a row to use that world in Play. Display names and tags never change save paths. Disconnect before hosting a different world.')
        library = ttk.Frame(page)
        library.grid(row=row, column=0, columnspan=3, sticky='ew')
        library.columnconfigure(0, weight=1)
        self.library_tree = ttk.Treeview(library, columns=('tags', 'trainers'), height=5, selectmode='browse')
        self.library_tree.heading('#0', text='Display name (world key)')
        self.library_tree.heading('tags', text='Tags')
        self.library_tree.heading('trainers', text='Trainers')
        self.library_tree.column('#0', width=260, minwidth=160)
        self.library_tree.column('tags', width=140, minwidth=80)
        self.library_tree.column('trainers', width=160, minwidth=100)
        self.library_tree.grid(row=0, column=0, sticky='ew')
        scroll = ttk.Scrollbar(library, orient='vertical', command=self.library_tree.yview)
        scroll.grid(row=0, column=1, sticky='ns')
        self.library_tree.configure(yscrollcommand=scroll.set)
        self.library_tree.bind('<<TreeviewSelect>>', self.select_library_world)
        row += 1
        self.library_details = tk.StringVar(value='Choose a world to see its details.')
        details = ttk.Label(page, textvariable=self.library_details, wraplength=700, justify='left')
        details.grid(row=row, column=0, columnspan=3, sticky='ew', pady=(10, 4))
        self.page_notes[page].append(details)
        row += 1
        field('world_label', 'Display name')
        field('world_tags', 'Tags (comma separated)')
        actions([('Rename / save tags', self.rename_selected_world), ('Refresh worlds', self.refresh)])
        heading('Deleted worlds')
        note('Move the selected world and all its trainer saves to Deleted. You can restore it later. Stop its hosts, games and GM workers first.')
        actions([('Move to Deleted', self.delete_selected_world)])
        self.deleted_entry = field('deleted_world', 'Deleted world to restore')
        actions([('Restore deleted world', self.restore_selected_world)])
        self.message = tk.StringVar(value=session.status)
        from .host_controls import HostControlsPanel
        self.host_controls = HostControlsPanel(self)
        self.activity = tk.StringVar(value='Connection and activity')
        status_header = ttk.Frame(frame)
        status_header.grid(row=3, column=0, sticky='ew')
        status_header.columnconfigure(0, weight=1)
        ttk.Label(status_header, textvariable=self.activity, style='Section.TLabel').grid(row=0, column=0, sticky='w')
        self.progress = ttk.Progressbar(status_header, mode='indeterminate', length=100)
        self.progress.grid(row=0, column=1, sticky='e')
        status = ttk.Frame(frame)
        status.grid(row=4, column=0, sticky='ew', pady=(8, 0))
        status.columnconfigure(0, weight=1)
        self.status_text = tk.Text(status, height=5, width=1, wrap='word',
                                   font='TkDefaultFont', relief='flat', padx=10, pady=8,
                                   background=style.lookup('TEntry', 'fieldbackground') or 'white',
                                   foreground=style.lookup('TLabel', 'foreground') or 'black')
        self.status_text.grid(row=0, column=0, sticky='ew')
        status_scroll = ttk.Scrollbar(status, orient='vertical', command=self.status_text.yview)
        status_scroll.grid(row=0, column=1, sticky='ns')
        self.status_text.configure(yscrollcommand=status_scroll.set)
        self.last_status = None
        self.message.trace_add('write', self._render_status)
        self._render_status()
        frame.bind('<Configure>', lambda event: root_label.configure(wraplength=max(200, event.width - 36)))
        self.refresh()
        self.after_id = window.after(150, self.tick)
        window.bind('<Destroy>', self.destroyed, add='+')
        for event in ('<Button-4>', '<Button-5>', '<MouseWheel>'):
            window.bind(event, self._scroll_page, add='+')

    def _scroll_page(self, event):
        # Bind only to this launcher. Selectors and the status box retain their
        # own scrolling instead of also moving the containing page.
        widget = event.widget
        if widget.winfo_class() in ('TCombobox', 'Treeview', 'Text', 'TScrollbar'):
            return
        while widget is not None:
            if widget in self.page_canvases.values():
                direction = -1 if event.num == 4 or event.delta > 0 else 1
                widget.yview_scroll(direction * 3, 'units')
                return 'break'
            widget = getattr(widget, 'master', None)

    def _reveal_control(self, event, canvas):
        bounds = canvas.bbox('all')
        if not bounds:
            return
        top = event.widget.winfo_rooty() - canvas.winfo_rooty()
        bottom = top + event.widget.winfo_height()
        offset = top if top < 0 else max(0, bottom - canvas.winfo_height())
        if offset:
            canvas.yview_moveto((canvas.canvasy(0) + offset) / max(1, bounds[3]))

    def _resize_page(self, event, canvas, content, page):
        canvas.itemconfigure(content, width=event.width)
        for label in self.page_notes[page]:
            label.configure(wraplength=max(200, event.width - 20))

    def _render_status(self, *args):
        text = self.message.get()
        if text == self.last_status:
            return
        self.last_status = text
        self.status_text.configure(state='normal')
        self.status_text.delete('1.0', 'end')
        self.status_text.insert('1.0', text)
        self.status_text.configure(state='disabled')

    def destroyed(self, event):
        if event.widget is self.window and self.after_id is not None:
            self.window.after_cancel(self.after_id)
            self.after_id = None

    def generate_cave(self):
        # submit() collects values and performs the confirmation on the UI thread.
        pass

    def generate_expansion_cave(self):
        # submit() collects values and performs the confirmation on the UI thread.
        pass

    def generate_wilds(self):
        # submit() owns the confirmation and background operation.
        pass

    def generate_guided_wilds(self):
        # submit() owns the confirmation and background operation.
        pass

    def generate_cast_wilds(self):
        # submit() owns the confirmation and background operation.
        pass

    def refresh_generated_areas(self):
        # submit() runs the database read on the session executor.
        pass

    def activate_generated_area(self):
        # submit() asks for confirmation and runs the authority operation.
        pass

    def start_gm(self):
        self.session.start_gm()

    def stop_gm(self):
        self.session.stop_gm()

    def submit_intent(self):
        value = self.values()
        self.session.submit_intent(value['trainer'], value['intent'])
        self.fields['intent'].set('')

    def refresh_intents(self):
        self.session.refresh_intents()

    def choose_root(self):
        if self.session.state is not None or self.session.hosted_worlds():
            raise SessionError('Disconnect and explicitly shut down local hosted worlds before choosing a different worlds root.')
        from tkinter import filedialog
        selected = filedialog.askdirectory(parent=self.window, initialdir=str(self.session.root), mustexist=False)
        if selected:
            replacement = DesktopSession(DesktopSession.create_root(Path(selected)))
            self.session.close()
            self.session = replacement
            self.remote_paths = None
            self.fields['world'].set('')
            self.root_label.set('Worlds folder: ' + str(replacement.root))
            self.refresh()

    def values(self):
        return {key: value.get().strip() for key, value in self.fields.items()}

    def refresh(self):
        if hasattr(self, 'friend_entry'):
            friends = [item['name'] for item in self.session.friend_worlds()]
            self.friend_entry['values'] = friends
            if hasattr(self, 'friend_hint'):
                self.friend_hint.set('' if friends else
                    'No saved friend connections yet. Use Import friend invitation above to get started.')
            if self.fields['friend_world'].get() not in friends:
                self.fields['friend_world'].set(friends[0] if friends else '')
        names = [item['name'] for item in self.session.worlds()]
        self.world_entry['values'] = names
        if names and not self.fields['world'].get():
            self.fields['world'].set(names[0])
        if hasattr(self, 'library_tree'):
            self.library_cards = self.session.world_library()
            for item in self.library_tree.get_children():
                self.library_tree.delete(item)
            for card in self.library_cards:
                self.library_tree.insert('', 'end', iid=card['key'],
                    text=f'{card["display_name"]} ({card["key"]})',
                    values=(', '.join(card['tags']), ', '.join(t['name'] for t in card['trainers']) or 'none yet'))
            self.deleted_entry['values'] = [item['token'] for item in self.session.deleted_worlds()]
            self.show_world_details()
        if hasattr(self, 'trainer_entry'):
            self.trainer_entry['values'] = self.session.trainers()

    def delete_selected_world(self):
        from tkinter import messagebox
        key = self.values()['world']
        # Capture identity before either modal prompt. Neither default is Yes.
        if not messagebox.askyesno('Move world to Deleted?',
                f'Move world {key} and every trainer save to Deleted? It can be restored.',
                parent=self.window, default='no'):
            return
        if not messagebox.askyesno('Confirm recoverable deletion',
                f'Confirm moving the entire world {key}. Stop all hosts, games and GM workers first.',
                parent=self.window, default='no'):
            return
        self.session.delete_world(key)
        self.refresh()

    def rename_selected_world(self):
        value = self.values()
        self.session.rename_world(value['world'], value['world_label'],
                                  [t.strip() for t in value['world_tags'].split(',') if t.strip()])
        self.refresh()

    def restore_selected_world(self):
        token = self.values()['deleted_world']
        path = self.session.restore_world(token)
        self.fields['world'].set(path.name)
        self.refresh()

    def select_library_world(self, event=None):
        if self.pending is not None or self.closing:
            return
        selected = self.library_tree.selection()
        if selected:
            self.fields['world'].set(selected[0])
        self.show_world_details()

    def show_world_details(self, event=None):
        if not hasattr(self, 'library_details'):
            return
        key = self.fields['world'].get().strip()
        card = next((item for item in self.library_cards if item['key'] == key), None)
        if card is None:
            self.library_details.set(
                'No saved worlds yet. In Play, enter a world key and choose Create world.'
                if not self.library_cards else
                'Select a saved world to see its details. Create a new world from Play.')
            return
        self.fields['world_label'].set(card['display_name'])
        self.fields['world_tags'].set(', '.join(card['tags']))
        lines = [card['display_name'] + ' | Stable key: ' + key,
                 'Tags: ' + (', '.join(card['tags']) or 'none')]
        if not card['trainers']:
            lines.append('No trainer profiles yet. Party, badges and play time unavailable.')
        for trainer in card['trainers']:
            lines.append(f'Trainer {trainer["name"]} | Save file modified: {trainer["saved_at"]}')
            lines.append(f'Party: {trainer["party"]} | Badges: {trainer["badges"]} | Play time: {trainer["playtime"]}')
        self.library_details.set('\n'.join(lines))

    def create(self):
        self.session.create_world(self.values()['world'])
        self.session.status = 'World created. Select Host to start it.'
        self.refresh()

    def host(self):
        self.session.host(self.values()['world'])

    def join_local(self):
        self.session.join_local(self.values()['world'])

    def start_display(self):
        self.session.start_display(self.values()['display'])

    def launch(self):
        value = self.values()
        self._launch(value, self.remote_paths)
        self.refresh()

    def _launch(self, value, remote_paths):
        if 'world' in value and self.session.state != self.session._world(value['world']):
            raise SessionError('Disconnect and host or join the selected world before launching its trainer.')
        paths = remote_paths or self.session.local_profile(value['trainer'], value['seed'] or None)
        display = value.get('display') or None
        if display and not Path('/tmp/.X11-unix/X' + display[1:]).is_socket():
            self.session.start_display(display)
        self.session.launch(paths, Path(value.get('binary') or self.binary), display)

    def launch_offline(self):
        self._launch_offline(self.values(), False)

    def copy_offline(self):
        self._launch_offline(self.values(), True)

    def _launch_offline(self, value, copy_online):
        display = value.get('display') or None
        if display and not Path('/tmp/.X11-unix/X' + display[1:]).is_socket():
            self.session.start_display(display)
        return self.session.launch_offline(value['world'], value['trainer'],
                                           Path(value.get('binary') or self.binary), display, copy_online)

    def launch_ai(self):
        self._launch_ai(self.values(), self.remote_paths)
        self.refresh()

    def _launch_ai(self, value, remote_paths):
        if 'world' in value and self.session.state != self.session._world(value['world']):
            raise SessionError('Disconnect and host or join the selected world before launching its trainer.')
        trainer = value['ai_trainer']
        if remote_paths:
            if trainer != remote_paths['profile'].name:
                raise SessionError('AI trainer must match its assigned invitation. Connect with a distinct AI invitation.')
            paths = remote_paths
        else:
            if trainer == value['trainer']:
                raise SessionError('Choose a distinct AI trainer name, different from the Human trainer.')
            paths = self.session.local_profile(trainer, value['seed'] or None)
        display = value.get('display') or None
        if display and not Path('/tmp/.X11-unix/X' + display[1:]).is_socket():
            self.session.start_display(display)
        self.session.launch(paths, Path(value.get('binary') or self.binary), display, agent_control=True)

    def disconnect(self):
        self.session.disconnect()
        self.remote_paths = None

    def leave_game(self):
        self.session.leave_game(self.values()['trainer'])

    def shutdown_world(self):
        from tkinter import messagebox
        name = self.values()['world']
        if name not in self.session.hosted_worlds():
            raise SessionError('This launcher does not own that local world. Remote dedicated worlds cannot be shut down here.')
        if messagebox.askyesno('Shut down local world?',
                f'Shut down {name} for everyone connected? Save your game first.',
                parent=self.window, default='no'):
            self.session.shutdown_world(name)
            self.remote_paths = None

    def rejoin_friend(self):
        name = self.values()['friend_world']
        self.remote_paths = self.session.rejoin_friend(name)
        self.fields['world'].set(name)
        self.fields['trainer'].set(self.remote_paths['profile'].name)
        self.refresh()

    def forget_friend(self):
        from tkinter import messagebox
        name = self.values()['friend_world']
        if not name:
            raise SessionError('Choose a saved friend world.')
        if messagebox.askyesno('Forget friend connection?',
                f'Forget the saved connection for {name}? Your trainer progress will stay on disk.',
                parent=self.window, default='no'):
            self.session.forget_friend(name)
            self.refresh()

    def import_friend_invitation(self, path=None):
        from .transport import read_invitation
        if self.session.state is not None:
            raise SessionError('Disconnect before importing a different world invitation.')
        if path is None:
            from tkinter import filedialog
            path = filedialog.askopenfilename(parent=self.window, title='Import friend invitation')
        if not path:
            return
        try:
            identity = read_invitation(path)
        except (OSError, ValueError):
            raise SessionError('Invalid friend invitation. No connection settings were changed.') from None
        if 'version' in identity:
            import hashlib
            endpoint = identity['endpoint']
            host = endpoint['host']
            address = f'[{host}]:{endpoint["port"]}' if ':' in host else f'{host}:{endpoint["port"]}'
            binding = json.dumps([host, endpoint['port'], identity['pin'].lower()]).encode()
            self.fields['world'].set('remote-' + hashlib.sha256(binding).hexdigest()[:16])
            self.fields['remote'].set(address)
            self.fields['pin'].set(identity['pin'])
        self.fields['trainer'].set(identity['trainer'])
        self.fields['invitation'].set(str(path))
        self.notebook.select(1)
        self.session.status = ('Invitation imported. Only trust it when received privately from your host. '
                               'Select Connect remote TLS, then launch your trainer in Play.')
        self.message.set(self.session.status)

    def share(self):
        self.fields['pin'].set(self._share(self.values()))

    def _share(self, value):
        import hashlib
        import ssl
        from .transport import _endpoint
        cert, key = (Path(value['cert']), Path(value['key'])) if value['cert'] and value['key'] else self.session.tls_material()
        address = self.session.share(cert, key, _endpoint(value['listen']))
        pin = hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert.read_text())).hexdigest()
        self.session.status = f'TLS listening at {address[0]}:{address[1]}\nCertificate pin: {pin}'
        return pin

    def invite(self):
        from tkinter import filedialog
        destination = filedialog.asksaveasfilename(parent=self.window, initialdir=str(self.session.root),
                                                 title='Save private trainer invitation', defaultextension='.json')
        if destination:
            from .transport import _endpoint
            value = self.values()
            address = _endpoint(value['advertised']) if value['advertised'] else None
            self.session.export_invitation(value['invite_trainer'], destination, address)

    def connect(self):
        from .transport import _endpoint
        value = self.values()
        self.remote_paths = self.session.connect_remote(value['world'], value['invitation'],
                                                        _endpoint(value['remote']), value['pin'])
        self.fields['trainer'].set(self.remote_paths['profile'].name)

    def _set_busy(self, busy):
        """Lock editable presentation state while a submitted operation is pending."""
        for button in self.buttons:
            button.state(['disabled'] if busy else ['!disabled'])
        for control, idle_state in getattr(self, 'inputs', []):
            control.configure(state='disabled' if busy else idle_state)
        if hasattr(self, 'activity'):
            self.activity.set('Working. Please wait…' if busy else 'Connection and activity')
            if busy:
                self.progress.start()
            else:
                self.progress.stop()

    def submit(self, operation):
        if self.pending is not None or self.closing:
            return
        # Tk reads and file dialogs stay on the UI thread. Network and bounded
        # author cleanup run in a serialized worker so the window stays live.
        if operation in (self.start_display, self.launch, self.launch_ai, self.launch_offline, self.copy_offline, self.share):
            value = self.values()
            self.pending_kind = operation.__name__
            if operation == self.start_display:
                self.pending = self.executor.submit(self.session.start_display, value['display'])
            elif operation == self.launch:
                self.pending = self.executor.submit(self._launch, value, self.remote_paths)
            elif operation == self.launch_ai:
                self.pending = self.executor.submit(self._launch_ai, value, self.remote_paths)
            elif operation in (self.launch_offline, self.copy_offline):
                self.pending = self.executor.submit(self._launch_offline, value, operation == self.copy_offline)
            else:
                self.pending = self.executor.submit(self._share, value)
            self.message.set('Starting session operation. The window remains available...')
            self._set_busy(True)
            return
        if operation in (self.generate_cave, self.generate_expansion_cave, self.generate_wilds, self.generate_guided_wilds, self.generate_cast_wilds):
            from tkinter import messagebox
            value = self.values()
            theme = value['cave_theme']
            expansion_species = operation == self.generate_expansion_cave
            cast = operation == self.generate_cast_wilds
            guide = operation == self.generate_guided_wilds
            wilds = operation in (self.generate_wilds, self.generate_guided_wilds, self.generate_cast_wilds)
            if not theme or len(theme.encode('utf-8')) > 2000:
                self.message.set('Enter a cave description of at most 2,000 UTF-8 bytes.')
                return
            if self.session.server is None or self.session.state is None:
                self.message.set('Host a compatible local world before generating a cave.')
                return
            if not messagebox.askyesno('Generate shared wilds?' if wilds else 'Generate a shared cave?',
                    'This sends your area description to the configured model provider and may incur charges. The current generated area will be replaced if it is unoccupied. Continue?',
                    parent=self.window, default='no'):
                return
            self.pending_kind = 'author_cave'
            if expansion_species:
                self.pending = self.executor.submit(self.session.author_shared_cave, theme, cohort='expansion-native')
            elif cast:
                self.pending = self.executor.submit(self.session.author_shared_cave, theme, wilds=True, cast=True)
            elif guide:
                self.pending = self.executor.submit(self.session.author_shared_cave, theme, wilds=True, guide=True)
            elif wilds:
                self.pending = self.executor.submit(self.session.author_shared_cave, theme, wilds=True)
            else:
                self.pending = self.executor.submit(self.session.author_shared_cave, theme)
            self.message.set('Generating a shared area. The window remains available...')
            self._set_busy(True)
            return
        if operation == self.refresh_generated_areas:
            self.generated_area_owner = (self.session.server, self.session.state)
            self.pending_kind = 'list_generated_areas'
            self.pending = self.executor.submit(self.session.list_generated_areas)
            self.message.set('Loading saved generated areas...')
            self._set_busy(True)
            return
        if operation == self.activate_generated_area:
            from tkinter import messagebox
            selection = self.values()['generated_area']
            identity = self.generated_area_ids.get(selection)
            if (not identity or self.generated_area_owner != (self.session.server, self.session.state)
             or self.session.server is None):
                self.message.set('Refresh saved areas for the current host, then choose one.')
                return
            if not messagebox.askyesno('Activate this generated area?',
                    'This replaces the current generated area. Everyone must leave it first. Continue?',
                    parent=self.window, default='no'):
                return
            self.pending_kind = 'activate_generated_area'
            self.pending = self.executor.submit(self.session.activate_generated_area, identity,
                                                expected_server=self.generated_area_owner[0], expected_state=self.generated_area_owner[1])
            self.message.set('Activating saved area...')
            self._set_busy(True)
            return
        if operation == self.submit_intent:
            value = self.values()
            self.pending_kind = 'intent'
            self.pending = self.executor.submit(self.session.submit_intent, value['trainer'], value['intent'])
            self.message.set('Sending intention over the authenticated world connection...')
            self._set_busy(True)
            return
        if operation == self.leave_game:
            trainer = self.values()['trainer']
            self.pending_kind = 'leave_game'
            self.pending = self.executor.submit(self.session.leave_game, trainer)
            self.message.set('Leaving the selected game. The world remains running...')
            self._set_busy(True)
            return
        if operation in (self.start_gm, self.stop_gm, self.disconnect, self.refresh_intents):
            self.pending_kind = operation.__name__
            self.pending = self.executor.submit(operation)
            self.message.set('Updating session. Waiting for owned work to finish...')
            self._set_busy(True)
            return
        if operation == self.rejoin_friend:
            name = self.values()['friend_world']
            if not name:
                self.message.set('Choose a saved friend world.')
                return
            self.pending_kind = 'rejoin_friend'
            self.pending = self.executor.submit(self.session.rejoin_friend, name)
            self.message.set('Rejoining saved friend world and verifying TLS pin...')
            self._set_busy(True)
            return
        if operation == self.connect:
            from .transport import _endpoint
            value = self.values()
            try:
                endpoint = _endpoint(value['remote'])
            except (ValueError, argparse.ArgumentTypeError):
                self.message.set('Error: use HOST:PORT for the remote address.')
                return
            self.pending_kind = 'connect'
            self.pending = self.executor.submit(self.session.connect_remote, value['world'],
                                                value['invitation'], endpoint, value['pin'])
            self.message.set('Connecting and verifying TLS pin...')
            self._set_busy(True)
            return
        try:
            operation()
            self.message.set(self.session.status)
            self.next_poll = 0
        except SessionError as exc:
            self.session.status = str(exc)
            self.message.set(self.session.status)
        except Exception:
            # Fixed guidance never displays credential-bearing provider text.
            guidance = {
                'create': 'Enter a new world name using letters, digits, _ or -. Existing worlds can be selected and hosted.',
                'host': 'Choose an existing world to host. If it is already hosted, use Join local. Disconnect before switching worlds.',
                'join_local': 'Choose a world already hosted on this computer. Otherwise use Host selected first.',
                'launch': 'Connect to a world first. Choose a trainer name and a built binary in Settings. Clear the seed field when resuming an existing save.',
                'share': 'Host a world first. Check the listen address and port. Existing certificate and key must match and stay outside game-visible folders.',
                'invite': 'Host a world first and choose a new private invitation file. Trainer names use letters, digits, _ or -.',
            }
            self.session.status = 'Could not complete this step. ' + guidance.get(operation.__name__, 'Check selection, files and connection, then retry.')
            self.message.set(self.session.status)

    def tick(self):
        self.after_id = None
        if self.pending is not None and self.pending.done():
            kind = self.pending_kind
            try:
                result = self.pending.result()
                if kind in ('connect', 'rejoin_friend'):
                    self.remote_paths = result
                    self.fields['trainer'].set(self.remote_paths['profile'].name)
                    if kind == 'rejoin_friend':
                        self.fields['world'].set(self.remote_paths['profile'].parent.parent.name)
                    self.refresh()
                elif kind == 'intent':
                    self.fields['intent'].set('')
                elif kind == 'author_cave':
                    self.fields['cave_theme'].set('')
                elif kind == 'list_generated_areas':
                    if self.generated_area_owner != (self.session.server, self.session.state):
                        result = []
                    self.generated_area_ids = {item['label'] + ' [' + item['identity'] + ']': item['identity'] for item in result}
                    choices = list(self.generated_area_ids)
                    self.generated_area_entry['values'] = choices
                    active = next((item['label'] + ' [' + item['identity'] + ']' for item in result if item['active']), '')
                    self.fields['generated_area'].set(active if active in self.generated_area_ids else choices[0] if choices else '')
                    self.session.status = 'Saved generated areas loaded.' if choices else 'No saved generated areas yet.'
                elif kind == 'share':
                    self.fields['pin'].set(result)
                elif kind in ('launch', 'launch_ai'):
                    self.refresh()
            except SessionError as exc:
                self.session.status = str(exc)
            except Exception:
                self.session.status = ('Error: remote connection failed. Check host, port, invitation and trusted pin.'
                                       if kind in ('connect', 'rejoin_friend') else 'Error: session operation failed. Check host authority and runtime configuration.')
            self.pending = None
            self.pending_kind = None
            self.message.set(self.session.status)
            self.next_poll = 0
            if kind == 'close':
                self.executor.shutdown(wait=True)
                self.window.destroy()
                return
            self._set_busy(self.closing)
        if self.closing and self.pending is None:
            self.pending_kind = 'close'
            self.pending = self.executor.submit(self.session.close)
        if self.poll_future is not None and self.poll_future.done():
            try:
                status = self.poll_future.result()
                if self.pending is None and not self.closing:
                    self.message.set(status)
            except Exception:
                if self.pending is None:
                    self.message.set('Connection status unavailable. Saves kept. Disconnect and retry the selected world.')
            self.poll_future = None
        import time
        if self.pending is None and self.poll_future is None and not self.closing and time.monotonic() >= self.next_poll:
            self.poll_future = self.executor.submit(self.session.poll)
            self.next_poll = time.monotonic() + 1
        self.after_id = self.window.after(150, self.tick)

    def close(self):
        from tkinter import messagebox
        if self.pending is not None:
            self.message.set('Wait for the current session operation, then close again to review local world shutdown.')
            return
        owned = self.session.hosted_worlds()
        if owned and not messagebox.askyesno('Exit and shut down local worlds?',
                'This launcher hosts ' + ', '.join(owned) + '. Exiting shuts these local worlds down for everyone. Disconnect instead to keep them running. Exit and shut down?',
                parent=self.window, default='no'):
            return
        self.closing = True
        self._set_busy(True)
        self.message.set('Closing owned games and connections. Saves are kept.')


def run_desktop(worlds_root, binary=REPO/'build/pokeemerald64', display=':95'):
    try:
        import tkinter as tk
    except ImportError as exc:
        raise ValueError('desktop UI requires Python with tkinter available') from exc
    # Validate before opening any window or scanning anything beyond the explicit root.
    with DesktopSession(DesktopSession.create_root(worlds_root)) as session:
        try:
            window = tk.Tk()
        except tk.TclError as exc:
            raise SessionError('Cannot open the launcher desktop. Set DISPLAY to your desktop display. The game uses its own dedicated display.') from exc
        app = None
        try:
            app = DesktopApp(window, session, binary, display)
            window.mainloop()
        finally:
            if app is not None:
                app.executor.shutdown(wait=True)
                app.session.close()
            try:
                window.destroy()
            except tk.TclError:
                pass
    return 0
