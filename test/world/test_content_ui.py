"""Local launcher content previews exercise the existing durable authorities."""
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import test_frontier_outposts as frontier
import test_settlement_plans as settlements
from test_route_landscape import plan as route_plan
from world.web_launcher import LauncherBridge
from world.session import SessionError


class ContentUI(unittest.TestCase):
    def setUp(self):
        self.f = frontier.FrontierAuthority(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.s = self.f.server
        session = SimpleNamespace(root=__import__('pathlib').Path('/unused'), server=self.s, state=SimpleNamespace(name='local'), engine='expansion-native')
        self.bridge = LauncherBridge(session, '/unused', engine='expansion-native')
        self.bridge.local_expeditions = lambda: [dict(key='local')]

    def call(self, action, **payload):
        return self.bridge.action('content_' + action, dict(world='local', **payload))

    def test_review_then_apply_exact_outpost_without_replacing_old_floor_or_residents(self):
        before = self.s.shared_cave
        read = self.call('read')
        self.assertEqual(read['identity'], before.identity)
        draft = self.call('preview', kind='outpost', label='My courtyard', plan=frontier.plan(), outcome_seq=None)
        self.assertEqual(self.s.shared_cave.identity, before.identity)
        self.assertGreater(draft['report']['added_walkable_tiles'], 0)
        with self.assertRaises(SessionError): self.call('apply', token=draft['token'], confirmed=False)
        result = self.call('apply', token=draft['token'], confirmed=True)
        self.assertTrue(result['saved'])
        self.assertNotEqual(result['identity'], before.identity)
        for y, row in enumerate(before._rows):
            for x, cell in enumerate(row):
                if cell == ord('.'): self.assertTrue(self.s.shared_cave.walkable(x, y))
        with self.assertRaises(SessionError): self.call('apply', token=draft['token'], confirmed=True)

    def test_stale_review_and_foreign_world_are_refused(self):
        draft = self.call('preview', kind='outpost', label='Courtyard', plan=frontier.plan(), outcome_seq=None)
        self.s.memory.append('area_named',dict(place_id=self.s.memory.place(self.s.shared_cave.identity),revision=self.s.shared_cave.identity,before='A',after='B')); self.s.db.commit()
        with self.assertRaisesRegex(SessionError, 'changed'): self.call('apply', token=draft['token'], confirmed=True)
        with self.assertRaises(SessionError): self.bridge.action('content_read',dict(world='hosted-elsewhere'))

    def test_route_cannot_replace_existing_geography(self):
        with self.assertRaisesRegex(SessionError, 'existing|archived'): self.call('preview', kind='survey', label='Route', plan=route_plan(), outcome_seq=None)
        self.assertEqual(self.s.shared_cave.identity, self.f.old)

    def test_existing_exact_route_registers_without_publishing_private_history(self):
        from world.route_landscape import compile_plan
        blob, report = compile_plan(route_plan()); self.s._replace_cave(blob, label='My route')
        history = self.s.memory.history()
        draft = self.call('preview', kind='survey', label='My route', plan=route_plan(), outcome_seq=None)
        result = self.call('apply', token=draft['token'], confirmed=True)
        self.assertTrue(result['saved']); self.assertEqual(result['identity'], report['revision'])
        self.assertEqual(self.s.memory.history(), history)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM survey_visits').fetchone()[0], 0)

    def test_complete_field_story_preview_install_and_idempotent_reinstall(self):
        from world.field_story_bundle import curated
        old=self.s.shared_cave.identity
        history=self.s.memory.history()
        draft=self.call('preview',kind='field_story',label='Signal',plan={},outcome_seq=None)
        self.assertEqual(draft['report']['stages'],2)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM mystery_packs').fetchone()[0],0)
        with self.assertRaises(SessionError):self.call('apply',token=draft['token'],confirmed=False)
        result=self.call('apply',token=draft['token'],confirmed=True)
        self.assertTrue(result['field_story']['installed'])
        self.assertEqual(self.s.shared_cave.identity,old)
        self.assertEqual(self.s.memory.history(),history)
        self.s.mysteries.command('Scout',['start','signal_v2'])
        run=self.s.mysteries._current('Scout')
        draft=self.call('preview',kind='field_story',label='Signal',plan={},outcome_seq=None)
        self.call('apply',token=draft['token'],confirmed=True)
        self.assertEqual(self.s.mysteries._current('Scout'),run)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_packs').fetchone()[0],1)

    def test_field_story_is_atomic_and_conflicts_preserve_both_parts(self):
        import sqlite3
        from world.field_story_bundle import curated, install
        self.s.db.execute("CREATE TRIGGER fail_bundle BEFORE INSERT ON story_packs BEGIN SELECT RAISE(ABORT,'fixture'); END")
        with self.assertRaises(sqlite3.Error):install(self.s,curated())
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM mystery_packs').fetchone()[0],0)
        self.s.db.execute('DROP TRIGGER fail_bundle')
        changed=curated();changed['story']['title']='Existing different story'
        # Install an incompatible pair first; the preset must never replace it.
        install(self.s,changed)
        with self.assertRaisesRegex(SessionError,'identity'):
            self.call('preview',kind='field_story',label='Signal',plan={},outcome_seq=None)
        self.assertIn('Existing different story',self.s.db.execute('SELECT document FROM story_packs').fetchone()[0])

    def test_packaged_preset_matches_authored_example_content(self):
        from pathlib import Path
        from world.field_story_bundle import curated
        root=Path(__file__).resolve().parents[2]
        bundle=curated()
        self.assertEqual(bundle['mystery'],json.loads((root/'examples/cooperative_signal.json').read_text()))
        self.assertEqual(bundle['story'],json.loads((root/'examples/cooperative_signal_story.json').read_text()))

    def test_field_story_refuses_connected_players_and_stale_review(self):
        draft=self.call('preview',kind='field_story',label='Signal',plan={},outcome_seq=None)
        self.s.peers['Alice']={'closing':False}
        with self.assertRaisesRegex(SessionError,'close all'):
            self.call('apply',token=draft['token'],confirmed=True)
        self.s.peers.clear()
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM mystery_packs').fetchone()[0],0)


class SettlementUI(unittest.TestCase):
    def test_reviewed_settlement_uses_existing_staged_authority_and_keeps_inhabitants(self):
        f = settlements.SettlementFlow(); f.setUp(); self.addCleanup(f.doCleanups)
        s = f.server
        session = SimpleNamespace(root=__import__('pathlib').Path('/unused'), server=s, state=SimpleNamespace(name='local'), engine='expansion-native')
        bridge = LauncherBridge(session, '/unused', engine='expansion-native')
        bridge.local_expeditions = lambda: [dict(key='local')]
        old = json.loads(json.dumps(s.module_state['world_characters']))
        read = bridge.action('content_read', dict(world='local'))
        self.assertIn(f.outcome['seq'], [e['seq'] for e in read['outcomes']])
        draft = bridge.action('content_preview',dict(world='local',kind='settlement',label='',plan=settlements.plan(),outcome_seq=f.outcome['seq']))
        self.assertNotIn('outpost_steward',s.module_state['world_characters'])
        with patch('world.client.admin_request',side_effect=f.transport):
            result = bridge.action('content_apply',dict(world='local',token=draft['token'],confirmed=True))
        self.assertTrue(result['saved']); self.assertIn('outpost_steward',result['residents'])
        for key, value in old.items(): self.assertEqual(s.module_state['world_characters'][key],value)


class FieldTestUI(unittest.TestCase):
    def test_curated_field_test_has_registered_survey_and_opt_in_recurring_character(self):
        import test_world_memory as memory
        f = memory.WorldMemoryTests(); f.setUp(); self.addCleanup(f.tearDown)
        s = f.server; s.runtime = settlements.FixtureRuntime()
        session = SimpleNamespace(root=f.root, server=s, state=SimpleNamespace(name='local'), engine='expansion-native')
        bridge = LauncherBridge(session, '/unused', engine='expansion-native')
        bridge.local_expeditions = lambda: [dict(key='local')]
        draft = bridge.action('content_preview',dict(world='local',kind='field_test',label='RC11 field test',plan={},outcome_seq=None))
        self.assertIsNone(s.shared_cave)
        self.assertIn('rc11_scholar', json.dumps(draft['plan']))
        result = bridge.action('content_apply',dict(world='local',token=draft['token'],confirmed=True))
        self.assertTrue(result['saved']); self.assertIn('rc11_scholar', result['residents'])
        self.assertIsNotNone(s.db.execute('SELECT 1 FROM survey_routes WHERE revision=?',(result['identity'],)).fetchone())
        self.assertEqual(s.db.execute('SELECT count(*) FROM survey_visits').fetchone()[0],0)
        self.assertEqual(s.db.execute('SELECT count(*) FROM survey_publications').fetchone()[0],0)
        obj = s.objects[0]; self.assertEqual((obj['x'],obj['y']),(8,8))
        self.assertNotIn('landmark_discovery_shared',[e['event'] for e in s.memory.history()['events']])
        with self.assertRaises(SessionError): bridge.action('content_preview',dict(world='local',kind='field_test',label='RC11 field test',plan={},outcome_seq=None))


if __name__ == '__main__': unittest.main()
