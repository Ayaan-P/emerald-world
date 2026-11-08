"""Read-only launcher journal against real authoritative commits."""
from pathlib import Path
from types import SimpleNamespace
import json
import unittest
from unittest.mock import patch
import test_world_memory as fixture
from world.session import SessionError
from world.world_journal import read_journal


class WorldJournalTests(unittest.TestCase):
    def setUp(self):
        self.case = fixture.WorldMemoryTests()
        self.case.setUp()
        self.addCleanup(self.case.tearDown)
        self.server = self.case.server
        self.session = SimpleNamespace(state=Path('/fixture/local'),server=self.server)
        self.worlds = [dict(key='local',name='Test world')]

    def read(self, **kwargs):
        return read_journal(self.session,self.worlds,dict(world='local',**kwargs))

    def test_journal_describes_commits_without_inventing_story_outcomes(self):
        first, second = self.case.bury_bridge_history()
        before = self.server.db.total_changes
        journal = self.read(place_id='native:LittlerootTown')
        self.assertEqual(self.server.db.total_changes,before)
        self.assertEqual([e['seq'] for e in journal['entries']],[second,first])
        self.assertIn('NPC keeper dialogue changed: Cedar bridge repaired. → Cedar bridge closed.',journal['entries'][0]['details'])
        self.assertEqual(journal['current']['objects'][0]['text'],'Cedar bridge closed.')
        serialized = json.dumps(journal)
        for private in ('not-for-recall','save_path','party_hash','token','City notice'):
            self.assertNotIn(private,serialized)
        self.assertEqual(journal['entries'][0]['evidence'],'authority_commit')

    def test_page_cutoff_refresh_and_world_scope(self):
        self.case.bury_bridge_history()
        first = self.read()
        self.assertEqual(len(first['entries']),20)
        self.assertTrue(first['has_more'])
        self.server._replace_cave(fixture.BLOB,label='New area')
        older = self.read(world_id=first['world_id'],through=first['through'],before=first['before'])
        self.assertEqual(older['through'],first['through'])
        self.assertFalse(set(e['seq'] for e in first['entries']) & set(e['seq'] for e in older['entries']))
        self.assertEqual(self.read()['entries'][0]['title'],'Area activated')
        with self.assertRaises(SessionError):self.read(world_id='other',through=first['through'])
        with self.assertRaises(SessionError):self.read(through=first['through'])
        with self.assertRaises(SessionError):self.read(before=True)

    def test_area_names_and_stable_place_revisions(self):
        old = self.server._replace_cave(fixture.BLOB,label='Old Harbor')
        place = self.server.memory.context(self.server)['active_area']['place_id']
        self.server._replace_cave(fixture.BLOB[:168]+b'#'+fixture.BLOB[169:],label='Harbor Garden',previous_revision=old)
        journal = self.read(place_id=place)
        self.assertEqual(len(journal['places']),1)
        self.assertEqual(journal['places'][0],dict(id=place,label='Harbor Garden',active=True))
        self.assertEqual(len(journal['entries']),2)
        self.assertIn('Continues the same recorded place.',journal['entries'][0]['details'])

    def test_detached_owned_host_and_closed_unknown_host(self):
        self.session.state = None
        self.session.server = None
        self.session._hosts = {'local':(self.server,None)}
        self.assertEqual(self.read()['world_id'],self.server.memory.world_id)
        with self.assertRaises(SessionError):read_journal(self.session,self.worlds,dict(world='other'))
        with self.assertRaises(SessionError):self.read(path='/private/save')
        self.session._hosts = {}
        with self.assertRaisesRegex(SessionError,'Open this local host'):self.read()

    def test_bridge_dispatch_is_read_only_and_scoped(self):
        from world.web_launcher import LauncherBridge
        import threading
        bridge = LauncherBridge.__new__(LauncherBridge)
        bridge.lock = threading.RLock()
        bridge.session = self.session
        bridge.local_expeditions = lambda:self.worlds
        before = self.server.db.total_changes
        result = bridge.action('journal_read',dict(world='local'))
        self.assertEqual(result['world_id'],self.server.memory.world_id)
        self.assertEqual(self.server.db.total_changes,before)



if __name__ == '__main__':unittest.main()
