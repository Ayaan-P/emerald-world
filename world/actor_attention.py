"""Persistent local attention to sampled authority state, not global perception."""
import json,time
from .actor_observation import observe

BASIS='sampled_local_authority_state'


def visible(entity):
    # Compare visible public content, not source hashes or thought-only versions.
    return {key:entity.get(key) for key in ('id','x','y','gfx','text','kind','actions','cave_link')}


def setup(db):
    db.execute('CREATE TABLE IF NOT EXISTS actor_attention(actor TEXT PRIMARY KEY,radius INTEGER,cooldown INTEGER,baseline TEXT,last_event REAL)')


def configure(server,actor,row,args):
    if set(args)!={'mode','radius','cooldown'} or args['mode'] not in ('local','off') or type(args['radius']) is not int or not 1<=args['radius']<=4 or type(args['cooldown']) is not int or not 30<=args['cooldown']<=3600:
        raise ValueError('Choose local/off, radius 1..4 and cooldown 30..3600 seconds')
    setup(server.db)
    if args['mode']=='off':
        server.db.execute('DELETE FROM actor_attention WHERE actor=?',(actor,))
        return dict(outcome='local_attention_stopped',character_id=actor)
    snapshot=observe(server,actor,row,dict(radius=args['radius']))
    if not server.db.execute('SELECT 1 FROM actor_attention WHERE actor=?',(actor,)).fetchone() and server.db.execute('SELECT count(*) FROM actor_attention').fetchone()[0]>=32:
        raise ValueError('At most 32 active local attention registrations')
    server.db.execute('INSERT OR REPLACE INTO actor_attention VALUES(?,?,?,?,?)',(actor,args['radius'],args['cooldown'],json.dumps(snapshot,sort_keys=True),time.time()))
    return dict(outcome='local_attention_started',character_id=actor,revision=snapshot['revision'],radius=args['radius'],cooldown=args['cooldown'],
        limits='Future sampled nearby public entity/weather changes only. Initial baseline is not a new encounter. No player identity, private state, rendered sight or guaranteed model response.')


def discover(server):
    setup(server.db)
    return [dict(actor=a,radius=r,cooldown=c,revision=json.loads(b)['revision']) for a,r,c,b in server.db.execute('SELECT actor,radius,cooldown,baseline FROM actor_attention ORDER BY actor')]


def tick(server,now=None):
    from .characters import records
    from .character_walks import walking
    now=time.time() if now is None else now
    setup(server.db);actors=records(server.module_state);emitted=[]
    for actor,radius,cooldown,raw,last in server.db.execute('SELECT * FROM actor_attention ORDER BY actor').fetchall():
        row=actors.get(actor)
        if not row or row['status']!='active':
            with server.db:server.db.execute('DELETE FROM actor_attention WHERE actor=?',(actor,))
            continue
        # A script/battle or ongoing walk is not a stationary sensory sample.
        if walking(server.module_state,actor) or any(type(p.get('character_pending')) is dict and p['character_pending'].get('id')==actor for p in server.peers.values()):continue
        try:current=observe(server,actor,row,dict(radius=radius))
        except ValueError:continue
        previous=json.loads(raw)
        if any(current[k]!=previous[k] for k in ('revision','x','y')) or now<last:
            # Rebase after movement, revision changes or clock rollback. Never
            # infer everybody departed the old place or appeared at the new one.
            with server.db:server.db.execute('UPDATE actor_attention SET baseline=?,last_event=? WHERE actor=?',(json.dumps(current,sort_keys=True),now,actor))
            continue
        if now-last<cooldown:continue
        old={e['id']:e for e in previous['entities']};new={e['id']:e for e in current['entities']}
        entered=[new[k] for k in sorted(new.keys()-old.keys())]
        absent=[old[k] for k in sorted(old.keys()-new.keys())]
        changed=[dict(before=old[k],after=new[k]) for k in sorted(old.keys()&new.keys()) if visible(old[k])!=visible(new[k])]
        weather=current['weather']!=previous['weather']
        if not (entered or absent or changed or weather):continue
        with server.db:
            seq=server.memory.append('character_surroundings_changed',dict(character_id=actor,character_version=row['version'],revision=current['revision'],position=[current['x'],current['y']],radius=radius,
                entered=entered,no_longer_observed=absent,changed=changed,weather_before=previous['weather'],weather_now=current['weather'],
                from_revision=previous['observed_revision'],observed_revision=current['observed_revision'],basis=BASIS,
                limits='Difference between bounded local authority samples, not an exhaustive timeline, rendered eyesight, completed meeting or proof of departure. No player data. Reinspect before acting.'))
            server.db.execute('UPDATE actor_attention SET baseline=?,last_event=? WHERE actor=?',(json.dumps(current,sort_keys=True),now,actor))
        server.revision=seq;emitted.append(seq)
    return emitted


def relevant(event,actor):
    return event.get('event')=='character_surroundings_changed' and event.get('character_id')==actor and event.get('basis')==BASIS
