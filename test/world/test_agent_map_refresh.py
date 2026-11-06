"""Offline agent output replacement and validation; no provider calls."""
import tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from world import map_store,author_cave
class AgentMapRefresh(unittest.TestCase):
 def test_default_exclusive_and_opt_in_atomic_replace(self):
  with tempfile.TemporaryDirectory() as t:
   path=Path(t)/'map.bin';map_store.write_map(path,b'old')
   with self.assertRaises(FileExistsError):map_store.write_map(path,b'new')
   self.assertEqual(path.read_bytes(),b'old');map_store.write_map(path,b'new',replace=True);self.assertEqual(path.read_bytes(),b'new')
   self.assertEqual(list(Path(t).iterdir()),[path])
 def test_failure_keeps_old_file_and_symlink_target(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);path=p/'map';path.write_bytes(b'old')
   with patch('world.map_store.os.replace',side_effect=OSError('failed')):
    with self.assertRaises(OSError):map_store.write_map(path,b'new',replace=True)
   self.assertEqual(path.read_bytes(),b'old');self.assertEqual(list(p.iterdir()),[path])
   link=p/'link';link.symlink_to(path)
   with self.assertRaises(ValueError):map_store.write_map(link,b'new',replace=True)
   self.assertEqual(path.read_bytes(),b'old')
 def test_readers_see_complete_old_or_new_map(self):
  with tempfile.TemporaryDirectory() as t:
   path=Path(t)/'map';a=b'a'*20000;b=b'b'*20000;path.write_bytes(a);seen=[];done=threading.Event()
   def reader():
    while not done.is_set():seen.append(path.read_bytes())
   thread=threading.Thread(target=reader);thread.start()
   try:
    for i in range(20):map_store.write_map(path,b if i%2==0 else a,replace=True)
   finally:done.set();thread.join()
   self.assertTrue(seen);self.assertTrue(all(x in (a,b) for x in seen))
 def test_explicit_cli_replacement_and_failed_author_preserves_old(self):
  with tempfile.TemporaryDirectory() as t:
   path=Path(t)/'map';path.write_bytes(b'old')
   with patch('world.author_cave.author',return_value=({'rows':[]},b'new')),patch('builtins.print'):
    self.assertEqual(author_cave.main(['theme','--xl-wilds-output',str(path)]),1);self.assertEqual(path.read_bytes(),b'old')
    self.assertEqual(author_cave.main(['theme','--xl-wilds-output',str(path),'--replace-output']),0);self.assertEqual(path.read_bytes(),b'new')
   with patch('world.author_cave.author',side_effect=ValueError('invalid')),patch('builtins.print'):
    self.assertEqual(author_cave.main(['theme','--xl-wilds-output',str(path),'--replace-output']),1);self.assertEqual(path.read_bytes(),b'new')
 def test_invalid_replacement_does_not_call_model(self):
  with tempfile.TemporaryDirectory() as t,patch('world.author_cave.author') as author,patch('builtins.print'):
   self.assertEqual(author_cave.main(['theme','--xl-wilds-output',str(Path(t)/'missing'),'--replace-output']),1);author.assert_not_called()
