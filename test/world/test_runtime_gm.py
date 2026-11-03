"""Durable developer-GM runtime contracts. Model calls are not used by unit tests."""
import tempfile
import unittest
from pathlib import Path

import json
import sys
from unittest.mock import patch

from world import runtime_gm as runtime
from test_gm import Admin, SOURCE, TESTS


class QueueTests(unittest.TestCase):
    def test_intent_is_durable_and_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            queue = runtime.IntentQueue(tmp)
            first = queue.submit('alice', 'Build a garden', 'client-1')
            self.assertEqual(queue.submit('alice', 'Build a garden', 'client-1'), first)
            queue.close()
            queue = runtime.IntentQueue(tmp)
            self.addCleanup(queue.close)
            self.assertEqual(len(queue.status()['requests']), 1)
            self.assertEqual(queue.status()['requests'][0]['status'], 'queued')
            with self.assertRaises(ValueError):
                queue.submit('alice', 'Different request', 'client-1')
            item = queue.claim()
            self.assertEqual(item['id'], first)
            queue.finish(first, 'failed', {'ok': False, 'stage': 'author'})
            self.assertIsNone(queue.claim())
            self.assertEqual(queue.status()['purposes'], {'alice': 'Build a garden'})

    def test_durable_interactions_coalesce_while_intent_runs_without_replay(self):
        def page(seq, player='alice', kind='interaction'):
            return {'ok': True, 'events': [{'seq': seq, 'kind': kind,
                    'data': {'player': player, 'object': 'garden'}}],
                    'cursor': seq, 'has_more': False}
        with tempfile.TemporaryDirectory() as tmp:
            queue = runtime.IntentQueue(tmp)
            # Existing native history is a baseline, never a startup author call.
            self.assertIsNone(queue.observe_events(page(1)))
            queue.submit('alice', 'Explore gently', 'intent')
            queue.claim()
            identifier = queue.observe_events(page(2))
            self.assertIsNotNone(identifier)
            self.assertEqual(queue.observe_events(page(3)), identifier)
            self.assertIsNone(queue.observe_events(page(4, 'bob')))
            self.assertIsNone(queue.observe_events(page(5, kind='deploy')))
            for seq in range(6, 56):
                queue.observe_events(page(seq))
            events = [r for r in queue.status()['requests'] if r['kind'] == 'event']
            self.assertEqual(len(events), 1)
            self.assertEqual(len(events[0]['result']['events']), 32)
            self.assertEqual(events[0]['result']['selected_purposes'], {'alice': 'Explore gently'})
            queue.finish('intent', 'succeeded', {'ok': True})
            self.assertEqual(queue.claim()['id'], identifier)
            queue.close()
            queue = runtime.IntentQueue(tmp)
            self.addCleanup(queue.close)
            queue.recover()
            self.assertIsNone(queue.observe_events(page(55)))
            self.assertIsNone(queue.claim())
            self.assertEqual(queue.event_cursor(), 55)

    def test_event_history_is_bounded_after_acknowledgment(self):
        with tempfile.TemporaryDirectory() as tmp:
            queue = runtime.IntentQueue(tmp)
            self.addCleanup(queue.close)
            queue.submit('alice', 'Explore', 'purpose')
            queue.claim()
            queue.finish('purpose', 'succeeded', {'ok': True})
            def page(seq):
                return {'ok': True, 'events': [{'seq': seq, 'kind': 'interaction',
                        'data': {'player': 'alice'}}], 'cursor': seq, 'has_more': False}
            queue.observe_events(page(1))
            for seq in range(2, 80):
                identifier = queue.observe_events(page(seq))
                self.assertEqual(queue.claim()['id'], identifier)
                queue.finish(identifier, 'succeeded', {'ok': True})
            queue.observe_events({'ok': True, 'events': [], 'cursor': 79, 'has_more': False})
            self.assertEqual(len([r for r in queue.status()['requests'] if r['kind'] == 'event']), 64)
            self.assertEqual(len([r for r in queue.status()['requests'] if r['kind'] == 'intent']), 1)
            self.assertIsNone(queue.claim())

    def test_events_disabled_and_baseline_pagination_are_acknowledged(self):
        with tempfile.TemporaryDirectory() as tmp:
            queue = runtime.IntentQueue(tmp)
            self.addCleanup(queue.close)
            queue.submit('alice', 'Explore', 'purpose')
            queue.claim()
            queue.finish('purpose', 'succeeded', {'ok': True})
            def page(seq, more):
                return {'ok': True, 'events': [{'seq': seq, 'kind': 'interaction',
                        'data': {'player': 'alice'}}], 'cursor': seq, 'has_more': more}
            self.assertIsNone(queue.observe_events(page(1, True)))
            self.assertIsNone(queue.observe_events(page(2, False)))
            self.assertIsNone(queue.observe_events(page(3, False), enqueue=False))
            self.assertIsNone(queue.observe_events(page(3, False)))
            invalid = page(4, False)
            invalid['events'][0]['data']['object'] = 'x' * 5000
            with self.assertRaises(ValueError):
                queue.observe_events(invalid)
            self.assertEqual(queue.event_cursor(), 3)

    def test_position_changes_coalesce_with_pending_native_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            queue = runtime.IntentQueue(tmp)
            self.addCleanup(queue.close)
            queue.submit('alice', 'Explore', 'purpose')
            queue.claim()
            queue.finish('purpose', 'succeeded', {'ok': True})
            queue.observe({'players': [{'id': 'alice', 'x': 1}]})
            identifier = queue.observe({'players': [{'id': 'alice', 'x': 2}]})
            self.assertEqual(queue.observe({'players': [{'id': 'alice', 'x': 3}]}), identifier)
            context = queue.status()['requests'][-1]['result']
            self.assertEqual(context['before']['players'][0]['x'], 1)
            self.assertEqual(context['after']['players'][0]['x'], 3)
            queue.observe_events({'ok': True, 'events': [], 'cursor': 0, 'has_more': False})
            self.assertEqual(queue.observe_events({'ok': True, 'events': [
                {'seq': 1, 'kind': 'interaction', 'data': {'player': 'alice', 'object': 'guide'}}],
                'cursor': 1, 'has_more': False}), identifier)
            self.assertEqual(queue.status()['requests'][-1]['result']['events'][0]['seq'], 1)

    def test_claim_rate_limit_survives_reopen_and_keeps_work_queued(self):
        with tempfile.TemporaryDirectory() as tmp:
            queue = runtime.IntentQueue(tmp)
            queue.submit('alice', 'Explore', 'first')
            with patch('world.runtime_gm.time.time', return_value=100):
                self.assertEqual(queue.claim(min_interval=15)['id'], 'first')
                queue.finish('first', 'succeeded', {'ok': True})
            queue.submit('alice', 'Build', 'second')
            queue.close()
            queue = runtime.IntentQueue(tmp)
            self.addCleanup(queue.close)
            with patch('world.runtime_gm.time.time', return_value=110):
                self.assertIsNone(queue.claim(min_interval=15))
            self.assertEqual(queue.status()['requests'][-1]['status'], 'queued')
            with patch('world.runtime_gm.time.time', return_value=115):
                self.assertEqual(queue.claim(min_interval=15)['id'], 'second')

    def test_recovery_is_terminal_and_does_not_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            queue = runtime.IntentQueue(tmp)
            self.addCleanup(queue.close)
            identifier = queue.submit('alice', 'A peaceful garden', 'recover')
            queue.claim()
            self.assertEqual(queue.recover(), 1)
            self.assertIsNone(queue.claim())
            self.assertEqual(queue.recover(), 0)
            self.assertEqual(queue.status()['requests'][0]['status'], 'interrupted')
            self.assertEqual(queue.submit('alice', 'A peaceful garden', 'recover'), identifier)

    def test_only_explicit_luna_configuration_is_allowed(self):
        for model in (None, '', 'gpt-6-luna', 'openai/gpt-6-luna',
                      'openai-codex/gpt-6.1-sol'):
            with self.subTest(model=model), self.assertRaises(ValueError):
                runtime.validate_config(model, 60, 2)
        runtime.validate_config('openai-codex/gpt-6-luna', 60, 2)
        for timeout in (0, float('nan'), float('inf'), 3601):
            with self.assertRaises(ValueError):
                runtime.validate_config('openai-codex/gpt-6-luna', timeout, 2)
        command = runtime.luna_author_argv('openai-codex/gpt-6-luna', 60)
        self.assertIn('author', command)
        self.assertIn('openai-codex/gpt-6-luna', command)


class RuntimeTests(unittest.TestCase):
    def test_live_intent_uses_pipeline_once_and_records_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            admin = Admin(tmp)
            self.addCleanup(admin.close)
            script = ('import sys,json; p=sys.stdin.read(); '
                      "assert 'Build a garden' in p and 'alice' in p; "
                      'print(json.dumps(' + repr({'source': SOURCE, 'tests': TESTS}) + '))')
            with patch.object(runtime, 'luna_author_argv', return_value=[sys.executable, '-c', script]):
                with runtime.RuntimeGM(tmp, admin.path, model=runtime.MODEL, min_author_interval=0) as worker:
                    worker.queue.submit('alice', 'Build a garden', 'once')
                    result = worker.step()
                    self.assertTrue(result['result']['ok'], result)
                    self.assertEqual(result['status'], 'succeeded')
                    self.assertIsNone(worker.step())
                    self.assertEqual(len([r for r in admin.calls if r['command'] == 'deploy']), 1)
                    with self.assertRaises(ValueError):
                        runtime.RuntimeGM(tmp, admin.path, model=runtime.MODEL, min_author_interval=0)
                with runtime.RuntimeGM(tmp, admin.path, model=runtime.MODEL, min_author_interval=0) as worker:
                    self.assertIsNone(worker.step())
                    self.assertEqual(worker.queue.status()['requests'][0]['status'], 'succeeded')

    def test_observation_ignores_unselected_players_and_own_mechanic_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            queue = runtime.IntentQueue(tmp)
            self.addCleanup(queue.close)
            queue.submit('alice', 'Explore', 'purpose')
            queue.claim()
            queue.finish('purpose', 'succeeded', {'ok': True})
            queue.observe({'players': [{'id': 'alice', 'x': 1}, {'id': 'bob', 'x': 1}], 'error': None})
            self.assertIsNone(queue.observe({'players': [{'id': 'alice', 'x': 1}, {'id': 'bob', 'x': 2}], 'error': 'candidate failed'}))

    def test_events_without_purpose_never_author_and_changes_are_durable(self):
        with tempfile.TemporaryDirectory() as tmp:
            queue = runtime.IntentQueue(tmp)
            self.addCleanup(queue.close)
            first = {'ok': True, 'players': [{'id': 'alice', 'x': 1}], 'revision': 1}
            self.assertIsNone(queue.observe(first))
            queue.submit('alice', 'Explore gently', 'purpose')
            queue.claim()
            queue.finish('purpose', 'succeeded', {'ok': True})
            self.assertIsNone(queue.observe(dict(first, revision=2)))
            changed = dict(first, players=[{'id': 'alice', 'x': 2}])
            identifier = queue.observe(changed)
            self.assertIsNotNone(identifier)
            self.assertIsNone(queue.observe(changed))
            queue.claim()
            queue.recover()
            self.assertIsNone(queue.observe(changed))
            self.assertIsNone(queue.claim())

    def test_failure_is_persisted_and_not_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            admin = Admin(tmp, reject=True)
            self.addCleanup(admin.close)
            script = 'import json; print(json.dumps(' + repr({'source': SOURCE, 'tests': TESTS}) + '))'
            with patch.object(runtime, 'luna_author_argv', return_value=[sys.executable, '-c', script]):
                with runtime.RuntimeGM(tmp, admin.path, model=runtime.MODEL, min_author_interval=0) as worker:
                    worker.queue.submit('alice', 'Make a garden', 'bad')
                    result = worker.step()
                    self.assertEqual(result['status'], 'failed')
                    self.assertEqual(result['result']['stage'], 'deploy')
                    visible = worker.queue.status()['runtime']
                    self.assertEqual(visible['stage'], 'deploy')
                    self.assertIn('candidate tests failed', visible['error'])
                    self.assertEqual(visible['report_path'], result['result']['report_path'])
                    self.assertIsNone(worker.step())
                with runtime.RuntimeGM(tmp, admin.path, model=runtime.MODEL, min_author_interval=0) as worker:
                    self.assertIsNone(worker.step())
                    self.assertEqual(worker.queue.status()['requests'][0]['status'], 'failed')
            self.assertEqual(len([r for r in admin.calls if r['command'] == 'deploy']), 1)

    def test_followup_author_sees_verified_previous_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            admin = Admin(tmp)
            self.addCleanup(admin.close)
            script = 'import json; print(json.dumps(' + repr({'source': SOURCE, 'tests': TESTS}) + '))'
            with patch.object(runtime, 'luna_author_argv', return_value=[sys.executable, '-c', script]):
                with runtime.RuntimeGM(tmp, admin.path, model=runtime.MODEL, min_author_interval=0) as worker:
                    worker.queue.submit('alice', 'Make a garden', 'first')
                    self.assertEqual(worker.step()['status'], 'succeeded')
                    worker.queue.submit('alice', 'Expand the garden', 'second')
                    result = worker.step()
                    context = json.loads(Path(result['result']['context_path']).read_text())
                    self.assertEqual(context['runtime']['previous_source'], SOURCE)
                    self.assertEqual(context['runtime']['model'], runtime.MODEL)

    def test_cli_roundtrip_and_unavailable_once_exits_nonzero(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            base = [sys.executable, '-B', '-m', 'world.runtime_gm']
            submit = ['submit', '--state-dir', tmp, '--player', 'alice', '--intent',
                      'Explore gently', '--request-id', 'cli-once']
            first = subprocess.run(base + submit, capture_output=True, text=True)
            second = subprocess.run(base + submit, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stdout)
            self.assertEqual(first.stdout, second.stdout)
            result = subprocess.run(base + ['run', '--state-dir', tmp, '--socket',
                str(Path(tmp) / 'absent.sock'), '--model', runtime.MODEL, '--once'],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stdout)
            status = subprocess.run(base + ['status', '--state-dir', tmp], capture_output=True, text=True)
            self.assertEqual(json.loads(status.stdout)['requests'][0]['status'], 'queued')

    def test_step_consumes_host_native_events_and_authors_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            admin = Admin(tmp)
            self.addCleanup(admin.close)
            with patch.object(runtime, 'luna_author_argv', return_value=[]), patch('world.gm.author_and_deploy', return_value={'ok': True}) as author:
                with runtime.RuntimeGM(tmp, admin.path, model=runtime.MODEL, min_author_interval=0) as worker:
                    worker.queue.submit('alice', 'Grow flowers', 'intent')
                    self.assertEqual(worker.step()['status'], 'succeeded')
                    admin.events.append({'seq': 4, 'kind': 'interaction', 'data': {'player': 'alice', 'object': 'garden'}})
                    self.assertEqual(worker.step()['status'], 'succeeded')
                    self.assertEqual(author.call_args.kwargs['runtime_context']['observed_event']['events'][0]['seq'], 4)
                    self.assertIsNone(worker.step())
                    self.assertEqual(author.call_count, 2)

    def test_last_good_source_survives_event_history_pruning(self):
        with tempfile.TemporaryDirectory() as tmp:
            admin = Admin(tmp)
            self.addCleanup(admin.close)
            script = 'import json; print(json.dumps(' + repr({'source': SOURCE, 'tests': TESTS}) + '))'
            with patch.object(runtime, 'luna_author_argv', return_value=[sys.executable, '-c', script]):
                with runtime.RuntimeGM(tmp, admin.path, model=runtime.MODEL, min_author_interval=0) as worker:
                    worker.queue.submit('alice', 'Explore', 'first')
                    self.assertEqual(worker.step()['status'], 'succeeded')
                    # A long run of failed reactions prunes the successful event
                    # record. Active source continuity must not depend on history.
                    worker.queue.db.execute("UPDATE requests SET kind='event'")
                    for seq in range(1, 67):
                        worker.queue.db.execute("INSERT INTO requests(id,player,text,kind,status,created) VALUES(?, '', '', 'event', 'failed', 0)", (str(seq),))
                    worker.queue.db.commit()
                    worker.queue.observe_events({'ok': True, 'events': [], 'cursor': 0, 'has_more': False})
                    self.assertFalse(any(row['id'] == 'first' for row in worker.queue.status()['requests']))
                    inspection = {'module_hash': admin.hash}
                    self.assertEqual(worker._previous_source(inspection), SOURCE)
                with runtime.RuntimeGM(tmp, admin.path, model=runtime.MODEL) as worker:
                    self.assertEqual(worker._previous_source(inspection), SOURCE)

    def test_actual_adapter_subprocess_and_sandbox_deployment_restart(self):
        import os
        from world.server import WorldServer
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tools = root / 'trusted-test-tools'
            tools.mkdir()
            script = tools / 'codex'
            initial = "def update(context, state):\n    return {'state': dict(state, kept='human-purpose'), 'tiles': []}\n"
            evolved = "def update(context, state):\n    return {'state': dict(state, evolved=True), 'tiles': []}\n"
            response = tools / 'response.json'
            response.write_text(json.dumps({'source': initial, 'tests': TESTS}))
            script.write_text('#!/usr/bin/python3\n' + '''import json,sys
from pathlib import Path
args = sys.argv[1:]
if args == ['--version']:
    print('codex-cli 0.156.1')
elif args == ['debug', 'models', '--bundled']:
    print(json.dumps({'models': [{'slug': 'gpt-6-luna', 'shell_type': 'unified_exec'}]}))
else:
    assert args[0] == 'exec' and args[args.index('--model')+1] == 'gpt-6-luna'
    assert '--ignore-user-config' in args and 'features.shell_tool=false' in args
    prompt = sys.stdin.read()
    assert 'selected_purposes' in prompt and 'human-purpose' in prompt
    response = Path(__file__).with_name('response.json').read_text()
    print(json.dumps({'type': 'item.completed', 'item': {'type': 'agent_message', 'text': response}}))
    print(json.dumps({'type': 'turn.completed'}))
''')
            script.chmod(0o700)
            path = str(root / 'transport' / 'world.sock')
            server = WorldServer(path, root).start()
            try:
                with patch.dict(os.environ, {'PATH': str(tools) + os.pathsep + os.environ['PATH']}):
                    with runtime.RuntimeGM(root, path, model=runtime.MODEL, min_author_interval=0) as worker:
                        worker.queue.submit('alice', 'human-purpose: explore peacefully', 'actual-adapter')
                        first = worker.step()
                        self.assertEqual(first['status'], 'succeeded', first)
                        self.assertEqual(first['result']['provenance'], 'subprocess_response')
                        self.assertEqual(first['result']['author']['returncode'], 0)
                        self.assertEqual(server.inspect()['state'], {'kept': 'human-purpose'})
                        response.write_text(json.dumps({'source': evolved, 'tests': TESTS}))
                        worker.queue.submit('alice', 'human-purpose: evolve exploration', 'migration')
                        second = worker.step()
                        self.assertEqual(second['status'], 'succeeded', second)
                        state = server.inspect()['state']
                        self.assertEqual(state, {'kept': 'human-purpose', 'evolved': True})
                        digest = server.inspect()['module_hash']
                        response.write_text(json.dumps({'source': SOURCE, 'tests': 'def test_bad():\n    assert False\n'}))
                        worker.queue.submit('alice', 'human-purpose: bad candidate', 'rejected')
                        rejected = worker.step()
                        self.assertEqual(rejected['status'], 'failed', rejected)
                        self.assertEqual(server.inspect()['module_hash'], digest)
                        self.assertEqual(server.inspect()['state'], state)
            finally:
                server.close()
            server = WorldServer(path, root).start()
            try:
                self.assertEqual(server.inspect()['module_hash'], digest)
                self.assertEqual(server.inspect()['state'], state)
                with runtime.RuntimeGM(root, path, model=runtime.MODEL, min_author_interval=0) as worker:
                    self.assertIsNone(worker.step())
                    self.assertEqual(worker._previous_source(server.inspect()), evolved)
            finally:
                server.close()

    def test_inspection_outage_preserves_queued_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            with runtime.RuntimeGM(tmp, Path(tmp) / 'absent.sock', model=runtime.MODEL) as worker:
                worker.queue.submit('alice', 'Explore gently', 'outage')
                self.assertIsNone(worker.step())
                status = worker.queue.status()
                self.assertEqual(status['requests'][0]['status'], 'queued')
                self.assertEqual(status['runtime']['state'], 'inspection_failed')


class AdapterTests(unittest.TestCase):
    def test_author_disables_host_tools_and_ambient_context(self):
        argv = runtime.codex_argv(runtime.MODEL, Path('/candidate/catalog.json'))
        for value in ('features.shell_tool=false', 'features.view_image=false',
                      'features.multi_agent=false', 'features.js_repl=false',
                      'features.code_mode=false', 'features.plugins=false',
                      'features.skip_host_skill_discovery=true', 'project_doc_max_bytes=0',
                      'web_search="disabled"', 'model_catalog_json="/candidate/catalog.json"'):
            self.assertIn(value, argv)
        model = {'slug': 'gpt-6-luna', 'shell_type': 'unified_exec',
                 'apply_patch_tool_type': 'freeform', 'experimental_supported_tools': ['clock'],
                 'base_instructions': 'trusted bundled instructions'}
        catalog = runtime.tool_disabled_catalog(json.dumps({'models': [model]}))
        self.assertEqual(len(catalog['models']), 1)
        self.assertEqual(catalog['models'][0]['shell_type'], 'disabled')
        self.assertIsNone(catalog['models'][0]['apply_patch_tool_type'])
        self.assertEqual(catalog['models'][0]['experimental_supported_tools'], [])
        with self.assertRaises(ValueError):
            runtime.tool_disabled_catalog('{"models": []}')

    def test_unexpected_tool_execution_is_not_an_author_success(self):
        events = [ {'type': 'item.completed', 'item': {'type': 'command_execution', 'command': 'cat /host/file'}},
                   {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': json.dumps({'source': SOURCE, 'tests': TESTS})}},
                   {'type': 'turn.completed'} ]
        with self.assertRaises(ValueError):
            runtime.decode_codex('\n'.join(json.dumps(item) for item in events))

    def test_nested_author_stays_in_parent_process_group(self):
        from world import gm
        import os
        script = 'import os; print(os.getpgrp())'
        evidence = {}
        output = gm._run_author([sys.executable, '-c', script], 'prompt', 2, evidence,
                                Path.cwd(), inherit_process_group=True)
        self.assertEqual(int(output), os.getpgrp())

    def test_codex_adapter_accepts_only_completed_json_author_message(self):
        response = {'source': SOURCE, 'tests': TESTS}
        events = [ {'type': 'thread.started'},
                   {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': json.dumps(response)}},
                   {'type': 'turn.completed'} ]
        wire = '\n'.join(json.dumps(item) for item in events)
        self.assertEqual(runtime.decode_codex(wire), response)
        with self.assertRaises(ValueError):
            runtime.decode_codex(wire + '\n' + json.dumps({'type': 'turn.failed'}))
        with self.assertRaises(ValueError):
            runtime.decode_codex(json.dumps(events[1]))
        with self.assertRaises(ValueError):
            runtime.decode_codex('not json')
        argv = runtime.codex_argv(runtime.MODEL, Path('/catalog.json'))
        self.assertIn('--ignore-user-config', argv)
        self.assertIn('--ephemeral', argv)
        self.assertIn('gpt-6-luna', argv)
        self.assertNotIn('--dangerously-bypass-approvals-and-sandbox', argv)
        with self.assertRaises(ValueError):
            runtime.codex_argv('openai-codex/gpt-6.1-sol', Path('/catalog.json'))


if __name__ == '__main__':
    unittest.main()
