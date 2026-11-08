"""Public outcome -> constrained route author -> persistent shared geometry."""
import unittest
from unittest.mock import patch
import test_history_area_author as fixtures
from test_author_cave import wire
from test_route_landscape import plan
from world import author_routes


class RouteAuthorTests(fixtures.HistoryAreaAuthorTests):
    def provider(self,prompt,validator,**kwargs):
        self.assertIn('Redwood',prompt)
        self.assertIn('guild_goal_completed',prompt)
        self.assertNotIn('PrivateTrainer',prompt)
        self.assertNotIn('party_hash',prompt)
        self.assertIn('Do not claim portals',prompt)
        return validator(wire(plan()))

    def generate(self,provider=None):
        with patch('world.client.admin_request',side_effect=self.transport), \
             patch('world.publish_cave.admin_request',side_effect=self.transport), \
             patch('world.author_cave.request_validated',side_effect=provider or self.provider), \
             patch('builtins.print'):
            return author_routes.main(['Honor the Redwood expedition','--activate-shared','admin',
                                       '--label','Redwood Refuge'])

    def test_outcome_creates_real_named_guide_destination_and_preserves_old_place(self):
        self.assertEqual(self.generate(),0)
        new=self.server.shared_cave.identity
        self.assertEqual(self.server.shared_cave.version,16)
        event=self.server.memory.history()['events'][-1]
        self.assertIn(self.event['seq'],event['history_evidence'])
        self.assertEqual(event['label'],'Redwood Refuge')
        self.assertNotEqual(event['place_id'],self.server.memory.place(self.old))
        self.assertEqual({a['identity'] for a in self.server.list_generated_areas()},{new,self.old})
        self.server.close();self.case.server=self.case.open();self.server=self.case.server
        self.assertEqual(self.server.shared_cave.identity,new)
        self.assertEqual(self.server.memory.history()['events'][-1],event)
        self.server.activate_generated_area(self.old)
        self.assertEqual(self.server.shared_cave.identity,self.old)

    def test_history_requires_explicit_publication_destination(self):
        with patch('world.author_cave.request_validated') as provider:
            with self.assertRaises(SystemExit):author_routes.main(['theme','--activate-shared','admin'])
            provider.assert_not_called()

    def test_occupied_world_refuses_new_destination(self):
        self.server.peers['occupied'] = dict(closing=False,in_generated_cave=True)
        try:
            self.assertEqual(self.generate(),1)
            self.assertEqual(self.server.shared_cave.identity,self.old)
            self.assertEqual(len(self.server.list_generated_areas()),1)
        finally:
            self.server.peers.clear()

    def test_offline_writes_template_without_activation(self):
        output=self.case.root/'new.ewmap'
        with patch('world.author_cave.request_validated',side_effect=lambda p,v,**kw:v(wire(plan()))):
            self.assertEqual(author_routes.main(['A mountain divide','--output',str(output)]),0)
        self.assertEqual(output.read_bytes()[:8],b'EWGMAP0A')
        self.assertEqual(self.server.shared_cave.identity,self.old)

    def test_transport_tool_activity_never_compiles(self):
        with patch('world.author_cave.request_validated',side_effect=lambda p,v,**kw:v(
            '{"type":"item.started","item":{"type":"command_execution"}}')):
            self.assertEqual(author_routes.main(['theme','--output',str(self.case.root/'bad')]),1)
        self.assertFalse((self.case.root/'bad').exists())

if __name__=='__main__':unittest.main()
