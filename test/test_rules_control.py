"""Agent-facing owner rule control, with no sockets."""
import contextlib
import io
import unittest
from unittest.mock import patch
from world import rules_control
from world.world_rules import DEFAULT_RULES

class RulesControl(unittest.TestCase):
 def test_status_and_set_submit_exact_versioned_requests(self):
  with patch.object(rules_control, 'admin_request', return_value={'ok': True, 'version': 3, 'revision': 5, 'rules': DEFAULT_RULES}) as send, contextlib.redirect_stdout(io.StringIO()):
   self.assertEqual(rules_control.main(['--admin-socket','/tmp/owner','status']),0)
   self.assertEqual(send.call_args.args[1], {'command':'world_rules','action':'status'})
   self.assertEqual(rules_control.main(['--admin-socket','/tmp/owner','set','--revision','5','--wild-shuffle','on','--seed','7']),0)
   self.assertEqual(send.call_args.args[1], {'command':'world_rules','action':'replace','expected_revision':5,'rules':{**DEFAULT_RULES, 'wild_shuffle':{'enabled':True,'seed':7}}})
 def test_v2_set_submits_three_gameplay_booleans(self):
  with patch.object(rules_control, 'admin_request', return_value={'ok': True, 'version': 2, 'revision': 5, 'rules': {'wild_shuffle': {'enabled': False, 'seed': 1}, 'reusable_tms': False, 'evolution_items_from_bag': False, 'party_exp_share': False}}) as send, contextlib.redirect_stdout(io.StringIO()):
   self.assertEqual(rules_control.main(['--admin-socket','/tmp/owner','set','--revision','5','--wild-shuffle','off','--seed','7', '--reusable-tms','on','--evolution-items-from-bag','off','--party-exp-share','on']),0)
   self.assertEqual(send.call_args.args[1]['rules'], {'wild_shuffle': {'enabled': False, 'seed': 7}, 'reusable_tms': True, 'evolution_items_from_bag': False, 'party_exp_share': True})

 def test_invalid_seed_never_contacts_authority(self):
  with patch.object(rules_control, 'admin_request') as send, contextlib.redirect_stderr(io.StringIO()):
   with self.assertRaises(SystemExit): rules_control.main(['--admin-socket','/tmp/owner','set','--revision','0','--wild-shuffle','on','--seed','21'])
   send.assert_not_called()
