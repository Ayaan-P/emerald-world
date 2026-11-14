"""Authority-executed cast construction, not animated NPC labor or player quests."""
import copy
import hashlib
import json
import re
import time
from .frontier_outposts import compile_outpost


def validate(worksite):
    if worksite is None:return
    if (type(worksite) is not dict or set(worksite)-{'partners'}!={'revision','label','plan'}
            or type(worksite['revision']) is not str or not re.fullmatch('[0-9a-f]{64}',worksite['revision'])
            or type(worksite['label']) is not str or not re.fullmatch("[A-Za-z0-9 .,!?'-]{1,55}",worksite['label'])
            or type(worksite['plan']) is not dict or set(worksite['plan'])!={'x','y','width','height','gate','reservations'}):
        raise ValueError('construction needs an exact source revision, literal label and bounded outpost plan')
    p=worksite['plan']
    if (any(type(p[k]) is not int for k in ('x','y','width','height'))
            or not 5<=p['width']<=15 or not 5<=p['height']<=15
            or p['x']<3 or p['y']<3 or p['x']+p['width']>124 or p['y']+p['height']>124
            or type(p['gate']) is not str or p['gate'] not in ('north','south','east','west')
            or type(p['reservations']) is not list or len(p['reservations'])>32):
        raise ValueError('invalid bounded construction plan')
    for r in p['reservations']:
        if (type(r) is not list or len(r)!=4 or any(type(v) is not int for v in r)
                or min(r)<1 or r[0]+r[2]>126 or r[1]+r[3]>126):raise ValueError('invalid construction reservation')


def signature(actor,row,task):
    return hashlib.sha256(json.dumps([actor,row['version'],task,row.get('worksite')],sort_keys=True).encode()).hexdigest()


def persist(server,receipt,previous,revision,place):
    """Private internal hook inside the same map publication transaction."""
    from .canonical_cast import records
    row=records(server.module_state).get(receipt['actor'])
    task=next((t for t in (row or {}).get('intentions',[]) if t['id']==receipt['intention']),None)
    if (not row or not task or task['kind']!='construction' or task['target']!=previous
            or signature(receipt['actor'],row,task)!=receipt['signature']
            or receipt['report']['revision']!=revision):
        raise ValueError('construction intention changed before commit')
    actor=receipt['actor']
    from .canonical_cooperation import participants
    agreed=participants(records(server.module_state),actor,row,task)
    seq=server.memory.append('canonical_construction_completed',dict(
        character_id=actor,intention=task['id'],character_version=row['version'],participants=agreed,
        previous_revision=previous,revision=revision,place_id=place,places=[place],
        label=row['worksite']['label'],report=receipt['report'],based_on=row['evidence'],
        publication='public_cast_construction',outcome='connected_courtyard_committed',
        basis='authority_compiled_and_committed_geometry',
        limits='Abstract character project execution, not animated labor, travel or item gathering.'))
    server.db.execute('INSERT INTO canonical_construction_receipts VALUES(?,?,?,?,?)',
        (actor,task['id'],receipt['signature'],revision,seq))


def step(server,*,now=None):
    """One bounded authority action between mechanic jobs, without player participation."""
    now=time.monotonic() if now is None else now
    if server.job is not None or server.deployment is not None:return None
    if now<getattr(server,'cast_construction_next',0):return None
    server.cast_construction_next=now+5
    from .canonical_cast import records
    waiting=None
    for actor,row in sorted(records(server.module_state).items()):
        worksite=row.get('worksite')
        if not worksite:continue
        if server.db.execute('SELECT count(*) FROM canonical_construction_receipts WHERE actor=?',(actor,)).fetchone()[0]>=8:continue
        for task in row.get('intentions',[]):
            if task['kind']!='construction':continue
            if server.db.execute('SELECT 1 FROM canonical_construction_receipts WHERE actor=? AND intention=?',(actor,task['id'])).fetchone():continue
            try:
                validate(worksite)
                from .canonical_cooperation import participants
                participants(records(server.module_state),actor,row,task)
                cave=server.shared_cave
                if not server.archive_generated_areas or not cave or cave.identity!=worksite['revision'] or task['target']!=cave.identity:
                    raise ValueError('waiting for the exact authored source map')
                stored=server.db.execute('SELECT template FROM generated_cave WHERE singleton=1').fetchone()
                if stored is None or hashlib.sha256(stored[0]).hexdigest()!=cave.identity:
                    raise ValueError('active map is not durably published')
                blob,report=compile_outpost(stored[0],worksite['plan'])
                from .character_rebinding import prepare
                continuation=prepare(server,cave.identity,report['revision'])
                receipt=dict(actor=actor,intention=task['id'],signature=signature(actor,row,task),report=report)
                server._replace_cave(blob,label=worksite['label'],previous_revision=cave.identity,
                    expected_world_id=server.memory.world_id,
                    expected_sequence=server.db.execute('SELECT coalesce(max(seq),0) FROM events').fetchone()[0],
                    history_evidence=copy.deepcopy(row['evidence']),character_continuation=continuation,
                    cast_construction=receipt)
                return dict(status='completed',actor=actor,intention=task['id'],revision=report['revision'])
            except ValueError as exc:
                # Occupied/busy/stale worlds wait; no repeated public event or synthetic success.
                waiting=dict(status='waiting',actor=actor,intention=task['id'],reason=str(exc))
    return waiting


def relevant(event,identity):
    return (event.get('event')=='canonical_construction_completed' and (event.get('character_id')==identity or identity in event.get('participants',[]))
            and event.get('publication')=='public_cast_construction'
            and event.get('outcome')=='connected_courtyard_committed')


def lines(server,identity):
    from .canonical_cast import records
    row=records(server.module_state).get(identity,{})
    result=['Authority-executed courtyard projects. No player work or physical NPC labor is implied.']
    for task in row.get('intentions',[]):
        if task['kind']!='construction':continue
        receipt=server.db.execute('SELECT revision FROM canonical_construction_receipts WHERE actor=? AND intention=?',(identity,task['id'])).fetchone()
        result.append(task['id']+': '+('Committed map '+receipt[0][:12] if receipt else 'Pending exact empty map and valid geometry.'))
        for partner in (row.get('worksite') or {}).get('partners',[]):
            decision=records(server.module_state).get(partner,{}).get('cooperate') or {}
            current=decision.get('signature')==signature(identity,row,task) and decision.get('owner')==identity and decision.get('intention')==task['id']
            result.append(partner+': '+(decision.get('decision','pending') if current else 'awaiting current project decision'))
    for revision,seq in server.db.execute('SELECT revision,seq FROM canonical_construction_receipts WHERE actor=? ORDER BY seq DESC LIMIT 3',(identity,)):
        result.append('Completed map '+revision[:12]+'; world record '+str(seq)+'.')
    return result
