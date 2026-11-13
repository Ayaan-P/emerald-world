import sqlite3,tempfile,types,unittest
from world import base_neighborhood as b
class Neighborhood(unittest.TestCase):
 def server(self,path=':memory:'):
  return types.SimpleNamespace(db=sqlite3.connect(path),link_protocol=types.SimpleNamespace(busy=lambda _:False))
 def conn(self,owner='alice',save='save_a'):return dict(id=owner,presence=dict(campaign_run=save))
 def payload(self,location=1):return f'{location:02x}'+'00'*153
 def test_restart_offline_exact_download_and_revoke(self):
  with tempfile.TemporaryDirectory() as d:
   s=self.server(d+'/db');c=self.conn();p=self.payload()
   self.assertEqual(b.handle(s,c,f'B PUT 1 {p}'.encode()),'B ACK 1\n')
   row=b.catalog(s)[0];self.assertNotIn('lineage',row);self.assertNotIn('save_a',str(row));s.db.close()
   s=self.server(d+'/db');guest=self.conn('bob','other')
   self.assertEqual(b.handle(s,guest,f"B GET 1 {row['id']} {row['revision']}".encode()),f'B DATA 1 {p}\n')
   self.assertEqual(b.handle(s,self.conn(),b'B DROP 1'),'B ACK 1\n');self.assertEqual(b.catalog(s),[])
   self.assertEqual(b.handle(s,guest,f"B GET 2 {row['id']} {row['revision']}".encode()),'B ERROR 2\n')
 def test_save_lineages_owner_scope_and_snapshot_update(self):
  s=self.server();a=self.conn();other=self.conn(save='save_b')
  b.handle(s,a,f'B PUT 1 {self.payload()}'.encode());old=b.catalog(s)[0]
  b.handle(s,other,f'B PUT 1 {self.payload(2)}'.encode());self.assertEqual(len(b.catalog(s)),2)
  b.handle(s,self.conn('bob'),b'B DROP 1');self.assertEqual(len(b.catalog(s)),2)
  b.handle(s,a,f'B PUT 2 {self.payload(3)}'.encode())
  self.assertEqual(b.handle(s,a,f"B GET 3 {old['id']} {old['revision']}".encode()),'B ERROR 3\n')
  b.handle(s,a,b'B DROP 4');self.assertEqual(b.catalog(s)[0]['base_location'],2)
 def test_protocol_guards_and_listing(self):
  s=self.server();c=self.conn()
  for i,p in enumerate(('bad',self.payload(0),self.payload(234)),1):self.assertEqual(b.handle(s,c,f'B PUT {i} {p}'.encode()),f'B ERROR {i}\n')
  self.assertEqual(b.catalog(s),[])
  b.handle(s,c,f'B PUT 4 {self.payload()}'.encode());self.assertEqual(b.handle(s,c,b'B DROP 4'),'B ERROR 4\n')
  self.assertTrue(any('/neighborhood get' in x for x in b.command(s,{},['page','0'])))
  c['presence'].clear();self.assertEqual(b.handle(s,c,b'B DROP 5'),'B ERROR 5\n')
  s.link_protocol.busy=lambda _:True
  self.assertEqual(b.handle(s,self.conn(),b'B DROP 1'),'B ERROR 1\n')
 def test_capacity_not_lifetime(self):
  s=self.server()
  for n in range(256):self.assertEqual(b.handle(s,self.conn(str(n)),f'B PUT 1 {self.payload()}'.encode()),'B ACK 1\n')
  self.assertEqual(b.handle(s,self.conn('extra'),f'B PUT 1 {self.payload()}'.encode()),'B ERROR 1\n')
  b.handle(s,self.conn('0'),b'B DROP 1')
  self.assertEqual(b.handle(s,self.conn('extra'),f'B PUT 1 {self.payload()}'.encode()),'B ACK 1\n')
