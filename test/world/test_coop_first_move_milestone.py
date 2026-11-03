"""Acceptance milestone semantics; never substitutes for native battle play."""
import copy
import unittest
import native_coop_acceptance as acceptance

class FirstMoveMilestoneTests(unittest.TestCase):
    def test_both_owned_moves_do_not_require_one_wild_to_hit_both_players(self):
        before = {n: {'party': [{'hp': 20, 'moves': [{'pp': 35}, {'pp': 40}]}]}
                  for n in ('alice', 'bob')}
        states = copy.deepcopy(before)
        for state in states.values():
            state['party'][0]['moves'][1]['pp'] = 39
        states['bob']['party'][0]['hp'] = 18
        predicate = getattr(acceptance, 'both_first_moves_executed', None)
        self.assertTrue(callable(predicate), 'explicit first-move predicate required')
        self.assertTrue(predicate(states, before))
        states['alice']['party'][0]['moves'][1]['pp'] = 40
        self.assertFalse(predicate(states, before), 'one trainer acting is insufficient')
        states['alice']['party'][0]['hp'] = 18
        self.assertFalse(predicate(states, before), 'damage cannot stand in for own move execution')

if __name__ == '__main__':
    unittest.main()
