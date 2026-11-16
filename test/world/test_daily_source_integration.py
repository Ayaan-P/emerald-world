"""Combined released RC12 and frozen actor/battle source contracts, not gameplay."""
import unittest
from copy import deepcopy
import test_characters as characters_fixture
import test_trainer_experiences as battle_fixture
from world import characters, canonical_cast


class DailySourceIntegrationTests(unittest.TestCase):
    def character_fixture(self):
        fixture = characters_fixture.CharacterLifecycleTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        return fixture

    def test_released_identity_and_place_suffixes_coexist_with_every_new_native_suffix(self):
        fixture = self.character_fixture()
        role = ('SOCIALCHATCAVE16REGION1CHAR1CHARQUEST1CHARREG1CHARWALK1'
                'COMMANDS1MOUNTS1CORE1CHARPK1CHARPK2CHARIDENT1CHARIDENT2PLACEQUEST1'
                'WORLDOBJ1CAVELINK1CAVELINKW1CHARSHOP1WEATHER1CHARTUTOR1')
        conn = fixture.peer(role=role)
        for field in ('character_identity_capable', 'character_identity2_capable',
                      'place_quest_capable', 'world_props_capable', 'cave_link_capable',
                      'cave_link_wildlife', 'character_shop_capable',
                      'outdoor_weather_capable', 'character_tutor_capable',
                      'character_pokemon_capable', 'character_state_capable',
                      'core_story_capable', 'private_commands', 'mount_capable'):
            self.assertTrue(conn[field], field)

    def test_authored_plan_preserves_released_guide_and_battle_portrait_fields(self):
        fixture = self.character_fixture()
        character = deepcopy(fixture.character)
        character.update(services=['guide'], battle_portrait='ranger_f', plan=dict(
            id='local_observation', purpose='Observe actual surroundings.', steps=[dict(
                id='look', tool='world.observe', args={'radius': 1}, after=[])]))
        self.assertEqual(characters.records({'world_characters': {'may': character}})['may'], character)
        self.assertIsNone(fixture.commit({'may': character}, fixture.npc))
        self.assertEqual(fixture.server.module_state['world_characters']['may'], character)
        self.assertIn('optional_services', characters.author_contract())
        self.assertIn('optional_battle_portrait', characters.author_contract())
        self.assertIn('optional_plan', characters.author_contract())
        fields = canonical_cast.contract()['change_fields']
        for name in ('plan', 'rematch', 'memories', 'investigation'):
            self.assertTrue(any(field.startswith(name+' ') for field in fields), name)

    def test_legacy_snapshot_does_not_access_unnegotiated_weather_state(self):
        from world.actor_weather import line
        from types import SimpleNamespace
        self.assertIsNone(line(SimpleNamespace(), {'state': None}))

    def test_standing_battle_mode_uses_nonce_bound_native_reply_without_public_evidence(self):
        fixture = battle_fixture.TrainerExperienceTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        server, peer = fixture.s, fixture.peer
        before = server.memory.history()['through']
        for nonce, key, guard, expected in ((31, 'get', 'private', 'OFF'),
                                             (32, 'on', 'confirm', 'ON'),
                                             (33, 'off', 'confirm', 'OFF')):
            peer['out'].clear()
            server._line(peer, f'CORE {"a"*32} BMODE {key} {guard} {nonce}'.encode())
            self.assertEqual(peer['out'].decode(), f'CORE REPLY {nonce} {"a"*32} BMODE {key} {expected}\n')
        self.assertEqual(server.memory.history()['through'], before)
