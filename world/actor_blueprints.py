"""Bounded JSON authoring drafts; editing never executes or publishes their contents."""
import copy,hashlib,json,re


def setup(db):
    db.execute('CREATE TABLE IF NOT EXISTS actor_blueprints(actor TEXT,id TEXT,revision INTEGER,document TEXT,closed INTEGER DEFAULT 0,PRIMARY KEY(actor,id))')


def encode(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)


def validate(value,depth=0):
    if depth>12:raise ValueError('Blueprint nesting exceeds 12')
    if value is None or type(value) is bool:return
    if type(value) is int:
        if not -(2**63)<=value<2**63:raise ValueError('Blueprint integer out of bounds')
        return
    if type(value) is str:
        if len(value)>2048 or any(not 32<=ord(c)<127 for c in value):raise ValueError('Use bounded printable fictional data')
        return
    if type(value) is dict:
        if len(value)>256 or any(type(k) is not str or not 1<=len(k)<=64 or any(not 32<=ord(c)<127 for c in k) for k in value):raise ValueError('Invalid blueprint keys')
        for child in value.values():validate(child,depth+1)
    elif type(value) is list:
        if len(value)>256:raise ValueError('Blueprint array exceeds 256 entries')
        for child in value:validate(child,depth+1)
    else:raise ValueError('Blueprints contain JSON literals, not numbers with fractions or executable objects')


def key(value):
    if type(value) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,23}',value):raise ValueError('Use a stable lowercase blueprint ID')
    return value


def load(server,actor,name):
    setup(server.db);key(name)
    row=server.db.execute('SELECT revision,document,closed FROM actor_blueprints WHERE actor=? AND id=?',(actor,name)).fetchone()
    if not row:raise ValueError('No blueprint owned by this actor')
    return row


def tokens(path):
    if type(path) is not str or len(path)>160 or (path and not path.startswith('/')):raise ValueError('Use a bounded JSON pointer')
    if not path:return []
    if re.search(r'~(?![01])',path):raise ValueError('Invalid JSON pointer escape')
    parts=[p.replace('~1','/').replace('~0','~') for p in path[1:].split('/')]
    if len(parts)>12:raise ValueError('Blueprint path is too deep')
    return parts


def index(container,part):
    if type(container) is dict:return part
    if type(container) is list and re.fullmatch('0|[1-9][0-9]*',part) and int(part)<len(container):return int(part)
    raise ValueError('Path does not address an existing array entry or object')


def patch(document,operations):
    result=copy.deepcopy(document)
    if type(operations) is not list or not 1<=len(operations)<=4:raise ValueError('Use one to four literal set/remove operations')
    for op in operations:
        if type(op) is not dict or op.get('op') not in ('set','remove') or set(op)!=({'op','path','value'} if op['op']=='set' else {'op','path'}):raise ValueError('Use set(path,value) or remove(path)')
        parts=tokens(op['path'])
        if not parts:
            if op['op']!='set' or type(op['value']) is not dict:raise ValueError('Root must remain a JSON object')
            result=copy.deepcopy(op['value']);continue
        target=result
        try:
            for part in parts[:-1]:target=target[index(target,part)]
            last=parts[-1]
            if type(target) is list and last=='-' and op['op']=='set':target.append(copy.deepcopy(op['value']));continue
            at=index(target,last)
            if op['op']=='remove':del target[at]
            else:target[at]=copy.deepcopy(op['value'])
        except (KeyError,IndexError,TypeError):raise ValueError('Blueprint path unavailable') from None
    validate(result)
    if len(encode(result).encode())>8192:raise ValueError('Blueprint exceeds 8192 bytes; downstream executor limits still apply')
    return result


def edit(server,actor,row,args):
    if set(args)!={'id','revision','patch'} or type(args['revision']) is not int or args['revision']<0 or type(args['patch']) is not str or len(args['patch'])>700:raise ValueError('Supply own blueprint ID, exact revision and bounded JSON patch')
    setup(server.db);name=key(args['id'])
    old=server.db.execute('SELECT revision,document,closed FROM actor_blueprints WHERE actor=? AND id=?',(actor,name)).fetchone()
    if old:
        revision,document,closed=old
        if closed or revision!=args['revision']:raise ValueError('Blueprint is closed or revision is stale')
    else:
        if args['revision']!=0:raise ValueError('New blueprint starts at revision zero')
        if server.db.execute('SELECT count(*) FROM actor_blueprints WHERE actor=? AND closed=0',(actor,)).fetchone()[0]>=16 or server.db.execute('SELECT count(*) FROM actor_blueprints WHERE closed=0').fetchone()[0]>=128:raise ValueError('Close an existing active draft before opening another')
        revision,document=0,'{}'
    operations=json.loads(args['patch']);updated=encode(patch(json.loads(document),operations));revision+=1
    server.db.execute('INSERT INTO actor_blueprints VALUES(?,?,?,?,0) ON CONFLICT(actor,id) DO UPDATE SET revision=excluded.revision,document=excluded.document',(actor,name,revision,updated))
    digest=hashlib.sha256(updated.encode()).hexdigest()
    seq=server.memory.append('actor_blueprint_edited',dict(character_id=actor,blueprint=name,revision=revision,patch=operations,digest=digest,basis='public_fictional_authoring_data_not_world_execution'))
    server.revision=seq
    return dict(outcome='blueprint_edited',blueprint=name,revision=revision,digest=digest,bytes=len(updated.encode()))


def inspect(server,actor,row,args):
    if set(args)!={'id'}:raise ValueError('Inspect own blueprint ID')
    revision,document,closed=load(server,actor,args['id'])
    return dict(outcome='blueprint_snapshot',blueprint=args['id'],revision=revision,document=document,closed=bool(closed),digest=hashlib.sha256(document.encode()).hexdigest())


def close(server,actor,row,args):
    if set(args)!={'id','revision'} or type(args['revision']) is not int:raise ValueError('Close own exact blueprint revision')
    revision,_,closed=load(server,actor,args['id'])
    if revision!=args['revision']:raise ValueError('Blueprint revision is stale')
    server.db.execute('UPDATE actor_blueprints SET closed=1 WHERE actor=? AND id=?',(actor,args['id']))
    return dict(outcome='blueprint_closed',blueprint=args['id'],revision=revision,already_closed=bool(closed))


def catalog(server):
    setup(server.db)
    return [dict(actor=a,id=k,revision=r,bytes=len(d.encode())) for a,k,r,d in server.db.execute('SELECT actor,id,revision,document FROM actor_blueprints WHERE closed=0 ORDER BY actor,id LIMIT 128')]
