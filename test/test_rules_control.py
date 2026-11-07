"""Agent-facing owner rule control, with no sockets."""
import contextlib
import io
import unittest
from unittest.mock import patch
from world import rules_control

class RulesControl(unittest.TestCase):
 def test_status_and_set_submit_exact_versioned_requests(self):
  with patch.object(rules_control, 'admin_request', return_value={'ok': True}) as send, contextlib.redirect_stdout(io.StringIO()):
   self.assertEqual(rules_control.main(['--admin-socket','/tmp/owner','status']),0)
   self.assertEqual(send.call_args.args[1], {'command':'world_rules','action':'status'})
   self.assertEqual(rules_control.main(['--admin-socket','/tmp/owner','set','--revision','5','--wild-shuffle','on','--seed','7']),0)
   self.assertEqual(send.call_args.args[1], {'command':'world_rules','action':'replace','expected_revision':5,'rules':{'wild_shuffle':{'enabled':True,'seed':7}}})
 def test_invalid_seed_never_contacts_authority(self):
  with patch.object(rules_control, 'admin_request') as send, contextlib.redirect_stderr(io.StringIO()):
   with self.assertRaises(SystemExit): rules_control.main(['--admin-socket','/tmp/owner','set','--revision','0','--wild-shuffle','on','--seed','21'])
   send.assert_not_called()
