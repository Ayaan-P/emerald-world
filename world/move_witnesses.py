"""Receipt-grounded local move notices, not rendered sight or party inspection."""
import json,time
from .actor_observation import observe
BASIS='local_authority_snapshot_at_move_admission'

def setup(db):
    db.execute('CREATE TABLE IF NOT EXISTS move_attention(actor TEXT PRIMARY KEY,radius INTEGER,cooldown INTEGER,last REAL,pending TEXT,omitted INTEGER)')

def configure(server,actor,row,args):
    if (set(args)!={'mode','radius','cooldown'} or args['mode'] not in ('local','off')
        or type(args['radius']) is not int or not 1<=args['radius']<=4
        or type(args['cooldown']) is not int or not 30<=args['cooldown']<=3600):
        raise ValueError('Choose local/off, connected radius 1..4 and cooldown 30..3600 seconds')
    setup(server.db)
    if args['mode']=='off':
        server.db.execute('DELETE FROM move_attention WHERE actor=?',(actor,))
        return dict(outcome='move_attention_stopped',character_id=actor)
    current=observe(server,actor,row,dict(radius=args['radius']))
    if not server.db.execute('SELECT 1 FROM move_attention WHERE actor=?',(actor,)).fetchone() and server.db.execute('SELECT count(*) FROM move_attention').fetchone()[0]>=32:
        raise ValueError('At most 32 move observers')
    # Explicit reconfiguration starts fresh; never replay earlier world events.
    server.db.execute('INSERT OR REPLACE INTO move_attention VALUES(?,?,?,?,?,0)',(actor,args['radius'],args['cooldown'],time.time(),'[]'))
    return dict(outcome='move_attention_started',character_id=actor,revision=current['revision'],radius=args['radius'],cooldown=args['cooldown'],limits='Future committed public move actions at locally reachable objects only. Not rendered sight, private party inspection, guaranteed response or belief in a client claim.')

def discover(server):
    setup(server.db)
    return [dict(actor=a,radius=r,cooldown=c,pending=len(json.loads(p)),omitted=n) for a,r,c,p,n in server.db.execute('SELECT actor,radius,cooldown,pending,omitted FROM move_attention ORDER BY actor')]

def admitted(server,identity,seq,object_id,evidence):
    """Called inside object admission's transaction, before new objects replace old.

    Records the observer's actual pre-effect locality, including a stationary
    target that a valid action subsequently moves. No notice from failed effects.
    """
    from .characters import records
    from .character_walks import walking
    setup(server.db);cast=records(server.module_state)
    for actor,radius,raw,omitted in server.db.execute('SELECT actor,radius,pending,omitted FROM move_attention ORDER BY actor').fetchall():
        row=cast.get(actor)
        if not row or row['status']!='active' or walking(server.module_state,actor):continue
        if evidence.get('character_id')==actor:continue # Own action already has its receipt.
        if any(type(p.get('character_pending')) is dict and p['character_pending'].get('id')==actor for p in server.peers.values()):continue
        try:snapshot=observe(server,actor,row,dict(radius=radius))
        except ValueError:continue
        obj=next((o for o in snapshot['entities'] if o['id']==object_id),None)
        if obj is None:continue
        pending=json.loads(raw)
        # Only public causal identifiers, not private party or native blob state.
        notice=dict(receipt=seq,request=identity,object=object_id,move=evidence['move'],basis=evidence['basis'],revision=snapshot['revision'],observer_position=[snapshot['x'],snapshot['y']],target_position=[obj['x'],obj['y']],observer_version=row['version'])
        for key in ('trainer_id','character_id'):
            if key in evidence:notice[key]=evidence[key]
        if len(pending)<8:pending.append(notice)
        else:omitted+=1
        server.db.execute('UPDATE move_attention SET pending=?,omitted=? WHERE actor=?',(json.dumps(pending,sort_keys=True),omitted,actor))

def tick(server,now=None):
    from .characters import records
    setup(server.db);now=time.time() if now is None else now;cast=records(server.module_state);result=[]
    for actor,cooldown,last,raw,omitted in server.db.execute('SELECT actor,cooldown,last,pending,omitted FROM move_attention ORDER BY actor').fetchall():
        row=cast.get(actor)
        if not row or row['status']!='active':
            with server.db:server.db.execute('DELETE FROM move_attention WHERE actor=?',(actor,))
            continue
        if now<last:
            with server.db:server.db.execute('UPDATE move_attention SET last=? WHERE actor=?',(now,actor))
            continue
        pending=json.loads(raw)
        if not pending or now-last<cooldown:continue
        with server.db:
            seq=server.memory.append('character_moves_noticed',dict(character_id=actor,character_version=row['version'],basis=BASIS,moves=pending,omitted=omitted,limits='Historical local authority snapshots of committed shared object effects, not rendered sight or current proximity. Player learned-move claims remain client-reported. Omitted notices are not summarized; original receipts remain in public history. No reaction, relationship, PP or growth inferred. Reobserve before acting.'))
            server.db.execute('UPDATE move_attention SET last=?,pending=?,omitted=0 WHERE actor=?',(now,'[]',actor))
        server.revision=seq;result.append(seq)
    return result

def relevant(event,actor):
    return event.get('event')=='character_moves_noticed' and event.get('character_id')==actor and event.get('basis')==BASIS
