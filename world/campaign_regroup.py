"""Voluntary speaker rotation and checkpoint party reformation; no inherited wins."""
import json


def command(server, conn, words, key, group):
    from .shared_campaigns import member, store, update_members
    from .battle_campaigns import document
    me = member(conn)
    if not words or words[0] not in ('volunteer-speaker', 'pass-speaker', 'regroup', 'withdraw'):
        return False
    if me not in group['members'] or group['status'] not in ('lobby', 'choice'):
        raise ValueError('Regroup or change speaker only in a lobby or completed-stage checkpoint')
    volunteers = group.setdefault('speaker_volunteers', [])
    with server.db:
        if words == ['volunteer-speaker']:
            if me == group['speaker']:
                raise ValueError('You are already the speaker')
            if me not in volunteers:
                volunteers.append(me)
        elif len(words) == 2 and words[0] == 'pass-speaker':
            target = next((m for m in group['members'] if m[0] == words[1]), None)
            if me != group['speaker'] or target not in volunteers:
                raise ValueError('Current speaker may pass only to a volunteering current participant')
            group['speaker'] = target
            group['speaker_volunteers'] = []
        elif len(words) == 2 and words[0] == 'regroup':
            if me != group['speaker'] or group['status'] != 'choice' or words[1] not in group['choices']:
                raise ValueError('Speaker chooses an available next route before reopening the party')
            document(server, group['campaign'])['nodes'][words[1]]
            group.update(node=words[1], status='lobby', results={}, advice={}, choices=[], roles={}, npc_roles={}, npc_results={}, npc_status={}, speaker_volunteers=[])
            update_members(server, key, group, node=words[1], status='lobby', choices=[])
        elif words == ['withdraw']:
            if group['status'] != 'lobby':
                raise ValueError('Reopen the party at the checkpoint before withdrawing')
            remaining = [m for m in group['members'] if m != me]
            if me == group['speaker'] and remaining:
                raise ValueError('Pass speaking to a volunteer before withdrawing')
            # Keep the departing save's history as an inactive private record.
            saved = server.db.execute('SELECT data FROM battle_campaign_runs WHERE trainer=? AND lineage=?', me).fetchone()
            if not saved or json.loads(saved[0]).get('shared') != key:
                raise ValueError('Save binding changed')
            data = json.loads(saved[0]); data.pop('shared', None)
            data.update(status='withdrawn', choices=[])
            server.db.execute('UPDATE battle_campaign_runs SET data=? WHERE trainer=? AND lineage=?', (json.dumps(data), *me))
            group['members'] = remaining
            group['speaker_volunteers'] = [m for m in volunteers if m != me]
            if not remaining:
                group['status'] = 'cancelled'
        else:
            raise ValueError('Invalid party regroup command')
        store(server, key, group)
    return True


def rows(conn, group):
    from .shared_campaigns import member
    me = member(conn)
    if group['status'] not in ('lobby', 'choice'):
        return []
    out = [('Speaker '+group['speaker'][0]+'. Party changes happen between stages.', None)]
    if me != group['speaker']:
        out.append(('Volunteer to speak for this party', ['volunteer-speaker']))
    else:
        out.extend(('Pass speaking to '+m[0], ['pass-speaker', m[0]]) for m in group.get('speaker_volunteers', []) if m in group['members'])
        if group['status'] == 'choice':
            out.extend(('Take '+route+' and reopen party for joining or withdrawal', ['regroup', route]) for route in group['choices'])
    if group['status'] == 'lobby':
        out.append(('Withdraw yourself; keep other trainers and their progress', ['withdraw']))
        out.append(('New members start this stage without earlier results or history.', None))
    return out
