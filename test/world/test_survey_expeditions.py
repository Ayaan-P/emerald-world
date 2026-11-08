"""Cooperative circuits require new fieldwork, not entry or personal survey reuse."""
import json
import unittest
import test_landmark_survey as fixture
from world.characters import history_feed


class SurveyExpeditions(unittest.TestCase):
    def setUp(self):
        self.f=fixture.LandmarkSurveyTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.s=self.f.s;self.a=self.f.conn;self.b=self.f.connect('Partner')
        self.s.guilds.command('Scout','create Wayfarers')
        self.s.guilds.command('Scout','invite Partner');self.s.guilds.command('Partner','accept Wayfarers')
        self.sites=json.loads(self.s.db.execute('SELECT sites FROM survey_routes WHERE revision=?',(self.f.revision,)).fetchone()[0])

    def command(self,command,conn=None):
        conn=conn or self.a;conn['chat_credit']=4;serial=self.s.chat_serial
        self.f.send(conn,f'CHAT {conn["seq"]+1} * '+('/guild '+command).encode().hex())
        return [bytes.fromhex(r[3]).decode() for r in conn['chat_history'] if r[0]>serial]

    def visit(self,conn,sites=None):
        for site in self.sites if sites is None else sites:self.f.state(conn,site['x'],site['y'])

    def goals(self):return [e for e in self.s.memory.history()['events'] if e['event']=='guild_goal_completed']
    def credits(self):return self.s.db.execute('SELECT count(*) FROM guild_expedition_visits').fetchone()[0]
    def arrivals(self):return self.s.db.execute('SELECT count(*) FROM guild_survey_arrivals').fetchone()[0]

    def test_two_member_circuit_restart_award_and_public_story(self):
        self.command('chronicle on')
        lines=self.command('expedition survey here 2');self.assertIn('each reach all',' '.join(lines))
        self.f.state(self.a,1,1);self.f.state(self.b,1,1);self.assertEqual(self.credits(),0)
        self.visit(self.a);self.visit(self.b,self.sites[:2]);self.assertEqual(self.credits(),1)
        self.assertIn('2/4',' '.join(self.command('expedition',self.b)))
        self.assertEqual(self.goals(),[])
        self.s.close();self.f.f.server=self.f.f.open();self.s=self.f.f.server;self.f.s=self.s
        self.a=self.f.connect('Scout');self.b=self.f.connect('Partner')
        self.assertEqual(self.arrivals(),6)
        self.visit(self.b,self.sites[2:]);self.assertEqual(self.credits(),2)
        e=self.goals()[0]
        self.assertEqual((e['goal_kind'],e['target'],e['credited'],e['awarded_guild_xp']),('survey',2,2,10))
        self.assertEqual(e['region_revision'],self.f.revision)
        self.assertEqual(e['place_id'],self.s.memory.place(self.f.revision))
        self.assertNotIn('Partner',json.dumps(e));self.assertNotIn('Scout',json.dumps(e))
        self.assertNotIn('landmark',json.dumps(e))
        feed=history_feed(self.s.db,{'character_history_cursor':e['seq']-1})
        self.assertEqual(feed['events'][0]['goal_kind'],'survey')
        self.visit(self.a);self.visit(self.b);self.assertEqual(len(self.goals()),1)
        self.assertEqual(self.s.db.execute('SELECT xp FROM guild_stats').fetchone()[0],10)
        self.assertTrue(any('expedition complete' in bytes.fromhex(r[3]).decode() for r in self.a['chat_history']))

    def test_no_retroactive_personal_progress_or_implicit_publication(self):
        self.f.command('/explore start');self.visit(self.a)
        self.assertEqual(self.f.count(),4)
        before=self.s.memory.history()['events']
        self.command('expedition survey here 1');self.assertEqual(self.arrivals(),0)
        self.f.state(self.a,1,1);self.assertEqual(self.credits(),0)
        self.visit(self.a);self.assertEqual(self.credits(),1)
        self.assertEqual(self.s.memory.history()['events'],before)
        self.command('expedition survey here 1');self.assertEqual(self.arrivals(),0)
        self.assertEqual(self.credits(),0)

    def test_reject_stale_unregistered_wrong_member_and_wrong_ack(self):
        self.command('expedition survey here 2',self.b)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM guild_expeditions').fetchone()[0],0)
        self.a['state_time']=0;self.command('expedition survey here 2')
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM guild_expeditions').fetchone()[0],0)
        self.f.state(self.a,1,1);self.command('expedition survey here 2')
        self.a['cave_ack']='0'*64;self.s.guild_chat.observe(self.a,self.a['state']);self.assertEqual(self.arrivals(),0)
        self.a['cave_ack']=self.f.revision
        outsider=self.f.connect('Outsider');self.visit(outsider);self.assertEqual(self.arrivals(),0)
        self.command('expedition cancel')
        with self.s.db:self.s.db.execute('DELETE FROM survey_routes')
        self.assertIn('registered survey',' '.join(self.command('expedition survey here 2')))
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM guild_expeditions').fetchone()[0],0)

    def test_failure_rolls_back_last_arrival_completion_and_xp_then_retries(self):
        self.command('chronicle on');self.command('expedition survey here 1')
        self.visit(self.a,self.sites[:-1]);self.assertEqual(self.arrivals(),3)
        self.s.db.execute("CREATE TRIGGER deny_goal BEFORE INSERT ON events WHEN NEW.kind='world_memory' AND json_extract(NEW.data,'$.event')='guild_goal_completed' BEGIN SELECT RAISE(ABORT,'test'); END")
        self.visit(self.a,self.sites[-1:])
        self.assertEqual(self.arrivals(),3);self.assertEqual(self.credits(),0)
        self.assertEqual(self.s.db.execute('SELECT xp FROM guild_stats').fetchone()[0],0)
        self.s.db.execute('DROP TRIGGER deny_goal')
        self.visit(self.a,self.sites[-1:]);self.assertEqual(self.credits(),1)
        self.assertEqual(len(self.goals()),1)

    def test_exact_revision_pause_and_real_walked_circuit(self):
        from collections import deque
        from unittest.mock import patch
        from test_route_landscape import plan
        from world.route_landscape import compile_plan
        self.command('expedition survey here 1')
        self.visit(self.a,self.sites[:1]);self.assertEqual(self.arrivals(),1)
        def leave(c):self.f.send(c,f'STATE {c["seq"]+1} 0 9 8 8 4 7 1 '+'a'*16+' '+'b'*16)
        def enter(c,revision):
            with patch('world.server.time.monotonic',return_value=c['cave_next']+.01):
                self.f.send(c,'CAVE GET');self.f.send(c,'CAVE ACK '+revision)
        leave(self.a);leave(self.b)
        alternate=plan();alternate['seed']=45
        other=self.s._replace_cave(compile_plan(alternate)[0],previous_revision=self.f.revision)
        enter(self.a,other);self.visit(self.a);self.assertEqual(self.arrivals(),1)
        leave(self.a);self.s.activate_generated_area(self.f.revision);enter(self.a,self.f.revision)
        self.f.state(self.a,1,1);walked=0
        for site in self.sites[1:]:
            start=tuple(self.a['state'][2:4]);goal=(site['x'],site['y'])
            queue=deque([start]);prev={start:None}
            while queue:
                x,y=queue.popleft()
                if (x,y)==goal:break
                for nxt in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                    if nxt not in prev and self.s.shared_cave.walkable(*nxt):prev[nxt]=(x,y);queue.append(nxt)
            path=[];at=goal
            while at!=start:path.append(at);at=prev[at]
            for point in reversed(path):self.f.state(self.a,*point);walked+=1
        self.assertGreater(walked,100);self.assertEqual(self.credits(),1)
        self.assertEqual(self.f.count(),0) # separate personal survey never opted in
        self.assertEqual(self.goals(),[]) # guild publication remains off

    def test_cancel_disband_and_regular_goal_do_not_reuse_circuit(self):
        self.command('expedition survey here 2');self.visit(self.a,self.sites[:1])
        self.command('expedition cancel');self.assertEqual(self.arrivals(),0)
        self.command('expedition start here 1');self.f.state(self.a,1,1)
        self.assertEqual(self.credits(),1)
        self.command('expedition survey here 2');self.visit(self.a,self.sites[:1])
        self.command('disband');self.assertEqual(self.arrivals(),0)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM guild_survey_routes').fetchone()[0],0)


if __name__=='__main__':unittest.main()
