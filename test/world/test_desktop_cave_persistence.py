"""Local host generated cave survives a restart without opening sockets."""
from pathlib import Path
import hashlib
import tempfile
import unittest
from unittest.mock import patch
from test_shared_generated_cave import MemoryAuthority
from test_large_generated_cave import DOC
from world import cave_blueprint,large_cave
from world.session import DesktopSession

class FakeLock:
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def close(self):pass

class DesktopCavePersistence(unittest.TestCase):
    def test_host_generated_world_reloads_same_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();path=root/'world';path.mkdir(mode=0o700)
            session=DesktopSession(root)
            proposal=cave_blueprint.proposal_from_blueprint(DOC,side=63)
            blob=large_cave.encode_wildlife(proposal,'ice',25,[{'species':'MAGIKARP','level':5}]*12)
            with patch.object(session,'_world',return_value=path),patch.object(session,'worlds',return_value=[{'path':str(path)}]), \
                 patch('world.world_library.WorldActivityLock',side_effect=lambda *_:FakeLock()), \
                 patch('world.server.WorldServer',MemoryAuthority),patch.object(MemoryAuthority,'start',return_value=None):
                session.host('world');server=session.server;self.assertTrue(server.persist_generated_cave)
                trainer=server.create_identity('Alice');save=Path(trainer['save_path']);save.write_bytes(b'private trainer save')
                with patch('world.author_cave.author',return_value=(proposal,blob)):
                    identity=session.author_shared_cave('icy cave')
                self.assertEqual(identity,hashlib.sha256(blob).hexdigest());self.assertIn('persist',session.status)
                server.close();session.server=None;session.state=None
                session.host('world')
                try:
                    self.assertEqual(session.server.shared_cave.identity,identity)
                    self.assertEqual(save.read_bytes(),b'private trainer save')
                finally:session.server.close()
