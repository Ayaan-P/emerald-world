"""Provenance-preserving exchange of actual observations, never invented sightings."""
import json
from .actor_social import participants


def setup(db):
    db.execute('''CREATE TABLE IF NOT EXISTS actor_knowledge(
        recipient TEXT,sender TEXT,observation INTEGER,delivered INTEGER,snapshot TEXT,
        PRIMARY KEY(recipient,sender,observation))''')


def inbox(server):
    from .characters import records
    return {actor:[dict(sender=s,observation=o,delivered=d,revision=json.loads(raw)['revision'])
        for s,o,d,raw in server.db.execute('SELECT sender,observation,delivered,snapshot FROM actor_knowledge WHERE recipient=? ORDER BY delivered DESC LIMIT 32',(actor,))]
        for actor in records(server.module_state)}


def share(server,actor,row,args):
    if set(args)!={'target','expected_version','observation'} or type(args['observation']) is not int:
        raise ValueError('Supply recipient version and own successful observation receipt')
    _,obj,target,other=participants(server,actor,args)
    if abs(obj['x']-other['x'])+abs(obj['y']-other['y'])!=1:
        raise ValueError('Share observations only with an actually adjacent character')
    saved=server.db.execute("SELECT result FROM actor_tool_receipts WHERE actor=? AND seq=? AND status='succeeded'",(actor,args['observation'])).fetchone()
    # Check the immutable event tool as well as the mutable plan receipt shape.
    event=server.db.execute("SELECT data FROM events WHERE seq=? AND kind='world_memory'",(args['observation'],)).fetchone()
    if not saved or not event:raise ValueError('Own observation receipt unavailable')
    evidence=json.loads(event[0]);snapshot=json.loads(saved[0])
    if evidence.get('tool')!='world.observe' or evidence.get('character_id')!=actor or evidence.get('result')!=snapshot:
        raise ValueError('Only actual authority observations may be shared')
    existing=server.db.execute('SELECT delivered FROM actor_knowledge WHERE recipient=? AND sender=? AND observation=?',(args['target'],actor,args['observation'])).fetchone()
    if existing:return dict(outcome='already_shared',delivery=existing[0],recipient=args['target'],observation=args['observation'])
    seq=server.memory.append('character_knowledge_shared',dict(character_id=actor,recipient=args['target'],recipient_version=target['version'],observation=args['observation'],observed_revision=snapshot['observed_revision'],revision=snapshot['revision'],meeting_revision=obj['region_revision'],publication='public_world_observation',basis='adjacent_authority_observation_handoff',limits='Dated report, not current recipient sight or agreement.'))
    server.db.execute('INSERT INTO actor_knowledge VALUES(?,?,?,?,?)',(args['target'],actor,args['observation'],seq,saved[0]))
    server.revision=seq
    return dict(outcome='observation_shared',delivery=seq,recipient=args['target'],observation=args['observation'])


def recall(server,actor,row,args):
    if set(args)!={'delivery'} or type(args['delivery']) is not int:raise ValueError('Supply received delivery receipt')
    saved=server.db.execute('SELECT sender,observation,snapshot FROM actor_knowledge WHERE recipient=? AND delivered=?',(actor,args['delivery'])).fetchone()
    if not saved:raise ValueError('This character did not receive that report')
    sender,observation,raw=saved;snapshot=json.loads(raw)
    return dict(outcome='dated_report_recalled',sender=sender,observation=observation,delivery=args['delivery'],
        report_revision=snapshot['revision'],report_x=snapshot['x'],report_y=snapshot['y'],snapshot=snapshot,
        semantics='Sender observed this at the recorded revision. Navigate and observe again before acting; not recipient first-hand sight or proof entities remain.')


def relevant(event,actor):
    return (event.get('event')=='character_knowledge_shared' and event.get('recipient')==actor
        and event.get('publication')=='public_world_observation' and event.get('basis')=='adjacent_authority_observation_handoff')
