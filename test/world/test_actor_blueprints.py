import copy,json,sqlite3,unittest
import test_battle_campaigns as fixture
from world import actor_blueprints as blueprints,actor_runtime as runtime
from world.battle_campaigns import command,active

class BlueprintTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.BattleCampaignTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
 def test_large_authored_document_executes_actual_campaign(self):
  nodes={f'n{i}':dict(opponent='field_researcher',win=[f'n{i+1}'] if i<15 else [],loss=[]) for i in range(16)}
  d=dict(id='assembled',title='An authored circuit',entry='n0',nodes=nodes)
  direct=dict(id='too_large',purpose='Publish.',steps=[dict(id='p',tool='world.publish_battle_campaign',args=dict(campaign=json.dumps(d)),after=[])])
  with self.assertRaises(ValueError):runtime.validate(direct)
  steps=[]
  for chunk in range(4):
   if not chunk:ops=[dict(op='set',path='',value=dict(d,nodes={f'n{i}':nodes[f'n{i}'] for i in range(4)}))]
   else:ops=[dict(op='set',path=f'/nodes/n{i}',value=nodes[f'n{i}']) for i in range(chunk*4,chunk*4+4)]
   steps.append(dict(id=f'edit{chunk}',tool='world.edit_blueprint',args=dict(id='draft',revision=chunk,patch=json.dumps(ops,separators=(',',':'))),after=[f'edit{chunk-1}'] if chunk else []))
  steps.append(dict(id='snapshot',tool='world.inspect_blueprint',args=dict(id='draft'),after=['edit3']))
  steps.append(dict(id='publish',tool='world.publish_battle_campaign',args=dict(campaign=dict(result='snapshot',key='document')),after=['snapshot']))
  plan=dict(id='assemble',purpose='Build playable content across bounded edits.',steps=steps);runtime.validate(plan)
  self.s.module_state['world_characters']['field_researcher']['plan']=plan
  for i in range(6):self.assertEqual(runtime.tick(self.s,now=10+i*6)['status'],'succeeded')
  self.assertEqual(json.loads(blueprints.inspect(self.s,'field_researcher',{},dict(id='draft'))['document']),d)
  command(self.s,self.f.a,['start','assembled']);self.f.battle(1)
  self.assertEqual(active(self.s,self.f.a)[1]['choices'],['n1'])
  command(self.s,self.f.a,['choose','n1']);self.f.battle(2)
  self.assertEqual(active(self.s,self.f.a)[1]['status'],'complete')
  self.assertEqual(self.f.f.fixture.stats(),(0,0,0))
 def edit(self,revision,ops,name='draft'):
  with self.s.db:return blueprints.edit(self.s,'field_researcher',{},dict(id=name,revision=revision,patch=json.dumps(ops)))
 def test_restart_revision_guards_and_snapshot_immutability(self):
  self.edit(0,[dict(op='set',path='/items',value=[1,2])]);snapshot=blueprints.inspect(self.s,'field_researcher',{},dict(id='draft'))
  db=sqlite3.connect(':memory:');self.s.db.backup(db);old=self.s.db;self.s.db=db
  try:
   blueprints.setup(db);self.edit(1,[dict(op='set',path='/items/-',value=3)])
   self.assertEqual(json.loads(snapshot['document']),dict(items=[1,2]))
   self.assertEqual(json.loads(blueprints.inspect(self.s,'field_researcher',{},dict(id='draft'))['document']),dict(items=[1,2,3]))
   with self.assertRaises(ValueError):self.edit(1,[dict(op='remove',path='/items/0')])
   with self.assertRaises(ValueError):blueprints.inspect(self.s,'other',{},dict(id='draft'))
  finally:self.s.db=old;db.close()
 def test_failed_patch_and_receipt_rollback_no_partial_changes(self):
  self.edit(0,[dict(op='set',path='/ok',value=1)])
  with self.assertRaises(ValueError):self.edit(1,[dict(op='set',path='/ok',value=2),dict(op='remove',path='/missing')])
  self.assertEqual(blueprints.inspect(self.s,'field_researcher',{},dict(id='draft'))['revision'],1)
  with self.assertRaises(RuntimeError):
   with self.s.db:
    blueprints.edit(self.s,'field_researcher',{},dict(id='draft',revision=1,patch='[{"op":"set","path":"/ok","value":3}]'))
    raise RuntimeError('later execution receipt failed')
  self.assertEqual(blueprints.inspect(self.s,'field_researcher',{},dict(id='draft'))['revision'],1)
 def test_close_releases_capacity_and_preserves_audit(self):
  for i in range(16):self.edit(0,[dict(op='set',path='/x',value=i)],f'd{i}')
  with self.assertRaises(ValueError):self.edit(0,[dict(op='set',path='/x',value=99)],'extra')
  with self.s.db:blueprints.close(self.s,'field_researcher',{},dict(id='d0',revision=1))
  self.edit(0,[dict(op='set',path='/x',value=99)],'extra')
  self.assertTrue(blueprints.inspect(self.s,'field_researcher',{},dict(id='d0'))['closed'])
  with self.assertRaises(ValueError):self.edit(1,[dict(op='set',path='/x',value=99)],'d0')
 def test_json_paths_and_unpublishable_data_do_not_gain_authority(self):
  result=blueprints.patch({},[dict(op='set',path='/a~1b',value=[]),dict(op='set',path='/a~1b/-',value=True)])
  self.assertEqual(result,{'a/b':[True]})
  for operations in ([dict(op='set',path='',value=[])],[dict(op='set',path='/bad',value=1.5)],[dict(op='set',path='/~x',value=1)]):
   with self.assertRaises(ValueError):blueprints.patch({},operations)
  self.edit(0,[dict(op='set',path='/arbitrary',value='data only')])
  from world.battle_campaigns import publish
  with self.assertRaises(ValueError):publish(self.s,'field_researcher',{},dict(campaign=blueprints.inspect(self.s,'field_researcher',{},dict(id='draft'))['document']))
