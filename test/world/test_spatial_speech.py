import copy,json,tempfile,time,unittest
from unittest.mock import patch
import test_actor_navigation as fixture
from world import spatial_speech as speech,actor_runtime as runtime,character_reactions as reactions
from world.runtime_gm import IntentQueue
from world.guilds import GuildError

class SpatialSpeechTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.NavigationTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s;self.peer=self.f.peer
  self.f.f.state(self.peer,*self.s.wilds_map,72,70)
 def publish(self,actor='harbor_guide',text='What should we study?',radius=4):
  with self.s.db:return speech.speak(self.s,actor,{},dict(text=text,radius=radius))
 def messages(self,peer=None):return [bytes.fromhex(x[3]).decode() for x in (peer or self.peer).get('chat_history',[])]
 def fetch(self,q):return dict(ok=True,world_id=self.s.memory.world_id,**self.s.memory.history(**{k:v for k,v in q.items() if k!='command'}))
 def test_actual_group_speech_independent_recipient_and_nearby_chat(self):
  with tempfile.TemporaryDirectory() as tmp:
   queue=IntentQueue(tmp);self.addCleanup(queue.close)
   reactions.configure(queue,self.s.inspect(),'second','Choose independently whether to answer public nearby speech.')
   first=self.publish();self.assertEqual(first['recipients'],['second'])
   self.assertEqual(len(reactions.observe(queue,self.s.inspect(),self.fetch)),1)
   self.assertNotIn('reply',self.s.module_state['world_characters']['second'])
   speech.flush(self.s);self.assertTrue(any('What should we study?' in x for x in self.messages()))
   self.publish('second','I would rather explore.',4);speech.flush(self.s)
   self.assertTrue(any('I would rather explore.' in x for x in self.messages()))
   events=[e for e in self.s.memory.history()['events'] if e.get('event')=='spatial_public_speech']
   self.assertEqual([e['character_id'] for e in events],['harbor_guide','second'])
   self.assertNotIn('Alice',json.dumps(events));self.assertNotIn('session',json.dumps(events))
 def test_player_can_join_public_group_without_assigning_npc_response(self):
  from world.npc_conversations import command
  lines=command(self.s,self.peer,['speak-public','Can','we','explore','together?'])
  self.assertIn('2 nearby NPCs',lines[0]);speech.flush(self.s)
  event=next(e for e in self.s.memory.history()['events'] if e.get('event')=='spatial_public_speech')
  self.assertIsNone(event['character_id']);self.assertEqual({r['id'] for r in event['recipients']},{'harbor_guide','second'})
  self.assertTrue(speech.relevant(event,'second'));self.assertFalse(speech.relevant(event,'unrelated'))
  self.assertTrue(any('Visitor: Can we explore together?' in x for x in self.messages()))
  with self.assertRaises(GuildError):command(self.s,self.peer,['speak-public','Again'])
 def test_runtime_plan_receipt_is_real_and_does_not_force_reply(self):
  state=copy.deepcopy(self.s.module_state);c=state['world_characters']['harbor_guide'];c['version']+=1
  c['plan']=dict(id='talk',purpose='Ask an open question.',steps=[dict(id='speak',tool='world.speak',args=dict(text='What do you think?',radius=4),after=[])])
  self.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects));self.assertIsNone(self.s.module_error)
  self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded');speech.flush(self.s)
  self.assertTrue(any('What do you think?' in x for x in self.messages()));self.assertIsNone(runtime.tick(self.s,now=16))
 def test_no_replay_to_new_session_or_late_arrival(self):
  self.publish();self.peer['npc_speech_session']='new-session';speech.flush(self.s)
  self.assertFalse(self.messages())
  self.assertEqual(self.s.db.execute('SELECT sum(delivered) FROM spatial_speech_audience').fetchone()[0],1)
  self.s.close();self.f.f.f.server=self.f.f.f.open();self.s=self.f.f.f.server
  speech.flush(self.s)
  with self.assertRaises(ValueError):self.publish()
 def test_leaving_place_stale_ready_or_expired_delivery_is_not_live(self):
  self.publish();self.peer['state'][2]=90;speech.flush(self.s);self.assertFalse(self.messages())
  with self.s.db:self.s.db.execute('DELETE FROM spatial_speech_cooldown')
  self.f.f.state(self.peer,*self.s.wilds_map,72,70);self.publish()
  with patch('world.spatial_speech.time.time',return_value=time.time()+16):speech.flush(self.s)
  self.assertFalse(self.messages())
 def test_geometry_does_not_transmit_through_disconnected_ground(self):
  from world.shared_cave import SharedCave
  from test_shared_generated_cave import BLOB
  cave=SharedCave(BLOB)
  # Actual catalog geometry: every returned cell must be walkable and within
  # connected cardinal distance, never merely a square around the speaker.
  origin=dict(group=0,num=0,x=71,y=70,region_revision=self.f.revision,radius=4)
  cells=speech.footprint(self.s,origin)
  self.assertIn((74,70),cells);self.assertNotIn((76,70),cells)
  with self.s.db:
   self.s.db.execute('UPDATE generated_area_archive SET template=? WHERE identity=?',(BLOB,self.f.revision))
  with self.assertRaises(ValueError):speech.footprint(self.s,origin)
 def test_unavailable_actor_wrong_revision_and_unauthed_player(self):
  self.s.objects[1]['region_revision']='f'*64
  self.peer['state'][2]=90
  with self.assertRaises(ValueError):self.publish()
  with self.assertRaises(ValueError):self.publish('missing')
  fake=dict(self.peer);fake['state']=list(self.peer['state']);fake['state'][2]=72
  with self.assertRaises(GuildError):speech.command(self.s,fake,['Hello'])
 def test_rate_limit_and_invalid_text_do_not_add_history(self):
  self.publish();before=self.s.memory.history()['through']
  with self.assertRaises(ValueError):self.publish(text='Another line')
  self.assertEqual(self.s.memory.history()['through'],before)
  for text in ('','bad\nline','x'*81):
   with self.assertRaises(ValueError):self.publish('second',text)
  self.assertEqual(self.s.memory.history()['through'],before)

 def test_three_independent_npcs_receive_only_actual_local_public_speech(self):
  state=copy.deepcopy(self.s.module_state);third=copy.deepcopy(state['world_characters']['second']);third.update(name='Third',object_id='third')
  state['world_characters']['third']=third
  objects=copy.deepcopy(self.s.objects)+[dict(self.s.objects[1],id='third',x=72,y=71)]
  self.f.f.commit(dict(state=state,tiles=[],objects=objects));self.assertIsNone(self.s.module_error)
  result=self.publish();self.assertEqual(set(result['recipients']),{'second','third'})
  event=next(e for e in self.s.memory.history()['events'] if e.get('event')=='spatial_public_speech')
  self.assertTrue(speech.relevant(event,'second'));self.assertTrue(speech.relevant(event,'third'));self.assertFalse(speech.relevant(event,'harbor_guide'))
 def test_native_map_uses_explicit_proximity_policy_and_existing_chat(self):
  import test_npc_conversations as native
  f=native.ConversationTests();f.setUp();self.addCleanup(f.doCleanups)
  with f.s.db:speech.speak(f.s,'may',{},dict(text='A visitor is welcome.',radius=4))
  speech.flush(f.s)
  self.assertTrue(any('A visitor is welcome.' in bytes.fromhex(x[3]).decode() for x in f.peer['chat_history']))
  event=next(e for e in f.s.memory.history()['events'] if e.get('event')=='spatial_public_speech')
  self.assertEqual(event['origin']['radius'],2);self.assertNotIn('region_revision',event['origin'])
 def test_real_pending_movement_prevents_physical_speech_claim(self):
  self.f.plan('harbor_guide',78,70);runtime.tick(self.s,now=10);self.f.advance(0,True)
  with self.assertRaises(ValueError):self.publish()

 def test_public_history_retrieval_finds_recipient_place_and_spoken_words(self):
  from world.actor_history import search
  result=self.publish(text='Study the old trees.')
  place=self.s.memory.place(self.f.revision)
  found=search(self.s,'second',{},dict(query=json.dumps(dict(actor='second',place=place,terms=['old trees'])),after=0,through=0))
  self.assertEqual(found['first_sequence'],result['speech'])
  self.assertEqual(found['events'][0]['record']['text'],'Study the old trees.')
  # Unrelated event schemas cannot cause JSON parsing errors in recipient search.
  with self.s.db:self.s.memory.append('other_public_event',dict(recipients=['not an object']))
  search(self.s,'second',{},dict(query=json.dumps(dict(actor='second')),after=0,through=0))
