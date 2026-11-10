"""Experience-backed, actor-owned typed methods compiled into ordinary plans."""
import copy,hashlib,json,re

# This is an execution/provenance review list, not a bypass for capability guards.
TOOLS={'world.observe':None,'world.inspect_object':None,
       'world.navigate':'authority_arrived',
       'world.use_object':'validated_object_state_committed',
       'world.set_weather':'outdoor_weather_configured'}
PARAMETERS={'world.observe':{'radius'},'world.inspect_object':{'object'},
            'world.navigate':{'x','y'},'world.use_object':{'action'},
            'world.set_weather':{'mode'}}

def setup(db):
    db.execute('CREATE TABLE IF NOT EXISTS actor_methods(actor TEXT,name TEXT,digest TEXT,document TEXT,PRIMARY KEY(actor,name))')
    db.execute('CREATE TABLE IF NOT EXISTS actor_method_invocations(actor TEXT,plan TEXT,request TEXT,expanded TEXT,PRIMARY KEY(actor,plan))')

def encode(v):return json.dumps(v,sort_keys=True,separators=(',',':'))
def key(v):
    if type(v) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,23}',v):raise ValueError('Use a stable lowercase method/parameter name')
    return v

def inspect_object(server,actor,row,args):
    from .actor_observation import observe
    if set(args)!={'object'} or type(args['object']) is not str:raise ValueError('Choose a public nearby object identity')
    snapshot=observe(server,actor,row,dict(radius=1))
    target=next((e for e in snapshot['entities'] if e['id']==args['object']),None)
    if not target or not target.get('object_revision'):raise ValueError('No adjacent advertised object action; inspect and replan')
    return dict(object=target['id'],object_revision=target['object_revision'],revision=snapshot['revision'],
                actions=target['actions'],outcome='adjacent_object_observed')

def remember(server,actor,row,args):
    from .actor_runtime import validate
    if set(args)!={'name','plan','parameters'}:raise ValueError('Supply method name, own completed plan and parameter slots')
    setup(server.db);name=key(args['name']);key(args['plan'])
    if type(args['parameters']) is not str or len(args['parameters'])>700:raise ValueError('Bounded JSON parameter slots required')
    parameters=json.loads(args['parameters'])
    if type(parameters) is not dict or len(parameters)>8:raise ValueError('At most eight parameter slots')
    saved=server.db.execute('SELECT definition FROM actor_plans WHERE actor=? AND plan=?',(actor,args['plan'])).fetchone()
    if not saved:raise ValueError('Own previously executed plan required')
    invocation=server.db.execute('SELECT expanded FROM actor_method_invocations WHERE actor=? AND plan=?',(actor,args['plan'])).fetchone()
    plan=json.loads(invocation[0] if invocation else saved[0]);validate(plan)
    steps=plan['steps'];by_id={s['id']:s for s in steps};evidence=[]
    if not 2<=len(steps)<=6 or steps[0]['tool']!='world.observe':raise ValueError('Method must begin with fresh observation and include an actual effect')
    effect=False
    for index,step in enumerate(steps):
        tool=step['tool']
        if tool not in TOOLS or 'when' in step or step['after']!=[s['id'] for s in steps[:index]]:
            raise ValueError('Use a reviewed sequential public method; every earlier step is a dependency')
        receipt=server.db.execute('SELECT status,result,seq FROM actor_tool_receipts WHERE actor=? AND plan=? AND step=?',(actor,args['plan'],step['id'])).fetchone()
        if not receipt or receipt[0]!='succeeded' or receipt[2] is None:raise ValueError('Every source step needs an actual completed own receipt')
        result=json.loads(receipt[1])
        if TOOLS[tool]:
            if result.get('outcome')!=TOOLS[tool]:raise ValueError('Source outcome does not establish the supported action')
            effect=True
        if tool=='world.inspect_object' and result.get('outcome')!='adjacent_object_observed':raise ValueError('Object observation is not proven')
        if tool=='world.observe' and not {'revision','cells','actor_version'}<=set(result):raise ValueError('Local observation is not proven')
        for argument,value in step['args'].items():
            if argument in ('revision','object_revision','object') and tool not in ('world.inspect_object',):
                expected=('world.inspect_object' if tool=='world.use_object' else 'world.observe')
                if (type(value) is not dict or by_id[value['result']]['tool']!=expected or value['key']!=argument):
                    raise ValueError('World/object identity and revisions must come from a fresh method observation')
        evidence.append(receipt[2])
    if not effect:raise ValueError('Observation alone is not a learned action method')
    used=set()
    for parameter,slot in parameters.items():
        key(parameter)
        if type(slot) is not dict or set(slot)!={'step','argument'} or type(slot['step']) is not str or type(slot['argument']) is not str:raise ValueError('Parameter slot needs step and argument')
        step=by_id.get(slot['step']);pair=(slot['step'],slot['argument'])
        if not step or slot['argument'] not in PARAMETERS[step['tool']] or pair in used or type(step['args'][slot['argument']]) not in (str,int):raise ValueError('Only distinct reviewed literal arguments can be parameterized')
        used.add(pair)
    document=dict(source_plan=plan['id'],purpose=plan['purpose'],steps=steps,parameters=parameters,evidence=evidence)
    raw=encode(document);digest=hashlib.sha256(raw.encode()).hexdigest()
    old=server.db.execute('SELECT digest FROM actor_methods WHERE actor=? AND name=?',(actor,name)).fetchone()
    if old and old[0]!=digest:raise ValueError('Method names are immutable; retain a new name')
    server.db.execute('INSERT OR IGNORE INTO actor_methods VALUES(?,?,?,?)',(actor,name,digest,raw))
    return dict(outcome='experienced_method_retained',method=name,digest=digest,evidence=evidence)

def invocation(plan):
    return any(s['tool']=='world.perform_method' for s in plan['steps'])

def expand(server,actor,plan):
    from .actor_runtime import validate
    setup(server.db)
    if not invocation(plan):return plan
    if len(plan['steps'])!=1:raise ValueError('A method invocation occupies the whole plan; no nested execution')
    request=encode(plan)
    saved=server.db.execute('SELECT request,expanded FROM actor_method_invocations WHERE actor=? AND plan=?',(actor,plan['id'])).fetchone()
    if saved:
        if saved[0]!=request:raise ValueError('Method invocation identity changed')
        return json.loads(saved[1])
    args=plan['steps'][0]['args']
    if any(type(v) is not str for v in args.values()) or len(args['bindings'])>700:raise ValueError('Method invocation requires literal name, digest and bounded JSON bindings')
    record=server.db.execute('SELECT digest,document FROM actor_methods WHERE actor=? AND name=?',(actor,args['method'])).fetchone()
    if not record or record[0]!=args['digest']:raise ValueError('Own exact retained method required')
    doc=json.loads(record[1]);bindings=json.loads(args['bindings'])
    if type(bindings) is not dict or set(bindings)!=set(doc['parameters']):raise ValueError('Supply every declared binding, and no others')
    result=dict(id=plan['id'],purpose=plan['purpose'],steps=copy.deepcopy(doc['steps']));by_id={s['id']:s for s in result['steps']}
    for name,slot in doc['parameters'].items():
        arguments=by_id[slot['step']]['args'];old=arguments[slot['argument']];value=bindings[name]
        if type(value) is not type(old):raise ValueError('Method binding must preserve literal argument type')
        arguments[slot['argument']]=value
    validate(result)
    server.db.execute('INSERT INTO actor_method_invocations VALUES(?,?,?,?)',(actor,plan['id'],request,encode(result)))
    return result

def unavailable(*args):raise ValueError('Method invocation must compile before ordinary execution')

def catalog(server):
    setup(server.db)
    return [dict(actor=a,name=n,digest=d,**json.loads(raw)) for a,n,d,raw in server.db.execute('SELECT actor,name,digest,document FROM actor_methods ORDER BY actor,name LIMIT 128')]

def command(server,conn,args):
    rows=catalog(server)
    if args:rows=[r for r in rows if r['actor']==args[0]]
    return ['Retained NPC methods: public completed actions, not promises of future success.']+[f"{r['actor']}: {r['name']} [teacher: {r.get('teacher',{}).get('actor','own experience')}] ({len(r['steps'])} steps; evidence {','.join(map(str,r['evidence']))})" for r in rows[:8]]


def expanded_plan(server,actor,plan):
    setup(server.db)
    row=server.db.execute('SELECT expanded FROM actor_method_invocations WHERE actor=? AND plan=?',(actor,plan)).fetchone()
    return json.loads(row[0]) if row else None
