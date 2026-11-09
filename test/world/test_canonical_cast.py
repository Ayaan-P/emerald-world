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

    def test_real_cast_letter_delivery_recipient_reply_and_growth_without_player_chores(self):
        self.apply(self.action())
        w=self.action();w['id']='canon_wally';self.apply(w)
        def letters():return [e for e in self.s.memory.history()['events'] if e['event']=='canonical_letter_delivered']
        def react(q,identity,action):
            self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.fetch)),1)
            turn=q.claim();self.assertEqual(turn['player'],identity)
            context=self.context();context['runtime'].update(kind='character',observed_event=json.loads(turn['result']))
            selected=reactions.prepare(context,self.fetch)
            reactions.check_response(dict(canonical_actions=[action],tests='assert True'),selected)
            self.apply(action);q.finish(turn['id'],'succeeded',dict(ok=True))
        with tempfile.TemporaryDirectory() as tmp:
            q=IntentQueue(tmp)
            try:
                for identity in ('canon_rydel','canon_wally'):
                    reactions.configure(q,self.s.inspect(),identity,'Consider delivered public correspondence without inventing meetings.')
                a=self.action(1);a['changes']['letter']=dict(to='canon_wally',text='Wally, would patient practice interest you? The field notes made me reconsider speed.')
                self.apply(a)
                first=letters()[0];self.assertEqual((first['sender'],first['recipient'],first['depth']),('canon_rydel','canon_wally',1))
                # No player visit, quest or synthetic achievement is needed for
                # the character to perform this supported communication.
                self.assertEqual(self.f.stats()[0],10)
                reply=deepcopy(w);reply['expected_version']=1
                reply['changes'].update(evidence=[first['seq']],goal='Consider patient practice after reading Rydel',dialogue='Rydel wrote to me. I want to think about patient practice.',letter=dict(to='canon_rydel',text='Thank you, Rydel. I would rather find my own pace than promise a race.'))
                react(q,'canon_wally',reply)
                second=letters()[-1];self.assertEqual(second['depth'],2)
                final=self.action(2,'Wally wants his own pace. I am rethinking how I encourage new riders.')
                final['changes'].update(evidence=[second['seq']],goal='Offer encouragement without assuming everyone wants speed',letter=None)
                # A third automatic letter cannot perpetuate the loop.
                loop=deepcopy(final);loop['changes']['letter']=dict(to='canon_wally',text='Another automatic reply.')
                with self.assertRaises(ValueError):cast.compile_actions([loop],self.context())
                react(q,'canon_rydel',final)
                self.assertEqual(reactions.observe(q,self.s.inspect(),self.fetch),[])
                self.assertEqual(len(letters()),2)
                # Unchanged source ticks cannot send again.
                ns={};exec(self.source,ns)
                self.commit(self.source,ns['update'](self.s._context(),deepcopy(self.s.module_state)))
                self.assertEqual(len(letters()),2)
                c=self.peer();view=cast.guild_command(self.s,c,['rydel','letters'])
                self.assertTrue(any('own pace' in line for line in view))
                self.assertIn('Wally wants his own pace',cast.response(self.s,c,'a'*32,'rydel')['briefing'])
                from world.world_journal import describe
                self.assertEqual(describe(second)['title'],'Wally wrote to Rydel')
                self.assertEqual(self.s.objects,[]);self.assertEqual(self.f.stats()[0],10)
                self.s.close();self.f.case.server=self.f.case.open();self.s=self.f.case.server;self.f.server=self.s
                self.assertEqual(len(letters()),2)
                self.assertIn('assuming',self.s.module_state[cast.KEY]['canon_rydel']['goal'])
            finally:q.close()

    def test_cast_letter_rejects_fake_recipient_or_evidence_and_rolls_back(self):
        self.apply(self.action())
        for target in ('Alice','canon_rydel','canon_wally'):
            a=self.action(1);a['changes']['letter']=dict(to=target,text='A letter without a valid existing recipient.')
            with self.assertRaises(ValueError):cast.compile_actions([a],self.context())
        w=self.action();w['id']='canon_wally';self.apply(w)
        a=self.action(1);a['changes']['letter']=dict(to='canon_wally',text='An actual public letter.');self.apply(a)
        event=next(e for e in self.s.memory.history()['events'] if e['event']=='canonical_letter_delivered')
        # Sender cannot treat its own outgoing letter as received evidence.
        bad=self.action(2);bad['changes']['evidence']=[event['seq']]
        with self.assertRaises(ValueError):cast.compile_actions([bad],self.context())
        bad=deepcopy(w);bad['expected_version']=1;bad['changes']['evidence']=[999999]
        with self.assertRaises(ValueError):cast.compile_actions([bad],self.context())
        before=deepcopy(self.s.module_state);after=deepcopy(before)
        after[cast.KEY]['canon_wally'].update(version=2,evidence=[event['seq']],letter=dict(to='Alice',text='Do not transmit.'))
        with self.assertRaises(ValueError):cast.validate_transition(before,after,[],self.s.db)
        self.assertEqual(self.s.module_state,before)

    def test_character_project_installs_actual_playable_relay_and_informs_another_actor(self):
        from world.canonical_projects import course_for
        from test_field_relays import FieldRelayTests
        from unittest.mock import patch
        w=self.action();w['id']='canon_wally';w['changes']['places'].append('native:PetalburgCity');self.apply(w)
        a=self.action();a['changes']['places'].append('native:PetalburgCity')
        a['changes']['project']=dict(kind='petalburg_relay',title='Rydel Patient Practice',limit=240,mounted=False)
        self.apply(a)
        course=course_for('canon_rydel',a['changes']['project'])
        self.assertEqual(self.s.relays._course(course['id']),course)
        self.assertTrue(any(x['id']==course['id'] for x in self.s.activities.catalog()))
        self.assertEqual(self.s.relays.runs,{})
        event=next(e for e in self.s.memory.history()['events'] if e['event']=='canonical_project_published')
        self.assertEqual(event['outcome'],'immutable_relay_course_installed')
        c=self.peer();b=self.peer('Bob');self.f.connections.update(Alice=c,Bob=b)
        self.assertTrue(any(course['id'] in line for line in cast.guild_command(self.s,c,['rydel','projects'])))
        # Execute actual relay CHAT/STATE authority, including readiness,
        # checkpoints, baton handoff and persistent private finish record.
        runner=FieldRelayTests();runner.s=self.s;runner.a=c;runner.b=b;runner.now=time.monotonic()
        self.s.relays.clock=lambda:runner.now
        with patch('world.server.time.monotonic',side_effect=lambda:runner.now),patch('test_field_relays.COURSE',course):
            run=runner.finish()
        record=self.s.db.execute('SELECT course,team,milliseconds FROM relay_records WHERE run=?',(run['id'],)).fetchone()
        self.assertEqual(record[0],course['id']);self.assertEqual(json.loads(record[1]),['Alice','Bob']);self.assertGreater(record[2],0)
        self.assertEqual(self.f.stats()[0],10)
        self.assertFalse(any(e['event'].startswith('relay_') for e in self.s.memory.history()['events']))
        with tempfile.TemporaryDirectory() as tmp:
            q=IntentQueue(tmp)
            try:
                reactions.configure(q,self.s.inspect(),'canon_wally','Consider real published projects without inferring private race participation.')
                letter=deepcopy(a);letter['expected_version']=1
                letter['changes'].update(evidence=[event['seq']],letter=dict(to='canon_wally',text='I published a patient practice course. You may look at the plan without promising to race.'))
                self.apply(letter)
                self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_projects').fetchone()[0],1)
                self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.fetch)),1)
                turn=q.claim();ctx=self.context();ctx['runtime'].update(kind='character',observed_event=json.loads(turn['result']))
                reaction=reactions.prepare(ctx,self.fetch)
                decision=deepcopy(w);decision['expected_version']=1
                decision['changes'].update(evidence=[reaction['evidence']],goal='Consider the published patient practice plan without committing to a race',dialogue='Rydel published a practice plan. I want to think about it first.')
                reactions.check_response(dict(canonical_actions=[decision],tests='assert True'),reaction)
                self.apply(decision);q.finish(turn['id'],'succeeded',dict(ok=True))
                self.assertEqual(reactions.observe(q,self.s.inspect(),self.fetch),[])
                self.assertEqual(len([e for e in self.s.memory.history()['events'] if e['event']=='canonical_project_published']),1)
            finally:q.close()
        self.s.close();self.f.case.server=self.f.case.open();self.s=self.f.case.server;self.f.server=self.s
        self.assertEqual(self.s.relays._course(course['id']),course)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_projects').fetchone()[0],1)

    def test_project_collision_rolls_back_character_history_and_course_atomically(self):
        from world.canonical_projects import course_for
        a=self.action();a['changes']['places'].append('native:PetalburgCity')
        a['changes']['project']=dict(kind='petalburg_relay',title='Conflicting Practice',limit=240,mounted=False)
        course=course_for('canon_rydel',a['changes']['project'])
        # Existing operator-owned course cannot be silently adopted/overwritten.
        self.s.relays.publish(course)
        history=deepcopy(self.s.memory.history());before=deepcopy(self.s.module_state)
        source=cast.compile_actions([a],self.context());ns={};exec(source,ns)
        candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
        future=Future();future.set_result((candidate,ns['update'](self.s._context(),deepcopy(before))))
        self.s.job=(future,'deploy',None,self.s.interaction_cursor);self.s._poll_mechanics()
        self.assertIn('conflicts',self.s.module_error)
        self.assertEqual(self.s.module_state,before);self.assertEqual(self.s.memory.history(),history)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_projects').fetchone()[0],0)
        self.assertEqual(self.s.relays._course(course['id']),course)
        a['changes']['project']['legs']=[]
        with self.assertRaises(ValueError):cast.compile_actions([a],self.context())

    def test_characters_collaborate_on_real_project_and_publish_actual_runner_guidance(self):
        from world.canonical_projects import course_for
        a=self.action();a['changes']['places'].append('native:PetalburgCity')
        a['changes']['project']=dict(kind='petalburg_relay',title='Shared Practice',limit=240,mounted=False)
        self.apply(a);course=course_for('canon_rydel',a['changes']['project'])
        published=next(e for e in self.s.memory.history()['events'] if e['event']=='canonical_project_published')
        w=self.action();w['id']='canon_wally';w['changes']['places'].append('native:PetalburgCity');self.apply(w)
        c=self.peer();b=self.peer('Bob');self.f.connections.update(Alice=c,Bob=b)
        with tempfile.TemporaryDirectory() as tmp:
            q=IntentQueue(tmp)
            try:
                for identity in ('canon_rydel','canon_wally'):
                    reactions.configure(q,self.s.inspect(),identity,'Consider actual project collaboration, never invented race participation.')
                contribution=deepcopy(w);contribution['expected_version']=1
                contribution['changes'].update(evidence=[published['seq']],contribution=dict(course=course['id'],digest=published['digest'],text='Wait for your partner at the handoff. A calm start is better than a hurried mistake.'))
                self.apply(contribution)
                proposal=next(e for e in self.s.memory.history()['events'] if e['event']=='canonical_contribution_proposed')
                self.assertEqual(proposal['recipient'],'canon_rydel')
                from world.canonical_collaboration import briefing
                self.assertEqual(briefing(self.s,course['id']),[])
                self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.fetch)),1)
                turn=q.claim();self.assertEqual(turn['player'],'canon_rydel')
                ctx=self.context();ctx['runtime'].update(kind='character',observed_event=json.loads(turn['result']))
                reaction=reactions.prepare(ctx,self.fetch)
                decision=deepcopy(a);decision['expected_version']=1
                decision['changes'].update(evidence=[proposal['seq']],goal='Make partner patience part of this practice project',resolve_contribution=dict(seq=proposal['seq'],decision='accept'))
                reactions.check_response(dict(canonical_actions=[decision],tests='assert True'),reaction)
                self.apply(decision);q.finish(turn['id'],'succeeded',dict(ok=True))
                resolved=next(e for e in self.s.memory.history()['events'] if e['event']=='canonical_contribution_resolved')
                self.assertEqual(resolved['outcome'],'activity_guidance_published')
                # Actual start/join shows accepted guidance to participants only.
                bob_before=deepcopy(b['chat_history'])
                self.f.command('relay start '+course['id'])
                run=self.s.relays._current('Alice')
                self.assertTrue(any('calm start' in line for line in run['cast_briefing']))
                self.assertEqual(b['chat_history'],bob_before)
                self.f.command('relay join '+run['id'],trainer='Bob')
                self.assertTrue(any('calm start' in bytes.fromhex(m[3]).decode() for m in b['chat_history']))
                self.assertEqual(run['phase'],'lobby');self.assertEqual(self.f.stats()[0],10)
                self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.fetch)),1)
                turn=q.claim();self.assertEqual(turn['player'],'canon_wally')
                ctx=self.context();ctx['runtime'].update(kind='character',observed_event=json.loads(turn['result']))
                reaction=reactions.prepare(ctx,self.fetch)
                next_goal=deepcopy(w);next_goal['expected_version']=2
                next_goal['changes'].update(evidence=[resolved['seq']],goal='Keep helping others practice patiently after Rydel adopted my guidance',dialogue='Rydel adopted my advice. I want to keep helping new partners.')
                reactions.check_response(dict(canonical_actions=[next_goal],tests='assert True'),reaction)
                self.apply(next_goal);q.finish(turn['id'],'succeeded',dict(ok=True))
                self.assertEqual(reactions.observe(q,self.s.inspect(),self.fetch),[])
                self.assertEqual(self.s.db.execute('SELECT status FROM canonical_contributions').fetchall(),[('accept',)])
                self.s.close();self.f.case.server=self.f.case.open();self.s=self.f.case.server;self.f.server=self.s
                self.assertTrue(any('calm start' in line for line in briefing(self.s,course['id'])))
                self.assertIn('helping',self.s.module_state[cast.KEY]['canon_wally']['goal'])
            finally:q.close()

    def test_project_contribution_needs_exact_publication_and_owner_resolution(self):
        a=self.action();a['changes']['places'].append('native:PetalburgCity')
        a['changes']['project']=dict(kind='petalburg_relay',title='Public Practice',limit=240,mounted=False);self.apply(a)
        published=next(e for e in self.s.memory.history()['events'] if e['event']=='canonical_project_published')
        w=self.action();w['id']='canon_wally';w['changes']['places'].append('native:PetalburgCity');self.apply(w)
        bad=deepcopy(w);bad['expected_version']=1
        bad['changes']['contribution']=dict(course=published['course'],digest=published['digest'],text='Patient advice.')
        with self.assertRaises(ValueError):cast.compile_actions([bad],self.context())
        bad['changes']['evidence']=[published['seq']];bad['changes']['contribution']['digest']='0'*64
        with self.assertRaises(ValueError):cast.compile_actions([bad],self.context())
        bad['changes']['contribution']['digest']=published['digest'];self.apply(bad)
        proposal=next(e for e in self.s.memory.history()['events'] if e['event']=='canonical_contribution_proposed')
        self_resolve=deepcopy(w);self_resolve['expected_version']=2
        self_resolve['changes'].update(evidence=[proposal['seq']],resolve_contribution=dict(seq=proposal['seq'],decision='accept'))
        with self.assertRaises(ValueError):cast.compile_actions([self_resolve],self.context())
        decline=deepcopy(a);decline['expected_version']=1
        decline['changes'].update(evidence=[proposal['seq']],resolve_contribution=dict(seq=proposal['seq'],decision='decline'));self.apply(decline)
        from world.canonical_collaboration import briefing
        self.assertEqual(briefing(self.s,published['course']),[])
        self.assertEqual(self.s.db.execute('SELECT status FROM canonical_contributions').fetchall(),[('decline',)])

    def test_retained_intention_initiates_real_action_without_new_player_event(self):
        w=self.action();w['id']='canon_wally';self.apply(w)
        a=self.action();a['changes']['intentions']=[dict(id='ask_wally',kind='letter',target='canon_wally',reason='Ask about his own practice priorities before making plans.')]
        self.apply(a);boundary=self.s.memory.history()['through']
        with tempfile.TemporaryDirectory() as tmp:
            q=IntentQueue(tmp)
            try:
                reactions.configure(q,self.s.inspect(),'canon_rydel','Pursue retained intentions within supported affordances.')
                self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.fetch)),1)
                turn=q.claim();packet=json.loads(turn['result'])
                self.assertEqual(packet['intention']['id'],'ask_wally')
                self.assertEqual(self.s.memory.history()['through'],boundary)
                ctx=self.context();ctx['runtime'].update(kind='character',observed_event=packet)
                reaction=reactions.prepare(ctx,self.fetch)
                done=deepcopy(a);done['expected_version']=1
                done['changes'].update(intentions=[],fulfill='ask_wally',letter=dict(to='canon_wally',text='Wally, what matters to you when you choose how to practice?'))
                reactions.check_response(dict(canonical_actions=[done],tests='assert True'),reaction)
                self.apply(done);q.finish(turn['id'],'succeeded',dict(ok=True))
                event=next(e for e in self.s.memory.history()['events'] if e['event']=='canonical_intention_fulfilled')
                receipt=next(e for e in self.s.memory.history()['events'] if e['seq']==event['action_receipt'])
                self.assertEqual(receipt['event'],'canonical_letter_delivered')
                self.assertEqual(receipt['recipient'],'canon_wally')
                self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.fetch)),1)
                reflection=q.claim();ctx=self.context();ctx['runtime'].update(kind='character',observed_event=json.loads(reflection['result']))
                selected=reactions.prepare(ctx,self.fetch)
                changed=self.action(2,'I have written to Wally. I will give him room to think.')
                changed['changes'].update(evidence=[event['seq']],goal='Wait for Wally rather than assume what he wants')
                reactions.check_response(dict(canonical_actions=[changed],tests='assert True'),selected)
                self.apply(changed);q.finish(reflection['id'],'succeeded',dict(ok=True))
                self.assertEqual(reactions.observe(q,self.s.inspect(),self.fetch),[])
                self.assertEqual(self.f.stats()[0],10)
                q.close();q=IntentQueue(tmp)
                self.assertEqual(reactions.observe(q,self.s.inspect(),self.fetch),[])
                self.s.close();self.f.case.server=self.f.case.open();self.s=self.f.case.server;self.f.server=self.s
                self.assertEqual(self.s.db.execute('SELECT intention FROM canonical_intent_receipts').fetchall(),[('ask_wally',)])
            finally:q.close()

    def test_intention_cannot_invent_completion_or_retry_interrupted_work(self):
        w=self.action();w['id']='canon_wally';self.apply(w)
        a=self.action();a['changes']['intentions']=[dict(id='ask_once',kind='letter',target='canon_wally',reason='Make one considered inquiry.')];self.apply(a)
        fake=deepcopy(a);fake['expected_version']=1;fake['changes'].update(intentions=[],fulfill='ask_once')
        with self.assertRaises(ValueError):cast.compile_actions([fake],self.context())
        fake['changes']['letter']=dict(to='canon_rydel',text='Wrong target.')
        with self.assertRaises(ValueError):cast.compile_actions([fake],self.context())
        with tempfile.TemporaryDirectory() as tmp:
            q=IntentQueue(tmp)
            try:
                reactions.configure(q,self.s.inspect(),'canon_rydel','Attempt retained work once.')
                self.assertEqual(reactions.observe(q,self.s.inspect(),self.fetch,enqueue=False),[])
                self.assertEqual(len(reactions.observe(q,self.s.inspect(),self.fetch)),1)
                turn=q.claim();packet=json.loads(turn['result'])
                unrelated=self.action(1)
                with self.assertRaises(ValueError):reactions.check_response(dict(canonical_actions=[unrelated],tests='assert True'),packet)
                q.close();q=IntentQueue(tmp) # running author is interrupted, not replayed
                self.assertEqual(reactions.observe(q,self.s.inspect(),self.fetch),[])
                self.assertEqual(self.s.module_state[cast.KEY]['canon_rydel']['intentions'][0]['id'],'ask_once')
                self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_intent_receipts').fetchone()[0],0)
                self.assertEqual(q.db.execute('SELECT count(*) FROM canonical_intent_attempts').fetchone()[0],1)
            finally:q.close()

    def test_private_encounter_memory_requires_display_receipt_and_is_save_specific(self):
        self.apply(self.action());a=self.peer();b=self.peer('Bob');self.f.connections.update(Alice=a,Bob=b)
        self.query(a)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_encounters').fetchone()[0],0)
        public=deepcopy(self.s.inspect());history=deepcopy(self.s.memory.history());bob_chat=deepcopy(b['chat_history'])
        self.f.command('cast rydel remember on')
        first=self.query(a);digest=first.split()[-2]
        self.assertNotIn('Good to see you again',bytes.fromhex(first.split()[-1]).decode())
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_encounters').fetchone()[0],0)
        def seen(peer,run,token):
            peer['out'].clear();self.s._line(peer,f'CORE {run} SEEN rydel {token} 50'.encode());return peer['out'].decode()
        self.assertIn('REFUSED',seen(a,'a'*32,'0'*64))
        self.assertIn('OK',seen(a,'a'*32,digest))
        self.assertIn('REFUSED',seen(a,'a'*32,digest))
        self.assertEqual(self.s.db.execute('SELECT talks FROM canonical_encounters').fetchall(),[(1,)])
        second=self.query(a)
        self.assertIn('Good to see you again',bytes.fromhex(second.split()[-1]).decode())
        self.assertNotEqual(second.split()[-2],digest)
        self.assertNotIn('Good to see you again',bytes.fromhex(self.query(b).split()[-1]).decode())
        other_run=cast.response(self.s,a,'b'*32,'rydel')
        self.assertNotIn('Good to see you again',other_run['briefing'])
        self.assertIn('REFUSED',seen(a,'a'*32,other_run['digest']))
        self.assertIn('OK',seen(a,'b'*32,other_run['digest']))
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_encounters').fetchone()[0],2)
        self.assertEqual(self.s.inspect(),public);self.assertEqual(self.s.memory.history(),history)
        self.assertEqual(b['chat_history'],bob_chat)
        self.s.close();self.f.case.server=self.f.case.open();self.s=self.f.case.server;self.f.server=self.s
        a=self.peer();self.f.connections['Alice']=a
        self.assertIn('Good to see you again',bytes.fromhex(self.query(a).split()[-1]).decode())
        self.assertTrue(any('1 acknowledged' in line for line in cast.guild_command(self.s,a,['rydel','memory'])))
        self.f.command('cast rydel remember off')
        self.assertNotIn('Good to see you again',bytes.fromhex(self.query(a).split()[-1]).decode())
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_encounters').fetchone()[0],2)
        a['state'][6]=0;self.f.command('cast rydel forget')
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_encounters').fetchone()[0],0)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_memory_optin').fetchone()[0],0)

    def test_encounter_receipt_expires_and_cannot_cross_connection_actor_or_location(self):
        from world.canonical_memory import acknowledge
        self.apply(self.action());a=self.peer();cast.guild_command(self.s,a,['rydel','remember','on'])
        response=cast.response(self.s,a,'a'*32,'rydel')
        a['cast_seen_pending']['expires']=0
        with self.assertRaises(ValueError):acknowledge(self.s,a,'a'*32,'canon_rydel',response['digest'])
        response=cast.response(self.s,a,'a'*32,'rydel');a['state'][:2]=[0,9]
        with self.assertRaises(ValueError):acknowledge(self.s,a,'a'*32,'canon_rydel',response['digest'])
        fresh=self.peer();cast.guild_command(self.s,fresh,['rydel','remember','on'])
        fresh['out'].clear();self.s._line(fresh,('CORE '+'a'*32+' SEEN rydel '+response['digest']+' 60').encode())
        self.assertIn(b'REFUSED',fresh['out'])
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_encounters').fetchone()[0],0)

    def prepare_private_reflection(self):
        from world.canonical_memory import acknowledge
        self.apply(self.action());peer=self.peer();self.f.connections['Alice']=peer
        cast.guild_command(self.s,peer,['rydel','remember','on'])
        reply=cast.response(self.s,peer,'a'*32,'rydel')
        acknowledge(self.s,peer,'a'*32,'canon_rydel',reply['digest'])
        return peer

    def test_consented_private_agent_reflection_uses_only_selected_summary_and_native_reply(self):
        from world.private_cast_worker import step
        peer=self.prepare_private_reflection();bob=self.peer('Bob')
        history=deepcopy(self.s.memory.history());inspection=deepcopy(self.s.inspect())
        def admin(body):
            conn=dict(sock=object(),out=bytearray(),closing=False)
            self.s._admin_line(conn,json.dumps(body).encode())
            return json.loads(conn['out'])
        self.assertIsNone(admin(dict(command='private_cast_claim'))['request'])
        preview=cast.guild_command(self.s,peer,['rydel','reflect'])
        self.assertTrue(any('OpenAI' in line for line in preview))
        self.assertTrue(any('last shown reply' in line for line in preview))
        self.assertTrue(all(len(line)<=113 for line in preview))
        self.assertIsNone(admin(dict(command='private_cast_claim'))['request'])
        nonce=peer['cast_reflection_preview']['nonce']
        cast.guild_command(self.s,peer,['rydel','reflect','confirm',nonce])
        prompts=[]
        def author(text):
            prompts.append(text)
            return dict(reply='I can offer ideas without choosing your pace for you.',interpretation='Rydel considers leaving the pace open rather than assuming agreement.')
        result=step('unused','gpt-6-luna',request=admin,author=author)
        self.assertEqual(result,dict(ok=True,status='ready'))
        self.assertEqual(len(prompts),1)
        self.assertNotIn('Alice',prompts[0]);self.assertNotIn('Bob',prompts[0]);self.assertNotIn('a'*32,prompts[0])
        self.assertIn('last_shown_reply',prompts[0])
        self.assertIn('without choosing your pace',cast.response(self.s,peer,'a'*32,'rydel')['briefing'])
        self.assertNotIn('without choosing',cast.response(self.s,bob,'b'*32,'rydel')['briefing'])
        self.assertNotIn('without choosing',cast.response(self.s,peer,'c'*32,'rydel')['briefing'])
        self.assertEqual(self.s.inspect(),inspection);self.assertEqual(self.s.memory.history(),history)
        self.assertEqual(step('unused','gpt-6-luna',request=admin,author=author)['status'],'idle')
        self.assertTrue(any('leaving the pace' in line for line in cast.guild_command(self.s,peer,['rydel','reflection'])))
        self.s.close();self.f.case.server=self.f.case.open();self.s=self.f.case.server;self.f.server=self.s
        peer=self.peer()
        self.assertIn('without choosing your pace',cast.response(self.s,peer,'a'*32,'rydel')['briefing'])

    def test_private_reflection_withdrawal_staleness_and_world_edit_outputs_fail_closed(self):
        from world.canonical_reflection import claim,finish
        from world.guilds import GuildError
        peer=self.prepare_private_reflection()
        def consent():
            cast.guild_command(self.s,peer,['rydel','reflect'])
            nonce=peer['cast_reflection_preview']['nonce']
            cast.guild_command(self.s,peer,['rydel','reflect','confirm',nonce])
        cast.guild_command(self.s,peer,['rydel','reflect'])
        with self.assertRaises(GuildError):cast.guild_command(self.s,peer,['rydel','reflect','confirm','bad'])
        consent();work=claim(self.s)['request']
        with self.assertRaises(ValueError):finish(self.s,work['id'],work['lease'],dict(source='change world',tests='assert True'))
        cast.guild_command(self.s,peer,['rydel','forget'])
        with self.assertRaises(ValueError):finish(self.s,work['id'],work['lease'],dict(reply='Late answer.',interpretation='Too late.'))
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_reflections').fetchone()[0],0)
        from world.canonical_memory import acknowledge
        cast.guild_command(self.s,peer,['rydel','remember','on'])
        reply=cast.response(self.s,peer,'a'*32,'rydel');acknowledge(self.s,peer,'a'*32,'canon_rydel',reply['digest'])
        consent();work=claim(self.s)['request']
        # A new displayed conversation invalidates the exact consented snapshot.
        reply=cast.response(self.s,peer,'a'*32,'rydel');acknowledge(self.s,peer,'a'*32,'canon_rydel',reply['digest'])
        self.assertFalse(finish(self.s,work['id'],work['lease'],dict(reply='Stale reply.',interpretation='Stale interpretation.'))['ok'])
        self.assertNotIn('Stale reply',cast.response(self.s,peer,'a'*32,'rydel')['briefing'])
        self.assertIsNone(claim(self.s)['request'])

    def test_private_adapter_schema_cannot_return_world_code_or_tool_activity(self):
        from world.runtime_gm import decode_codex
        def wire(value):return json.dumps(dict(type='item.completed',item=dict(type='agent_message',text=json.dumps(value))))+'\n'+json.dumps(dict(type='turn.completed'))
        result=dict(reply='We can consider that together.',interpretation='Rydel leaves the choice open.')
        self.assertEqual(decode_codex(wire(result),private_cast=True),result)
        with self.assertRaises(ValueError):decode_codex(wire(result))
        with self.assertRaises(ValueError):decode_codex(wire(dict(source='anything',tests='assert True')),private_cast=True)
        with self.assertRaises(ValueError):decode_codex(json.dumps(dict(type='item.completed',item=dict(type='command_execution')))+'\n'+wire(result),private_cast=True)

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
        cast.guild_command(self.s,peer,['rydel','remember','on'])
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
assert(strstr(sent,"SEEN rydel"));printf("%s",sent);
hidden=true;assert(!WorldCoreStory_BeforeScript(hook));assert(progress==0);
return 0;}
'''.replace('WORLD',json.dumps(world)).replace('PACKET',json.dumps(packet))
        with tempfile.TemporaryDirectory() as tmp:
            c=Path(tmp)/'paired.c';c.write_text(fixture+source+checks);exe=Path(tmp)/'paired'
            subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],check=True)
            emitted=subprocess.run([str(exe)],check=True,capture_output=True,text=True).stdout
            self.s._line(peer,emitted.strip().encode())
            self.assertEqual(self.s.db.execute('SELECT talks FROM canonical_encounters').fetchone()[0],1)
            self.assertIn('Good to see you again',bytes.fromhex(self.query(peer).split()[-1]).decode())
