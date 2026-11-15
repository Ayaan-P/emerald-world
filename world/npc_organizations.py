"""Persistent voluntary NPC institutions, with no pooled authority or player saves."""
import json,re,time
from . import actor_agreements as agreements


def setup(db):
    db.execute('CREATE TABLE IF NOT EXISTS npc_organizations(id TEXT PRIMARY KEY,name TEXT,goal TEXT,revision INTEGER,members TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS npc_organization_invites(organization TEXT,actor TEXT,revision INTEGER,PRIMARY KEY(organization,actor))')
    db.execute('CREATE TABLE IF NOT EXISTS npc_organization_actions(agreement TEXT PRIMARY KEY,organization TEXT,revision INTEGER,campaign TEXT)')


def load(server,key):
    setup(server.db)
    row=server.db.execute('SELECT name,goal,revision,members FROM npc_organizations WHERE id=?',(key,)).fetchone()
    if not row:raise ValueError('Unknown organization')
    return dict(id=key,name=row[0],goal=row[1],revision=row[2],members=json.loads(row[3]))


def member(server,actor,key):
    group=load(server,key)
    if actor not in group['members']:raise ValueError('Only a current member may do this')
    return group


def event(server,group,kind,**extra):
    seq=server.memory.append(kind,dict(organization=group['id'],participants=group['members'],
        basis='voluntary_npc_organization',**extra))
    server.revision=seq


def found(server,actor,row,args):
    if set(args)!={'id','name','goal'} or type(args['id']) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,23}',args['id']):
        raise ValueError('Use a new stable organization id, name and public fictional goal')
    for key,limit in [('name',40),('goal',120)]:
        if type(args[key]) is not str or not 1<=len(args[key])<=limit or any(not 32<=ord(c)<127 for c in args[key]):
            raise ValueError('Use bounded printable public organization text')
    agreements.active_actors(server,[actor]);setup(server.db)
    if server.db.execute('SELECT count(*) FROM npc_organizations').fetchone()[0]>=32:raise ValueError('Organization capacity reached')
    if server.db.execute('SELECT 1 FROM npc_organizations WHERE id=?',(args['id'],)).fetchone():raise ValueError('Organization identity already exists')
    server.db.execute('INSERT INTO npc_organizations VALUES(?,?,?,?,?)',(args['id'],args['name'],args['goal'],1,json.dumps([actor])))
    group=load(server,args['id']);event(server,group,'npc_organization_founded',character_id=actor,name=args['name'],goal=args['goal'])
    return dict(outcome='organization_founded',organization=args['id'])


def invite(server,actor,row,args):
    if set(args)!={'organization','target'}:raise ValueError('Choose organization and target character')
    group=member(server,actor,args['organization']);agreements.active_actors(server,[actor,args['target']])
    if args['target'] in group['members'] or len(group['members'])>=4:raise ValueError('Member already joined or group is full')
    if server.db.execute('SELECT count(*) FROM npc_organization_invites WHERE organization=?',(group['id'],)).fetchone()[0]>=8:raise ValueError('Resolve outstanding invitations first')
    server.db.execute('INSERT OR REPLACE INTO npc_organization_invites VALUES(?,?,?)',(group['id'],args['target'],group['revision']))
    event(server,group,'npc_organization_invited',character_id=actor,recipient=args['target'])
    return dict(outcome='organization_invitation_sent',organization=group['id'],recipient=args['target'])


def decide(server,actor,row,args):
    if set(args)!={'organization','decision'} or args['decision'] not in ('join','decline','leave'):raise ValueError('Choose join, decline or leave')
    group=load(server,args['organization']);decision=args['decision']
    if decision=='leave':
        if actor not in group['members']:raise ValueError('Not a member')
        group['members'].remove(actor)
    else:
        invitation=server.db.execute('SELECT revision FROM npc_organization_invites WHERE organization=? AND actor=?',(group['id'],actor)).fetchone()
        if invitation!=(group['revision'],):raise ValueError('No current invitation; membership changed')
        if decision=='join':
            agreements.active_actors(server,[actor])
            if actor in group['members'] or len(group['members'])>=4:raise ValueError('Already joined or group full')
            group['members'].append(actor)
    server.db.execute('DELETE FROM npc_organization_invites WHERE organization=? AND actor=?',(group['id'],actor))
    if decision!='decline':
        group['revision']+=1
        server.db.execute('UPDATE npc_organizations SET revision=?,members=? WHERE id=?',(group['revision'],json.dumps(sorted(group['members'])),group['id']))
        server.db.execute('DELETE FROM npc_organization_invites WHERE organization=?',(group['id'],))
        # Leaving/rejoining cannot restore old consent, even through direct agreement tools.
        server.db.execute("UPDATE actor_agreements SET status='cancelled' WHERE status='open' AND id IN (SELECT agreement FROM npc_organization_actions WHERE organization=?)",(group['id'],))
    event(server,group,'npc_organization_membership',character_id=actor,decision=decision)
    return dict(outcome='organization_'+decision,organization=group['id'],revision=group['revision'])


def propose(server,actor,row,args):
    if set(args)!={'organization','purpose','tool','args','hours','campaign'}:raise ValueError('Choose exact operation, purpose, expiry and optional existing campaign')
    group=member(server,actor,args['organization'])
    if len(group['members'])<2:raise ValueError('Joint projects need at least two voluntary members')
    campaign=args['campaign']
    if type(campaign) is not str:raise ValueError('Use an existing own campaign id or empty string')
    if campaign:
        saved=server.db.execute('SELECT actor FROM battle_campaigns WHERE id=?',(campaign,)).fetchone()
        if saved!=(actor,):raise ValueError('Offer only a campaign you actually published')
    result=agreements.propose(server,actor,row,dict(participants=json.dumps([m for m in group['members'] if m!=actor]),
        purpose=args['purpose'],tool=args['tool'],args=args['args'],hours=args['hours']),
        organization=dict(organization=group['id'],organization_revision=group['revision'],campaign=campaign))
    server.db.execute('INSERT INTO npc_organization_actions VALUES(?,?,?,?)',(result['agreement'],group['id'],group['revision'],campaign))
    event(server,group,'npc_organization_project',character_id=actor,agreement=result['agreement'],campaign=campaign)
    return dict(result,organization=group['id'],campaign=campaign)


def guard(server,key,terms):
    setup(server.db)
    binding=server.db.execute('SELECT organization,revision FROM npc_organization_actions WHERE agreement=?',(key,)).fetchone()
    if not binding:return
    group=load(server,binding[0])
    if group['revision']!=binding[1] or sorted(group['members'])!=sorted(terms['participants']):
        raise ValueError('Organization membership changed; make a fresh project')


def catalog(server):
    setup(server.db)
    groups=[]
    for (key,) in server.db.execute('SELECT id FROM npc_organizations ORDER BY id'):
        group=load(server,key)
        group['invitations']=[a for (a,) in server.db.execute('SELECT actor FROM npc_organization_invites WHERE organization=? AND revision=?',(key,group['revision']))]
        group['projects']=[dict(agreement=a,revision=r,campaign=c,status='expired' if st=='open' and expires<=time.time() else st,result=json.loads(result) if result else None)
            for a,r,c,st,result,expires in server.db.execute('SELECT o.agreement,o.revision,o.campaign,a.status,a.result,a.expires FROM npc_organization_actions o JOIN actor_agreements a ON a.id=o.agreement WHERE o.organization=? ORDER BY a.rowid DESC LIMIT 8',(key,))]
        groups.append(group)
    return groups


def _command(server,conn,words):
    from .guilds import GuildError
    try:
        groups=catalog(server)
        if not words or words[0]=='list':
            if words and (len(words)>2 or len(words)==2 and not re.fullmatch('[1-4]',words[1])):
                raise ValueError('Use /guild org list PAGE, from 1 to 4')
            page=int(words[1]) if len(words)==2 else 1
            selected=groups[(page-1)*8:page*8]
            return ['NPC organizations page '+str(page)+'. /guild org list PAGE',
                'Public NPC groups. No player membership or automatic enrolment.']+([g['id']+': '+g['name']+' ('+str(len(g['members']))+' members)' for g in selected] or ['No organizations on this page.'])
        group=next((g for g in groups if g['id']==words[0]),None)
        if not group:raise ValueError('Unknown organization. Use /guild org list')
        if len(words)==1:
            lines=[group['name'],group['goal'],'Members: '+(', '.join(group['members']) or 'none; dormant'),
                'Membership grants no new powers. Projects use normal world rules.']
            for p in group['projects'][:3]:
                lines.append(p['agreement'][:12]+': '+p['status']+(' / '+p['result'].get('outcome','committed') if p['result'] else ''))
                if p['status']=='applied' and p['revision']==group['revision'] and p['campaign']:
                    lines.append('/guild org '+group['id']+' play '+p['campaign'])
            return lines
        if len(words)==3 and words[1]=='play':
            if not any(p['status']=='applied' and p['revision']==group['revision'] and p['campaign']==words[2] for p in group['projects']):
                raise ValueError('No current committed group project offers that adventure')
            from .battle_campaigns import command as campaign_command
            return campaign_command(server,conn,['share',words[2]])
        raise ValueError('Use /guild org list, /guild org ID or /guild org ID play CAMPAIGN')
    except (ValueError,TypeError,KeyError) as exc:raise GuildError(str(exc)) from None


def relevant(event,actor):
    return event.get('basis')=='voluntary_npc_organization' and (actor in event.get('participants',[]) or actor in (event.get('recipient'),event.get('character_id')))


def command(server,conn,words):
    return [line[offset:offset+110] for line in _command(server,conn,words) for offset in range(0,len(line),110)]
