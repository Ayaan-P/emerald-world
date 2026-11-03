"""Cross-process lifecycle races on disposable worlds, never personal saves."""
import multiprocessing
from pathlib import Path
import tempfile
import unittest


def _move_paused(root, token, ready, proceed, moved, release, results):
    from world import world_library as library
    original = library._move
    def pause(source, destination):
        ready.set()
        if not proceed.wait(10):
            raise RuntimeError('move test timed out')
        original(source, destination)
        moved.set()
        if not release.wait(10):
            raise RuntimeError('release test timed out')
    library._move = pause
    try:
        value = library.restore(root, token, 0) if token else library.delete(root, 'stable')
        results.put(('ok', str(value)))
    except BaseException as error:
        results.put(('error', repr(error)))


def _start(root, operation, results):
    from world.launcher import ProfileLock, prepare_profile, main
    from world.runtime_gm import IntentQueue, RuntimeGM, MODEL
    from world.session import DesktopSession
    from world.server import WorldServer
    state = Path(root)/'stable'
    resource = None
    try:
        if operation == 'profile':
            resource = ProfileLock(state, 'brandnew')
        elif operation == 'prepare':
            prepare_profile(state, 'brandnew')
        elif operation == 'queue':
            resource = IntentQueue(state)
        elif operation == 'runtime':
            resource = RuntimeGM(state, str(state/'transport/world.sock'), model=MODEL)
        elif operation == 'create':
            DesktopSession(root).create_world('stable')
        elif operation == 'host':
            resource = DesktopSession(root)
            resource.host('stable')
        elif operation == 'author':
            from world.gm import author_and_deploy
            author_and_deploy(state, state/'transport/world.sock', 'test request',
                              author_argv=lambda _: {}, timeout=0.2)
        elif operation == 'label':
            from world.world_library import rename
            rename(root, 'stable', 'Racing label', [])
        elif operation == 'server':
            resource = WorldServer(state/'transport/world.sock', state)
        elif operation == 'cli':
            main(['--state-dir', str(state), 'join', 'brandnew', '--print-command'])
        else:
            raise AssertionError(operation)
        results.put(('started', operation))
    except (ValueError, OSError) as error:
        results.put(('blocked', type(error).__name__))
    finally:
        if resource is not None:
            resource.close()


def _hold(root, operation, ready, release):
    from world.launcher import ProfileLock
    from world.runtime_gm import IntentQueue, RuntimeGM, MODEL
    from world.session import DesktopSession
    state = Path(root)/'stable'
    if operation == 'profile':
        resource = ProfileLock(state, 'alice')
    elif operation == 'runtime':
        resource = RuntimeGM(state, state/'transport/world.sock', model=MODEL)
    elif operation == 'queue':
        resource = IntentQueue(state)
    else:
        resource = DesktopSession(root)
        resource.host('stable')
    try:
        ready.set()
        if not release.wait(10):
            raise RuntimeError('holder timed out')
    finally:
        resource.close()


class LifecycleRaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ew-lifecycle-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ctx = multiprocessing.get_context('spawn')
        from world.session import DesktopSession
        DesktopSession(self.root).create_world('stable')

    def start_attempt(self, operation):
        results = self.ctx.Queue()
        child = self.ctx.Process(target=_start, args=(str(self.root), operation, results))
        child.start()
        child.join(10)
        if child.is_alive():
            child.kill()
            child.join()
            self.fail('start blocked instead of failing closed: ' + operation)
        self.assertEqual(child.exitcode, 0)
        outcome = results.get(timeout=2)
        results.close()
        return outcome

    def test_delete_excludes_new_starts_before_and_after_atomic_move(self):
        self.assert_move_excludes_starts(None)

    def test_restore_excludes_destination_starts_before_and_after_atomic_move(self):
        from world.world_library import delete
        self.assert_move_excludes_starts(delete(self.root, 'stable'))

    def test_direct_server_constructor_obeys_move_barrier(self):
        self.assert_move_excludes_starts(None, operations=('server',))

    def test_direct_gm_author_obeys_move_barrier(self):
        self.assert_move_excludes_starts(None, operations=('author',))

    def assert_move_excludes_starts(self, token, operations=None):
        if operations is None:
            operations = ('profile', 'prepare', 'queue', 'runtime', 'create', 'host', 'label', 'cli')
        ready, proceed, moved, release = [self.ctx.Event() for _ in range(4)]
        results = self.ctx.Queue()
        child = self.ctx.Process(target=_move_paused,
            args=(str(self.root), token, ready, proceed, moved, release, results))
        child.start()
        try:
            self.assertTrue(ready.wait(10))
            for phase in ('before', 'after'):
                for operation in operations:
                    with self.subTest(phase=phase, operation=operation):
                        self.assertEqual(self.start_attempt(operation)[0], 'blocked')
                if phase == 'before':
                    proceed.set()
                    self.assertTrue(moved.wait(10))
            self.assertEqual((self.root/'stable').exists(), token is not None,
                             'a starter recreated the moved world')
        finally:
            proceed.set()
            release.set()
            child.join(10)
            if child.is_alive():
                child.kill()
                child.join()
        self.assertEqual(child.exitcode, 0)
        self.assertEqual(results.get(timeout=2)[0], 'ok')
        results.close()

    def test_running_participants_block_move_and_release_after_exit(self):
        from world.world_library import delete, restore
        for operation in ('profile', 'runtime', 'queue', 'host'):
            with self.subTest(operation=operation):
                ready, release = self.ctx.Event(), self.ctx.Event()
                child = self.ctx.Process(target=_hold, args=(str(self.root), operation, ready, release))
                child.start()
                try:
                    self.assertTrue(ready.wait(10))
                    with self.assertRaises(ValueError):
                        delete(self.root, 'stable')
                    self.assertTrue((self.root/'stable').exists())
                    # Shared world leases must not serialize independent trainers.
                    self.assertEqual(self.start_attempt('profile')[0], 'started')
                finally:
                    release.set()
                    child.join(10)
                    if child.is_alive():
                        child.kill()
                        child.join()
                self.assertEqual(child.exitcode, 0)
                restore(self.root, delete(self.root, 'stable'), 0)

    def test_runtime_initialization_failure_releases_world_barrier(self):
        from world.runtime_gm import RuntimeGM, MODEL
        from world.world_library import WorldActivityLock
        state = self.root/'stable'
        (state/'gm').mkdir()
        (state/'gm/.runtime.lock').mkdir()
        with self.assertRaises(OSError):
            RuntimeGM(state, state/'transport/world.sock', model=MODEL)
        with WorldActivityLock(state, exclusive=True):
            pass


if __name__ == '__main__':
    unittest.main()
