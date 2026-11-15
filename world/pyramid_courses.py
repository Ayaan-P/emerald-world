"""Immutable opt-in native Pyramid geometry courses, not verified expeditions."""
import hashlib,json,re
from pathlib import Path
DATA=json.loads(Path(__file__).with_name('pyramid_catalog.json').read_text())

def setup(db):db.execute('CREATE TABLE IF NOT EXISTS pyramid_courses(id TEXT PRIMARY KEY,actor TEXT,seed INTEGER,revision TEXT,active INTEGER)')
def seeds(seed):
    state=seed or 0x6D2B79F5;result=[]
    for _ in range(4):
        state^=(state<<13)&0xffffffff;state^=state>>17;state^=(state<<5)&0xffffffff
        result.append(state&65535)
    return result

def advance(values,floor):
    old=list(values)
    return [(old[i]*25173+old[(i+1)%4]*97+13849+floor*257+i)&65535 for i in range(4)]

def preview(seed):
    values=seeds(seed);result=[]
    for floor in range(7):
        if floor:values=advance(values,floor)
        template=next(t for threshold,t in DATA['options'][DATA['offsets'][floor]:] if values[3]%100<threshold)
        entry,exit=values[3]%16,values[0]%16
        if entry==exit:entry=(entry+1)%16;exit=(exit+15)%16
        result.append(dict(floor=floor+1,seeds=values[:],template=template,entrance_square=entry,exit_square=exit,**DATA['templates'][template]))
    return result

def catalog(server):
    setup(server.db)
    return [dict(id=i,actor=a,seed=s,revision=r) for i,a,s,r in server.db.execute('SELECT id,actor,seed,revision FROM pyramid_courses WHERE active=1 ORDER BY id')]

def publish(server,actor,row,args):
    setup(server.db)
    if set(args)!={'id','seed'} or type(args['id']) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,23}',args['id']) or type(args['seed']) is not int or not 0<=args['seed']<=0xffffffff:raise ValueError('Use id and uint32 seed')
    ident=args['id'];seed=args['seed'];revision=hashlib.sha256(f'pyramid1:{seed}'.encode()).hexdigest()[:16]
    prior=server.db.execute('SELECT actor,seed,active FROM pyramid_courses WHERE id=?',(ident,)).fetchone()
    if prior and prior[:2]!=(actor,seed):raise ValueError('Course identity is immutable; choose a new ID')
    if (not prior or not prior[2]) and len(catalog(server))>=32:raise ValueError('Close a course first')
    server.db.execute('INSERT OR REPLACE INTO pyramid_courses VALUES(?,?,?,?,1)',(ident,actor,seed,revision))
    return dict(outcome='native_pyramid_course_published',id=ident,revision=revision,floors=preview(seed),limits='Opt-in geometry course only. Native admission, personal streak/wild teams/loot/battles/saves remain native. No participant or victory inferred.')

def close(server,actor,row,args):
    setup(server.db)
    if set(args)!={'id'} or type(args['id']) is not str:raise ValueError('Use course id')
    old=server.db.execute('SELECT actor FROM pyramid_courses WHERE id=?',(args['id'],)).fetchone()
    if not old or old[0]!=actor:raise ValueError('Only own course may close')
    server.db.execute('UPDATE pyramid_courses SET active=0 WHERE id=?',(args['id'],))
    return dict(outcome='course_closed_to_new_downloads',id=args['id'],limits='Downloaded/admitted personal courses are not revoked.')

def handle(server,conn,raw):
    setup(server.db);seq=0
    try:
        f=raw.decode('ascii').split(' ')
        if len(f)!=5 or f[:2]!=['E','GET'] or not re.fullmatch('[1-9][0-9]{0,9}',f[2]):raise ValueError()
        seq=int(f[2])
        if seq>0xffffffff or not conn['presence'].get('campaign_run') or server.link_protocol.busy(conn['id']):raise ValueError()
        r=server.db.execute('SELECT seed FROM pyramid_courses WHERE id=? AND revision=? AND active=1',(f[3],f[4])).fetchone()
        if not r:raise ValueError()
        return f'E COURSE {seq} {r[0]}\n'
    except (ValueError,KeyError,UnicodeError):return f'E ERROR {seq}\n'

def command(server,conn,words):
    from .guilds import GuildError
    rows=catalog(server)
    if not words:return ['Native Pyramid courses: /guild pyramid page N or show ID.','Experimental opt-in before normal Pyramid admission; personal progress and parties stay native.']
    if len(words)==2 and words[0]=='page' and words[1].isdigit() and len(words[1])<4:
        rows=rows[int(words[1])*3:int(words[1])*3+3]
        return [line for r in rows for line in (f"{r['id']} by {r['actor']}",f"/pyramid load {r['id']} {r['revision']} yes")]+([] if rows else ['No courses on this page.'])
    if len(words)==2 and words[0]=='show':
        r=next((r for r in rows if r['id']==words[1]),None)
        if not r:raise GuildError('Course unavailable')
        return [f"{r['id']}: native layout forecast, not a completed run."]+[f"Floor {f['floor']}: template {f['template']}, {f['trainers']} trainers, {f['items']} items; squares {f['entrance_square']} to {f['exit_square']}" for f in preview(r['seed'])]
    raise GuildError('Use /guild pyramid [page N|show ID]')
