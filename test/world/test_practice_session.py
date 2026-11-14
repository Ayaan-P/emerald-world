import unittest,tempfile,hashlib,threading,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import test_cast_practice_worker as fixtures
from world.companion_practice import Ledger
from world.session import DesktopSession

class BudgetTests(unittest.TestCase):
 def test_period_restart_clock_rollback_and_no_catchup(self):
  f=fixtures.CastPracticeTests();f.setUp();self.addCleanup(f.doCleanups);f.register()
  self.assertEqual(f.run_step(turn_limit=1,period_hours=1,now=100)['status'],'completed_in_host_ledger')
  changed=f.action.copy();changed['expected_version']=1;changed['changes']=dict(f.action['changes'],intentions=[dict(id='second',kind='practice',target='partner',reason='Try again.')]);f.f.apply(changed)
  f.ledger.close();f.ledger=Ledger(Path(f.tmp.name)/'npc-only.db');self.addCleanup(f.ledger.close)
  for now in (99,3699):self.assertEqual(f.run_step(turn_limit=1,period_hours=1,now=now)['status'],'idle')
  old=f.engine.run;f.engine.run=lambda line:dict(old(line),exp=325,level=7,blob='0200')
  self.assertEqual(f.run_step(turn_limit=1,period_hours=1,now=3700)['status'],'completed_in_host_ledger')
  self.assertEqual(f.ledger.db.execute('SELECT used,started FROM practice_budget').fetchone(),(1,3700))

class SessionTests(unittest.TestCase):
 def test_gate_managed_start_stop_and_error_no_retry(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);s=DesktopSession(root,engine='expansion-native');s.state=root/'world';s.state.mkdir();s.server=SimpleNamespace(_closed=False)
   binary=root/'native';binary.write_bytes(b'fixture never executed');digest=hashlib.sha256(binary.read_bytes()).hexdigest()
   with self.assertRaises(ValueError):s.start_practice(binary,digest)
   called=threading.Event()
   def run(*args,**kwargs):called.set();return dict(status='failed')
   with patch('world.cast_practice_worker.step',side_effect=run) as worker:
    s.start_practice(binary,digest,validated_native=True)
    self.assertTrue(called.wait(2));s.stop_practice();self.assertFalse(s.practice_thread.is_alive());self.assertEqual(s.practice_error,'failed');self.assertEqual(worker.call_count,1)
