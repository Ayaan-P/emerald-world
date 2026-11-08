"""Construction preserves authored ecology and exact-revision survey semantics."""
import unittest
from unittest.mock import patch
import test_settlement_plans as fixtures
import test_route_encounters as encounter_tests
from world.route_encounters import encode, from_inspection
from world.frontier_outposts import compile_outpost
from world.route_artifacts import create, load
from world.shared_cave import SharedCave
from world.server import WorldServer

TABLE=dict(rate=12,wildlife=[dict(species='ZUBAT',level=8+i) for i in range(12)])

class WildlifeSettlements(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.SettlementFlow()
        original=WorldServer._replace_cave
        def replace(server,blob,**kwargs):
            return original(server,encode(blob,TABLE) if blob[:8]==b'EWGMAP0A' else blob,**kwargs)
        with patch.object(WorldServer,'_replace_cave',replace):self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def test_author_settlement_existing_resident_consent_and_restart(self):
        original=self.f.f.send
        def send(conn,line):return original(conn,line.replace('CAVE16','CAVE17'))
        with patch.object(self.f.f,'send',side_effect=send):
            self.f.test_real_outcome_becomes_inhabited_outpost_then_explicit_offer_completion_changes_dialogue()
        server=self.f.server
        self.assertEqual(server.shared_cave.version,17)
        self.assertEqual(server.shared_cave.wildlife,encode(b'EWGMAP0A'+b''.join(server.shared_cave._rows),TABLE)[8:45])
        saved=server.memory.inspect_saved_place(server,server.shared_cave.identity)
        self.assertEqual(SharedCave(from_inspection(saved)).wildlife,server.shared_cave.wildlife)
        saved['encounters']['wildlife'][0]['level']+=1
        with self.assertRaisesRegex(ValueError,'revision'):from_inspection(saved)
        old=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
        token=server.create_identity('OldClient')['token']
        self.f.f.send(old,f'HELLO 1 OldClient {token} SOCIALCAVE16')
        self.assertEqual(self.f.f.send(old,'CAVE GET'),'CAVE NONE\n')

    def test_construction_does_not_relabel_original_route_recipe(self):
        server=self.f.server
        blob,artifact=create(encounter_tests.plan())
        server._replace_cave(blob,route_artifact=artifact)
        old=server.shared_cave.identity
        server.landmark_survey.register_revision(old)
        chosen=None
        for x in range(5,115,10):
            for y in range(5,115,10):
                p=dict(x=x,y=y,width=7,height=7,gate='west',reservations=[])
                try:new,report=compile_outpost(blob,p)
                except ValueError:continue
                chosen=(new,report);break
            if chosen:break
        self.assertIsNotNone(chosen)
        new,report=chosen
        server._replace_cave(new,previous_revision=old)
        self.assertEqual(server.memory.place(old),server.memory.place(report['revision']))
        self.assertEqual(load(server,old),artifact)
        self.assertIsNone(server.db.execute('SELECT sites FROM survey_routes WHERE revision=?',(report['revision'],)).fetchone())
        with self.assertRaisesRegex(ValueError,'unavailable'):load(server,report['revision'])
        self.assertEqual(SharedCave(new).wildlife,SharedCave(blob).wildlife)

    def test_actual_native_decoder_accepts_constructed_ecology(self):
        original=encounter_tests.compile_plan
        def compile_constructed(plan):
            blob,report=original(plan)
            for x in range(5,115,10):
                for y in range(5,115,10):
                    try:return compile_outpost(blob,dict(x=x,y=y,width=7,height=7,gate='west',reservations=[]))
                    except ValueError:pass
            raise AssertionError('fixture has no construction site')
        # Use the real paired decoder harness, substituting only constructed input.
        with patch.object(encounter_tests,'compile_plan',side_effect=compile_constructed):
            encounter_tests.RouteEncounterTests().test_actual_native_decoder_binds_authored_population_and_routes()

if __name__=='__main__':unittest.main()
