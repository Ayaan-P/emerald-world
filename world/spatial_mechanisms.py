"""Fresh, exact-place spatial inputs for admitted shared object mechanisms.

Positions are client field attestations, not anti-cheat proof. No player IDs or
private save data enter the public mechanism state or the author context.
"""
import time


def validate(rules, states, cave, anchors):
    if type(rules) is not list or len(rules)>2:
        raise ValueError('At most two ordered spatial transitions per phase')
    for rule in rules:
        if (type(rule) is not dict or set(rule)!={'to','mode','occupied','hold','zones'}
            or type(rule['to']) is not str or rule['to'] not in states
            or rule['mode'] not in ('all','any') or type(rule['occupied']) is not bool
            or type(rule['hold']) is not int or not 1<=rule['hold']<=30
            or type(rule['zones']) is not list or not 1<=len(rule['zones'])<=4):
            raise ValueError('Invalid spatial transition')
        for zone in rule['zones']:
            if (type(zone) is not dict or set(zone)!={'x','y','radius','players','characters'}
                or any(type(v) is not int for v in zone.values())
                or not 0<=zone['radius']<=2 or not 0<=zone['players']<=4
                or not 0<=zone['characters']<=8 or not zone['players']+zone['characters']
                or not cave.walkable(zone['x'],zone['y'])
                or min(abs(zone['x']-x)+abs(zone['y']-y) for x,y in anchors)>4):
                raise ValueError('Use nearby walkable zones and bounded participant counts')


def transition(server, key, network, status):
    """Return one eligible phase; commit still passes normal geometry admission."""
    from .region_characters import scoped
    from .characters import records
    node=network['program']['states'][status['phase']]
    rules=node.get('when',[])
    if not rules:return None
    # New/replaced programs cannot act before their installation is committed.
    if server.module_state.get('world_object_networks',{}).get(key)!=network:return None
    objects={o['id']:o for o in server.objects}
    members=[objects.get(i) for i in network['objects']]
    if not all(members):return None
    anchor=members[0];revision=anchor.get('region_revision')
    if not revision or any(any(o.get(k)!=anchor.get(k) for k in ('group','num','region_revision')) for o in members):return None
    now=time.monotonic()
    holds=getattr(server,'_spatial_mechanism_holds',None)
    if holds is None:holds={};server._spatial_mechanism_holds=holds
    # Keep only current active networks; never retain a departed phase's timer.
    for old in list(holds):
        if old[0] not in server.module_state.get('world_object_networks',{}) or old[0]==key and old[1]!=status['phase']:holds.pop(old,None)
    players=[]
    for peer in server.peers.values():
        state=peer.get('state')
        if (not peer.get('closing') and state and state[6]
            and 0<=now-peer.get('state_time',0)<=3
            and scoped(server,peer,anchor,revision)):
            players.append(tuple(state[2:4]))
    actors=records(server.module_state)
    characters=[(o['x'],o['y']) for i,o in objects.items()
                if actors.get(i,{}).get('status')=='active'
                and all(o.get(k)==anchor.get(k) for k in ('group','num','region_revision'))]
    for index,rule in enumerate(rules):
        values=[]
        for zone in rule['zones']:
            near=lambda p:abs(p[0]-zone['x'])+abs(p[1]-zone['y'])<=zone['radius']
            values.append(sum(map(near,players))>=zone['players'] and sum(map(near,characters))>=zone['characters'])
        occupied=all(values) if rule['mode']=='all' else any(values)
        timer=(key,status['phase'],index)
        if occupied!=rule['occupied']:holds.pop(timer,None);continue
        since,last=holds.get(timer,(now,now))
        if now<last or now-last>3:since=now
        holds[timer]=(since,now)
        if now-since>=rule['hold']:
            target=network['program']['states'][rule['to']]['objects']
            changed={(v['x'],v['y']) for i,v in target.items()
                     if (v['x'],v['y'])!=(objects[i]['x'],objects[i]['y'])}
            # Busy/menu/stale trainers still physically occupy their last tile.
            # They cannot activate a sensor, but must never have a prop placed
            # under them. Postpone, rather than bypassing the normal validator.
            if any(not p.get('closing') and p.get('state')
                   and scoped(server,p,anchor,revision)
                   and tuple(p['state'][2:4]) in changed for p in server.peers.values()):
                continue
            return rule['to']
    return None
