"""Paired field clues, persisted completion, and consequent place stories."""
import copy
import json
import sqlite3
import unittest
from pathlib import Path
from test_opportunities import OpportunityTests, ROOT
from test_shared_generated_cave import MemoryAuthority


class MysteryTests(OpportunityTests):
    def setUp(self):
        super().setUp()
        self.pack=json.loads((ROOT/'examples/cooperative_signal.json').read_text())
        self.story=json.loads((ROOT/'examples/cooperative_signal_story.json').read_text())
        self.assertTrue(self.admin(dict(command='publish_mystery',pack=self.pack))['ok'])
        self.assertTrue(self.admin(dict(command='publish_opportunities',pack=self.story))['ok'])
        self.chat(self.a,'/mystery start signal_v2')
        self.run=self.s.mysteries._current('Alice')[0]
        self.chat(self.b,'/mystery join '+self.run)

    def station(self,conn,index,role):
        g,n,x,y=self.pack['stages'][index]['stations'][role]['at']
        self.s._line(conn,f'STATE {conn["seq"]+1} {g} {n} {x} {y} 1 7 1 {"a"*16} {"b"*16}'.encode())
        self.assertEqual(conn['state'][:4],[g,n,x,y])

    def solve(self,index):
        for role,conn in enumerate((self.a,self.b)):
            self.station(conn,index,role)
            lines=self.chat(conn,'/mystery clue')
            self.assertIn(self.pack['stages'][index]['stations'][role]['clue'],lines)
        return self.chat(self.b,f'/mystery solve {index+1} '+self.pack['stages'][index]['answer'])

    def test_full_two_player_loop_unlocks_choices_and_later_visitors(self):
        sentinel=self.root/'normal.sav';sentinel.write_bytes(b'normal save untouched')
        late=self.connect('Cara')
        self.assertFalse(self.s.opportunities.offers('Alice','RustboroCity','signal_after_v2'))
        first=self.solve(0)
        self.assertTrue(any('Stage 2' in line for line in first))
        self.assertFalse(self.a['chat_history'])
        result=self.solve(1)
        self.assertIn(self.pack['ending'],result)
        for name in ('Alice','Bob'):
            self.assertTrue(self.s.mysteries.completed(name,'signal_v2'))
            self.assertTrue(self.s.opportunities.offers(name,'RustboroCity','signal_after_v2'))
        self.assertFalse(self.s.opportunities.offers('Cara','RustboroCity','signal_after_v2'))
        lines=self.chat(self.a,'/story signal_after_v2')
        choice=next(x for x in lines if '/story pick signal_after_v2 decision restore ' in x)
        self.chat(self.a,choice)
        self.assertFalse(late['chat_history'])
        scenes=self.s.opportunities.offers('Cara','RustboroCity','signal_after_v2')[0]['scenes']
        self.assertEqual([x['id'] for x in scenes],['warning'])
        self.assertEqual(sentinel.read_bytes(),b'normal save untouched')
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM mystery_solved').fetchone()[0],2)

    def test_resume_survives_restart_but_requires_fresh_presence(self):
        self.solve(0)
        self.s.close();self.s=MemoryAuthority(self.root/'sock',self.root/'world')
        self.assertEqual(self.s.mysteries._current('Alice')[2],1)
        with self.assertRaisesRegex(ValueError,'Stand ready'):
            self.s.mysteries.command('Alice',['clue'])
        self.a=self.connect('Alice');self.b=self.connect('Bob')
        self.solve(1)
        self.s.close();self.s=MemoryAuthority(self.root/'sock',self.root/'world')
        self.assertIn(self.pack['ending'],self.s.mysteries.status('Alice'))
        self.assertTrue(self.s.mysteries.completed('Bob','signal_v2'))
        self.assertTrue(self.s.opportunities.offers('Alice','RustboroCity','signal_after_v2'))

    def test_private_clue_and_fresh_two_station_requirements(self):
        self.station(self.a,0,0)
        own=self.chat(self.a,'/MYSTERY clue')
        self.assertIn(self.pack['stages'][0]['stations'][0]['clue'],own)
        self.assertFalse(self.b['chat_history'])
        self.station(self.b,0,1)
        reply=self.chat(self.b,'/mystery solve 1 SUNRISE')
        self.assertTrue(any('read their current clue' in x for x in reply))
        self.chat(self.b,'/mystery clue');self.a['state_time']-=100
        self.assertTrue(any('Both partners' in x for x in self.chat(self.b,'/mystery solve 1 SUNRISE')))
        self.assertEqual(self.s.mysteries._current('Bob')[2],0)

    def test_atomic_completion_and_duplicate_stage_protection(self):
        self.s.db.execute("CREATE TRIGGER fail_solve BEFORE UPDATE ON mystery_runs BEGIN SELECT RAISE(ABORT,'fixture'); END")
        result=self.solve(0)
        self.assertTrue(any('transaction failed' in x for x in result))
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM mystery_solved').fetchone()[0],0)
        self.assertEqual(self.s.mysteries._current('Bob')[2],0)
        self.s.db.execute('DROP TRIGGER fail_solve');self.solve(0)
        repeat=self.chat(self.b,'/mystery solve 1 SUNRISE')
        self.assertTrue(any('not the current stage' in x for x in repeat))
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM mystery_solved').fetchone()[0],1)

    def test_immutable_content_and_nonparticipant_cannot_take_completion(self):
        modified=copy.deepcopy(self.pack);modified['title']='Changed'
        self.assertFalse(self.admin(dict(command='publish_mystery',pack=modified))['ok'])
        unknown=copy.deepcopy(self.story);unknown['id']='bad';unknown['scenes']['decision']['mystery']='missing'
        self.assertFalse(self.admin(dict(command='publish_opportunities',pack=unknown))['ok'])
        third=self.connect('Cara')
        self.assertTrue(any('unavailable' in x for x in self.chat(third,'/mystery join '+self.run)))
        self.chat(self.a,'/mystery leave')
        self.assertFalse(self.s.mysteries.completed('Alice','signal_v2'))
        self.assertTrue(any('ended' in x for x in self.chat(self.b,'/mystery status')))

class AuthoredStationTests(unittest.TestCase):
    def test_preset_stations_are_clear_connected_ground_in_released_layouts(self):
        import hashlib
        import struct
        from collections import deque
        # These exact blobs were verified against native main 7d463da (RC11).
        # This static test does not replace rendered native two-client QA.
        hashes={'PetalburgCity':'35f0172ca20a07e800bc248b803e740364a24715',
                'RustboroCity':'06736e47e512902a29a417da5bbc773d15ae2ef1'}
        layouts=json.loads((ROOT/'data/layouts/layouts.json').read_text())['layouts']
        pack=json.loads((ROOT/'examples/cooperative_signal.json').read_text())
        for stage,name in zip(pack['stages'],hashes):
            doc=json.loads((ROOT/'data/maps'/name/'map.json').read_text())
            layout=next(x for x in layouts if x['id']==doc['layout'])
            raw=(ROOT/layout['blockdata_filepath']).read_bytes()
            self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),hashes[name])
            width,height=layout['width'],layout['height']
            tiles=struct.unpack('<'+'H'*(width*height),raw)
            def clear(x,y):
                if not (0<=x<width and 0<=y<height):return False
                v=tiles[y*width+x]
                return (v>>10)&3==0 and v>>12==3
            points=[tuple(s['at'][2:]) for s in stage['stations']]
            for x,y in points:
                self.assertTrue(clear(x,y),(name,x,y))
                for obj in doc.get('object_events',[]):
                    self.assertFalse(abs(x-obj['x'])<=obj.get('movement_range_x',0) and abs(y-obj['y'])<=obj.get('movement_range_y',0),(name,x,y,obj))
            seen={points[0]};queue=deque(seen)
            while queue:
                x,y=queue.popleft()
                for q in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                    if q not in seen and clear(*q):seen.add(q);queue.append(q)
            self.assertIn(points[1],seen)
            self.assertTrue(any(x in (0,width-1) or y in (0,height-1) for x,y in seen))
