"""Send owner-only commands to a trainer's active interactive adventure.

A successful submission means queued. Query its session and sequence to learn
whether the authenticated game client reports applied, rejected or unknown.
"""
import argparse
import json
from pathlib import Path
from .client import admin_request


def set_state(admin_socket, trainer, identity, state):
    return admin_request('', {'command': 'set_event_state', 'trainer': trainer,
        'identity': identity, 'state': state}, admin_path=admin_socket)


def set_rule(admin_socket, trainer, identity, state, npc, next_state, text):
    return admin_request('', {'command': 'set_event_rule', 'trainer': trainer,
        'identity': identity, 'state': state, 'npc': npc,
        'next_state': next_state, 'text': text}, admin_path=admin_socket)


def status(admin_socket, trainer, identity, session, sequence):
    return admin_request('', {'command': 'event_command_status', 'trainer': trainer,
        'identity': identity, 'session': session, 'sequence': sequence}, admin_path=admin_socket)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, epilog=(
        'Keep the session and sequence from the submission response. A queued or '
        'unknown outcome is not proof of application. Do not automatically resend '
        'an uncertain command. Changes apply only to this trainer and reset on a new visit.'))
    parser.add_argument('--admin-socket', required=True, type=Path, help='Owner socket of the hosted world')
    parser.add_argument('--trainer', required=True, help='Connected trainer inside the active adventure')
    parser.add_argument('--area', required=True, help='Exact active adventure SHA256 identity')
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument('--state', type=int, choices=range(16), metavar='0..15', help='Set state, or select the state whose NPC rule is replaced')
    operation.add_argument('--status', type=int, metavar='SEQUENCE', help='Query a previously submitted command')
    parser.add_argument('--session', help='Connection session returned with the submitted command')
    parser.add_argument('--npc', type=int, choices=range(1, 4), metavar='1..3', help='Character local ID for a rule change')
    parser.add_argument('--next-state', type=int, choices=range(16), metavar='0..15', help='State after talking to this character')
    parser.add_argument('--text', help='Literal dialogue for a rule change, not a script or live chat')
    args = parser.parse_args(argv)
    if (args.status is not None) != (args.session is not None):
        parser.error('--status and --session must be supplied together')
    rule_fields = (args.npc, args.next_state, args.text)
    if args.status is not None and any(value is not None for value in rule_fields):
        parser.error('--status cannot be combined with rule fields')
    if any(value is not None for value in rule_fields) and any(value is None for value in rule_fields):
        parser.error('--npc, --next-state and --text must be supplied together')
    if args.status is not None and args.status < 1:
        parser.error('--status requires a positive sequence number')
    try:
        if args.status is not None:
            result = status(args.admin_socket, args.trainer, args.area, args.session, args.status)
        elif args.npc is not None:
            result = set_rule(args.admin_socket, args.trainer, args.area, args.state,
                              args.npc, args.next_state, args.text)
        else:
            result = set_state(args.admin_socket, args.trainer, args.area, args.state)
    except (OSError, ValueError):
        parser.exit(1, 'Could not read the owner response. The command outcome is unknown. '
                    'Check the hosted world and observe the game before retrying.\n')
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get('ok') is True else 1


if __name__ == '__main__':
    raise SystemExit(main())
