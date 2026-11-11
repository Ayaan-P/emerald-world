"""Real authority/compiler/SQLite closure for new Hoenn app source, not native play."""
import unittest
import time
from test_canonical_cast import CanonicalCastTests
from test_contest_guests import ContestGuests
from world import actor_runtime, birch_field_studies, canonical_cast
from world.build_catalog import catalog_maps
from world.species_cohort import species_id


class HoennAuthority(unittest.TestCase):
    def test_compiled_birch_study_native_wire_private_acceptance_and_frozen_terms(self):
        fixture = CanonicalCastTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        server = fixture.s
        fixture.apply(dict(id='canon_birch', expected_version=0, changes=dict(
            goal='Offer an optional field study', dialogue='An optional local field study is available.',
            places=['native:LittlerootTown'], evidence=[fixture.evidence],
            reason='Consider voluntary public field activity',
            tutor=dict(move=102, appearances=['birch'], research=dict(species=['WURMPLE'], days=2)))))
        peer = fixture.peer()
        peer['state'][:2] = next(pair for pair, row in catalog_maps().items()
                                  if row['name'] == 'LittlerootTown_ProfessorBirchsLab')
        run = 'a' * 32
        def request(action, guard, nonce):
            peer['state_time'] = time.monotonic()
            peer['out'].clear()
            server._line(peer, f'CORE {run} {action} birch {guard} {nonce}'.encode())
            return peer['out'].decode().strip().split()
        self.assertEqual(request('CAST', 'safe', 1)[:6], ['CORE', 'REPLY', '1', run, 'CAST', 'birch'])
        before = server.memory.history()['events']
        offer = request('STUDY', 'view', 2)
        self.assertEqual(offer[6], 'offer')
        self.assertEqual(int(offer[-1]), species_id('WURMPLE', 'expansion-native'))
        accepted = request('STUDY', 'accept:' + offer[8], 3)
        self.assertEqual(accepted[6], 'active')
        stored = birch_field_studies.retained(server, peer, run)
        self.assertEqual(stored['move'], 102)
        self.assertIsNone(birch_field_studies.retained(server, dict(id='other'), run))
        self.assertIsNone(birch_field_studies.retained(server, peer, 'b' * 32))
        self.assertEqual(server.memory.history()['events'], before)
        # Withdrawal of authored terms does not rewrite already accepted private terms.
        canonical_cast.records(server.module_state)['canon_birch'].pop('tutor')
        view = request('STUDY', 'view', 4)
        teaching = request('STUDY', 'tutor:' + view[8], 5)
        self.assertEqual(teaching[6:8], ['teach', '102'])
        self.assertEqual(server.memory.history()['events'], before)

    def test_actual_actor_market_plan_projects_public_shelf_and_keeps_other_capabilities(self):
        fixture = ContestGuests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        server = fixture.s
        fixture.c = dict(fixture.c, version=3, plan=dict(
            id='shelf', purpose='Offer optional original mart supplies', steps=[dict(
                id='open', tool='world.arrange_market_shelf',
                args=dict(site='SlateportCity_Mart', items='[28]', minutes=30), after=[])]))
        fixture.commit()
        self.assertEqual(actor_runtime.tick(server, now=10)['status'], 'succeeded')
        inspection = actor_runtime.inspect_runtime(server)
        self.assertEqual(inspection['hoenn_markets']['active'][0]['items'], [28])
        for tool in ('world.organize_rematches', 'world.arrange_market_shelf',
                     'world.build_adventure', 'world.use_move', 'world.reply_player'):
            self.assertIn(tool, inspection['capabilities'])
        self.assertTrue(inspection['capabilities']['world.reply_player']['during_activity'])
        self.assertIn('route_rematch_events', inspection)
        self.assertIn('shared_research', inspection)


if __name__ == '__main__':
    unittest.main()
