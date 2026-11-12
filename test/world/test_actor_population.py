from copy import deepcopy
import hashlib,json,unittest
import test_actor_places as fixture
from world import actor_runtime as runtime
from world.mechanics import Candidate
from world.actor_observation import observe

class PopulationTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.PlaceTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
 def define(self,identity='researcher',kind='character'):
  d=dict(id=identity,kind=kind,x=5,y=5,gfx=7 if kind=='character' else 0,text='Hello there.')
  if kind=='character':d.update(name='Neri',role='An independent researcher.',goals=['Study this place.'],team=[dict(species=280,level=8)])
  else:d['portable']=True
  return d
 def plan(self,definition=None):
  self.f.plan();state=deepcopy(self.s.module_state);c=state['world_characters']['harbor_guide'];c['version']+=1;c['plan']['id']='create_and_populate'
  c['plan']['steps'].append(dict(id='populate',tool='world.populate',args=dict(revision=dict(result='create',key='revision'),definition=json.dumps(definition or self.define(),separators=(',',':'))),after=['create']))
  self.f.f.f.f.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects));self.assertIsNone(self.s.module_error)
 def admit(self):
  _,path,_=self.s.deployment;self.s.deployment=None;source=path.read_text();candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest());ns={};exec(source,ns)
  self.f.f.f.f.f.f.candidate=candidate
  self.f.f.f.f.f.f.commit(ns['update'](self.s._context(),deepcopy(self.s.module_state)))
  self.assertIsNone(self.s.module_error)
 def test_create_populate_observe_and_restart(self):
  self.plan();self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded');self.assertEqual(runtime.tick(self.s,now=16)['status'],'pending')
  self.assertNotIn('researcher',self.s.module_state['world_characters']);self.admit()
  self.assertEqual(runtime.tick(self.s,now=22)['status'],'succeeded')
  observed=observe(self.s,'researcher',{},dict(radius=2));self.assertEqual((observed['x'],observed['y']),(5,5))
  revision=observed['revision'];self.assertEqual(revision,self.f.result()['revision'])
  client=self.f.connect('Visitor');client.select_region(self.f.result()['place_id']);peer=client.sock.conn
  peer['character_capable']=peer['character_region_capable']=True
  client.send_state(peer['seq']+1,*self.s.cave_map,5,4,1,7,1,'a'*16,'b'*16)
  snapshot=self.s._snapshot(peer);self.assertIn('REGION_OBJECT '+revision+' researcher ',snapshot);self.assertIn('CHARACTER researcher 1',snapshot)
  self.s.close();base=self.f.f.f.f.f.f.f;base.server=base.open();self.s=base.server
  self.assertEqual(observe(self.s,'researcher',{},dict(radius=1))['revision'],revision)
  self.assertIsNone(runtime.tick(self.s,now=30))
 def test_prop_uses_real_prop_wire_not_character(self):
  self.plan(self.define('marker','prop'));runtime.tick(self.s,now=10);self.assertEqual(runtime.tick(self.s,now=16)['status'],'pending');self.admit()
  self.assertEqual(runtime.tick(self.s,now=22)['status'],'succeeded');self.assertNotIn('marker',self.s.module_state['world_characters'])
  self.assertTrue(next(o for o in self.s.objects if o['id']=='marker')['portable'])
  token=self.s.create_identity('PropViewer')['token'];peer=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
  def send(line):
   peer['out'].clear();self.s._line(peer,line.encode());return peer['out'].decode()
  self.assertIn('WELCOME',send('HELLO 1 PropViewer '+token+' SOCIALCAVE16REGION1CHAR1CHARREG1WORLDOBJ1'))
  send('STATE 1 0 9 8 8 1 7 1 aaaaaaaaaaaaaaaa bbbbbbbbbbbbbbbb')
  result=self.f.result();self.assertIn('REGION SELECTED',send('REGION SELECT '+result['place_id']))
  send('CAVE GET');self.assertIn('CAVE OK',send('CAVE ACK '+result['revision']))
  send('STATE 2 %s %s 5 4 1 7 1 aaaaaaaaaaaaaaaa bbbbbbbbbbbbbbbb'%self.s.cave_map)
  snapshot=self.s._snapshot(peer);self.assertIn('REGION_PROP '+result['revision']+' marker ',snapshot);self.assertNotIn('CHARACTER marker ',snapshot)

 def test_invalid_placement_and_canonical_copy_rejected(self):
  d=self.define();d.update(x=1,y=1);self.plan(d);runtime.tick(self.s,now=10)
  self.assertEqual(runtime.tick(self.s,now=16)['status'],'blocked');self.assertIsNone(self.s.deployment)
 def test_unadmitted_source_never_claims_population(self):
  self.plan();runtime.tick(self.s,now=10);runtime.tick(self.s,now=16);self.s.deployment=None
  self.assertEqual(runtime.tick(self.s,now=22)['status'],'blocked');self.assertNotIn('researcher',self.s.module_state['world_characters'])
 def test_canonical_copy_is_not_a_generic_spawn(self):
  d=self.define();d['name']='Steven';self.plan(d);runtime.tick(self.s,now=10)
  self.assertEqual(runtime.tick(self.s,now=16)['status'],'blocked');self.assertIsNone(self.s.deployment)
 def test_new_character_can_execute_its_own_navigation_plan(self):
  self.plan();runtime.tick(self.s,now=10);runtime.tick(self.s,now=16);self.admit();runtime.tick(self.s,now=22)
  state=deepcopy(self.s.module_state);c=state['world_characters']['researcher'];c['version']+=1
  revision=next(o['region_revision'] for o in self.s.objects if o['id']=='researcher')
  c['plan']=dict(id='explore',purpose='Inspect another part of this room.',steps=[dict(id='walk',tool='world.navigate',args=dict(revision=revision,x=6,y=5),after=[]),dict(id='look',tool='world.observe',args=dict(radius=1),after=['walk'])])
  self.f.f.f.f.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects));self.assertIsNone(self.s.module_error)
  self.assertEqual(runtime.tick(self.s,now=28)['status'],'pending');self.admit()
  for tick in range(1,10):
   self.s.tick=tick;ns={};exec(self.s.candidate.source,ns)
   self.f.f.f.f.f.f.commit(ns['update'](self.s._context(),deepcopy(self.s.module_state)))
   self.assertIsNone(self.s.module_error)
  self.assertEqual(runtime.tick(self.s,now=40)['status'],'succeeded')
  self.assertEqual(runtime.tick(self.s,now=46)['status'],'succeeded')
  self.assertEqual(observe(self.s,'researcher',{},dict(radius=1))['x'],6)

class PersistentPopulationTests(PopulationTests):
 def create(self,style='rooms',identity='new_place',now=10):
  self.f.plan(style=style,identity=identity)
  self.assertEqual(runtime.tick(self.s,now=now)['status'],'succeeded')
  return self.f.result()['revision']
 def group(self,revision,definitions):
  from world.actor_population import populate_group
  return populate_group(self.s,'harbor_guide',self.s.module_state['world_characters']['harbor_guide'],dict(revision=revision,definitions=json.dumps(definitions,separators=(',',':'))))
 def test_group_atomic_native_population_and_restart(self):
  from world.actor_population import poll
  revision=self.create();a=self.define();b=self.define('colleague');b.update(x=7)
  pending=self.group(revision,[a,b]);self.assertNotIn('researcher',self.s.module_state['world_characters'])
  pending.dispatch();self.admit();result=poll(self.s,'harbor_guide',{},pending.data)
  self.assertEqual(result['outcome'],'population_group_admitted');self.assertEqual(len(result['members']),2)
  self.assertEqual(observe(self.s,'researcher',{},dict(radius=4))['revision'],revision)
  client=self.f.connect('GroupVisitor');client.select_region(self.f.result()['place_id']);peer=client.sock.conn
  peer['character_capable']=peer['character_region_capable']=peer['world_object_capable']=True
  client.send_state(peer['seq']+1,*self.s.cave_map,5,4,1,7,1,'a'*16,'b'*16)
  self.assertIn('CHARACTER researcher 1',self.s._snapshot(peer))
  self.s.close();base=self.f.f.f.f.f.f.f;base.server=base.open();self.s=base.server
  self.assertEqual(poll(self.s,'harbor_guide',{},pending.data),result)
  self.assertEqual(len([o for o in self.s.objects if o['id'] in ('researcher','colleague')]),2)
 def test_group_bad_second_member_never_stages_first(self):
  revision=self.create();a=self.define();b=self.define('duplicate');b['x']=1;b['y']=1
  before=deepcopy(self.s.module_state)
  with self.assertRaises(ValueError):self.group(revision,[a,b])
  self.assertIsNone(self.s.deployment);self.assertEqual(before,self.s.module_state)
  with self.assertRaises(ValueError):self.group(revision,[a,a])
  self.assertNotIn('researcher',self.s.module_state['world_characters'])
 def test_twenty_actual_admissions_across_three_places_without_wrapper_chain(self):
  from world.actor_population import spawn,poll
  index=0
  for map_index,style in enumerate(('rooms','rounded','organic')):
   revision=self.create(style,'place_'+str(map_index),10+map_index*100)
   from world.shared_cave import SharedCave
   cave=SharedCave(self.s.db.execute('SELECT template FROM generated_area_archive WHERE identity=?',(revision,)).fetchone()[0])
   cells=[(x,y) for y in range(3,29) for x in range(3,29) if cave.walkable(x,y)]
   count=0
   for x,y in cells:
    definition=self.define('prop_'+str(index),'prop');definition.update(x=x,y=y)
    try:pending=spawn(self.s,'harbor_guide',self.s.module_state['world_characters']['harbor_guide'],dict(revision=revision,definition=json.dumps(definition)))
    except ValueError:continue
    pending.dispatch();self.admit();self.assertEqual(poll(self.s,'harbor_guide',{},pending.data)['object'],definition['id']);index+=1;count+=1
    if count==(7 if map_index<2 else 6):break
  self.assertEqual(index,20)
  source=self.s.candidate.source
  self.assertEqual(source.count('def _ew_population_step_v1('),1)
  self.assertEqual(source.count('_ew_population_previous_v1=update'),1)
  self.assertEqual(len(self.s.module_state['world_population_receipts']),20)
  self.s.close();base=self.f.f.f.f.f.f.f;base.server=base.open();self.s=base.server
  self.assertEqual(len([o for o in self.s.objects if o['id'].startswith('prop_')]),20)
  self.assertEqual(len(self.s.module_state['world_population_receipts']),20)
 def test_dispatcher_tampering_refused_and_legacy_source_preserved(self):
  from world.actor_population import dispatch_source
  old='def update(context,state):\n    return dict(state=state,objects=[])\n'
  request=dict(request='a',object=dict(id='one'),character=None)
  source=dispatch_source(old,[request],{})
  second=dict(request='b',object=dict(id='two'),character=None)
  self.assertTrue(dispatch_source(source,[second],{}).startswith(old))
  with self.assertRaises(ValueError):dispatch_source(source.replace('result=_ew_population_previous_v1(context,state)','result={}'),[second],{})
  with self.assertRaises(ValueError):dispatch_source(source,[request],{})
 def test_old_append_only_projector_and_receipts_survive_new_dispatcher(self):
  import inspect
  from world.actor_population import population_step,dispatch_source
  first=dict(request='legacy',object=dict(id='old',region_revision='a'*64),character=None)
  second=dict(request='new',object=dict(id='new',region_revision='b'*64),character=None)
  base='def update(context,state):\n    return dict(state=state,objects=[])\n'
  old=base+'\n_old_population=update\n'+inspect.getsource(population_step)+'\ndef update(context,state):\n    return population_step(_old_population(context,state),'+repr(first)+')\n'
  source=dispatch_source(old,[second],{})
  self.assertTrue(source.startswith(old));ns={};exec(source,ns)
  result=ns['update']({},{});again=ns['update']({},deepcopy(result['state']))
  self.assertEqual(result,again);self.assertEqual(set(result['state']['world_population_receipts']),{'legacy','new'})
  self.assertEqual([o['id'] for o in result['objects']],['old','new'])
