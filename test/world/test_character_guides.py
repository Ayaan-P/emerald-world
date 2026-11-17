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

    def survey_reply_cases(self):
        """Real authority commands, enrollment, visits, and private peer baseline."""
        other = self.f.connect('Other')
        other_history = list(other['chat_history'])
        before = self.s.memory.history()['events']
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM survey_sessions').fetchone()[0], 0)
        self.assertEqual(self.f.count(), 0)
        for command in ('/explore start', '/explore guide route_guide', '/explore directions', '/explore stop'):
            serial = self.s.chat_serial
            wire = self.f.command(command)
            replies = [entry for entry in self.f.conn['chat_history'] if entry[0] > serial]
            self.assertTrue(replies, command)
            for entry in replies:
                yield command, wire, entry
        self.assertEqual(self.s.db.execute('SELECT active FROM survey_sessions WHERE trainer=?', ('Scout',)).fetchone(), (0,))
        self.assertEqual(self.f.count(), 1)
        self.assertIsNotNone(self.s.db.execute('SELECT 1 FROM survey_guidance WHERE trainer=?', ('Scout',)).fetchone())
        self.assertEqual(other['chat_history'], other_history)
        self.assertEqual(self.s.memory.history()['events'], before)

    def test_survey_and_guide_producer_emits_private_self_replies(self):
        # Always runs in authority-only CI, without the private native checkout.
        for command, wire, entry in self.survey_reply_cases():
            with self.subTest(command=command, reply=entry):
                self.assertEqual(entry[1:3], ('Scout', 'Scout'))
                self.assertIn(f'CHATMSG {entry[0]} Scout Scout {entry[3]}', wire)

    def test_native_objectives_displays_real_survey_and_guide_replies_privately(self):
        from pathlib import Path
        import os
        import tempfile
        from native_objectives_harness import ENGINE, build, render

        required = [ENGINE / 'src/world' / name for name in ('world_chat.c', 'world_bridge.c')]
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            if 'EW_RC7_ENGINE' in os.environ:
                self.fail('Explicit EW_RC7_ENGINE is missing native sources: ' + ', '.join(missing))
            self.skipTest('Private native source unavailable; set EW_RC7_ENGINE to exercise compiled objectives consumer')
        with tempfile.TemporaryDirectory() as directory:
            binary = build(Path(directory))
            for command, _, entry in self.survey_reply_cases():
                with self.subTest(command=command, reply=entry):
                    text = bytes.fromhex(entry[3]).decode('ascii')
                    self.assertEqual(render(binary, 'Scout', [entry]), text)
                    noise = [(0, 'Other', '*', b'public chatter'.hex()),
                             (0, 'Other', 'Scout', b'private whisper'.hex()),
                             (0, 'World', 'Scout', b'world whisper'.hex()),
                             (0, 'Scout', 'Other', b'another recipient'.hex())]
                    for rejected in noise:
                        self.assertEqual(render(binary, 'Scout', [rejected]), 'No private activity reply yet.')
                    self.assertEqual(render(binary, 'Scout', noise + [entry] + noise), text)

    def private_text(self):
        return '\n'.join(bytes.fromhex(row[3]).decode() for row in self.f.conn.get('chat_history',[]))

    def test_first_directions_uses_adjacent_resident_without_typed_identity(self):
        other = self.f.connect('Other')
        other_history = list(other['chat_history'])
        self.f.command('/explore start')
        before = self.s.memory.history()['events']
        self.f.command('/explore directions')
        self.assertIn('walking steps', self.private_text())
        note = self.s.db.execute('SELECT revision,landmark,guide FROM survey_guidance WHERE trainer=?', ('Scout',)).fetchone()
        self.assertEqual(note[::2], (self.f.revision, 'route_guide'))
        from world.player_activity import snapshot
        self.assertEqual(snapshot(self.s, 'Scout')['survey']['next_objective']['id'], note[1])
        self.assertEqual(self.s.memory.history()['events'], before)
        self.assertEqual(other['chat_history'], other_history)

    def test_reached_notes_retarget_through_adjacent_eligible_guide(self):
        self.f.command('/explore start')
        self.f.command('/explore guide route_guide')
        note = self.s.db.execute('SELECT landmark FROM survey_guidance WHERE trainer=?', ('Scout',)).fetchone()[0]
        target = next(site for site in self.f.report['landmarks'] if site['id'] == note)
        self.f.state(self.f.conn, target['x'], target['y'])
        self.f.state(self.f.conn, 15, 20)
        self.f.command('/explore directions')
        replacement = self.s.db.execute('SELECT landmark FROM survey_guidance WHERE trainer=?', ('Scout',)).fetchone()[0]
        self.assertNotEqual(replacement, note)
        self.assertIn('Guide to ' + replacement, self.private_text())

    def test_fallback_rejects_stale_wrong_revision_nonfacing_or_moving_residents(self):
        from world.character_guides import directions, _schema
        import time
        _schema(self.s)
        self.f.command('/explore start')
        obj = next(o for o in self.s.objects if o['id'] == 'route_guide')
        baseline = dict(obj)
        for case in ('stale', 'future', 'ack', 'revision', 'away', 'facing', 'moving', 'displaced', 'closing'):
            with self.subTest(case=case):
                self.f.conn['state_time'] = time.monotonic()
                self.f.conn['cave_ack'] = self.f.revision
                self.f.conn['state'][4] = 4
                self.f.conn['closing'] = False
                self.s.peers['Scout'] = self.f.conn
                self.s.module_state['world_characters']['route_guide']['status'] = 'active'
                self.s.module_state.pop('world_character_controls', None)
                obj.update(baseline)
                if case == 'stale': self.f.conn['state_time'] = 0
                if case == 'future': self.f.conn['state_time'] = time.monotonic() + 60
                if case == 'ack': self.f.conn['cave_ack'] = '0' * 64
                if case == 'revision': obj['region_revision'] = '0' * 64
                if case == 'away': self.s.module_state['world_characters']['route_guide']['status'] = 'away'
                if case == 'facing': self.f.conn['state'][4] = 3
                if case == 'moving': self.s.module_state['world_character_controls'] = {'route_guide': {'walk': {'index': 0, 'path': [[16,20],[17,20]]}}}
                if case == 'displaced': self.s.peers['Scout'] = dict(self.f.conn)
                if case == 'closing': self.f.conn['closing'] = True
                self.assertNotIn('walking steps', ' '.join(directions(self.s, self.f.conn)))
                self.assertIsNone(self.s.db.execute('SELECT landmark FROM survey_guidance WHERE trainer=?', ('Scout',)).fetchone())

    def test_geometry_directions_arrival_share_and_restart_isolation(self):
        other=self.f.connect('Other')
        other_history = list(other['chat_history'])
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
        self.assertEqual(other['chat_history'], other_history)
        self.f.command('/explore share '+note[1]);self.assertEqual(self.s.memory.history()['events'],before)
        self.f.command('/explore share '+note[1]+' confirm')
        event=self.s.memory.history()['events'][-1];self.assertEqual(event['event'],'landmark_discovery_shared')
        self.assertNotIn('Scout',str(event))
        self.s.close();self.f.f.server=self.f.f.open();self.f.s=self.f.f.server;self.s=self.f.s
        self.f.conn=self.f.connect('Scout');self.f.state(self.f.conn,15,20)
        self.f.command('/explore directions');self.assertIn('reached the clearing',self.private_text())
        self.assertNotEqual(self.s.db.execute('SELECT revision,landmark,guide FROM survey_guidance WHERE trainer=?',('Scout',)).fetchone()[1], note[1])
        self.f.conn=self.f.connect('Other');self.f.command('/explore start');self.f.command('/explore directions')
        self.assertIn('Ask an adjacent resident',self.private_text())

    def test_guide_adjacency_freshness_pause_revision_and_malformed_privacy(self):
        other=self.f.connect('Other')
        other_history = list(other['chat_history'])
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
        self.assertEqual(other['chat_history'], other_history)


if __name__=='__main__':unittest.main()
