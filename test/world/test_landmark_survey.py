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

    def test_registration_requires_exact_archived_template(self):
        changed=plan();changed['seed']=45
        result=self.f.admin(dict(command='register_survey',plan=changed))
        self.assertFalse(result['ok'])
        self.assertEqual(self.s.shared_cave.identity,self.revision)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM survey_routes').fetchone()[0],1)

if __name__=='__main__':unittest.main()
