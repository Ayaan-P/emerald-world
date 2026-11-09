"""Actual authority/public activity/canonical response loop, not rendered play."""
from concurrent.futures import Future
from copy import deepcopy
import hashlib
import json
import tempfile
import time
import unittest
from test_guild_world_memory import GuildWorldMemoryTests
from world import canonical_cast as cast, character_reactions as reactions
from world.build_catalog import catalog_maps
from world.mechanics import Candidate
from world.runtime_gm import IntentQueue

class CanonicalCastTests(unittest.TestCase):
    def setUp(self):
        self.f=GuildWorldMemoryTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.s=self.f.server
        self.source='def update(context,state):\n    return dict(state=state,tiles=[],objects=[])\n'
        self.commit(self.source,dict(state={},tiles=[],objects=[]))
        self.f.command('chronicle on');self.complete()
    def commit(self,source,result):
        candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
        future=Future();future.set_result((candidate,result))
        self.s.job=(future,'deploy',None,self.s.interaction_cursor);self.s.next_tick=float('inf');self.s._poll_mechanics()
        self.assertIsNone(self.s.module_error)
        self.source=source
    def complete(self):
        self.f.command('expedition start LittlerootTown 2');self.f.state('Alice');self.f.state('Bob')
        self.evidence=self.f.events()[-1]['seq']
    def action(self,version=0,text='The field teams have been busy. I am thinking about gentler rides.'):
        return dict(id='canon_rydel',expected_version=version,changes=dict(goal='Consider routes suggested by real field activity',dialogue=text,
            places=['native:LittlerootTown'],evidence=[self.evidence],reason='Public field results inform the next cycling idea'))
    def context(self):
        c=self.s.inspect();c['runtime']=dict(previous_source=self.source)
        c['recalled_history']=dict(events=self.s.memory.history()['events']);return c
    def apply(self,action):
        source=cast.compile_actions([action],self.context());ns={};exec(source,ns)
        result=ns['update'](self.s._context(),deepcopy(self.s.module_state));self.commit(source,result)
    def peer(self,name='Alice',cap=True):
        token=self.s.create_identity(name)['token'];self.s.peers.pop(name,None)
        c=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
        self.s._line(c,('HELLO 1 '+name+' '+token+' SOCIALCHATCOMMANDS1'+('CORE1' if cap else '')).encode())
        self.assertEqual(c['id'],name);c['out'].clear()
        pair=next(p for p,m in catalog_maps().items() if m['name']=='MauvilleCity_BikeShop')
        c['state']=[*pair,1,1,1,7,1];c['state_time']=time.monotonic();return c
    def query(self,c):
        c['out'].clear();self.s._line(c,('CORE '+'a'*32+' CAST rydel safe 15').encode());return c['out'].decode().strip()
    def fetch(self,query):
        return dict(ok=True,world_id=self.s.memory.world_id,**self.s.memory.history(**{k:v for k,v in query.items() if k!='command'}))
    def test_original_identity_public_activity_reaction_and_restart(self):
        self.apply(self.action());self.assertEqual(self.s.objects,[])
        c=self.peer();first=self.query(c);self.assertTrue(first.startswith('CORE REPLY 15'))
        self.assertIn('field teams',bytes.fromhex(first.split()[-1]).decode())
        with tempfile.TemporaryDirectory() as tmp:
            q=IntentQueue(tmp)
            try:
                reactions.configure(q,self.s.inspect(),'canon_rydel','Choose useful cycling ideas from public activity, without changing the bike service.')
                self.assertEqual(reactions.observe(q,self.s.inspect(),self.fetch),[])
                # Restore fixture connection to actual authority peer before visiting.
                self.f.connections['Alice']=c;self.complete()
                self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.fetch)),1)
                item=q.claim();packet=json.loads(item['result']);ctx=self.context()
                ctx['runtime'].update(kind='character',observed_event=packet)
                reaction=reactions.prepare(ctx,self.fetch)
                action=self.action(1,'Those new field notes changed my plan. I am looking into a gentler cycling route.')
                reactions.check_response(dict(canonical_actions=[action],tests='assert True'),reaction)
                self.apply(action);q.finish(item['id'],'succeeded',dict(ok=True))
                self.assertEqual(reactions.observe(q,self.s.inspect(),self.fetch),[])
            finally:q.close()
        c['state_time']=time.monotonic();c['state'][:2]=next(p for p,m in catalog_maps().items() if m['name']=='MauvilleCity_BikeShop')
        second=self.query(c);self.assertIn('changed my plan',bytes.fromhex(second.split()[-1]).decode())
        self.assertNotEqual(first,second);self.assertEqual(self.s.objects,[])
        from world.world_journal import describe
        decisions=[e for e in self.s.memory.history()['events'] if e['event']=='canonical_actor_changed']
        self.assertEqual(len(decisions),2)
        self.assertEqual(describe(decisions[-1])['title'],'Rydel reconsidered a goal')
        self.assertIn('native:MauvilleCity_BikeShop',decisions[-1]['places'])
        self.assertEqual(self.f.stats(),(20,2,0))
        self.s.close();self.f.case.server=self.f.case.open();self.s=self.f.case.server;self.f.server=self.s
        self.assertEqual(cast.records(self.s.module_state)['canon_rydel']['version'],2)
        self.assertIn('changed my plan',bytes.fromhex(self.query(self.peer()).split()[-1]).decode())
    def test_refusal_preserves_unknown_actor_location_and_legacy_boundaries(self):
        self.assertEqual(self.query(self.peer()),'CORE REFUSED 15')
        self.apply(self.action());self.assertEqual(self.query(self.peer('Bob',False)),'CORE REFUSED 15')
        c=self.peer();c['state_time']-=10;self.assertEqual(self.query(c),'CORE REFUSED 15')
        c['state_time']=time.monotonic();c['state'][:2]=[0,9];self.assertEqual(self.query(c),'CORE REFUSED 15')
    def test_rejects_fake_private_evidence_controls_and_duplicate_objects(self):
        for changes in [dict(dialogue='Unsafe {PLAYER} control'),dict(team=[{'species':1,'level':100}]),dict(evidence=[999999])]:
            action=self.action();action['changes'].update(changes)
            with self.assertRaises(ValueError):cast.compile_actions([action],self.context())
        self.apply(self.action());state=deepcopy(self.s.module_state)
        with self.assertRaises(ValueError):cast.validate_transition(state,state,[dict(id='canon_rydel')],self.s.db)
        state['canonical_cast']['canon_rydel']['version']=5
        with self.assertRaises(ValueError):cast.validate_transition(self.s.module_state,state,[],self.s.db)

    @unittest.skipUnless(__import__('os').environ.get('EW_NATIVE_SOURCE'),'set EW_NATIVE_SOURCE for actual native adapter pairing')
    def test_actual_authority_reply_enters_original_script_adapter(self):
        from pathlib import Path
        import os,re,subprocess
        native=Path(os.environ['EW_NATIVE_SOURCE'])
        tests=(native/'tests/test_world_core_story.py').read_text()
        fixture=re.search(r"fixture=r'''(.*?)'''",tests,re.S).group(1)
        source=re.sub(r'^#include .*\n','',(native/'src/world/world_core_story.c').read_text(),flags=re.M)
        self.apply(self.action())
        packet=self.query(self.peer())
        world=self.s.memory.world_id
        checks='''
int main(void){
char *ready[]={"CORE","READY","1",WORLD};
assert(WorldCoreStory_Line(4,ready));sCore.nonce=14;script=true;progress=0;
const u8 *hook=MauvilleCity_BikeShop_EventScript_Rydel+2;
assert(WorldCoreStory_BeforeScript(hook));assert(strstr(sent,"CAST rydel safe 15"));
char line[]=PACKET;char *tokens[16];unsigned n=0;
for(char *t=strtok(line," ");t;t=strtok(NULL," "))tokens[n++]=t;
assert(WorldCoreStory_Line(n,tokens));assert(strstr(sCore.briefing,"field teams"));
assert(WorldCoreStory_BeforeScript(hook));assert(shown==1);
hidden=true;assert(!WorldCoreStory_BeforeScript(hook));assert(progress==0);
return 0;}
'''.replace('WORLD',json.dumps(world)).replace('PACKET',json.dumps(packet))
        with tempfile.TemporaryDirectory() as tmp:
            c=Path(tmp)/'paired.c';c.write_text(fixture+source+checks);exe=Path(tmp)/'paired'
            subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)
