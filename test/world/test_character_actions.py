"""Authored live actions use public evidence and real authority/native admission."""
import ast
from concurrent.futures import Future
from copy import deepcopy
import hashlib
import json
import unittest

import test_character_offers as offer_fixture
from world.character_actions import action_step, compile_actions, validate_actions
from world.character_chapters import chapter_step
from world.mechanics import Candidate
from world.runtime_gm import decode_codex


class CharacterActionTests(unittest.TestCase):
    def setUp(self):
        self.f=offer_fixture.CharacterOfferTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.server=self.f.server
        self.f.fixture.command('chronicle on');self.f.accept()
        self.f.fixture.state('Alice');self.f.fixture.state('Bob');self.f.tick()
        self.evidence=self.f.fixture.events()[-1]['seq']
        self.actions=[dict(id='field_researcher',expected_version=2,evidence=[self.evidence],
            reason='Completed field expedition motivates a Route101 research post',
            changes=dict(goals=['Teach field training on Route101'],team=[dict(species=278,level=20)]),
            object=dict(id='field_researcher',group=0,num=16,x=9,y=8,gfx=8,text='The notes brought me here.\nTrain with my field team!'))]
        self.context=self.server.inspect();self.context['runtime']={'previous_source':self.f.candidate.source}

    def commit(self,result,candidate):
        future=Future();future.set_result((candidate,result))
        self.server.job=(future,'tick',None,self.server.interaction_cursor);self.server.next_tick=float('inf')
        self.server._poll_mechanics()

    def test_action_relocates_real_presence_and_battle_then_survives_old_story(self):
        source=compile_actions(self.actions,self.context);ast.parse(source)
        candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
        definition=hashlib.sha256(json.dumps(self.actions,sort_keys=True).encode()).hexdigest()
        base=dict(state=self.server.module_state,tiles=[],objects=self.server.objects)
        result=action_step(self.actions,definition,base);self.commit(result,candidate)
        self.assertIsNone(self.server.module_error)
        character=self.server.module_state['world_characters']['field_researcher']
        self.assertEqual(character['version'],3);self.assertEqual(character['evidence'],[self.evidence])
        self.assertEqual(self.server.objects[0]['num'],16)
        self.f.send(self.f.alice,f'STATE {self.f.alice["seq"]+1} 0 9 8 8 4 7 1 '+'a'*16+' '+'b'*16)
        self.assertIn('CHARACTER_REJECT',self.f.send(self.f.alice,f'CHARACTER_CHALLENGE {self.f.alice["seq"]+1} field_researcher 3'))
        self.f.send(self.f.alice,f'STATE {self.f.alice["seq"]+1} 0 16 8 8 4 7 1 '+'a'*16+' '+'b'*16)
        self.assertIn('field_researcher 3 1 278 20',self.f.send(self.f.alice,f'CHARACTER_CHALLENGE {self.f.alice["seq"]+1} field_researcher 3'))
        # The older authored source still runs for unrelated behavior. Its old
        # character projection cannot pull this controlled actor back home.
        old=chapter_step(self.f.plan,self.f.definition,self.f.after,self.server._context(),
                         dict(state=self.server.module_state,tiles=[],objects=self.server.objects))
        self.assertEqual(old['objects'][0]['num'],9)
        self.commit(action_step(self.actions,definition,old),candidate)
        self.assertIsNone(self.server.module_error)
        self.assertEqual(self.server.objects[0]['num'],16)
        self.assertEqual(self.server.module_state['world_characters']['field_researcher'],character)
        self.server.close();self.f.fixture.case.server=self.f.fixture.case.open()
        self.f.fixture.server=self.f.fixture.case.server
        self.assertEqual(self.f.fixture.server.objects[0]['num'],16)
        self.assertEqual(self.f.fixture.server.module_state['world_characters']['field_researcher'],character)

    def test_compiled_source_stages_from_current_checkpoint_not_first_chapter(self):
        before = deepcopy(self.context)
        source = compile_actions(self.actions, self.context)
        scope = {}
        exec(compile(source, '<compiled-character-action-test>', 'exec'), scope)
        staging_context = {'tick': 0, 'players': [], 'interactions': []}
        result = scope['update'](staging_context, {})
        character = result['state']['world_characters']['field_researcher']
        self.assertEqual(character['version'], 3)
        self.assertEqual(character['team'], [dict(species=278, level=20)])
        self.assertEqual(result['objects'][0]['num'], 16)
        self.assertEqual(self.context, before)
        # Fresh staging is deterministic; subsequent ticks do not reapply the action.
        self.assertEqual(scope['update'](staging_context, {}), result)
        later = scope['update'](dict(staging_context, tick=1), result['state'])
        self.assertEqual(later['state']['world_characters']['field_researcher'], character)
        self.assertEqual(len(later['state']['world_character_current_receipt']), 1)
        stale = deepcopy(before['state'])
        stale['world_characters']['field_researcher']['version'] = 4
        with self.assertRaisesRegex(ValueError, 'character changed before action admission'):
            scope['update'](staging_context, stale)

    def test_stale_and_private_evidence_reject_before_compile_or_commit(self):
        for key,value in [('expected_version',1),('evidence',[]),('evidence',[999999])]:
            actions=deepcopy(self.actions);actions[0][key]=value
            with self.assertRaises(ValueError):validate_actions(actions,self.context)
        actions=deepcopy(self.actions);actions[0]['changes']['relationships']={'human_player':'trusted'}
        with self.assertRaises(ValueError):validate_actions(actions,self.context)
        before=deepcopy(self.server.module_state)
        stale=deepcopy(self.actions);stale[0]['expected_version']=1
        with self.assertRaises(ValueError):action_step(stale,'stale',dict(state=before,tiles=[],objects=self.server.objects))
        self.assertEqual(self.server.module_state,before)
        wrong=deepcopy(self.context);wrong['runtime']['previous_source']+='\n# changed'
        with self.assertRaises(ValueError):compile_actions(self.actions,wrong)

    def test_later_action_supersedes_old_wrappers_without_reapplication(self):
        base=dict(state=self.server.module_state,tiles=[],objects=self.server.objects)
        first=action_step(self.actions,'first',base)
        later=deepcopy(self.actions);later[0]['expected_version']=3
        later[0]['changes']={'status':'away'};later[0]['object']=None
        second=action_step(later,'second',first)
        replay=action_step(self.actions,'first',second)
        self.assertEqual(replay,second)
        self.assertEqual(replay['objects'],[])
        self.assertEqual(replay['state']['world_characters']['field_researcher']['version'],4)
        self.assertEqual(replay['state']['world_character_action_receipts'],['first','second'])

    def test_adapter_and_generated_map_boundary(self):
        payload={'character_actions':self.actions,'tests':'def test_action():\n    assert callable(update)'}
        wire='\n'.join(map(json.dumps,[{'type':'item.completed','item':{'type':'agent_message','text':json.dumps(payload)}},{'type':'turn.completed'}]))
        self.assertEqual(decode_codex(wire),payload)
        actions=deepcopy(self.actions);actions[0]['object']['id']='wrong'
        with self.assertRaises(ValueError):validate_actions(actions,self.context)
        self.assertIn('character_actions',__import__('world.character_actions',fromlist=['contract']).contract()['response'])


if __name__=='__main__':unittest.main()
