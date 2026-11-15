from test_combined_regions import WireHandlers
from world import combined_regions as regions
class ConnectedTravel(WireHandlers):
 def test_v2_ack_and_actual_region_round_trip(self):
  a,l=self.peer('Alice',False)
  self.assertEqual(self.send(l,'RGC 2 '+regions.DIGEST),'RGC OK 2 '+regions.DIGEST+'\n')
  self.state(a,1,0,1,19,20)
  self.state(a,2,38,0,6,8)
  self.assertEqual(a['state'][:4],[38,0,6,8])
  self.state(a,3,0,1,19,20)
  self.assertEqual(a['state'][:4],[0,1,19,20])
  self.s._drop(l)
  a,l=self.peer('Alice',False)
  self.state(a,1,38,0,6,8);self.assertIsNone(a['state'])
 def test_v1_has_no_unknown_ack(self):
  a,l=self.peer('Alice',False)
  self.assertEqual(self.send(l,'RGC 1 '+regions.DIGEST),'')
 def test_unknown_version_fails_closed(self):
  a,l=self.peer('Alice',False)
  self.assertIn('ERROR REGISTRY',self.send(l,'RGC 3 '+regions.DIGEST))
