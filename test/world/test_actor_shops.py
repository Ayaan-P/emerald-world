import json,unittest
import test_characters
from world import actor_shops as shops,actor_runtime

class RetailTests(unittest.TestCase):
 def setUp(self):
  self.f=test_characters.CharacterLifecycleTests();self.f.setUp();self.addCleanup(self.f.tearDown);self.s=self.f.server
  self.assertIsNone(self.f.commit({'may':self.f.character},self.f.npc))
 def test_catalog_native_negotiation_close_and_restart(self):
  peer=self.f.peer(role='SOCIALCHAR1CHARSHOP1')
  with self.s.db:r=shops.configure(self.s,'may',{},dict(items='[1,28,114]'))
  self.assertIn('CHARACTER_SHOP may 1',self.s._snapshot(peer))
  old=self.f.peer('Old',role='SOCIALCHAR1')
  self.assertNotIn('CHARACTER_SHOP',self.s._snapshot(old))
  self.s.close();self.f.server=self.f.open();self.s=self.f.server
  self.assertEqual(shops.catalog(self.s)['services']['may']['items'],[1,28,114])
  with self.s.db:shops.configure(self.s,'may',{},dict(items='[]'))
  self.assertIsNone(shops.line(self.s,dict(character_shop_capable=True),'may',1))
 def test_general_author_plan_admits_catalog_without_claiming_sale(self):
  c=dict(self.f.character,version=2,reason='Choose to offer ordinary supplies.',evidence=[self.s.revision],
   plan=dict(id='service',purpose='Offer travel supplies.',steps=[dict(id='open',tool='world.configure_shop',args=dict(items='[2,29]'),after=[])]))
  self.assertIsNone(self.f.commit({'may':c},self.f.npc))
  self.assertEqual(actor_runtime.tick(self.s,now=10)['status'],'succeeded')
  self.assertEqual(shops.catalog(self.s)['services']['may']['items'],[2,29])
  self.assertFalse(any(e.get('event')=='purchase' for e in self.s.memory.history()['events']))
 def test_no_unknown_key_item_free_catalog_or_duplicates(self):
  for data in ('[4]','[999]','[1,1]','[true]','[1,2,3,28,29,30,31,32,33]'):
   with self.assertRaises(ValueError):shops.configure(self.s,'may',{},dict(items=data))

 def test_actual_authority_snapshot_through_native_parser_and_shop(self):
  import importlib.util,pathlib,tempfile,subprocess,os,re
  path=pathlib.Path(os.environ.get('EW_RETAIL_NATIVE_SOURCE','../native-npc-retail')).resolve()
  if not (path/'tests/test_retail.py').exists():self.skipTest('Exact retail native source unavailable')
  peer=self.f.peer(role='SOCIALCHAR1CHARSHOP1')
  with self.s.db:shops.configure(self.s,'may',{},dict(items='[1,28,114]'))
  wire=next(x for x in self.s._snapshot(peer).splitlines() if x.startswith('CHARACTER_SHOP '))
  spec=importlib.util.spec_from_file_location('retail_native',path/'tests/test_retail.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  with tempfile.TemporaryDirectory() as d:subprocess.run([str(module.build(d,wire))],check=True,capture_output=True)
  header=(path/'include/constants/items.h').read_text()
  for item in shops.ITEMS:self.assertRegex(header,r'ITEM_[A-Z_]+ = '+str(item)+r',')
