"""A public discovery brings an authored caravan into the shared playable scene."""
import ast
from concurrent.futures import Future
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from world import gm
from world.character_chapters import chapter_step
from world.character_ensembles import compile_ensemble
from world.mechanics import Candidate
from world.runtime_gm import decode_codex
from test_character_chapters import plan
import test_landmark_survey as fixtures


class CaravanTests(unittest.TestCase):
    def setUp(self):
        original=fixtures.LandmarkSurveyTests.send
        self.protocol=patch.object(fixtures.LandmarkSurveyTests,'send',new=lambda f,c,line:original(f,c,line.replace('SOCIALCAVE16','SOCIALCAVE16CHAR1CHARREG1')))
        self.protocol.start();self.addCleanup(self.protocol.stop)
        self.f=fixtures.LandmarkSurveyTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.s=self.f.s;self.plans=[]
        for i,identity in enumerate(('caravan_guide','caravan_trainer')):
            p=plan();p.update(id=identity,name='Caravan Guide' if i==0 else 'Caravan Trainer',role='A visiting field caravan resident')
            waiting=deepcopy(p['chapters'][0]);waiting.update(id='travelling',status='away',object=None,reason='The caravan awaits public route reports')
            arrival=deepcopy(p['chapters'][0]);arrival.update(id='camp',when=self.trigger('ruins'),reason='A public ruins report brings the caravan to camp')
            arrival['object'].update(id=identity,group=self.s.wilds_map[0],num=self.s.wilds_map[1],x=15+i*2,y=20,region_revision=self.f.revision,
                                     text='The caravan has arrived!\nLet us study these paths.')
            if i==0:arrival['services']=['guide']
            else:arrival['team']=[dict(species=278,level=18)]
            moved=deepcopy(arrival);moved.update(id='lookout',when=self.trigger('orchard'),reason='The public orchard report moves the caravan to the lookout')
            moved['object'].update(x=105+i*2,y=105,text='Our camp is here now.\nThe orchard led us onward.')
            p['chapters']=[waiting,arrival,moved];self.plans.append(p)
        self.inspection=self.s.inspect();self.source=compile_ensemble(self.plans,self.inspection)
        self.candidate=Candidate(self.source,hashlib.sha256(self.source.encode()).hexdigest())

    def trigger(self,site):
        return dict(event='landmark_discovery_shared',place_id=self.s.memory.place(self.f.revision),revision=self.f.revision,landmark=site)

    def tick(self):
        result=dict(state=self.s.module_state,tiles=[],objects=self.s.objects)
        context=self.s._context()
        for p in self.plans:
            definition=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()
            result=chapter_step(p,definition,self.inspection['world_memory']['through'],context,result)
        future=Future();future.set_result((self.candidate,result))
        self.s.job=(future,'tick',None,self.s.interaction_cursor);self.s.next_tick=float('inf');self.s._poll_mechanics()

    def share(self,site,x,y):
        self.f.state(self.f.conn,x,y);self.f.command('/explore share '+site+' confirm')

    def test_public_history_brings_distinct_playable_residents_then_moves_whole_camp(self):
        self.tick();self.assertIsNone(self.s.module_error);self.assertEqual(self.s.objects,[])
        self.f.command('/explore start');self.f.state(self.f.conn,95,35);self.tick()
        self.assertEqual(self.s.objects,[])
        self.share('ruins',95,35);self.tick();self.assertIsNone(self.s.module_error)
        self.assertEqual([(o['id'],o['x'],o['y']) for o in self.s.objects],[(p['id'],15+i*2,20) for i,p in enumerate(self.plans)])
        snapshot=self.s._snapshot(self.f.conn)
        for p in self.plans:self.assertIn('REGION_OBJECT '+self.f.revision+' '+p['id'],snapshot)
        self.f.state(self.f.conn,14,20);self.f.command('/explore guide caravan_guide')
        self.assertTrue(any('Guide to' in bytes.fromhex(r[3]).decode() for r in self.f.conn['chat_history']))
        self.f.state(self.f.conn,16,20)
        reply=self.f.send(self.f.conn,f'CHARACTER_CHALLENGE_REGION {self.f.conn["seq"]+1} caravan_trainer 2 {self.f.revision}')
        self.assertIn('caravan_trainer 2 1 278 18',reply)
        pending=self.f.conn['character_pending']
        self.f.send(self.f.conn,f'CHARACTER_RESULT {pending["seq"]} caravan_trainer 2 0')
        before=deepcopy(self.s.module_state)
        self.s.close();self.f.f.server=self.f.f.open();self.s=self.f.s=self.f.f.server;self.f.conn=self.f.connect('Scout')
        self.assertEqual(self.s.module_state,before)
        self.share('orchard',30,95);self.tick();self.assertIsNone(self.s.module_error)
        self.assertEqual([(o['x'],o['y']) for o in self.s.objects],[(105,105),(107,105)])
        self.assertTrue(all(c['version']==3 for c in self.s.module_state['world_characters'].values()))
        before=deepcopy(self.s.module_state['world_characters']);objects=deepcopy(self.s.objects)
        self.tick();self.assertEqual(self.s.module_state['world_characters'],before);self.assertEqual(self.s.objects,objects)

    def test_failed_second_resident_history_write_never_publishes_half_a_caravan(self):
        self.tick();self.f.command('/explore start');self.share('ruins',95,35)
        before=deepcopy(self.s.module_state);history=self.s.memory.history()
        self.s.db.execute("""CREATE TRIGGER refuse_caravan BEFORE INSERT ON events
            WHEN NEW.kind='world_memory' AND instr(NEW.data,'caravan_trainer')>0
            BEGIN SELECT RAISE(ABORT,'fixture refuses second resident'); END""")
        self.tick();self.assertIsNotNone(self.s.module_error)
        self.assertEqual(self.s.objects,[]);self.assertEqual(self.s.module_state,before)
        self.assertEqual(self.s.memory.history(),history)
        self.s.close();self.f.f.server=self.f.f.open();self.s=self.f.s=self.f.f.server
        self.assertEqual(self.s.module_state,before);self.assertEqual(self.s.objects,[])

    def test_cast_validation_capacity_identity_and_existing_source_preservation(self):
        ast.parse(self.source)
        for bad in ([self.plans[0]],self.plans*3,[self.plans[0],self.plans[0]]):
            with self.assertRaises(ValueError):compile_ensemble(bad,self.inspection)
        occupied=deepcopy(self.inspection);occupied['state']['world_characters']={self.plans[0]['id']:{}}
        with self.assertRaises(ValueError):compile_ensemble(self.plans,occupied)
        full=deepcopy(self.inspection);full['state']['world_characters']={str(i):{} for i in range(7)}
        with self.assertRaisesRegex(ValueError,'capacity'):compile_ensemble(self.plans,full)
        previous="def update(context,state):\n    return {'state':state,'tiles':[],'objects':[]}\n"
        context=deepcopy(self.inspection);context['module_hash']=hashlib.sha256(previous.encode()).hexdigest()
        with self.assertRaises(ValueError):compile_ensemble(self.plans,context)
        context['runtime']={'previous_source':previous}
        self.assertTrue(compile_ensemble(self.plans,context).startswith(previous))
        collision=deepcopy(self.plans)
        for p in collision:p['chapters']=p['chapters'][1:];p['chapters'][0]['when']=None
        collision[1]['chapters'][0]['object'].update(x=15,y=20)
        with self.assertRaises(ValueError):compile_ensemble(collision,self.inspection)

    def test_real_gm_adapter_retains_entire_cast_and_requires_normal_sandbox(self):
        response={'character_ensemble':self.plans,'tests':'def test_cast():\n    assert callable(update)\n'}
        wire='\n'.join(map(json.dumps,[{'type':'item.completed','item':{'type':'agent_message','text':json.dumps(response)}},{'type':'turn.completed'}]))
        self.assertEqual(decode_codex(wire),response)
        proposed=[]
        def transport(socket,request,timeout):
            if request['command']=='deploy':
                proposed.append(Path(request['source_path']).read_text())
                return dict(ok=False,error='Fixture refuses sandbox acceptance')
            return self.f.f.admin(request)
        def author(prompt):
            self.assertIn('character_ensembles',prompt);return response
        with patch('world.gm.admin_request',side_effect=transport):
            report=gm.author_and_deploy(self.f.f.root/'caravan-controller',self.f.f.root/'socket','Bring a travelling field caravan',author)
        self.assertFalse(report['ok']);self.assertEqual(report['stage'],'deploy')
        self.assertEqual(report['character_ensemble'],self.plans);self.assertEqual(len(proposed),1)
        ast.parse(proposed[0]);self.assertEqual(self.s.objects,[])

if __name__=='__main__':unittest.main()
