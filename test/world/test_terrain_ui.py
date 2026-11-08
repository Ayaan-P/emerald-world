"""Local terrain UI against the existing authority without sockets or a game."""
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from world.server import WorldServer
from world.session import SessionError
from world.terrain_ui import terrain_action
from world.wilds_events import encode


class TerrainUiTests(unittest.TestCase):
    def setUp(self):
        guard = patch('socket.socket', side_effect=AssertionError('No socket tests'))
        guard.start(); self.addCleanup(guard.stop)
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        rows = ['#' * 63] + ['#' + '.' * 61 + '#'] * 61 + ['#' * 63]
        self.blob = encode({'rows': rows, 'spawn': [1, 1], 'exit': [61, 61]}, [{'gfx': 7, 'text': 'Hi!'}],
                           {'initial': 0, 'rules': [{'state': 0, 'npc': 1, 'next': 1, 'text': 'Hi!'}]})
        self.server = WorldServer(self.root / 'socket', self.root / 'world', cave_template=self.blob,
                                  persist_generated_cave=True, archive_generated_areas=True)
        self.addCleanup(self.server.close)
        self.server._replace_cave(self.blob)
        self.identity = self.server.shared_cave.identity
        self.session = SimpleNamespace(server=self.server, state=Path('/fixture/local'))
        self.scope = {'world': 'local', 'identity': self.identity}
        self.tile = {'x': 3, 'y': 3, 'terrain': 'tall_grass'}

    def action(self, name, **payload):
        return terrain_action(self.session, [{'key': 'local'}], name, dict(self.scope, **payload))

    def test_inspect_review_apply_and_reload_use_real_persistent_authority(self):
        current = self.action('terrain_read')
        self.assertEqual((current['revision'], current['players'], current['tiles']), (0, 0, []))
        before = self.server.db.total_changes
        review = self.action('terrain_review', expected_revision=0, tiles=[self.tile])
        self.assertEqual(review['proposed_tiles'], [self.tile]); self.assertEqual(self.server.db.total_changes, before)
        result = self.action('terrain_apply', expected_revision=0, tiles=[self.tile], confirmed=True)
        self.assertTrue(result['saved']); self.assertEqual(result['revision'], 1)
        self.assertEqual(self.action('terrain_read')['tiles'], [self.tile])
        self.assertEqual(self.server.inspect_shared_terrain(self.identity)['tiles'], [self.tile])
        self.server.close()
        restored = WorldServer(self.root / 'other', self.root / 'world', persist_generated_cave=True, archive_generated_areas=True)
        try:
            self.assertEqual(restored.inspect_shared_terrain(self.identity)['revision'], 1)
            self.assertEqual(restored.inspect_shared_terrain(self.identity)['tiles'], [self.tile])
        finally: restored.close()

    def test_no_confirmation_and_stale_revision_cannot_mutate(self):
        for confirmation in (False, 1, None):
            with self.assertRaises(SessionError): self.action('terrain_apply', expected_revision=0, tiles=[self.tile], confirmed=confirmation)
        self.server.set_shared_geometry(self.identity, [self.tile], replace=True)
        for action in ('terrain_review', 'terrain_apply'):
            with self.assertRaisesRegex(SessionError, 'Terrain changed'):
                self.action(action, expected_revision=0, tiles=[], **({'confirmed': True} if action.endswith('apply') else {}))
        self.assertEqual(self.action('terrain_read')['revision'], 1)

    def test_all_players_outside_and_pending_offers_still_block_apply(self):
        for peer in ({}, {'cave_offer': self.identity}, {'cave_ack': self.identity}, {'in_generated_cave': True}):
            self.server.peers = {'Player': peer}
            self.assertEqual(self.action('terrain_review', expected_revision=0, tiles=[self.tile])['players'], 1)
            with self.assertRaisesRegex(SessionError, 'close all connected games'):
                self.action('terrain_apply', expected_revision=0, tiles=[self.tile], confirmed=True)
            self.assertEqual(self.server._active_terrain(), (0, b'\0'))
        self.server.peers.clear()

    def test_reentrant_lock_covers_revision_admission_and_write(self):
        original = self.server.set_shared_geometry
        def write(*args, **kwargs):
            self.assertTrue(self.server.lock._is_owned())
            self.assertEqual(kwargs, {'replace': True})
            return original(*args, **kwargs)
        with patch.object(self.server, 'set_shared_geometry', side_effect=write):
            self.action('terrain_apply', expected_revision=0, tiles=[self.tile], confirmed=True)

    def test_connectivity_npcs_protected_cells_and_duplicates_rejected_before_mutation(self):
        blocked = [{'x': x, 'y': y, 'terrain': 'water'} for x, y in [(9, 10), (10, 9), (11, 10), (10, 11)]]
        cases = [blocked, [dict(self.tile, x=1, y=1)], [dict(self.tile, x=2, y=1)],
                 [dict(self.tile, x=61, y=60)], [dict(self.tile, x=0)], [self.tile, self.tile],
                 [dict(self.tile, x=True)], [dict(self.tile, terrain='script')], [dict(self.tile, extra=1)],
                 [self.tile] * 513]
        before = self.server.db.total_changes
        for tiles in cases:
            with self.subTest(tiles=tiles[:2]), self.assertRaises(SessionError):
                self.action('terrain_review', expected_revision=0, tiles=tiles)
        self.assertEqual(self.server.db.total_changes, before)

    def test_replace_reset_and_512_overrides_follow_existing_semantics(self):
        tiles = [{'x': x, 'y': y, 'terrain': 'grass'} for x in range(3, 62) for y in range(2, 60)][:512]
        result = self.action('terrain_apply', expected_revision=0, tiles=tiles, confirmed=True)
        self.assertEqual(len(result['tiles']), 512)
        result = self.action('terrain_apply', expected_revision=1, tiles=[], confirmed=True)
        self.assertEqual((result['tiles'], result['revision']), ([], 2))

    def test_scope_and_active_identity_changes_fail_closed(self):
        for changes in ({'world': 'remote'}, {'identity': 'f' * 64}, {'identity': '../path'}, {'extra': True}):
            with self.assertRaises(SessionError):
                terrain_action(self.session, [{'key': 'local'}], 'terrain_read', dict(self.scope, **changes))
        self.server._closed = True
        try:
            with self.assertRaises(SessionError): self.action('terrain_read')
        finally: self.server._closed = False
        with patch.object(self.server.shared_cave, 'version', 16):
            with self.assertRaisesRegex(SessionError, '63'): self.action('terrain_read')

    def test_corrupt_stored_overlay_is_bounded_and_errors_hide_paths(self):
        self.server.db.execute('INSERT INTO generated_area_terrain VALUES(?,?,?)', (self.identity, 1, b'x' * 1540))
        with self.assertRaises(SessionError) as result: self.action('terrain_read')
        self.assertNotIn(str(self.root), str(result.exception))

    def test_launcher_bridge_routes_without_replacing_session_snapshot(self):
        from world.web_launcher import LauncherBridge
        bridge = LauncherBridge.__new__(LauncherBridge)
        bridge.session = self.session
        bridge.lock = threading.RLock()
        bridge.local_expeditions = Mock(return_value=[{'key': 'local'}])
        bridge.snapshot = Mock(side_effect=AssertionError('Terrain is response-only'))
        self.assertEqual(bridge.action('terrain_read', self.scope)['revision'], 0)
        bridge.snapshot.assert_not_called()

    def test_uncertain_post_commit_failure_does_not_retry(self):
        original = self.server.set_shared_geometry
        def uncertain(*args, **kwargs):
            original(*args, **kwargs)
            raise OSError('/private/path')
        with patch.object(self.server, 'set_shared_geometry', side_effect=uncertain) as method:
            with self.assertRaisesRegex(SessionError, 'save confirmed'):
                self.action('terrain_apply', expected_revision=0, tiles=[self.tile], confirmed=True)
            self.assertEqual(method.call_count, 1)
        self.assertEqual(self.action('terrain_read')['revision'], 1)


if __name__ == '__main__': unittest.main()
