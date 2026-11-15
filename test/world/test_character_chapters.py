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

    def test_shared_discovery_requires_exact_public_landmark_scope(self):
        p=plan();p['chapters'][1]['when']=dict(event='landmark_discovery_shared',
            place_id='area:11111111-1111-1111-1111-111111111111',revision='a'*64,landmark='lookout')
        validate_plan(p)
        for key in ('place_id','revision','landmark'):
            bad=deepcopy(p);bad['chapters'][1]['when'].pop(key)
            with self.assertRaisesRegex(ValueError,'exact place'):validate_plan(bad)
        for event in ('survey_visit','landmark_discovered','private_exploration'):
            bad=deepcopy(p);bad['chapters'][1]['when']['event']=event
            with self.assertRaises(ValueError):validate_plan(bad)
        base=dict(state={},tiles=[],objects=[])
        wrong=dict(p['chapters'][1]['when'],seq=1,revision='b'*64)
        result=chapter_step(p,'discovery',0,{'character_history':{'events':[wrong],'through':1}},base)
        self.assertEqual(result['state']['world_character_chapters'][p['id']]['chapter'],0)
        shared=dict(p['chapters'][1]['when'],seq=2)
        result=chapter_step(p,'discovery',0,{'character_history':{'events':[shared],'through':2}},result)
        self.assertEqual(result['state']['world_character_chapters'][p['id']]['chapter'],1)
        self.assertEqual(result['state']['world_characters'][p['id']]['evidence'],[2])

    def test_guidance_is_an_explicit_authored_service(self):
        p=plan();p['chapters'][0]['services']=['guide'];validate_plan(p)
        result=chapter_step(p,'guide',0,{'character_history':{'events':[],'through':0}},dict(state={},tiles=[],objects=[]))
        self.assertEqual(result['state']['world_characters'][p['id']]['services'],['guide'])
        p['chapters'][0]['services']=['auto_publish']
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

    def test_branch_validation_and_deterministic_first_event(self):
        p=plan();p['chapters'][0]['next']=['fieldwork','return']
        p['chapters'][1]['next']=[];p['chapters'][2]['next']=[]
        validate_plan(p)
        for targets in (['arrival'],['missing'],['fieldwork','fieldwork']):
            broken=deepcopy(p);broken['chapters'][0]['next']=targets
            with self.assertRaises(ValueError):validate_plan(broken)
        broken=deepcopy(p);broken['chapters'][0]['next']=[]
        with self.assertRaisesRegex(ValueError,'reachable'):validate_plan(broken)
        # One chronological batch contains both alternatives. The earlier
        # committed outcome chooses the terminal route; later/replayed events
        # cannot resurrect a skipped branch.
        events=[dict(seq=1,event='guild_goal_completed',place_id='native:LittlerootTown',goal_kind='meetup'),
                dict(seq=2,event='guild_goal_completed',place_id='native:LittlerootTown',goal_kind='expedition')]
        base=dict(state={},tiles=[],objects=[])
        result=chapter_step(p,'branches',0,{'character_history':{'events':events,'through':2}},base)
        self.assertEqual(result['state']['world_character_chapters'][p['id']]['chapter'],2)
        self.assertEqual(result['state']['world_characters'][p['id']]['evidence'],[1])
        replay=chapter_step(p,'branches',0,{'character_history':{'events':events,'through':2}},result)
        self.assertEqual(result,replay)

    def test_real_guild_choice_changes_returning_character_playable_role(self):
        for goal in ('expedition','meetup'):
            with self.subTest(goal=goal):
                fixture=guild_fixture.GuildWorldMemoryTests();fixture.setUp()
                try:
                    server=fixture.server;p=plan()
                    p['chapters'][0]['next']=['fieldwork','return']
                    explorer=p['chapters'][1];explorer['next']=[];explorer['status']='active'
                    explorer['object']=deepcopy(p['chapters'][0]['object'])
                    explorer['object']['text']='Your expedition inspired me!\nMeet my field team.'
                    explorer['team']=[dict(species=278,level=18)]
                    mentor=p['chapters'][2];mentor['next']=[]
                    mentor['object']['text']='Your reunion inspired me.\nI will stay and teach.'
                    mentor['team']=[dict(species=277,level=14)]
                    p=validate_plan(p);snapshot=server.inspect()
                    definition=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()
                    source=compile_plan(p,snapshot);candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
                    def tick():
                        result=chapter_step(p,definition,snapshot['world_memory']['through'],server._context(),
                            dict(state=server.module_state,tiles=[],objects=server.objects))
                        future=Future();future.set_result((candidate,result))
                        server.job=(future,'tick',None,server.interaction_cursor);server.next_tick=float('inf')
                        server._poll_mechanics();self.assertIsNone(server.module_error)
                    tick();fixture.command('chronicle on')
                    fixture.command(('expedition' if goal=='expedition' else 'meet')+' start LittlerootTown 2')
                    fixture.state('Alice');tick()
                    self.assertEqual(server.module_state['world_characters'][p['id']]['version'],1)
                    fixture.state('Bob');tick()
                    chosen=explorer if goal=='expedition' else mentor
                    character=server.module_state['world_characters'][p['id']]
                    self.assertEqual(character['version'],2)
                    self.assertEqual(character['team'],chosen['team'])
                    self.assertEqual(server.objects[0]['text'],chosen['object']['text'])
                    self.assertEqual(character['evidence'],[fixture.events()[-1]['seq']])
                    # The chosen branch's team is the real battle admission
                    # payload, not just narrative metadata.
                    token=server.create_identity('Alice')['token'];server.peers.pop('Alice',None)
                    conn=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
                    server._line(conn,('HELLO 1 Alice '+token+' SOCIALTRAVELCHATRALLYCHAR1').encode())
                    self.assertIn(b'WELCOME',conn['out']);conn['out'].clear()
                    server._line(conn,('STATE 1 0 9 8 8 4 7 1 '+'a'*16+' '+'b'*16).encode())
                    conn['out'].clear();server._line(conn,b'CHARACTER_CHALLENGE 2 field_researcher 2')
                    mon=chosen['team'][0]
                    self.assertIn(f'CHARACTER_BATTLE_V1 2 field_researcher 2 1 {mon["species"]} {mon["level"]}',conn['out'].decode())
                    server.close();fixture.case.server=fixture.case.open();fixture.server=fixture.case.server
                    self.assertEqual(fixture.server.module_state['world_characters'][p['id']],character)
                finally:fixture.doCleanups()

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
