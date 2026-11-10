"""Occupancy-aware destination travel over real, single-step native journeys."""
import hashlib,json
from . import actor_navigation
from .characters import records


def setup(db):
    db.execute('CREATE TABLE IF NOT EXISTS actor_adaptive_navigation(id TEXT PRIMARY KEY,actor TEXT,data TEXT)')


def position(character,obj):
    return dict(version=character['version'],revision=obj['region_revision'],x=obj['x'],y=obj['y'])


def occupied(server,revision):
    return {(p['x'],p['y']) for p in server.inspect()['players'] if p.get('generated_place',{}).get('revision')==revision}


def start(server,actor,row,args):
    from .actor_runtime import Pending
    if set(args)!={'revision','x','y','max_steps'} or type(args['max_steps']) is not int or not 1<=args['max_steps']<=256:
        raise ValueError('Supply exact generated revision, destination and 1..256 actual-step allowance')
    current,obj,path=actor_navigation.route(server,actor,[args['x'],args['y']],args['revision'],avoid=occupied(server,args['revision']))
    execution=getattr(server,'actor_tool_execution',None)
    if not execution or execution[0]!=actor:raise ValueError('Durable actor execution required')
    key=hashlib.sha256(json.dumps([server.memory.world_id,actor,execution[2]['id'],execution[3]['id']]).encode()).hexdigest()
    setup(server.db)
    data=dict(target=args,expected=position(current,obj),active=None,halting=None,steps=0,reroutes=0,last_receipt=None)
    server.db.execute('INSERT INTO actor_adaptive_navigation VALUES(?,?,?)',(key,actor,json.dumps(data)))
    return Pending(dict(journey=key),lambda:None)


def save(server,key,data):
    server.db.execute('UPDATE actor_adaptive_navigation SET data=? WHERE id=?',(json.dumps(data,sort_keys=True),key))


def poll(server,actor,row,pending):
    setup(server.db);found=server.db.execute('SELECT actor,data FROM actor_adaptive_navigation WHERE id=?',(pending['journey'],)).fetchone()
    if not found or found[0]!=actor:raise ValueError('Adaptive journey unavailable')
    data=json.loads(found[1]);obj=next((o for o in server.objects if o['id']==actor),None);current=records(server.module_state).get(actor,{})
    if not obj or current.get('status')!='active' or obj.get('region_revision')!=data['target']['revision']:
        raise ValueError('Actor or exact scope changed; inspect and replan')
    if any(type(p.get('character_pending')) is dict and p['character_pending'].get('id')==actor for p in server.peers.values()):return None
    control=server.module_state.get('world_character_controls',{}).get(actor,{})
    if data['halting']:
        if control.get('journey') or position(current,obj)!=data['halting']:
            raise ValueError('Owned blocked step halt was not admitted; no reroute or arrival claimed')
        data['active']=None;data['expected']=position(current,obj);data['halting']=None;data['reroutes']+=1
        save(server,pending['journey'],data)
    if data['active']:
        active=data['active'];result=actor_navigation.poll(server,actor,row,active)
        if result is None:
            next_tile=tuple(active['destination'])
            blocked=any(o['id']!=actor and o.get('region_revision')==obj['region_revision'] and (o['x'],o['y'])==next_tile for o in server.objects)
            blocked=blocked or any(p.get('generated_place',{}).get('revision')==obj['region_revision'] and (p['x'],p['y'])==next_tile for p in server.inspect()['players'])
            if blocked:
                from .npc_guidance import halt
                # Never rewrite an active movement path in place. Admit an
                # explicit stop at its real current tile before selecting again.
                halt(server,actor,current,obj,reason='Replan an owned blocked navigation step at its actual current tile.')
                data['halting']=dict(position(current,obj),version=current['version']+1)
                save(server,pending['journey'],data)
            return None
        if position(current,obj)!=dict(version=active['version']+1,revision=result['revision'],x=result['x'],y=result['y']):
            raise ValueError('Actor changed outside its admitted step')
        data['steps']+=1;data['last_receipt']=result['arrival_receipt'];data['active']=None;data['expected']=position(current,obj)
        save(server,pending['journey'],data)
    if data['expected']!=position(current,obj):raise ValueError('Actor changed outside adaptive navigation; inspect and replan')
    target=data['target'];arrived=(obj['x'],obj['y'])==(target['x'],target['y'])
    if arrived or data['steps']>=target['max_steps']:
        return dict(outcome='authority_arrived' if arrived else 'navigation_step_budget_exhausted',revision=obj['region_revision'],x=obj['x'],y=obj['y'],steps=data['steps'],reroutes=data['reroutes'],last_arrival_receipt=data['last_receipt'],limits='Actual admitted cardinal steps only, not rendered animation or canonical/cross-map travel.')
    try:_,_,path=actor_navigation.route(server,actor,[target['x'],target['y']],target['revision'],avoid=occupied(server,target['revision']))
    except ValueError:return None # Real occupancy may leave no route. Wait, never teleport.
    operation=actor_navigation.stage(server,actor,current,obj,path[:2],target['revision'])
    data['active']=operation.data;save(server,pending['journey'],data);operation.dispatch()
    return None
