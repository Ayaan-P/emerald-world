"""Original-NPC field access to its actual local shared project choices."""
import secrets,time
from .canonical_cast import location,records,check_actor_location


def panel(server,conn,run,key,guard):
    actor,place=location(key);row=records(server.module_state).get(actor)
    reached=conn.get('canonical_location') or {}
    if (not row or reached.get('actor')!=actor or reached.get('run')!=run
            or conn.get('core_active_run')!=run or reached.get('version')!=row['version']
            or reached.get('map')!=place or reached.get('expires',0)<time.monotonic()):
        raise ValueError('Project panel needs current original actor context')
    check_actor_location(server,conn,actor)
    project=row.get('initiative')
    if not project:raise ValueError('No owned project')
    owner=server.db.execute('SELECT actor FROM canonical_initiatives WHERE pack=?',(project['id'],)).fetchone()
    if owner!=(actor,):raise ValueError('Project ownership changed')
    parts=guard.split(':')
    if parts==['view']:
        conn.pop('cast_project_panel',None)
        offers=server.opportunities.offers(conn['id'],place,project['id'])
        if not offers:return result(server,row,'-',5,'No project choices are available here.',[dict(label='Return to normal conversation.',advice=0)])
        offered=offers[0];scene=offered['scenes'][0];token=secrets.token_hex(4)
        conn['cast_project_panel']=dict(token=token,actor=actor,run=run,version=row['version'],pack=project['id'],place=place,
            scene=scene['id'],choices=scene['choices'],revision=offered['revision'],expires=time.monotonic()+120)
        return result(server,row,token,4,scene['text'],[dict(label=c['text'],advice=0) for c in scene['choices']])
    pending=conn.get('cast_project_panel')
    if (not pending or len(parts)!=4 or parts[:3]!=['pick',pending['token'],str(row['version'])]
            or parts[3] not in ('1','2','3') or pending['actor']!=actor or pending['run']!=run
            or pending['place']!=place or pending['pack']!=project['id'] or pending['expires']<time.monotonic()):
        raise ValueError('Project choice changed; inspect again')
    index=int(parts[3])-1
    if index>=len(pending['choices']):raise ValueError('Unknown project choice')
    # Consume this connection's one-use UI offer even if current shared state refuses.
    conn.pop('cast_project_panel',None)
    outcome=server.opportunities.choose(conn['id'],place,pending['pack'],pending['scene'],pending['choices'][index]['id'],pending['revision'],'p'+pending['token'])
    return result(server,row,pending['token'],5,outcome['text'],[dict(label='Return to normal conversation.',advice=0)])


def result(server,row,token,role,question,options):
    return dict(world_id=server.memory.world_id,version=row['version'],session=token,role=role,question=question,options=options)
