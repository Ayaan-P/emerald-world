"""Optional field expeditions resolved by admitted world changes, not chosen wins."""
import time
from . import campaign_mechanisms as mechanisms


def validate(server, node):
    if set(node) != {'expedition'}:
        raise ValueError('An expedition stage contains only expedition')
    goal = node['expedition']
    if type(goal) is not dict or set(goal) != {'network', 'definition', 'label', 'resolutions'}:
        raise ValueError('Use network, definition, label and resolutions')
    resolutions = goal['resolutions']
    if type(resolutions) is not dict or not 2 <= len(resolutions) <= 4:
        raise ValueError('Offer two to four genuine world resolutions')
    for phase, resolution in resolutions.items():
        if type(phase) is not str or type(resolution) is not dict or set(resolution) != {'label', 'next'}:
            raise ValueError('Each phase needs a label and next routes')
        mechanisms.validate(server, dict(mechanism=dict(network=goal['network'], definition=goal['definition'],
            label=goal['label'], phase=phase), next=[]))
        label = resolution['label']
        if type(label) is not str or not 1 <= len(label) <= 40 or any(not 32 <= ord(c) < 127 for c in label):
            raise ValueError('Use a short printable resolution label')
        routes = resolution['next']
        if type(routes) is not list or len(routes) > 4 or any(type(k) is not str for k in routes) or len(set(routes)) != len(routes):
            raise ValueError('Use up to four distinct next routes')


def routes(node):
    return list(dict.fromkeys(k for value in node['expedition']['resolutions'].values() for k in value['next']))


def current(server, conn):
    from .battle_campaigns import active, document
    value = active(server, conn)
    if not value or value[1]['status'] != 'ready':
        raise ValueError('No ready field expedition')
    key, data = value
    node = document(server, key)['nodes'][data['node']]
    if 'expedition' not in node:
        raise ValueError('This is not a field expedition')
    validate(server, node)
    return key, data, node


def ready(server, conn):
    from .battle_campaigns import save
    from .shared_campaigns import load, member, store, update_members
    key, data, node = current(server, conn)
    goal = node['expedition']
    if data.get('expedition_ready') == data['node']:
        raise ValueError('Already ready for this expedition')
    with server.db:
        data['expedition_ready'] = data['node']
        save(server, conn, key, data)
        if data.get('shared'):
            group = load(server, data['shared'])
            if group['status'] != 'ready' or member(conn) not in group['members']:
                raise ValueError('Party stage changed')
            checkpoint = group.get('expedition')
            if not checkpoint or checkpoint['node'] != data['node']:
                checkpoint = dict(node=data['node'], definition=goal['definition'], ready=[])
            if checkpoint['definition'] != goal['definition']:
                raise ValueError('Expedition definition changed')
            checkpoint['ready'].append(member(conn))
            if sorted(checkpoint['ready']) == sorted(group['members']):
                checkpoint['after'] = server.db.execute('SELECT coalesce(max(seq),0) FROM events').fetchone()[0]
                update_members(server, data['shared'], group, expedition_watch=dict(node=data['node'],
                    definition=goal['definition'], after=checkpoint['after']))
            group['expedition'] = checkpoint
            store(server, data['shared'], group)
        else:
            data['expedition_watch'] = dict(node=data['node'], definition=goal['definition'],
                after=server.db.execute('SELECT coalesce(max(seq),0) FROM events').fetchone()[0])
            save(server, conn, key, data)


def check(server, conn, phase):
    from .battle_campaigns import save
    from .shared_campaigns import load, store, complete_stage
    from .region_characters import scoped
    key, data, node = current(server, conn)
    goal = node['expedition']; watch = data.get('expedition_watch', {})
    if watch.get('node') != data['node'] or watch.get('definition') != goal['definition']:
        raise ValueError('Every party member must ready before the world change')
    if phase not in goal['resolutions']:
        raise ValueError('Unknown expedition resolution')
    state = conn.get('state')
    if (server.peers.get(conn.get('id')) is not conn or conn.get('closing') or not state or not state[6]
        or not 0 <= time.monotonic() - conn.get('state_time', 0) <= 5 or conn.get('character_pending')):
        raise ValueError('Stand ready beside the actual mechanism')
    network = mechanisms.definition(server, goal['network'])
    if not any(o['id'] in network['objects'] and state[:2] == [o['group'], o['num']]
        and abs(state[2]-o['x']) + abs(state[3]-o['y']) <= 1
        and scoped(server, conn, o, o.get('region_revision')) for o in server.objects):
        raise ValueError('Observe the exact admitted mechanism nearby')
    if server.module_state.get('world_object_network_state', {}).get(goal['network'], {}).get('phase') != phase:
        raise ValueError('World outcome changed. Inspect the current expedition again')
    receipt = server.db.execute('SELECT request,seq FROM campaign_mechanism_receipts WHERE network=? AND definition=? AND phase=? AND seq>? ORDER BY seq DESC LIMIT 1',
        (goal['network'], goal['definition'], phase, watch['after'])).fetchone()
    if not receipt:
        raise ValueError('No new admitted resolution after the party became ready')
    record = dict(node=data['node'], network=goal['network'], phase=phase, request=receipt[0], seq=receipt[1],
        basis='committed_world_transition_witness', presence='client_reported', attribution='shared_world_not_personal_action')
    with server.db:
        if data.get('shared'):
            group = load(server, data['shared']); checkpoint = group.get('expedition', {})
            if checkpoint.get('node') != data['node'] or checkpoint.get('definition') != goal['definition']:
                raise ValueError('Party expedition changed')
            if checkpoint.get('phase', phase) != phase:
                raise ValueError('Party already witnessed another resolution. Restore that state or cancel')
            checkpoint['phase'] = phase
            store(server, data['shared'], group)
            complete_stage(server, conn, key, data, 1, record)
        else:
            data['history'].append(record)
            choices = goal['resolutions'][phase]['next']
            data.update(status='choice' if choices else 'complete', choices=choices)
            save(server, conn, key, data)


def rows(server, data, node):
    goal = node['expedition']
    out = [(goal['label'], None), ('Actual world changes decide the next leg. No party, item or story save is changed.', None)]
    network = mechanisms.definition(server, goal['network'])
    out.append((mechanisms.location(server,network),None))
    for phase, resolution in goal['resolutions'].items():
        out.append((resolution['label'] + '. Then ' + (', '.join(resolution['next']) or 'finish expedition'), None))
    if data.get('shared'):
        from .shared_campaigns import load
        group = load(server, data['shared'])
        checkpoint = group.get('expedition', {})
        if checkpoint.get('node') == data['node']:
            out.append(('Ready trainers ' + str(len(checkpoint['ready'])) + '/' + str(len(group['members'])) + '. Wait for everyone before acting.', None))
            if 'phase' in checkpoint:
                out.append(('Party resolution: ' + goal['resolutions'][checkpoint['phase']]['label'], None))
    if data.get('expedition_ready') != data['node']:
        out.append(('Ready. Share my nearby world observations with this run.', ['expedition-ready']))
    elif data.get('expedition_watch', {}).get('node') != data['node']:
        out.append(('Waiting for all trainers. Earlier changes will not count.', None))
    else:
        out.append(('Explore and act normally. Return here to witness a committed outcome.', None))
        phase = server.module_state.get('world_object_network_state', {}).get(goal['network'], {}).get('phase')
        if phase in goal['resolutions']:
            out.append(('Witness ' + goal['resolutions'][phase]['label'], ['expedition-check', phase]))
    return out
