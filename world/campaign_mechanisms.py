"""Campaign objectives witnessed from committed shared mechanisms, never claimed actions."""
import json,time
from .actor_objects import digest


def install(db):
    db.execute('CREATE TABLE IF NOT EXISTS campaign_mechanism_receipts(request TEXT PRIMARY KEY, network TEXT, definition TEXT, phase TEXT, seq INTEGER)')
    db.execute('CREATE INDEX IF NOT EXISTS campaign_mechanism_lookup ON campaign_mechanism_receipts(network,seq)')


def definition(server,key):
    network=server.module_state.get('world_object_networks',{}).get(key)
    if not network:raise ValueError('Shared mechanism is unavailable')
    return network


def fingerprint(server,network):
    regions={o['id']:o.get('region_revision') for o in server.objects if o['id'] in network['objects']}
    if set(regions)!=set(network['objects']) or any(not r for r in regions.values()):raise ValueError('All mechanism members must exist in admitted regions')
    return digest([network,regions])


def catalog(server):
    result=[]
    for key,network in server.module_state.get('world_object_networks',{}).items():
        try:bound=fingerprint(server,network)
        except ValueError:continue
        result.append(dict(network=key,definition=bound,phases=list(network['program']['states']),objects=list(network['objects']),current=server.module_state.get('world_object_network_state',{}).get(key,{}).get('phase')))
    return result


def validate(server,node):
    if set(node)!={'mechanism','next'}:raise ValueError('Mechanism stage requires mechanism and next')
    goal=node['mechanism']
    if type(goal) is not dict or set(goal)!={'network','phase','definition','label'}:raise ValueError('Use network, phase, definition digest and label')
    if any(type(v) is not str for v in goal.values()):raise ValueError('Mechanism objective uses literal strings')
    if not 1<=len(goal['label'])<=40 or any(not 32<=ord(c)<127 for c in goal['label']):raise ValueError('Use a short printable objective label')
    network=definition(server,goal['network'])
    if fingerprint(server,network)!=goal['definition'] or goal['phase'] not in network['program']['states']:raise ValueError('Bind an existing exact mechanism definition and phase')


def admitted(server,identity,seq,before,state):
    """Called only after the ordinary object receipt has passed admission validation."""
    install(server.db)
    receipt=state['world_object_current_receipt'][identity]
    for key,network in state.get('world_object_networks',{}).items():
        if receipt['object'] not in network['objects']:continue
        old=before.get('world_object_network_state',{}).get(key,{})
        new=state.get('world_object_network_state',{}).get(key,{})
        if network!=before.get('world_object_networks',{}).get(key) or old.get('phase')==new.get('phase'):return
        if new.get('turn')!=old.get('turn',0)+1:return
        server.db.execute('INSERT OR IGNORE INTO campaign_mechanism_receipts VALUES(?,?,?,?,?)',(identity,key,fingerprint(server,network),new['phase'],seq))
        return


def current(server,conn):
    from .battle_campaigns import active
    from .parallel_campaigns import effective
    run=active(server,conn)
    if not run or run[1]['status']!='ready':raise ValueError('No ready mechanism objective')
    key,data=run;node=effective(server,key,data)
    if 'mechanism' not in node:raise ValueError('This stage is not a shared mechanism objective')
    validate(server,node)
    return key,data,node


def arm(server,conn):
    from .battle_campaigns import save
    key,data,node=current(server,conn)
    if data.get('mechanism_watch',{}).get('node')==data['node']:raise ValueError('Already watching this stage; prior transitions cannot be reused')
    mark=server.db.execute('SELECT coalesce(max(seq),0) FROM events').fetchone()[0]
    data['mechanism_watch']=dict(node=data['node'],after=mark,definition=node['mechanism']['definition'])
    with server.db:save(server,conn,key,data)


def check(server,conn):
    from .battle_campaigns import save,routes
    from .region_characters import scoped
    key,data,node=current(server,conn);goal=node['mechanism'];watch=data.get('mechanism_watch',{})
    if watch.get('node')!=data['node'] or watch.get('definition')!=goal['definition']:raise ValueError('Begin watching before the world interaction')
    state=conn.get('state')
    if (server.peers.get(conn.get('id')) is not conn or conn.get('closing') or not state or not state[6]
        or not 0<=time.monotonic()-conn.get('state_time',0)<=5 or conn.get('character_pending')):raise ValueError('Stand ready beside the actual mechanism')
    network=definition(server,goal['network'])
    near=any(o['id'] in network['objects'] and state[:2]==[o['group'],o['num']] and abs(state[2]-o['x'])+abs(state[3]-o['y'])<=1
        and scoped(server,conn,o,o.get('region_revision')) for o in server.objects)
    if not near:raise ValueError('Observe the exact admitted mechanism nearby')
    if server.module_state.get('world_object_network_state',{}).get(goal['network'],{}).get('phase')!=goal['phase']:raise ValueError('The shared mechanism is not currently in the requested state')
    install(server.db)
    receipt=server.db.execute('SELECT request,seq FROM campaign_mechanism_receipts WHERE network=? AND definition=? AND phase=? AND seq>? ORDER BY seq DESC LIMIT 1',(goal['network'],goal['definition'],goal['phase'],watch['after'])).fetchone()
    if not receipt:raise ValueError('No new admitted interaction reached this state since you began watching')
    record=dict(node=data['node'],network=goal['network'],phase=goal['phase'],request=receipt[0],seq=receipt[1],basis='committed_world_transition_witness',presence='client_reported',attribution='shared_world_not_personal_action')
    with server.db:
        if data.get('shared'):
            from .shared_campaigns import complete_stage
            complete_stage(server,conn,key,data,1,record)
        else:
            data['history'].append(record);choices=routes(node)
            data.update(choices=choices,status='choice' if choices else 'complete');save(server,conn,key,data)


def rows(server,data,node):
    goal=node['mechanism'];watch=data.get('mechanism_watch',{}).get('node')==data['node']
    return [(goal['label']+' - '+goal['network']+' / '+goal['phase'],None),
        ('Use the real shared mechanism. Moves, choices and cooperative requirements are unchanged.',None),
        ('This records a witnessed world change, not proof you caused it. Party members witness separately.',None),
        ('Check the committed change nearby',['mechanism-check']) if watch else ('Begin watching future changes',['mechanism-watch'])]
