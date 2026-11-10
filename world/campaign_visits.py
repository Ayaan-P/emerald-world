"""Voluntary campaign check-ins from fresh presence, not verified travel or lore."""
import time


def validate(server,node):
    from .build_catalog import validate_coords
    if set(node)-{'visit','next'} or not {'visit','next'}<=set(node):raise ValueError('Visit node requires visit and next routes')
    visit=node['visit']
    if type(visit) is not dict or set(visit)!={'label','point'}:raise ValueError('Visit requires label and point')
    if type(visit['label']) is not str or not 1<=len(visit['label'])<=40 or any(not 32<=ord(c)<127 for c in visit['label']):raise ValueError('Use a literal destination label')
    point=visit['point']
    if type(point) is not list or len(point)!=4 or any(type(v) is not int for v in point):raise ValueError('Use integer map group, map number, x and y')
    validate_coords(*point)
    if tuple(point[:2]) in (tuple(server.cave_map),tuple(server.wilds_map)):raise ValueError('Visit stages require stable ordinary maps, not generated aliases')


def describe(node):
    v=node['visit'];g,n,x,y=v['point']
    return ['Visit '+v['label'],f'Destination map {g} {n} tile {x} {y}.', 'Travel normally, then check in. Presence is client-reported, not proof of a journey.']


def check_in(server,conn,current):
    from .battle_campaigns import document,save,routes
    if not current or current[1]['status']!='ready':raise ValueError('No active visit stage ready for check-in')
    key,data=current;node=document(server,key)['nodes'][data['node']]
    if 'visit' not in node:raise ValueError('Current stage requires its normal battle')
    state=conn.get('state')
    if (server.peers.get(conn.get('id')) is not conn or conn.get('closing') or not state or not state[6]
        or not 0<=time.monotonic()-conn.get('state_time',0)<=5 or state[:4]!=node['visit']['point'] or conn.get('character_pending')):
        raise ValueError('Stand ready at the exact destination with a fresh world connection')
    record=dict(node=data['node'],point=list(state[:4]),basis='voluntary_fresh_client_presence',outcome='checked_in')
    with server.db:
        if data.get('shared'):
            from .shared_campaigns import complete_stage
            complete_stage(server,conn,key,data,1,record)
        else:
            data['history'].append(record);choices=routes(node)
            data.update(choices=choices,status='choice' if choices else 'complete')
            save(server,conn,key,data)
