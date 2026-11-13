import unittest
from copy import deepcopy
import test_actor_object_programs as fixture
from world import actor_objects,object_choices
from world.guilds import GuildError

class ChoiceTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.ProgramTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  self.f.program['states']['first']['on']['stay']='first'
  self.f.program['states']['first']['choices']=['stay','turn']
  self.f.program['states']['second']['choices']=['reset']
  self.f.install();self.peer=self.f.f.connect('User',True)
  send=lambda line:self.f.f.f.f.send(self.peer,line)
  send('CAVE GET');send('CAVE ACK '+self.s.shared_cave.identity)
  self.f.f.f.f.state(self.peer,*self.s.wilds_map,72,69);self.peer['state'][4]=1
 def choices(self):
  object_choices.command(self.s,self.peer,['choices']);return self.peer['object_choices']['token']
 def choose(self,action):return object_choices.command(self.s,self.peer,['choose',self.choices(),action])
 def admit(self,n):
  self.f.f.f.advance(n,True);actor_objects.poll_player(self.s);self.f.f.f.advance(n+1)
 def test_real_alternative_choices_repeated_transitions_and_restart(self):
  self.choose('stay');self.assertEqual(self.s.objects[-1]['text'],'First face.');self.admit(1)
  self.assertEqual(self.s.module_state['world_object_controls']['fixture']['state'],{'phase':'first'})
  self.choose('turn');self.admit(3);self.assertEqual(self.s.objects[-1]['text'],'Second face.')
  self.choose('reset');self.admit(5);self.assertEqual(self.s.objects[-1]['text'],'First face.')
  self.s.close();base=self.f.f.f.f.f;base.server=base.open();self.s=base.server
  self.assertEqual(self.s.module_state['world_object_controls']['fixture']['state'],{'phase':'first'})
 def test_token_single_use_state_change_and_wrong_position(self):
  token=self.choices();object_choices.command(self.s,self.peer,['choose',token,'turn'])
  with self.assertRaises(GuildError):object_choices.command(self.s,self.peer,['choose',token,'turn'])
  self.admit(1);token=self.choices();self.peer['state'][4]=2
  with self.assertRaises(GuildError):object_choices.command(self.s,self.peer,['choose',token,'reset'])
  self.peer['state'][4]=1;self.s.module_state['world_object_player_choices']['fixture']=[]
  with self.assertRaises(GuildError):object_choices.command(self.s,self.peer,['choose',token,'reset'])
 def test_agent_only_transition_and_failed_admission(self):
  self.s.module_state['world_object_player_choices']['fixture']=['stay']
  with self.assertRaises(GuildError):self.choose('turn')
  self.choose('stay');self.s.deployment=None;actor_objects.poll_player(self.s)
  self.assertNotIn('world_object_controls',self.s.module_state)
 def test_guild_wire_dispatches_choice_without_public_chat(self):
  self.assertTrue(self.s.guild_chat.handle(self.peer,'/guild object choices'))
  token=self.peer['object_choices']['token']
  self.assertTrue(self.s.guild_chat.handle(self.peer,'/guild object choose '+token+' turn'))
  self.admit(1);self.assertEqual(self.s.objects[-1]['text'],'Second face.')
 def test_verified_old_dispatcher_upgrades_without_replaying(self):
  import hashlib
  from world.mechanics import Candidate
  self.choose('stay');self.admit(1)
  source=self.s.candidate.source
  current="""    if request.get('player_choice'):
        if request['action'] not in state.get('world_object_player_choices',{}).get(request['object'],[]):
            raise ValueError('Player choice is no longer advertised')
    elif request.get('player_use'):"""
  self.assertIn(current,source)
  source=source.replace(current,"    if request.get('player_use'):")
  self.f.f.f.f.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
  self.f.f.f.f.commit(dict(state=self.s.module_state,tiles=[],objects=self.s.objects))
  self.choose('turn');self.admit(3)
  self.assertEqual(self.s.objects[-1]['text'],'Second face.')
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM object_transition_archive').fetchone()[0],2)
