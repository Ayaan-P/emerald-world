"""Opt-in player runtime tests. Provider fixtures are not real model verification."""
import copy
import json
import sys
import threading
import time
import unittest

if __package__:
    from .test_player import NativeSocket, reply
else:
    from test_player import NativeSocket, reply


def observation(seq=8, target='hermes'):
    return {'id': 1, 'ok': True, 'state': {'frame': 10, 'world': {
        'trainer': 'hermes', 'meeting': {'seq': seq, 'target': target,
        'player': 'ayaan', 'signal': 'explore'}}}}


class Clock:
    now = 0.0
    def __call__(self):
        return self.now


class RuntimeTests(unittest.TestCase):
    def test_baseline_target_dedupe_periodic_and_persistent_socket(self):
        from world.player_runtime import RuntimePlayer
        clock = Clock()
        state = observation()
        calls = []
        def handler(conn, request):
            reply(conn, request, state=state['state'])
        def policy(context):
            calls.append(copy.deepcopy(context))
            return {'actions': [{'buttons': ['A'], 'frames': 1}]}
        with NativeSocket(handler) as server:
            with RuntimePlayer(server.path, policy, interval=10, min_model_interval=5,
                               clock=clock) as runtime:
                self.assertEqual(runtime.step()['status'], 'baseline')
                self.assertEqual(runtime.step()['status'], 'idle')
                state['state']['world']['meeting']['seq'] = 9
                self.assertEqual(runtime.step()['status'], 'acted')
                self.assertEqual(calls[0]['trigger'], 'meeting')
                clock.now = 1
                state['state']['world']['meeting']['seq'] = 10
                self.assertEqual(runtime.step()['status'], 'idle')
                clock.now = 5
                self.assertEqual(runtime.step()['status'], 'acted')
                clock.now = 15
                self.assertEqual(runtime.step()['status'], 'acted')
                self.assertEqual(calls[-1]['trigger'], 'periodic')
                self.assertEqual(server.connections, 1)
                self.assertEqual([r['op'] for r in server.requests].count('press'), 3)
                self.assertTrue(all(set(r) <= {'id', 'op', 'buttons', 'frames'} for r in server.requests))

    def test_policy_over_30_seconds_keeps_lease_on_owner_thread_with_observe_only(self):
        from world.player_runtime import RuntimePlayer
        clock = Clock()
        started, release = threading.Event(), threading.Event()
        observed = threading.Condition()
        times, thread_ids, statuses = [], [], []
        last_request = [0.0]
        def handler(conn, request):
            if clock.now - last_request[0] >= 30:
                conn.shutdown(2)
                return
            last_request[0] = clock.now
            reply(conn, request, state=observation()['state'])
            if request['op'] == 'observe':
                with observed:
                    times.append(clock.now)
                    observed.notify_all()
        def policy(_):
            started.set()
            release.wait(3)
            return {'actions': [{'buttons': ['A'], 'frames': 1}]}
        with NativeSocket(handler) as server:
            # Even an operator's long poll interval must not exceed the native
            # 30 second lease. No wall-time sleeps are needed to cross it.
            with RuntimePlayer(server.path, policy, interval=1, min_model_interval=1,
                               poll_interval=3600, clock=clock) as runtime:
                runtime.step()
                clock.now = 1
                for name in ('observe', 'press'):
                    method = getattr(runtime.client, name)
                    def record(*args, _method=method, **kwargs):
                        thread_ids.append(threading.get_ident())
                        return _method(*args, **kwargs)
                    setattr(runtime.client, name, record)
                owner = threading.Thread(target=lambda: statuses.append(runtime.step()))
                owner.start()
                try:
                    self.assertTrue(started.wait(1))
                    for now in range(6, 47, 5):
                        with observed:
                            clock.now = now
                            self.assertTrue(observed.wait_for(lambda: times[-1] == now, timeout=1),
                                            'inference must renew the native idle lease')
                        self.assertNotIn('press', [r['op'] for r in server.requests])
                finally:
                    release.set()
                    owner.join(2)
                self.assertFalse(owner.is_alive())
                self.assertEqual(statuses, [{'status': 'acted', 'completed': 1}])
                self.assertGreaterEqual(times[-1] - 1, 45)
                self.assertEqual(server.connections, 1)
                self.assertEqual(set(thread_ids), {owner.ident})
                self.assertEqual([r['op'] for r in server.requests].count('press'), 1)

    def test_run_caps_idle_polling_below_30_second_native_lease(self):
        from world.player_runtime import RuntimePlayer
        clock = Clock()
        waits = []
        class Stop(threading.Event):
            def wait(self, timeout=None):
                assert timeout is not None
                waits.append(timeout)
                clock.now += timeout
                if clock.now >= 40:
                    self.set()
                return self.is_set()
        def handler(conn, request):
            reply(conn, request, state=observation()['state'])
        with NativeSocket(handler) as server:
            runtime = RuntimePlayer(server.path, lambda _: self.fail('no policy due'),
                                    interval=3600, poll_interval=3600, stop=Stop(), clock=clock)
            runtime.run()
            self.assertLessEqual(max(waits), 5)
            self.assertGreaterEqual(len(server.requests), 8)
            self.assertTrue(all(request['op'] == 'observe' for request in server.requests))
            self.assertEqual(server.connections, 1)

    def test_run_polls_until_policy_stop_and_closes_socket(self):
        from world.player_runtime import RuntimePlayer
        stop = threading.Event()
        calls = []
        def handler(conn, request):
            reply(conn, request, state=observation()['state'])
        def policy(context):
            calls.append(context)
            stop.set()
            return {'actions': [{'buttons': ['A'], 'frames': 1}]}
        with NativeSocket(handler) as server:
            runtime = RuntimePlayer(server.path, policy, interval=.01,
                                    min_model_interval=.01, poll_interval=.005, stop=stop)
            thread = threading.Thread(target=runtime.run)
            thread.start()
            thread.join(1)
            self.assertFalse(thread.is_alive())
            self.assertEqual(len(calls), 1)
            self.assertTrue(runtime._closed)
            self.assertNotIn('press', [r['op'] for r in server.requests])

    def test_batch_is_fully_validated_before_first_press_and_failure_backoff(self):
        from world.player_runtime import RuntimePlayer
        invalid = [
            {'actions': [{'buttons': ['A'], 'frames': 1}, {'buttons': ['B'], 'frames': 121}]},
            {'actions': [{'buttons': ['UP'], 'frames': True}]},
            {'actions': [], 'code': 'evil'},
            '{"actions":[],"actions":[]}',
            {'actions': [{'buttons': ['A', 'A'], 'frames': 1}]},
            {'actions': [{'buttons': [], 'frames': 1}] * 9},
            {'actions': [], 'reason': 'x' * 1025},
            'not JSON',
        ]
        for response in invalid:
            with self.subTest(response=str(response)[:100]):
                clock = Clock()
                calls = []
                def handler(conn, request):
                    reply(conn, request, state=observation()['state'])
                def policy(context):
                    calls.append(context)
                    return response
                with NativeSocket(handler) as server:
                    with RuntimePlayer(server.path, policy, interval=1,
                                       min_model_interval=5, clock=clock) as runtime:
                        runtime.step()
                        clock.now = 5
                        self.assertEqual(runtime.step()['status'], 'policy_failed')
                        clock.now = 6
                        self.assertEqual(runtime.step()['status'], 'idle')
                        self.assertEqual(len(calls), 1)
                        self.assertNotIn('press', [r['op'] for r in server.requests])

    def test_lost_press_ack_halts_without_replay(self):
        from world.player_runtime import RuntimePlayer
        clock = Clock()
        def handler(conn, request):
            if request['op'] == 'press':
                conn.shutdown(2)
            else:
                reply(conn, request, state=observation()['state'])
        with NativeSocket(handler) as server:
            with RuntimePlayer(server.path, lambda _: {'actions': [
                    {'buttons': ['A'], 'frames': 1}] * 2}, interval=1,
                    min_model_interval=1, clock=clock) as runtime:
                runtime.step()
                clock.now = 2
                self.assertEqual(runtime.step()['status'], 'action_outcome_unknown')
                self.assertEqual(runtime.step()['status'], 'stopped')
                self.assertEqual(sum(r['op'] == 'press' for r in server.requests), 1)

    def test_stop_during_hung_callable_and_endpoint_exclusion(self):
        from world.player_runtime import RuntimePlayer
        clock = Clock()
        started, release = threading.Event(), threading.Event()
        def policy(_):
            started.set()
            release.wait(3)
            return {'actions': [{'buttons': ['A'], 'frames': 1}]}
        def handler(conn, request):
            reply(conn, request, state=observation()['state'])
        with NativeSocket(handler) as server:
            with RuntimePlayer(server.path, policy, interval=1,
                               min_model_interval=1, clock=clock) as runtime:
                other = RuntimePlayer(server.path, policy)
                try:
                    with self.assertRaises(BlockingIOError):
                        other.__enter__()
                finally:
                    other.close()
                runtime.step()
                clock.now = 2
                thread = threading.Thread(target=runtime.step)
                thread.start()
                self.assertTrue(started.wait(1))
                runtime.stop.set()
                thread.join(1)
                release.set()
                self.assertFalse(thread.is_alive())
                self.assertNotIn('press', [r['op'] for r in server.requests])

    def test_runtime_cancels_provider_on_stop_and_deadline(self):
        from world.player_runtime import RuntimePlayer
        for shutdown in ('stop', 'timeout'):
            with self.subTest(shutdown=shutdown):
                started, cancelled, finished = threading.Event(), threading.Event(), threading.Event()
                class Policy:
                    def __call__(self, _):
                        started.set()
                        cancelled.wait(2)
                        finished.set()
                        return {'actions': []}
                    def cancel(self):
                        cancelled.set()
                clock = Clock()
                def handler(conn, request):
                    reply(conn, request, state=observation()['state'])
                with NativeSocket(handler) as server:
                    with RuntimePlayer(server.path, Policy(), interval=1,
                                       min_model_interval=1, clock=clock, model_timeout=.1) as runtime:
                        runtime.step()
                        clock.now = 2
                        worker = threading.Thread(target=runtime.step)
                        worker.start()
                        self.assertTrue(started.wait(1))
                        if shutdown == 'stop':
                            runtime.stop.set()
                        worker.join(1)
                        self.assertFalse(worker.is_alive())
                        self.assertTrue(cancelled.is_set())
                        self.assertTrue(finished.wait(.1))

    def test_identity_change_cannot_redirect_controller(self):
        from world.player_runtime import RuntimePlayer
        state = observation()
        clock = Clock()
        calls = []
        def handler(conn, request):
            reply(conn, request, state=state['state'])
        with NativeSocket(handler) as server:
            with RuntimePlayer(server.path, lambda ctx: calls.append(ctx) or {'actions': []},
                               clock=clock) as runtime:
                runtime.step()
                state['state']['world']['trainer'] = 'ayaan'
                clock.now = 60
                self.assertEqual(runtime.step()['status'], 'identity_changed')
                self.assertEqual(runtime.step()['status'], 'stopped')
                self.assertEqual(calls, [])

    def test_other_target_never_wakes_and_sequence_regression_never_replays(self):
        from world.player_runtime import RuntimePlayer
        state = observation()
        clock = Clock()
        calls = []
        def handler(conn, request):
            reply(conn, request, state=state['state'])
        with NativeSocket(handler) as server:
            with RuntimePlayer(server.path, lambda ctx: calls.append(ctx) or {'actions': []},
                               clock=clock) as runtime:
                runtime.step()
                state['state']['world']['meeting'] = observation(10, 'other')['state']['world']['meeting']
                runtime.step()
                state['state']['world']['meeting'] = observation(9)['state']['world']['meeting']
                runtime.step()
                self.assertEqual(calls, [])


class PolicyTests(unittest.TestCase):
    def test_codex_decoder_rejects_tool_activity_and_invalid_protocol(self):
        from world.player_runtime import decode_player_codex
        def event(kind, **fields):
            return json.dumps({'type': kind, **fields})
        message = event('item.completed', item={'type': 'agent_message',
                                               'text': '{"actions":[]}'})
        complete = event('turn.completed', usage={})
        good = '\n'.join([event('thread.started', thread_id='x'), event('turn.started'), message, complete])
        self.assertEqual(decode_player_codex(good), {'actions': []})
        for wire in [message, message + '\n' + complete + '\n' + event('mcp.call'),
                     event('item.started', item={'type': 'command_execution'}) + '\n' + good,
                     good + '\n' + event('turn.failed'),
                     message + '\n' + message + '\n' + complete]:
            with self.subTest(wire=wire):
                with self.assertRaises(ValueError):
                    decode_player_codex(wire)

    def test_command_bridge_real_subprocess_json_timeout_output_bound_and_stop(self):
        from world.player_runtime import CommandPolicy
        good = CommandPolicy([sys.executable, '-c',
                              'import sys,json; x=json.load(sys.stdin); print(json.dumps({"actions":[]}))'])
        self.assertEqual(good({'trigger': 'periodic'}), {'actions': []})
        for source in ['import time; time.sleep(20)', 'print("x" * 200000)',
                       'import sys; sys.stderr.write("secret"); sys.exit(1)']:
            policy = CommandPolicy([sys.executable, '-c', source], timeout=.15,
                                   max_output_bytes=16384)
            start = time.monotonic()
            with self.assertRaises((ValueError, TimeoutError)) as caught:
                policy({})
            self.assertNotIn('secret', str(caught.exception))
            self.assertLess(time.monotonic() - start, 2)
        stop = threading.Event()
        stop.set()
        with self.assertRaises(ValueError):
            CommandPolicy([sys.executable, '-c', 'print("should not run")'], stop=stop)({})

    def test_codex_explicit_model_and_hardened_argv(self):
        from world.player_runtime import CodexPolicy
        from world.runtime_gm import MODEL
        with self.assertRaises(ValueError):
            CodexPolicy(None)
        with self.assertRaises(ValueError):
            CodexPolicy('unreviewed/model')
        policy = CodexPolicy(MODEL)
        self.assertEqual(policy.model, MODEL)
        argv = policy.argv('/tmp/catalog.json')
        self.assertIn('--ignore-user-config', argv)
        self.assertIn('features.shell_tool=false', argv)
        self.assertIn('features.computer_use=false', argv)
        self.assertIn('features.plugins=false', argv)
        self.assertIn('--json', argv)

    def test_codex_adapter_runs_version_catalog_and_model_with_player_prompt(self):
        from unittest.mock import patch
        from world.player_runtime import CodexPolicy
        from world.runtime_gm import MODEL, CODEX_VERSION
        calls = []
        def invoke(argv, text, timeout, stop, bound, cwd):
            calls.append((argv, text, timeout, bound))
            if argv == ['codex', '--version']:
                return CODEX_VERSION.encode()
            if argv == ['codex', 'debug', 'models', '--bundled']:
                return b'{"models":[{"slug":"gpt-6-luna","shell_type":"default"}]}'
            from pathlib import Path
            catalog_arg = next(a for a in argv if a.startswith('model_catalog_json='))
            path = Path(json.loads(catalog_arg.split('=', 1)[1]))
            catalog = json.loads(path.read_text())
            self.assertEqual(catalog['models'][0]['shell_type'], 'disabled')
            self.assertIsNone(catalog['models'][0]['apply_patch_tool_type'])
            self.assertIn('ordinary Pokemon native player', text)
            self.assertIn('UNTRUSTED GAME DATA', text)
            self.assertNotIn('source and tests', text)
            return (json.dumps({'type': 'item.completed', 'item': {'type': 'agent_message',
                    'text': '{"actions":[{"buttons":["UP"],"frames":16}]}'}}) + '\n' +
                    json.dumps({'type': 'turn.completed'})).encode()
        with patch('world.player_runtime._invoke', invoke):
            response = CodexPolicy(MODEL)({'observation': observation(), 'trigger': 'meeting'})
        self.assertEqual(response['actions'][0], {'buttons': ['UP'], 'frames': 16})
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(0 < c[2] <= 120 for c in calls))

    def test_cli_requires_explicit_model(self):
        from world.player_runtime import main
        with self.assertRaises(SystemExit) as caught:
            main(['--endpoint', '/unused'])
        self.assertEqual(caught.exception.code, 2)

    def test_direct_script_cli_help_without_pythonpath(self):
        import os
        import subprocess
        from pathlib import Path
        script = Path(__file__).resolve().parents[2] / 'world' / 'player_runtime.py'
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        result = subprocess.run([sys.executable, str(script), '--help'], cwd='/tmp',
                                env=env, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--model', result.stdout)


if __name__ == '__main__':
    unittest.main()
