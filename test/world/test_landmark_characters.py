"""Only explicitly shared exploration drives visible persistent character changes."""
from concurrent.futures import Future
from copy import deepcopy
import hashlib
import json
import unittest
import test_landmark_survey as survey_fixture
from world.character_chapters import validate_plan,compile_plan,chapter_step
from world.characters import history_feed
from world.mechanics import Candidate

class LandmarkCharacterTests(unittest.TestCase):
    def setUp(self):
        self.f=survey_fixture.LandmarkSurveyTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.s=self.f.s;g,n=self.s.wilds_map
        obj=dict(id='route_scholar',group=g,num=n,x=15,y=20,gfx=8,text='I await public field notes.',region_revision=self.f.revision)
        first=dict(id='waiting',when=None,goals=['Wait for a shared lookout discovery'],team=[dict(species=277,level=12)],status='active',object=obj,reason='A scholar asks for voluntarily shared discoveries')
        second=dict(id='investigating',when=dict(event='landmark_discovery_shared',place_id=self.s.memory.place(self.f.revision),revision=self.f.revision,landmark='lookout'),goals=['Study the publicly reported lookout'],team=[dict(species=278,level=18)],status='active',object=dict(obj,x=105,y=105,text='Shared notes led me here.\nMeet my research team!'),reason='An explicitly shared discovery inspires an authored research visit')
        self.plan=validate_plan(dict(id='route_scholar',name='Route Scholar',role='Responds to shared field notes',origin_evidence=[],chapters=[first,second]))
        context=self.s.inspect();self.after=context['world_memory']['through']
        self.definition=hashlib.sha256(json.dumps(self.plan,sort_keys=True).encode()).hexdigest()
        source=compile_plan(self.plan,context);self.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest());self.tick()
    def tick(self):
        result=chapter_step(self.plan,self.definition,self.after,self.s._context(),dict(state=self.s.module_state,tiles=[],objects=self.s.objects))
        future=Future();future.set_result((self.candidate,result));self.s.job=(future,'tick',None,self.s.interaction_cursor)
        self.s.next_tick=float('inf');self.s._poll_mechanics();self.assertIsNone(self.s.module_error)
    def test_private_arrival_and_prompt_never_reveal_or_move_character(self):
        self.f.command('/explore start');self.f.state(self.f.conn,105,105);self.tick()
        self.assertEqual(self.s.objects[0]['x'],15)
        self.f.command('/explore share lookout');self.tick();self.assertEqual(self.s.objects[0]['x'],15)
        self.assertFalse(any(e['event']=='landmark_discovery_shared' for e in self.s.memory.history()['events']))
        self.f.command('/explore share lookout confirm')
        event=[e for e in self.s.memory.history()['events'] if e['event']=='landmark_discovery_shared'][-1]
        feed=history_feed(self.s.db,{'character_history_cursor':event['seq']-1})
        self.assertEqual(feed['events'][0]['landmark'],'lookout');self.assertNotIn('Scout',json.dumps(feed));self.assertNotIn('survey_visits',json.dumps(feed))
        self.tick();character=self.s.module_state['world_characters']['route_scholar']
        self.assertEqual(character['version'],2);self.assertEqual(character['evidence'],[event['seq']])
        self.assertEqual((self.s.objects[0]['x'],self.s.objects[0]['y']),(105,105));self.assertEqual(character['team'],[dict(species=278,level=18)])
        self.assertIn('Shared notes',self.s.objects[0]['text'])
        self.f.command('/explore share lookout confirm');self.tick();self.assertEqual(self.s.module_state['world_characters']['route_scholar'],character)
        token=self.s.create_identity('Visitor')['token'];conn=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
        self.f.send(conn,f'HELLO 1 Visitor {token} SOCIALCAVE16CHAR1CHARQUEST1CHARREG1');self.f.send(conn,'CAVE GET');self.f.send(conn,'CAVE ACK '+self.f.revision);self.f.state(conn,104,105)
        self.assertIn('REGION_OBJECT '+self.f.revision+' route_scholar',self.s._snapshot(conn))
        self.assertIn('route_scholar 2 1 278 18',self.f.send(conn,f'CHARACTER_CHALLENGE_REGION {conn["seq"]+1} route_scholar 2 {self.f.revision}'))
        self.s.close();self.f.f.server=self.f.f.open();self.f.s=self.f.f.server;self.s=self.f.s
        self.assertEqual(self.s.module_state['world_characters']['route_scholar'],character);self.assertEqual(self.s.objects[0]['x'],105)
    def test_condition_requires_exact_destination_and_ignores_other_scope(self):
        for key in ('place_id','revision','landmark'):
            p=deepcopy(self.plan);p['chapters'][1]['when'].pop(key)
            with self.assertRaisesRegex(ValueError,'exact place'):validate_plan(p)
        event=dict(self.plan['chapters'][1]['when'],seq=self.after+100,revision='0'*64)
        result=chapter_step(self.plan,self.definition,self.after,{'character_history':{'events':[event],'through':event['seq']}},dict(state=self.s.module_state,tiles=[],objects=self.s.objects))
        self.assertEqual(result['state']['world_characters']['route_scholar']['version'],1)

if __name__=='__main__':unittest.main()
