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
    from .world_rules import GAMEPLAY_BITS
    for key in GAMEPLAY_BITS:
        replace.add_argument('--' + key.replace('_', '-'), choices=('on', 'off'),
                             help='world permission; omitted gameplay options preserve their current value')
    args = parser.parse_args(argv)
    request: dict = {'command': 'world_rules', 'action': 'status'}
    if args.action == 'set':
        # Read the complete document before patching named options. The private
        # authority still owns the atomic zero-player/revision check on write.
        from .rules_ui import _status
        try:
            current = _status(admin_request('', request, admin_path=args.admin_socket))
            if current['revision'] != args.revision:
                raise ValueError('world rules changed; refresh and retry')
            rules = current['rules']
            rules['wild_shuffle'] = {'enabled': args.wild_shuffle == 'on', 'seed': args.seed}
            for key in GAMEPLAY_BITS:
                flag = getattr(args, key)
                if flag is not None:
                    if key not in rules:
                        raise ValueError('unsupported world rules capability')
                    rules[key] = flag == 'on'
        except ValueError as exc:
            print(json.dumps({'ok': False, 'error': str(exc)}, sort_keys=True))
            return 1
        request.update(action='replace', expected_revision=args.revision, rules=rules)
    result = admin_request('', request, admin_path=args.admin_socket)
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get('ok') is True else 1


if __name__ == '__main__':
    raise SystemExit(main())
