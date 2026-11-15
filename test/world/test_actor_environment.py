import json, unittest
from unittest.mock import patch
import test_actor_runtime as fixture
import test_large_agent_terrain as terrain_fixture
from pathlib import Path
from world import actor_runtime as runtime, shared_terrain

class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.ActorRuntimeTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.s=self.f.s
        self.s.persist_generated_cave=True; self.s.archive_generated_areas=True
        self.s._replace_cave(terrain_fixture.LargeAgentTerrain().blob(),label='Public terrain')

    def plan(self,actor='canon_rydel',tiles=None):
        self.f.apply(dict(id='landscape',purpose='Change shared terrain from committed public experience.',steps=[
            dict(id='inspect',tool='world.inspect_environment',args=dict(x=10,y=10,width=4,height=4),after=[]),
            dict(id='reshape',tool='world.reshape_environment',args=dict(observation=dict(result='inspect',key='tool_receipt'),
                tiles=json.dumps(tiles or [dict(x=11,y=11,terrain='water'),dict(x=12,y=11,terrain='tall_grass')])),after=['inspect'])]),actor=actor,version=1 if actor=='canon_wally' else 0)
        self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded')

    def test_actual_surface_change_restart_and_no_replay(self):
        self.plan(); self.assertEqual(runtime.tick(self.s,now=16)['status'],'succeeded')
        revision,payload=self.s._active_terrain()
        self.assertEqual(revision,1)
        self.assertEqual(shared_terrain.validate(self.s.shared_cave,payload),{(11,11):2,(12,11):1})
        self.assertFalse(self.s._active_walkable(11,11))
        events=self.s.memory.history()['events']
        self.assertTrue(any(e['event']=='terrain_changed' and e.get('history_evidence') for e in events))
        self.assertEqual(self.s.objects,[]) # no canonical duplication or relocation
        self.assertIsNone(runtime.tick(self.s,now=22))
        db=self.s.db.execute('PRAGMA database_list').fetchone()[2]
        from test_shared_generated_cave import MemoryAuthority
        self.s.close()
        restored=MemoryAuthority('/tmp/environment-not-listening',Path(db).parent,persist_generated_cave=True,archive_generated_areas=True)
        self.addCleanup(restored.close)
        self.assertEqual(restored._active_terrain(),(revision,payload))
        self.assertIsNone(runtime.tick(restored,now=30))

    def test_another_actor_and_native_transfer(self):
        self.plan('canon_wally');self.assertEqual(runtime.tick(self.s,now=16)['status'],'succeeded')
        token=self.s.create_identity('Visitor')['token']
        c=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
        self.s._line(c,('HELLO 1 Visitor '+token+' SOCIALTRAVELCHATRALLYCAVE9G').encode());c['out'].clear()
        self.s._line(c,b'CAVE GET')
        self.assertIn(b'CAVE TERRAIN ',c['out']);self.assertIn(b'020b0b020c0b01',c['out'])
        # CAVE9 without geometry cannot enter a world whose water surface it lacks.
        c['cave_geometry']=False;c['cave_next']=0;c['out'].clear()
        self.s._line(c,b'CAVE GET');self.assertEqual(c['out'],b'CAVE NONE\n')

    def test_occupied_and_stale_inspection_refuse(self):
        self.plan();before=self.s._active_terrain()
        self.s.peers['Alice']['in_generated_cave']=True
        self.s.peers['Alice']['cave_capable']=True
        self.assertEqual(runtime.tick(self.s,now=16)['status'],'blocked')
        self.assertEqual(self.s._active_terrain(),before)

    def test_stale_refuses(self):
        self.plan();self.s.set_shared_geometry(self.s.shared_cave.identity,[dict(x=14,y=14,terrain='grass')])
        self.assertEqual(runtime.tick(self.s,now=16)['status'],'blocked')
        self.assertEqual(shared_terrain.validate(self.s.shared_cave,self.s._active_terrain()[1]),{(14,14):0})

    def test_outside_inspection_and_disconnect_refuse(self):
        self.plan(tiles=[dict(x=50,y=50,terrain='water')])
        self.assertEqual(runtime.tick(self.s,now=16)['status'],'blocked')
        self.assertEqual(self.s._active_terrain(),(0,b'\0'))

    def test_receipt_failure_rolls_back_surface_and_history(self):
        self.plan();before=self.s.memory.history()['events'];original=runtime._receipt
        def fail(server,actor,row,plan,step,status,result):
            if step['id']=='reshape' and status=='succeeded':raise ValueError('receipt failure')
            return original(server,actor,row,plan,step,status,result)
        with patch.object(runtime,'_receipt',side_effect=fail):
            self.assertEqual(runtime.tick(self.s,now=16)['status'],'blocked')
        self.assertEqual(self.s._active_terrain(),(0,b'\0'))
        self.assertFalse(any(e['event']=='terrain_changed' for e in self.s.memory.history()['events'][len(before):]))

    def test_disconnected_floor_refuses_atomically(self):
        self.plan(tiles=[dict(x=x,y=y,terrain='water') for x,y in [(10,11),(11,10),(12,11),(11,12)]])
        self.assertEqual(runtime.tick(self.s,now=16)['status'],'blocked')
        self.assertEqual(self.s._active_terrain(),(0,b'\0'))

    def test_unchanged_surface_completes_without_new_terrain_revision(self):
        self.s.set_shared_geometry(self.s.shared_cave.identity,[dict(x=11,y=11,terrain='grass')])
        self.plan(tiles=[dict(x=11,y=11,terrain='grass')])
        self.assertEqual(runtime.tick(self.s,now=16)['status'],'succeeded')
        self.assertEqual(self.s._active_terrain()[0],1)
        result=json.loads(self.s.db.execute("SELECT result FROM actor_tool_receipts WHERE step='reshape'").fetchone()[0])
        self.assertFalse(result['changed'])
