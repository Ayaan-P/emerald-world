"""Read-only event seam, using native socket fixtures and deterministic clocks."""
import copy
import unittest


def observation(**world_changes):
    world = {'trainer': 'hermes', 'connected': True, 'peers': [],
             'meeting': {'seq': 8, 'player': 'ayaan', 'target': 'hermes', 'signal': 'explore'},
             'dialogue_active': True, 'dialogue_object': 'ayaan',
             'dialogue_text': "ayaan\nLet's explore together!", 'interaction_seq': 1}
    world.update(world_changes)
    return {'id': 1, 'ok': True, 'state': {'frame': 10, 'map': [0, 9],
                                            'battle': 0, 'world': world}}


class FakeClient:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.closed = 0
        self.calls = 0

    def observe(self):
        self.calls += 1
        value = next(self.responses)
        if isinstance(value, BaseException):
            raise value
        return copy.deepcopy(value)

    def close(self):
        self.closed += 1


class PlayerEventTests(unittest.TestCase):
    def test_initial_snapshot_and_idle_do_not_trigger_historic_greeting(self):
        from world.player_events import PlayerObserver
        client = FakeClient(observation(), observation())
        observer = PlayerObserver(client, trainer='hermes')
        self.assertEqual(observer.poll(), [])
        self.assertEqual(observer.poll(), [])
        self.assertEqual(client.calls, 2)

    def test_targeted_meeting_requires_strictly_new_sequence(self):
        from world.player_events import PlayerObserver
        client = FakeClient(observation(), observation(meeting={'seq': 9, 'player': 'ayaan',
                    'target': 'other', 'signal': 'explore'}),
                    observation(meeting={'seq': 9, 'player': 'ayaan', 'target': 'hermes', 'signal': 'explore'}),
                    observation(meeting={'seq': 10, 'player': 'ayaan', 'target': 'hermes', 'signal': 'explore'}),
                    observation())
        observer = PlayerObserver(client, trainer='hermes')
        self.assertEqual([observer.poll() for _ in range(3)], [[], [], []])
        event, = observer.poll()
        self.assertEqual(event['type'], 'meeting')
        self.assertEqual(event['data'], {'seq': 10, 'player': 'ayaan', 'target': 'hermes', 'signal': 'explore'})
        self.assertEqual(observer.poll(), [])

    def test_public_changes_are_projected_without_private_envelope(self):
        from world.player_events import PlayerObserver
        first = observation(dialogue_active=False, meeting=None)
        second = observation(meeting=None, peers=[{'trainer': 'ayaan', 'map': [0, 9],
                                                   'pos': [7, 17], 'token': 'PRIVATE'}])
        third = copy.deepcopy(second)
        third['state']['map'] = [0, 10]
        third['state']['battle'] = 1
        third['state']['world']['peers'][0]['pos'] = [8, 17]
        third['state']['world']['peers'][0]['map'] = [0, 10]
        third['state']['world']['dialogue_text'] = 'Follow me!'
        fourth = observation(dialogue_active=False, meeting=None)
        observer = PlayerObserver(FakeClient(first, second, third, fourth), trainer='hermes')
        self.assertEqual(observer.poll(), [])
        opened = observer.poll()
        self.assertEqual({e['type'] for e in opened}, {'dialogue_opened', 'peer_arrived'})
        dialogue = next(e for e in opened if e['type'] == 'dialogue_opened')
        self.assertEqual(dialogue['data']['text'], "ayaan\nLet's explore together!")
        self.assertTrue(dialogue['data']['untrusted'])
        self.assertNotIn('PRIVATE', str(opened))
        changed = observer.poll()
        self.assertEqual({e['type'] for e in changed},
                         {'dialogue_changed', 'peer_moved', 'map_changed', 'battle_changed'})
        self.assertIn('peer_departed', {e['type'] for e in observer.poll()})

    def test_reconnect_backoff_and_baseline_do_not_replay_meeting(self):
        from world.player import PlayerError
        from world.player_events import PlayerObserver
        sleeps = []
        client = FakeClient(observation(), PlayerError('/private/path token=SECRET'),
                            PlayerError('SECRET'), observation(meeting={'seq': 20, 'player': 'ayaan',
                                 'target': 'hermes', 'signal': 'explore'}), observation())
        observer = PlayerObserver(client, trainer='hermes', interval=0.25,
                                  backoff_initial=1, backoff_max=2, sleep=sleeps.append,
                                  clock=lambda: 42.0)
        self.assertEqual(observer.poll(), [])
        event, = observer.poll()
        self.assertEqual(event['type'], 'disconnected')
        self.assertEqual(event['time'], 42.0)
        self.assertNotIn('SECRET', str(event))
        self.assertEqual(observer.poll(), [])
        self.assertEqual([e['type'] for e in observer.poll()], ['reconnected'])
        self.assertEqual(observer.poll(), [])
        self.assertEqual(sleeps, [0.25, 1, 2, 0.25])
        self.assertGreaterEqual(client.closed, 2)

    def test_world_disconnect_reconnect_suppresses_stale_differences(self):
        from world.player_events import PlayerObserver
        observer = PlayerObserver(FakeClient(observation(), observation(connected=False),
                    observation(connected=False), observation(dialogue_text='Offline update'),
                    observation(dialogue_text='Offline update')), trainer='hermes', sleep=lambda _: None)
        self.assertEqual(observer.poll(), [])
        self.assertEqual([e['type'] for e in observer.poll()], ['disconnected'])
        self.assertEqual(observer.poll(), [])
        self.assertEqual([e['type'] for e in observer.poll()], ['reconnected'])
        self.assertEqual(observer.poll(), [])

    def test_identity_is_required_and_mismatch_is_fatal(self):
        from world.player_events import PlayerObserver, PlayerIdentityError
        for name in ('', '../hermes', 'hermes\n', True, 'a' * 65):
            with self.subTest(name=name), self.assertRaises(ValueError):
                PlayerObserver(FakeClient(), trainer=name)
        client = FakeClient(observation(trainer='ayaan'))
        observer = PlayerObserver(client, trainer='hermes')
        with self.assertRaises(PlayerIdentityError):
            observer.poll()
        self.assertEqual(client.closed, 1)
        with self.assertRaises(RuntimeError):
            observer.poll()

    def test_malformed_data_fails_closed_and_is_paced(self):
        from world.player_events import PlayerObserver
        bad = [None, {}, {'ok': True, 'state': []}, observation(peers=[{}]),
               observation(meeting={'seq': True}), observation(dialogue_active='yes'),
               observation(peers=[{'trainer': 'x', 'map': [0, 9], 'pos': [1, 2]}] * 65)]
        sleeps = []
        observer = PlayerObserver(FakeClient(*bad), trainer='hermes', sleep=sleeps.append,
                                  backoff_initial=1, backoff_max=4)
        events = [event for _ in bad for event in observer.poll()]
        self.assertEqual([e['type'] for e in events], ['disconnected'])
        self.assertEqual(sleeps, [1, 2, 4, 4, 4, 4])

    def test_public_text_is_bounded_and_sensitive_strings_are_suppressed(self):
        import json
        from world.player_events import PlayerObserver, MAX_EVENT_BYTES
        responses = [observation(dialogue_active=False, meeting=None),
                     observation(meeting=None, dialogue_text='Hello ' * 300, token='SECRET',
                                 screenshot='/private/profile/file')]
        for text in ('token=SECRET /private/profile/file', 'C:\\private\\file',
                     'Bearer SECRET', 'sk-' + 'x' * 50):
            responses.append(observation(meeting=None, dialogue_text=text))
        observer = PlayerObserver(FakeClient(*responses), trainer='hermes', sleep=lambda _: None)
        observer.poll()
        event, = observer.poll()
        self.assertLessEqual(len(event['data']['text']), 512)
        self.assertTrue(event['data']['truncated'])
        self.assertLessEqual(len(json.dumps(event).encode()), MAX_EVENT_BYTES)
        for _ in responses[2:]:
            for event in observer.poll():
                self.assertNotIn('SECRET', str(event))
                self.assertNotIn('private', str(event))
                self.assertNotIn('sk-', str(event))

    def test_watch_real_player_client_emits_only_flushed_jsonl_events(self):
        import io
        import json
        from world.player import PlayerClient
        from world.player_events import PlayerObserver, watch
        if __package__:
            from .test_player import NativeSocket, reply
        else:
            from test_player import NativeSocket, reply
        responses = iter([observation(dialogue_active=False, meeting=None),
                          observation(meeting=None), observation(meeting=None)])
        def handler(conn, request):
            reply(conn, request, state=next(responses)['state'])
        class Output(io.StringIO):
            flushes = 0
            def flush(self):
                self.flushes += 1
        output = Output()
        with NativeSocket(handler) as server:
            client = PlayerClient(server.path, timeout=1)
            observer = PlayerObserver(client, trainer='hermes', sleep=lambda _: None)
            self.assertEqual(watch(observer, max_polls=3, stream=output), 0)
            self.assertIsNone(client._conn)
            self.assertEqual([r['op'] for r in server.requests], ['observe'] * 3)
        events = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([e['type'] for e in events], ['dialogue_opened'])
        self.assertEqual(output.flushes, 1)

    def test_cli_watch_uses_explicit_endpoint_and_own_identity(self):
        import subprocess
        import sys
        import json
        if __package__:
            from .test_player import NativeSocket, reply
        else:
            from test_player import NativeSocket, reply
        from pathlib import Path
        script = Path(__file__).resolve().parents[2] / 'world' / 'player_events.py'
        seq = iter([8, 9])
        def handler(conn, request):
            native = observation(meeting={'seq': next(seq), 'player': 'ayaan',
                                          'target': 'hermes', 'signal': 'explore'})
            reply(conn, request, state=native['state'])
        with NativeSocket(handler) as server:
            result = subprocess.run([sys.executable, str(script), '--endpoint', server.path,
                      '--trainer', 'hermes', '--interval', '0.05', 'watch', '--max-polls', '2'],
                      cwd='/tmp', capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual([json.loads(line)['type'] for line in result.stdout.splitlines()], ['meeting'])
            self.assertEqual([r['op'] for r in server.requests], ['observe', 'observe'])
        missing = subprocess.run([sys.executable, str(script), '--trainer', 'hermes', 'watch'],
                                 capture_output=True, text=True, timeout=5)
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn('--endpoint', missing.stderr)

    def test_ctrl_c_closes_client(self):
        import io
        from unittest.mock import patch
        from world.player_events import main
        client = FakeClient(KeyboardInterrupt())
        with patch('world.player_events.PlayerClient', return_value=client), patch('sys.stdout', io.StringIO()):
            self.assertEqual(main(['--endpoint', '/explicit/player.sock', '--trainer', 'hermes', 'watch']), 130)
        self.assertEqual(client.closed, 1)

    def test_configuration_limits_reject_busy_loops_and_nonfinite_delays(self):
        from world.player_events import PlayerObserver
        for kwargs in ({'interval': 0}, {'interval': float('nan')}, {'interval': True},
                       {'backoff_max': float('inf')}, {'backoff_initial': 0.1},
                       {'backoff_max': 0.25}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                PlayerObserver(FakeClient(), trainer='hermes', **kwargs)
        observer = PlayerObserver(FakeClient(), trainer='hermes')
        for limit in (0, -1, True, 1.5):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                list(observer.events(max_polls=limit))

    def test_unicode_dialogue_still_fits_jsonl_byte_bound(self):
        import io
        import json
        from world.player_events import PlayerObserver, watch, MAX_EVENT_BYTES
        output = io.StringIO()
        observer = PlayerObserver(FakeClient(observation(dialogue_active=False),
                    observation(dialogue_text='🌍' * 512)), trainer='hermes', sleep=lambda _: None)
        self.assertEqual(watch(observer, max_polls=2, stream=output), 0)
        line = output.getvalue()
        self.assertLessEqual(len(line.encode()), MAX_EVENT_BYTES)
        self.assertTrue(json.loads(line)['data']['truncated'])

    def test_consumer_cannot_mutate_dedupe_baseline(self):
        from world.player_events import PlayerObserver
        peer = {'trainer': 'ayaan', 'map': [0, 9], 'pos': [7, 17]}
        observer = PlayerObserver(FakeClient(observation(peers=[]), observation(peers=[peer]),
                    observation(peers=[peer])), trainer='hermes', sleep=lambda _: None)
        observer.poll()
        event, = observer.poll()
        event['data']['pos'][0] = 999
        self.assertEqual(observer.poll(), [])

    def test_real_oversized_response_is_closed_without_raw_output(self):
        from world.player import PlayerClient
        from world.player_events import PlayerObserver, MAX_OBSERVATION_BYTES
        if __package__:
            from .test_player import NativeSocket
        else:
            from test_player import NativeSocket
        sleeps = []
        def handler(conn, request):
            conn.sendall(b'{"token":"SECRET","padding":"' + b'x' * (MAX_OBSERVATION_BYTES + 1))
        with NativeSocket(handler) as server:
            client = PlayerClient(server.path, timeout=1, max_response_bytes=MAX_OBSERVATION_BYTES)
            observer = PlayerObserver(client, trainer='hermes', sleep=sleeps.append)
            first = observer.poll()
            self.assertEqual([e['type'] for e in first], ['disconnected'])
            self.assertNotIn('SECRET', str(first))
            self.assertIsNone(client._conn)
            self.assertEqual(observer.poll(), [])
            self.assertEqual(sleeps, [0.5])
            observer.close()
            self.assertTrue(all(r['op'] == 'observe' for r in server.requests))

    def test_oversized_envelope_and_duplicate_peers_are_not_partial_events(self):
        from world.player_events import PlayerObserver, MAX_OBSERVATION_BYTES
        huge = observation()
        huge['private'] = 'SECRET' * MAX_OBSERVATION_BYTES
        duplicate = {'trainer': 'ayaan', 'map': [0, 9], 'pos': [1, 2]}
        observer = PlayerObserver(FakeClient(observation(), huge,
                    observation(peers=[duplicate, duplicate])), trainer='hermes', sleep=lambda _: None)
        observer.poll()
        self.assertEqual([e['type'] for e in observer.poll()], ['disconnected'])
        self.assertEqual(observer.poll(), [])


if __name__ == '__main__':
    unittest.main()
