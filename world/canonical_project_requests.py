"""Independent cast invitations whose accepted roles execute real shared actions."""
import json,re
from .opportunities import identity,encoded
from .canonical_world_actions import validate as validate_action


def install(db):
    db.execute('''CREATE TABLE IF NOT EXISTS canonical_project_requests(
      sender TEXT,id TEXT,target TEXT,action TEXT,message TEXT,seq INTEGER,
      decision TEXT,reply_seq INTEGER,PRIMARY KEY(sender,id))''')


def validate(row,actor,actors):
    request=row.get('project_request');reply=row.get('project_reply')
    if request is not None:
        if type(request) is not dict or set(request)!={'id','to','action','message'}:raise ValueError('Invalid project invitation')
        identity(request['id']);validate_action(request['action'])
        if request['to']==actor or request['to'] not in actors:raise ValueError('Invite an existing other actor')
        if 'native:'+request['action']['place'] not in row['places']:raise ValueError('Invitation must concern actor interests')
        text(request['message'])
    if reply is not None:
        if type(reply) is not dict or set(reply)!={'sender','id','decision','message'}:raise ValueError('Invalid project reply')
        identity(reply['id']);text(reply['message'])
        if reply['sender']==actor or reply['sender'] not in actors or reply['decision'] not in ('accept','decline'):raise ValueError('Reply requires another actor and a decision')


def text(value):
    if type(value) is not str or not re.fullmatch("[A-Za-z0-9 .,!?'-]{1,200}",value):raise ValueError('Bounded literal public speech required')


def relevant(event,actor):
    return (event.get('event') in ('canonical_project_requested','canonical_project_responded')
        and event.get('publication')=='public_cast_project_exchange'
        and actor in (event.get('sender'),event.get('recipient')))


def check_reply(row,actor,lookup):
    reply=row.get('project_reply')
    if reply is None:return
    if not any((e:=lookup(seq)).get('event')=='canonical_project_requested'
               and relevant(e,actor) and e.get('recipient')==actor
               and e.get('sender')==reply['sender'] and e.get('request_id')==reply['id'] for seq in row['evidence']):
        raise ValueError('Reply must cite the actual addressed project request')


def current(server,sender,key):
    from .canonical_cast import records
    row=server.db.execute('SELECT target,action,message,seq,decision,reply_seq FROM canonical_project_requests WHERE sender=? AND id=?',(sender,key)).fetchone()
    if not row:raise ValueError('Unknown project request')
    request=dict(id=key,to=row[0],action=json.loads(row[1]),message=row[2])
    active=records(server.module_state).get(sender,{}).get('project_request')==request
    return row,request,active


def publish(server,change):
    actor=change['character_id'];before=change.get('before') or {};after=change['after']
    request=after.get('project_request')
    if request and request!=before.get('project_request'):
        key=request['id'];action=request['action'];document=encoded(action)
        old=server.db.execute('SELECT target,action,message FROM canonical_project_requests WHERE sender=? AND id=?',(actor,key)).fetchone()
        if old:
            if old!=(request['to'],document,request['message']):raise ValueError('Request identity is immutable')
        else:
            owner=server.db.execute('SELECT actor FROM canonical_initiatives WHERE pack=?',(action['pack'],)).fetchone()
            if owner!=(actor,):raise ValueError('Only the project owner may invite a role')
            if server.db.execute('SELECT count(*) FROM canonical_project_requests WHERE sender=?',(actor,)).fetchone()[0]>=8:raise ValueError('Eight invitations per actor')
            offered=next((o for o in server.opportunities.actor_actions(request['to']) if all(o[k]==action[k] for k in ('pack','scene','place','revision')) and action['choice'] in o['choices']),None)
            if not offered:raise ValueError('Invited role is not currently assigned and available')
            seq=server.memory.append('canonical_project_requested',dict(sender=actor,recipient=request['to'],request_id=key,action=action,message=request['message'],places=['native:'+action['place']],publication='public_cast_project_exchange',limits='A request only. No agreement, physical meeting or action completion.'))
            server.db.execute('INSERT INTO canonical_project_requests VALUES(?,?,?,?,?,?,NULL,NULL)',(actor,key,request['to'],document,request['message'],seq));server.revision=seq
    reply=after.get('project_reply')
    if reply and reply!=before.get('project_reply'):
        old,request,active=current(server,reply['sender'],reply['id'])
        if old[0]!=actor:raise ValueError('Only the addressed actor may decide')
        if old[4] is not None:raise ValueError('Project request already answered')
        action=request['action'];receipt=None
        if reply['decision']=='accept':
            if not active:raise ValueError('Project owner withdrew or replaced this request')
            outcome=server.opportunities.actor_choose(actor,action)
            receipt=server.memory.append('canonical_world_action_committed',dict(character_id=actor,character_version=after['version'],intention='project_request',pack=action['pack'],scene=action['scene'],choice=action['choice'],revision=outcome['revision'],changes=outcome['changes'],result=outcome['text'],based_on=after['evidence'],places=['native:'+action['place']],publication='public_cast_world_action',outcome='shared_story_state_committed',limits='Accepted assigned shared project action, not physical travel, rewards or campaign progress.'))
        seq=server.memory.append('canonical_project_responded',dict(sender=reply['sender'],recipient=actor,request_id=reply['id'],decision=reply['decision'],message=reply['message'],request_seq=old[3],action_receipt=receipt,places=['native:'+action['place']],publication='public_cast_project_exchange',limits='Independent fictional response. Acceptance has a real shared-state action receipt; refusal changes no project state.'))
        server.db.execute('UPDATE canonical_project_requests SET decision=?,reply_seq=? WHERE sender=? AND id=?',(reply['decision'],seq,reply['sender'],reply['id']));server.revision=seq


def view(server):
    result=[]
    for s,i,t,a,m,q,d,r in server.db.execute('SELECT * FROM canonical_project_requests ORDER BY seq DESC LIMIT 32'):
        action=json.loads(a);_,_,active=current(server,s,i)
        available=active and d is None and any(all(o[k]==action[k] for k in ('pack','scene','place','revision')) and action['choice'] in o['choices'] for o in server.opportunities.actor_actions(t))
        result.append(dict(sender=s,id=i,recipient=t,action=action,message=m,seq=q,decision=d,reply_seq=r,available=available))
    return result
