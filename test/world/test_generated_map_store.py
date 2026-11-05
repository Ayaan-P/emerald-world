import copy
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from world import procedural_map as pm
from world import generated_map_store as store

def plan(seed=1):
    return {'schema':1,'seed':seed,'width':15,'height':11,'rooms':2,'room_size':3,'biome':'cave','points':['landmark']}

class GeneratedStoreTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.s=store.GeneratedMapStore(self.db)
    def tearDown(self):self.db.close()
    def test_publish_is_immutable_idempotent_and_revalidated(self):
        doc=pm.generate(plan());identifier=self.s.publish('seeded',doc)
        self.assertEqual(self.s.publish('seeded',doc),identifier)
        self.assertEqual(self.s.get(identifier),('seeded',doc))
        self.assertEqual(self.db.execute(f'SELECT count(*) FROM {store.TABLE}').fetchone()[0],1)
        tampered=copy.deepcopy(doc);tampered['rows'][1]='#'*15
        with self.assertRaises(store.StoreError):self.s.publish('seeded',tampered)
        self.assertEqual(self.s.get(identifier),('seeded',doc))
    def test_proposal_roundtrip_and_unknown_kind(self):
        doc=pm.generate(plan());proposal=pm.accept_proposal({k:doc[k] for k in ('rows','spawn','exit','points')} | {'schema':1,'biome':'cave'})
        self.assertEqual(self.s.get(self.s.publish('proposal',proposal)),('proposal',proposal))
        with self.assertRaises(store.StoreError):self.s.publish('code','print(1)')
    def test_invalid_identifier_and_corrupted_storage_fail_closed(self):
        doc=pm.generate(plan());identifier=self.s.publish('seeded',doc)
        with self.assertRaises(store.StoreError):self.s.get('../bad')
        self.db.execute(f'UPDATE {store.TABLE} SET document=? WHERE id=?',('{"bad":1}',identifier))
        with self.assertRaises(store.StoreError):self.s.get(identifier)
        self.assertIsNone(self.s.get('0'*64))
    def test_outer_transaction_can_rollback(self):
        self.db.commit();self.db.execute('BEGIN')
        identifier=self.s.publish('seeded',pm.generate(plan()))
        self.db.rollback();self.assertIsNone(self.s.get(identifier))
    def test_existing_id_with_different_content_is_rejected(self):
        doc=pm.generate(plan());identifier=doc['sha256']
        self.db.execute(f'INSERT INTO {store.TABLE} VALUES (?,?,?)',(identifier,'seeded','{}'))
        with self.assertRaisesRegex(store.StoreError,'different content'):self.s.publish('seeded',doc)
    def test_capacity_and_duplicate_at_capacity(self):
        saved=store.MAX_MAPS;store.MAX_MAPS=2
        try:
            a=pm.generate(plan(1));b=pm.generate(plan(2));c=pm.generate(plan(3))
            self.s.publish('seeded',a);self.s.publish('seeded',b)
            self.assertEqual(self.s.publish('seeded',a),a['sha256'])
            with self.assertRaisesRegex(store.StoreError,'capacity'):self.s.publish('seeded',c)
        finally:store.MAX_MAPS=saved
    def test_concurrent_publish_is_idempotent_across_connections(self):
        import threading
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'world.sqlite';init=sqlite3.connect(path);store.GeneratedMapStore(init);init.commit();init.close()
            document=pm.generate(plan(44));barrier=threading.Barrier(4);results=[];errors=[]
            def worker():
                try:
                    db=sqlite3.connect(path,timeout=5);writer=store.GeneratedMapStore(db)
                    barrier.wait(timeout=5);results.append(writer.publish('seeded',document));db.commit();db.close()
                except BaseException as error:errors.append(error)
            threads=[threading.Thread(target=worker) for _ in range(4)]
            for thread in threads:thread.start()
            for thread in threads:thread.join(timeout=8)
            self.assertFalse(any(t.is_alive() for t in threads));self.assertEqual(errors,[])
            self.assertEqual(results,[document['sha256']]*4)
            db=sqlite3.connect(path);self.assertEqual(db.execute(f'SELECT count(*) FROM {store.TABLE}').fetchone()[0],1);db.close()

    def test_persists_across_connections(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'test.sqlite';a=sqlite3.connect(path);s=store.GeneratedMapStore(a)
            doc=pm.generate(plan());identifier=s.publish('seeded',doc);a.commit();a.close()
            b=sqlite3.connect(path);self.assertEqual(store.GeneratedMapStore(b).get(identifier),('seeded',doc));b.close()

if __name__=='__main__':unittest.main()
