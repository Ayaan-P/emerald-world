import json,unittest
from copy import deepcopy
import test_object_networks
from world import actor_objects,object_choices,cooperative_moves
from world.guilds import GuildError
class Cooperative(unittest.TestCase):
 def setUp(self):
  self.f=test_object_networks.NetworkTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  n=self.f.definition['program']['states']['off'];n['on']['fixture']={'charge':'off','release':'on'};n['use']={};n['choices']={'fixture':['charge','release']};n['moves']={'fixture':{'charge':[85],'release':[85]}}
  n['cooperate']={'fixture':{'release':[dict(object='fixture',action='charge')]*2}}
  self.f.install()
 def peer(self,name):
  p=self.f.f.f.connect(name,True);send=lambda line:self.f.f.f.f.f.send(p,line)
  send('CAVE GET');send('CAVE ACK '+self.s.shared_cave.identity);self.f.f.f.f.f.state(p,*self.s.wilds_map,72,69);p['state'][4]=1;return p
 def act(self,p,action):
  object_choices.command(self.s,p,['moves']);token=p['object_moves']['token'];object_choices.command(self.s,p,['move',token,action,'85'])
 def admit(self,t):self.f.f.f.f.advance(t,True);actor_objects.poll_player(self.s)
 def test_actual_distinct_commits_then_visible_transition_and_restart(self):
  a=self.peer('UserOne');b=self.peer('UserTwo')
  self.assertNotIn('release',actor_objects.offers(self.s,next(o for o in self.s.objects if o['id']=='fixture'))['actions'])
  self.act(a,'charge');self.admit(1)
  self.act(a,'charge');self.admit(2)
  status=self.s.module_state['world_object_network_state']['mechanism'];self.assertEqual(status['cooperators'],{'fixture/charge':['player:UserOne']})
  with self.assertRaises(GuildError):self.act(a,'release')
  self.act(b,'charge');self.admit(3)
  obj=next(o for o in self.s.objects if o['id']=='fixture');self.assertIn('release',actor_objects.offers(self.s,obj)['actions'])
  self.assertTrue(cooperative_moves.inspect(self.s,obj)['gates'][0]['ready'])
  self.act(a,'release');self.admit(4)
  self.assertEqual(next(o for o in self.s.objects if o['id']=='panel')['y'],72)
  self.assertEqual(self.s.module_state['world_object_network_state']['mechanism']['cooperators'],{})
  members=deepcopy(self.s.objects);self.s.close();base=self.f.f.f.f.f.f;base.server=base.open();self.s=base.server
  self.assertEqual(self.s.objects,members);self.assertEqual(self.s.module_state['world_object_network_state']['mechanism']['cooperators'],{})
 def test_failed_admission_does_not_contribute(self):
  p=self.peer('UserOne');self.act(p,'charge');self.s.deployment=None;actor_objects.poll_player(self.s)
  self.assertFalse(self.s.module_state['world_object_network_state']['mechanism'].get('cooperators'))
 def test_matching_not_counts_and_bounds(self):
  needs=[dict(object='a',action='x'),dict(object='b',action='y')]
  self.assertFalse(cooperative_moves.ready(needs,{'a/x':['p'],'b/y':['p']}))
  self.assertTrue(cooperative_moves.ready(needs,{'a/x':['p','q'],'b/y':['p']}))
  bad=deepcopy(self.f.definition['program']['states']['off']);bad['cooperate']['fixture']['release'][0]={'object':'panel','action':'invented'}
  with self.assertRaises(ValueError):cooperative_moves.validate(bad,['fixture','panel'])
 def test_forged_contributions_rejected_and_restart_preserves_real_one(self):
  from world.object_networks import project
  p=self.peer('UserOne');self.act(p,'charge');self.admit(1)
  result=dict(state=deepcopy(self.s.module_state),objects=deepcopy(self.s.objects),tiles=[])
  result['state']['world_object_network_state']['mechanism']['cooperators']['fixture/charge'].append('player:Fake')
  with self.assertRaises(ValueError):project(result,self.s)
  result=dict(state=deepcopy(self.s.module_state),objects=deepcopy(self.s.objects),tiles=[])
  control=result['state']['world_object_controls']['fixture']['state'];control['turn']+=1;control['cooperators']['fixture/charge'].append('player:Fake')
  with self.assertRaises(ValueError):project(result,self.s)
  self.s.close();base=self.f.f.f.f.f.f;base.server=base.open();self.s=base.server
  self.assertEqual(self.s.module_state['world_object_network_state']['mechanism']['cooperators'],{'fixture/charge':['player:UserOne']})
  self.assertNotIn('release',actor_objects.offers(self.s,next(o for o in self.s.objects if o['id']=='fixture'))['actions'])
 def test_npc_native_inspection_contributes_without_fabricating_a_player(self):
  from world import overworld_moves
  from world.character_training import source
  p=self.peer('UserOne');self.act(p,'charge');self.admit(1)
  state=deepcopy(self.s.module_state);c=state['world_characters']['harbor_guide'];c['version']+=1;c.pop('plan',None);c['team']=[dict(species=277,level=5,individual='partner')]
  self.f.f.f.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects))
  identity=source(self.s,'harbor_guide','partner');native=dict(size=100,species=277,level=5,personality=identity['personality'],owner=identity['owner'],exp=125,blob='00'*100)
  self.s.db.execute('INSERT INTO character_training VALUES(?,?,?,?,?)',('harbor_guide','partner','a'*64,5,json.dumps(native,sort_keys=True)))
  current=source(self.s,'harbor_guide','partner')
  # Fixture for previously reconciled native MOVES1, not a live native run.
  self.s.db.execute('INSERT INTO actor_move_requests VALUES(?,?,?,?,?,?,?,?)',('inspection','harbor_guide','partner',c['version'],current['token'],'prior',json.dumps({'individual':'partner'}),json.dumps(dict(outcome='native_move_choices',slots=[85,0,0,0]))))
  offer=actor_objects.offers(self.s,next(o for o in self.s.objects if o['id']=='fixture'));self.s.actor_tool_execution=(None,None,dict(id='help'),dict(id='charge'))
  args=dict(object='fixture',action='charge',object_revision=offer['object_revision'],individual='partner',move=85)
  work=overworld_moves.use(self.s,'harbor_guide',{},args);work.dispatch();self.f.f.f.f.advance(3,True)
  self.assertEqual(actor_objects.poll(self.s,'harbor_guide',{},work.data)['outcome'],'validated_object_state_committed')
  status=self.s.module_state['world_object_network_state']['mechanism'];self.assertEqual(set(status['cooperators']['fixture/charge']),{'player:UserOne','npc:harbor_guide'})
 def test_previous_dispatcher_upgrades_without_arbitrary_rewrite(self):
  import ast
  source='def update(context,state):\n return dict(state=state,objects=[],tiles=[])\n'
  request=dict(id='test',target={},actions={},object='p',action='a')
  generated=actor_objects.dispatch_source(source,request,{})
  tree=ast.parse(generated)
  for n in tree.body:
   if isinstance(n,ast.FunctionDef) and n.name=='_ew_object_dispatch_v1':
    n.body=[b for b in n.body if not (isinstance(b,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='cooperation' for t in b.targets)) and not (isinstance(b,ast.If) and isinstance(b.test,ast.Name) and b.test.id=='cooperation')]
  upgraded=actor_objects.dispatch_source(ast.unparse(tree),dict(request,id='next'),{})
  self.assertIn("cooperation=request.get('network_cooperation')",upgraded)
