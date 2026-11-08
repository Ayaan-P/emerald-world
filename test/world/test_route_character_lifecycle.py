"""Actual route publication + persisted NPC + later public-outcome action.

Provider output and sandbox execution are fixture boundaries. Author validation,
shared-map activation, history, NPC authority commits and scoped wire are real.
"""
from concurrent.futures import Future
from copy import deepcopy
import hashlib
import json
import unittest

import test_author_routes as route_fixture
from test_route_landscape import plan as route_plan
from test_character_chapters import plan as character_plan
from world.route_landscape import compile_plan as compile_route
from world.route_characters import bind_landmarks
from world.character_chapters import compile_plan, chapter_step
from world.character_actions import compile_actions, action_step
from world.mechanics import Candidate


class RouteCharacterLifecycle(unittest.TestCase):
    def setUp(self):
        self.f=route_fixture.RouteAuthorTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.server=self.f.server

    def commit(self,source,result):
        candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
        future=Future();future.set_result((candidate,result))
        self.server.job=(future,'tick',None,self.server.interaction_cursor);self.server.next_tick=float('inf')
        self.server._poll_mechanics();self.assertIsNone(self.server.module_error)
        return candidate

    def send(self,conn,line):
        conn['out'].clear();self.server._line(conn,line.encode());self.assertFalse(conn['closing'],conn['out'])
        return conn['out'].decode()

    def state(self,conn,group,num,x,y):
        return self.send(conn,f'STATE {conn["seq"]+1} {group} {num} {x} {y} 4 7 1 '+'a'*16+' '+'b'*16)

    def test_real_route_and_character_follow_public_history_through_revisit(self):
        self.assertEqual(self.f.generate(),0)  # only model provider is substituted
        blob,report=compile_route(route_plan())
        self.assertEqual(self.server.shared_cave.identity,report['revision'])
        activation=self.server.memory.history()['events'][-1]
        self.assertIn(self.f.event['seq'],activation['history_evidence'])
        p=character_plan();p['chapters']=[p['chapters'][0]];p['origin_evidence']=[self.f.event['seq']]
        p['chapters'][0]['object']['text']='Redwood inspired this camp.\nLet us study these paths!'
        p=bind_landmarks(p,blob,report,{'arrival':'camp'})
        inspection=self.server.inspect();source=compile_plan(p,inspection)
        definition=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()
        result=chapter_step(p,definition,inspection['world_memory']['through'],self.server._context(),
                            dict(state=self.server.module_state,tiles=[],objects=self.server.objects))
        candidate=self.commit(source,result)
        obj=self.server.objects[0];self.assertEqual((obj['x'],obj['y']),(15,20))
        token=self.server.create_identity('PrivateTrainer')['token']
        conn=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
        self.assertIn('WELCOME',self.send(conn,f'HELLO 1 PrivateTrainer {token} SOCIALCAVE16CHAR1CHARQUEST1CHARREG1'))
        self.state(conn,0,9,8,8)
        self.assertIn('XLWILDS',self.send(conn,'CAVE GET'))
        self.assertIn('CAVE OK',self.send(conn,'CAVE ACK '+report['revision']))
        self.state(conn,obj['group'],obj['num'],obj['x']-1,obj['y'])
        self.assertIn('REGION_OBJECT '+report['revision']+' field_researcher',self.server._snapshot(conn))
        self.send(conn,f'INTERACT_REGION {conn["seq"]+1} field_researcher {report["revision"]}')
        self.assertIn('field_researcher 1 1 277 12',self.send(conn,
            f'CHARACTER_CHALLENGE_REGION {conn["seq"]+1} field_researcher 1 {report["revision"]}'))
        pending=conn['character_pending'];self.send(conn,f'CHARACTER_RESULT {pending["seq"]} field_researcher 1 0')
        # A real later authority goal, not a battle report, motivates a new action.
        self.state(conn,0,9,8,8)
        partner_token=self.server.create_identity('Partner')['token']
        self.server.guilds.command('PrivateTrainer','invite Partner')
        self.server.guilds.command('Partner','accept Redwood')
        partner=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
        self.assertIn('WELCOME',self.send(partner,f'HELLO 1 Partner {partner_token} SOCIAL'))
        self.server.guilds.command('PrivateTrainer','meet start LittlerootTown 2')
        self.state(conn,0,9,9,8);self.state(partner,0,9,8,8)
        events=[e for e in self.server.memory.history()['events'] if e['event']=='guild_goal_completed']
        outcome=events[-1];self.assertEqual(outcome['goal_kind'],'meetup')
        next_plan=deepcopy(p);next_plan=bind_landmarks(next_plan,blob,report,{'arrival':'lookout'})
        next_object=next_plan['chapters'][0]['object']
        # Respect the native two-line width contract.
        next_object['text']='Our reunion brought ideas.\nMeet my new field team!'
        actions=[dict(id='field_researcher',expected_version=1,evidence=[outcome['seq']],
            reason='Public reunion inspires a new lookout research post',
            changes={'team':[dict(species=278,level=20)],'goals':['Study the lookout routes']},object=next_object)]
        context=self.server.inspect();context['runtime']={'previous_source':candidate.source}
        action_source=compile_actions(actions,context)
        action_definition=hashlib.sha256(json.dumps(actions,sort_keys=True).encode()).hexdigest()
        result=action_step(actions,action_definition,dict(state=self.server.module_state,tiles=[],objects=self.server.objects))
        self.commit(action_source,result)
        self.state(conn,obj['group'],obj['num'],14,20)
        self.assertIn('CHARACTER_REJECT',self.send(conn,f'CHARACTER_CHALLENGE_REGION {conn["seq"]+1} field_researcher 2 {report["revision"]}'))
        self.state(conn,next_object['group'],next_object['num'],104,105)
        self.assertIn('field_researcher 2 1 278 20',self.send(conn,f'CHARACTER_CHALLENGE_REGION {conn["seq"]+1} field_researcher 2 {report["revision"]}'))
        self.assertEqual(self.server.module_state['world_characters']['field_researcher']['evidence'],[outcome['seq']])
        self.server.close();self.f.case.server=self.f.case.open();self.f.server=self.f.case.server;self.server=self.f.server
        self.assertEqual(self.server.shared_cave.identity,report['revision'])
        self.assertEqual(self.server.objects,[next_object])
        self.assertEqual(self.server.module_state['world_characters']['field_researcher']['team'],[dict(species=278,level=20)])
        replay=action_step(actions,action_definition,dict(state=self.server.module_state,tiles=[],objects=self.server.objects))
        self.assertEqual(replay['state'],self.server.module_state)

    def test_landmark_binding_rejects_mismatched_geometry_and_missing_sites(self):
        blob,report=compile_route(route_plan());p=character_plan();p['chapters']=[p['chapters'][0]]
        for bindings in ({},{'arrival':'entry'},{'arrival':'unknown'}):
            with self.assertRaises(ValueError):bind_landmarks(p,blob,report,bindings)
        report['revision']='0'*64
        with self.assertRaises(ValueError):bind_landmarks(p,blob,report,{'arrival':'camp'})


if __name__=='__main__':unittest.main()
