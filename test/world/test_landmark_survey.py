"""Real authority presence and chat drive a private persistent route survey."""
import json
import unittest
from unittest.mock import patch
import test_world_memory as fixtures
from test_route_landscape import plan
from world.route_landscape import compile_plan

class LandmarkSurveyTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.WorldMemoryTests();self.f.setUp();self.addCleanup(self.f.tearDown)
        self.s=self.f.server;self.blob,self.report=compile_plan(plan())
        self.revision=self.s._replace_cave(self.blob,label='Orchard Divide')
        result=self.f.admin(dict(command='register_survey',plan=plan()))
        self.assertTrue(result['ok'],result)
        self.conn=self.connect('Scout')

    def send(self,conn,line):
        conn['out'].clear();self.s._line(conn,line.encode());self.assertFalse(conn['closing'])
        return conn['out'].decode()

    def connect(self,name):
        token=self.s.create_identity(name)['token']
        c=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
        self.send(c,f'HELLO 1 {name} {token} SOCIALCAVE16')
        self.send(c,'CHAT_ENABLE')
        self.send(c,'CAVE GET');self.send(c,'CAVE ACK '+self.revision)
        self.state(c,1,1)
        return c

    def state(self,c,x,y):
        g,n=self.s.wilds_map
        return self.send(c,f'STATE {c["seq"]+1} {g} {n} {x} {y} 4 7 1 '+'a'*16+' '+'b'*16)

    def command(self,text):
        self.conn['chat_credit']=4
        return self.send(self.conn,f'CHAT {self.conn["seq"]+1} * {text.encode().hex()}')

    def count(self):
        return self.s.db.execute('SELECT count(*) FROM survey_visits').fetchone()[0]

    def test_opt_in_arrival_completion_restart_and_private_history(self):
        before=self.s.memory.history()['events']
        self.state(self.conn,15,20);self.assertEqual(self.count(),0)
        self.command('/explore start');self.assertEqual(self.count(),1)
        for site in self.report['landmarks'][1:-1]:self.state(self.conn,site['x'],site['y'])
        self.assertEqual(self.count(),4)
        self.assertIn('Survey complete',' '.join(self.s.landmark_survey.lines(self.conn)))
        stranger=self.connect('Other');self.assertEqual(len(stranger['chat_history']),0)
        self.assertEqual(self.s.memory.history()['events'],before)
        self.s.close();self.f.server=self.f.open();self.s=self.f.server
        self.conn=self.connect('Scout')
        self.assertEqual(self.count(),4)
        self.assertIn('4/4',self.s.landmark_survey.lines(self.conn)[0])

    def test_stop_stale_and_revision_changes_do_not_credit(self):
        self.command('/explore start');self.command('/explore stop')
        self.state(self.conn,15,20);self.assertEqual(self.count(),0)
        self.conn['state_time']=0;self.command('/explore start')
        self.assertEqual(self.count(),0)
        self.state(self.conn,1,1);self.command('/explore start')
        self.conn['cave_ack']='0'*64
        self.s.landmark_survey.observe(self.conn);self.assertEqual(self.count(),0)

    def test_other_revision_pauses_until_original_map_returns(self):
        self.command('/explore start')
        self.send(self.conn,f'STATE {self.conn["seq"]+1} 0 9 8 8 4 7 1 '+'a'*16+' '+'b'*16)
        alternate=plan();alternate['seed']=45
        blob,_=compile_plan(alternate);other=self.s._replace_cave(blob)
        with patch('world.server.time.monotonic',return_value=self.conn['cave_next']+.01):
            self.send(self.conn,'CAVE GET');self.send(self.conn,'CAVE ACK '+other)
        self.state(self.conn,15,20);self.assertEqual(self.count(),0)
        self.assertIn('Return to the same map',self.s.landmark_survey.lines(self.conn)[1])
        self.send(self.conn,f'STATE {self.conn["seq"]+1} 0 9 8 8 4 7 1 '+'a'*16+' '+'b'*16)
        self.s.activate_generated_area(self.revision)
        with patch('world.server.time.monotonic',return_value=self.conn['cave_next']+.01):
            self.send(self.conn,'CAVE GET');self.send(self.conn,'CAVE ACK '+self.revision)
        self.state(self.conn,15,20);self.assertEqual(self.count(),1)

    def test_explicit_share_becomes_recalled_author_evidence_without_identity(self):
        from world import author_cave, author_routes
        from test_author_cave import wire
        self.command('/explore start');self.state(self.conn,15,20)
        before=self.s.memory.history()['events']
        self.command('/explore share camp')
        self.assertEqual(self.s.memory.history()['events'],before)
        self.command('/explore share camp confirm')
        event=self.s.memory.history()['events'][-1]
        self.assertEqual(event['event'],'landmark_discovery_shared')
        self.assertEqual(event['revision'],self.revision)
        self.assertEqual(event['place_id'],self.s.memory.place(self.revision))
        self.assertNotIn('Scout',json.dumps(event))
        self.assertNotIn('trainer',event)
        self.command('/explore share camp confirm')
        self.assertEqual(self.s.memory.history()['events'][-1],event)
        self.send(self.conn,f'STATE {self.conn["seq"]+1} 0 9 8 8 4 7 1 '+'a'*16+' '+'b'*16)
        def transport(_socket,request,**kw):return self.f.admin(request)
        def provider(prompt,validator,**kw):
            self.assertIn('landmark_discovery_shared',prompt)
            self.assertNotIn('Scout',prompt)
            candidate=plan();candidate['seed']=45
            return validator(wire(candidate))
        with patch('world.client.admin_request',side_effect=transport), \
             patch('world.publish_cave.admin_request',side_effect=transport), \
             patch('world.author_cave.request_validated',side_effect=provider):
            self.assertEqual(author_routes.main(['Build beyond camp','--activate-shared','admin','--label','Beyond Camp']),0)
        activation=self.s.memory.history()['events'][-1]
        self.assertIn(event['seq'],activation['history_evidence'])
        self.s.close();self.f.server=self.f.open();self.s=self.f.server
        self.assertEqual(self.s.db.execute('SELECT seq FROM survey_publications').fetchone()[0],event['seq'])

    def test_share_requires_current_presence_and_rolls_back_history_failure(self):
        import sqlite3
        self.command('/explore start');self.state(self.conn,15,20)
        before=self.s.memory.history()['events']
        self.command('/explore share unknown confirm')
        self.state(self.conn,30,95);self.command('/explore share camp confirm')
        self.assertEqual(self.s.memory.history()['events'],before)
        self.state(self.conn,15,20)
        append=self.s.memory.append
        def fail(*args,**kw):
            append(*args,**kw)
            raise sqlite3.OperationalError('fixture failure after event insertion')
        with patch.object(self.s.memory,'append',side_effect=fail):
            self.command('/explore share camp confirm')
        self.assertEqual(self.s.memory.history()['events'],before)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM survey_publications').fetchone()[0],0)

    def test_registration_requires_exact_archived_template(self):
        changed=plan();changed['seed']=45
        result=self.f.admin(dict(command='register_survey',plan=changed))
        self.assertFalse(result['ok'])
        self.assertEqual(self.s.shared_cave.identity,self.revision)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM survey_routes').fetchone()[0],1)

if __name__=='__main__':unittest.main()
