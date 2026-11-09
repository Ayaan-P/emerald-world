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

    def test_two_original_actors_offer_real_activities_without_duplicate_objects(self):
        from world.guilds import GuildError
        for identity in ('canon_wally','canon_briney'):
            action=self.action();action['id']=identity
            action['changes']['offer']=dict(map='LittlerootTown',count=2)
            self.apply(action)
        self.assertEqual(self.s.objects,[])
        c=self.peer();self.f.connections['Alice']=c
        def locate(identity):
            pair=next(p for p,m in catalog_maps().items() if m['name']==cast.BINDINGS[identity]['map'])
            c['state']=[*pair,1,1,1,7,1];c['state_time']=time.monotonic()
        with tempfile.TemporaryDirectory() as tmp:
            q=IntentQueue(tmp)
            try:
                for identity in ('canon_wally','canon_briney'):
                    reactions.configure(q,self.s.inspect(),identity,'Choose a next field proposal from its actual result.')
                locate('canon_wally')
                preview=cast.guild_command(self.s,c,['wally'])
                self.assertIn('2 trainers visit LittlerootTown',preview[0])
                self.assertIn('Public guild expedition',preview[1])
                self.assertEqual(self.f.stats()[0],10)
                with self.assertRaises(GuildError):cast.guild_command(self.s,c,['wally','0'])
                self.f.command('chronicle off')
                with self.assertRaises(GuildError):cast.guild_command(self.s,c,['wally','1'])
                self.f.command('chronicle on')
                # Actual chat dispatcher, not a side-channel start.
                self.f.command('cast wally 1')
                self.f.state('Alice');self.f.state('Bob')
                event=self.f.events()[-1]
                self.assertEqual((event['character_id'],event['character_offer_id'],event['character_offer_revision']),('canon_wally','field_plan',1))
                self.assertEqual(self.f.stats()[0],20)
                self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.fetch)),1)
                turn=q.claim();self.assertEqual(turn['player'],'canon_wally')
                # Briney does not claim Wally's proposal outcome.
                action=self.action(1,'That field visit helped. I would like to study the route again.')
                action['id']='canon_wally';action['changes']['evidence']=[event['seq']]
                action['changes']['offer']=dict(map='LittlerootTown',count=1)
                ctx=self.context();ctx['runtime'].update(kind='character',observed_event=json.loads(turn['result']))
                reaction=reactions.prepare(ctx,self.fetch)
                reactions.check_response(dict(canonical_actions=[action],tests='assert True'),reaction)
                self.apply(action);q.finish(turn['id'],'succeeded',dict(ok=True))
                locate('canon_wally')
                with self.assertRaises(GuildError):cast.guild_command(self.s,c,['wally','1'])
                self.assertIn('1 trainers',cast.guild_command(self.s,c,['wally'])[0])
                locate('canon_briney');self.f.command('cast briney 1')
                self.f.state('Alice');self.f.state('Bob')
                self.assertEqual(self.f.stats()[0],30)
                self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.fetch)),1)
                self.assertEqual(q.claim()['player'],'canon_briney')
                locate('canon_briney')
                self.assertEqual(cast.guild_command(self.s,c,['briney','1']),['Character offer already accepted.'])
                self.assertEqual(self.f.stats()[0],30)
            finally:q.close()

    def test_proposals_fail_closed_on_location_readiness_and_forged_destinations(self):
        from world.guilds import GuildError
        action=self.action();action['changes']['offer']=dict(map='LittlerootTown',count=2);self.apply(action)
        c=self.peer();c['state'][6]=0
        with self.assertRaises(GuildError):cast.guild_command(self.s,c,['rydel','1'])
        c['state'][6]=1;c['state_time']=0
        with self.assertRaises(GuildError):cast.guild_command(self.s,c,['rydel','1'])
        action=self.action(1);action['changes']['offer']=dict(map='GeneratedWorld_Wilds',count=1)
        with self.assertRaises(ValueError):cast.compile_actions([action],self.context())

    def test_directional_relationship_changes_motivation_from_other_actor_real_result(self):
        # Rydel offers; real guild completion establishes evidence for Wally's interest.
        a=self.action();a['changes']['offer']=dict(map='LittlerootTown',count=2);self.apply(a)
        c=self.peer();self.f.connections['Alice']=c
        self.f.command('cast rydel 1');self.f.state('Alice');self.f.state('Bob')
        first=self.f.events()[-1]['seq']
        w=self.action();w['id']='canon_wally';w['changes']['evidence']=[first]
        w['changes']['relationships']={'canon_rydel':dict(stance='curious',motivation='I wonder if his field plans could help me practice patiently.',evidence=[first])}
        w['changes']['offer']=dict(map='LittlerootTown',count=1)
        self.apply(w)
        # This relation is one-way; no Rydel reaction is invented.
        self.assertNotIn('relationships',self.s.module_state[cast.KEY]['canon_rydel'])
        with tempfile.TemporaryDirectory() as tmp:
            q=IntentQueue(tmp)
            try:
                reactions.configure(q,self.s.inspect(),'canon_wally','Let actual public field results inform this directional interest.')
                a=self.action(1);a['changes']['evidence']=[first]
                a['changes']['offer']=dict(map='LittlerootTown',count=2);self.apply(a)
                self.assertEqual(reactions.observe(q,self.s.inspect(),self.fetch),[]) # authored decision is not a result
                pair=next(p for p,m in catalog_maps().items() if m['name']=='MauvilleCity_BikeShop')
                c['state']=[*pair,1,1,1,7,1];c['state_time']=time.monotonic()
                self.f.command('cast rydel 2');self.f.state('Alice');self.f.state('Bob')
                second=self.f.events()[-1]['seq']
                self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.fetch)),1)
                turn=q.claim();self.assertEqual(turn['player'],'canon_wally')
                ctx=self.context();ctx['runtime'].update(kind='character',observed_event=json.loads(turn['result']))
                reaction=reactions.prepare(ctx,self.fetch)
                self.assertEqual(ctx['players'],[])
                changed=deepcopy(w);changed['expected_version']=1
                changed['changes'].update(goal='Try shorter field practice after considering the new cycling results',dialogue='Rydel has me thinking. I want to try shorter practice trips.',evidence=[second],offer=None)
                changed['changes']['relationships']['canon_rydel']=dict(stance='encouraged',motivation='The new field result makes patient practice seem worth trying.',evidence=[second])
                reactions.check_response(dict(canonical_actions=[changed],tests='assert True'),reaction)
                self.apply(changed);q.finish(turn['id'],'succeeded',dict(ok=True))
                self.assertEqual(reactions.observe(q,self.s.inspect(),self.fetch),[])
                pair=next(p for p,m in catalog_maps().items() if m['name']=='VerdanturfTown_WandasHouse')
                c['state']=[*pair,1,1,1,7,1];c['state_time']=time.monotonic()
                reply=cast.response(self.s,c,'a'*32,'wally')
                self.assertIn('shorter practice trips',reply['briefing'])
                thoughts=cast.guild_command(self.s,c,['wally','thoughts'])
                self.assertTrue(any('Encouraged about Rydel' in line for line in thoughts))
                self.assertTrue(all(len(line)<=113 for line in thoughts))
                self.assertEqual(self.s.objects,[]);self.assertEqual(self.f.stats()[0],30)
                self.s.close();self.f.case.server=self.f.case.open();self.s=self.f.case.server;self.f.server=self.s
                self.assertEqual(self.s.module_state[cast.KEY]['canon_wally']['relationships']['canon_rydel']['stance'],'encouraged')
            finally:q.close()

    def test_relationship_rejects_players_self_and_unattributed_evidence(self):
        self.apply(self.action())
        for target in ('Alice','canon_wally','canon_rydel'):
            a=self.action();a['id']='canon_wally'
            a['changes']['relationships']={target:dict(stance='respectful',motivation='An unsupported inference.',evidence=[self.evidence])}
            with self.assertRaises(ValueError):cast.compile_actions([a],self.context())
        # Even arbitrary source admission cannot attach relationship meaning to
        # a real but unrelated public event.
        a=self.action();a['id']='canon_wally';self.apply(a)
        before=deepcopy(self.s.module_state);after=deepcopy(before)
        row=after[cast.KEY]['canon_wally'];row['version']+=1
        row['relationships']={'canon_rydel':dict(stance='competitive',motivation='This has no target attribution.',evidence=[self.evidence])}
        with self.assertRaises(ValueError):cast.validate_transition(before,after,[],self.s.db)

    def test_private_conversation_is_independent_persistent_and_not_public_author_input(self):
        action=self.action();action['changes']['conversation']={
            'patient':dict(label='I want to learn at my own pace.',reply='We can take this slowly. You choose the pace.'),
            'challenge':dict(label='I want a new challenge.',reply='You sound eager. Think about which route suits you.')}
        self.apply(action)
        alice=self.peer();bob=self.peer('Bob');self.f.connections.update(Alice=alice,Bob=bob)
        history=deepcopy(self.s.memory.history());inspection=deepcopy(self.s.inspect())
        bob_history=deepcopy(bob['chat_history'])
        self.f.command('cast rydel talk')
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_conversations').fetchone()[0],0)
        self.f.command('cast rydel talk 1 patient')
        self.assertEqual(bob['chat_history'],bob_history)
        self.assertIn('take this slowly',cast.response(self.s,alice,'a'*32,'rydel')['briefing'])
        self.assertEqual(cast.response(self.s,bob,'b'*32,'rydel')['briefing'],action['changes']['dialogue'])
        self.f.command('cast rydel talk 1 challenge',trainer='Bob')
        self.assertIn('sound eager',cast.response(self.s,bob,'b'*32,'rydel')['briefing'])
        self.assertIn('take this slowly',cast.response(self.s,alice,'a'*32,'rydel')['briefing'])
        self.assertEqual(self.s.memory.history(),history)
        self.assertEqual(self.s.inspect(),inspection)
        # Private selections never become recalled public evidence or a public
        # character author turn. No party, reward or progress is changed.
        with tempfile.TemporaryDirectory() as tmp:
            q=IntentQueue(tmp)
            try:
                reactions.configure(q,self.s.inspect(),'canon_rydel','Consider public results only.')
                self.assertEqual(reactions.observe(q,self.s.inspect(),self.fetch),[])
            finally:q.close()
        self.assertEqual(self.f.stats()[0],10)
        self.s.close();self.f.case.server=self.f.case.open();self.s=self.f.case.server;self.f.server=self.s
        alice=self.peer();bob=self.peer('Bob');self.f.connections.update(Alice=alice,Bob=bob)
        self.assertIn('take this slowly',cast.response(self.s,alice,'a'*32,'rydel')['briefing'])
        self.assertIn('sound eager',cast.response(self.s,bob,'b'*32,'rydel')['briefing'])
        # Withdrawal remains available away from the NPC, even when busy.
        saved=deepcopy(alice['state']);alice['state'][6]=0
        self.f.command('cast rydel forget');alice['state']=saved
        self.assertEqual(cast.response(self.s,alice,'a'*32,'rydel')['briefing'],action['changes']['dialogue'])
        self.assertIn('sound eager',cast.response(self.s,bob,'b'*32,'rydel')['briefing'])

    def test_private_choice_stale_version_or_wrong_identity_never_changes_another_trainer(self):
        from world.guilds import GuildError
        a=self.action();a['changes']['conversation']={'patient':dict(label='Let us take our time.',reply='There is no need to rush.')};self.apply(a)
        c=self.peer();cast.guild_command(self.s,c,['rydel','talk','1','patient'])
        a['expected_version']=1;a['changes']['conversation']['patient']['reply']='The new field result gives us something else to consider.';self.apply(a)
        # Public actor revision does not silently reinterpret a private choice.
        self.assertEqual(cast.response(self.s,c,'a'*32,'rydel')['briefing'],a['changes']['dialogue'])
        with self.assertRaises(GuildError):cast.guild_command(self.s,c,['rydel','talk','1','patient'])
        with self.assertRaises(GuildError):cast.guild_command(self.s,c,['rydel','talk','2','Bob'])
        impostor=dict(c)
        with self.assertRaises(GuildError):cast.guild_command(self.s,impostor,['rydel','talk','2','patient'])
        c['state_time']=0
        with self.assertRaises(GuildError):cast.guild_command(self.s,c,['rydel','talk','2','patient'])
        self.assertEqual(self.s.db.execute('SELECT trainer,version,choice FROM canonical_conversations').fetchall(),[('Alice',1,'patient')])
        for conversation in [{'patient':dict(label='Hi',reply='{PLAYER}')},{'Alice':dict(label='Hi',reply='Hello')}]:
            a['expected_version']=2;a['changes']['conversation']=conversation
            with self.assertRaises(ValueError):cast.compile_actions([a],self.context())

    @unittest.skipUnless(__import__('os').environ.get('EW_NATIVE_SOURCE'),'set EW_NATIVE_SOURCE for actual native adapter pairing')
    def test_actual_authority_reply_enters_original_script_adapter(self):
        from pathlib import Path
        import os,re,subprocess
        native=Path(os.environ['EW_NATIVE_SOURCE'])
        tests=(native/'tests/test_world_core_story.py').read_text()
        fixture=re.search(r"fixture=r'''(.*?)'''",tests,re.S).group(1)
        source=re.sub(r'^#include .*\n','',(native/'src/world/world_core_story.c').read_text(),flags=re.M)
        action=self.action();action['changes']['conversation']={'patient':dict(label='Take our time.',reply='The field teams can wait. We will take our time.')}
        self.apply(action);peer=self.peer()
        cast.guild_command(self.s,peer,['rydel','talk','1','patient'])
        packet=self.query(peer)
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
