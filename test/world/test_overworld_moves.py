import json,unittest
from copy import deepcopy
import test_actor_object_programs as fixture
from world import actor_objects,object_choices,overworld_moves
from world.guilds import GuildError

class MoveEffects(unittest.TestCase):
 def setUp(self):
  self.f=fixture.ProgramTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  for phase,action,move in [('first','turn',52),('second','reset',55)]:
   n=self.f.program['states'][phase];n.update(use='',choices=[action],moves={action:[move]})
  self.f.install();self.peer=self.f.f.connect('User',True)
  send=lambda line:self.f.f.f.f.send(self.peer,line)
  send('CAVE GET');send('CAVE ACK '+self.s.shared_cave.identity)
  self.f.f.f.f.state(self.peer,*self.s.wilds_map,72,69);self.peer['state'][4]=1
 def offer(self):
  lines=object_choices.command(self.s,self.peer,['moves']);self.assertIn('public',lines[1]);self.assertTrue(all(len(line)<=120 for line in lines));return self.peer['object_moves']['token']
 def act(self,action,move):
  object_choices.command(self.s,self.peer,['move',self.offer(),action,str(move)])
 def admit(self,n):
  self.f.f.f.advance(n,True);actor_objects.poll_player(self.s);self.f.f.f.advance(n+1)
 def test_guild_wire_discovery_fits_native_chat(self):
  self.assertTrue(self.s.guild_chat.handle(self.peer,'/guild object moves'))
  self.assertIn('object_moves',self.peer)
  self.assertTrue(any('public' in bytes.fromhex(row[3]).decode() for row in self.peer['chat_history']))
 def test_two_moves_real_shared_effect_receipts_restart(self):
  self.act('turn',52);self.assertEqual(self.s.objects[-1]['text'],'First face.');self.admit(1)
  self.assertEqual(self.s.objects[-1]['text'],'Second face.');self.act('reset',55);self.admit(3)
  self.assertEqual(self.s.objects[-1]['text'],'First face.')
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM world_move_intents WHERE seq IS NOT NULL').fetchone()[0],2)
  evidence=json.loads(self.s.db.execute('SELECT evidence FROM world_move_intents ORDER BY seq LIMIT 1').fetchone()[0]);self.assertEqual(evidence['basis'],'client_reported_learned_move');self.assertEqual(evidence['move'],52)
  self.s.close();base=self.f.f.f.f.f;base.server=base.open();self.s=base.server
  self.assertEqual(self.s.objects[-1]['text'],'First face.');self.assertEqual(self.s.db.execute('SELECT count(*) FROM world_move_intents WHERE seq IS NOT NULL').fetchone()[0],2)
 def test_cannot_bypass_with_regular_choice_or_wrong_move_and_no_failed_receipt(self):
  object_choices.command(self.s,self.peer,['choices']);token=self.peer['object_choices']['token']
  with self.assertRaises(GuildError):object_choices.command(self.s,self.peer,['choose',token,'turn'])
  with self.assertRaises(GuildError):self.act('turn',55)
  self.act('turn',52);self.s.deployment=None;actor_objects.poll_player(self.s)
  self.assertEqual(self.s.objects[-1]['text'],'First face.');self.assertEqual(self.s.db.execute('SELECT count(*) FROM world_move_intents WHERE seq IS NOT NULL').fetchone()[0],0)
 def test_stale_position_replay_and_authoring_default_guard(self):
  token=self.offer();self.peer['state'][4]=2
  with self.assertRaises(GuildError):object_choices.command(self.s,self.peer,['move',token,'turn','52'])
  self.peer['state'][4]=1;self.act('turn',52)
  with self.assertRaises(GuildError):object_choices.command(self.s,self.peer,['move',token,'turn','52'])
  with self.assertRaises(ValueError):overworld_moves.validate_node(dict(on={'burn':'open'},use='burn',moves={'burn':[52]}))
 def test_npc_actual_receipt_required_then_shared_effect(self):
  from world.character_training import source
  from world.actor_history import search
  self.act('turn',52);self.admit(1)
  history=search(self.s,'harbor_guide',{},dict(query=json.dumps({'event':'object_move_committed'}),after=0,through=0))
  self.assertEqual(history['events'][0]['record']['basis'],'client_reported_learned_move')
  state=deepcopy(self.s.module_state);c=state['world_characters']['harbor_guide'];c['version']+=1;c.pop('plan',None);c['team']=[dict(species=277,level=5,individual='partner')]
  self.f.f.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects))
  identity=source(self.s,'harbor_guide','partner');native=dict(size=100,species=277,level=5,personality=identity['personality'],owner=identity['owner'],exp=125,blob='00'*100)
  self.s.db.execute('INSERT INTO character_training VALUES(?,?,?,?,?)',('harbor_guide','partner','a'*64,5,json.dumps(native,sort_keys=True)))
  current=source(self.s,'harbor_guide','partner')
  with self.assertRaises(ValueError):overworld_moves.prove_companion(self.s,'harbor_guide','partner',55)
  # Explicit fixture for an already reconciled native MOVES1 receipt, not a live engine run.
  self.s.db.execute('INSERT INTO actor_move_requests VALUES(?,?,?,?,?,?,?,?)',('inspection','harbor_guide','partner',c['version'],current['token'],'prior',json.dumps({'individual':'partner'}),json.dumps(dict(outcome='native_move_choices',slots=[55,0,0,0]))))
  overworld_moves.prove_companion(self.s,'harbor_guide','partner',55)
  with self.assertRaises(ValueError):overworld_moves.prove_companion(self.s,'harbor_guide','partner',52)
  offer=actor_objects.offers(self.s,self.s.objects[-1]);self.s.actor_tool_execution=(None,None,dict(id='react'),dict(id='move'))
  work=overworld_moves.use(self.s,'harbor_guide',{},dict(object='fixture',action='reset',object_revision=offer['object_revision'],individual='partner',move=55));work.dispatch();self.f.f.f.advance(3,True)
  result=actor_objects.poll(self.s,'harbor_guide',{},work.data);self.assertEqual(result['outcome'],'validated_object_state_committed');self.assertEqual(self.s.objects[-1]['text'],'First face.')
  self.assertEqual(json.loads(self.s.db.execute('SELECT evidence FROM world_move_intents ORDER BY seq DESC LIMIT 1').fetchone()[0])['basis'],'matching_native_move_inspection')

class NetworkMoveEffects(unittest.TestCase):
 def test_move_activates_linked_objects_with_real_position_change(self):
  import test_object_networks
  f=test_object_networks.NetworkTests();f.setUp();self.addCleanup(f.doCleanups);server=f.s
  for phase,action,move in [('off','activate',85),('on','reset',16)]:
   node=f.definition['program']['states'][phase];node['use']={};node['choices']={'fixture':[action]};node['moves']={'fixture':{action:[move]}}
  f.install();peer=f.f.f.connect('User',True);send=lambda line:f.f.f.f.f.send(peer,line)
  send('CAVE GET');send('CAVE ACK '+server.shared_cave.identity);f.f.f.f.f.state(peer,*server.wilds_map,72,69);peer['state'][4]=1
  object_choices.command(server,peer,['moves']);token=peer['object_moves']['token'];object_choices.command(server,peer,['move',token,'activate','85'])
  f.f.f.f.advance(1,True);actor_objects.poll_player(server)
  self.assertEqual(next(o for o in server.objects if o['id']=='panel')['y'],72)
  self.assertEqual(server.module_state['world_object_network_state']['mechanism']['phase'],'on')
  self.assertEqual(server.db.execute('SELECT count(*) FROM world_move_intents WHERE seq IS NOT NULL').fetchone()[0],1)
