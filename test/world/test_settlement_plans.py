"""Public outcome -> inert plan -> staged inhabited map -> consented expedition.

Provider and sandbox execution are fixture boundaries. Production authority,
compilers, chapter reducer, publication, guild and wire paths are real.
"""
from concurrent.futures import Future
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_character_rebinding as actors
import test_frontier_outposts as frontier
from test_author_cave import wire
from world.mechanics import Candidate, MechanicRuntime
from world.author_settlement import author_settlement


def plan():
    return dict(label='Redwood Field Station',construction=frontier.plan(),resident=dict(
        id='outpost_steward',name='Outpost Steward',role='Guide the new field station',
        goals=['Chart the Littleroot trail'],team=[dict(species=277,level=12)],gfx=8,
        text='Will you chart a trail?',completion_text='Your trail notes are here.',
        completion_goals=['Keep the route notes'],
        offer=dict(id='field_survey',revision=1,kind='expedition',place_id='native:LittlerootTown',target=1)))


class FixtureRuntime:
    def __init__(self): self.calls=[]
    def stage(self,path,tests=None):
        self.calls.append('stage');source=Path(path).read_text()
        scope={};exec(source,scope);scope['update'](dict(players=[],interactions=[],tick=0,revision=0),{})
        return Candidate(source,hashlib.sha256(source.encode()).hexdigest())
    def run(self,candidate,context,state):
        self.calls.append('run');scope={};exec(candidate.source,scope)
        return scope['update'](context,deepcopy(state))


class SettlementFlow(unittest.TestCase):
    def setUp(self):
        self.f=actors.Rebinding();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.server=self.f.server;self.runtime=FixtureRuntime();self.server.runtime=self.runtime
        self.server.create_identity('Founder')
        self.server.guilds.command('Founder','create Redwood')
        self.server.guilds.command('Founder','chronicle on')
        self.server.guilds.command('Founder','expedition start LittlerootTown 1')
        self.server.guilds.visit('Founder','LittlerootTown')
        self.outcome=self.server.memory.history()['events'][-1]
        self.assertEqual(self.outcome['event'],'guild_goal_completed')

    def request(self):
        m=self.server.memory.context(self.server)
        return dict(command='found_settlement',plan=plan(),outcome_seq=self.outcome['seq'],
            previous_revision=self.server.shared_cave.identity,expected_world_id=m['world_id'],expected_sequence=m['through'])

    def transport(self,_socket,request,**kwargs):
        conn=dict(id=None,out=bytearray(),closing=False,sock=object())
        self.server.connections[conn['sock']]=conn
        try:
            self.server._admin_line(conn,json.dumps(request).encode())
            if self.server.job and self.server.job[1]=='settlement':
                self.server.job[0].result(timeout=5)
                self.server._poll_mechanics();self.server.next_tick=float('inf')
            return json.loads(conn['out'])
        finally:self.server.connections.pop(conn['sock'],None)

    def provider(self,prompt,validator,**kwargs):
        self.assertIn('Redwood',prompt);self.assertIn('guild_goal_completed',prompt)
        self.assertNotIn('Founder',prompt);self.assertNotIn('save_path',prompt)
        self.assertIn('explicit player consent',prompt)
        return validator(wire(plan()))

    def tick(self):
        candidate=self.server.candidate
        result=self.runtime.run(candidate,self.server._context(),self.server.module_state)
        future=Future();future.set_result((candidate,result))
        self.server.job=(future,'tick',None,self.server.interaction_cursor)
        self.server.next_tick=float('inf');self.server._poll_mechanics()
        self.assertIsNone(self.server.module_error)

    def test_real_outcome_becomes_inhabited_outpost_then_explicit_offer_completion_changes_dialogue(self):
        previous=self.server.shared_cave.identity;state=deepcopy(self.server.module_state)
        with patch('world.author_settlement.admin_request',side_effect=self.transport),patch('world.author_cave.request_validated',side_effect=self.provider):
            preview=author_settlement('admin','Honor the Redwood expedition',self.outcome['seq'])
            self.assertFalse(preview['applied']);self.assertEqual(self.server.shared_cave.identity,previous)
            published=author_settlement('admin','Honor the Redwood expedition',self.outcome['seq'],apply=True)
        self.assertTrue(published['applied']);new=self.server.shared_cave.identity
        self.assertEqual(self.runtime.calls[:2],['stage','run'])
        self.assertEqual(self.server.module_state['world_characters'][self.f.p['id']],state['world_characters'][self.f.p['id']])
        obj=next(o for o in self.server.objects if o['id']=='outpost_steward')
        self.assertEqual((obj['x'],obj['y']),(19,23));self.assertEqual(obj['region_revision'],new)
        self.assertEqual(self.server.memory.place(new),self.server.memory.place(previous))
        activation=next(e for e in reversed(self.server.memory.history()['events']) if e['event']=='area_activated')
        self.assertEqual(activation['history_evidence'],[self.outcome['seq']])
        token=self.server.create_identity('Visitor')['token']
        self.server.guilds.command('Visitor','create Surveyors')
        conn=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
        self.assertIn('WELCOME',self.f.send(conn,f'HELLO 1 Visitor {token} SOCIALCAVE16CHAR1CHARQUEST1CHARREG1'))
        self.f.state(conn,0,9,8,8);self.f.send(conn,'CAVE GET');self.f.send(conn,'CAVE ACK '+new)
        self.f.state(conn,*self.server.wilds_map,18,23)
        snapshot=self.server._snapshot(conn)
        self.assertIn('CHARACTER_OFFER',snapshot);self.assertIn('outpost_steward',snapshot)
        def accept():return self.f.send(conn,f'CHARACTER_ACCEPT_REGION {conn["seq"]+1} outpost_steward 1 field_survey 1 {new}')
        self.assertIn('PRIVATE',accept())
        self.server.guilds.command('Visitor','chronicle on')
        self.assertIn('STARTED',accept())
        self.assertEqual(self.server.module_state['world_characters']['outpost_steward']['version'],1)
        self.f.state(conn,0,9,8,8)
        completion=self.server.memory.history()['events'][-1]
        self.assertEqual(completion['character_id'],'outpost_steward')
        self.tick()
        resident=self.server.module_state['world_characters']['outpost_steward']
        self.assertEqual(resident['version'],2);self.assertNotIn('offer',resident)
        self.assertEqual(resident['team'],plan()['resident']['team'])
        self.assertEqual(resident['evidence'],[completion['seq']])
        self.assertEqual(next(o for o in self.server.objects if o['id']=='outpost_steward')['text'],plan()['resident']['completion_text'])
        self.server.peers.clear();self.server.close()
        self.f.f.f.server=self.f.f.f.open();self.server=self.f.f.f.server;self.f.server=self.server;self.f.f.server=self.server
        self.assertEqual(self.server.module_state['world_characters']['outpost_steward'],resident)
        self.assertEqual(self.server.shared_cave.identity,new)

    def test_staging_failure_or_concurrent_publication_never_leaves_empty_outpost(self):
        original=self.server.shared_cave.identity;before=self.server.memory.history()
        def fail(*args,**kwargs):raise ValueError('sandbox unavailable')
        with patch.object(self.runtime,'stage',side_effect=fail):
            # Completion is handled like the real server, not raised to transport.
            request=self.request();conn=dict(id=None,out=bytearray(),closing=False,sock=object())
            self.server.connections[conn['sock']]=conn
            self.server._admin_line(conn,json.dumps(request).encode())
            try:self.server.job[0].result(timeout=5)
            except ValueError:pass
            self.server._poll_mechanics()
            self.assertFalse(json.loads(conn['out'])['ok']);self.server.connections.clear()
        self.assertEqual(self.server.shared_cave.identity,original);self.assertEqual(self.server.memory.history(),before)
        # Real staging succeeds, then another authoritative event invalidates its guard.
        request=self.request();conn=dict(id=None,out=bytearray(),closing=False,sock=object())
        self.server.connections[conn['sock']]=conn
        self.server._admin_line(conn,json.dumps(request).encode());self.server.job[0].result(timeout=5)
        self.server.memory.append('area_named',dict(place_id=self.server.memory.place(original),revision=original,before='A',after='B'));self.server.db.commit()
        self.server._poll_mechanics();self.assertFalse(json.loads(conn['out'])['ok']);self.server.connections.clear()
        self.assertEqual(self.server.shared_cave.identity,original);self.assertNotIn('outpost_steward',self.server.module_state['world_characters'])

    def test_first_resident_without_existing_mechanic_and_duplicate_identity_refusal(self):
        self.server.db.execute('DELETE FROM module');self.server.db.commit()
        self.server.candidate=None;self.server.module_state={};self.server.objects=[]
        result=self.transport('',self.request());self.assertTrue(result['ok'],result)
        self.assertEqual(list(self.server.module_state['world_characters']),['outpost_steward'])
        before=self.server.memory.history();revision=self.server.shared_cave.identity
        request=self.request();request['plan']['construction'].update(x=40,y=45)
        refused=self.transport('',request);self.assertFalse(refused['ok'])
        self.assertEqual(self.server.shared_cave.identity,revision);self.assertEqual(self.server.memory.history(),before)

    def test_new_resident_insert_failure_rolls_back_everything(self):
        before=self.server.memory.history();source=self.server.candidate.source;objects=deepcopy(self.server.objects)
        self.server.db.execute("CREATE TRIGGER fail_settlement BEFORE UPDATE ON module BEGIN SELECT RAISE(ABORT,'fail'); END")
        result=self.transport('',self.request());self.assertFalse(result['ok'])
        self.assertEqual(self.server.shared_cave.identity,self.f.old)
        self.assertEqual(self.server.candidate.source,source);self.assertEqual(self.server.objects,objects)
        self.assertEqual(self.server.memory.history(),before)

    def test_non_outcome_and_injected_model_tool_activity_are_rejected(self):
        request=self.request();request['outcome_seq']=1
        self.assertFalse(self.transport('',request)['ok']);self.assertEqual(self.runtime.calls,[])
        with patch('world.author_settlement.admin_request',side_effect=self.transport),patch('world.author_cave.request_validated',side_effect=lambda p,v,**kw:v('{"type":"item.started","item":{"type":"command_execution"}}')):
            with self.assertRaises(ValueError):author_settlement('admin','Redwood camp',self.outcome['seq'],apply=True)
        self.assertNotIn('outpost_steward',self.server.module_state['world_characters'])


if __name__=='__main__':unittest.main()
