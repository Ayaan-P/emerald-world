"""Explicit optional demonstration pack; the campaign framework remains generic."""
import copy,hashlib,inspect,json,time
from pathlib import Path

ID='hoenn_practice'
ACTORS=('camp_gate','camp_sky','camp_meadow','camp_final')

def graph():
    nodes={}
    for key,actor,win,move in [('gate',ACTORS[0],['sky','meadow'],0),('sky',ACTORS[1],['final'],210),('meadow',ACTORS[2],['final'],205),('final',ACTORS[3],[],164)]:
        nodes[key]=dict(opponent=actor,win=win,loss=[],preparation=dict(camp=dict(actor=actor,items=[28],move=move)))
    return dict(id=ID,title='Hoenn practice circuit',entry='gate',nodes=nodes)


def add_sample(result,characters,objects):
    import copy
    result=copy.deepcopy(result);cast=result['state'].setdefault('world_characters',{})
    for key,row in characters.items():
        cast.setdefault(key,copy.deepcopy(row))
    for obj in objects:
        if cast[obj['id']]['status']=='active' and not any(o['id']==obj['id'] for o in result.get('objects',[])):
            result.setdefault('objects',[]).append(copy.deepcopy(obj))
    result['state']['practice_circuit_installed']=True
    return result


def status(server):
    if not server.db.execute("SELECT 1 FROM sqlite_master WHERE name='practice_circuit_install'").fetchone():return None
    row=server.db.execute('SELECT data FROM practice_circuit_install WHERE singleton=1').fetchone()
    if not row:return None
    data=json.loads(row[0]);ready=server.db.execute('SELECT 1 FROM battle_campaigns WHERE id=?',(ID,)).fetchone() is not None
    return dict(status='ready' if ready else 'staged',place=data['place'],revision=data['revision'],campaign=ID,
                instruction='Use a REGION1 build. Select Hoenn Practice at the generated cave entrance, enter, then Ctrl+B.')


def install(server):
    from .characters import records,validate_transition
    from .trainer_context import parse_parties
    from .species_cohort import species_id
    from .cave_blueprint import proposal_from_blueprint
    from .shared_cave import SharedCave
    from .region_characters import validate_region_objects
    from .actor_runtime import validate
    if not server.archive_generated_areas:raise ValueError('Enable persistent generated-area archival before installing the optional circuit')
    if server.job is not None or server.deployment is not None:raise ValueError('Wait for the current mechanic operation')
    prior=server.candidate.sha256 if server.candidate else None
    existing=status(server)
    if existing:
        if existing['status']=='ready' or server.module_state.get('practice_circuit_installed'):return existing
        data=json.loads(server.db.execute('SELECT data FROM practice_circuit_install WHERE singleton=1').fetchone()[0])
        if prior!=data['prior']:raise ValueError('Another mechanic replaced the installation base; do not overwrite it')
        path=Path(data['source'])
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=data['sha']:raise ValueError('Staged example source unavailable')
        server.deployment=(None,path,None);return existing
    if server.db.execute('SELECT 1 FROM battle_campaigns WHERE id=?',(ID,)).fetchone():raise ValueError('Example campaign ID already exists')
    if any(a in records(server.module_state) or any(o['id']==a for o in server.objects) for a in ACTORS):raise ValueError('Example identities already used; nothing replaced')
    if len(records(server.module_state))+4>8 or len(server.objects)+4>8:raise ValueError('Circuit needs four free NPC/object slots')
    if server.db.execute('SELECT count(*) FROM world_region_revisions').fetchone()[0]>=32:raise ValueError('No free opened-region slot')
    plan=dict(id='publish_practice',purpose='Publish the host-requested optional practice circuit.',steps=[dict(id='publish',tool='world.publish_battle_campaign',args=dict(campaign=json.dumps(graph(),separators=(',',':'))),after=[])])
    validate(plan)
    proposal=proposal_from_blueprint(dict(rooms=[[4,4,21,19]],links=[],entrance_room=0,exit_room=0))
    blob=b'EWGMAP01'+''.join(proposal['rows']).encode();cave=SharedCave(blob)
    if server.db.execute('SELECT 1 FROM generated_area_archive WHERE identity=?',(cave.identity,)).fetchone():raise ValueError('Venue geometry already exists; refusing to assume ownership')
    source_refs=json.loads(Path(__file__).with_name('practice_trainer_sources.json').read_text())['definitions']
    characters={};objects=[]
    for i,(actor,ref,name,x,y) in enumerate(zip(ACTORS,['CALVIN_1','ALLEN','TIANA','HALEY_1'],['Gate Coach','Sky Coach','Meadow Coach','Final Coach'],[7,11,7,11],[7,7,11,11])):
        party=parse_parties(source_refs[ref])[0]['party']
        team=[dict(individual='partner_'+str(j+1),species=species_id(m['species_and_item'].upper(),'expansion-native'),level=m['level']) for j,m in enumerate(party)]
        characters[actor]=dict(version=1,name=name,role='Optional practice coach with a source-inspired early Hoenn team',goals=['Offer optional practice without changing the original campaign'],relationships={},team=team,status='active',object_id=actor,evidence=[],reason='Explicit host-installed example. Species and levels from TRAINER_'+ref+'; not the original trainer, exact stats or a claimed catch.')
        if i==0:characters[actor]['plan']=plan
        objects.append(dict(id=actor,group=server.cave_map[0],num=server.cave_map[1],x=x,y=y,gfx=7 if i%2==0 else 8,text='Optional Hoenn practice.',region_revision=cave.identity))
    base=server.candidate.source if server.candidate else 'def update(context,state):\n    return dict(state=state,tiles=[],objects=[])\n'
    helper=inspect.getsource(add_sample).replace('def add_sample(','def _practice_example_v1(',1)
    source=base+'\n_practice_previous_v1=update\n'+helper+'\ndef update(context,state):\n    if not state:\n        import copy\n        state=copy.deepcopy('+repr(server.module_state)+')\n    return _practice_example_v1(_practice_previous_v1(context,state),'+repr(characters)+','+repr(objects)+')\n'
    if len(source.encode())>256*1024:raise ValueError('Existing mechanic needs consolidation')
    sha=hashlib.sha256(source.encode()).hexdigest();path=server.runtime.candidates/('practice_'+sha+'.py')
    try:
        with path.open('x') as f:f.write(source)
    except FileExistsError:
        if path.is_symlink() or path.read_text()!=source:raise ValueError('Example source path conflict')
    proposed=add_sample(dict(state=server.module_state,tiles=server.tiles,objects=server.objects),characters,objects)
    with server.db:
        server.db.execute('INSERT INTO generated_area_archive VALUES(?,?,?,?,?)',(cave.identity,'Hoenn Practice','cave',blob,int(time.time())))
        opened=server._pin_region(cave.identity)
        server._validated(proposed);validate_transition(server.module_state,proposed['state'],proposed['objects'],server.db);validate_region_objects(server,proposed['objects'],proposed['state'])
        server.db.execute('CREATE TABLE IF NOT EXISTS practice_circuit_install(singleton INTEGER PRIMARY KEY,data TEXT)')
        server.db.execute('INSERT INTO practice_circuit_install VALUES(1,?)',(json.dumps(dict(place=opened['place_id'],revision=cave.identity,prior=prior,source=str(path),sha=sha)),))
    server.revision=server.db.execute('SELECT coalesce(max(seq),0) FROM events').fetchone()[0]
    server.deployment=(None,path,None)
    return status(server)
