"""Voluntary NPC visit roles backed by actual post-acceptance journey receipts."""
import json,secrets


def setup(db):
    db.execute('CREATE TABLE IF NOT EXISTS campaign_cast_invites(id TEXT PRIMARY KEY,run TEXT,node TEXT,role TEXT,actor TEXT,visit TEXT,status TEXT,accepted INTEGER,arrival INTEGER)')


def catalog(server):
    setup(server.db);prune(server)
    # Public invitations contain no private run key, participant identity/history,
    # human results or choices. A public invite is not a private party transcript.
    return [dict(id=i,actor=a,visit=json.loads(v),status=s,accepted=seq) for i,a,v,s,seq in server.db.execute("SELECT id,actor,visit,status,accepted FROM campaign_cast_invites WHERE status IN ('offered','accepted') ORDER BY rowid DESC LIMIT 64")]


def current(server,key,actor):
    from .shared_campaigns import load
    setup(server.db)
    r=server.db.execute('SELECT run,node,role,actor,visit,status,accepted,arrival FROM campaign_cast_invites WHERE id=?',(key,)).fetchone()
    if not r or r[3]!=actor:raise ValueError('Invitation is not addressed to this character')
    group=load(server,r[0])
    if group['node']!=r[1] or group['status'] not in ('deploying','ready'):raise ValueError('Invited stage is no longer open')
    return r,group


def invite(server,conn,words,key,group):
    from .shared_campaigns import member,store
    from .battle_campaigns import document
    from .characters import records
    from .actor_navigation import route
    if len(words)!=3 or words[0]!='invite-npc':return False
    if member(conn)!=group['speaker'] or group['status']!='deploying':raise ValueError('Only the speaker can publish a role invitation during deployment')
    actor,role=words[1:];node=document(server,group['campaign'])['nodes'][group['node']]
    task=node.get('roles',{}).get(role,{})
    if 'revision' not in task.get('visit',{}):raise ValueError('NPC roles require an exact generated-map visit, never a battle or ordinary-map visit')
    if role in list(group.get('roles',{}).values())+list(group.get('npc_roles',{}).values()):raise ValueError('Role already assigned')
    if actor in group.get('npc_roles',{}):raise ValueError('Character already has a role')
    cast=records(server.module_state)
    if actor not in cast or cast[actor]['status']!='active':raise ValueError('Active generated character required')
    visit=task['visit'];route(server,actor,visit['point'][2:],visit['revision'])
    setup(server.db);prune(server)
    if server.db.execute("SELECT 1 FROM campaign_cast_invites WHERE actor=? AND status IN ('offered','accepted')",(actor,)).fetchone():raise ValueError('Character already has an outstanding invitation; resolve it first')
    identity=secrets.token_hex(12)
    with server.db:
        server.db.execute('INSERT INTO campaign_cast_invites VALUES(?,?,?,?,?,?,?,NULL,NULL)',(identity,key,group['node'],role,actor,json.dumps(visit,sort_keys=True),'offered'))
        seq=server.memory.append('character_campaign_invited',dict(character_id=actor,invitation=identity,visit=visit,
            publication='speaker_explicit_public_role_invitation',basis='optional_request_not_participation',
            limits='Only this destination is public. No private party identity, reports or history; character may decline.'))
    server.revision=seq
    return True


def decide(server,actor,row,args):
    from .shared_campaigns import store,update_members
    from .parallel_campaigns import assignment_count
    from .battle_campaigns import document
    from .actor_navigation import route
    if set(args)!={'invitation','decision'} or args['decision'] not in ('accept','decline','withdraw'):raise ValueError('Choose accept, decline or withdraw for an addressed invitation')
    r,group=current(server,args['invitation'],actor)
    if r[5]=='accepted' and args['decision']=='withdraw':
        # Never reset completed human work or silently replace the NPC. The
        # party sees the withdrawal and may cancel; no fictional completion.
        server.db.execute("UPDATE campaign_cast_invites SET status='withdrawn' WHERE id=?",(args['invitation'],))
        group.setdefault('npc_status',{})[actor]='withdrawn';store(server,r[0],group)
        outcome='npc_role_withdrawn'
    elif r[5]=='offered' and args['decision'] in ('accept','decline'):
        accepted=args['decision']=='accept'
        if accepted:
            if group['status']!='deploying' or r[2] in list(group.get('roles',{}).values())+list(group.get('npc_roles',{}).values()):raise ValueError('Role is no longer free')
            total=len(document(server,group['campaign'])['nodes'][group['node']]['roles'])
            if len(group.get('npc_roles',{}))>=total-len(group['members']):raise ValueError('Keep one role for every human participant')
            visit=json.loads(r[4]);route(server,actor,visit['point'][2:],visit['revision'])
            group.setdefault('npc_roles',{})[actor]=r[2];group.setdefault('npc_status',{})[actor]='accepted'
            if assignment_count(group)==len(document(server,group['campaign'])['nodes'][group['node']]['roles']):
                group['status']='ready';update_members(server,r[0],group,status='ready')
            store(server,r[0],group)
        outcome='npc_role_accepted' if accepted else 'npc_role_declined'
        server.db.execute('UPDATE campaign_cast_invites SET status=? WHERE id=?',('accepted' if accepted else 'declined',args['invitation']))
    else:raise ValueError('Invitation already resolved')
    seq=server.memory.append('character_campaign_decided',dict(character_id=actor,invitation=args['invitation'],decision=args['decision'],basis='independent_character_choice_not_arrival'))
    if args['decision']=='accept':server.db.execute('UPDATE campaign_cast_invites SET accepted=? WHERE id=?',(seq,args['invitation']))
    server.revision=seq
    return dict(outcome=outcome,invitation=args['invitation'],visit=json.loads(r[4]),limits='Choice only. Use world.navigate, then submit its actual arrival receipt; no movement or completion implied.')


def finish(server,actor,row,args):
    from .actor_runtime import Pending
    if set(args)!={'invitation','arrival_receipt'} or type(args['arrival_receipt']) is not int:raise ValueError('Supply invitation and actual own arrival receipt')
    current(server,args['invitation'],actor)
    return Pending(dict(args),lambda:None)


def poll(server,actor,row,pending):
    from .shared_campaigns import store,settle
    from .character_walks import walking
    r,group=current(server,pending['invitation'],actor)
    if r[5]!='accepted':raise ValueError('Role was not accepted or has been withdrawn')
    visit=json.loads(r[4]);seq=pending['arrival_receipt']
    source=server.db.execute("SELECT e.data FROM character_journey_receipts j JOIN events e ON e.seq=j.seq WHERE j.actor=? AND j.seq=? AND e.kind='world_memory'",(actor,seq)).fetchone()
    if not source or seq<=r[6]:raise ValueError('A genuine post-acceptance journey receipt is required')
    event=json.loads(source[0]);obj=next((o for o in server.objects if o['id']==actor),None)
    if (event.get('event')!='character_journey_arrived' or event.get('character_id')!=actor
        or event.get('basis')!='committed_authority_cardinal_steps' or event.get('revision')!=visit['revision']
        or event.get('destination')!=visit['point'][2:] or not obj or obj.get('region_revision')!=visit['revision']
        or [obj['group'],obj['num'],obj['x'],obj['y']]!=visit['point'] or walking(server.module_state,actor)):
        raise ValueError('Arrival or current character position does not match the exact invited destination')
    if group['status']=='deploying':return None
    group.setdefault('npc_results',{})[actor]=dict(outcome=1,arrival=seq)
    group.setdefault('npc_status',{})[actor]='arrived'
    server.db.execute("UPDATE campaign_cast_invites SET status='arrived',arrival=? WHERE id=?",(seq,pending['invitation']))
    settle(server,r[0],group);store(server,r[0],group)
    return dict(outcome='npc_campaign_arrival_recorded',invitation=pending['invitation'],arrival_receipt=seq,revision=visit['revision'],
        limits='Own actual authority arrival only. No human results/history, native victory, reward or player movement disclosed.')


def rows(server,conn,group):
    from .shared_campaigns import member
    from .battle_campaigns import document
    from .characters import records
    setup(server.db);prune(server)
    out=[('NPC '+a+' - '+role+' - offered, awaiting independent decision',None) for a,role in server.db.execute("SELECT actor,role FROM campaign_cast_invites WHERE run=? AND node=? AND status='offered'",(active_key(server,conn),group['node']))]
    for actor,role in group.get('npc_roles',{}).items():out.append(('NPC '+actor+' - '+role+' - '+group.get('npc_status',{}).get(actor,'accepted'),None))
    if group['status']!='deploying' or member(conn)!=group['speaker']:return out
    out.append(('Invite NPC publishes only the role destination. They decide; no party history is sent.',None))
    node=document(server,group['campaign'])['nodes'][group['node']]
    assigned=list(group.get('roles',{}).values())+list(group.get('npc_roles',{}).values())
    for role,task in node.get('roles',{}).items():
        if role in assigned or 'revision' not in task.get('visit',{}):continue
        for obj in server.objects:
            if obj['id'] in records(server.module_state) and obj.get('region_revision')==task['visit']['revision']:
                out.append(('Publish invite '+obj['id']+' for '+role,['invite-npc',obj['id'],role]))
    return out


def relevant(event,actor):
    return event.get('event')=='character_campaign_invited' and event.get('character_id')==actor and event.get('publication')=='speaker_explicit_public_role_invitation'


def prune(server):
    from .shared_campaigns import load
    for i,key,node,role,actor,status in server.db.execute("SELECT id,run,node,role,actor,status FROM campaign_cast_invites WHERE status IN ('offered','accepted')").fetchall():
        try:g=load(server,key)
        except ValueError:g={}
        stale=g.get('node')!=node or g.get('status') not in ('deploying','ready')
        if status=='offered' and role in list(g.get('roles',{}).values())+list(g.get('npc_roles',{}).values()):stale=True
        if stale:server.db.execute("UPDATE campaign_cast_invites SET status='cancelled' WHERE id=?",(i,))


def active_key(server,conn):
    from .battle_campaigns import active
    current=active(server,conn)
    return current[1].get('shared','') if current else ''
