"""Independent public cast decisions with real shared-project consequences."""
import re
from .canonical_construction import signature


def validate(row,actors,identity):
    worksite=row.get('worksite')
    if worksite is not None and type(worksite) is not dict:raise ValueError('invalid worksite')
    partners=(worksite or {}).get('partners',[])
    if (type(partners) is not list or len(partners)>2 or any(type(p) is not str or p not in actors or p==identity for p in partners)
            or len(set(partners))!=len(partners)):
        raise ValueError('project partners must be up to two distinct existing other actors')
    decision=row.get('cooperate')
    if decision is None:return
    if (type(decision) is not dict or set(decision)!={'owner','intention','signature','decision'}
            or type(decision['owner']) is not str or decision['owner'] not in actors or decision['owner']==identity
            or type(decision['intention']) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,23}',decision['intention'])
            or type(decision['signature']) is not str or not re.fullmatch('[0-9a-f]{64}',decision['signature'])
            or decision['decision'] not in ('join','decline')):
        raise ValueError('cooperation requires another actor exact project and independent join or decline')


def check(before,row,identity,actors,lookup):
    d=row.get('cooperate')
    if not d or d==before.get('cooperate'):return
    owner=actors[d['owner']]
    task=next((t for t in owner.get('intentions',[]) if t['id']==d['intention'] and t['kind']=='construction'),None)
    if (not task or identity not in (owner.get('worksite') or {}).get('partners',[])
            or signature(d['owner'],owner,task)!=d['signature']):
        raise ValueError('project invitation changed or was withdrawn')
    if not any(e.get('event')=='canonical_project_invited' and e.get('recipient')==identity
               and e.get('character_id')==d['owner'] and e.get('intention')==d['intention']
               and e.get('signature')==d['signature'] for e in (lookup(n) for n in row['evidence'])):
        raise ValueError('cooperation requires inspected exact invitation evidence')


def publish(server,change):
    identity=change['character_id'];row=change['after']
    for task in row.get('intentions',[]):
        if task['kind']!='construction':continue
        if server.db.execute('SELECT 1 FROM canonical_construction_receipts WHERE actor=? AND intention=?',(identity,task['id'])).fetchone():continue
        for recipient in (row.get('worksite') or {}).get('partners',[]):
            server.revision=server.memory.append('canonical_project_invited',dict(
                character_id=identity,recipient=recipient,intention=task['id'],signature=signature(identity,row,task),
                worksite=row['worksite'],publication='public_cast_cooperation',places=change['places'],
                basis='authored_exact_project_invitation',limits='No agreement, meeting or travel is implied.'))
    decision=row.get('cooperate')
    if not decision or decision==(change.get('before') or {}).get('cooperate'):return
    if server.db.execute('SELECT 1 FROM canonical_construction_receipts WHERE actor=? AND intention=?',(decision['owner'],decision['intention'])).fetchone():
        raise ValueError('completed collaboration cannot be changed retroactively')
    server.revision=server.memory.append('canonical_project_decided',dict(
        character_id=identity,recipient=decision['owner'],intention=decision['intention'],
        signature=decision['signature'],decision=decision['decision'],
        publication='public_cast_cooperation',places=change['places'],
        basis='independent_authored_project_decision',limits='Project agreement only, not physical participation or mutual affection.'))


def participants(actors,owner,row,task):
    """Exact current decisions, rechecked immediately before atomic map commit."""
    agreed=[owner];sig=signature(owner,row,task)
    for partner in (row.get('worksite') or {}).get('partners',[]):
        d=actors.get(partner,{}).get('cooperate')
        if not d or any(d.get(k)!=v for k,v in dict(owner=owner,intention=task['id'],signature=sig,decision='join').items()):
            raise ValueError('waiting for independent agreement from '+partner)
        agreed.append(partner)
    return agreed


def relevant(event,identity):
    return (event.get('event') in ('canonical_project_invited','canonical_project_decided')
            and event.get('publication')=='public_cast_cooperation' and event.get('recipient')==identity)


def shared_result(event,identity,target):
    return (event.get('event')=='canonical_construction_completed'
            and event.get('publication')=='public_cast_construction'
            and event.get('outcome')=='connected_courtyard_committed'
            and identity in event.get('participants',[]) and target in event.get('participants',[]))
