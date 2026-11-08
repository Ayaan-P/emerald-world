"""Owner-only living grass habitat controls for a published event area.

Configured tiles grow tall grass. Repeated player steps wear it down, removing
that tile's grass encounters. Steps elsewhere let it regrow. This is an opt-in
shared terrain owner: disable before manually repainting its cells. Disabling
preserves current terrain. Status reports pending commits, not client rendering.
"""
import argparse
import json
from pathlib import Path
from .client import admin_request


def request(admin_socket, identity, action='status', **options):
    return admin_request('', dict(command='habitat', identity=identity, action=action, **options), admin_path=admin_socket)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--admin-socket', required=True, type=Path)
    parser.add_argument('--area', required=True)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--status', action='store_true')
    actions.add_argument('--disable', action='store_true')
    actions.add_argument('--tiles-file', type=Path, help='JSON array of {"x": integer, "y": integer}, at most 64 cells')
    parser.add_argument('--wear-steps', type=int, default=4)
    parser.add_argument('--rest-steps', type=int, default=40)
    args = parser.parse_args(argv)
    options = {}
    if args.tiles_file:
        with args.tiles_file.open('rb') as source:
            data = source.read(8193)
        if len(data) > 8192:
            parser.error('tile input too large')
        options = dict(tiles=json.loads(data), wear_steps=args.wear_steps, rest_steps=args.rest_steps)
    result = request(args.admin_socket, args.area, 'configure' if args.tiles_file else 'disable' if args.disable else 'status', **options)
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get('ok') is True else 1


if __name__ == '__main__':
    raise SystemExit(main())
