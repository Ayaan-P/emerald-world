"""Optional launcher adapter for the separately reviewed hosted-world service.

No credentials or native invitations appear in launcher snapshots or logs.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import stat
import tempfile

from .session import SessionError


def available():
    return all(importlib.util.find_spec(name) is not None for name in
               ('world.hosting_client', 'world.hosting_protocol', 'world.hosting_session'))


def backup_available():
    return importlib.util.find_spec('world.hosted_profile_backup') is not None


class HostedLauncher:
    def __init__(self, session):
        self.session = session
        self.profile = session.root / '.hosted-owner.json'
        self.marker = session.root / '.hosted-enrolled.json'
        self.pending = session.root / '.hosted-pending-create.json'
        self.worlds = []
        self.loaded = False
        self.invite_requests = {}
        self.completed_request = None

    def _private(self, path):
        from .hosting_client import read_private
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_nlink != 1 or info.st_mode & 0o077):
            raise ValueError('unsafe private file')
        return read_private(path)

    def _root(self):
        info = self.session.root.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_mode & 0o022 or self.session.root.resolve() != self.session.root):
            raise SessionError('Hosted accounts require a private, owned world storage folder.')

    def enrolled(self):
        if not available():
            return False
        try:
            from .hosting_client import HostingClient
            self._root()
            self._private(self.profile)
            HostingClient.from_file(self.profile)
            marker = self._private(self.marker)
            digest = hashlib.sha256(self.profile.read_bytes()).hexdigest()
            return marker == {'profile_sha256': digest}
        except (OSError, ValueError, TypeError):
            return False

    def pending_create(self):
        if not available() or not os.path.lexists(self.pending):
            return None
        value = self._private(self.pending)
        if (set(value) != {'name', 'trainer', 'request_id'}
                or not isinstance(value['name'], str) or not 1 <= len(value['name']) <= 80
                or not isinstance(value['trainer'], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,24}', value['trainer'])
                or not isinstance(value['request_id'], str) or not re.fullmatch(r'[0-9a-f]{32}', value['request_id'])):
            raise SessionError('A pending world request is invalid. Do not create another until it is resolved.')
        return value

    def state(self):
        if not available():
            return {'available': False, 'backup_available': False, 'enrolled': False, 'loaded': False, 'worlds': [], 'pending': None}
        try:
            pending = self.pending_create()
        except (OSError, ValueError, SessionError):
            pending = {'invalid': True}
        return {'available': True, 'backup_available': backup_available(), 'enrolled': self.enrolled(), 'loaded': self.loaded,
                'worlds': self.worlds,
                'pending': {'name': pending['name'], 'trainer': pending['trainer']} if pending and not pending.get('invalid') else pending}

    def _ready(self):
        if not available():
            raise SessionError('The hosted-world backend is not installed yet.')
        if not self.enrolled():
            raise SessionError('Import your host access file before managing hosted worlds.')

    @staticmethod
    def _write_temp(raw, directory):
        if not isinstance(raw, str) or not 0 < len(raw.encode('utf-8')) <= 4096:
            raise SessionError('Choose a valid private access file.')
        path = Path(directory) / 'access.json'
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as output:
            output.write(raw)
        return path

    def enroll(self, raw):
        if not available():
            raise SessionError('The hosted-world backend is not installed yet.')
        self._root()
        from .hosting_client import HostingClient, write_private
        with tempfile.TemporaryDirectory(prefix='emerald-host-access-') as directory:
            HostingClient.enroll(self._write_temp(raw, directory), self.profile)
        self._private(self.profile)
        digest = hashlib.sha256(self.profile.read_bytes()).hexdigest()
        if os.path.lexists(self.marker):
            if self._private(self.marker) != {'profile_sha256': digest}:
                raise SessionError('An existing host account was left unchanged.')
        else:
            write_private(self.marker, {'profile_sha256': digest})
        self.worlds, self.loaded = [], False

    def export_profile(self):
        self._ready()
        if not backup_available():
            raise SessionError('Host account backup support is not installed yet.')
        from .hosted_profile_backup import read_profile
        return json.dumps(read_profile(self.profile), separators=(',', ':'))

    def restore_profile(self, raw):
        if not available() or not backup_available():
            raise SessionError('Host account backup support is not installed yet.')
        self._root()
        from .hosted_profile_backup import read_profile, copy_profile
        from .hosting_client import write_private
        # Never replace an account, or associate an orphaned creation request
        # or enrollment marker with a different credential.
        if not os.path.lexists(self.profile) and (os.path.lexists(self.pending) or os.path.lexists(self.marker)):
            raise SessionError('Existing account state was left unchanged. Resolve it before restoring.')
        with tempfile.TemporaryDirectory(prefix='emerald-host-restore-') as directory:
            source = self._write_temp(raw, directory)
            incoming = read_profile(source)
            if os.path.lexists(self.profile):
                if read_profile(self.profile) != incoming:
                    raise SessionError('A different host account already exists on this device. It was not changed.')
            else:
                copy_profile(source, self.profile)
        digest = hashlib.sha256(self.profile.read_bytes()).hexdigest()
        if os.path.lexists(self.marker):
            if self._private(self.marker) != {'profile_sha256': digest}:
                raise SessionError('An existing account marker was left unchanged.')
        else:
            write_private(self.marker, {'profile_sha256': digest})
        self.worlds, self.loaded = [], False
        self.session.status = 'Host account restored locally. Refresh hosted worlds to verify access.'

    @staticmethod
    def _world(item):
        if (not isinstance(item, dict) or set(item) != {'id', 'name', 'trainer'}
                or not isinstance(item['id'], str) or not re.fullmatch('[0-9a-f]{16}', item['id'])
                or not isinstance(item['name'], str) or not 1 <= len(item['name']) <= 80
                or any(ord(c) < 32 for c in item['name'])
                or not isinstance(item['trainer'], str) or not re.fullmatch('[A-Za-z0-9_-]{1,24}', item['trainer'])):
            raise ValueError('invalid world metadata')
        return {key: item[key] for key in ('id', 'name', 'trainer')}

    def rules(self, world_id, rules=None):
        self._ready()
        from .hosting_client import HostingClient
        client = HostingClient.from_file(self.profile)
        return client.world_rules(world_id) if rules is None else client.set_world_rules(world_id, rules)

    def refresh(self):
        self._ready()
        from .hosting_client import HostingClient
        values = HostingClient.from_file(self.profile).list()
        if not isinstance(values, list) or len(values) > 64:
            raise ValueError('invalid world list')
        worlds = [self._world(item) for item in values]
        self.worlds, self.loaded = worlds, True

    def _remember_name(self, result):
        """Seed a friendly local label without overwriting a player's label."""
        try:
            from .world_library import _read_metadata
            world = self._world(result['world'])
            key = result['key']
            if key != 'hosted-' + world['id']:
                return
            current = _read_metadata(self.session._world(key))
            if current['display_name'] != key:
                return
            previous = self.session.status
            try:
                self.session.rename_world(key, world['name'], current['tags'])
            finally:
                self.session.status = previous
        except (OSError, ValueError, TypeError, KeyError):
            pass  # A label must never turn a successful connection into a failure.

    def create(self, name, trainer):
        self._ready()
        if (not isinstance(name, str) or not 1 <= len(name.strip()) <= 80
                or any(ord(c) < 32 for c in name)
                or not isinstance(trainer, str) or not re.fullmatch('[A-Za-z0-9_-]{1,24}', trainer)):
            raise SessionError('Enter a world name and a valid trainer profile.')
        from .hosting_client import write_private
        from .hosting_session import HostedWorldSession
        pending = self.pending_create()
        if pending is None:
            pending = {'name': name, 'trainer': trainer, 'request_id': secrets.token_hex(16)}
            write_private(self.pending, pending)
        elif (pending['name'], pending['trainer']) != (name, trainer):
            raise SessionError('Retry your pending world creation with the same name and trainer first.')
        result = HostedWorldSession(self.session, self.profile).create(name, trainer, request_id=pending['request_id'])
        world = self._world(result['world'])
        if (world['name'], world['trainer']) != (name, trainer):
            raise SessionError('The server returned an unexpected world. Retry the pending request.')
        # Keep the idempotency record until the browser acknowledges receipt.
        # If the HTTP response is lost, a later retry must use the same ID.
        self.completed_request = pending['request_id']
        self._remember_name(result)
        self.worlds = [item for item in self.worlds if item['id'] != world['id']] + [world]
        return result['paths']

    def acknowledge_create(self):
        pending = self.pending_create()
        if pending is None or self.completed_request != pending['request_id']:
            raise SessionError('No completed creation is awaiting confirmation.')
        self.pending.unlink()
        self.completed_request = None

    def resume(self, world_id):
        self._ready()
        from .hosting_session import HostedWorldSession
        result = HostedWorldSession(self.session, self.profile).resume(world_id)
        self._remember_name(result)
        return result['paths']

    def join(self, raw, trainer):
        if not available():
            raise SessionError('The hosted-world backend is not installed yet.')
        self._root()
        if not isinstance(trainer, str) or not re.fullmatch('[A-Za-z0-9_-]{1,24}', trainer):
            raise SessionError('Use 1 to 24 letters, numbers, underscores or hyphens for your trainer.')
        from .hosting_session import HostedWorldSession
        with tempfile.TemporaryDirectory(prefix='emerald-world-join-') as directory:
            result = HostedWorldSession(self.session).join(self._write_temp(raw, directory), trainer)
            self._remember_name(result)
            return result['paths']

    def invite_owner(self):
        self._ready()
        from .hosting_client import HostingClient
        request_id = self.invite_requests.setdefault('owner', secrets.token_hex(16))
        with tempfile.TemporaryDirectory(prefix='emerald-host-invite-') as directory:
            destination = Path(directory) / 'host-access.json'
            HostingClient.from_file(self.profile).invite_account(destination, request_id=request_id)
            value = self._private(destination)
            raw = json.dumps(value, separators=(',', ':'))
        self.invite_requests.pop('owner', None)
        return raw

    def invite(self, world_id):
        self._ready()
        from .hosting_client import HostingClient
        if not isinstance(world_id, str) or not re.fullmatch('[0-9a-f]{16}', world_id):
            raise SessionError('Choose an owned world.')
        request_id = self.invite_requests.setdefault(world_id, secrets.token_hex(16))
        with tempfile.TemporaryDirectory(prefix='emerald-world-invite-') as directory:
            destination = Path(directory) / 'invitation.json'
            HostingClient.from_file(self.profile).invite(world_id, destination, request_id=request_id)
            value = self._private(destination)
            raw = json.dumps(value, separators=(',', ':'))
        self.invite_requests.pop(world_id, None)
        return raw
