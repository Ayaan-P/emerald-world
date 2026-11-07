import copy
import io
import sqlite3
import unittest
from unittest.mock import patch
from world.rules_control import main
from world.world_rules import WorldRules, GAMEPLAY_BITS

class Rc10Control(unittest.TestCase):
    def test_shuffle_cli_preserves_all_unmentioned_flags_and_revision(self):
        with sqlite3.connect(':memory:') as db:
            authority = WorldRules(db)
            rules = authority.status()['rules']; rules.update(dict.fromkeys(GAMEPLAY_BITS, True))
            authority.replace(rules, 0)
            def request(unused, payload, **kwargs):
                if payload['action'] == 'status': return authority.status()
                return authority.replace(payload['rules'], payload['expected_revision'])
            with patch('world.rules_control.admin_request', side_effect=request) as admin, patch('sys.stdout', new_callable=io.StringIO):
                self.assertEqual(main(['--admin-socket','/tmp/disposable.sock','set','--revision','1','--wild-shuffle','on','--seed','13']), 0)
            self.assertEqual(admin.call_count, 2)
            self.assertTrue(all(authority.status()['rules'][key] for key in GAMEPLAY_BITS))
            self.assertEqual(authority.status()['rules']['wild_shuffle'], {'enabled': True, 'seed': 13})

if __name__ == '__main__': unittest.main()
