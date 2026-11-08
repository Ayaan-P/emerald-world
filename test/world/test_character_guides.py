"""Resident guidance uses real private survey progress and actual route geometry."""
from concurrent.futures import Future
import hashlib
import re
import unittest
from unittest.mock import patch
import test_landmark_survey as survey_fixture
from world.character_guides import guide,directions
from world.mechanics import Candidate

class CharacterGuideTests(unittest.TestCase):
    def setUp(self):
        original_send=survey_fixture.LandmarkSurveyTests.send
        negotiated=patch.object(survey_fixture.LandmarkSurveyTests,'send',new=lambda f,c,line:original_send(f,c,line.replace('SOCIALCAVE16','SOCIALCAVE16CHAR1CHARREG1')))
        negotiated.start();self.addCleanup(negotiated.stop)
        self.f=survey_fixture.LandmarkSurveyTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.s=self.f.s;g,n=self.s.wilds_map
        self.obj=dict(id='path_guide',group=g,num=n,x=15,y=20,gfx=8,text='Ask me for private guidance.',region_revision=self.f.revision)
        self.character=dict(version=1,name='Path Guide',role='Helps willing explorers navigate',goals=['Guide private surveys'],relationships={},team=[dict(species=277,level=12)],status='active',object_id='path_guide',evidence=[],reason='An authored guide offers directions',services=['guide'])
        source="def update(context,state):\n return {'state':state,'tiles':[],'objects':[]}\n"
        candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
        future=Future();future.set_result((candidate,dict(state={'world_characters':{'path_guide':self.character}},tiles=[],objects=[self.obj])))
        self.s.job=(future,'tick',None,self.s.interaction_cursor);self.s.next_tick=float('inf');self.s._poll_mechanics();self.assertIsNone(self.s.module_error)

    def command(self,text):
        serial=self.s.chat_serial
        self.f.command(text)
        return [bytes.fromhex(row[3]).decode('ascii') for row in self.f.conn['chat_history'] if row[0]>serial]

    def test_real_guidance_leads_to_private_discovery_before_explicit_share(self):
        self.f.state(self.f.conn,14,20)
        self.assertIn('/explore start',' '.join(self.command('/explore guide path_guide')))
        self.f.command('/explore start');before=self.s.memory.history()['events']
        lines=self.command('/explore guide path_guide');self.assertIn('Guide to',' '.join(lines))
        target=self.s.db.execute('SELECT landmark FROM survey_guidance WHERE trainer=?',('Scout',)).fetchone()[0]
        walked=0
        for _ in range(400):
            lines=self.command('/explore directions')
            if 'You reached' in lines[0]:break
            first=next(line for line in lines if line.startswith('Walk '))
            match=re.search(r'\((\d+),(\d+)\)',first);tx,ty=map(int,match.groups())
            x,y=self.f.conn['state'][2:4]
            self.assertTrue(x==tx or y==ty)
            while (x,y)!=(tx,ty):
                x+=(tx>x)-(tx<x);y+=(ty>y)-(ty<y)
                self.assertNotEqual((x,y),(15,20));self.assertTrue(self.s.shared_cave.walkable(x,y))
                self.f.state(self.f.conn,x,y);walked+=1
        else:self.fail('guide never reaches its assigned clearing')
        self.assertGreater(walked,0)
        self.assertIsNotNone(self.s.db.execute('SELECT 1 FROM survey_visits WHERE trainer=? AND landmark=?',('Scout',target)).fetchone())
        self.assertEqual(self.s.memory.history()['events'],before)
        self.f.command('/explore share '+target+' confirm')
        event=self.s.memory.history()['events'][-1]
        self.assertEqual((event['event'],event['landmark']),('landmark_discovery_shared',target))
        self.assertNotIn('Scout',str(event))

    def test_guidance_requires_service_scope_and_restores_private_notes(self):
        self.f.command('/explore start')
        self.assertIn('beside',' '.join(self.command('/explore guide path_guide')))
        self.f.state(self.f.conn,14,20)
        self.assertIn('not available',' '.join(guide(self.s,self.f.conn,'unknown')))
        self.f.conn['cave_ack']='0'*64
        self.assertIn('acknowledged',' '.join(self.command('/explore guide path_guide')))
        self.f.conn['cave_ack']=self.f.revision
        self.command('/explore guide path_guide')
        note=self.s.db.execute('SELECT revision,landmark,guide FROM survey_guidance WHERE trainer=?',('Scout',)).fetchone()
        stranger=self.f.connect('Other');self.assertIn('first',' '.join(directions(self.s,stranger)))
        self.s.close();self.f.f.server=self.f.f.open();self.f.s=self.f.f.server;self.s=self.f.s
        self.f.conn=self.f.connect('Scout');self.f.state(self.f.conn,14,20)
        self.assertEqual(self.s.db.execute('SELECT revision,landmark,guide FROM survey_guidance WHERE trainer=?',('Scout',)).fetchone(),note)
        self.assertIn('Guide to',' '.join(self.command('/explore directions')))
        self.f.command('/explore stop');self.assertIn('Resume',' '.join(self.command('/explore directions')))

    def test_inherited_evidence_is_not_targeted_or_reported_as_new_arrival(self):
        self.f.state(self.f.conn,14,20);self.f.command('/explore start')
        sites=self.s.db.execute('SELECT sites FROM survey_routes WHERE revision=?',(self.f.revision,)).fetchone()[0]
        import json
        with self.s.db:
            for site in json.loads(sites):
                self.s.db.execute('INSERT INTO survey_inherited VALUES (?,?,?,?)',('Scout',self.f.revision,site['id'],'a'*64))
        before=self.s.memory.history()['events'];visits=self.f.count()
        self.assertIn('already know',' '.join(self.command('/explore guide path_guide')))
        self.assertEqual(self.f.count(),visits);self.assertEqual(self.s.memory.history()['events'],before)
        self.f.conn['character_region_capable']=False
        self.assertIn('cannot display',' '.join(self.command('/explore guide path_guide')))

if __name__=='__main__':unittest.main()
