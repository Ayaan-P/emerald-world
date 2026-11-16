"""Real authority identity archive and negotiated native opponent descriptors."""
from copy import deepcopy
import unittest
from test_characters import CharacterLifecycleTests

class CompanionIdentityTests(unittest.TestCase):
    def setUp(self):
        self.f=CharacterLifecycleTests();self.f.setUp();self.addCleanup(self.f.tearDown)
        self.s=self.f.server
        self.c=deepcopy(self.f.character)
        self.c['team']=[dict(species=277,level=12,individual='cedar_partner'),dict(species=278,level=10,individual='coastal_partner')]
        self.assertIsNone(self.f.commit({'may':self.c},self.f.npc))
    def values(self,wire):
        tokens=wire.strip().split();self.assertEqual(tokens[0],'CHARACTER_BATTLE_V2')
        return [list(map(int,tokens[i:i+4])) for i in range(5,len(tokens),4)]
    def test_identity_survives_level_growth_reordering_restart_and_exact_pending_snapshot(self):
        a=self.f.peer(role='SOCIALCHAR1CHARPK1')
        first=self.values(self.f.send(a,'CHARACTER_CHALLENGE 1 may 1'))
        self.assertEqual(first[0][:2],[277,12]);self.assertEqual(first[1][:2],[278,10])
        self.assertNotEqual(first[0][2],first[1][2]);self.assertEqual(first[0][3],first[1][3])
        frozen=deepcopy(a['character_pending'])
        revised=deepcopy(self.c);revised['version']=2
        revised['team']=list(reversed(revised['team']));revised['team'][1]['level']=20
        self.assertIsNone(self.f.commit({'may':revised},self.f.npc))
        self.assertEqual(a['character_pending'],frozen)
        self.f.send(a,'CHARACTER_RESULT 1 may 1 0')
        second=self.values(self.f.send(a,'CHARACTER_CHALLENGE 2 may 2'))
        self.assertEqual(second[1][2:],first[0][2:]);self.assertEqual(second[1][:2],[277,20])
        self.assertEqual(second[0][2:],first[1][2:])
        self.s.close();self.f.server=self.f.open();self.s=self.f.server
        a=self.f.peer(role='SOCIALCHAR1CHARPK1')
        self.assertEqual(self.values(self.f.send(a,'CHARACTER_CHALLENGE 1 may 2')),second)
    def test_old_clients_refuse_identified_teams_and_species_identity_cannot_be_reassigned(self):
        a=self.f.peer()
        self.assertIn('CHARACTER_REJECT',self.f.send(a,'CHARACTER_CHALLENGE 1 may 1'))
        self.assertNotIn('character_pending',a)
        bad=deepcopy(self.c);bad['version']=2;bad['team'][0]['species']=278
        self.assertIsNotNone(self.f.commit({'may':bad},self.f.npc))
        self.assertEqual(self.s.module_state['world_characters']['may'],self.c)
        mixed=deepcopy(self.c);mixed['version']=2;mixed['team'][0].pop('individual')
        self.assertIsNotNone(self.f.commit({'may':mixed},self.f.npc))
        duplicate=deepcopy(self.c);duplicate['version']=2;duplicate['team'][1]['individual']='cedar_partner'
        self.assertIsNotNone(self.f.commit({'may':duplicate},self.f.npc))
    def test_removed_partner_retains_identity_and_different_actor_has_independent_owner(self):
        archived=self.s.db.execute("SELECT personality,owner FROM character_companions WHERE actor='may' AND individual='cedar_partner'").fetchone()
        revised=deepcopy(self.c);revised.update(version=2,team=[self.c['team'][1]])
        self.assertIsNone(self.f.commit({'may':revised},self.f.npc))
        revised.update(version=3,team=self.c['team']);self.assertIsNone(self.f.commit({'may':revised},self.f.npc))
        self.assertEqual(archived,self.s.db.execute("SELECT personality,owner FROM character_companions WHERE actor='may' AND individual='cedar_partner'").fetchone())
        from world.character_companions import commit
        with self.s.db:commit(self.s.db,self.s.memory.world_id,[dict(character_id='other',after=self.c)])
        other=self.s.db.execute("SELECT personality,owner FROM character_companions WHERE actor='other' AND individual='cedar_partner'").fetchone()
        self.assertNotEqual(archived,other)
