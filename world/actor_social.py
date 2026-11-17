"""Local interaction with independently controlled, existing world actors."""
from .characters import records
from .character_walks import walking


def participants(server,actor,args):
    rows=records(server.module_state);source=rows.get(actor);target=rows.get(args['target'])
    obj=next((o for o in server.objects if o['id']==actor),None)
    other=next((o for o in server.objects if o['id']==args['target']),None)
    if (args['target']==actor or not source or source['status']!='active' or not target or target['status']!='active'
        or type(args['expected_version']) is not int or target['version']!=args['expected_version'] or not obj or not other
        or not obj.get('region_revision') or any(obj.get(k)!=other.get(k) for k in ('group','num','region_revision'))):
        raise ValueError('Interaction needs distinct active characters on the same exact generated map and inspected target version')
    if any(walking(server.module_state,a) for a in (actor,args['target'])):
        raise ValueError('Wait for the characters to finish moving')
    if any(p.get('character_pending',{}).get('id') in (actor,args['target']) for p in server.peers.values() if type(p.get('character_pending')) is dict):
        raise ValueError('A character is busy with a player battle')
    return source,obj,target,other


def approach(server,actor,row,args):
    from .actor_navigation import route,stage
    if set(args)!={'target','expected_version'}:raise ValueError('Approach requires target and expected_version')
    source,obj,target,other=participants(server,actor,args)
    if abs(obj['x']-other['x'])+abs(obj['y']-other['y'])==1:
        return dict(outcome='already_adjacent',target=args['target'],recipient_version=target['version'],revision=obj['region_revision'],x=obj['x'],y=obj['y'])
    routes=[]
    for x,y in ((other['x']-1,other['y']),(other['x']+1,other['y']),(other['x'],other['y']-1),(other['x'],other['y']+1)):
        try:routes.append(route(server,actor,[x,y],obj['region_revision'])[2])
        except ValueError:continue
    if not routes:raise ValueError('No supported route to an adjacent unoccupied destination')
    path=min(routes,key=lambda p:(len(p),p[-1]))
    pending=stage(server,actor,source,obj,path,obj['region_revision'])
    pending.data.update(target=args['target'],recipient_version=target['version'])
    return pending


def poll_approach(server,actor,row,pending):
    from .actor_navigation import poll
    result=poll(server,actor,row,pending)
    if result is None:return None
    # Arrival is real even if the recipient subsequently moved. Address is a
    # separate action and always validates the recipient again.
    result.update(target=pending['target'],recipient_version=pending['recipient_version'],limits='Arrived at chosen approach cell; inspect or address to verify recipient presence now.')
    return result


def address(server,actor,row,args):
    from .character_encounters import validate_control,deliver
    if set(args)!={'target','expected_version','text'}:raise ValueError('Address requires target, expected_version and public text')
    validate_control(dict(meeting=args),actor)
    source,obj,target,other=participants(server,actor,args)
    if abs(obj['x']-other['x'])+abs(obj['y']-other['y'])!=1:raise ValueError('Characters are not adjacent; approach first')
    return deliver(server,actor,obj,args,server.module_state,server.objects,dict(channel='actor_local_address',speaker_version=source['version']))
