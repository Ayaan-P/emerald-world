import json,tempfile,unittest
from copy import deepcopy
import test_characters
from world import npc_conversations as speech,actor_runtime as runtime,character_reactions as reactions
from world.runtime_gm import IntentQueue

class ConversationTests(unittest.TestCase):
 def setUp(self):
  self.f=test_characters.CharacterLifecycleTests();self.f.setUp();self.addCleanup(self.f.tearDown);self.s=self.f.server
  self.assertIsNone(self.f.commit({'may':self.f.character},self.f.npc));self.peer=self.f.peer(role='SOCIALCHATCHAR1')
 def say(self):
  message='/guild npc say-public may What are you working on?'
  self.f.send(self.peer,'CHAT %s * %s'%(self.peer['seq']+1,message.encode().hex()))
  row=self.s.db.execute('SELECT seq FROM npc_public_speech').fetchone();self.assertIsNotNone(row);return row[0]
 def plan(self,seq):
  c=deepcopy(self.f.character);c['version']=2;c['evidence']=[seq];c['reason']='Reply to an actual public player question.'
  c['plan']=dict(id='reply',purpose='Choose whether to respond to the actual visitor.',steps=[dict(id='answer',tool='world.reply_player',args=dict(speech=seq,text='I am considering where to train next.'),after=[])])
  self.assertIsNone(self.f.commit({'may':c},self.f.npc))
 def fetch(self,q):return dict(ok=True,world_id=self.s.memory.world_id,**self.s.memory.history(**{k:v for k,v in q.items() if k!='command'}))
 def test_actual_command_independent_author_event_reply_chat_and_restart(self):
  with tempfile.TemporaryDirectory() as td:
   q=IntentQueue(td);self.addCleanup(q.close);reactions.configure(q,self.s.inspect(),'may','Respond independently to public visitors.')
   seq=self.say();self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.fetch)),1)
   job=q.claim();context=self.s.inspect();context['runtime']=dict(kind='character',observed_event=json.loads(job['result']))
   self.assertEqual(reactions.prepare(context,self.fetch)['id'],'may')
   self.plan(seq);self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded')
   speech.flush(self.s)
   messages=[bytes.fromhex(v[3]).decode() for v in self.peer['chat_history']]
   self.assertTrue(any('considering where' in v for v in messages))
   self.assertIn('considering where'.encode().hex().encode(),self.peer['out'])
   count=len(messages);speech.flush(self.s);self.assertEqual(len(self.peer['chat_history']),count)
   event=next(e for e in self.s.memory.history()['events'] if e.get('event')=='player_addressed_character')
   self.assertNotIn('trainer',event);self.assertNotIn('player',event)
   self.s.close();self.f.server=self.f.open();self.s=self.f.server
   self.assertEqual(speech.inbox(self.s)['may'][0]['status'],'replied')
 def test_remote_and_new_session_do_not_get_delayed_reply(self):
  self.peer['state'][2]+=10
  self.s.guild_chat.handle(self.peer,'/guild npc say-public may Hello')
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM npc_public_speech').fetchone()[0],0)
  self.peer['state'][2]-=10;seq=self.say();self.plan(seq)
  self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded');self.peer['npc_speech_session']='different'
  speech.flush(self.s)
  self.assertEqual(self.s.db.execute('SELECT delivery FROM npc_public_speech').fetchone()[0],'not_nearby')
 def test_wrong_actor_and_duplicate_reply_do_not_invent_delivery(self):
  seq=self.say()
  with self.assertRaises(ValueError):speech.reply(self.s,'other',{},dict(speech=seq,text='No'))
  self.plan(seq);runtime.tick(self.s,now=10)
  self.assertEqual(speech.reply(self.s,'may',{},dict(speech=seq,text='I am considering where to train next.'))['outcome'],'already_replied')
 def test_nearby_group_hears_actual_speech_and_reply_without_host_lock(self):
  bob=self.f.peer('Bob',role='SOCIALCHATCHAR1');far=self.f.peer('Far',role='SOCIALCHATCHAR1')
  far['state'][2]+=12
  seq=self.say();speech.flush(self.s)
  def messages(p):return [bytes.fromhex(v[3]).decode() for v in p.get('chat_history',[])]
  self.assertTrue(any('Visitor to May' in x for x in messages(bob)))
  self.assertFalse(any('Visitor to May' in x for x in messages(far)))
  # A second participant may address the same actor; no host/speaker ownership.
  speech.command(self.s,bob,['say-public','may','Can I join you?'])
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM npc_public_speech').fetchone()[0],2)
  self.plan(seq);runtime.tick(self.s,now=10);speech.flush(self.s)
  self.assertTrue(any('considering where' in x for x in messages(bob)))
  self.assertFalse(any('considering where' in x for x in messages(far)))
  n=len(messages(bob));speech.flush(self.s);self.assertEqual(len(messages(bob)),n)
 def test_audience_is_session_scoped_and_late_arrivals_do_not_replay(self):
  bob=self.f.peer('Bob',role='SOCIALCHATCHAR1');seq=self.say()
  bob['npc_speech_session']='replacement'
  late=self.f.peer('Late',role='SOCIALCHATCHAR1')
  self.plan(seq);runtime.tick(self.s,now=10);speech.flush(self.s)
  for p in (bob,late):
   self.assertFalse(any('considering where' in bytes.fromhex(v[3]).decode() for v in p.get('chat_history',[])))
  self.s.close();self.f.server=self.f.open();self.s=self.f.server
  speech.flush(self.s)
  self.assertEqual(self.s.db.execute('SELECT sum(answered) FROM npc_speech_audience').fetchone()[0],2)
