"""Real pinned-service owner admission for the built-in adventure catalogue."""
import http.client
import json
import ssl
import unittest
import test_hosting as hosting_fixture


class HostedAdventureTests(unittest.TestCase):
    def setUp(self):
        from world.hosting import HostingService
        self.fixture = hosting_fixture.HostingTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.manager = self.fixture.manager()
        self.addCleanup(self.manager.close)
        self.service = HostingService(self.manager, ('127.0.0.1', 0)).start()
        self.addCleanup(self.service.close)
        access = self.manager.create_account()
        self.manager.enroll(access['token'], 'a'*64)
        self.world = self.manager.create_world('a'*64, 'Product world', 'Alice', 'product')['world']['id']

    def call(self, method, suffix='', body=None, token=None):
        context = ssl.create_default_context(cafile=str(self.fixture.cert))
        conn = http.client.HTTPSConnection('localhost', self.service.address[1], context=context, timeout=15)
        try:
            data = None if body is None else json.dumps(body)
            headers = {'Authorization': 'Bearer ' + (token or 'a'*64)}
            if body is not None:
                headers['Content-Type'] = 'application/json'
            conn.request(method, '/v1/worlds/' + self.world + '/adventure' + suffix, data, headers)
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    def test_owner_can_read_actual_catalogue_without_mutating_world(self):
        status, value = self.call('GET')
        self.assertEqual(status, 200, value)
        self.assertEqual(value['adventures'][0]['id'], 'lantern-trail')
        self.assertFalse(value['adventures'][0]['installed'])
        server = self.manager.running[self.world][0]
        self.assertIsNone(server.candidate)
        self.assertIsNone(server.shared_cave)
        self.assertNotIn('a'*64, json.dumps(value))
    def test_owner_can_review_named_adventure_without_applying(self):
        status, value = self.call('POST', '/preview', {'adventure': 'lantern-trail'})
        self.assertEqual(status, 200, value.get('error'))
        self.assertEqual(value['adventure'], 'lantern-trail')
        self.assertRegex(value['token'], '^[0-9a-f]{48}$')
        self.assertRegex(value['proposed_revision'], '^[0-9a-f]{64}$')
        self.assertNotIn('proposed_rows', value)
        self.assertNotIn('plan', value)
        self.assertNotIn('outcomes', value)
        self.assertLessEqual(len(json.dumps(value).encode()), 16384)
        server = self.manager.running[self.world][0]
        self.assertIsNone(server.candidate)
        self.assertIsNone(server.shared_cave)
    def test_reviewed_owner_apply_commits_actual_adventure_and_can_read_it_back(self):
        status, preview = self.call('POST', '/preview', {'adventure': 'lantern-trail'})
        self.assertEqual(status, 200, preview.get('error'))
        status, value = self.call('POST', '/apply', {'token': preview['token'], 'confirmed': True})
        self.assertEqual(status, 200, value.get('error'))
        self.assertTrue(value['saved'])
        server = self.manager.running[self.world][0]
        self.assertEqual(server.shared_cave.identity, value['registered_revision'])
        self.assertIsNotNone(server.candidate)
        status, current = self.call('GET')
        self.assertEqual(status, 200)
        self.assertTrue(current['adventures'][0]['installed'])
        self.assertEqual(set(current['residents']), {'Mira', 'Ivo', 'Ren'})
    def test_pinned_owner_client_can_read_review_and_apply(self):
        from world.hosting_client import HostingClient
        client = HostingClient(dict(kind='host-profile', version=1,
                                    endpoint=dict(host='localhost', port=self.service.address[1]),
                                    pin=self.fixture.pin, token='a'*64))
        self.assertTrue(callable(getattr(client, 'read_adventures', None)), 'Missing owner adventure client')
        self.assertFalse(client.read_adventures(self.world)['adventures'][0]['installed'])
        preview = client.preview_adventure(self.world, 'lantern-trail')
        saved = client.apply_adventure(self.world, preview['token'], confirmed=True)
        self.assertTrue(saved['saved'])
        self.assertTrue(client.read_adventures(self.world)['adventures'][0]['installed'])
    def test_launcher_owner_adapter_reuses_pinned_profile_and_exact_world_id(self):
        from types import SimpleNamespace
        import hashlib
        from world.hosting_client import write_private
        from world.hosting_ui import HostedLauncher
        root = self.fixture.root/'launcher'
        root.mkdir(mode=0o700)
        session = SimpleNamespace(root=root, status='')
        hosted = HostedLauncher(session)
        profile = dict(kind='host-profile', version=1,
                       endpoint=dict(host='localhost', port=self.service.address[1]),
                       pin=self.fixture.pin, token='a'*64)
        write_private(hosted.profile, profile)
        write_private(hosted.marker, {'profile_sha256': hashlib.sha256(hosted.profile.read_bytes()).hexdigest()})
        self.assertTrue(callable(getattr(hosted, 'adventure_action', None)), 'Missing hosted adventure adapter')
        value = hosted.adventure_action('adventure_read', {'world': self.world})
        self.assertEqual(value['world'], self.world)
        self.assertFalse(value['adventures'][0]['installed'])
        preview = hosted.adventure_action('adventure_preview', {'world': self.world, 'adventure': 'lantern-trail'})
        saved = hosted.adventure_action('adventure_apply', {'world': self.world, 'token': preview['token'], 'confirmed': True})
        self.assertTrue(saved['saved'])
        self.assertEqual(saved['world'], self.world)


if __name__ == '__main__':
    unittest.main()
