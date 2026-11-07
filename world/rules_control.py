"""Inspect or replace owner-controlled world rules through the local admin API."""
import argparse
import json
from pathlib import Path
from .client import admin_request


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--admin-socket', required=True, type=Path)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('status')
    replace = sub.add_parser('set')
    replace.add_argument('--revision', required=True, type=int,
                         help='last observed revision; stale writes are rejected')
    replace.add_argument('--wild-shuffle', choices=('on', 'off'), required=True)
    replace.add_argument('--seed', type=int, choices=range(1, 21), required=True)
    args = parser.parse_args(argv)
    request = {'command': 'world_rules', 'action': 'status'}
    if args.action == 'set':
        request.update(action='replace', expected_revision=args.revision,
                       rules={'wild_shuffle': {'enabled': args.wild_shuffle == 'on', 'seed': args.seed}})
    result = admin_request('', request, admin_path=args.admin_socket)
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get('ok') is True else 1


if __name__ == '__main__':
    raise SystemExit(main())
