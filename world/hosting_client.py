"""Pinned HTTPS hosted-world API and private-file CLI for launcher integration.

No method reads game saves. Native invitations are ordinary unchanged v1 files.
Never pass credentials on argv or stdout. Obtain HOST ACCESS files privately.
"""
import base64
import hashlib
import hmac
import http.client
import json
import os
from pathlib import Path
import re
import secrets
import ssl
import stat

from .hosting_protocol import HostingError, _json_object
from .transport import validate_invitation, validate_invitation_host


def write_private(path, value):
    """Create a new 0600 JSON file. Never follow links or overwrite a file."""
    raw = (json.dumps(value, separators=(',', ':')) + '\n').encode('utf-8')
    if len(raw) > 4096:
        raise ValueError('private file too large')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        Path(path).unlink()
        raise


def read_private(path):
    """Bounded regular-file reader. Reject credentials readable by other users."""
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > 4096 or info.st_mode & 0o077:
                raise ValueError('invalid private file')
            raw = stream.read(4097)
        if len(raw) > 4096:
            raise ValueError('invalid private file')
        return _json_object(raw)
    except (OSError, ValueError, TypeError, RecursionError):
        raise ValueError('invalid private file') from None


def _bundle(value, kind):
    expected = {'kind', 'version', 'endpoint', 'pin', 'token'}
    if kind == 'world-join':
        expected.add('world_id')
    if (type(value) is not dict or set(value) != expected or value.get('kind') != kind
            or type(value.get('version')) is not int or value['version'] != 1):
        raise ValueError('invalid hosting credentials')
    # Reuse the native endpoint, fingerprint and bearer validation contract.
    validate_invitation(dict(version=1, endpoint=value['endpoint'], pin=value['pin'],
                             token=value['token'], trainer='validation'))
    if not re.fullmatch('[0-9a-f]{64}', value['token']):
        raise ValueError('invalid hosting credentials')
    if kind == 'world-join' and (type(value['world_id']) is not str
                                or not re.fullmatch('[0-9a-f]{16}', value['world_id'])):
        raise ValueError('invalid hosting credentials')
    return value


class HostingClient:
    """Methods return Python dictionaries. Only list metadata is safe to display."""
    def __init__(self, profile):
        self.profile = dict(_bundle(profile, 'host-profile'))

    @classmethod
    def from_file(cls, profile_path):
        return cls(read_private(profile_path))

    @staticmethod
    def _request(credentials, method, path, body=None):
        endpoint = credentials['endpoint']
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        connection = http.client.HTTPSConnection(endpoint['host'], endpoint['port'], context=context, timeout=10)
        try:
            connection.connect()
            pin = hashlib.sha256(connection.sock.getpeercert(binary_form=True)).hexdigest()
            if not hmac.compare_digest(pin, credentials['pin'].lower()):
                raise ValueError('TLS trust failed')
            # Absolutely no HTTP request, body or authorization before the pin.
            raw = None if body is None else json.dumps(body, separators=(',', ':')).encode('utf-8')
            from .shared_cave import MAX_SIZE
            upload = method == 'POST' and re.fullmatch('/v1/worlds/[0-9a-f]{16}/generated-areas', path)
            limit = 4 * ((MAX_SIZE + 2) // 3) + 1024 if upload else 4096
            if raw is not None and len(raw) > limit:
                raise ValueError('request too large')
            connection.request(method, path, body=raw, headers={
                'Authorization': 'Bearer ' + credentials['token'], 'Content-Type': 'application/json'})
            response = connection.getresponse()
            raw = response.read(16385)
            if len(raw) > 16384:
                raise ValueError('invalid hosting response')
            value = _json_object(raw)
            if response.status != 200:
                allowed = {400: {'invalid_request'}, 403: {'forbidden'}, 409: {'conflict'},
                           503: {'capacity', 'unavailable'}}
                code = value.get('error')
                if code not in allowed.get(response.status, set()):
                    raise ValueError('invalid hosting response')
                raise HostingError(response.status, code)
            return value
        except (OSError, http.client.HTTPException):
            raise ValueError('hosting connection failed') from None
        finally:
            connection.close()

    @classmethod
    def enroll(cls, invitation_path, profile_path):
        access = _bundle(read_private(invitation_path), 'host-access')
        if Path(profile_path).exists():
            profile = _bundle(read_private(profile_path), 'host-profile')
            if profile['endpoint'] != access['endpoint'] or profile['pin'] != access['pin']:
                raise ValueError('profile belongs to another host')
        else:
            profile = dict(access, kind='host-profile', token=secrets.token_hex(32))
            # Persist first so a lost HTTPS response can retry the exact enrollment.
            write_private(profile_path, profile)
        cls._request(access, 'POST', '/v1/enroll', dict(account_token=profile['token']))
        return cls(profile)

    def list(self):
        return self._request(self.profile, 'GET', '/v1/worlds')['worlds']

    def create(self, name, trainer, *, request_id=None):
        """Supply a stable request_id when retrying an ambiguous network failure."""
        return self._request(self.profile, 'POST', '/v1/worlds',
                             dict(name=name, trainer=trainer, request_id=request_id or secrets.token_hex(16)))

    @staticmethod
    def _world_id(world_id):
        if type(world_id) is not str or not re.fullmatch('[0-9a-f]{16}', world_id):
            raise ValueError('invalid world id')
        return world_id

    def resume(self, world_id):
        return self._request(self.profile, 'POST', '/v1/worlds/' + self._world_id(world_id) + '/resume', {})

    def read_adventures(self, world_id):
        """Read owner-only built-in adventures without a provider or game launch."""
        return self._request(self.profile, 'GET',
                             '/v1/worlds/' + self._world_id(world_id) + '/adventure')

    def preview_adventure(self, world_id, adventure='lantern-trail'):
        if type(adventure) is not str or not re.fullmatch('[a-z0-9-]{1,48}', adventure):
            raise ValueError('invalid adventure id')
        return self._request(self.profile, 'POST',
                             '/v1/worlds/' + self._world_id(world_id) + '/adventure/preview',
                             dict(adventure=adventure))

    def apply_adventure(self, world_id, review_token, *, confirmed=False):
        """One explicit attempt; an ambiguous result must be read back, not replayed."""
        if (confirmed is not True or type(review_token) is not str
                or not re.fullmatch('[0-9a-f]{48}', review_token)):
            raise ValueError('Review and confirm the exact adventure before applying.')
        return self._request(self.profile, 'POST',
                             '/v1/worlds/' + self._world_id(world_id) + '/adventure/apply',
                             dict(token=review_token, confirmed=True))

    def generated_area_status(self, world_id):
        """Return owner-only capabilities, archive metadata and current occupancy."""
        return self._request(self.profile, 'GET',
                             '/v1/worlds/' + self._world_id(world_id) + '/generated-areas')

    generated_areas = generated_area_status

    def publish_generated_area(self, world_id, blob, *, label):
        """Publish locally authored inert bytes. This never invokes a provider."""
        from .shared_cave import SharedCave
        SharedCave(blob)
        if (type(label) is not str or not label.strip() or len(label) > 80
                or any(ord(c) < 32 or ord(c) == 127 for c in label)):
            raise ValueError('invalid generated area label')
        return self._request(self.profile, 'POST',
                             '/v1/worlds/' + self._world_id(world_id) + '/generated-areas',
                             dict(template=base64.b64encode(blob).decode('ascii'), label=label))

    def activate_generated_area(self, world_id, identity):
        if type(identity) is not str or not re.fullmatch('[0-9a-f]{64}', identity):
            raise ValueError('invalid generated area identity')
        return self._request(self.profile, 'POST',
                             '/v1/worlds/' + self._world_id(world_id) + '/generated-areas/activate',
                             dict(identity=identity))

    def invite_account(self, invitation_out, *, request_id=None):
        """Bootstrap sponsor issues a private HOST ACCESS file for another owner."""
        value = self._request(self.profile, 'POST', '/v1/accounts/invites',
                              dict(request_id=request_id or secrets.token_hex(16)))
        _bundle(value, 'host-access')
        self._save(invitation_out, value)
        return value

    def invite(self, world_id, invitation_out, *, request_id=None):
        value = self._request(self.profile, 'POST', '/v1/worlds/' + self._world_id(world_id) + '/invites',
                              dict(request_id=request_id or secrets.token_hex(16)))
        _bundle(value, 'world-join')
        self._save(invitation_out, value)
        return value

    @classmethod
    def redeem(cls, invitation_path, trainer):
        """Redeem into memory for the native-session adapter; never log result."""
        access = _bundle(read_private(invitation_path), 'world-join')
        return cls._request(access, 'POST', '/v1/join', dict(trainer=trainer))

    @classmethod
    def join(cls, invitation_path, trainer, invitation_out):
        value = cls.redeem(invitation_path, trainer)
        cls.save_invitation(value, invitation_out)
        return value

    @staticmethod
    def _save(path, value):
        try:
            write_private(path, value)
        except FileExistsError:
            if read_private(path) != value:
                raise ValueError('output already exists') from None

    @staticmethod
    def save_invitation(result, destination):
        HostingClient._save(destination, validate_invitation(result['invitation']))


def main(argv=None):
    import argparse
    import sys
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    enroll = commands.add_parser('enroll')
    enroll.add_argument('--access', required=True, type=Path)
    enroll.add_argument('--profile', required=True, type=Path)
    join = commands.add_parser('join')
    join.add_argument('--invitation', required=True, type=Path)
    join.add_argument('--trainer', required=True)
    join.add_argument('--invitation-out', required=True, type=Path)
    for action in ('list', 'create', 'resume', 'invite', 'invite-account'):
        command = commands.add_parser(action)
        command.add_argument('--profile', required=True, type=Path)
        if action != 'list':
            command.add_argument('--invitation-out', required=True, type=Path)
        if action in ('resume', 'invite'):
            command.add_argument('--world', required=True)
        if action in ('create', 'invite', 'invite-account'):
            command.add_argument('--request-id', required=True,
                                 help='reuse exactly this id for a retry')
        if action == 'create':
            command.add_argument('--name', required=True)
            command.add_argument('--trainer', required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == 'enroll':
            HostingClient.enroll(args.access, args.profile)
        elif args.action == 'join':
            HostingClient.join(args.invitation, args.trainer, args.invitation_out)
        else:
            client = HostingClient.from_file(args.profile)
            if args.action == 'list':
                print(json.dumps(client.list()))
            elif args.action == 'create':
                result = client.create(args.name, args.trainer, request_id=args.request_id)
                client.save_invitation(result, args.invitation_out)
                print(json.dumps(result['world']))
            elif args.action == 'resume':
                client.save_invitation(client.resume(args.world), args.invitation_out)
            elif args.action == 'invite-account':
                client.invite_account(args.invitation_out, request_id=args.request_id)
            elif args.action == 'invite':
                client.invite(args.world, args.invitation_out, request_id=args.request_id)
        return 0
    except HostingError as exc:
        print('hosting: ' + exc.code, file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError):
        print('hosting: private file, TLS trust or connection failure', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
