import sqlite3,types,tempfile,unittest
from world import maze_courses as m
class Mazes(unittest.TestCase):
 def server(self,path=':memory:'):return types.SimpleNamespace(db=sqlite3.connect(path),link_protocol=types.SimpleNamespace(busy=lambda _:False))
 def test_immutable_restart_optional_download_close(self):
  with tempfile.TemporaryDirectory() as d:
   s=self.server(d+'/db')
   with s.db:r=m.publish(s,'guide',{},dict(id='maze',seed=501))
   self.assertEqual(len(r['floors']),4)
   with self.assertRaises(ValueError):m.publish(s,'other',{},dict(id='maze',seed=501))
   with self.assertRaises(ValueError):m.publish(s,'guide',{},dict(id='maze',seed=502))
   s.db.close();s=self.server(d+'/db');c=dict(id='a',presence=dict(campaign_run='save'))
   raw=f"MC GET 1 maze {r['revision']}".encode();self.assertEqual(m.handle(s,c,raw),'MC MAZE 1 501\n')
   m.close(s,'guide',{},dict(id='maze'));self.assertEqual(m.handle(s,c,raw),'MC ERROR 1\n')
 def test_all_seeds_connect_entrances_even_with_both_trainers(self):
  digest=2166136261
  for seed in range(4096):
   for floor in range(4):
    rows=m.generate(seed,floor);cells=[c=='.' for row in rows for c in row]
    for c in cells:digest=((digest^c)*16777619)&0xffffffff
    cells[11*16+14]=cells[13*16+14]=False
    seen={1};queue=[1]
    for pos in queue:
     x,y=pos%16,pos//16
     for nx,ny in [(x+1,y),(x-1,y),(x,y+1),(x,y-1)]:
      p=ny*16+nx
      if 0<=nx<16 and 0<=ny<16 and cells[p] and p not in seen:seen.add(p);queue.append(p)
    self.assertIn(13,seen);self.assertEqual(len(seen),sum(cells));self.assertIn(11*16+13,seen);self.assertIn(13*16+13,seen)
  self.assertEqual(digest,3885374541)
 def test_tool_guards_rollback_and_listing(self):
  s=self.server();m.setup(s.db);s.db.commit()
  for seed in [True,-1,4096,'1']:
   with self.assertRaises(ValueError):m.publish(s,'a',{},dict(id='x',seed=seed))
  with self.assertRaises(RuntimeError):
   with s.db:m.publish(s,'a',{},dict(id='x',seed=1));raise RuntimeError()
  self.assertEqual(m.catalog(s),[])
  r=m.tool(s,'a',{},dict(operation='publish',value='{"id":"x","seed":123}'))
  self.assertIn('/maze load',' '.join(m.command(s,{},['page','0'])))
  self.assertEqual(m.tool(s,'a',{},dict(operation='preview',value='123'))['floors'],r['floors'])
  self.assertEqual(m.handle(s,dict(id='a',presence={}),f"MC GET 1 x {r['revision']}".encode()),'MC ERROR 1\n')
