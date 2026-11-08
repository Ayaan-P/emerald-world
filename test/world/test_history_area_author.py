"""Committed guild outcome -> inert guide author -> actual archived destination."""
import json
import unittest
from unittest.mock import patch

import test_world_memory as fixtures
from test_author_cave import DOC, wire
from test_shared_generated_cave import BLOB
from world import author_cave


class HistoryAreaAuthorTests(unittest.TestCase):
    def setUp(self):
        self.case=fixtures.WorldMemoryTests()
        self.case.setUp()
        self.addCleanup(self.case.tearDown)
        self.server=self.case.server
        self.old=self.server._replace_cave(BLOB,label='Old Camp')
        self.server.create_identity('PrivateTrainer')
        self.server.guilds.command('PrivateTrainer','create Redwood')
        self.server.guilds.command('PrivateTrainer','chronicle on')
        self.server.guilds.command('PrivateTrainer','expedition start LittlerootTown 1')
        self.server.guilds.visit('PrivateTrainer','LittlerootTown')
        self.event=self.server.memory.history()['events'][-1]
        self.assertEqual(self.event['event'],'guild_goal_completed')

    def transport(self,_socket,request,**kwargs):
        return self.case.admin(request)

    def provider(self,prompt,validator,**kwargs):
        self.assertIn('Redwood',prompt)
        self.assertIn('guild_goal_completed',prompt)
        self.assertNotIn('PrivateTrainer',prompt)
        self.assertNotIn('save_path',prompt)
        self.assertNotIn('party_hash',prompt)
        self.assertIn('Do not claim portals',prompt)
        return validator(wire({**DOC,'guide_gfx':'boy','guide_text':'Redwood reached its goal!'}))

    def generate(self,provider=None):
        with patch('world.client.admin_request',side_effect=self.transport), \
             patch('world.publish_cave.admin_request',side_effect=self.transport), \
             patch('world.author_cave.request_validated',side_effect=provider or self.provider), \
             patch('builtins.print'):
            return author_cave.main(['Honor the Redwood expedition','--admin-socket','admin',
                                     '--world-history','--label','Redwood Refuge','--shared-guided-wilds'])

    def test_outcome_creates_real_named_guide_destination_and_preserves_old_place(self):
        self.assertEqual(self.generate(),0)
        new=self.server.shared_cave.identity
        self.assertNotEqual(new,self.old)
        self.assertIn(b'Redwood reached its goal!',self.server.shared_cave.guide)
        event=self.server.memory.history()['events'][-1]
        self.assertEqual(event['event'],'area_activated')
        self.assertIn(self.event['seq'],event['history_evidence'])
        self.assertEqual(event['label'],'Redwood Refuge')
        self.assertNotEqual(event['place_id'],self.server.memory.place(self.old))
        self.assertEqual({area['identity'] for area in self.server.list_generated_areas()},{new,self.old})
        self.server.close()
        self.case.server=self.case.open()
        self.server=self.case.server
        self.assertEqual(self.server.shared_cave.identity,new)
        self.assertEqual(self.server.memory.history()['events'][-1],event)
        self.server.activate_generated_area(self.old)
        self.assertEqual(self.server.shared_cave.identity,self.old)

    def test_concurrent_change_refuses_publication_without_losing_existing_area(self):
        def race(prompt,validator,**kwargs):
            result=self.provider(prompt,validator,**kwargs)
            self.server._replace_cave(BLOB,label='Renamed Camp')
            return result
        self.assertEqual(self.generate(race),1)
        self.assertEqual(self.server.shared_cave.identity,self.old)
        self.assertEqual(len(self.server.list_generated_areas()),1)

    def test_history_requires_explicit_publication_destination(self):
        with patch('world.author_cave.request_validated') as provider:
            with self.assertRaises(SystemExit):
                author_cave.main(['theme','--world-history'])
            provider.assert_not_called()


if __name__=='__main__':
    unittest.main()
