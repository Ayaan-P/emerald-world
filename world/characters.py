"""Durable authored characters carried by the existing atomic mechanic state.

These are public fictional NPC records, not human trainer/save information.
Team records are author intent until the native battle adapter confirms support.
"""
import json
from pathlib import Path
import re

KEY = 'world_characters'
FIELDS = {'version', 'name', 'role', 'goals', 'relationships', 'team', 'status',
          'object_id', 'evidence', 'reason'}


def _text(value, maximum):
    if type(value) is not str or not 1 <= len(value) <= maximum or any(ord(c) < 32 for c in value):
        raise ValueError('invalid character text')


def records(state):
    value = state.get(KEY, {}) if type(state) is dict else {}
    if type(value) is not dict or len(value) > 8:
        raise ValueError('at most eight persistent characters')
    species = set(json.loads(Path(__file__).with_name('expansion_species.json').read_text())['species'].values())
    for identity, character in value.items():
        if type(identity) is not str or not re.fullmatch('[A-Za-z0-9_-]{1,24}', identity):
            raise ValueError('invalid character identity')
        if type(character) is not dict or set(character) != FIELDS:
            raise ValueError('invalid character fields')
        if type(character['version']) is not int or not 1 <= character['version'] <= 2**31-1:
            raise ValueError('invalid character version')
        _text(character['name'], 32)
        _text(character['role'], 160)
        _text(character['reason'], 240)
        if character['object_id'] != identity or character['status'] not in ('active', 'away', 'retired'):
            raise ValueError('invalid character presence')
        goals = character['goals']
        if type(goals) is not list or len(goals) > 4:
            raise ValueError('invalid character goals')
        for goal in goals:
            _text(goal, 160)
        relations = character['relationships']
        if type(relations) is not dict or len(relations) > 8:
            raise ValueError('invalid character relationships')
        for target, relationship in relations.items():
            if target not in value or target == identity:
                raise ValueError('relationships must reference other public characters')
            _text(relationship, 120)
        team = character['team']
        if type(team) is not list or not 1 <= len(team) <= 6:
            raise ValueError('character team must contain one to six Pokemon')
        for mon in team:
            if type(mon) is not dict or set(mon) != {'species', 'level'}:
                raise ValueError('invalid character team member')
            if type(mon['species']) is not int or mon['species'] not in species:
                raise ValueError('unknown character species')
            if type(mon['level']) is not int or not 1 <= mon['level'] <= 100:
                raise ValueError('invalid character level')
        evidence = character['evidence']
        if (type(evidence) is not list or len(evidence) > 8 or
                any(type(seq) is not int or seq < 1 for seq in evidence) or
                len(set(evidence)) != len(evidence)):
            raise ValueError('invalid character evidence')
    return value


def validate_transition(before, after, objects, db):
    old, new = records(before), records(after)
    if old.keys() - new.keys():
        raise ValueError('persistent characters must be retained; retire explicitly')
    visible = {obj['id']: obj for obj in objects}
    changes = []
    for identity, character in new.items():
        if (character['status'] == 'active') != (identity in visible):
            raise ValueError('active characters must have a rendered object; away/retired must not')
        previous = old.get(identity)
        if previous == character:
            continue
        if character['version'] != (previous['version'] + 1 if previous else 1):
            raise ValueError('character version must advance exactly once')
        if previous and previous['status'] == 'retired' and character['status'] != 'retired':
            raise ValueError('retired character identity cannot be reused')
        for seq in character['evidence']:
            row = db.execute('SELECT kind FROM events WHERE seq=?', (seq,)).fetchone()
            if row is None or row[0] != 'world_memory':
                raise ValueError('character evidence must reference committed public world history')
        changes.append({'character_id': identity, 'before': previous, 'after': character,
                        'interpretation': 'agent_authored_transition_not_proof_of_battle_or_catch'})
    return changes


def author_contract():
    return {
        'state_key': KEY,
        'record_fields': sorted(FIELDS),
        'team_member': {'species': 'enabled numeric species ID', 'level': 'integer 1..100'},
        'presence': 'active requires a matching top-level objects entry; away/retired must not render',
        'identity': 'stable ID matches object_id, never delete; retire explicitly; version starts at 1 and increments exactly once per changed record',
        'evidence': 'up to eight exact public world_memory sequence IDs; creation may have none; rationale is authored interpretation, never proof of battles or catches',
        'runtime': 'world_history is a bounded recent authority tail; use durable seq cursors for replay-safe decisions; absence is not proof an event never happened',
        'limits': 'eight public fictional characters, four goals, relationships only to other registered NPC identities; never store private player teams or save fields',
        'native_battles': 'not available through this character registry alone; do not claim a battle occurred or a team is native until the battle adapter confirms it',
    }


def challenge(server, conn, fields):
    """Freeze one explicitly requested opponent for exactly this authenticated peer."""
    import time
    if (len(fields) != 4 or not conn.get('character_capable') or
            server.peers.get(conn.get('id')) is not conn or conn.get('closing')):
        raise ValueError('character challenge unavailable')
    try:
        seq, version = int(fields[1]), int(fields[3])
    except ValueError:
        raise ValueError('invalid character challenge') from None
    if str(seq) != fields[1] or str(version) != fields[3] or not conn['seq'] < seq <= 2**31-1:
        raise ValueError('stale character challenge')
    pending = conn.get('character_pending')
    if pending:
        raise ValueError('character challenge already pending')
    character = records(server.module_state).get(fields[2])
    obj = next((obj for obj in server.objects if obj['id'] == fields[2]), None)
    state = conn.get('state')
    if (character is None or character['status'] != 'active' or character['version'] != version or
            obj is None or not state or not state[6] or
            time.monotonic() - conn.get('state_time', 0) > 5 or
            tuple(state[:2]) in (server.cave_map, server.wilds_map) or
            state[:2] != [obj['group'], obj['num']] or
            server.link_protocol.busy(conn['id']) or server.rally.current(conn) is not None):
        raise ValueError('character moved, changed or player unavailable')
    delta = {1:(0,1), 2:(0,-1), 3:(-1,0), 4:(1,0)}.get(state[4])
    if delta is None or (state[2]+delta[0], state[3]+delta[1]) != (obj['x'], obj['y']):
        raise ValueError('character challenge requires adjacent facing player')
    frozen = json.loads(json.dumps({'seq': seq, 'id': fields[2], 'version': version, 'team': character['team']}))
    conn['character_pending'] = frozen
    conn['seq'] = seq
    return 'CHARACTER_BATTLE_V1 ' + ' '.join(map(str, [seq, fields[2], version, len(frozen['team']),
        *[value for mon in frozen['team'] for value in (mon['species'], mon['level'])]])) + '\n'


def report_result(server, conn, fields):
    """Consume an exact pending challenge once; never grant rewards from reports."""
    pending = conn.get('character_pending')
    if (len(fields) != 5 or not conn.get('character_capable') or
            server.peers.get(conn.get('id')) is not conn or conn.get('closing') or not pending or
            fields[1:4] != [str(pending['seq']), pending['id'], str(pending['version'])] or
            not fields[4].isdigit() or not 0 <= int(fields[4]) <= 255):
        raise ValueError('unmatched character result')
    with server.db:
        server._event('character_battle_report', dict(player=conn['id'], character=pending['id'],
            version=pending['version'], outcome=int(fields[4]), evidence='authenticated_client_report_not_verified_outcome'))
    conn.pop('character_pending')
    return 'CHARACTER_RESULT_ACK ' + ' '.join(fields[1:4]) + '\n'
