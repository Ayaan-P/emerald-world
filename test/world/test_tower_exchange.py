import sqlite3,tempfile,types,unittest
from world import tower_exchange as t
class Exchange(unittest.TestCase):
 def server(self,path=':memory:'):return types.SimpleNamespace(db=sqlite3.connect(path),link_protocol=types.SimpleNamespace(busy=lambda _:False))
 def conn(self,owner='alice',save='save_a'):return dict(id=owner,presence=dict(campaign_run=save))
 def payload(self,streak=7):return (bytes([1,0,1])+streak.to_bytes(2,'little')+bytes(144)).hex()
 def test_offline_restart_exact_revision_and_withdrawal(self):
  with tempfile.TemporaryDirectory() as d:
   s=self.server(d+'/db');p=self.payload();a=self.conn()
   self.assertEqual(t.handle(s,a,f'TR PUT 1 {p}'.encode()),'TR ACK 1\n');row=t.catalog(s)[0]
   self.assertEqual(row['streak'],7);self.assertNotIn('save_a',str(row));s.db.close()
   s=self.server(d+'/db');b=self.conn('bob')
   self.assertEqual(t.handle(s,b,f"TR GET 1 {row['id']} {row['revision']}".encode()),f'TR DATA 1 {p}\n')
   self.assertEqual(t.handle(s,self.conn(),b'TR DROP 1'),'TR ACK 1\n');self.assertEqual(t.catalog(s),[])
   self.assertEqual(t.handle(s,b,f"TR GET 2 {row['id']} {row['revision']}".encode()),'TR ERROR 2\n')
 def test_independent_saves_update_replay_and_old_revision(self):
  s=self.server();a=self.conn();other=self.conn(save='b')
  t.handle(s,a,f'TR PUT 1 {self.payload()}'.encode());row=t.catalog(s)[0]
  t.handle(s,other,f'TR PUT 1 {self.payload()}'.encode());self.assertEqual(len(t.catalog(s)),2)
  t.handle(s,a,f'TR PUT 2 {self.payload(9)}'.encode())
  self.assertEqual(t.handle(s,a,f"TR GET 3 {row['id']} {row['revision']}".encode()),'TR ERROR 3\n')
  self.assertEqual(t.handle(s,a,b'TR DROP 3'),'TR ERROR 3\n');self.assertEqual(len(t.catalog(s)),2)
  t.handle(s,a,b'TR DROP 4');self.assertEqual(len(t.catalog(s)),1)
 def test_malformed_busy_unbound_and_catalog(self):
  s=self.server();c=self.conn()
  for i,p in enumerate(('bad','00'*149,self.payload(0)),1):self.assertEqual(t.handle(s,c,f'TR PUT {i} {p}'.encode()),f'TR ERROR {i}\n')
  t.handle(s,c,f'TR PUT 4 {self.payload()}'.encode());self.assertIn('/towerrecord get',' '.join(t.command(s,c,['page','0'])))
  c['presence'].clear();self.assertEqual(t.handle(s,c,b'TR DROP 5'),'TR ERROR 5\n')
  s.link_protocol.busy=lambda _:True;self.assertEqual(t.handle(s,self.conn(),b'TR DROP 1'),'TR ERROR 1\n')
 def test_namespace_not_old_record_mixing_transport(self):
  s=self.server();c=self.conn();c['neighborhood_seq']=100
  self.assertEqual(t.handle(s,c,f'TR PUT 1 {self.payload()}'.encode()),'TR ACK 1\n')
  self.assertEqual(t.handle(s,c,b'T DROP 2'),'TR ERROR 0\n')
