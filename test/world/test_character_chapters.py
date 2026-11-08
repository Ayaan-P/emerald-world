"""Production chapter reducer, public outcomes and normal GM source compilation."""
import ast
from concurrent.futures import Future
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from world.character_chapters import chapter_step, compile_plan, validate_plan
from world.mechanics import Candidate
from world import gm
from world.runtime_gm import decode_codex
import test_guild_world_memory as guild_fixture


def plan():
    arrival=dict(id='arrival',when=None,goals=['Help the Redwood expedition'],
        team=[dict(species=277,level=12)],status='active',
        object=dict(id='field_researcher',group=0,num=9,x=9,y=8,gfx=8,text='Let us explore together.'),
        reason='An authored researcher joins the expedition')
    away=dict(id='fieldwork',when=dict(event='guild_goal_completed',place_id='native:LittlerootTown',goal_kind='expedition'),
        goals=['Compare the expedition notes'],team=[dict(species=277,level=12)],status='away',object=None,
        reason='The authority completed the opted-in expedition, so the researcher leaves for fieldwork')
    returned=deepcopy(arrival)
    returned.update(id='return',when=dict(event='guild_goal_completed',place_id='native:LittlerootTown',goal_kind='meetup'),
        goals=['Share field notes at the reunion'],team=[dict(species=278,level=18)],
        reason='Authored team growth accompanies the completed reunion')
    returned['object']['text']='I have new field notes.'
    return dict(id='field_researcher',name='Field Researcher',role='A recurring expedition researcher',
                origin_evidence=[],chapters=[arrival,away,returned])


class CharacterChapterTests(unittest.TestCase):
    def test_validation_rejects_untrusted_triggers_and_unsupported_presence(self):
        for event in ('character_battle_report','interaction','player_save'):
            p=plan();p['chapters'][1]['when']['event']=event
            with self.assertRaises(ValueError):validate_plan(p)
        p=plan();p['chapters'][1]['when']={'event':'guild_goal_completed'}
        with self.assertRaises(ValueError):validate_plan(p)
        p=plan();p['chapters'][1]['status']='retired'
        with self.assertRaises(ValueError):validate_plan(p)
        p=plan();p['chapters'][0]['object']['id']='other'
        with self.assertRaises(ValueError):validate_plan(p)

    def test_compile_requires_exact_previous_source_and_known_evidence(self):
        p=plan();p['origin_evidence']=[42]
        with self.assertRaises(ValueError):compile_plan(p,{'state':{}})
        context={'state':{},'world_memory':{'through':42,'recent':[{'seq':42}]}}
        source=compile_plan(p,context)
        ast.parse(source)
        self.assertIn('chapter_step',source)
        old="def update(context,state):\n    return {'state':state,'tiles':[],'objects':[]}\n"
        context['module_hash']=hashlib.sha256(old.encode()).hexdigest()
        with self.assertRaises(ValueError):compile_plan(p,context)
        context['runtime']={'previous_source':old+'# changed'}
        with self.assertRaises(ValueError):compile_plan(p,context)
        context['runtime']={'previous_source':old}
        self.assertTrue(compile_plan(p,context).startswith(old))
        context['state']={'world_characters':{'field_researcher':{}}}
        with self.assertRaises(ValueError):compile_plan(p,context)

    def test_reducer_preserves_other_effects_and_ignores_old_or_wrong_outcomes(self):
        p=validate_plan(plan());other=dict(id='guide',group=0,num=9,x=10,y=8,gfx=7,text='Welcome.')
        base=dict(state={'keep':{'value':1}},tiles=[{'fixture':True}],objects=[other])
        old=dict(seq=5,event='guild_goal_completed',place_id='native:LittlerootTown',goal_kind='expedition')
        result=chapter_step(p,'definition',10,{'character_history':{'events':[old],'through':5}},base)
        self.assertEqual(result['state']['world_character_chapters'][p['id']]['chapter'],0)
        self.assertEqual(result['state']['keep'],base['state']['keep'])
        self.assertEqual(result['tiles'],base['tiles']);self.assertIn(other,result['objects'])
        self.assertNotIn('world_characters',base['state'])
        wrong=dict(old,seq=11,place_id='native:OtherTown')
        result=chapter_step(p,'definition',10,{'character_history':{'events':[wrong],'through':11}},result)
        self.assertEqual(result['state']['world_characters'][p['id']]['version'],1)
        outcome=dict(old,seq=12)
        result=chapter_step(p,'definition',10,{'character_history':{'events':[outcome],'through':12}},result)
        self.assertEqual(result['state']['world_characters'][p['id']]['status'],'away')
        self.assertEqual(result['objects'],[other])
        replay=chapter_step(p,'definition',10,{'character_history':{'events':[outcome],'through':12}},result)
        self.assertEqual(replay,result)
        with self.assertRaises(ValueError):chapter_step(p,'changed',10,{},result)

    def test_codex_adapter_preserves_chapter_response_without_executing_it(self):
        response={'character_plan':plan(),'tests':'def test_example():\n    assert callable(update)\n'}
        wire='\n'.join(map(json.dumps,[{'type':'item.completed','item':{'type':'agent_message','text':json.dumps(response)}},{'type':'turn.completed'}]))
        self.assertEqual(decode_codex(wire),response)

    def test_real_opted_in_guild_outcomes_drive_departure_and_return(self):
        fixture=guild_fixture.GuildWorldMemoryTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        server=fixture.server
        p=validate_plan(plan());definition=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()
        snapshot=server.inspect();published_after=snapshot['world_memory']['through']
        source=compile_plan(p,snapshot)
        candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
        def tick():
            context=server._context()
            base=dict(state=server.module_state,tiles=[],objects=server.objects)
            result=chapter_step(p,definition,published_after,context,base)
            future=Future();future.set_result((candidate,result))
            server.job=(future,'tick',None,server.interaction_cursor);server.next_tick=float('inf')
            server._poll_mechanics();self.assertIsNone(server.module_error)
        tick();self.assertEqual(server.objects[0]['id'],p['id'])
        fixture.command('chronicle on');fixture.command('expedition start LittlerootTown 2')
        fixture.state('Alice');tick()
        self.assertEqual(server.module_state['world_characters'][p['id']]['status'],'active')
        fixture.state('Bob');tick()
        self.assertEqual(server.module_state['world_characters'][p['id']]['status'],'away')
        self.assertEqual(server.objects,[])
        self.assertEqual(fixture.stats(),(10,1,0))
        fixture.command('meet start LittlerootTown 2');fixture.state('Alice');fixture.state('Bob');tick()
        returned=server.module_state['world_characters'][p['id']]
        self.assertEqual(returned['team'],[dict(species=278,level=18)])
        self.assertEqual(returned['version'],3)
        self.assertEqual(server.objects[0]['text'],'I have new field notes.')
        self.assertEqual(fixture.stats(),(25,1,1))
        self.assertEqual(returned['evidence'],[fixture.events()[-1]['seq']])
        tick();self.assertEqual(server.module_state['world_characters'][p['id']]['version'],3)
        server.close();fixture.case.server=fixture.case.open();fixture.server=fixture.case.server
        self.assertEqual(fixture.server.module_state['world_characters'][p['id']],returned)

    def test_gm_compiles_plan_but_still_submits_to_normal_sandbox(self):
        fixture=guild_fixture.GuildWorldMemoryTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        proposed=[]
        def transport(socket,request,timeout):
            if request['command']=='deploy':
                proposed.append(Path(request['source_path']).read_text())
                return {'ok':False,'error':'Fixture does not claim sandbox acceptance'}
            return fixture.case.admin(request)
        def author(prompt):
            context=json.loads(prompt.split('Request and snapshot follow:\n',1)[1])['inspection']
            self.assertIn('character_chapters',context)
            return {'character_plan':plan(),'tests':'def test_contract():\n    assert callable(update)\n'}
        with patch('world.gm.admin_request',side_effect=transport):
            result=gm.author_and_deploy(fixture.case.root/'controller',fixture.case.root/'socket',
                'Create a recurring expedition researcher',author)
        self.assertFalse(result['ok']);self.assertEqual(result['stage'],'deploy')
        self.assertEqual(result['character_plan']['id'],'field_researcher')
        self.assertEqual(len(proposed),1);ast.parse(proposed[0])
        self.assertEqual(fixture.server.objects,[])


if __name__=='__main__':unittest.main()
