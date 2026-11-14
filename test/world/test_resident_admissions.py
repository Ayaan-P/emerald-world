from copy import deepcopy
import hashlib,json,unittest
import test_procedural_adventures as fixture
from world import actor_runtime as runtime,character_reactions as reactions,population_agents as lifecycle
from world.runtime_gm import IntentQueue
from world.character_actions import compile_actions
from world.mechanics import Candidate

class ResidentAdmissionsTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.AdventureTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
        self.q=IntentQueue(self.s.root);self.addCleanup(lambda:self.q.close())
        reactions.configure(self.q,self.s.inspect(),'harbor_guide','Create real places and original residents.')
    def fetch(self,q):return dict(ok=True,world_id=self.s.memory.world_id,**self.s.memory.history(**{k:v for k,v in q.items() if k!='command'}))
    def drain(self):
        for _ in range(20):
            reactions.observe(self.q,self.s.inspect(),self.fetch)
            if lifecycle.policy(self.q)['cursor']==self.s.inspect()['world_memory']['through']:return
        self.fail('History did not drain')
    def build(self,enabled=True):
        if enabled:lifecycle.configure(self.q,self.s.inspect(),True)
        self.f.plan();self.assertEqual(runtime.tick(self.s,now=10)['status'],'pending');self.f.p.admit()
        if enabled:self.drain() # actual admission may arrive on a different page before publication
        self.assertEqual(runtime.tick(self.s,now=16)['status'],'succeeded')
        if enabled:self.drain()
    def test_batch_residents_independently_change_actual_native_services(self):
        self.build();children=self.q.db.execute("SELECT * FROM requests WHERE player LIKE 'visitor_%' ORDER BY player").fetchall()
        self.assertEqual(len(children),2);self.assertNotEqual(children[0]['id'],children[1]['id'])
        for i,item in enumerate(children):
            identity=item['player'];ctx=self.s.inspect();ctx['runtime']=dict(kind='character',observed_event=json.loads(item['result']),previous_source=self.s.candidate.source)
            evidence=json.loads(item['result'])['evidence']
            ctx['recalled_history']=dict(events=self.s.memory.history(after=evidence-1,through=evidence,limit=1)['events'])
            reaction=reactions.prepare(ctx,self.fetch);self.assertEqual(reaction['id'],identity)
            plan=dict(id='own_choice',purpose='Choose an optional preparation service.',steps=[dict(id='offer',tool='world.configure_shop',args=dict(items=json.dumps([28 if i==0 else 114])),after=[])])
            action=dict(id=identity,expected_version=reaction['expected_version'],evidence=[reaction['evidence']],reason='Independent fixture decision based on actual creation.',changes=dict(plan=plan),object=next(o for o in self.s.objects if o['id']==identity))
            source=compile_actions([action],ctx);ns={};exec(source,ns)
            self.f.p.f.f.f.f.f.f.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
            self.f.p.f.f.f.f.f.f.commit(ns['update'](self.s._context(),deepcopy(self.s.module_state)))
            self.assertIsNone(self.s.module_error);result=runtime.tick(self.s,now=30+i*6);self.assertEqual(result['status'],'succeeded');self.assertEqual(result['actor'],identity)
            from world.actor_shops import line
            self.assertTrue(line(self.s,dict(character_shop_capable=True),identity,2).endswith(' 1 '+str(28 if i==0 else 114)))
    def test_capacity_waits_durably_then_admits_without_raising_limits(self):
        with self.q.db:
            for i in range(6):self.q.db.execute('INSERT INTO character_reactions VALUES(?,?,?,?)',('occupied_'+str(i),'Test capacity slot',self.s.memory.world_id,0))
        self.build();self.assertEqual(self.q.db.execute('SELECT count(*) FROM character_reactions').fetchone()[0],8)
        self.assertEqual(self.q.db.execute("SELECT count(*) FROM population_admissions WHERE status='waiting'").fetchone()[0],1)
        self.q.close();self.q=IntentQueue(self.s.root);reactions.unfollow(self.q,'occupied_0');self.drain()
        self.assertEqual(self.q.db.execute('SELECT count(*) FROM population_agents').fetchone()[0],2)
        self.assertEqual(self.q.db.execute('SELECT count(*) FROM character_reactions').fetchone()[0],8)
        before=self.q.db.execute('SELECT count(*) FROM requests').fetchone()[0];self.drain();self.assertEqual(self.q.db.execute('SELECT count(*) FROM requests').fetchone()[0],before)
    def test_disable_or_unfollow_cancels_waiting_not_just_queued(self):
        with self.q.db:
            for i in range(7):self.q.db.execute('INSERT INTO character_reactions VALUES(?,?,?,?)',('occupied_'+str(i),'Test capacity slot',self.s.memory.world_id,0))
        self.build();self.assertEqual(self.q.db.execute("SELECT count(*) FROM population_admissions WHERE status='waiting'").fetchone()[0],2)
        reactions.unfollow(self.q,'visitor_0');reactions.unfollow(self.q,'occupied_0');self.drain()
        self.assertIsNone(self.q.db.execute("SELECT 1 FROM population_agents WHERE id='visitor_0'").fetchone())
        self.assertIsNotNone(self.q.db.execute("SELECT 1 FROM population_agents WHERE id='visitor_1'").fetchone())
        lifecycle.configure(self.q,self.s.inspect(),False);lifecycle.configure(self.q,self.s.inspect(),True);self.drain()
        self.assertEqual(self.q.db.execute("SELECT count(*) FROM population_agents WHERE status='active'").fetchone()[0],0)
    def test_repeat_publication_after_opt_in_cannot_enroll_older_residents(self):
        self.build(False);lifecycle.configure(self.q,self.s.inspect(),True)
        self.f.plan(name='repeat');self.assertEqual(runtime.tick(self.s,now=22)['status'],'succeeded');self.drain()
        self.assertEqual(self.q.db.execute('SELECT count(*) FROM population_agents').fetchone()[0],0)
    def test_unfollowed_creator_and_missing_admission_never_enroll(self):
        self.build(False);lifecycle.configure(self.q,self.s.inspect(),True);reactions.unfollow(self.q,'harbor_guide')
        event=dict(event='actor_tool_result',source='authority_capability_runtime',tool='world.build_adventure',status='succeeded',character_id='harbor_guide',result=dict(outcome='procedural_adventure_published',trainers=['visitor_0','visitor_1']))
        with self.s.db:self.s.memory.append(event.pop('event'),event)
        self.drain();self.assertEqual(self.q.db.execute('SELECT count(*) FROM population_agents').fetchone()[0],0)
    def test_mixed_group_recognizes_characters_not_props(self):
        event=dict(event='actor_tool_result',source='authority_capability_runtime',tool='world.populate_group',status='succeeded',result=dict(outcome='population_group_admitted',members=[dict(object='a',kind='character'),dict(object='b',kind='prop')]))
        self.assertEqual(lifecycle.created(event),['a']);self.assertTrue(lifecycle.creation(event,'a'));self.assertFalse(lifecycle.creation(event,'b'))
        event['status']='pending';self.assertEqual(lifecycle.created(event),[])
    def test_waiting_never_interrupts_unfinished_plan_and_budgets_stay_per_actor(self):
        from unittest.mock import patch
        with patch('world.npc_goal_reviews.unfinished',side_effect=lambda data,identity,child:identity=='visitor_0'):
            self.build()
        self.assertIsNone(self.q.db.execute("SELECT 1 FROM population_agents WHERE id='visitor_0'").fetchone())
        self.drain();lifecycle.configure(self.q,self.s.inspect(),True,turn_limit=1,period_hours=1)
        with self.q.db:
            self.assertTrue(lifecycle.reserve(self.q,'visitor_0'));self.assertFalse(lifecycle.reserve(self.q,'visitor_0'))
            self.assertTrue(lifecycle.reserve(self.q,'visitor_1'));self.assertFalse(lifecycle.reserve(self.q,'visitor_1'))
