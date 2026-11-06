"""Native item allocation and reachable, progression-gated acquisition data."""
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


class MegaAcquisitionTests(unittest.TestCase):
    def test_old_item_ids_and_explicit_stone_mapping(self):
        old = subprocess.check_output(['git', 'show', '9bddf20337bbbaceb5db4a543b0eb43962f00b37:include/constants/items.h'], cwd=ROOT, text=True)
        current = (ROOT/'include/constants/items.h').read_text()
        pattern = r'^#define (ITEM_[A-Z0-9_]+) (\d+)\s*$'
        before = dict(re.findall(pattern, old, re.M))
        after = dict(re.findall(pattern, current, re.M))
        self.assertTrue(before)
        for name, value in before.items():
            self.assertEqual(after[name], value, name)
        old_values = {int(v) for v in before.values()}
        allocated = [int(v) for k, v in after.items() if k not in before]
        self.assertFalse(old_values.intersection(allocated))
        self.assertEqual(len(allocated), len(set(allocated)))
        forms = (ROOT/'src/platform/mega_forms.c').read_text()
        for name in ['VENUSAURITE','CHARIZARDITE_Y','ALAKAZITE','SLOWBRONITE','GENGARITE','STARMINITE','MEWTWONITE_Y','TYRANITARITE','SCEPTILITE','BLAZIKENITE','SWAMPERTITE','MEDICHAMITE','MANECTITE','CHIMECHITE','LATIASITE','LATIOSITE']:
            self.assertIn(f'case ITEM_{name}: return MEGA_STONE_{name};', forms)

    def test_rock_display_offers_ring_and_paid_matching_stones(self):
        script = (ROOT/'data/maps/MossdeepCity_StevensHouse/scripts.inc').read_text()
        self.assertIn('callnative MegaGame_CheckAcquisition', script)
        self.assertIn('giveitem ITEM_MEGA_RING', script)
        self.assertIn('checkitem ITEM_MEGA_RING', script)
        self.assertIn('pokemart MossdeepCity_StevensHouse_MegaStones', script)
        shop = script.split('MossdeepCity_StevensHouse_MegaStones:')[1].split('.endif')[0]
        self.assertEqual(shop.count('.2byte ITEM_'), 17)  # 16 stones and terminator
        items = (ROOT/'src/data/items.h').read_text()
        for block in re.findall(r'\[ITEM_\w+\] = \{[^}]+\}', items):
            if 'sMegaStoneDesc' in block:
                self.assertIn('.price = 10000', block)


if __name__ == '__main__':
    unittest.main()
