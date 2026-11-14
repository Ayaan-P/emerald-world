import copy,json,unittest
from test_field_flags import FlagTests
from world.field_flags import ARENA
from world.actor_field_games import publish,catalog

class TeamGames(unittest.TestCase):
    setUp=FlagTests.setUp
    connect=FlagTests.connect
    chat=FlagTests.chat
    state=FlagTests.state

    def team_game(self):
        arena=copy.deepcopy(ARENA);arena.update(id='custom_teams',captures=1,starts=[[0,0,10,10],[0,0,22,12],[0,0,10,11],[0,0,22,11]])
        result=publish(self.s,'author',{},dict(arena=json.dumps(arena)))
        self.assertEqual(result['players'],4)
        self.d=self.connect('Dara');self.chat(self.a,'/guild invite Dara');self.chat(self.d,'/guild accept Runners')
        self.chat(self.a,'/guild play start flag custom_teams');r=self.s.flags.current('Alice')
        self.chat(self.a,'/guild play share flag')
        for c in (self.b,self.c,self.d):self.chat(c,'/guild play join Alice')
        self.assertEqual(len(r['members']),4)
        for c,p in zip(r['members'],arena['starts']):self.state(c,p);self.chat(c,'/guild flag ready')
        self.assertEqual(r['phase'],'countdown');self.now+=3
        for c in r['members']:c['state_time']=self.now
        self.s.flags.tick();self.assertEqual(r['phase'],'playing')
        return r

    def test_actual_team_capture_board_and_restart(self):
        r=self.team_game()
        for c,p in [(self.b,[0,0,23,13]),(self.d,[0,0,24,13])]:self.state(c,p)
        self.state(self.c,ARENA['bases'][1]);self.assertTrue(r['carrying'][2])
        self.state(self.a,ARENA['bases'][1]);self.assertFalse(r['carrying'][0]) # one enemy flag
        self.state(self.c,ARENA['bases'][0]);self.assertEqual(r['scores'],[1,0]);self.assertFalse(self.s.flags.runs)
        for c in (self.a,self.c):self.assertTrue(any('Cara 1' in x for x in self.chat(c,'/guild flag records')))
        self.s.close();from test_shared_generated_cave import MemoryAuthority
        self.s=MemoryAuthority(self.root/'sock',self.root/'world')
        self.assertEqual(json.loads(self.s.db.execute('SELECT players FROM flag_results').fetchone()[0]),['Alice','Bob','Cara','Dara'])
        self.assertFalse(self.s.flags.runs);self.assertEqual(len(catalog(self.s)[0]['starts']),4)

    def test_teammate_does_not_tag_opponent_does(self):
        r=self.team_game()
        self.state(self.b,[0,0,23,13]);self.state(self.d,[0,0,24,13])
        self.state(self.a,ARENA['bases'][1]);self.state(self.c,[0,0,22,11]);self.assertTrue(r['carrying'][0])
        self.state(self.d,[0,0,22,13]);self.assertFalse(r['carrying'][0]);self.assertFalse(r['armed'][0])
        self.d['closing']=True;self.s.flags.tick();self.assertFalse(self.s.flags.runs)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM flag_results').fetchone()[0],0)

    def test_bounds_and_transaction_rollback(self):
        arena=copy.deepcopy(ARENA);arena['id']='atomic_game'
        with self.assertRaises(RuntimeError):
            with self.s.db:
                publish(self.s,'author',{},dict(arena=json.dumps(arena)))
                raise RuntimeError('later receipt failed')
        self.assertFalse(self.s.db.execute('SELECT 1 FROM flag_arenas WHERE id=?',(arena['id'],)).fetchone())
        arena['starts']=[ARENA['bases'][0]]*4
        with self.assertRaises(ValueError):publish(self.s,'author',{},dict(arena=json.dumps(arena)))

    def test_actor_plan_publishes_real_arena_once(self):
        from test_actor_runtime import ActorRuntimeTests
        from world import actor_runtime
        f=ActorRuntimeTests();f.setUp();self.addCleanup(f.doCleanups)
        arena=copy.deepcopy(ARENA);arena['id']='agent_field'
        f.apply(dict(id='organize_game',purpose='Offer a voluntary field game.',steps=[dict(id='publish',tool='world.publish_flag_arena',args=dict(arena=json.dumps(arena)),after=[])]))
        receipt=actor_runtime.tick(f.s,now=10)
        self.assertEqual(receipt['status'],'succeeded')
        self.assertEqual(f.s.flags.publish(arena)['id'],'agent_field')
        self.assertIsNone(actor_runtime.tick(f.s,now=20))
        self.assertEqual(f.s.db.execute('SELECT count(*) FROM flag_arenas WHERE id=?',('agent_field',)).fetchone()[0],1)
