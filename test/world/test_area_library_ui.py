"""Read-only archive previews using real validators and SQLite, never sockets."""
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from world import large_cave, offline_cave, wilds, wilds_cast, wilds_events, wilds_guide, xl_wilds
from world.area_library_ui import inspect_area
from world.session import SessionError
from world.shared_cave import MAX_SIZE, SharedCave
from world.species_cohort import species_id
from world.web_launcher import LauncherBridge


def proposal(side):
    return {'rows': ['#' * side] + ['#' + '.' * (side - 2) + '#'] * (side - 2) + ['#' * side],
            'spawn': [1, 1], 'exit': [side - 2, side - 2]}


class AreaLibraryTests(unittest.TestCase):
    def setUp(self):
        self.sockets = patch('socket.socket', side_effect=AssertionError('No sockets in archive previews'))
        self.sockets.start()
        self.addCleanup(self.sockets.stop)
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.execute('CREATE TABLE generated_area_archive(identity TEXT PRIMARY KEY,label TEXT,template BLOB)')
        self.server = SimpleNamespace(db=self.db, lock=threading.RLock(), _closed=False,
                                      archive_generated_areas=True, shared_cave=None)
        self.session = SimpleNamespace(server=self.server, state=Path('/fixture/local'))
        self.worlds = [{'key': 'local'}]

    def save(self, blob, label='Quiet cave', identity=None):
        identity = identity or hashlib.sha256(blob).hexdigest()
        self.db.execute('INSERT OR REPLACE INTO generated_area_archive VALUES(?,?,?)', (identity, label, blob))
        return identity

    def inspect(self, identity):
        return inspect_area(self.session, self.worlds, {'world': 'local', 'identity': identity})

    def test_all_geometry_versions_and_exact_positions_without_mutation(self):
        cast = [{'gfx': 7, 'text': 'Hidden dialogue.'}, {'gfx': 8, 'text': 'More hidden dialogue.'}]
        events = {'initial': 0, 'rules': [{'state': 0, 'npc': 1, 'next': 1, 'text': 'Hidden story.'}]}
        p = proposal(63)
        cases = [(b'EWGMAP01' + ''.join(proposal(31)['rows']).encode(), 'cave', 31, 0),
                 (offline_cave.encode_profile(proposal(31), 'ice'), 'cave', 31, 0),
                 (large_cave.encode(p), 'cave', 63, 0),
                 (wilds.encode(p), 'wilds', 63, 0),
                 (wilds_guide.encode(p, 7, 'Hidden guide dialogue.'), 'guided_wilds', 63, 1),
                 (wilds_cast.encode(p, cast), 'cast_wilds', 63, 2),
                 (wilds_events.encode(p, cast, events), 'event_wilds', 63, 2),
                 (xl_wilds.encode(proposal(127)), 'xl_wilds', 127, 0)]
        active = SharedCave(cases[0][0])
        self.server.shared_cave = active
        for blob, kind, side, count in cases:
            with self.subTest(kind=kind, side=side):
                identity = self.save(blob)
                before = self.db.total_changes
                result = self.inspect(identity)
                self.assertEqual((result['kind'], result['side']), (kind, side))
                self.assertEqual(result['rows'], proposal(side)['rows'])
                self.assertEqual(result['entrance'], [1, 1])
                self.assertEqual(result['exit'], [side - 2, side - 2])
                self.assertEqual(result['floor_tiles'], (side - 2) ** 2)
                self.assertEqual([(npc['x'], npc['y']) for npc in result['characters']], [(2, 1), (20, 20)][:count])
                self.assertEqual(result['interactive'], kind == 'event_wilds')
                self.assertEqual(result['layout'], 'saved_base')
                self.assertNotIn('Hidden', json.dumps(result))
                self.assertNotIn('template', result)
                self.assertNotIn('events', result)
                self.assertEqual(self.db.total_changes, before)
                self.assertIs(self.server.shared_cave, active)

    def test_real_cohort_rosters_group_species_and_keep_distinct_levels(self):
        for cohort, name in [('vanilla', 'ZUBAT'), ('expansion-native', 'ROOKIDEE')]:
            for side, encoder in [(31, offline_cave.encode_wildlife), (63, large_cave.encode_wildlife)]:
                with self.subTest(cohort=cohort, side=side):
                    roster = [{'species': name, 'level': 5 + i % 2} for i in range(12)]
                    blob = encoder(proposal(side), 'granite', 20, roster, cohort=cohort)
                    result = self.inspect(self.save(blob))
                    self.assertEqual(result['wildlife_cohort'], cohort)
                    self.assertEqual(result['wildlife'], [{'species': species_id(name, cohort), 'name': name.title(), 'levels': [5, 6]}])
                    self.assertNotIn('rate', result)

    def test_current_world_scope_archive_and_live_host_required(self):
        identity = self.save(large_cave.encode(proposal(63)))
        for change in ('wrong_world', 'unknown_world', 'disconnected', 'remote', 'closed', 'archive_disabled'):
            with self.subTest(change=change):
                session = SimpleNamespace(server=self.server, state=Path('/fixture/local'))
                worlds = self.worlds
                if change == 'wrong_world': session.state = Path('/fixture/other')
                if change == 'unknown_world': worlds = []
                if change == 'disconnected': session.state = None
                if change == 'remote': session.server = None
                self.server._closed = change == 'closed'
                self.server.archive_generated_areas = change != 'archive_disabled'
                with self.assertRaisesRegex(SessionError, 'Open the local world'):
                    inspect_area(session, worlds, {'world': 'local', 'identity': identity})

    def test_payloads_cannot_supply_paths_extra_fields_or_noncanonical_ids(self):
        identity = self.save(large_cave.encode(proposal(63)))
        for value in (None, [], {}, {'world': 'local'}, {'world': 'local', 'identity': identity, 'path': '/tmp/other'},
                      {'world': 'local', 'identity': identity.upper()}, {'world': 'local', 'identity': '../other'},
                      {'world': False, 'identity': identity}, {'world': 'local', 'identity': 3}):
            with self.subTest(value=value), self.assertRaises(SessionError):
                inspect_area(self.session, self.worlds, value)

    def test_corrupt_missing_oversized_and_mislabeled_entries_fail_closed(self):
        blob = large_cave.encode(proposal(63))
        for data, label, identity in [(blob, 'Quiet', 'f' * 64), (b'x' * (MAX_SIZE + 1), 'Quiet', None),
                                      (blob[:-1], 'Quiet', None), (blob, 'x' * 81, None), (blob, '', None),
                                      (blob, '  ', None), (blob, 'bad\x00label', None), (blob, b'bad label', None),
                                      (blob[:8] + b'.' + blob[9:], 'Quiet', None)]:
            with self.subTest(label=label, size=len(data)):
                key = self.save(data, label, identity)
                with self.assertRaisesRegex(SessionError, 'Nothing was changed'):
                    self.inspect(key)
        with self.assertRaises(SessionError): self.inspect('0' * 64)
        self.db.execute('UPDATE generated_area_archive SET template=?', ('text instead of bytes',))
        with self.assertRaises(SessionError): self.inspect(key)

    def test_catalogue_and_database_errors_are_safe_and_read_only(self):
        blob = offline_cave.encode_wildlife(proposal(31), 'granite', 20, [{'species': 'ZUBAT', 'level': 5}] * 12)
        identity = self.save(blob)
        with patch('world.area_library_ui.catalogue', side_effect=ValueError('private path')):
            with self.assertRaises(SessionError) as result: self.inspect(identity)
        self.assertNotIn('private path', str(result.exception))
        self.db.execute('DROP TABLE generated_area_archive')
        with self.assertRaisesRegex(SessionError, 'Nothing was changed'): self.inspect(identity)

    def test_bridge_returns_only_inspection_and_never_mutates_or_snapshots(self):
        identity = self.save(large_cave.encode(proposal(63)))
        bridge = LauncherBridge.__new__(LauncherBridge)
        bridge.session = self.session
        bridge.lock = threading.RLock()
        bridge.local_expeditions = Mock(return_value=self.worlds)
        bridge.snapshot = Mock(side_effect=AssertionError('Preview is not a snapshot'))
        result = bridge.action('inspect_area', {'world': 'local', 'identity': identity})
        self.assertEqual(result['identity'], identity)
        bridge.snapshot.assert_not_called()
        self.assertNotIn('download', result)


if __name__ == '__main__': unittest.main()
