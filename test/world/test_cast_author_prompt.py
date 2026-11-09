"""Production prompt routing agrees with real typed admission, without model calls."""
import unittest
from world import gm,character_reactions as reactions,author_backends as backends

class CastPromptTests(unittest.TestCase):
 def test_canonical_first_and_planning_turns_have_one_legal_response_contract(self):
  for extra in ({'bootstrap':True},{'self_direction':True},{}):
   reaction=dict(id='canon_rydel',expected_version=0,evidence=1,canonical=True,**extra)
   prompt=gm._prompt('Consider your own goal',dict(character_reaction=reaction))
   self.assertIn('exactly canonical_actions and tests',prompt)
   self.assertNotIn('Implement the human request as novel Python',prompt)
   self.assertNotIn('Return ONLY JSON {"source"',prompt)
   self.assertIn('initial identity-based goal and greeting only',prompt)
   self.assertIn('"changes": {"goal":',prompt)
   self.assertIn('"places": [',prompt)
   self.assertIn('"evidence": [',prompt)
   self.assertIn('state["canonical_cast"]',prompt)
   self.assertIn('not world_characters',prompt)
   self.assertIn('def test_initialization():',prompt)
   self.assertIn('update(context, state)',prompt)
   self.assertIn('Never define test_*(update)',prompt)
   answer=backends.check_result(dict(canonical_actions=[],tests='assert True'))
   reactions.check_response(answer,reaction)
   with self.assertRaises(ValueError):reactions.check_response(dict(source='source',tests='assert True'),reaction)
 def test_dynamic_reactions_and_general_authoring_keep_distinct_routes(self):
  prompt=gm._prompt('Wait',dict(character_reaction=dict(id='guide',canonical=False)))
  self.assertIn('exactly character_actions and tests',prompt)
  general=gm._prompt('Build an optional area',dict(ok=True))
  self.assertIn('Implement the human request as novel Python',general)
  self.assertIn('Return ONLY JSON {"source"',general)
