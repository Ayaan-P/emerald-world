"""Real authority walking positions, exact scope, collision yield and admission."""
from concurrent.futures import Future
from copy import deepcopy
import hashlib
import json
import unittest
import test_region_characters as region_fixture
from world.character_actions import action_step, compile_actions, validate_actions
from world.mechanics import Candidate


class CharacterWalkTests(unittest.TestCase):
    def setUp(self):
        self.f=region_fixture.RegionCharacterTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.server=self.f.server;self.revision=self.f.enable_shared_xl()
        self.alice=self.f.connect_shared_xl(walking=True)
        history=self.server.memory.history()['events'];evidence=history[-1]['seq']
        obj=dict(self.f.obj,x=73,y=71,text='Follow me to this clearing.')
        self.actions=[dict(id='harbor_guide',expected_version=2,evidence=[evidence],reason='Scout the next clearing',
            changes={},object=obj,walk=[[71,70],[72,70],[73,70],[73,71]])]
        context=self.server.inspect();context['runtime']={'previous_source':self.f.candidate.source}
        source=compile_actions(self.actions,context)
        self.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
        self.definition=hashlib.sha256(json.dumps(self.actions,sort_keys=True).encode()).hexdigest()
        self.tick(0)

    def tick(self,tick):
        self.server.tick=tick
        context=self.server._context()
        result=action_step(self.actions,self.definition,dict(state=self.server.module_state,tiles=[],objects=self.server.objects),context)
        self.commit(result)
        return result

    def commit(self,result):
        future=Future();future.set_result((self.candidate,result))
        self.server.job=(future,'tick',None,self.server.interaction_cursor);self.server.next_tick=float('inf')
        self.server._poll_mechanics();self.assertIsNone(self.server.module_error)

    def walk(self):return self.server.module_state['world_character_controls']['harbor_guide']['walk']

    def test_authority_steps_yields_and_gates_interaction_until_complete(self):
        self.assertEqual((self.server.objects[0]['x'],self.server.objects[0]['y']),(71,70))
        self.assertIn(f'CHARACTER_WALK harbor_guide 3 {self.definition[:24]} 0 4 71 70 72 70 73 70 73 71',self.server._snapshot(self.alice))
        legacy=self.f.connect_shared_xl('Legacy')
        self.assertNotIn('harbor_guide',self.server._snapshot(legacy))
        reply=self.f.send(self.alice,f'CHARACTER_CHALLENGE_REGION {self.alice["seq"]+1} harbor_guide 3 {self.revision}')
        self.assertIn('CHARACTER_REJECT',reply)
        self.assertIn('UNAVAILABLE',self.f.send(self.alice,f'CHARACTER_ACCEPT_REGION {self.alice["seq"]+1} harbor_guide 3 harbor_trip 1 {self.revision}'))
        self.f.state(self.alice,*self.server.wilds_map,72,70)
        self.tick(1);self.assertEqual(self.walk()['index'],0) # actual reported player occupies next tile
        self.f.state(self.alice,*self.server.wilds_map,70,70)
        self.tick(2);self.assertEqual(self.walk()['index'],1)
        self.tick(2);self.assertEqual(self.walk()['index'],1) # nested wrappers/replay cannot double step
        self.tick(3);self.assertEqual(self.walk()['index'],2)
        self.tick(4);self.assertEqual(self.walk()['index'],3)
        self.assertIn('harbor_guide',self.server._snapshot(legacy))
        self.f.state(self.alice,*self.server.wilds_map,72,71)
        self.assertIn('harbor_guide 3 1 278 18',self.f.send(self.alice,f'CHARACTER_CHALLENGE_REGION {self.alice["seq"]+1} harbor_guide 3 {self.revision}'))
        self.assertEqual(self.server.module_state['world_characters']['harbor_guide']['version'],3)

    def test_restart_continues_from_persisted_step_without_teleport(self):
        self.tick(1);self.assertEqual(self.walk()['index'],1)
        self.server.close();self.f.f.server=self.f.f.open();self.f.server=self.f.f.server;self.server=self.f.server
        self.assertEqual((self.server.objects[0]['x'],self.server.objects[0]['y']),(72,70))
        self.tick(0);self.assertEqual(self.walk()['index'],2)
        self.tick(0);self.assertEqual(self.walk()['index'],2)
        self.tick(1);self.assertEqual(self.walk()['index'],3)

    def test_invalid_path_and_step_jump_cannot_replace_authority(self):
        context=self.server.inspect()
        for path in ([[71,70],[73,70]],[[71,70],[72,70],[71,70]],[[0,0],[1,0]]):
            actions=deepcopy(self.actions);actions[0]['expected_version']=3;actions[0]['walk']=path
            with self.assertRaises(ValueError):validate_actions(actions,context)
        before=deepcopy(self.server.module_state);objects=deepcopy(self.server.objects)
        forged=dict(state=deepcopy(before),tiles=[],objects=deepcopy(objects))
        control=forged['state']['world_character_controls']['harbor_guide'];control['walk']['index']=3
        control['object']['x']=73;control['object']['y']=71;forged['objects'][0].update(x=73,y=71)
        future=Future();future.set_result((self.candidate,forged))
        self.server.job=(future,'tick',None,self.server.interaction_cursor);self.server.next_tick=float('inf');self.server._poll_mechanics()
        self.assertTrue('skip or rewrite' in self.server.module_error or 'once per authority tick' in self.server.module_error)
        self.assertEqual(self.server.module_state,before);self.assertEqual(self.server.objects,objects)


if __name__=='__main__':unittest.main()
