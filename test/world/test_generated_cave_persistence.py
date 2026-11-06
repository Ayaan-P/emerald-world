"""Exercise opt-in cave persistence through the production authority database.

This does not start sockets or a native game.
"""
from pathlib import Path
import sqlite3
import tempfile
import unittest
from test_shared_generated_cave import BLOB, MemoryAuthority
from world.shared_cave import CaveError, SharedCave

class CavePersistence(unittest.TestCase):
 def test_explicit_persistence_survives_restart_and_off_mode_ignores_it(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);world=root/'world';changed=bytearray(BLOB);changed[8+2*31+2]=ord('#');changed=bytes(changed)
   server=MemoryAuthority(root/'socket',world,cave_template=BLOB,persist_generated_cave=True)
   identity=server._replace_cave(changed);server.close()
   server=MemoryAuthority(root/'socket',world,cave_template=BLOB)
   self.assertEqual(server.shared_cave.identity,SharedCave(BLOB).identity);server.close()
   server=MemoryAuthority(root/'socket',world,cave_template=BLOB,persist_generated_cave=True)
   self.assertEqual(server.shared_cave.identity,identity);server.close()
 def test_same_template_is_saved_and_storage_failure_preserves_live_map(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);world=root/'world';server=MemoryAuthority(root/'socket',world,cave_template=BLOB,persist_generated_cave=True)
   identity=server._replace_cave(BLOB)
   row=server.db.execute('SELECT template FROM generated_cave WHERE singleton=1').fetchone();self.assertEqual(row[0],BLOB)
   server.db.execute('PRAGMA query_only=ON')
   changed=bytearray(BLOB);changed[8+2*31+2]=ord('#')
   with self.assertRaisesRegex(ValueError,'persisted'):server._replace_cave(bytes(changed))
   self.assertEqual(server.shared_cave.identity,identity)
   server.close()
 def test_corrupt_persisted_template_fails_closed(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);world=root/'world';server=MemoryAuthority(root/'socket',world,persist_generated_cave=True)
   server._replace_cave(BLOB);server.close()
   db=sqlite3.connect(world/'world.sqlite3');db.execute("UPDATE generated_cave SET template=x'01'");db.commit();db.close()
   with self.assertRaises(CaveError):MemoryAuthority(root/'socket',world,persist_generated_cave=True)

if __name__=='__main__':unittest.main()
