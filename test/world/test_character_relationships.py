"""Real public goal -> authored NPC alliance -> another playable NPC consequence."""
from concurrent.futures import Future
from copy import deepcopy
import hashlib
import json
import unittest
import test_character_offers as offer_fixture
from test_character_chapters import plan
from world.character_chapters import validate_plan,compile_plan,chapter_step
from world.character_actions import compile_actions,action_step
from world.characters import history_feed
from world.mechanics import Candidate


class CharacterRelationshipTests(unittest.TestCase):
    def setUp(self):
        self.f=offer_fixture.CharacterOfferTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.s=self.f.server;self.actions=[]
        p=plan();p['id']='trail_mentor';p['name']='Trail Mentor';p['chapters']=[p['chapters'][0],p['chapters'][2]]
        for chapter in p['chapters']:
            chapter['object'].update(id='trail_mentor',x=12)
        p['chapters'][0]['object']['text']='I train with trusted guides.'
        p['chapters'][1]['when']=dict(event='character_changed',character_id='field_researcher',relationship_target='trail_mentor',relationship='trusted guide')
        p['chapters'][1]['object']['text']='Our alliance opens trails.\nExplore Route101 with us!'
        p['chapters'][1]['offer']=dict(id='trail_lessons',revision=1,kind='expedition',place_id='native:Route101',target=2)
        p['chapters'][1]['reason']='The researcher committed a public alliance with this mentor'
        self.plan=validate_plan(p);context=self.s.inspect();self.after=context['world_memory']['through']
        context['runtime']={'previous_source':self.f.candidate.source}
        self.source=compile_plan(p,context);self.definition=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest();self.tick()

    def tick(self):
        context=self.s._context();result=dict(state=self.s.module_state,tiles=[],objects=self.s.objects)
        result=chapter_step(self.f.plan,self.f.definition,self.f.after,context,result)
        result=chapter_step(self.plan,self.definition,self.after,context,result)
        for action,definition in self.actions:result=action_step(action,definition,result,context)
        candidate=Candidate(self.source,hashlib.sha256(self.source.encode()).hexdigest())
        future=Future();future.set_result((candidate,result));self.s.job=(future,'tick',None,self.s.interaction_cursor)
        self.s.next_tick=float('inf');self.s._poll_mechanics();self.assertIsNone(self.s.module_error)

    def author_action(self,changes,evidence):
        character=self.s.module_state['world_characters']['field_researcher']
        obj=next(o for o in self.s.objects if o['id']=='field_researcher')
        actions=[dict(id='field_researcher',expected_version=character['version'],evidence=[evidence],
            reason='The completed expedition informs a new alliance decision',changes=changes,object=deepcopy(obj))]
        context=self.s.inspect();context['runtime']={'previous_source':self.source}
        self.source=compile_actions(actions,context)
        definition=hashlib.sha256(json.dumps(actions,sort_keys=True).encode()).hexdigest()
        self.actions.append((actions,definition));self.tick()

    def test_committed_alliance_unlocks_second_character_expedition_and_reward(self):
        self.f.fixture.command('chronicle on');self.assertIn('STARTED',self.f.accept())
        self.f.fixture.state('Alice');self.f.fixture.state('Bob');self.tick()
        completed=self.f.fixture.events()[0]
        self.assertEqual(self.s.module_state['world_characters']['trail_mentor']['version'],1)
        self.author_action({'relationships':{'trail_mentor':'trusted guide'}},completed['seq'])
        alliance=[e for e in self.s.memory.history()['events'] if e['event']=='character_changed' and e['character_id']=='field_researcher'][-1]
        self.assertEqual(self.s.module_state['world_characters']['trail_mentor']['version'],1) # cannot react to an uncommitted same-tick assertion
        feed=history_feed(self.s.db,{'character_history_cursor':alliance['seq']-1})
        self.assertEqual(feed['events'][0]['relationship_changes'],{'trail_mentor':'trusted guide'})
        self.tick();mentor=self.s.module_state['world_characters']['trail_mentor']
        self.assertEqual(mentor['version'],2);self.assertEqual(mentor['evidence'],[alliance['seq']])
        self.assertEqual(mentor['offer']['id'],'trail_lessons')
        self.assertIn('alliance',next(o for o in self.s.objects if o['id']=='trail_mentor')['text'])
        self.f.send(self.f.alice,f'STATE {self.f.alice["seq"]+1} 0 9 11 8 4 7 1 '+'a'*16+' '+'b'*16)
        self.assertIn('CHARACTER_OFFER trail_mentor 2 trail_lessons 1 2 Route101',self.s._snapshot(self.f.alice))
        response=self.f.send(self.f.alice,f'CHARACTER_ACCEPT {self.f.alice["seq"]+1} trail_mentor 2 trail_lessons 1')
        self.assertIn('STARTED',response)
        self.f.fixture.state('Alice',location=(0,16));self.f.fixture.state('Bob',location=(0,16))
        self.assertEqual(self.f.fixture.stats(),(20,2,0))
        self.assertEqual(self.f.fixture.events()[-1]['character_id'],'trail_mentor')
        self.tick();self.assertEqual(self.s.module_state['world_characters']['trail_mentor']['version'],2)
        # An unrelated later team edit retaining the relationship is not a new alliance.
        latest=self.f.fixture.events()[-1]['seq']
        self.author_action({'team':[dict(species=278,level=22)]},latest)
        changed=[e for e in self.s.memory.history()['events'] if e['event']=='character_changed' and e['character_id']=='field_researcher'][-1]
        feed=history_feed(self.s.db,{'character_history_cursor':changed['seq']-1})
        self.assertEqual(feed['events'][0]['relationship_changes'],{})
        self.s.close();self.f.fixture.case.server=self.f.fixture.case.open();self.f.fixture.server=self.f.fixture.case.server
        self.assertEqual(self.f.fixture.server.module_state['world_characters']['trail_mentor'],mentor)

    def test_relationship_predicate_cannot_match_unrelated_changes(self):
        bad=deepcopy(self.plan);bad['chapters'][1]['when'].pop('relationship_target')
        with self.assertRaisesRegex(ValueError,'actor'):validate_plan(bad)
        bad=deepcopy(self.plan);bad['chapters'][1]['when']['relationship_target']='field_researcher'
        with self.assertRaises(ValueError):validate_plan(bad)
        event=dict(seq=self.after+100,event='character_changed',character_id='field_researcher',relationship_changes={'another_npc':'trusted guide'})
        result=chapter_step(self.plan,self.definition,self.after,{'character_history':{'events':[event],'through':event['seq']}},dict(state=self.s.module_state,tiles=[],objects=self.s.objects))
        self.assertEqual(result['state']['world_characters']['trail_mentor']['version'],1)


if __name__=='__main__':unittest.main()
