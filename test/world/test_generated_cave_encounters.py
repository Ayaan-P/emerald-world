"""Validate the generated cave's native encounter data and floor behavior.

Does not launch a real battle or exercise multiplayer battle transitions.
"""
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]

class GeneratedCaveEncounters(unittest.TestCase):
 def test_table_and_cave_floor_are_connected_to_vanilla_encounter_path(self):
  groups=json.loads((ROOT/'src/data/wild_encounters.json').read_text())['wild_encounter_groups']
  entries=next(g['encounters'] for g in groups if g['label']=='gWildMonHeaders')
  generated=[e for e in entries if e.get('map')=='MAP_GENERATED_WORLD_CAVE']
  granite=[e for e in entries if e.get('map')=='MAP_GRANITE_CAVE_1F']
  self.assertEqual(len(generated),1);self.assertEqual(len(granite),1)
  self.assertEqual(generated[0]['land_mons'],granite[0]['land_mons'])
  self.assertEqual(len(generated[0]['land_mons']['mons']),12)
  # Dynamic cave floor 0x333 is the stock cave tileset's MB_CAVE (8).
  attrs=(ROOT/'data/tilesets/secondary/cave/metatile_attributes.bin').read_bytes()
  self.assertEqual(int.from_bytes(attrs[(0x333-512)*2:(0x333-512)*2+2],'little') & 255,8)
  behavior=(ROOT/'src/metatile_behavior.c').read_text()
  self.assertRegex(behavior,r'\[MB_CAVE\]\s*=\s*TILE_FLAG_UNUSED\s*\|\s*TILE_FLAG_HAS_ENCOUNTERS')
  source=(ROOT/'src/platform/generated_map.c').read_text()
  self.assertIn('#define GEN_FLOOR 0x3333',source)
  self.assertIn('#if GENERATED_MAP_READY',source)

if __name__ == '__main__': unittest.main()
