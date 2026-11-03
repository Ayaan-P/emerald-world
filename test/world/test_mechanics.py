"""Real bubblewrap integration tests. No sandbox mocks or optional skips."""
import dataclasses
from pathlib import Path
import tempfile
import unittest

from world.mechanics import MechanicError, MechanicRuntime


BASE = "def update(context, state):\n    return {'state': {'count': state.get('count', 0) + 1}, 'tiles': []}\n"
CONTEXT = {'players': [], 'tick': 0, 'revision': 0}


class MechanicsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mechanics-', dir='/home/ayaan/projects/emerald-world-research')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'candidates').mkdir()
        self.runtime = MechanicRuntime(self.root)

    def source(self, text, name='candidate.py'):
        path = self.root / 'candidates' / name
        path.write_text(text)
        return path

    def test_linux_seals_remain_enforced_without_python_header_constants(self):
        import fcntl
        from unittest.mock import patch
        names=('F_ADD_SEALS','F_GET_SEALS','F_SEAL_WRITE','F_SEAL_GROW','F_SEAL_SHRINK','F_SEAL_SEAL')
        missing={key:value for key,value in vars(fcntl).items() if key not in names}
        with patch.dict(fcntl.__dict__,missing,clear=True):
            candidate=self.runtime.stage(self.source(BASE))
            self.assertEqual(self.runtime.run(candidate,CONTEXT,{})['state'],{'count':1})

    def test_missing_kernel_seals_fail_closed_before_candidate_execution(self):
        import fcntl
        from unittest.mock import patch
        real_fcntl=fcntl.fcntl
        def ignore_sealing(fd, command, *args):
            return 0 if command==1033 else real_fcntl(fd,command,*args)
        with patch.object(fcntl,'fcntl',side_effect=ignore_sealing):
            with self.assertRaisesRegex(MechanicError,'seals'):
                self.runtime.stage(self.source(BASE))

    def test_staged_source_is_immutable_and_runs_with_explicit_state(self):
        path = self.source(BASE)
        candidate = self.runtime.stage(path)
        path.write_text('this is not Python')
        state = {'count': 9}
        self.assertEqual(self.runtime.run(candidate, CONTEXT, state), {'state': {'count': 10}, 'tiles': []})
        self.assertEqual(state, {'count': 9})
        self.assertEqual(candidate.source, BASE)
        self.assertEqual(len(candidate.sha256), 64)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            candidate.source = 'changed'

    def test_shared_objects_are_optional_and_validated(self):
        obj = dict(id='guide', group=0, num=1, x=10, y=12, gfx=7,
                   text='Hello trainer!\nWelcome here.')
        result = dict(state={}, tiles=[], objects=[obj])
        candidate = self.runtime.stage(self.source('def update(context,state):\n return ' + repr(result)))
        self.assertEqual(self.runtime.run(candidate, CONTEXT, {}), result)
        for change in ({'x': 999}, {'gfx': 0}, {'text': '$bad'}, {'text': 'x'*29},
                       {'id': '../bad'}, {'x': True}, {'group': 255}):
            with self.subTest(change=change), self.assertRaises(MechanicError):
                self.runtime.stage(self.source('def update(context,state):\n return ' +
                    repr(dict(result, objects=[dict(obj, **change)]))))
        with self.assertRaises(MechanicError):
            self.runtime.stage(self.source('def update(context,state):\n return ' +
                repr(dict(result, objects=[obj, obj]))))

    def test_invalid_results_are_rejected(self):
        tile = {'group': 0, 'num': 0, 'x': 1, 'y': 2, 'metatile': 3, 'collision': 0}
        bad_results = [
            {'state': {}, 'tiles': [dict(tile, x=True)]},
            {'state': {}, 'tiles': [dict(tile, x=1024)]},
            {'state': {}, 'tiles': [dict(tile, y=-1)]},
            {'state': {}, 'tiles': [dict(tile, group=256)]},
            {'state': {}, 'tiles': [dict(tile, num=False)]},
            {'state': {}, 'tiles': [dict(tile, metatile=1024)]},
            {'state': {}, 'tiles': [dict(tile, collision=2)]},
            {'state': {}, 'tiles': [dict(tile, collision=True)]},
            {'state': {}, 'tiles': [dict(tile, extra=0)]},
            {'state': {}, 'tiles': [tile, tile]},
            {'state': {}, 'tiles': [dict(tile, x=i) for i in range(129)]},
            {'state': 'x' * 65536, 'tiles': []},
            {'state': float('nan'), 'tiles': []},
            {'state': {}, 'tiles': 'bad'},
            {'state': {}},
        ]
        for result in bad_results:
            with self.subTest(result=repr(result)[:100]):
                path = self.source('def update(context, state):\n    return ' + repr(result) + '\n')
                with self.assertRaises(MechanicError):
                    self.runtime.stage(path)

    def test_optional_tests_execute_functions_and_unittest_cases(self):
        tests = self.source("import unittest\ndef test_counter():\n    assert update({}, {'count': 2})['state']['count'] == 3\nclass CounterCase(unittest.TestCase):\n    def test_empty(self):\n        self.assertEqual(update({}, {})['state']['count'], 1)\n", 'tests.py')
        self.runtime.stage(self.source(BASE), tests)
        tests.write_text('def test_reject():\n    assert False, "candidate rejected by test"\n')
        with self.assertRaisesRegex(MechanicError, 'candidate rejected by test'):
            self.runtime.stage(self.source(BASE), tests)
        tests.write_text('# no tests\n')
        with self.assertRaises(MechanicError):
            self.runtime.stage(self.source(BASE), tests)

    def test_stage_validates_every_tested_interaction_result(self):
        obj = dict(id='luna', group=0, num=1, x=10, y=12, gfx=8, text='Hello!')
        tile = dict(group=0, num=0, x=1, y=2, metatile=3, collision=0)
        invalid = [
            (dict(state={}, tiles=[], objects=[dict(obj, text='x' * 29)]), 'object text'),
            (dict(state={}, tiles=[], objects=[dict(obj, group=255)]), 'map coordinates'),
            (dict(state={}, tiles=[dict(tile, metatile=656)]), 'tileset allocations'),
        ]
        tests = self.source('''def test_interactions():
    assert update({}, {})['tiles'] == []
    result = update({'interactions': [{'object': 'luna'}]}, {})
    assert result['state'] == {}
    # Later valid calls or mutations must not hide earlier invalid results.
    result.clear()
    assert update({}, {})['tiles'] == []
''', 'tests.py')
        for result, error in invalid:
            with self.subTest(error=error):
                source = ('def update(context, state):\n'
                          '    if context.get("interactions"):\n'
                          '        return ' + repr(result) + '\n'
                          '    return {"state": {}, "tiles": []}\n')
                with self.assertRaisesRegex(MechanicError, error):
                    self.runtime.stage(self.source(source), tests)

    def test_tested_results_keep_strict_json_depth_and_output_bounds(self):
        tests = self.source('''def test_result():
    try:
        update({'interactions': [1]}, {})
    except (ValueError, TypeError, RecursionError):
        pass
''', 'tests.py')
        for expression in ("{1: 'bad key'}", '(1, 2)', "float('nan')",
                           "'x' * 65536", "'x' * 200000"):
            with self.subTest(expression=expression):
                source = ('def update(context, state):\n'
                          '    value = ' + expression + ' if context.get("interactions") else {}\n'
                          '    return {"state": value, "tiles": []}\n')
                with self.assertRaises(MechanicError):
                    self.runtime.stage(self.source(source), tests)
        source = '''def update(context, state):
    value = 0
    if context.get('interactions'):
        for _ in range(65):
            value = [value]
    return {'state': value, 'tiles': []}
'''
        with self.assertRaises(MechanicError):
            self.runtime.stage(self.source(source), tests)
        # Every single result is valid, but their retained snapshots exceed the
        # aggregate byte cap. Catching the error must not discard that failure.
        tests.write_text('''def test_aggregate():
    for _ in range(1000):
        try:
            update({}, {})
        except ValueError:
            pass
''')
        with self.assertRaises(MechanicError):
            self.runtime.stage(self.source("def update(context, state):\n    return {'state': 'x' * 1000, 'tiles': []}\n"), tests)

    def test_many_valid_test_calls_and_boundary_depth_still_stage(self):
        source = '''def update(context, state):
    value = 0
    for _ in range(63):
        value = [value]
    return {'state': value, 'tiles': []}
'''
        tests = self.source('''def test_depth():
    assert update({}, {})['tiles'] == []
def test_many_calls():
    for _ in range(1000):
        assert update({}, {})['state']['count'] == 1
''', 'tests.py')
        # A separate small source keeps 1,000 snapshots inside the output cap.
        self.runtime.stage(self.source(BASE), tests)
        tests.write_text('def test_depth():\n    assert update({}, {})["tiles"] == []\n')
        self.runtime.stage(self.source(source), tests)

    def test_source_restore_validates_hash_and_rechecks_baseline(self):
        candidate = self.runtime.stage(self.source(BASE))
        restored = self.runtime.from_source(candidate.source, candidate.sha256)
        self.assertEqual(candidate, restored)
        self.assertEqual(self.runtime.run(restored, CONTEXT, {})['state'], {'count': 1})
        with self.assertRaises(MechanicError):
            self.runtime.from_source(BASE, '0' * 64)
        with self.assertRaises(MechanicError):
            self.runtime.from_source('def broken(')

    def test_sandbox_denies_process_creation_network_and_file_writes(self):
        source = '''import os, socket

def update(context, state):
    blocked = {}
    try:
        pid = os.fork()
    except OSError:
        blocked['fork'] = True
    else:
        if pid == 0:
            os._exit(0)
        os.waitpid(pid, 0)
        blocked['fork'] = False
    try:
        socket.socket()
    except OSError:
        blocked['network'] = True
    else:
        blocked['network'] = False
    try:
        open('/tmp/write-attempt', 'w').close()
    except OSError:
        blocked['write'] = True
    else:
        blocked['write'] = False
    return {'state': blocked, 'tiles': []}
'''
        candidate = self.runtime.stage(self.source(source))
        self.assertEqual(self.runtime.run(candidate, CONTEXT, {})['state'],
                         {'fork': True, 'network': True, 'write': True})

    def test_private_paths_environment_and_sibling_sources_are_absent(self):
        secret = self.root / 'private-sentinel'
        secret.write_text('not visible to code')
        sibling = self.source('private sibling', 'sibling.py')
        source = "import os\ndef update(context, state):\n    return {'state': {'visible': [os.path.exists(p) for p in " + repr([str(secret), str(sibling), '/home/ayaan/.hermes', '/root']) + "], 'home': os.environ.get('HOME'), 'env': sorted(os.environ)}, 'tiles': []}\n"
        result = self.runtime.run(self.runtime.stage(self.source(source)), CONTEXT, {})
        self.assertEqual(result['state']['visible'], [False] * 4)
        self.assertEqual(result['state']['home'], '/nonexistent')
        self.assertLessEqual(set(result['state']['env']), {'HOME', 'LANG', 'LC_CTYPE'})

    def test_runaway_code_is_killed_without_changing_caller_state(self):
        source = "def update(context, state):\n    if context['tick']:\n        state['changed'] = True\n        while True: pass\n    return {'state': state, 'tiles': []}\n"
        candidate = self.runtime.stage(self.source(source))
        runtime = MechanicRuntime(self.root, timeout=0.2)
        state = {'count': 3}
        with self.assertRaisesRegex(MechanicError, 'timeout'):
            runtime.run(candidate, dict(CONTEXT, tick=1), state)
        self.assertEqual(state, {'count': 3})
        self.assertEqual(self.runtime.run(candidate, CONTEXT, state)['state'], state)

    def test_bad_syntax_missing_update_and_import_failure_cannot_stage(self):
        for source in ('def update(', 'x = 1', "raise RuntimeError('broken import')", "def update(context, state):\n    raise RuntimeError('broken update')"):
            with self.subTest(source=source):
                with self.assertRaises(MechanicError):
                    self.runtime.stage(self.source(source))

    def test_excessive_output_and_memory_are_rejected(self):
        for source in ("print('x' * 300000)\n" + BASE,
                       "def update(context, state):\n    return {'state': 'x' * (256 * 1024 * 1024), 'tiles': []}\n"):
            with self.subTest(source=source):
                with self.assertRaises(MechanicError):
                    self.runtime.stage(self.source(source))

    def test_malformed_stdout_is_rejected(self):
        with self.assertRaises(MechanicError):
            self.runtime.stage(self.source("print('not JSON')\n" + BASE))

    def test_paths_must_stay_inside_candidates(self):
        outside = self.root / 'outside.py'
        outside.write_text(BASE)
        link = self.root / 'candidates' / 'link.py'
        link.symlink_to(outside)
        for path in (outside, link, '../outside.py'):
            with self.subTest(path=path):
                with self.assertRaises(MechanicError):
                    self.runtime.stage(path)
        with self.assertRaises(MechanicError):
            self.runtime.stage(self.source(BASE), outside)

    def test_input_state_must_be_bounded_strict_json(self):
        candidate = self.runtime.stage(self.source("def update(context, state):\n    return {'state': state, 'tiles': []}\n"))
        cyclic = []
        cyclic.append(cyclic)
        deep = 0
        for _ in range(66):
            deep = [deep]
        for state in ({1: 'non-string key'}, (1, 2), float('inf'), cyclic, deep, 'x' * 65536):
            with self.subTest(state_type=type(state)):
                with self.assertRaises(MechanicError):
                    self.runtime.run(candidate, CONTEXT, state)
        with self.assertRaises(MechanicError):
            self.runtime.run(candidate, {'payload': 'x' * 300000}, {})

    def test_non_json_python_return_types_are_not_silently_coerced(self):
        for expression in ("{1: 'bad key'}", '(1, 2)', "float('inf')"):
            with self.subTest(expression=expression):
                with self.assertRaises(MechanicError):
                    self.runtime.stage(self.source("def update(context, state):\n    return {'state': " + expression + ", 'tiles': []}\n"))

    def test_valid_boundary_tiles_and_new_context_dependent_code(self):
        source = '''def update(context, state):
    ready = sum(1 for player in context['players'] if player['ready'])
    return {'state': {'ready': ready, 'ticks': state.get('ticks', 0) + 1},
            'tiles': [{'group': 0, 'num': 0, 'x': i % 30, 'y': i // 30,
                       'metatile': 655, 'collision': int(ready == 0)} for i in range(128)]}
'''
        candidate = self.runtime.stage(self.source(source))
        context = dict(CONTEXT, players=[{'id': 'alice', 'group': 0, 'num': 0,
                                         'x': 0, 'y': 0, 'facing': 1, 'gfx': 0, 'ready': True}])
        result = self.runtime.run(candidate, context, {'ticks': 8})
        self.assertEqual(result['state'], {'ready': 1, 'ticks': 9})
        self.assertEqual(len(result['tiles']), 128)
        self.assertTrue(all(tile['collision'] == 0 for tile in result['tiles']))

    def test_nonregular_source_cannot_hang_stage(self):
        import os
        import threading
        fifo = self.root / 'candidates' / 'fifo.py'
        os.mkfifo(fifo)
        errors = []
        def attempt():
            try:
                self.runtime.stage(fifo)
            except MechanicError as exc:
                errors.append(exc)
        thread = threading.Thread(target=attempt, daemon=True)
        thread.start()
        thread.join(0.3)
        self.assertFalse(thread.is_alive(), 'source reader blocked on a FIFO')
        self.assertEqual(len(errors), 1)

    def test_runtime_configuration_and_reconstructed_candidates_are_bounded(self):
        from world.mechanics import Candidate
        for timeout in (0, -1, float('inf'), float('nan'), 11):
            with self.subTest(timeout=timeout):
                with self.assertRaises(MechanicError):
                    MechanicRuntime(self.root, timeout=timeout)
        import hashlib
        huge = BASE + '\n# ' + 'x' * 262144
        for candidate in (Candidate(BASE, 'bad'), Candidate(1, 'bad'),
                          Candidate(huge, hashlib.sha256(huge.encode()).hexdigest())):
            with self.subTest(candidate_type=type(candidate.source)):
                with self.assertRaises(MechanicError):
                    self.runtime.run(candidate, CONTEXT, {})


if __name__ == '__main__':
    unittest.main()
