"""Generated atlas publication and real REGION1 selection without shared activation."""
import copy
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import test_region_admission as fixture
from world.region_atlas import compile_atlas,main


def atlas():
    return dict(title='Lantern Archipelago',regions=[
        dict(label=label,blueprint=dict(rooms=[[1,1,5,5],[x,12,6,5],[21,22,6,6]],
             links=[[0,1],[1,2]],entrance_room=0,exit_room=2,style=style,seed=71,corridor_width=width))
        for label,x,style,width in [('Tide Vault',8,'rounded',1),('Moss Library',12,'organic',2),('Star Observatory',17,'maze',3)]])


class AtlasTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.RegionAdmissionTests();self.f.setUp();self.addCleanup(self.f.tearDown)
        self.s=self.f.server
    def request(self,apply=False,plan=None):
        return dict(command='publish_atlas' if apply else 'preview_atlas',plan=plan or atlas(),
                    expected_world_id=self.s.memory.world_id,
                    expected_sequence=self.s.db.execute('SELECT coalesce(max(seq),0) FROM events').fetchone()[0])
    def count(self,table):return self.s.db.execute('SELECT count(*) FROM '+table).fetchone()[0]
    def publish(self,plan=None):
        result=self.f.admin(self.request(True,plan));self.assertTrue(result['ok'],result);return result

    def test_preview_then_publish_concurrent_regions_restart_and_return(self):
        visitor=self.f.connect('Visitor');visitor.select_region(self.f.ra['place_id']);self.f.enter(visitor)
        occupant=self.f.connect('Default')
        occupant.sock.sendall(b'CAVE GET\n');occupant.sock.conn['out'].clear()
        occupant.sock.sendall(('CAVE ACK '+self.s.shared_cave.identity+'\n').encode());occupant.sock.conn['out'].clear()
        self.f.enter(occupant)
        active=self.s.shared_cave.identity;previous=self.s.db.execute('SELECT template FROM generated_cave').fetchone()
        ack=visitor.sock.conn['cave_ack'];default_ack=occupant.sock.conn.get('cave_ack')
        before=self.s.db.total_changes;preview=self.f.admin(self.request())
        self.assertTrue(preview['ok'],preview);self.assertEqual(self.s.db.total_changes,before)
        self.assertNotIn('place_id',preview['regions'][0])
        result=self.publish();self.assertEqual(len(result['regions']),3)
        self.assertEqual(self.s.shared_cave.identity,active)
        self.assertEqual(self.s.db.execute('SELECT template FROM generated_cave').fetchone(),previous)
        self.assertEqual(visitor.sock.conn['cave_ack'],ack);self.assertEqual(occupant.sock.conn.get('cave_ack'),default_ack)
        menu=visitor.sock.conn
        menu['out'].clear();self.s._line(menu,b'REGION LIST 0');first=menu['out'].decode()
        menu['out'].clear();self.s._line(menu,b'REGION LIST 4');second=menu['out'].decode()
        self.assertIn('REGION BEGIN 0 4 4',first);self.assertIn('REGION BEGIN 4 1 0',second)
        for region in result['regions']:self.assertIn(region['place_id'],first+second)
        a=self.f.connect('Alice');b=self.f.connect('Bob');c=self.f.connect('Carol')
        places=result['regions']
        for client,region in ((a,places[0]),(b,places[1]),(c,places[0])):
            client.select_region(region['place_id']);self.f.enter(client)
            self.assertEqual(client.sock.conn['cave_ack'],region['revision'])
        self.assertIn('PEER Carol ',self.s._snapshot(a.sock.conn));self.assertNotIn('PEER Bob ',self.s._snapshot(a.sock.conn))
        with self.assertRaisesRegex(ValueError,'refused'):a.select_region(places[2]['place_id'])
        self.f.outside(a);a.select_region(places[2]['place_id']);self.f.enter(a)
        self.assertEqual(a.sock.conn['cave_ack'],places[2]['revision'])
        events=[e for e in self.s.memory.history()['events'] if e.get('atlas_id')==result['atlas_id']]
        self.assertEqual(len(events),3);self.assertTrue(all(e['event']=='region_opened' for e in events))
        self.assertFalse(any(e['event']=='area_activated' and e.get('revision') in {p['revision'] for p in places} for e in self.s.memory.history()['events']))
        self.s.close();self.f.server=self.f.open();self.s=self.f.server
        again=self.publish();self.assertFalse(again['applied']);self.assertTrue(again['already_published'])
        self.assertEqual(again['regions'],places)
        returning=self.f.connect('Returner');returning.select_region(places[0]['place_id']);self.f.enter(returning)
        self.assertEqual(returning.sock.conn['cave_ack'],places[0]['revision'])

    def test_bad_last_destination_and_duplicate_geometry_add_nothing(self):
        before=(self.count('generated_area_archive'),self.count('world_region_revisions'),self.count('events'))
        bad=atlas();bad['regions'][-1]['blueprint']['links']=[]
        result=self.f.admin(self.request(True,bad));self.assertFalse(result['ok'])
        bad=atlas();bad['regions'][1]['blueprint']=copy.deepcopy(bad['regions'][0]['blueprint'])
        result=self.f.admin(self.request(True,bad));self.assertFalse(result['ok'])
        self.assertEqual((self.count('generated_area_archive'),self.count('world_region_revisions'),self.count('events')),before)
        self.assertEqual(self.count('world_region_atlases'),0)

    def test_late_manifest_and_history_failure_roll_back_all_maps(self):
        before={table:self.count(table) for table in ('generated_area_archive','world_region_revisions','world_places','events')}
        for trigger in ("BEFORE INSERT ON world_region_atlases", "BEFORE INSERT ON events WHEN NEW.kind='world_memory' AND json_extract(NEW.data,'$.label')='Star Observatory'"):
            self.s.db.execute("CREATE TRIGGER deny_atlas "+trigger+" BEGIN SELECT RAISE(ABORT,'test'); END")
            result=self.f.admin(self.request(True));self.assertFalse(result['ok']);self.assertIn('no destinations',result['error'])
            self.assertEqual({table:self.count(table) for table in before},before)
            self.s.db.execute('DROP TRIGGER deny_atlas')
        self.assertTrue(self.publish()['applied'])

    def test_stale_world_and_conflicting_archive_refuse_without_renaming(self):
        request=self.request(True);request['expected_world_id']='another-world'
        self.assertFalse(self.f.admin(request)['ok'])
        request=self.request(True);request['expected_sequence']-=1
        self.assertFalse(self.f.admin(request)['ok'])
        _,items=compile_atlas(atlas());item=items[0]
        self.s._replace_cave(item['blob'],label='Original name')
        self.assertFalse(self.f.admin(self.request(True))['ok'])
        self.assertEqual(self.s.db.execute('SELECT label FROM generated_area_archive WHERE identity=?',(item['revision'],)).fetchone()[0],'Original name')
        self.assertEqual(self.count('world_region_atlases'),0)

    def test_existing_same_named_map_and_existing_place_pin_are_not_overwritten(self):
        _,items=compile_atlas(atlas())
        with self.s.db:self.s.db.execute('UPDATE generated_area_archive SET label=? WHERE identity=?',('Tide Vault',self.f.a))
        self.assertFalse(self.f.admin(self.request(True))['ok'])
        with self.s.db:self.s.db.execute('UPDATE generated_area_archive SET label=? WHERE identity=?',('Harbor',self.f.a))
        # An archived revision already attached to a place with another immutable pin.
        item=items[0]
        with self.s.db:
            self.s.db.execute('INSERT INTO generated_area_archive VALUES (?,?,?,?,?)',(item['revision'],item['label'],'cave',item['blob'],0))
            self.s.db.execute('INSERT INTO world_places VALUES (?,?)',(item['revision'],self.f.ra['place_id']))
        self.assertFalse(self.f.admin(self.request(True))['ok'])
        self.assertEqual(self.count('world_region_atlases'),0)
        self.assertEqual(self.s.db.execute('SELECT revision FROM world_region_revisions WHERE place_id=?',(self.f.ra['place_id'],)).fetchone()[0],self.f.a)

    def test_cli_preview_and_apply_use_real_admin_dispatch(self):
        path=self.f.root/'atlas.json';path.write_text(json.dumps(atlas()))
        with patch('world.client.admin_request',side_effect=lambda _,req,**kw:self.f.admin(req)),patch('sys.stdout',new_callable=io.StringIO):
            self.assertEqual(main([str(path),'--admin-socket','fixture']),0)
            self.assertEqual(self.count('world_region_atlases'),0)
            self.assertEqual(main([str(path),'--admin-socket','fixture','--apply']),0)
        self.assertEqual(self.count('world_region_atlases'),1)

if __name__=='__main__':unittest.main()
