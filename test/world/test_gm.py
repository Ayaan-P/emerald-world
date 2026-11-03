"""Developer GM orchestration tests using local admin sockets, never an LLM account."""
import hashlib
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest

from world import gm


SOURCE = "def update(context, state):\n    return {'state': state, 'tiles': []}\n"
TESTS = "def test_update():\n    assert update({'players': []}, {})['tiles'] == []\n"


class Admin:
    def __init__(self, root, reject=False, production=False):
        self.path = str(Path(root) / 'world.sock')
        admin_path = self.path + '.admin'
        if production:
            (Path(root) / 'transport').mkdir(exist_ok=True)
            self.path = str(Path(root) / 'transport' / 'world.sock')
            admin_path = str(Path(root) / 'admin.sock')
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.listener.bind(admin_path)
        self.listener.listen()
        self.listener.settimeout(.1)
        self.stop = threading.Event()
        self.calls = []
        self.events = []
        self.hash = None
        self.reject = reject
        self.mismatch = False
        self.wrapped = False
        self.thread = threading.Thread(target=self.run)
        self.thread.start()

    def run(self):
        while not self.stop.is_set():
            try:
                conn, _ = self.listener.accept()
            except socket.timeout:
                continue
            with conn, conn.makefile('rb') as stream:
                request = json.loads(stream.readline())
                self.calls.append(request)
                if request['command'] == 'inspect':
                    response = {'ok': True, 'players': [{'id': 'alice', 'x': 7, 'y': 9,
                                'token': 'do-not-copy'}], 'revision': 18,
                                'state': {'door': False}, 'module_hash': 'wrong' if self.mismatch else self.hash}
                    if self.wrapped:
                        response = {'ok': True, 'data': response}
                elif request['command'] == 'events_since':
                    events = [event for event in self.events if event['seq'] > request['cursor']][:request['limit']]
                    response = {'ok': True, 'events': events,
                                'cursor': events[-1]['seq'] if events else request['cursor'], 'has_more': False}
                elif self.reject:
                    response = {'ok': False, 'error': 'candidate tests failed'}
                else:
                    self.hash = hashlib.sha256(Path(request['source_path']).read_bytes()).hexdigest()
                    response = {'ok': True, 'module_hash': self.hash, 'revision': 19}
                conn.sendall(json.dumps(response).encode() + b'\n')

    def close(self):
        self.stop.set()
        self.thread.join(2)
        self.listener.close()


class GMTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.admin = Admin(self.root)

    def tearDown(self):
        self.admin.close()
        self.tmp.cleanup()

    def test_author_gets_live_context_and_deployment_is_verified(self):
        prompts = []
        def author(prompt):
            prompts.append(prompt)
            return {'source': SOURCE, 'tests': TESTS}
        report = gm.author_and_deploy(self.root, self.admin.path, 'invent a cooperative door', author)
        self.assertTrue(report['ok'], report)
        self.assertEqual([r['command'] for r in self.admin.calls], ['inspect', 'deploy', 'inspect'])
        self.assertIn('invent a cooperative door', prompts[0])
        self.assertIn('alice', prompts[0])
        self.assertIn('update(context, state)', prompts[0])
        self.assertIn('global', prompts[0])
        self.assertNotIn('do-not-copy', prompts[0])
        self.assertEqual(report['source_sha256'], self.admin.hash)
        self.assertEqual(report['provenance'], 'injected_callable')
        self.assertEqual(report['tests']['status'], 'passed_by_admin')
        self.assertEqual(Path(report['source_path']).read_text(), SOURCE)
        self.assertEqual(Path(report['report_path']).read_text(), json.dumps(report, indent=2, sort_keys=True) + '\n')
        self.assertFalse(Path(report['source_path']).stat().st_mode & 0o222)
        self.assertNotIn('do-not-copy', Path(report['context_path']).read_text())

    def test_prompt_documents_live_objects_and_interactions_without_forced_goals(self):
        prompt = gm._prompt('choose exploration', {'ok': True})
        self.assertIn('objects', prompt)
        self.assertIn('interactions', prompt)
        self.assertIn('gfx', prompt)
        self.assertIn('7 or 8', prompt)
        self.assertIn('Do not add mortality', prompt)
        self.assertIn('Do not call tools', prompt)
        self.assertIn('"seq": 42, "player": "alice", "object": "welcome"', prompt)
        self.assertIn('no type or object_id field', prompt)
        self.assertIn('top-level objects key', prompt)
        self.assertIn('not rendered', prompt)

    def test_author_context_supplies_exact_bounded_catalog_fixtures(self):
        from world.build_catalog import catalog_maps, validate_tile
        from unittest.mock import patch
        maps = list(catalog_maps())
        inspection = {'ok': True, 'players': [dict(group=g, num=n) for g, n in [(1, 4)] + maps],
                      'tiles': [[1, 4, 6, 5, 0, 0]], 'objects': [], 'state': {}}
        prompts = []
        def author(prompt):
            prompts.append(prompt)
            return {'source': SOURCE, 'tests': TESTS}
        real_admin_request = gm.admin_request
        def inspect_override(path, request, timeout):
            if request['command'] == 'inspect' and self.admin.hash is None:
                return inspection
            return real_admin_request(path, request, timeout)
        with patch.object(gm, 'admin_request', side_effect=inspect_override):
            report = gm.author_and_deploy(self.root, self.admin.path, 'preserve tiles', author)
        self.assertTrue(report['ok'], report)
        context = json.loads(Path(report['context_path']).read_text())
        constraints = context['author_constraints']
        self.assertLessEqual(len(constraints['maps']), 8)
        self.assertLess(len(json.dumps(constraints)), 12000)
        self.assertTrue(constraints['maps_truncated'])
        current = constraints['maps'][0]
        self.assertEqual((current['group'], current['num']), (1, 4))
        catalog = catalog_maps()[(1, 4)]
        for key in ('width', 'height', 'primary_count', 'secondary_count'):
            self.assertEqual(current[key], catalog[key])
        self.assertEqual(current['primary_count'], 8)
        for entry in constraints['maps']:
            fixture = entry['tile_fixture']
            validate_tile([fixture[k] for k in ('group', 'num', 'x', 'y', 'metatile', 'collision')])
        self.assertIn(json.dumps(constraints, sort_keys=True), prompts[0])
        self.assertIn('not supplied to update', prompts[0])
        self.assertIn('including test fixtures', prompts[0])
        self.assertIn('512 <= metatile < 512 + secondary_count', prompts[0])

    def test_catalog_fixture_stages_but_original_unsafe_metatile_still_fails(self):
        from world.mechanics import MechanicRuntime
        constraints = gm._author_constraints({'data': {'players': [{'group': 1, 'num': 4}]}})
        tile = constraints['maps'][0]['tile_fixture']
        source = "def update(context, state):\n    return {'state': state, 'tiles': context.get('tiles', [])}\n"
        tests = "def test_preserve():\n    tiles = " + repr([tile]) + "\n    assert update({'tiles': tiles}, {})['tiles'] == tiles\n"
        directory = self.root / 'candidates'
        directory.mkdir()
        source_path, tests_path = directory / 'fixture.py', directory / 'fixture_tests.py'
        source_path.write_text(source)
        tests_path.write_text(tests)
        sandbox = MechanicRuntime(self.root)
        sandbox.stage(source_path, tests_path)
        # Replay the live failure shape, not a repair of the model artifact.
        unsafe = dict(tile, x=6, y=5, metatile=12)
        tests_path.write_text(tests.replace(repr([tile]), repr([unsafe])))
        with self.assertRaisesRegex(ValueError, 'metatile outside target tileset allocations'):
            sandbox.stage(source_path, tests_path)
        empty = gm._author_constraints({'ok': True})
        self.assertEqual(len(empty['maps']), 1)
        self.assertFalse(empty['maps_truncated'])
        self.assertEqual(empty['update_context_fixture'],
                         {'players': [], 'tick': 0, 'revision': 0, 'interactions': []})

    def test_prompt_mixed_interaction_example_preserves_npc_and_cursor_in_sandbox(self):
        from world.mechanics import MechanicRuntime
        prompt = gm._prompt('preserve guide', {'ok': True})
        self.assertIn('kind=trainer', prompt)
        self.assertIn('target', prompt)
        self.assertIn('signal', prompt)
        loop = prompt.split('```python\n', 1)[1].split('```', 1)[0]
        npc = dict(id='guide', group=1, num=4, x=5, y=5, gfx=7, text='Explore!')
        source = ('def update(context, state):\n    state = dict(state)\n' +
                  ''.join('    ' + line + '\n' for line in loop.splitlines()) +
                  "    return {'state': state, 'tiles': [], 'objects': " + repr([npc]) + '}\n')
        tests = '''def test_mixed():
    events = [
        {'seq': 42, 'player': 'alice', 'object': 'guide', 'group': 1, 'num': 4, 'x': 5, 'y': 5},
        {'seq': 43, 'kind': 'trainer', 'player': 'alice', 'target': 'bob', 'signal': 'explore', 'group': 1, 'num': 4, 'x': 6, 'y': 5}]
    result = update({'players': [], 'interactions': events}, {'kept': True})
    assert result['state'] == {'kept': True, 'last_seq': 43}
    assert result['objects'][0]['id'] == 'guide'
    assert update({'interactions': events}, result['state']) == result
    assert update({}, result['state']) == result
'''
        candidates = self.root / 'candidates'
        candidates.mkdir()
        source_path, tests_path = candidates / 'mixed.py', candidates / 'mixed_tests.py'
        source_path.write_text(source)
        tests_path.write_text(tests)
        MechanicRuntime(self.root).stage(source_path, tests_path)

    def test_real_subprocess_author_reads_prompt_on_stdin(self):
        script = "import sys,json; p=sys.stdin.read(); assert 'alice' in p; print(json.dumps(" + repr({'source': SOURCE, 'tests': TESTS}) + "))"
        report = gm.author_and_deploy(self.root, self.admin.path, 'open a door', [sys.executable, '-c', script])
        self.assertTrue(report['ok'], report)
        self.assertEqual(report['provenance'], 'subprocess_response')
        self.assertEqual(report['author']['returncode'], 0)

    def test_cli_external_response_records_provenance_without_model_claim(self):
        import subprocess
        response = self.root / 'response.json'
        response.write_text(json.dumps({'source': SOURCE, 'tests': TESTS}))
        proc = subprocess.run([sys.executable, '-B', '-m', 'world.gm', '--state-dir', str(self.root),
                               '--socket', self.admin.path, '--request', 'cooperative door',
                               '--response-file', str(response)], capture_output=True, text=True, timeout=5)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        report = json.loads(proc.stdout)
        self.assertTrue(report['ok'])
        self.assertEqual(report['provenance'], 'external_response')
        self.assertNotIn('started', report['author'])

    def test_candidate_files_cannot_escape_via_candidates_symlink(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (self.root / 'candidates').symlink_to(outside, target_is_directory=True)
        report = gm.author_and_deploy(self.root, self.admin.path, 'door', lambda p: {'source': SOURCE, 'tests': TESTS})
        self.assertFalse(report['ok'], report)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertNotIn('deploy', [r['command'] for r in self.admin.calls])

    def test_failed_candidate_does_not_claim_test_success(self):
        self.admin.reject = True
        report = gm.author_and_deploy(self.root, self.admin.path, 'door', lambda p: {'source': SOURCE, 'tests': TESTS})
        self.assertFalse(report['ok'])
        self.assertEqual(report['tests']['status'], 'admin_rejected_candidate')
        self.assertEqual(report['deploy']['error'], 'candidate tests failed')
        self.assertIn('candidate tests failed', report['error'])
        self.assertEqual(len(self.admin.calls), 2)

    def test_generated_code_is_written_not_executed_by_controller(self):
        marker = self.root / 'must-not-exist'
        source = "from pathlib import Path\nPath(" + repr(str(marker)) + ").touch()\n" + SOURCE
        report = gm.author_and_deploy(self.root, self.admin.path, 'door', lambda p: {'source': source, 'tests': TESTS})
        self.assertTrue(report['ok'], report)
        self.assertFalse(marker.exists())

    def test_repeated_requests_create_distinct_readonly_versions(self):
        reports = [gm.author_and_deploy(self.root, self.admin.path, 'door', lambda p: {'source': SOURCE, 'tests': TESTS}) for _ in range(2)]
        self.assertTrue(all(r['ok'] for r in reports))
        self.assertNotEqual(reports[0]['source_path'], reports[1]['source_path'])
        self.assertEqual(Path(reports[0]['source_path']).read_text(), SOURCE)

    def test_timeout_is_bounded_and_records_real_process_exit(self):
        import time
        start = time.monotonic()
        report = gm.author_and_deploy(self.root, self.admin.path, 'door',
                                      [sys.executable, '-c', 'import time; time.sleep(60)'], timeout=.2)
        self.assertFalse(report['ok'])
        self.assertIn('timeout', report['error'])
        self.assertTrue(report['author']['started'])
        self.assertLess(report['author']['returncode'], 0)
        self.assertLess(time.monotonic() - start, 3)
        self.assertEqual([r['command'] for r in self.admin.calls], ['inspect'])

    def test_output_limit_aborts_noisy_author(self):
        report = gm.author_and_deploy(self.root, self.admin.path, 'door',
                                      [sys.executable, '-c', "import sys; sys.stdout.write('x'*2000000)"], timeout=2)
        self.assertFalse(report['ok'])
        self.assertIn('output exceeds limit', report['error'])
        self.assertLessEqual(report['author']['stdout_bytes'], gm.MAX_RESPONSE + 8192)

    def test_malformed_or_oversized_author_response_never_deploys(self):
        for response in ('not JSON', {'source': SOURCE}, {'source': SOURCE, 'tests': ''},
                         {'source': 'x' * (gm.MAX_SOURCE + 1), 'tests': TESTS}):
            with self.subTest(response_type=type(response).__name__):
                report = gm.author_and_deploy(self.root, self.admin.path, 'door', lambda p: response)
                self.assertFalse(report['ok'])
        self.assertTrue(all(r['command'] == 'inspect' for r in self.admin.calls))

    def test_shell_string_is_not_accepted_as_an_author_command(self):
        report = gm.author_and_deploy(self.root, self.admin.path, 'door', 'touch /tmp/not-allowed')
        self.assertFalse(report['ok'])
        self.assertIn('argv list', report['error'])

    def test_oversized_request_rejected_before_inspection(self):
        report = gm.author_and_deploy(self.root, self.admin.path, 'x' * (gm.MAX_REQUEST + 1), [])
        self.assertFalse(report['ok'])
        self.assertEqual(self.admin.calls, [])
        self.assertIsNone(report['request'])

    def test_lock_rejects_concurrent_authors(self):
        import fcntl
        directory = self.root / 'gm'
        directory.mkdir()
        with (directory / '.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            report = gm.author_and_deploy(self.root, self.admin.path, 'door', [])
        self.assertFalse(report['ok'])
        self.assertIn('active', report['error'])
        self.assertEqual(self.admin.calls, [])

    def test_missing_executable_is_honest_failure(self):
        report = gm.author_and_deploy(self.root, self.admin.path, 'door', ['/no-such-author-executable'])
        self.assertFalse(report['ok'])
        self.assertFalse(report['author']['started'])
        self.assertIsNone(report['author']['returncode'])

    def test_deployment_reply_is_not_treated_as_active_module_verification(self):
        self.admin.mismatch = True
        report = gm.author_and_deploy(self.root, self.admin.path, 'door', lambda p: {'source': SOURCE, 'tests': TESTS})
        self.assertFalse(report['ok'])
        self.assertEqual(report['stage'], 'verify')
        self.assertIn('hash', report['error'])

    def test_nested_inspection_data_is_supported(self):
        self.admin.wrapped = True
        report = gm.author_and_deploy(self.root, self.admin.path, 'door', lambda p: {'source': SOURCE, 'tests': TESTS})
        self.assertTrue(report['ok'], report)

    def test_timeout_kills_author_descendant_process(self):
        import time
        marker = self.root / 'late-child-effect'
        script = ('import os,time; pid=os.fork(); '
                  + "time.sleep(1) if pid == 0 else time.sleep(60); "
                  + "open(" + repr(str(marker)) + ", 'w').write('escaped')")
        report = gm.author_and_deploy(self.root, self.admin.path, 'door', [sys.executable, '-c', script], timeout=.2)
        self.assertFalse(report['ok'])
        time.sleep(1.1)
        self.assertFalse(marker.exists(), 'descendant survived process group cleanup')

    @unittest.skipUnless(Path('/usr/bin/bwrap').is_file() and Path('/usr/bin/python3').is_file(),
                         'real runtime requires system Python and bubblewrap')
    def test_real_world_server_stages_tests_and_reports_active_hash(self):
        import subprocess
        script = '''import json,sys
from world.server import WorldServer
from world.gm import author_and_deploy
root, path, source, tests = json.load(sys.stdin)
server = WorldServer(path, root).start()
try:
    report = author_and_deploy(root, path, 'integration test mechanic',
                               lambda prompt: {'source': source, 'tests': tests})
    print(json.dumps(report))
finally:
    server.close()
'''
        proc = subprocess.run(['/usr/bin/python3', '-B', '-c', script],
                              input=json.dumps([str(self.root), str(self.root / 'real.sock'), SOURCE, TESTS]),
                              capture_output=True, text=True, timeout=15)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads(proc.stdout)
        self.assertTrue(report['ok'], report)
        self.assertEqual(report['verification']['module_hash'], hashlib.sha256(SOURCE.encode()).hexdigest())
        self.assertEqual(report['tests']['status'], 'passed_by_admin')

    def test_production_admin_socket_is_outside_game_transport(self):
        self.admin.close()
        self.admin = Admin(self.root, production=True)
        report = gm.author_and_deploy(self.root, self.admin.path, 'door', lambda p: {'source': SOURCE, 'tests': TESTS})
        self.assertTrue(report['ok'], report)
        self.assertEqual([r['command'] for r in self.admin.calls], ['inspect', 'deploy', 'inspect'])
        self.assertFalse(Path(self.admin.path + '.admin').exists())


if __name__ == '__main__':
    unittest.main()
