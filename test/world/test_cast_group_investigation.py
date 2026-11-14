"""Original actor -> 4-person field investigation -> private completion -> shared decision."""
import copy,json,time,unittest
import test_canonical_cast as fixture
from world import canonical_cast as cast,canonical_investigations as investigations,character_reactions as reactions
from world.canonical_project_panel import panel
from world.runtime_gm import IntentQueue
import tempfile

class GroupInvestigationTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CanonicalCastTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  self.pack=dict(id='route_notes',title='Compare route research cards',roles=['North reader','South reader','Coast reader','Interpreter'],ending='Your group compared its research cards.',stages=[dict(title='Compare four cards',stations=[dict(at=list(p),clue='Your research card says '+part+'.') for p,part in zip(investigations.STATIONS,['DA','W','N','Combine the first three cards'])],answer='DAWN',result='Your interpretation is ready to discuss.')])
  a=self.f.action();a['changes'].update(places=['native:LittlerootTown','native:PetalburgCity','native:RustboroCity','native:MauvilleCity_BikeShop'],investigation=self.pack,initiative=dict(id='route_discussion',title='Discuss route research',qualities=dict(published=dict(scope='place',initial=0,max=1)),scenes=dict(
   consider=dict(place='MauvilleCity_BikeShop',text='Rydel may consider the proposed research.',actors=['canon_rydel'],requires=dict(published=[1,1]),once='world',choices=dict(review=dict(text='Review the interpretation',requires={},effects=dict(published=-1),result='Rydel reopened the discussion.'))),
   publish=dict(place='MauvilleCity_BikeShop',text='Public project choice: share your group interpretation?',mystery=self.pack['id'],requires=dict(published=[0,0]),once='world',choices=dict(share=dict(text='Publish interpretation',requires={},effects=dict(published=1),result='The shared interpretation is available for discussion.'))))))
  self.f.apply(a)
  self.peers=[self.f.peer(n) for n in ('Alice','Bob','Cara','Dan')]
  for p in self.peers:p['core_active_run']='a'*32
 def at(self,p,role):
  p['state'][:4]=list(investigations.STATIONS[role]);p['state_time']=time.monotonic()
 def test_four_trainers_choose_roles_complete_privately_then_return_to_original_actor(self):
  before=self.s.memory.history()
  # Starter is a reader, not the solver. Others independently choose remaining roles.
  self.s.mysteries.command('Alice',['start','route_notes','2']);run=self.s.mysteries._current('Alice')[0]
  self.s.mysteries.command('Bob',['join',run,'4'])
  self.assertEqual(self.s.mysteries._current('Bob')[3],'waiting')
  self.s.mysteries.command('Cara',['join',run,'1']);self.s.mysteries.command('Dan',['join',run,'3'])
  for p,role in zip(self.peers,[1,3,0,2]):
   self.at(p,role);self.assertIn(self.pack['stages'][0]['stations'][role]['clue'],self.s.mysteries.command(p['id'],['clue']))
  self.peers[2]['state_time']-=100
  with self.assertRaises(ValueError):self.s.mysteries.command('Bob',['solve','1','DAWN'])
  self.at(self.peers[2],0);self.s.mysteries.command('Bob',['solve','1','DAWN'])
  self.assertEqual(self.s.memory.history(),before) # No private completion disclosure.
  for name in ('Alice','Bob','Cara','Dan'):self.assertTrue(self.s.mysteries.completed(name,'route_notes'))
  self.assertFalse(self.s.mysteries.completed('Eve','route_notes'))
  bob=self.f.peer('Bob');self.f.query(bob);ui=panel(self.s,bob,'a'*32,'rydel','view');self.assertEqual(ui['role'],4)
  eve=self.f.peer('Eve');self.f.query(eve);self.assertEqual(panel(self.s,eve,'a'*32,'rydel','view')['role'],5)
  with tempfile.TemporaryDirectory() as tmp:
   q=IntentQueue(tmp)
   try:
    reactions.configure(q,self.s.inspect(),'canon_rydel','Consider actual shared interpretations.')
    panel(self.s,bob,'a'*32,'rydel','pick:'+ui['session']+':1:1')
    event=self.s.memory.history()['events'][-1];self.assertEqual(event['event'],'canonical_shared_project_decided')
    for name in ('Alice','Bob','Cara','Dan','DAWN'):self.assertNotIn(name,json.dumps(event))
    for key in ('trainer','clue','answer','run'):self.assertNotIn(key,event)
    self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.f.fetch)),1)
    next_action=self.f.action(1);next_action['changes'].update(goal='Reconsider my research from the published interpretation',evidence=[event['seq']]);self.f.apply(next_action)
   finally:q.close()
  self.s.close();self.f.f.case.server=self.f.f.case.open();self.s=self.f.f.case.server;self.f.s=self.s
  dan=self.f.peer('Dan');dan['core_active_run']='a'*32
  self.assertTrue(self.s.mysteries.completed('Dan','route_notes'))
  self.assertEqual(cast.records(self.s.module_state)['canon_rydel']['version'],2)
 def test_role_collision_cancel_and_replay_no_partial_completion(self):
  self.s.mysteries.command('Alice',['start','route_notes','4']);run=self.s.mysteries._current('Alice')[0]
  with self.assertRaises(ValueError):self.s.mysteries.command('Bob',['join',run,'4'])
  self.assertIsNone(self.s.mysteries._current('Bob'))
  with self.assertRaises(ValueError):self.s.mysteries.command('Bob',['join',run,'5'])
  self.s.mysteries.command('Bob',['join',run]);self.s.mysteries.command('Bob',['join',run])
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM mystery_members WHERE run=?',(run,)).fetchone()[0],2)
  self.s.mysteries.command('Alice',['leave']);self.assertFalse(self.s.mysteries.completed('Bob','route_notes'))
 def test_unsupported_station_and_private_actor_gates_rejected(self):
  a=self.f.action(1);a['changes']['investigation']=copy.deepcopy(self.pack);a['changes']['investigation']['stages'][0]['stations'][0]['at']=[0,0,0,0]
  with self.assertRaises(ValueError):cast.compile_actions([a],self.f.context())

 def test_three_role_pack_preserves_participant_only_completion(self):
  pack=copy.deepcopy(self.pack);pack['id']='three_cards';pack['roles']=pack['roles'][:3];pack['stages'][0]['stations']=pack['stages'][0]['stations'][:3]
  self.s.mysteries.publish(pack)
  self.s.mysteries.command('Alice',['start','three_cards']);run=self.s.mysteries._current('Alice')[0]
  self.s.mysteries.command('Bob',['join',run]);self.s.mysteries.command('Cara',['join',run])
  for role,p in enumerate(self.peers[:3]):self.at(p,role);self.s.mysteries.command(p['id'],['clue'])
  self.s.mysteries.command('Cara',['solve','1','DAWN'])
  self.assertTrue(self.s.mysteries.completed('Bob','three_cards'))
  self.assertFalse(self.s.mysteries.completed('Dan','three_cards'))

 def finish_current_group(self):
  self.s.mysteries.command('Alice',['start','route_notes']);run=self.s.mysteries._current('Alice')[0]
  for role,p in enumerate(self.peers[1:],1):self.s.mysteries.command(p['id'],['join',run,str(role+1)])
  for role,p in enumerate(self.peers):self.at(p,role);self.s.mysteries.command(p['id'],['clue'])
  return run

 def test_save_a_completion_does_not_unlock_save_b_before_or_after_restart(self):
  run=self.finish_current_group();self.s.mysteries.command('Dan',['solve','1','DAWN'])
  alice=self.peers[0]
  from world.build_catalog import catalog_maps
  alice['state'][:2]=next(k for k,v in catalog_maps().items() if v['name']=='MauvilleCity_BikeShop')
  cast.response(self.s,alice,'b'*32,'rydel')
  self.assertFalse(self.s.mysteries.completed('Alice','route_notes'))
  self.assertEqual(panel(self.s,alice,'b'*32,'rydel','view')['role'],5)
  cast.response(self.s,alice,'a'*32,'rydel')
  self.assertTrue(self.s.mysteries.completed('Alice','route_notes'))
  self.assertEqual(panel(self.s,alice,'a'*32,'rydel','view')['role'],4)
  self.s.close();self.f.f.case.server=self.f.f.case.open();self.s=self.f.s=self.f.f.case.server
  alice=self.f.peer('Alice');cast.response(self.s,alice,'b'*32,'rydel')
  self.assertFalse(self.s.mysteries.completed('Alice','route_notes'))
  cast.response(self.s,alice,'a'*32,'rydel');self.assertTrue(self.s.mysteries.completed('Alice','route_notes'))
  # An older completion with no reliable save identity cannot be guessed into A.
  with self.s.db:self.s.db.execute('DELETE FROM mystery_lineages WHERE run=?',(run,))
  self.assertFalse(self.s.mysteries.completed('Alice','route_notes'))
  self.assertEqual(self.s.db.execute('SELECT status FROM mystery_runs WHERE id=?',(run,)).fetchone(),('completed',))

 def test_switching_save_cannot_supply_another_saves_station_or_cancel_its_run(self):
  run=self.finish_current_group();self.peers[0]['core_active_run']='b'*32
  with self.assertRaises(ValueError):self.s.mysteries.command('Dan',['solve','1','DAWN'])
  with self.assertRaises(ValueError):self.s.mysteries.command('Alice',['clue'])
  with self.assertRaises(ValueError):self.s.mysteries.command('Alice',['leave'])
  self.assertEqual(self.s.db.execute('SELECT status FROM mystery_runs WHERE id=?',(run,)).fetchone(),('active',))
  self.peers[0]['core_active_run']='a'*32
  self.s.mysteries.command('Dan',['solve','1','DAWN'])
  self.assertTrue(self.s.mysteries.completed('Alice','route_notes'))

 def test_unbound_start_rolls_back_without_assigning_a_role(self):
  self.peers[0].pop('core_active_run')
  with self.assertRaisesRegex(ValueError,'Connect this save'):self.s.mysteries.command('Alice',['start','route_notes'])
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM mystery_runs').fetchone()[0],0)
