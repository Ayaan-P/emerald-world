"""Authenticated authored identity, independent of private trainer/save identity."""
import unittest
from typing import Any
import test_characters as character_fixture


class CharacterIdentityTests(unittest.TestCase):
    def setUp(self):
        self.fixture = character_fixture.CharacterLifecycleTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.server = self.fixture.server
        self.fixture.character['name'] = 'Field Scholar'
        self.assertIsNone(self.fixture.commit({'may': self.fixture.character}, self.fixture.npc))

    def test_capable_challenge_freezes_authored_identity_with_the_team(self):
        conn: Any = self.fixture.peer(role='SOCIALCHAR1CHARIDENT1')
        reply = self.fixture.send(conn, 'CHARACTER_CHALLENGE 1 may 1')
        expected = 'CHARACTER_BATTLE_V2 1 may 1 1 ' + b'Field Scholar'.hex() + ' scientist 277 12\n'
        self.assertEqual(reply, expected)
        self.assertEqual(conn['character_pending']['name'], 'Field Scholar')
        self.assertEqual(conn['character_pending']['portrait'], 'scientist')
        self.fixture.character['name'] = 'Changed name'
        self.fixture.npc['gfx'] = 7
        self.assertEqual(conn['character_pending']['name'], 'Field Scholar')
        self.assertEqual(conn['character_pending']['portrait'], 'scientist')

    def test_legacy_wire_remains_exactly_v1(self):
        conn: Any = self.fixture.peer()
        self.assertEqual(self.fixture.send(conn, 'CHARACTER_CHALLENGE 1 may 1'),
                         'CHARACTER_BATTLE_V1 1 may 1 1 277 12\n')
        self.assertNotIn('name', conn['character_pending'])

    def test_identity_suffix_and_place_offer_suffix_can_coexist(self):
        conn: Any = self.fixture.peer(role='SOCIALCAVE16CHAR1CHARQUEST1CHARREG1CHARWALK1CHARIDENT1PLACEQUEST1')
        for key in ('character_capable', 'character_quest_capable', 'character_region_capable',
                    'character_walk_capable', 'character_identity_capable', 'place_quest_capable'):
            self.assertTrue(conn[key], key)

    def test_identity_capability_without_character_contract_is_refused(self):
        identity = self.server.create_identity('Invalid')
        conn: Any = dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
        self.server._line(conn, ('HELLO 1 Invalid %s SOCIALCHARIDENT1' % identity['token']).encode())
        self.assertIn(b'ERROR AUTH', conn['out'])

    def test_unrenderable_authored_name_refuses_without_creating_pending(self):
        conn: Any = self.fixture.peer(role='SOCIALCHAR1CHARIDENT1')
        self.server.module_state['world_characters']['may']['name'] = '\u2603'
        self.assertIn('CHARACTER_REJECT', self.fixture.send(conn, 'CHARACTER_CHALLENGE 1 may 1'))
        self.assertNotIn('character_pending', conn)
        self.assertEqual(conn['seq'], 0)

    def test_unsupported_name_glyphs_do_not_become_native_control_bytes(self):
        conn: Any = self.fixture.peer(role='SOCIALCHAR1CHARIDENT1')
        self.server.module_state['world_characters']['may']['name'] = 'Dr. M\u00e2y\u2666'
        reply = self.fixture.send(conn, 'CHARACTER_CHALLENGE 1 may 1')
        self.assertEqual(reply, 'CHARACTER_BATTLE_V2 1 may 1 1 ' + b'Dr. M y'.hex() + ' scientist 277 12\n')
    def test_chapter_can_author_a_bounded_portrait_and_reset_to_default(self):
        import hashlib
        import json
        from test_character_chapters import plan
        from world.character_chapters import validate_plan, chapter_step
        from world.characters import records
        p: Any = plan()
        p['chapters'][0]['battle_portrait'] = 'ranger_f'
        try:
            p = validate_plan(p)
        except ValueError:
            self.fail('Authored portrait is not accepted by the chapter compiler')
        definition = hashlib.sha256(json.dumps(p, sort_keys=True).encode()).hexdigest()
        context = {'character_history': {'events': [], 'through': 0}}
        result = chapter_step(p, definition, 0, context, {'state': {}, 'objects': [], 'tiles': []})
        self.assertEqual(records(result['state'])[p['id']]['battle_portrait'], 'ranger_f')
        event = dict(p['chapters'][1]['when'], seq=1)
        context = {'character_history': {'events': [event], 'through': 1}}
        result = chapter_step(p, definition, 0, context, result)
        self.assertEqual(records(result['state'])[p['id']].get('battle_portrait', 'scientist'), 'scientist')
    def test_portrait_change_uses_existing_history_grounded_action_path(self):
        from world.character_actions import validate_actions, action_step
        from world.characters import records
        from copy import deepcopy
        import hashlib
        import json
        action = dict(id='may', expected_version=1, evidence=[self.fixture.evidence],
                      reason='Authored ranger presentation', changes={'battle_portrait': 'ranger_f'},
                      object=self.fixture.npc)
        try:
            actions = validate_actions([action], self.server.inspect())
        except ValueError:
            self.fail('Existing character action path rejects an authored portrait change')
        definition = hashlib.sha256(json.dumps(actions, sort_keys=True).encode()).hexdigest()
        result = {'state': deepcopy(self.server.module_state), 'objects': self.server.objects, 'tiles': []}
        result = action_step(actions, definition, result, self.server._context())
        self.assertEqual(records(result['state'])['may']['battle_portrait'], 'ranger_f')
        self.assertEqual(records(result['state'])['may']['version'], 2)

    def test_unknown_or_nonliteral_portraits_are_rejected(self):
        from world.characters import records
        for portrait in ('admin', '../scientist', 'SCIENTIST', True, 1, None, {}, 'ranger_m\n'):
            with self.subTest(portrait=portrait), self.assertRaises(ValueError):
                records({'world_characters': {'may': dict(self.fixture.character, battle_portrait=portrait)}})


if __name__ == '__main__':
    unittest.main()
