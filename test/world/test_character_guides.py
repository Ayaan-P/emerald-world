"""Real sandbox chapters and authenticated chat keep resident route notes private."""
from concurrent.futures import Future
import re
import unittest
import test_landmark_survey as survey_fixture
from world.character_chapters import compile_plan
from world.mechanics import MechanicRuntime


class CharacterGuideTests(unittest.TestCase):
    def setUp(self):
        self.f=survey_fixture.LandmarkSurveyTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.s=self.f.s
        g,n=self.s.wilds_map
        obj=dict(id='route_guide',group=g,num=n,x=16,y=20,gfx=8,text='Ask for private directions.',region_revision=self.f.revision)
        self.plan=dict(id='route_guide',name='Route Guide',role='Resident navigator',origin_evidence=[],chapters=[dict(
            id='home',when=None,goals=['Help willing surveyors'],team=[dict(species=277,level=12)],
            status='active',object=obj,reason='Authored resident service',services=['guide'])])
        self.runtime=MechanicRuntime(self.s.root)
        source=compile_plan(self.plan,self.s.inspect())
        self.candidate=self.runtime.from_source(source)
        result=self.runtime.run(self.candidate,self.s._context(),self.s.module_state)
        future=Future();future.set_result((self.candidate,result))
        self.s.job=(future,'tick',None,self.s.interaction_cursor);self.s.next_tick=float('inf');self.s._poll_mechanics()
        self.assertIsNone(self.s.module_error)
        self.f.state(self.f.conn,15,20)

    def private_text(self):
        return '\n'.join(bytes.fromhex(row[3]).decode() for row in self.f.conn.get('chat_history',[]))

    def test_geometry_directions_arrival_share_and_restart_isolation(self):
        other=self.f.connect('Other')
        self.f.command('/explore start')
        before=self.s.memory.history()['events']
        self.f.command('/explore guide route_guide')
        self.assertIn('walking steps',self.private_text())
        note=self.s.db.execute('SELECT revision,landmark,guide FROM survey_guidance WHERE trainer=?',('Scout',)).fetchone()
        self.assertEqual(note[::2],(self.f.revision,'route_guide'))
        cave=self.s._connection_cave(self.f.conn)
        for _ in range(100):
            serial=self.f.conn['chat_history'][-1][0] if self.f.conn['chat_history'] else 0
            self.f.command('/explore directions')
            lines=[bytes.fromhex(r[3]).decode() for r in self.f.conn['chat_history'] if r[0]>serial]
            if any('reached the clearing' in line for line in lines):break
            turns=[re.fullmatch(r'Walk (north|south|west|east) to \((\d+),(\d+)\)\.',line) for line in lines]
            turns=[turn for turn in turns if turn]
            self.assertTrue(turns,lines)
            turn=turns[0];target=tuple(map(int,turn.groups()[1:]))
            x,y=self.f.conn['state'][2:4]
            dx,dy={'north':(0,-1),'south':(0,1),'west':(-1,0),'east':(1,0)}[turn[1]]
            while (x,y)!=target:
                x+=dx;y+=dy;self.assertTrue(cave.walkable(x,y));self.assertNotEqual((x,y),(16,20))
                self.f.state(self.f.conn,x,y)
        else:self.fail('directions did not reach a clearing')
        self.assertTrue(self.s.db.execute('SELECT 1 FROM survey_visits WHERE trainer=? AND revision=? AND landmark=?',('Scout',note[0],note[1])).fetchone())
        self.assertEqual(self.s.memory.history()['events'],before)
        self.assertEqual(other['chat_history'],[])
        self.f.command('/explore share '+note[1]);self.assertEqual(self.s.memory.history()['events'],before)
        self.f.command('/explore share '+note[1]+' confirm')
        event=self.s.memory.history()['events'][-1];self.assertEqual(event['event'],'landmark_discovery_shared')
        self.assertNotIn('Scout',str(event))
        self.s.close();self.f.f.server=self.f.f.open();self.f.s=self.f.f.server;self.s=self.f.s
        self.f.conn=self.f.connect('Scout');self.f.state(self.f.conn,15,20)
        self.f.command('/explore directions');self.assertIn('reached the clearing',self.private_text())
        self.assertEqual(self.s.db.execute('SELECT revision,landmark,guide FROM survey_guidance WHERE trainer=?',('Scout',)).fetchone(),note)
        self.f.conn=self.f.connect('Other');self.f.command('/explore start');self.f.command('/explore directions')
        self.assertIn('Ask an adjacent resident',self.private_text())

    def test_guide_adjacency_freshness_pause_revision_and_malformed_privacy(self):
        other=self.f.connect('Other')
        self.f.command('/explore guide route_guide');self.assertIn('start first',self.private_text())
        self.f.command('/explore start');self.f.conn['state_time']=0
        self.f.command('/explore guide route_guide');self.assertIn('Stand ready',self.private_text())
        self.f.state(self.f.conn,14,20);self.f.command('/explore guide route_guide')
        self.assertIn('face the resting guide',self.private_text())
        self.f.state(self.f.conn,15,20);self.f.command('/explore guide route_guide')
        self.f.command('/explore stop');self.f.command('/explore directions')
        self.assertIn('Resume your private survey',self.private_text())
        self.f.command('/explore start');self.f.conn['cave_ack']='0'*64
        self.f.command('/explore directions');self.assertIn('exact acknowledged destination',self.private_text())
        for command in ('/explore guide','/explore directions extra','/explore guide unknown extra'):
            self.f.command(command)
        self.assertEqual(other['chat_history'],[])


if __name__=='__main__':unittest.main()
