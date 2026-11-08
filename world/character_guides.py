"""Private resident guidance over actual archived survey geometry; never publication."""
from collections import deque
import json
import time


def handle(server,conn,text):
    """Consume guide commands privately before the ordinary survey dispatcher."""
    command=text.split()
    if not command or command[0]!='/explore':return False
    if command[1:2] not in (['guide'],['directions']):return False
    with server.lock:
        if command[1:2]==['guide'] and len(command)==3:
            lines=guide(server,conn,command[2])
        elif command[1:]==['directions']:
            lines=directions(server,conn)
        else:
            lines=['Use /explore guide NPC_ID or /explore directions.']
        server.landmark_survey.reply(conn,lines)
    return True


def guide(server,conn,identity):
    from .characters import records
    survey=server.landmark_survey
    revision=survey.scope(conn);state=conn.get('state')
    if (revision is None or server.peers.get(conn.get('id')) is not conn or conn.get('closing')
            or not 0<=time.monotonic()-conn.get('state_time',0)<=5):
        return ['Stand ready in your acknowledged survey destination to ask a guide.']
    character=records(server.module_state).get(identity)
    obj=next((o for o in server.objects if o['id']==identity),None)
    if (not character or character['status']!='active' or 'guide' not in character.get('services',[])
            or obj is None or obj.get('region_revision')!=revision or state[:2]!=[obj['group'],obj['num']]):
        return ['That resident is not available as a guide in this place.']
    dx,dy={1:(0,1),2:(0,-1),3:(-1,0),4:(1,0)}.get(state[4],(0,0))
    motion=server.module_state.get('world_character_controls',{}).get(identity,{}).get('walk')
    if ((state[2]+dx,state[3]+dy)!=(obj['x'],obj['y']) or
            (motion and motion['index']<len(motion['path'])-1)):
        return ['Stand beside and face the resting guide before asking.']
    session=server.db.execute('SELECT revision,active FROM survey_sessions WHERE trainer=?',(conn['id'],)).fetchone()
    if session!=(revision,1):
        return ['Use /explore start first. Guidance uses only your active private survey.']
    row=server.db.execute('SELECT sites FROM survey_routes WHERE revision=?',(revision,)).fetchone()
    if row is None:return ['No survey is registered for this exact destination.']
    seen={r[0] for r in server.db.execute('SELECT landmark FROM survey_visits WHERE trainer=? AND revision=?',(conn['id'],revision))}
    sites=[p for p in json.loads(row[0]) if p['id'] not in seen]
    if not sites:return ['You have already discovered every clearing in this survey.']
    return _directions(server,conn,revision,sites,identity)


def directions(server,conn):
    revision=server.landmark_survey.scope(conn)
    if revision is None:return ['Enter the exact acknowledged destination to read your guide notes.']
    _schema(server)
    note=server.db.execute('SELECT revision,landmark,guide FROM survey_guidance WHERE trainer=?',(conn['id'],)).fetchone()
    session=server.db.execute('SELECT revision,active FROM survey_sessions WHERE trainer=?',(conn['id'],)).fetchone()
    if note is None:return ['Ask an adjacent resident with /explore guide NPC_ID first.']
    if note[0]!=revision or session!=(revision,1):return ['Resume your private survey in the same destination to use these notes.']
    if server.db.execute('SELECT 1 FROM survey_visits WHERE trainer=? AND revision=? AND landmark=?',(conn['id'],revision,note[1])).fetchone():
        return ['You reached the clearing in your guide notes. That discovery remains private.']
    row=server.db.execute('SELECT sites FROM survey_routes WHERE revision=?',(revision,)).fetchone()
    sites=[site for site in json.loads(row[0]) if site['id']==note[1]] if row else []
    return _directions(server,conn,revision,sites,None)


def _schema(server):
    server.db.execute('CREATE TABLE IF NOT EXISTS survey_guidance (trainer TEXT PRIMARY KEY, revision TEXT NOT NULL, landmark TEXT NOT NULL, guide TEXT NOT NULL)')


def _directions(server,conn,revision,sites,guide_identity):
    state=conn['state']
    cave=server._connection_cave(conn);start=tuple(state[2:4])
    blocked={(o['x'],o['y']) for o in server.objects if o.get('region_revision')==revision}
    now=time.monotonic()
    for other in server.peers.values():
        position=other.get('state')
        if (other is not conn and not other.get('closing') and position and position[6]
                and 0<=now-other.get('state_time',0)<=5 and server._region_scope(other)==revision):
            blocked.add(tuple(position[2:4]))
    targets={}
    for site in sorted(sites,key=lambda p:p['id']):
        x,y=site['x'],site['y']
        for point in ((x,y),(x-1,y),(x+1,y),(x,y-1),(x,y+1)):
            if point not in blocked and cave.walkable(*point):targets.setdefault(point,site['id'])
    frontier=deque([start]);previous={start:None};finish=None
    while frontier:
        point=frontier.popleft()
        if point in targets:finish=point;break
        x,y=point
        for nxt in ((x,y-1),(x-1,y),(x+1,y),(x,y+1)):
            if nxt not in previous and nxt not in blocked and cave.walkable(*nxt):
                previous[nxt]=point;frontier.append(nxt)
    if finish is None:return ['No clear walking route is available right now. Try again when the path clears.']
    path=[];point=finish
    while point is not None:path.append(point);point=previous[point]
    path.reverse();turns=[];direction=None
    if guide_identity is not None:
        _schema(server)
        with server.db:server.db.execute('INSERT OR REPLACE INTO survey_guidance VALUES (?,?,?,?)',(conn['id'],revision,targets[finish],guide_identity))
    for old,new in zip(path,path[1:]):
        step=(new[0]-old[0],new[1]-old[1])
        if direction is not None and step!=direction:turns.append((direction,old))
        direction=step
    if direction is not None:turns.append((direction,finish))
    names={(0,-1):'north',(0,1):'south',(-1,0):'west',(1,0):'east'}
    lines=[f'Guide to {targets[finish]}: {len(path)-1} walking steps. Your survey stays private.']
    lines += [f'Walk {names[d]} to ({p[0]},{p[1]}).' for d,p in turns[:3]]
    lines.append('Use /explore directions for the next turns as you walk.')
    return lines
