"""Rydel's optional route board. Reuses races; never moves players or starts models."""
import json
import secrets
import re
import time


def relevant(event, identity):
    return (identity == 'canon_rydel' and event.get('event') == 'route_finish_shared'
            and event.get('basis') == 'explicit_own_committed_race_record'
            and type(event.get('course')) is str and type(event.get('milliseconds')) is int
            and 0 <= event['milliseconds'] <= 1800000
            and event.get('publication') == 'anonymous_public_finish')


def _install(db):
    db.execute('CREATE TABLE IF NOT EXISTS route_finish_shares(trainer TEXT,run TEXT,seq INTEGER NOT NULL,PRIMARY KEY(trainer,run))')


def panel(server, conn, run, key, guard):
    if (key != 'rydel' or server.peers.get(conn.get('id')) is not conn
            or conn.get('closing') or conn.get('core_active_run') != run):
        raise ValueError('Current authenticated Rydel visit required')
    server.core_story._place(conn, 'MauvilleCity_BikeShop')
    if server.link_protocol.busy(conn['id']):
        raise ValueError('Finish the native activity first')
    now=time.monotonic()
    old=conn.get('rydel_board')
    action=('home',)
    if guard != 'view':
        words=guard.split(':')
        if (not old or old['run']!=run or old['until']<now or len(words)!=4
                or words[:3]!=['pick',old['token'],str(old['version'])]
                or words[3] not in [str(i+1) for i in range(len(old['actions']))]):
            raise ValueError('Board changed. Open it again')
        action=old['actions'][int(words[3])-1]
    # Every response rotates its lease; old confirmation messages cannot execute twice.
    conn.pop('rydel_board',None)
    races=server.races
    labels=[]; actions=[]
    question='Rydel route board. Optional field races. Original bike service is unchanged.'
    def option(label, *args):
        labels.append(label);actions.append(args)
    kind=action[0]
    if kind=='start':
        for line in races.command(conn,['start',action[1]]):server.guild_chat.message(conn,conn['id'],line[:120])
        question='Race lobby opened. Directions sent to private chat. Exit the shop and visit your start pad. Ready there when you choose.'
    elif kind=='join':
        for line in races.command(conn,['join',action[1]]):server.guild_chat.message(conn,conn['id'],line[:120])
        question='Joined the guild race. Directions sent to private chat. Exit the shop and visit your pad. Ready there when you choose.'
    elif kind=='share':
        # Select only this authenticated trainer's committed record. No partner rows.
        _install(server.db)
        record=server.db.execute('SELECT course,milliseconds,splits FROM race_results WHERE run=? AND trainer=?',(action[1],conn['id'])).fetchone()
        if not record or tuple(record)!=tuple(action[2:]):raise ValueError('Finish changed')
        seq=None
        with server.db:
            if not server.db.execute('SELECT 1 FROM route_finish_shares WHERE trainer=? AND run=?',(conn['id'],action[1])).fetchone():
                seq=server.memory.append('route_finish_shared',dict(course=record[0],milliseconds=record[1],
                    basis='explicit_own_committed_race_record',publication='anonymous_public_finish',
                    limits='Recreational client movement reports, not anti-cheat proof. No partner result, rank, bike type or original Cycling Road record is implied.',
                    places=['native:MauvilleCity_BikeShop']))
                server.db.execute('INSERT INTO route_finish_shares VALUES(?,?,?)',(conn['id'],action[1],seq))
        if seq is not None:server.revision=seq
        question='Your anonymous finish is now public world history. Rydel may respond independently. No reward or response is promised.'
    elif kind=='finish':
        record=server.db.execute('SELECT run,course,milliseconds,splits FROM race_results WHERE trainer=? ORDER BY rowid DESC LIMIT 1',(conn['id'],)).fetchone()
        if record:
            question=f'Share {record[2]/1000:.2f}s on {record[1]} with ALL players and authors permanently? No name or partner results.'
            option('Publish this finish', 'share', *record)
        else:question='No completed private race record to share. Nothing from an unfinished race can be published.'
    elif kind=='courses':
        courses=races.catalog()
        if courses:
            index=action[1]%len(courses);course=courses[index]
            question=f"{course['title']}. {len(course['starts'])} racers, {course['laps']} laps, {course['limit']} seconds. " + ('Requires a Pokemon mount.' if course['mounted'] else 'Walking or native bikes allowed.')
            option('Review start and rules','course',course['id'])
            option('Next course','courses',index+1)
        else:question='No authored courses yet. Original cycling and bike services remain available.'
    elif kind=='course':
        course=races.course(action[1]);p=course['starts'][0]
        question=f"Start {races.coords(*p)['name'][:45]} {p[2]},{p[3]}. No teleport or rewards. Ready at your pad. Route walkability is unverified."
        option('Open this race lobby','start',course['id'])
    elif kind=='join_preview':
        guild=server.guilds._require(conn['id'])
        lobby=next((r for r in races.runs.values() if r['guild']==guild[0] and r['phase']=='lobby' and len(r['members'])<len(r['course']['starts'])),None)
        if lobby:
            question=lobby['course']['title']+'. Join this guild lobby? Travel and readiness are your choice. No transport.'
            option('Join this lobby','join',lobby['id'])
        else:question='No open guild race lobby. Current races and ordinary play are unchanged.'
    if kind=='home':
        option('Browse authored courses','courses',0)
        option('Review a guild race','join_preview')
        option('Share my last finish','finish')
    else:option('Back to route board','home')
    version=(old['version']+1 if old else 1)
    token=secrets.token_hex(4)
    conn['rydel_board']=dict(run=run,until=now+60,token=token,version=version,actions=actions)
    # Match the existing bounded native panel encoding, never arbitrary commands.
    question=re.sub(r"[^a-zA-Z0-9 .,'!?-]", ' ', question)
    if len(question)>160:raise ValueError('Route board message too long')
    return dict(world_id=server.memory.world_id,version=version,session=token,role=4,
                question=question,options=[dict(label=l,advice=0) for l in labels])
