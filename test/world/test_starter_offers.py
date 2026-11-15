import sqlite3,tempfile,types,json,unittest
from world import starter_offers as s
class Offers(unittest.TestCase):
 def server(self,path=':memory:'):return types.SimpleNamespace(db=sqlite3.connect(path),link_protocol=types.SimpleNamespace(busy=lambda _:False))
 def args(self,id='variety'):return dict(id=id,species=json.dumps(['CHIKORITA','FENNEKIN','SOBBLE']))
 def test_immutable_restart_close_and_native_ids(self):
  with tempfile.TemporaryDirectory() as d:
   server=self.server(d+'/db')
   with server.db:r=s.publish(server,'birch',{},self.args())
   with self.assertRaises(ValueError):s.publish(server,'other',{},self.args())
   changed=self.args();changed['species']=json.dumps(['TREECKO','TORCHIC','MUDKIP'])
   with self.assertRaises(ValueError):s.publish(server,'birch',{},changed)
   server.db.close();server=self.server(d+'/db');c=dict(id='a',presence=dict(campaign_run='a'))
   line=s.handle(server,c,f"SO GET 1 variety {r['revision']}".encode())
   self.assertEqual(line,'SO OFFER 1 '+' '.join(str(s.SPECIES[n]) for n in ['CHIKORITA','FENNEKIN','SOBBLE'])+'\n')
   with self.assertRaises(ValueError):s.close(server,'other',{},dict(id='variety'))
   s.close(server,'birch',{},dict(id='variety'));self.assertEqual(s.handle(server,c,f"SO GET 2 variety {r['revision']}".encode()),'SO ERROR 2\n')
 def test_tools_catalog_validation_and_rollback(self):
  server=self.server();s.setup(server.db);server.db.commit()
  self.assertEqual(len(s.tool(server,'a',{},dict(operation='inspect',value=''))['species']),27)
  for species in ['null','[]','[1,2,3]','["MEWTWO","TREECKO","MUDKIP"]','["TREECKO","TREECKO","MUDKIP"]']:
   with self.assertRaises(ValueError):s.publish(server,'a',{},dict(id='x',species=species))
  with self.assertRaises(RuntimeError):
   with server.db:s.publish(server,'a',{},self.args());raise RuntimeError()
  self.assertEqual(s.catalog(server),[])
  result=s.tool(server,'a',{},dict(operation='publish',value=json.dumps(dict(id='x',species=['TREECKO','TORCHIC','MUDKIP']))));self.assertIn('revision',result)
  self.assertTrue(any('/starter load' in l for l in s.command(server,{},['page','0'])))
 def test_context_capacity_and_withdrawal(self):
  server=self.server();r=s.publish(server,'a',{},self.args());raw=f"SO GET 1 variety {r['revision']}".encode()
  self.assertEqual(s.handle(server,dict(id='a',presence={}),raw),'SO ERROR 1\n')
  server.link_protocol.busy=lambda _:True;self.assertEqual(s.handle(server,dict(id='a',presence=dict(campaign_run='s')),raw),'SO ERROR 1\n')
  for n in range(31):s.publish(server,'a',{},self.args('offer'+str(n)))
  with self.assertRaises(ValueError):s.publish(server,'a',{},self.args('extra'))
  s.close(server,'a',{},dict(id='variety'));s.publish(server,'a',{},self.args('extra'))
  with self.assertRaises(ValueError):s.publish(server,'a',{},self.args())
