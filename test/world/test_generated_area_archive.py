"""Durable generated-area catalog using a socket-free real authority."""
from pathlib import Path
import tempfile
import unittest
from test_large_generated_cave import DOC
from test_shared_generated_cave import MemoryAuthority
from world import cave_blueprint,large_cave,wilds
from world.shared_cave import SharedCave

class GeneratedAreaArchive(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        proposal=cave_blueprint.proposal_from_blueprint(DOC,side=63)
        self.cave=large_cave.encode_wildlife(proposal,'ice',20,[{'species':'MAGIKARP','level':5}]*12)
        self.wilds=wilds.encode(proposal)
    def server(self,**kwargs):return MemoryAuthority(self.root/'socket',self.root/'world',**kwargs)

    def test_revisit_and_restart_without_touching_trainer_save(self):
        server=self.server(persist_generated_cave=True,archive_generated_areas=True)
        try:
            ident=server.create_identity('Alice');save=Path(ident['save_path']);save.write_bytes(b'private save')
            a=server._replace_cave(self.cave,label='Icy grotto');b=server._replace_cave(self.wilds,label='Green islands')
            rows=server.list_generated_areas();self.assertEqual({r['identity'] for r in rows},{a,b})
            self.assertEqual({r['label'] for r in rows},{'Icy grotto','Green islands'});self.assertTrue(next(r for r in rows if r['identity']==b)['active'])
            self.assertTrue(all('template' not in r for r in rows))
        finally:server.close()
        server=self.server(persist_generated_cave=True,archive_generated_areas=True)
        try:
            self.assertEqual(server.shared_cave.identity,b);self.assertEqual(len(server.list_generated_areas()),2)
            self.assertEqual(server.activate_generated_area(a),a);self.assertEqual(server.shared_cave.identity,a)
            self.assertEqual(save.read_bytes(),b'private save')
        finally:server.close()

    def test_occupied_area_and_corrupt_archive_are_not_activated(self):
        server=self.server(persist_generated_cave=True,archive_generated_areas=True)
        try:
            a=server._replace_cave(self.cave);b=server._replace_cave(self.wilds)
            server.peers['busy']={'state':[server.wilds_map[0],server.wilds_map[1],1,1,1,7,1],'closing':False}
            with self.assertRaises(ValueError):server.activate_generated_area(a)
            self.assertEqual(server.shared_cave.identity,b);server.peers.clear()
            with server.db:server.db.execute('UPDATE generated_area_archive SET template=? WHERE identity=?',(b'tampered',a))
            with self.assertRaises(ValueError):server.activate_generated_area(a)
            self.assertEqual(server.shared_cave.identity,b)
        finally:server.close()

    def test_archive_write_failure_rolls_back_active_template(self):
        server=self.server(persist_generated_cave=True,archive_generated_areas=True)
        try:
            a=server._replace_cave(self.cave)
            server.db.execute("CREATE TRIGGER block_archive BEFORE INSERT ON generated_area_archive BEGIN SELECT RAISE(ABORT,'full'); END")
            with self.assertRaises(ValueError):server._replace_cave(self.wilds)
            self.assertEqual(server.shared_cave.identity,a)
            stored=server.db.execute('SELECT template FROM generated_cave WHERE singleton=1').fetchone()[0]
            self.assertEqual(SharedCave(stored).identity,a)
        finally:server.close()

    def test_existing_single_template_migrates_and_default_stays_opt_in(self):
        server=self.server(persist_generated_cave=True)
        try:
            old=server._replace_cave(self.cave)
            with self.assertRaises(ValueError):server.list_generated_areas()
        finally:server.close()
        server=self.server(persist_generated_cave=True,archive_generated_areas=True)
        try:self.assertEqual(server.list_generated_areas()[0]['identity'],old)
        finally:server.close()
        with self.assertRaises(ValueError):self.server(archive_generated_areas=True)
