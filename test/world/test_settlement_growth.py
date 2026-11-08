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
