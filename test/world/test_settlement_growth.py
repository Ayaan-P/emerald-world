"""Real accepted steward completion drives the existing opt-in GM queue once."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from world.runtime_gm import RuntimeGM, IntentQueue, MODEL
from world.settlement_growth import candidates
import test_settlement_plans as settlement
from test_settlement_plans import plan, FixtureRuntime
from test_author_cave import wire
from world.author_settlement import author_settlement


class Growth(unittest.TestCase):
    def setUp(self):
        self.f=settlement.SettlementFlow();self.f.setUp();self.addCleanup(self.f.doCleanups)

    def test_wildlife_destination_retains_population_during_construction(self):
        from world.route_encounters import encode
        server=self.f.server
        blob=server.db.execute('SELECT template FROM generated_cave WHERE singleton=1').fetchone()[0]
        wildlife=encode(blob,dict(rate=12,wildlife=[dict(species='ZUBAT',level=10)]*12))
        server._replace_cave(wildlife)
        revision=server.shared_cave.identity
        page=candidates(server,0)
        self.assertEqual(page['candidates'],[])
        self.assertIsNone(page['blocked'])
        result=self.f.transport('',self.f.request())
        self.assertTrue(result['ok'],result)
        self.assertNotEqual(server.shared_cave.identity,revision)
        self.assertEqual(server.shared_cave.wildlife,wildlife[8:45])
        self.assertEqual(server.shared_cave.version,17)

    def test_player_completion_queues_real_author_route_and_persists_exactly_once_growth(self):
        def admin(_socket,request,*args,**kwargs):return self.f.transport('',request)
        root=self.f.server.root
        with RuntimeGM(root,root/'transport'/'world.sock',model=MODEL,observe_events=False,
                       min_author_interval=0,settlement_growth_theme='Extend the surveyed frontier') as worker:
            with patch('world.gm.admin_request',side_effect=admin):
                self.assertIsNone(worker.step())  # enable before the player acts
                self.f.test_real_outcome_becomes_inhabited_outpost_then_explicit_offer_completion_changes_dialogue()
                self.f.server.runtime=FixtureRuntime()
                page=candidates(self.f.server,worker.queue.settlement_cursor(self.f.server.memory.context(self.f.server)['active_area']['place_id'])['cursor'])
                self.assertEqual(len(page['candidates']),1)
                seq=page['candidates'][0]['seq'];self.assertEqual(page['candidates'][0]['character_id'],'outpost_steward')
                fresh=plan();fresh['label']='Survey Ridge';fresh['construction'].update(x=40,y=45)
                fresh['resident'].update(id='ridge_steward',name='Ridge Steward')
                fresh['resident']['offer']['id']='ridge_survey'
                with patch('world.author_settlement.admin_request',side_effect=admin),patch('world.author_cave.request_validated',side_effect=lambda p,v,**kw:v(wire(fresh))) as provider:
                    result=worker.step();self.assertEqual(result['status'],'succeeded',result)
                    self.assertEqual(provider.call_count,1)
                    self.assertEqual(worker._previous_source(self.f.server.inspect()),self.f.server.candidate.source)
                    new=self.f.server.shared_cave.identity
                    self.assertTrue(self.f.server.shared_cave.walkable(44,48))
                    self.assertEqual({o['id'] for o in self.f.server.objects},{'field_researcher','outpost_steward','ridge_steward'})
                    self.assertIsNone(worker.step());self.assertEqual(provider.call_count,1)
                receipt=self.f.server.db.execute('SELECT resident_id,revision FROM settlement_foundings WHERE outcome_seq=?',(seq,)).fetchone()
                self.assertEqual(receipt,('ridge_steward',new))
                replay=self.f.request();replay['outcome_seq']=seq;replay['plan']=fresh
                replay['plan']['resident']['id']='duplicate_guide';replay['plan']['construction'].update(x=60,y=60)
                self.assertIn('already founded',admin('',replay)['error'])
        with RuntimeGM(root,root/'transport'/'world.sock',model=MODEL,observe_events=False,
                       min_author_interval=0,settlement_growth_theme='Extend the surveyed frontier') as worker:
            with patch('world.gm.admin_request',side_effect=admin),patch('world.author_settlement.author_settlement') as author:
                self.assertIsNone(worker.step());author.assert_not_called()

    def test_owner_recovery_before_provider_before_commit_and_after_lost_response(self):
        from world.settlement_growth import reconcile
        root=self.f.server.root
        memory=self.f.server.memory.context(self.f.server)
        identity=dict(world_id=memory['world_id'],place_id=memory['active_area']['place_id'],
                      revision=memory['active_area']['revision'],outcome_seq=self.f.outcome['seq'])
        def authority(_socket,request,**kwargs):return reconcile(self.f.server,request)
        with RuntimeGM(root,root/'transport'/'world.sock',model=MODEL) as worker:
            q=worker.queue
            for stage in ('inspection','provider','commit'):
                identifier='recovery-'+stage
                with q.db:
                    q.db.execute("INSERT INTO requests(id,player,text,kind,status,created,result) VALUES(?,?,?,?,?,?,?)",
                                 (identifier,'','Grow','settlement','queued',0,json.dumps(identity)))
                item=q.claim();self.assertEqual(item['id'],identifier)
                q.settlement_progress(identifier,stage=stage,outcome_state='uncertain' if stage=='commit' else 'not_committed')
                q.finish(identifier,'failed',dict(ok=False,error='TimeoutError'))
                saved=next(r['result'] for r in q.status()['requests'] if r['id']==identifier)
                self.assertEqual(saved['stage'],stage);self.assertEqual(saved['outcome_seq'],identity['outcome_seq'])
                with patch('world.client.admin_request',side_effect=authority):
                    if stage=='commit':
                        # Simulate response loss after actual atomic founding.
                        self.f.server.runtime=FixtureRuntime()
                        response=self.f.transport('',self.f.request())
                        self.assertTrue(response['ok'],response)
                        result=worker.retry_settlement(identifier)
                        self.assertEqual(result['status'],'succeeded')
                        self.assertEqual(result['reconciliation']['state'],'committed')
                        self.assertIsNone(q.claim())
                    else:
                        result=worker.retry_settlement(identifier)
                        self.assertEqual(result['status'],'queued')
                        self.assertEqual(q.claim()['id'],identifier)
                        q.finish(identifier,'succeeded',dict(ok=True))

    def test_recovery_defers_pending_and_rejects_wrong_revision_or_world(self):
        from world.settlement_growth import reconcile
        memory=self.f.server.memory.context(self.f.server)
        request=dict(command='settlement_recovery',world_id=memory['world_id'],
                     place_id=memory['active_area']['place_id'],revision=memory['active_area']['revision'],
                     outcome_seq=self.f.outcome['seq'])
        self.f.server.job=object()
        self.assertEqual(reconcile(self.f.server,request)['state'],'uncertain')
        self.f.server.job=None
        for field in ('world_id','revision','place_id'):
            with self.assertRaises(ValueError):reconcile(self.f.server,dict(request,**{field:'wrong'}))

    def test_interruption_preserves_identity_and_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            q=IntentQueue(tmp);self.addCleanup(q.close)
            page=dict(ok=True,world_id='w',place_id='p',revision='r',through=1,cursor=1,candidates=[],blocked=None)
            q.observe_settlements(page,'Grow')
            q.observe_settlements(dict(page,through=2,cursor=2,candidates=[dict(seq=2)]),'Grow')
            item=q.claim();q.settlement_progress(item['id'],stage='commit')
            q.recover();result=q.status()['requests'][0]['result']
            self.assertEqual((result['world_id'],result['place_id'],result['outcome_seq'],result['stage']),('w','p',2,'commit'))
            self.assertEqual(result['outcome_state'],'uncertain');self.assertIsNone(q.claim())

    def test_unrelated_guild_completion_does_not_trigger_growth(self):
        page=candidates(self.f.server)
        self.assertEqual(page['candidates'],[])  # founder outcome has no settlement steward
        self.f.test_real_outcome_becomes_inhabited_outpost_then_explicit_offer_completion_changes_dialogue()
        seq=candidates(self.f.server)['candidates'][0]['seq']
        self.f.server.activate_generated_area(self.f.f.old)
        self.assertEqual(candidates(self.f.server)['candidates'][0]['seq'],seq)
        self.assertGreater(seq,0)

    def test_disabled_queue_and_failed_attempt_never_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            q=IntentQueue(tmp);self.addCleanup(q.close)
            base=dict(ok=True,world_id='world',place_id='area:one',through=10,cursor=10,candidates=[],blocked=None)
            q.observe_settlements(base,'Grow')
            page=dict(base,through=11,cursor=11,candidates=[dict(seq=11,character_id='steward')])
            q.observe_settlements(page,'Grow')
            self.assertIsNone(q.claim(allow_settlements=False))
            item=q.claim();self.assertEqual(item['kind'],'settlement')
            q.finish(item['id'],'failed',dict(ok=False,error='provider blocked'))
            q.observe_settlements(dict(page,candidates=[]),'Grow')
            self.assertIsNone(q.claim());self.assertEqual(len(q.status()['requests']),1)
            with self.assertRaises(ValueError):q.observe_settlements(dict(page,world_id='other'),'Grow')

    def test_place_cursors_preserve_archived_outcomes_across_switch_and_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            q=IntentQueue(tmp)
            def page(place,through,events):
                return dict(ok=True,world_id='world',place_id=place,through=through,cursor=through,
                            candidates=[dict(seq=seq,character_id='steward') for seq in events],blocked=None)
            q.observe_settlements(page('A',10,[]),'Grow')
            q.observe_settlements(page('B',30,[20]),'Grow')
            self.assertEqual(q.settlement_cursor('A')['cursor'],10)
            q.close();q=IntentQueue(tmp);self.addCleanup(q.close)
            q.observe_settlements(page('A',40,[15]),'Grow')
            self.assertEqual({r['result']['outcome_seq'] for r in q.status()['requests']},{15,20})
            self.assertEqual(q.settlement_cursor('B')['cursor'],30)
            item=q.claim(settlement_place='A');self.assertEqual(json.loads(item['result'])['place_id'],'A')
            q.finish(item['id'],'succeeded',dict(ok=True))
            self.assertIsNone(q.claim(settlement_place='A'))
            q.observe_settlements(page('B',40,[]),'Grow')
            self.assertEqual(len(q.status()['requests']),2)

    def test_growth_read_rejects_swapped_place_before_acknowledging_cursor(self):
        with self.assertRaisesRegex(ValueError,'place changed'):
            candidates(self.f.server,expected_world_id=self.f.server.memory.world_id,expected_place_id='other')

    def test_wrong_queued_place_fails_before_provider(self):
        with patch('world.author_settlement.admin_request',side_effect=self.f.transport),patch('world.author_cave.request_validated') as provider:
            with self.assertRaisesRegex(ValueError,'another world or place'):
                author_settlement('admin','Grow',self.f.outcome['seq'],apply=True,expected_place_id='area:other')
            provider.assert_not_called()

    def test_failed_founding_does_not_consume_outcome(self):
        self.f.test_new_resident_insert_failure_rolls_back_everything()
        self.assertEqual(self.f.server.db.execute('SELECT count(*) FROM settlement_foundings').fetchone()[0],0)


if __name__=='__main__':unittest.main()
