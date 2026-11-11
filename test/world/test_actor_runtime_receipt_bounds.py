"""Real SQLite/runtime regressions for ACTOR-RUNTIME-001; no adapter mocks."""
import json
import sqlite3
from types import SimpleNamespace
import unittest

from world import actor_runtime as runtime
from world.actor_knowledge import recall, share
from world.characters import records
from world.world_memory import WorldMemory


class ReceiptBoundsTests(unittest.TestCase):
    def setUp(self):
        db = sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        db.execute('CREATE TABLE events(seq INTEGER PRIMARY KEY,kind TEXT,data TEXT)')
        self.s = SimpleNamespace(db=db, memory=WorldMemory(db), module_state={},
                                 objects=[], job=None, deployment=None, revision=0)
        runtime.install(db)

    def actor(self, identity, steps):
        plan = dict(id='recall', purpose='Recall a received report.', steps=steps)
        row = dict(version=1, name=identity, role='guide', goals=[], relationships={},
                   team=[dict(species=278, level=18)], status='active', object_id=identity,
                   evidence=[], reason='Investigate public reports.', plan=plan)
        self.s.module_state.setdefault('world_characters', {})[identity] = row
        records(self.s.module_state)

    def step(self, delivery, identity='remember', after=None):
        return dict(id=identity, tool='world.recall_report', args=dict(delivery=delivery),
                    after=after or [])

    def report(self, actor, delivery=1, x=2):
        snapshot = dict(revision='dated', x=x, y=3)
        self.s.db.execute('INSERT INTO actor_knowledge VALUES(?,?,?,?,?)',
                          (actor, 'sender', delivery, delivery, json.dumps(snapshot)))
        self.s.db.commit()

    def assert_blocked_once_then_healthy(self, now):
        result = runtime.tick(self.s, now=now)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['actor'], 'bad')
        # A later actor must still run, and the malformed plan must never retry.
        self.report('healthy')
        self.actor('healthy', [self.step(1)])
        healthy = runtime.tick(self.s, now=now + 6)
        self.assertEqual((healthy['actor'], healthy['status']), ('healthy', 'succeeded'))
        self.assertIsNone(runtime.tick(self.s, now=now + 12))
        rows = self.s.db.execute("SELECT status,result FROM actor_tool_receipts WHERE actor='bad' AND step='remember'").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], 'blocked')
        events = [json.loads(raw) for raw, in self.s.db.execute("SELECT data FROM events WHERE kind='world_memory'")]
        self.assertEqual(sum(e['event'] == 'actor_tool_result' and e['character_id'] == 'bad' and e['status'] == 'blocked' for e in events), 1)
        self.assertIsNone(self.s.actor_tool_execution)

    def test_oversized_direct_delivery_durably_blocks_without_stopping_next_actor(self):
        self.actor('bad', [self.step(10**30)])
        self.assert_blocked_once_then_healthy(10)

    def test_share_rejects_out_of_range_observation_before_participant_lookup(self):
        for observation in (-1, 0, 2**63, 10**30, True):
            with self.subTest(observation=observation):
                with self.assertRaisesRegex(ValueError, 'positive signed 64-bit'):
                    share(self.s, 'bad', {}, dict(target='other', expected_version=1,
                                                  observation=observation))

    def test_recall_receipt_bounds_and_valid_maximum(self):
        for delivery in (-1, 0, 2**63, 10**30, True):
            with self.subTest(delivery=delivery):
                with self.assertRaisesRegex(ValueError, 'positive signed 64-bit'):
                    recall(self.s, 'healthy', {}, dict(delivery=delivery))
        self.report('healthy', delivery=2**63-1)
        self.assertEqual(recall(self.s, 'healthy', {}, dict(delivery=2**63-1))['delivery'], 2**63-1)

    def test_result_reference_receipt_bounds_durably_block(self):
        for value in (-1, 0, 2**63, 10**30):
            with self.subTest(value=value):
                self.setUp()
                self.report('bad', x=value)
                self.actor('bad', [self.step(1, identity='source'),
                                   self.step(dict(result='source', key='report_x'), after=['source'])])
                self.assertEqual(runtime.tick(self.s, now=10)['status'], 'succeeded')
                self.assert_blocked_once_then_healthy(16)
                reason = json.loads(self.s.db.execute("SELECT result FROM actor_tool_receipts WHERE actor='bad' AND step='remember'").fetchone()[0])['reason']
                self.assertIn('positive signed 64-bit', reason)

    def test_sqlite_overflow_at_execution_boundary_durably_blocks(self):
        step = dict(id='remember', tool='world.reply_player',
                    args=dict(speech=10**30, text='Hello.'), after=[])
        self.actor('bad', [step])
        self.assert_blocked_once_then_healthy(10)


if __name__ == '__main__':
    unittest.main()
