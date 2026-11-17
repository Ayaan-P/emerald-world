"""Bounded public collaboration on installed cast projects."""
import json
import re


def validate_fields(row):
    c=row.get('contribution')
    if c is not None:
        if (type(c) is not dict or set(c)!={'course','digest','text'} or type(c['course']) is not str
                or not re.fullmatch('[a-z][a-z0-9_]{0,23}',c['course']) or type(c['digest']) is not str
                or not re.fullmatch('[0-9a-f]{64}',c['digest']) or type(c['text']) is not str
                or not re.fullmatch("[A-Za-z0-9 .,!?'-]{1,200}",c['text'])):
            raise ValueError('contribution requires an exact published project and bounded literal guidance')
    r=row.get('resolve_contribution')
    if r is not None and (type(r) is not dict or set(r)!={'seq','decision'}
            or type(r['seq']) is not int or r['seq'] not in row['evidence'] or r['decision'] not in ('accept','decline')):
        raise ValueError('project resolution requires exact inspected proposal and explicit decision')


def relevant(event, identity):
    return (event.get('event') in ('canonical_contribution_proposed','canonical_contribution_resolved')
            and event.get('publication')=='public_cast_collaboration' and event.get('recipient')==identity)


def validate_evidence(row, lookup):
    c=row.get('contribution')
    if c and not any(e.get('event')=='canonical_project_published' and e.get('course')==c['course']
                     and e.get('digest')==c['digest'] for e in (lookup(n) for n in row['evidence'])):
        raise ValueError('contribution needs inspected project publication evidence')
    r=row.get('resolve_contribution')
    if r and lookup(r['seq']).get('event')!='canonical_contribution_proposed':
        raise ValueError('resolution needs actual proposal evidence')


def apply(server, change):
    identity=change['character_id'];row=change['after'];old=change.get('before') or {}
    c=row.get('contribution')
    if c and c!=old.get('contribution'):
        project=server.db.execute('SELECT actor,digest FROM canonical_projects WHERE course=?',(c['course'],)).fetchone()
        if not project or project[0]==identity or project[1]!=c['digest']:
            raise ValueError('contribute only to another actor exact installed project')
        if server.db.execute('SELECT 1 FROM canonical_contributions WHERE course=? AND actor=?',(c['course'],identity)).fetchone():
            raise ValueError('this actor already contributed to this immutable project')
        seq=server.memory.append('canonical_contribution_proposed',dict(
            character_id=identity,recipient=project[0],course=c['course'],digest=c['digest'],text=c['text'],
            publication='public_cast_collaboration',places=['native:PetalburgCity'],based_on=row['evidence']))
        server.db.execute('INSERT INTO canonical_contributions VALUES(?,?,?,?,?,?)',
                          (seq,c['course'],identity,project[0],c['text'],'proposed'))
        server.revision=seq
    r=row.get('resolve_contribution')
    if r and r!=old.get('resolve_contribution'):
        proposal=server.db.execute('SELECT course,actor,owner,text,status FROM canonical_contributions WHERE seq=?',(r['seq'],)).fetchone()
        if not proposal or proposal[2]!=identity or proposal[4]!='proposed':
            raise ValueError('only project owner can resolve an outstanding contribution')
        server.db.execute('UPDATE canonical_contributions SET status=? WHERE seq=?',(r['decision'],r['seq']))
        server.revision=server.memory.append('canonical_contribution_resolved',dict(
            character_id=identity,recipient=proposal[1],course=proposal[0],proposal=r['seq'],decision=r['decision'],
            publication='public_cast_collaboration',places=['native:PetalburgCity'],based_on=row['evidence'],
            outcome='activity_guidance_published' if r['decision']=='accept' else 'contribution_declined'))


def briefing(server, course):
    from .canonical_cast import BINDINGS
    lines=[]
    for actor,text in server.db.execute("SELECT actor,text FROM canonical_contributions WHERE course=? AND status='accept' ORDER BY seq LIMIT 2",(course,)):
        lines.append(BINDINGS[actor]['name']+' contributed this guidance:')
        lines.extend(text[i:i+110] for i in range(0,len(text),110))
    return lines
