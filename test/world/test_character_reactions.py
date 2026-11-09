"""Real offered-goal outcomes schedule open-ended typed character actions.

The author is deterministic test code, not a live model; native rendering is not
exercised. Actual guild authority, public history and atomic mechanic admission
are used rather than fabricated completion or rewards.
"""
from concurrent.futures import Future
from copy import deepcopy
import hashlib
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from world import gm

from test_character_offers import CharacterOfferTests
from world import character_reactions as reactions
from world.character_actions import compile_actions
from world.mechanics import Candidate
from world.runtime_gm import IntentQueue


class ReactionTests(unittest.TestCase):
    def setUp(self):
        self.f = CharacterOfferTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.server = self.f.server
        # Remove the fixture's predetermined future chapters. This actor's next
        # action will come from the test author after the actual outcome.
        source = 'def update(context,state):\n    return dict(state=state,tiles=[],objects=' + repr(self.server.objects) + ')\n'
        self.f.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
        future=Future();future.set_result((self.f.candidate,dict(state=deepcopy(self.server.module_state),tiles=[],objects=deepcopy(self.server.objects))))
        self.server.job=(future,'deploy',None,self.server.interaction_cursor)
        self.server.next_tick=float('inf');self.server._poll_mechanics()
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.q = IntentQueue(self.tmp.name); self.addCleanup(lambda:self.q.close())
        reactions.configure(self.q, self.server.inspect(), 'field_researcher',
                            'Respond to actual field results; choose your own next research activity.')

    def fetch(self, query):
        return dict(ok=True, world_id=self.server.memory.world_id,
                    **self.server.memory.history(**{k:v for k,v in query.items() if k!='command'}))

    def finish_trip(self, *, public=True):
        if public:self.f.fixture.command('chronicle on')
        self.assertIn(' STARTED' if public else ' PRIVATE',self.f.accept())
        self.f.fixture.state('Alice');self.f.fixture.state('Bob')

    def observe(self):
        return reactions.observe(self.q, self.server.inspect(), self.fetch)

    def test_real_goal_action_result_next_choice_and_restart(self):
        self.assertEqual(self.observe(), [])
        self.finish_trip()
        self.assertEqual(len(self.observe()),1)
        item=self.q.claim(); packet=__import__('json').loads(item['result'])
        context=self.server.inspect()
        context['runtime']=dict(kind='character',observed_event=packet,previous_source=self.f.candidate.source)
        reaction=reactions.prepare(context,self.fetch)
        event=packet['evidence']
        action=dict(id='field_researcher',expected_version=1,evidence=[event],
                    reason='Successful field notes suggest inviting a new survey, not a preset chapter.',
                    changes=dict(goals=['Compare another field visit'],team=[dict(species=278,level=14)],
                                 offer=dict(id='followup_visit',revision=1,kind='expedition',place_id='native:LittlerootTown',target=2)),
                    object=dict(self.server.objects[0],text='Your notes helped.\nCompare another survey?'))
        response=dict(character_actions=[action],tests='assert True')
        reactions.check_response(response,reaction)
        source=compile_actions([action],context)
        namespace={};exec(source,namespace)
        result=namespace['update'](self.server._context(),deepcopy(self.server.module_state))
        candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
        future=Future();future.set_result((candidate,result))
        self.server.job=(future,'tick',None,self.server.interaction_cursor)
        self.server.next_tick=float('inf');self.server._poll_mechanics()
        self.assertIsNone(self.server.module_error)
        self.assertIn('Compare another survey', self.server.objects[0]['text'])
        self.assertEqual(self.server.module_state['world_characters']['field_researcher']['team'],[dict(species=278,level=14)])
        self.q.finish(item['id'],'succeeded',dict(ok=True))
        self.assertEqual(self.observe(),[])  # our own character change cannot wake itself
        self.f.send(self.f.alice,f'STATE {self.f.alice["seq"]+1} 0 9 8 8 4 7 1 '+'a'*16+' '+'b'*16)
        reply=self.f.send(self.f.alice,f'CHARACTER_ACCEPT {self.f.alice["seq"]+1} field_researcher 2 followup_visit 1')
        self.assertIn(' STARTED',reply)
        self.f.fixture.state('Alice');self.f.fixture.state('Bob')
        self.assertEqual(len(self.observe()),1)
        self.assertEqual(self.f.fixture.stats(),(20,2,0))
        self.q.close();self.q=IntentQueue(self.tmp.name)
        second=self.q.claim()
        self.assertEqual(__import__('json').loads(second['result'])['expected_version'],2)
        self.q.recover();self.assertIsNone(self.q.claim())  # unknown interrupted outcome not replayed

    def test_private_and_unrelated_activity_cannot_trigger(self):
        self.finish_trip(public=False)
        self.assertEqual(self.observe(),[])
        self.server.memory.append('area_named',dict(place_id='native:LittlerootTown',before='A',after='B'))
        self.assertEqual(self.observe(),[])

    def test_exact_actor_version_evidence_and_typed_effects(self):
        self.finish_trip();self.observe();item=self.q.claim()
        packet=__import__('json').loads(item['result']);context=self.server.inspect()
        context['runtime']=dict(kind='character',observed_event=packet)
        reaction=reactions.prepare(context,self.fetch)
        reactions.check_response(dict(character_actions=[],tests='assert True'),reaction)
        for response in [dict(source='def update(c,s):return s',tests='pass'),
                         dict(character_actions=[dict(id='someone_else',expected_version=1,evidence=[packet['evidence']])],tests='pass')]:
            with self.assertRaises(ValueError):reactions.check_response(response,reaction)
        context['state']['world_characters']['field_researcher']['version']+=1
        with self.assertRaises(ValueError):reactions.prepare(context,self.fetch)

    def test_backlog_pages_do_not_drop_a_goal_and_disabled_enrollment_does_not_replay(self):
        for i in range(70):
            self.server.memory.append('area_named',dict(place_id='native:LittlerootTown',before=str(i),after=str(i+1)))
        self.finish_trip()
        self.assertEqual(self.observe(),[]);self.assertEqual(self.observe(),[])
        self.assertEqual(len(self.observe()),1)
        reactions.unfollow(self.q,'field_researcher')
        self.assertIsNone(self.q.claim())
        reactions.configure(self.q,self.server.inspect(),'field_researcher','Continue from now')
        self.assertEqual(self.observe(),[])

    def test_missing_actor_world_swap_and_tampered_public_evidence_refuse(self):
        with self.assertRaises(ValueError):reactions.configure(self.q,self.server.inspect(),'wally','No duplicate canonical actor')
        self.finish_trip();self.observe();item=self.q.claim()
        packet=__import__('json').loads(item['result']);context=self.server.inspect()
        context['runtime']=dict(kind='character',observed_event=packet)
        def altered(query):
            page=self.fetch(query);page['events'][0]['character_offer_revision']=99;return page
        with self.assertRaises(ValueError):reactions.prepare(context,altered)
        context['world_memory']['world_id']='another-world'
        with self.assertRaises(ValueError):reactions.observe(self.q,context,self.fetch)

    def test_gm_wait_is_recorded_without_redeploy_and_raw_source_is_refused(self):
        self.finish_trip();self.observe();item=self.q.claim()
        packet=__import__('json').loads(item['result'])
        calls=[];prompts=[]
        def admin(socket, request, timeout=120):
            calls.append(request['command'])
            if request['command']=='inspect':return self.server.inspect()
            if request['command']=='world_history':return self.fetch(request)
            raise AssertionError('Wait must not deploy or request other authority')
        def author(prompt):
            prompts.append(prompt)
            return dict(character_actions=[],tests='assert True')
        runtime=dict(kind='character',observed_event=packet,previous_source=self.f.candidate.source)
        with patch('world.gm.admin_request',side_effect=admin), patch('world.world_memory.recall_request',return_value=None):
            report=gm.author_and_deploy(self.tmp.name,'unused','Decide next research action',author,120,runtime_context=runtime)
            self.assertTrue(report['ok'],report)
            self.assertEqual(report['stage'],'character_wait')
            self.assertNotIn('deploy',calls)
            self.assertTrue(Path(report['report_path']).is_file())
            self.assertIn('character_reaction',prompts[0])
            self.assertIn(str(packet['evidence']),prompts[0])
            report=gm.author_and_deploy(self.tmp.name,'unused','Decide next research action',
                lambda _:dict(source='def update(c,s): return s',tests='assert True'),120,runtime_context=runtime)
            self.assertFalse(report['ok'])
            self.assertIn('bounded typed actions',report['error'])

    def test_unfollow_during_history_fetch_cannot_queue_stale_work(self):
        self.finish_trip()
        def fetch_then_cancel(query):
            page=self.fetch(query)
            reactions.unfollow(self.q,'field_researcher')
            return page
        self.assertEqual(reactions.observe(self.q,self.server.inspect(),fetch_then_cancel),[])
        self.assertIsNone(self.q.claim())
        self.assertEqual(reactions.subscriptions(self.q),[])
