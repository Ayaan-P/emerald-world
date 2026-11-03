"""The Windows native fixture accepts either channel arrival order."""
import importlib.util
from pathlib import Path
import socket
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('windows_bridge_fixture', ROOT/'scripts/windows_bridge_test.py')
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FixtureChannels(unittest.TestCase):
    def test_link_first_does_not_replace_social_authentication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save = root/'seed.sav'
            save.write_bytes(b'disposable fixture')
            fixture = MODULE.Fixture(root/'unused.exe', save, root/'profile')
            errors = []
            def connect():
                try:
                    fixture.connect()
                except BaseException as exc:
                    errors.append(exc)
            worker = threading.Thread(target=connect)
            worker.start()
            try:
                prefix = f'EWLOCAL1 {fixture.local_key}\nHELLO 1 alice {fixture.token} '.encode()
                address = fixture.listener.getsockname()
                with socket.create_connection(address, timeout=2) as link:
                    link.sendall(prefix+b'LINK\n')
                    self.assertEqual(link.recv(128), b'ERROR PRESENCE\n')
                with socket.create_connection(address, timeout=2) as social:
                    social.sendall(prefix+b'SOCIAL\n')
                    self.assertEqual(social.recv(128), b'WELCOME 1 alice 0\n')
                worker.join(3)
                self.assertFalse(worker.is_alive())
                self.assertEqual(errors, [])
                self.assertIsNotNone(fixture.conn)
            finally:
                fixture.close()
                worker.join(7)
