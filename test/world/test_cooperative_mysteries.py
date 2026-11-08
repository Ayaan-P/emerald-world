"""Paired field clues, persisted completion, and consequent place stories."""
import copy
import json
import sqlite3
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
        self.chat(self.a,'/mystery start signal')
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
        self.assertFalse(self.s.opportunities.offers('Alice','RustboroCity','signal_after'))
        first=self.solve(0)
        self.assertTrue(any('Stage 2' in line for line in first))
        self.assertFalse(self.a['chat_history'])
        result=self.solve(1)
        self.assertIn(self.pack['ending'],result)
        for name in ('Alice','Bob'):
            self.assertTrue(self.s.mysteries.completed(name,'signal'))
            self.assertTrue(self.s.opportunities.offers(name,'RustboroCity','signal_after'))
        self.assertFalse(self.s.opportunities.offers('Cara','RustboroCity','signal_after'))
        lines=self.chat(self.a,'/story signal_after')
        choice=next(x for x in lines if '/story pick signal_after decision restore ' in x)
        self.chat(self.a,choice)
        self.assertFalse(late['chat_history'])
        scenes=self.s.opportunities.offers('Cara','RustboroCity','signal_after')[0]['scenes']
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
        self.assertTrue(self.s.mysteries.completed('Bob','signal'))
        self.assertTrue(self.s.opportunities.offers('Alice','RustboroCity','signal_after'))

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
        self.assertFalse(self.s.mysteries.completed('Alice','signal'))
        self.assertTrue(any('ended' in x for x in self.chat(self.b,'/mystery status')))
