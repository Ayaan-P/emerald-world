"""Private command routing uses a session record, never chat announcements."""
from unittest.mock import Mock
from test_chat_in_memory import ChatRoutingTests
from world.rally import RallyCoordinator


class PrivateCommandTests(ChatRoutingTests):
    def test_reserved_commands_never_fall_through_to_room_or_whispers(self):
        for i, (target, text) in enumerate([
            ('*', '/STORY choose secret'), ('*', '  /mYsTeRy secret'),
            ('*', '/future-command secret'), ('bob', '/story secret')], 1):
            self.alice['chat_credit'] = 4
            self.send(i, target, text)
            self.assertEqual(self.server.peers['bob']['chat_history'], [])
            self.assertEqual(self.server.peers['carol']['chat_history'], [])
        self.server._broadcast.assert_not_called()

    def test_negotiated_feature_dispatch_preserves_choice_case(self):
        self.server.opportunity_chat = Mock()
        self.alice['private_commands'] = True
        self.send(1, '*', '  /STORY choose PrivateChoice')
        self.server.opportunity_chat.handle.assert_called_once_with(self.alice, '/story choose PrivateChoice')
        self.server._broadcast.assert_not_called()
        self.assertIn('COMMANDS 1 13\n', self.server._snapshot(self.alice))

    def test_legacy_and_forged_chat_do_not_grant_capabilities(self):
        self.server.opportunity_chat = Mock()
        self.send(1, 'alice', 'Guild: protocol 1')
        self.send(2, '*', '/story choose secret')
        self.server.opportunity_chat.handle.assert_not_called()
        self.assertFalse(self.alice.get('private_commands'))
        self.assertNotIn('COMMANDS', self.server._snapshot(self.alice))
        self.assertEqual(self.server.peers['bob']['chat_history'], [])

    def test_existing_survey_dispatch_is_private_and_case_insensitive(self):
        self.server.landmark_survey.handle = Mock(return_value=True)
        self.send(1, '*', ' /EXPLORE share Landmark confirm')
        self.server.landmark_survey.handle.assert_called_once_with(self.alice, '/explore share Landmark confirm')
        self.server._broadcast.assert_not_called()

    def test_session_capability_strips_after_all_released_suffixes(self):
        self.server.db.execute('CREATE TABLE identities (id TEXT, token TEXT)')
        token = 'ab' * 32
        self.server.db.execute('INSERT INTO identities VALUES (?, ?)', ('new', token))
        self.server.peers = {}
        self.server.rally = RallyCoordinator(self.server.peers)
        self.server.max_players = 8
        self.server._event = Mock()
        conn = {'id': None, 'closing': False, 'state': None}
        role = 'SOCIALTRAVELCHATRALLYPEER32CAVE16REGION1RULES3CHAR1CHARQUEST1CHARREG1CHARWALK1COMMANDS1'
        self.server._line(conn, f'HELLO 1 new {token} {role}'.encode())
        self.assertTrue(conn['private_commands'])
        self.assertTrue(conn['character_walk_capable'])
        self.assertTrue(conn['region_capable'])
        self.assertIn('COMMANDS 1 12\n', self.server._snapshot(conn))
        # Reconnection creates a new authority session; no sticky capability.
        self.server.peers.clear()
        old = {'id': None, 'closing': False, 'state': None}
        self.server._line(old, f'HELLO 1 new {token} SOCIALCHAT'.encode())
        self.assertFalse(old['private_commands'])
        self.assertNotIn('COMMANDS', self.server._snapshot(old))
