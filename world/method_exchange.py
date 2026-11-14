"""Voluntary transfer of proven public action recipes, never execution or mastery."""
import hashlib,json,time
from . import actor_methods as methods


def setup(db):
    methods.setup(db)
    db.execute('CREATE TABLE IF NOT EXISTS method_lessons(id TEXT PRIMARY KEY, donor TEXT, recipient TEXT, method TEXT, digest TEXT, expires REAL, status TEXT, learned TEXT)')


def meeting(server,actor,target):
    from .characters import records
    from .character_walks import walking
    rows=records(server.module_state);objects={o['id']:o for o in server.objects}
    if actor==target or any(a not in rows or rows[a]['status']!='active' or a not in objects or walking(server.module_state,a) for a in (actor,target)):
        raise ValueError('Two active stationary generated characters required')
    a,b=objects[actor],objects[target]
    if (not a.get('region_revision') or any(a.get(k)!=b.get(k) for k in ('group','num','region_revision')) or abs(a['x']-b['x'])+abs(a['y']-b['y'])!=1):
        raise ValueError('Meet adjacent in the same generated place first')


def event(server,kind,lesson,donor,recipient):
    seq=server.memory.append('character_method_'+kind,dict(lesson=lesson,character_id=donor,recipient=recipient,publication='public_method_exchange',limits='Recipe exchange only; recipient must observe and execute independently.'))
    server.revision=seq
    return seq


def offer(server,actor,row,args):
    if set(args)!={'lesson','recipient','method','digest'} or any(type(v) is not str for v in args.values()):raise ValueError('Supply lesson name, recipient and exact own method')
    methods.key(args['lesson']);setup(server.db);meeting(server,actor,args['recipient'])
    record=server.db.execute('SELECT digest,document FROM actor_methods WHERE actor=? AND name=?',(actor,args['method'])).fetchone()
    if not record or record[0]!=args['digest'] or json.loads(record[1]).get('teacher'):
        raise ValueError('Offer an own first-hand experienced method; inherited recipes cannot be reattributed')
    identity=hashlib.sha256((actor+':'+args['lesson']).encode()).hexdigest()
    old=server.db.execute('SELECT recipient,method,digest,status FROM method_lessons WHERE id=?',(identity,)).fetchone()
    if old:
        if old[:3]!=(args['recipient'],args['method'],args['digest']):raise ValueError('Lesson identity is immutable')
        return dict(outcome='lesson_already_recorded',lesson=identity,status=old[3])
    if server.db.execute("SELECT count(*) FROM method_lessons WHERE donor=? AND status='offered' AND expires>?",(actor,time.time())).fetchone()[0]>=8:raise ValueError('At most eight unexpired offers')
    server.db.execute('INSERT INTO method_lessons VALUES(?,?,?,?,?,?,?,?)',(identity,actor,args['recipient'],args['method'],args['digest'],time.time()+600,'offered',None))
    return dict(outcome='method_offered',lesson=identity,evidence=event(server,'offered',identity,actor,args['recipient']))


def respond(server,actor,row,args):
    if set(args)!={'lesson','decision','name'} or any(type(v) is not str for v in args.values()) or args['decision'] not in ('accept','decline','withdraw'):raise ValueError('Accept, decline or withdraw an exact offer')
    setup(server.db)
    item=server.db.execute('SELECT donor,recipient,method,digest,expires,status,learned FROM method_lessons WHERE id=?',(args['lesson'],)).fetchone()
    if not item:raise ValueError('Unknown lesson')
    donor,recipient,name,digest,expires,status,learned=item
    if actor!=(donor if args['decision']=='withdraw' else recipient):raise ValueError('Not your lesson decision')
    if status!='offered':return dict(outcome='lesson_already_settled',status=status,method=learned)
    if args['decision']=='accept':
        if time.time()>expires:raise ValueError('Lesson expired; request a new offer')
        meeting(server,donor,recipient);methods.key(args['name'])
        saved=server.db.execute('SELECT digest,document FROM actor_methods WHERE actor=? AND name=?',(donor,name)).fetchone()
        if not saved or saved[0]!=digest:raise ValueError('Teacher method changed')
        doc=json.loads(saved[1]);doc['teacher']=dict(actor=donor,method=name,digest=digest,lesson=args['lesson'])
        raw=methods.encode(doc);new_digest=hashlib.sha256(raw.encode()).hexdigest()
        old=server.db.execute('SELECT digest FROM actor_methods WHERE actor=? AND name=?',(recipient,args['name'])).fetchone()
        if old and old[0]!=new_digest:raise ValueError('Choose a new recipient method name')
        server.db.execute('INSERT OR IGNORE INTO actor_methods VALUES(?,?,?,?)',(recipient,args['name'],new_digest,raw))
        status='accepted';learned=args['name']
    else:status='declined' if args['decision']=='decline' else 'withdrawn'
    server.db.execute('UPDATE method_lessons SET status=?,learned=? WHERE id=?',(status,learned,args['lesson']))
    seq=event(server,status,args['lesson'],donor,recipient)
    return dict(outcome='method_'+status,method=learned,evidence=seq,limits='No execution, mastery or successful recipient experience implied')


def catalog(server):
    setup(server.db)
    return [dict(id=i,donor=d,recipient=r,method=m,digest=h,status=s if s!='offered' or e>=time.time() else 'expired',learned=n) for i,d,r,m,h,e,s,n in server.db.execute('SELECT * FROM method_lessons ORDER BY rowid DESC LIMIT 64')]


def relevant(e,actor):
    return e.get('publication')=='public_method_exchange' and e.get('event') in ('character_method_offered','character_method_accepted','character_method_declined','character_method_withdrawn') and actor in (e.get('recipient'),e.get('character_id'))
