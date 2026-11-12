import copy,json,sqlite3,time,unittest
import test_shared_outbreaks as fixture
from world import actor_runtime as runtime,actor_stories,shared_outbreaks


def document():
 return dict(id='shared_choice',title='A public decision',qualities=dict(decision=dict(scope='place',initial=0,max=2)),scenes=dict(decide=dict(place='Route102',text='Choose a future direction.',requires={},once='world',choices=dict(yes=dict(text='Ask for a habitat change',requires={},effects=dict(decision=1),result='The request is recorded, not yet acted on.'),no=dict(text='Leave things alone',requires={},effects=dict(decision=2),result='The request is declined.')))))

class ActorStories(unittest.TestCase):
 def setUp(self):
  self.f=fixture.OutbreakTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  token=self.s.create_identity('Alice')['token'];self.p=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
  self.s._line(self.p,f'HELLO 1 Alice {token} SOCIALCHATCOMMANDS1OUTBREAK1'.encode())
  from world.build_catalog import catalog_maps
  pair=next(k for k,v in catalog_maps().items() if v['name']=='Route102')
  self.f.f.state(self.p,*pair,1,1)
 def chat(self,text):
  self.p['chat_credit']=4;self.s._line(self.p,f"CHAT {self.p['seq']+1} * {text.encode().hex()}".encode())
  out=[bytes.fromhex(x[3]).decode() for x in self.p['chat_history']];self.p['chat_history']=[];return out
 def plan(self):
  steps=[dict(id='offer',tool='world.publish_story',args=dict(pack=json.dumps(document(),separators=(',',':'))),after=[]),dict(id='hear',tool='world.await_story_choice',args=dict(pack='shared_choice',after_cursor=0),after=['offer']),dict(id='act',tool='world.configure_outbreak',args=self.f.args,after=['hear'],when=dict(step='hear',path='/choice',equals='yes'))]
  c=dict(self.f.f.character,version=2,plan=dict(id='respond',purpose='Offer a choice and respond to its actual outcome.',steps=steps))
  self.f.f.commit(dict(state={'world_characters':{'harbor_guide':c}},tiles=[],objects=[self.f.f.obj]));self.assertIsNone(self.s.module_error)
 def choose(self,choice):
  lines=self.chat('/story shared_choice');self.assertTrue(any('PUBLIC choices' in x for x in lines))
  cmd=next(x for x in lines if x.startswith('/story pick-public') and ' '+choice+' ' in x)
  return cmd,self.chat(cmd)
 def test_actual_player_choice_then_real_gameplay_effect_no_early_action(self):
  self.plan();self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded')
  self.assertIsNone(shared_outbreaks.line(self.s,self.p))
  cmd,_=self.choose('yes') # Before wait starts: must not lose this committed choice.
  self.assertIsNone(shared_outbreaks.line(self.s,self.p))
  self.assertEqual(runtime.tick(self.s,now=16)['status'],'pending')
  self.assertEqual(runtime.tick(self.s,now=22)['status'],'succeeded')
  self.assertEqual(runtime.tick(self.s,now=28)['status'],'succeeded')
  self.assertIn('WILD_OUTBREAK',self.s._snapshot(self.p))
  self.chat(cmd);self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_public_results').fetchone()[0],1)
  event=next(e for e in self.s.memory.history()['events'] if e['event']=='public_story_choice_committed')
  self.assertNotIn('Alice',json.dumps(event));self.assertNotIn('trainer',event);self.assertTrue(actor_stories.relevant(event,'harbor_guide'))
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_players').fetchone()[0],0)
 def test_decline_skips_action_and_restart_retains_receipt(self):
  self.plan();runtime.tick(self.s,now=10);self.choose('no');runtime.tick(self.s,now=16)
  self.s.close();case=self.f.f.f;case.server=case.open();self.s=case.server
  self.assertEqual(runtime.tick(self.s,now=22)['status'],'succeeded')
  self.assertEqual(runtime.tick(self.s,now=28)['status'],'skipped')
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM shared_outbreaks').fetchone()[0],0)
 def test_no_private_adoption_or_silent_public_choice_and_atomic_event(self):
  d=document();self.s.opportunities.publish(d)
  with self.assertRaises(ValueError):actor_stories.publish(self.s,'harbor_guide',{},dict(pack=json.dumps(d)))
  d['id']='new_public'
  with self.s.db:actor_stories.publish(self.s,'harbor_guide',{},dict(pack=json.dumps(d,separators=(',',':'))))
  with self.assertRaises(ValueError):self.s.opportunities.choose('Alice','Route102','new_public','decide','yes',0,'r1')
  self.s.db.execute("CREATE TRIGGER fail_public BEFORE INSERT ON story_public_results BEGIN SELECT RAISE(ABORT,'fixture'); END")
  before=self.s.memory.history()['through']
  with self.assertRaises(sqlite3.Error):self.s.opportunities.choose('Alice','Route102','new_public','decide','yes',0,'r1',public=True)
  self.assertEqual(self.s.memory.history()['through'],before);self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_consequences').fetchone()[0],0)
 def test_reject_private_scope_and_other_actor_wait(self):
  d=document();d['qualities']['decision']['scope']='player'
  with self.assertRaises(ValueError):actor_stories.publish(self.s,'harbor_guide',{},dict(pack=json.dumps(d)))
  self.plan();runtime.tick(self.s,now=10)
  with self.assertRaises(ValueError):actor_stories.wait(self.s,'other',{},dict(pack='shared_choice',after_cursor=0))

 def test_private_choices_do_not_emit_public_records(self):
  self.s.opportunities.publish(document());before=self.s.memory.history()['through']
  self.s.opportunities.choose('Alice','Route102','shared_choice','decide','yes',0,'private_request')
  self.assertEqual(self.s.memory.history()['through'],before)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_public_results').fetchone()[0],0)
