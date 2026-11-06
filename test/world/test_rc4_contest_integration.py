"""Expanded contest records must initialize the move table, not function pointers."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]

class ContestIntegrationTests(unittest.TestCase):
    def test_expanded_records_are_inside_the_move_table(self):
        source = (ROOT / 'src/data/contest_moves.h').read_text()
        tables = dict(re.findall(r'(gContest\w+)\s*\[[^\]]*\][^=]*=\s*\{(.*?)^};', source, re.M | re.S))
        include = '#include "expanded_moves/contest_moves.h"'
        self.assertIn(include, tables['gContestMoves'])
        self.assertNotIn(include, tables['gContestEffectFuncs'])
