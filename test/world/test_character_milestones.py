"""Several real public discoveries unlock a visible resident role, not private travel."""
from concurrent.futures import Future
from copy import deepcopy
import hashlib
import json
import unittest
from unittest.mock import patch
from world.character_chapters import chapter_step,compile_plan,validate_plan
from world.route_characters import bind_landmarks
from world.route_artifacts import load
from world.mechanics import Candidate
from test_character_chapters import plan
import test_landmark_survey as fixtures


def trigger(landmark):
    return dict(event='landmark_discovery_shared',place_id='area:11111111-1111-1111-1111-111111111111',revision='a'*64,landmark=landmark)


def program():
    p=plan();p['chapters']=[p['chapters'][0],p['chapters'][2]]
    p['chapters'][1]['when']={'all':[trigger('ruins'),trigger('orchard')]}
    return p


class MilestoneTests(unittest.TestCase):
    def test_bounded_public_conditions_and_offered_goal_consent_contract(self):
        p=program();validate_plan(p)
        for value in ([],[trigger('ruins')],[trigger('ruins')]*2,[trigger(str(i)) for i in range(5)],
                      [{'event':'private_visit','place_id':'x'},trigger('ruins')],
                      [{'all':[trigger('ruins'),trigger('orchard')]},trigger('ruins')]):
            q=deepcopy(p);q['chapters'][1]['when']={'all':value}
            with self.assertRaises(ValueError):validate_plan(q)
        p['chapters'][0]['offer']=dict(id='survey',revision=1,kind='expedition',place_id='native:LittlerootTown',target=1)
        p['chapters'][1]['when']['all'][0]=dict(event='guild_goal_completed',place_id='native:LittlerootTown')
        with self.assertRaisesRegex(ValueError,'exact character'):validate_plan(p)

    def test_order_batches_replay_and_one_record_per_requirement(self):
        p=program();base=dict(state={},objects=[],tiles=[])
        def step(result,events):
            return chapter_step(p,'milestones',10,{'character_history':{'events':events,'through':events[-1]['seq']}},result)
        result=step(base,[dict(trigger('orchard'),seq=11)])
        self.assertEqual(result['state']['world_characters'][p['id']]['version'],1)
        self.assertEqual(step(result,[dict(trigger('orchard'),seq=11)]),result)
        result=step(result,[dict(trigger('ruins'),seq=12,revision='b'*64)])
        self.assertEqual(result['state']['world_character_chapters'][p['id']]['chapter'],0)
        result=step(result,[dict(trigger('ruins'),seq=13)])
        self.assertEqual(result['state']['world_characters'][p['id']]['evidence'],[11,13])
        self.assertEqual(result['state']['world_characters'][p['id']]['version'],2)
        self.assertNotIn('milestones',result['state']['world_character_chapters'][p['id']])
        # Overlapping predicates still need two distinct records, never one duplicated fact.
        p['chapters'][1]['when']={'all':[dict(event='area_named',place_id='area:x'),dict(event='area_named',after='New')]}
        result=step(base,[dict(event='area_named',place_id='area:x',after='New',seq=11)])
        self.assertEqual(result['state']['world_character_chapters'][p['id']]['chapter'],0)

    def test_branch_choice_discards_partial_milestones_and_future_events_need_repeating(self):
        p=program();alternative=deepcopy(p['chapters'][1])
        alternative.update(id='alternate',when=dict(event='area_named',after='New'),next=[])
        p['chapters'].append(alternative);p['chapters'][0]['next']=['return','alternate']
        p['chapters'][1]['next']=[];validate_plan(p)
        events=[dict(trigger('orchard'),seq=1),dict(event='area_named',after='New',seq=2),dict(trigger('ruins'),seq=3)]
        result=chapter_step(p,'branch',0,{'character_history':{'events':events,'through':3}},dict(state={},tiles=[],objects=[]))
        self.assertEqual(result['state']['world_character_chapters'][p['id']]['chapter'],2)
        self.assertNotIn('milestones',result['state']['world_character_chapters'][p['id']])
        self.assertEqual(result['state']['world_characters'][p['id']]['evidence'],[2])
        # A condition that occurred before a chapter became eligible is not a stored universal achievement.
        p=program();arrival=deepcopy(p['chapters'][0]);arrival.update(id='waiting',when=dict(event='area_named',after='Begin'))
        p['chapters'].insert(1,arrival);validate_plan(p)
        events=[dict(trigger('orchard'),seq=1),dict(event='area_named',after='Begin',seq=2),dict(trigger('ruins'),seq=3)]
        result=chapter_step(p,'later',0,{'character_history':{'events':events,'through':3}},dict(state={},tiles=[],objects=[]))
        self.assertEqual(result['state']['world_character_chapters'][p['id']]['chapter'],1)
        self.assertEqual(len(result['state']['world_character_chapters'][p['id']]['milestones']['return']),1)

    def test_real_shared_landmarks_relocate_researcher_enable_guide_and_freeze_new_team(self):
        f=fixtures.LandmarkSurveyTests()
        original=fixtures.LandmarkSurveyTests.send
        with patch.object(fixtures.LandmarkSurveyTests,'send',new=lambda f,c,line:original(f,c,line.replace('SOCIALCAVE16','SOCIALCAVE16CHAR1CHARREG1'))):
            f.setUp();self.addCleanup(f.doCleanups)
            s=f.s;artifact=load(s,f.revision);p=program()
            for condition in p['chapters'][1]['when']['all']:
                condition.update(place_id=s.memory.place(f.revision),revision=f.revision)
            p['chapters'][0]['object']['text']='Share orchard and ruins.\nI will chart a new camp.'
            p['chapters'][1]['object']['text']='Both reports reached me!\nAsk me to guide you.'
            p['chapters'][1]['services']=['guide']
            blob=s.db.execute('SELECT template FROM generated_area_archive WHERE identity=?',(f.revision,)).fetchone()[0]
            p=bind_landmarks(p,blob,artifact['report'],{'arrival':'camp','return':'lookout'})
            inspection=s.inspect();source=compile_plan(p,inspection)
            definition=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()
            candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
            def tick():
                result=chapter_step(p,definition,inspection['world_memory']['through'],s._context(),dict(state=s.module_state,tiles=[],objects=s.objects))
                future=Future();future.set_result((candidate,result))
                s.job=(future,'tick',None,s.interaction_cursor);s.next_tick=float('inf');s._poll_mechanics()
                self.assertIsNone(s.module_error)
            tick();f.command('/explore start')
            f.state(f.conn,95,35);tick()
            self.assertEqual(s.module_state['world_characters'][p['id']]['version'],1)
            f.command('/explore share ruins confirm');tick()
            self.assertEqual(s.module_state['world_characters'][p['id']]['version'],1)
            partial=deepcopy(s.module_state['world_character_chapters'][p['id']])
            self.assertEqual(len(partial['milestones']['return']),1)
            s.close();f.f.server=f.f.open();s=f.s=f.f.server;f.conn=f.connect('Scout')
            self.assertEqual(s.module_state['world_character_chapters'][p['id']],partial)
            # Another explorer supplies the independent missing public discovery.
            f.conn=f.connect('Partner');f.command('/explore start');f.state(f.conn,30,95)
            tick();self.assertEqual(s.module_state['world_characters'][p['id']]['version'],1)
            f.command('/explore share orchard confirm');tick()
            resident=s.module_state['world_characters'][p['id']]
            self.assertEqual(resident['version'],2);self.assertEqual(resident['services'],['guide'])
            self.assertEqual((s.objects[0]['x'],s.objects[0]['y']),(105,105))
            self.assertEqual(s.objects[0]['text'],'Both reports reached me!\nAsk me to guide you.')
            events=[e for e in s.memory.history()['events'] if e['event']=='landmark_discovery_shared']
            self.assertEqual(resident['evidence'],[e['seq'] for e in events])
            f.state(f.conn,104,105)
            reply=f.send(f.conn,f'CHARACTER_CHALLENGE_REGION {f.conn["seq"]+1} field_researcher 2 {f.revision}')
            self.assertIn('field_researcher 2 1 278 18',reply)
            tick();self.assertEqual(s.module_state['world_characters'][p['id']],resident)

if __name__=='__main__':unittest.main()
