"""Recovery of locks and resources after a real failed SQLite commit."""
import fcntl
import sqlite3
import tempfile
import unittest
from pathlib import Path
from world.server import WorldServer

class CloseFailureTests(unittest.TestCase):
    def test_loop_failure_closes_clients_even_before_owner_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);server=WorldServer(root/'socket',root/'world')
            server.pending_states['alice']={'id':'alice','seq':1,'state':[0,1,10,12,4,7,1],
                'party_hash':'a'*16,'bag_hash':'b'*16}
            server.next_state_flush=0
            server.db.set_authorizer(lambda op,arg,*_: sqlite3.SQLITE_DENY
                if op==sqlite3.SQLITE_TRANSACTION and arg=='COMMIT' else sqlite3.SQLITE_OK)
            class Endpoint:
                closed=False
                def close(self):self.closed=True
            class BrokenEndpoint:
                failed=False
                def close(self):
                    if not self.failed:
                        self.failed=True
                        raise OSError('simulated close failure')
            class Key:
                def __init__(self,endpoint):self.fileobj=endpoint
            class Selector:
                def __init__(self, endpoints):self.items={i:Key(e) for i,e in enumerate(endpoints)}
                def select(self,timeout):return []
                def get_map(self):return self.items
                def close(self):pass
            listener,client=Endpoint(),Endpoint()
            server.selector=Selector([listener,BrokenEndpoint(),client])
            try:
                with self.assertRaises(sqlite3.Error):server._loop()
                self.assertTrue(listener.closed)
                self.assertTrue(client.closed)
                self.assertTrue(server.stopping.is_set())
            finally:
                server.db.set_authorizer(None);server.close()

    def test_failed_flush_closes_database_and_releases_world_lifecycle_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); state=root/'world'
            server=WorldServer(root/'socket',state)
            identity=server.create_identity('alice')
            server.authority_lock=(state/'world.lock').open('a+b')
            fcntl.flock(server.authority_lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            authority_handle=server.authority_lock
            save=Path(identity['save_path']);save.write_bytes(b'private-progress-unchanged')
            server.pending_states['alice']={'id':'alice','seq':1,'state':[0,1,10,12,4,7,1],
                'party_hash':'a'*16,'bag_hash':'b'*16}
            server.db.set_authorizer(lambda op,arg,*_: sqlite3.SQLITE_DENY
                if op==sqlite3.SQLITE_TRANSACTION and arg=='COMMIT' else sqlite3.SQLITE_OK)
            with self.assertRaises(sqlite3.Error):server.close()
            with self.assertRaises(sqlite3.ProgrammingError):server.db.execute('SELECT 1')
            self.assertTrue(authority_handle.closed)
            server.close()  # A repeated close is harmless after the reported failure.
            with (state/'world.lock').open('a+b') as new_lock:
                fcntl.flock(new_lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.assertEqual(save.read_bytes(),b'private-progress-unchanged')
            replacement=WorldServer(root/'socket',state)
            try:
                rows=replacement.db.execute("SELECT count(*) FROM events WHERE kind='state'").fetchone()[0]
                self.assertEqual(rows,0)
            finally:replacement.close()

if __name__=='__main__':unittest.main()
