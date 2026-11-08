"""Publish an inert cave template to a running local authority's admin socket.

The authority accepts a replacement only when no connected trainer is in its
cave. Content is ephemeral unless the host opts into cave persistence.
"""
import argparse
import base64
import json
from pathlib import Path
import sys
from .client import admin_request
from .shared_cave import SharedCave, MAX_SIZE
from .cave_blueprint import proposal_from_blueprint, MAX_INPUT


def publish(template, admin_socket, *, previous_revision=None):
    with Path(template).open('rb') as stream:
        blob = stream.read(MAX_SIZE + 1)
    return publish_bytes(blob, admin_socket, previous_revision=previous_revision)


def publish_blueprint(path, admin_socket, *, previous_revision=None):
    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_INPUT + 1)
    if len(raw) > MAX_INPUT:
        raise ValueError('blueprint exceeds size limit')
    proposal = proposal_from_blueprint(json.loads(raw))
    blob = b'EWGMAP01' + ''.join(proposal['rows']).encode('ascii')
    return publish_bytes(blob, admin_socket, previous_revision=previous_revision)


def publish_bytes(blob, admin_socket, *, label=None, previous_revision=None, world_history=None, route_artifact=None):
    # Validate again using the authority's production format before touching admin.
    cave = SharedCave(blob)
    request = {'command': 'replace_cave', 'template': base64.b64encode(blob).decode('ascii')}
    if previous_revision is not None:
        import re
        if type(previous_revision) is not str or not re.fullmatch(r'[0-9a-f]{64}', previous_revision):
            raise ValueError('invalid previous area revision')
        request['previous_revision'] = previous_revision
    if label is not None:
        if (type(label) is not str or not label.strip() or len(label) > 80
                or any(ord(c) < 32 or ord(c) == 127 for c in label)):
            raise ValueError('Use 1 to 80 printable characters for the area name')
        request['label'] = label
    if world_history is not None:
        request.update(expected_world_id=world_history['world_id'],expected_sequence=world_history['through'],
                       history_evidence=[event['seq'] for event in world_history['events']])
    if route_artifact is not None:
        from .route_artifacts import validate
        validate(route_artifact, blob)
        request['route_artifact'] = route_artifact
    response = admin_request('', request, admin_path=admin_socket)
    if (type(response) is not dict or response.get('ok') is not True
            or response.get('id') != cave.identity or type(response.get('persistent')) is not bool):
        raise ValueError('authority did not accept the cave')
    return cave.identity


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--admin-socket', required=True, type=Path)
    parser.add_argument('--previous-revision', help='Explicitly continue the active logical place at this exact content hash; does not migrate trainer progress')
    parser.add_argument('--blueprint', type=Path, help='compile an inert room blueprint before publishing')
    parser.add_argument('template', type=Path, nargs='?')
    args = parser.parse_args(argv)
    if (args.template is None) == (args.blueprint is None):
        parser.error('provide exactly one template or --blueprint')
    try:
        print(publish_blueprint(args.blueprint, args.admin_socket, previous_revision=args.previous_revision) if args.blueprint else publish(args.template, args.admin_socket, previous_revision=args.previous_revision))
    except (OSError, ValueError, TypeError, UnicodeError):
        print('Could not publish cave; check the template, local authority and occupancy.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
