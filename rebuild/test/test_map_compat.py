import importlib.util
from pathlib import Path
import unittest
p=Path(__file__).resolve().parents[1]/'scripts/map_compat.py'
spec=importlib.util.spec_from_file_location('map_compat',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class MapCompatibility(unittest.TestCase):
 def test_only_identical_names_and_ids(self):
  w={'group_order':['a','b'],'a':['A','B'],'b':['C','WorldOnly']}
  e={'group_order':['a','b'],'a':['A','Different'],'b':['C','New']}
  self.assertEqual(m.compatible(w,e),[0,256])
 def test_rejects_duplicate_map_names(self):
  with self.assertRaises(ValueError):m.ids({'group_order':['a'],'a':['A','A']})
if __name__=='__main__':unittest.main()
