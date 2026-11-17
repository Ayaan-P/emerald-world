import ast,unittest
import test_actor_object_programs as fixture
from world import actor_objects

class DispatcherTests(unittest.TestCase):
 def test_more_than_32_uses_stay_bounded_and_history_survives_restart(self):
  f=fixture.ProgramTests();f.setUp();self.addCleanup(f.doCleanups);f.install();s=f.s
  peer=f.f.connect('User',True);send=lambda line:f.f.f.f.send(peer,line)
  send('CAVE GET');send('CAVE ACK '+s.shared_cave.identity)
  sizes=[]
  for index in range(40):
   f.f.f.f.state(peer,*s.wilds_map,72,69);peer['state'][4]=1;peer['last_interaction']=-1
   send('INTERACT_REGION %s fixture %s'%(peer['seq']+1,s.shared_cave.identity));self.assertIsNotNone(s.deployment)
   f.f.f.advance(index*2+1,True);actor_objects.poll_player(s);f.f.f.advance(index*2+2)
   sizes.append(len(s.candidate.source));self.assertEqual(len(s.module_state['world_object_current_receipt']),1)
  self.assertEqual(s.db.execute('SELECT count(*) FROM object_transition_archive').fetchone()[0],40)
  self.assertLess(max(sizes)-min(sizes),2000)
  self.assertEqual(sum(isinstance(n,ast.FunctionDef) and n.name=='_ew_object_dispatch_v1' for n in ast.parse(s.candidate.source).body),1)
  self.assertEqual(s.db.execute("SELECT count(*) FROM events WHERE kind='world_memory' AND data LIKE '%object_action_applied%'").fetchone()[0],40)
  s.close();base=f.f.f.f.f;base.server=base.open();f.s=base.server;s=f.s
  self.assertEqual(s.module_state['world_object_controls']['fixture']['state'],{'phase':'first'})
 def test_legacy_wrapper_and_receipts_survive_without_replay(self):
  import inspect
  source="def update(context,state):\n return dict(state=state,objects=[dict(id='p',x=1,y=1,gfx=0,text='Old.')],tiles=[])\ndef actor_interact(obj,action,state):\n return dict(state={'uses':state.get('uses',0)+1},x=1,y=1,gfx=0,text='Used.')\n"
  request=dict(actor='',id='old',object='p',action='use',target=dict(id='p',x=1,y=1,gfx=0,text='Old.'),actions={'use':'Use'},player_use=True)
  legacy=source+'\n_previous=update\n'+inspect.getsource(actor_objects.object_step)+f"\ndef update(context,state):\n return object_step(_previous(context,state),{request!r},actor_interact)\n"
  ns={};exec(legacy,ns);state={'world_object_actions':{'p':{'use':'Use'}},'world_object_player_use':{'p':'use'}}
  first=ns['update']({},state);old_receipt=first['state']['world_object_action_receipts']['old'].copy()
  fresh=dict(request,id='new',target=first['objects'][0])
  ns={};exec(actor_objects.dispatch_source(legacy,fresh,first['state']),ns)
  result=ns['update']({},first['state']);again=ns['update']({},result['state'])
  self.assertEqual(again['state']['world_object_controls']['p']['state']['uses'],2)
  self.assertEqual(again['state']['world_object_action_receipts']['old'],old_receipt)
  self.assertEqual(list(again['state']['world_object_current_receipt']),['new'])
 def test_modified_dispatcher_is_not_silently_rewritten(self):
  source='def update(context,state):\n return dict(state=state,objects=[],tiles=[])\n'
  request=dict(id='test',target={},actions={},object='p',action='a')
  generated=actor_objects.dispatch_source(source,request,{})
  with self.assertRaises(ValueError):actor_objects.dispatch_source(generated.replace('receipts.clear()','receipts.clear(); print(1)'),request,{})
