"""Real authority choices are remembered on ordinary CAST visits without a worker."""
import json
import time
import unittest
import test_canonical_cast as fixture
from world import canonical_cast as cast
from world.canonical_memory import acknowledge


class DecisionRevisitTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.CanonicalCastTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.s = self.f.s
        action = self.f.action(text='There is room for different ways to ride.')
        action['changes']['council'] = dict(
            mode='speaker', question='What should I consider for my next advice?',
            options=dict(independent='Independent journeys', together='Travelling together'))
        self.f.apply(action)
        self.a = self.f.peer()
        self.b = self.f.peer('Bob')

    def command(self, peer, *args):
        return cast.guild_command(self.s, peer, ['rydel', *args])

    def visit(self, peer, run='a'*32):
        peer['state_time'] = time.monotonic()
        peer['out'].clear()
        self.s._line(peer, ('CORE '+run+' CAST rydel safe 15').encode())
        wire = peer['out'].decode().strip()
        self.assertTrue(wire.startswith('CORE REPLY 15 '), wire)
        return bytes.fromhex(wire.split()[-1]).decode('ascii')

    def choose(self):
        self.command(self.a, 'converse')
        identifier = self.s.db.execute('SELECT id FROM canonical_dialogues').fetchone()[0]
        self.command(self.a, 'choose', identifier, 'independent')

    def test_ordinary_revisit_recalls_consented_choice_without_model_or_public_identity(self):
        self.command(self.a, 'remember', 'on')
        shown = cast.response(self.s, self.a, 'a'*32, 'rydel')
        acknowledge(self.s, self.a, 'a'*32, 'canon_rydel', shown['digest'])
        self.choose()
        history = self.s.memory.history()
        inspection = self.s.inspect()
        text = self.visit(self.a)
        self.assertIn('You chose Independent journeys', text)
        self.assertIn('not a completed journey', text)
        self.assertLessEqual(len(text.encode('ascii')), 240)
        self.assertEqual(self.s.memory.history(), history)
        self.assertEqual(self.s.inspect(), inspection)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_reflections').fetchone()[0], 0)
        self.assertNotIn('You chose', self.visit(self.b))
        self.assertNotIn('You chose', self.visit(self.a, 'b'*32))
        self.assertIn('You chose Independent journeys', self.visit(self.a))
        self.s.close()
        self.f.f.case.server = self.f.f.case.open()
        self.s = self.f.f.case.server
        self.f.s = self.s
        self.f.f.server = self.s
        self.a = self.f.peer()
        self.assertIn('You chose Independent journeys', self.visit(self.a))
        public = json.dumps(self.s.inspect())+json.dumps(self.s.memory.history())
        self.assertNotIn('You chose Independent journeys', public)

    def test_listener_recall_keeps_advice_distinct_from_the_speaker_choice(self):
        self.command(self.a, 'remember', 'on')
        self.command(self.b, 'remember', 'on')
        cast.response(self.s, self.a, 'a'*32, 'rydel')
        cast.response(self.s, self.b, 'b'*32, 'rydel')
        self.command(self.b, 'converse')
        identifier = self.s.db.execute('SELECT id FROM canonical_dialogues').fetchone()[0]
        self.command(self.a, 'listen', identifier)
        self.command(self.a, 'advise', identifier, 'together')
        self.command(self.b, 'choose', identifier, 'independent')
        text = self.visit(self.a)
        self.assertIn('You suggested Travelling together', text)
        self.assertIn('The speaker chose Independent journeys', text)
        self.assertIn('not your decision', text)
        self.assertNotIn('You chose Independent journeys', text)
        self.assertIn('You chose Independent journeys', self.visit(self.b, 'b'*32))

    def test_remembering_discloses_local_recall_and_can_be_paused_or_erased(self):
        disclosure = self.command(self.a, 'remember', 'on')
        self.assertTrue(any('local choice reminders' in line for line in disclosure))
        cast.response(self.s, self.a, 'a'*32, 'rydel')
        self.choose()
        self.assertIn('You chose Independent journeys', self.visit(self.a))
        self.command(self.a, 'remember', 'off')
        self.assertNotIn('You chose', self.visit(self.a))
        self.command(self.a, 'remember', 'on')
        self.assertIn('You chose Independent journeys', self.visit(self.a))
        self.command(self.a, 'forget')
        self.command(self.a, 'remember', 'on')
        self.assertNotIn('You chose', self.visit(self.a))

    def test_no_retroactive_choice_memory_when_player_did_not_opt_in(self):
        cast.response(self.s, self.a, 'a'*32, 'rydel')
        self.choose()
        self.command(self.a, 'remember', 'on')
        self.assertNotIn('You chose', self.visit(self.a))

    def test_maximum_choice_labels_fit_native_reply_without_truncating_advice(self):
        action = self.f.action(1)
        action['changes']['council'] = dict(mode='speaker', question='Which route?',
            options=dict(independent='A'*48, together='B'*48))
        self.f.apply(action)
        self.command(self.a, 'remember', 'on')
        cast.response(self.s, self.a, 'a'*32, 'rydel')
        cast.response(self.s, self.b, 'b'*32, 'rydel')
        self.command(self.b, 'converse')
        identifier = self.s.db.execute('SELECT id FROM canonical_dialogues').fetchone()[0]
        self.command(self.a, 'listen', identifier)
        self.command(self.a, 'advise', identifier, 'together')
        self.command(self.b, 'choose', identifier, 'independent')
        text = self.visit(self.a)
        self.assertIn('B'*48, text)
        self.assertIn('A'*48, text)
        self.assertIn('not your decision for the group.', text)
        self.assertLessEqual(len(text.encode('ascii')), 240)

    def test_explicit_current_private_answer_keeps_priority_over_local_recall(self):
        self.command(self.a, 'remember', 'on')
        cast.response(self.s, self.a, 'a'*32, 'rydel')
        self.choose()
        action = self.f.action(1)
        action['changes']['conversation'] = dict(rest=dict(
            label='A quiet day', reply='We can leave the bicycles here today.'))
        self.f.apply(action)
        self.command(self.a, 'talk', '2', 'rest')
        text = self.visit(self.a)
        self.assertIn('We can leave the bicycles here today.', text)
        self.assertNotIn('You chose Independent journeys', text)
