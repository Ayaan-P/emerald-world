import subprocess
import threading
import time
import unittest
from world import launcher


class NativeProcessParentTests(unittest.TestCase):
    def test_sandbox_survives_http_request_thread_exit(self):
        command = ['bwrap', '--unshare-all', '--die-with-parent', '--new-session',
            '--ro-bind', '/usr', '/usr', '--ro-bind', '/lib', '/lib',
            '--ro-bind', '/lib64', '/lib64', '--symlink', 'usr/bin', '/bin',
            '--', '/usr/bin/sleep', '20']
        processes = []
        def request():
            processes.append(getattr(launcher, 'start_owned_process', subprocess.Popen)(command))
            time.sleep(.15)
        worker = threading.Thread(target=request)
        worker.start()
        worker.join(timeout=5)
        self.assertFalse(worker.is_alive())
        process = processes[0]
        try:
            time.sleep(.15)
            self.assertIsNone(process.poll(), 'request thread exit killed the native sandbox')
        finally:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=3)

    def test_spawn_failure_is_returned_to_request(self):
        with self.assertRaises(FileNotFoundError):
            launcher.start_owned_process(['/nonexistent/emerald-test-command'])


if __name__ == '__main__':
    unittest.main()
