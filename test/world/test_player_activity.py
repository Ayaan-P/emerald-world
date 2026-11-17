"""Player projection through the real authority and launcher bridge."""
import json
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
import test_landmark_survey as fixture
from world.session import SessionError
from world.web_launcher import LauncherBridge


class PlayerActivityTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.LandmarkSurveyTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.s = self.f.s
        self.bridge = LauncherBridge.__new__(LauncherBridge)
        self.bridge.lock = threading.RLock()
        self.bridge.engine = 'expansion-native'
        self.bridge.session = SimpleNamespace(state=Path('/fixture/local'), server=self.s, remote_trainer='Scout')
        self.bridge.local_expeditions = lambda: [dict(key='local')]

    def call(self, action='player_activity_read', **payload):
        return self.bridge.action(action, dict(world='local', **payload))

    def test_own_survey_only_and_refresh_does_not_write(self):
        self.f.command('/explore start')
        self.f.state(self.f.conn,15,20)
        other = self.f.connect('Other')
        self.s.landmark_survey.handle(other,'/explore start')
        before = self.s.db.total_changes
        value = self.call()
        self.assertEqual(self.s.db.total_changes,before)
        self.assertEqual(value['trainer'],'Scout')
        self.assertEqual(value['survey']['visited'],['camp'])
        self.assertEqual(len(value['survey']['landmarks']),4)
        self.assertNotIn('Other',json.dumps(value))
        self.assertNotIn('token',json.dumps(value))
        self.assertNotIn('Survey complete',json.dumps(value))

    def test_next_objective_is_authoritative_nearest_with_exact_scope(self):
        self.f.command('/explore start')
        sites = self.f.report['landmarks'][1:-1]
        target = sites[-1]
        self.f.state(self.f.conn, target['x'] - 2, target['y'])
        value = self.call()['survey']
        self.assertEqual(value['next_objective']['id'], target['id'])
        self.assertEqual(value['next_objective']['revision'], self.f.revision)
        self.assertIn('Next: ' + target['id'], ' '.join(self.s.landmark_survey.lines(self.f.conn)))
        self.f.conn['cave_ack'] = '0' * 64
        self.assertIsNone(self.call()['survey']['next_objective'])
        self.assertFalse(self.call()['survey']['in_scope'])
        import time
        self.f.conn['cave_ack'] = self.f.revision
        self.f.conn['state_time'] = time.monotonic() + 60
        self.assertIsNone(self.call()['survey']['next_objective'])
        self.assertFalse(self.call()['survey']['in_scope'])

    def test_recap_is_latest_public_commits_not_private_notes(self):
        self.f.f.bury_bridge_history()
        self.f.send(self.f.conn,'STATE '+str(self.f.conn['seq']+1)+' 0 9 8 8 4 7 1 '+'a'*16+' '+'b'*16)
        self.s._replace_cave(fixture.fixtures.BLOB, label='Most recent area')
        result = self.call()
        self.assertEqual(result['recap'][0]['title'],'Area activated')
        self.assertIn('Most recent area',result['recap'][0]['details'])
        self.assertNotIn('not-for-recall',json.dumps(result))
        self.assertLessEqual(len(result['recap']),8)

    def test_public_recap_labels_only_explicitly_shared_discovery(self):
        self.f.command('/explore start'); self.f.state(self.f.conn,15,20)
        private = self.call()['recap']
        self.f.command('/explore share camp confirm')
        public = self.call()['recap']
        self.assertEqual(public[0]['title'],'Landmark discovery shared')
        self.assertIn('camp near (15, 20).',public[0]['details'])
        self.assertNotIn('Scout',json.dumps(public))
        self.assertNotEqual(public,private)

    def test_resident_offer_reuses_current_guild_goal_without_claiming_acceptance(self):
        import test_character_offers as offers
        f = offers.CharacterOfferTests(); f.setUp(); self.addCleanup(f.doCleanups)
        self.bridge.session.server = f.server
        self.bridge.session.remote_trainer = 'Alice'
        value = self.call()
        self.assertEqual(value['offers'][0]['name'],'Field Researcher')
        self.assertEqual(value['offers'][0]['destination'],'Littleroot Town')
        self.assertEqual(value['guild']['goals'],[])
        f.fixture.command('chronicle on')
        f.accept()
        value = self.call()
        self.assertEqual(value['guild']['goals'][0]['target'],2)
        self.assertFalse(value['guild']['goals'][0]['complete'])
        self.assertNotIn('Bob',json.dumps(value))

    def test_named_adventure_bridge_uses_real_preview_and_confirmed_apply(self):
        self.s.peers.clear()
        before = self.s.db.total_changes
        catalogue = self.call('adventure_read')
        self.assertEqual(catalogue['adventures'][0]['label'],'Lantern Trail Outpost')
        review = self.call('adventure_preview',adventure='lantern-trail')
        self.assertEqual(self.s.db.total_changes,before)
        self.assertTrue(review['token'])
        with self.assertRaises(SessionError): self.call('adventure_apply',token=review['token'],confirmed=False)
        applied = self.call('adventure_apply',token=review['token'],confirmed=True)
        self.assertTrue(applied['saved'])
        self.assertEqual(self.s.shared_cave.identity,applied['registered_revision'])
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM survey_sessions').fetchone()[0],0)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM survey_publications').fetchone()[0],0)
        self.assertTrue(self.call('adventure_read')['adventures'][0]['installed'])

    def test_hosted_adventure_rejects_identity_overrides_before_transport(self):
        calls = []
        self.bridge.hosted = SimpleNamespace(adventure_action=lambda *args:calls.append(args))
        for payload in ({'world':'hosted-remote','trainer':'Other'}, {'world':'hosted-remote','plan':{}}, {'world':'hosted-remote','token':'x'}):
            with self.assertRaises(SessionError): self.bridge.action('adventure_read',payload)
        self.assertEqual(calls,[])

    def test_hosted_adventure_passes_exact_owner_id_without_launcher_prefix(self):
        calls = []
        self.bridge.hosted = SimpleNamespace(adventure_action=lambda *args:calls.append(args))
        self.bridge.action('adventure_read',dict(world='hosted-0123456789abcdef'))
        self.assertEqual(calls,[('adventure_read',{'world':'0123456789abcdef'})])
        with self.assertRaises(SessionError): self.bridge.action('adventure_read',dict(world='hosted-not-an-id'))

    def test_authenticated_control_can_read_saved_own_progress_without_native_presence(self):
        from unittest.mock import MagicMock
        from world.player_activity import snapshot
        self.f.command('/explore start'); self.f.state(self.f.conn,15,20)
        self.s.peers.clear()
        client = MagicMock()
        client.__enter__.return_value = client
        client._request.return_value = dict(ok=True,activity=snapshot(self.s,'Scout'))
        selected = []
        self.bridge.session._intent_client = lambda trainer: selected.append(trainer) or client
        result = self.call()
        self.assertEqual(result['survey']['visited'],['camp'])
        self.assertEqual(selected,['Scout'])
        client._request.assert_called_once_with({'command':'player_activity'})
        client._request.return_value = dict(ok=True,activity=dict(result,trainer='Other'))
        with self.assertRaises(SessionError): self.call()

    def test_identity_and_world_cannot_be_selected_from_browser(self):
        for payload in ({'trainer':'Other'},{'identity':'Other'},{'world':'elsewhere'}):
            with self.assertRaises(SessionError):
                self.bridge.action('player_activity_read',{'world':'local',**payload})
        self.bridge.session.remote_trainer = None
        with self.assertRaises(SessionError): self.call()
        self.bridge.session.remote_trainer = 'Scout'
        self.f.conn['closing'] = True
        with self.assertRaises(SessionError): self.call()


if __name__ == '__main__': unittest.main()
