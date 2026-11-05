"""Publish an inert cave template to a running local authority's admin socket.

The authority accepts a replacement only when no connected trainer is in its
cave. This is ephemeral world content and is not retained across restart.
"""
import argparse
import base64
import json
from pathlib import Path
import sys
from .client import admin_request
from .shared_cave import SharedCave, SIZE
from .cave_blueprint import proposal_from_blueprint, MAX_INPUT


def publish(template, admin_socket):
    with Path(template).open('rb') as stream:
        blob = stream.read(SIZE + 1)
    return publish_bytes(blob, admin_socket)


def publish_blueprint(path, admin_socket):
    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_INPUT + 1)
    if len(raw) > MAX_INPUT:
        raise ValueError('blueprint exceeds size limit')
    proposal = proposal_from_blueprint(json.loads(raw))
    blob = b'EWGMAP01' + ''.join(proposal['rows']).encode('ascii')
    return publish_bytes(blob, admin_socket)


def publish_bytes(blob, admin_socket):
    # Validate again using the authority's production format before touching admin.
    cave = SharedCave(blob)
    response = admin_request('', {'command':'replace_cave', 'template':base64.b64encode(blob).decode('ascii')},
                             admin_path=admin_socket)
    if (type(response) is not dict or response.get('ok') is not True
            or response.get('id') != cave.identity or response.get('persistent') is not False):
        raise ValueError('authority did not accept the cave')
    return cave.identity


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--admin-socket', required=True, type=Path)
    parser.add_argument('--blueprint', type=Path, help='compile an inert room blueprint before publishing')
    parser.add_argument('template', type=Path, nargs='?')
    args = parser.parse_args(argv)
    if (args.template is None) == (args.blueprint is None):
        parser.error('provide exactly one template or --blueprint')
    try:
        print(publish_blueprint(args.blueprint, args.admin_socket) if args.blueprint else publish(args.template, args.admin_socket))
    except (OSError, ValueError, TypeError, UnicodeError):
        print('Could not publish cave; check the template, local authority and occupancy.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
