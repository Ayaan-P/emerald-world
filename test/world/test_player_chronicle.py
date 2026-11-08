"""Player chat reads bounded committed history, without publishing private travel."""
import json
import unittest
from unittest.mock import patch
import test_landmark_survey as fixtures
from world.player_chronicle import read


class PlayerChronicleTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.LandmarkSurveyTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.s=self.f.s;self.place=self.s.memory.place(self.f.revision)

    def command(self,text):
        before=self.s.chat_serial;self.f.command(text)
        return [bytes.fromhex(row[3]).decode('ascii') for row in self.f.conn['chat_history'] if row[0]>before]

    def test_real_discovery_requires_explicit_share_and_survives_restart(self):
        other=self.f.connect('Other')
        self.f.command('/explore start');self.f.state(self.f.conn,15,20)
        self.assertNotIn('shared a visit',' '.join(self.command('/explore history')))
        self.f.command('/explore share camp confirm')
        before=self.s.db.total_changes
        lines=self.command('/explore history')
        self.assertIn('shared a visit to camp',' '.join(lines))
        self.assertIn('client-reported',' '.join(lines))
        self.assertNotIn('Scout',' '.join(lines));self.assertEqual(self.s.db.total_changes,before)
        self.assertFalse(any('history through' in bytes.fromhex(r[3]).decode() for r in other['chat_history']))
        self.s.close();self.f.f.server=self.f.f.open();self.s=self.f.s=self.f.f.server
        self.f.conn=self.f.connect('Scout')
        self.assertIn('history first',' '.join(self.command('/explore history older')))
        self.assertIn('shared a visit to camp',' '.join(self.command('/explore history')))

    def test_pagination_freezes_boundary_filters_places_and_refreshes(self):
        sequences=[]
        with self.s.db:
            for i in range(8):
                sequences.append(self.s.memory.append('area_named',dict(place_id=self.place,before='Old',after='Name '+str(i))))
                self.s.memory.append('area_named',dict(place_id='area:unrelated',before='Secret',after='OtherPlace'))
        first=self.command('/explore history');boundary=self.f.conn['place_history_cursor']['through']
        with self.s.db:self.s.memory.append('area_named',dict(place_id=self.place,before='Old',after='Newest'))
        pages=[first]
        while self.f.conn['place_history_cursor']['before'] is not None:
            pages.append(self.command('/explore history older'))
        text=' '.join(line for page in pages for line in page)
        self.assertNotIn('OtherPlace',text);self.assertNotIn('Newest',text)
        for seq in sequences:self.assertEqual(text.count('Record '+str(seq)+':'),1)
        self.assertTrue(all(len(page)<=8 and all(line.isascii() and len(line)<=120 for line in page) for page in pages))
        self.assertEqual(self.f.conn['place_history_cursor']['through'],boundary)
        self.assertIn('No older',' '.join(self.command('/explore history older')))
        self.assertIn('Newest',' '.join(self.command('/explore history')))

    def test_authentication_freshness_and_revision_scope(self):
        self.command('/explore history')
        self.f.conn['state_time']=0
        self.assertIn('acknowledged',' '.join(read(self.s,self.f.conn)))
        self.f.state(self.f.conn,1,1)
        self.f.conn['cave_ack']='0'*64
        self.assertIn('acknowledged',' '.join(read(self.s,self.f.conn)))
        self.f.conn['cave_ack']=self.f.revision
        forged=dict(self.f.conn)
        self.assertIn('acknowledged',' '.join(read(self.s,forged)))
        self.f.conn['place_history_cursor']['revision']='0'*64
        self.assertIn('history first',' '.join(self.command('/explore history older')))

    def test_allowlisted_history_does_not_expose_extra_payload_or_private_tables(self):
        with self.s.db:
            self.s.memory.append('unknown_future_event',dict(place_id=self.place,private_save='DO_NOT_DISCLOSE'))
            self.s.memory.append('area_named',dict(place_id=self.place,before='Old',after='A\n\x1b'+ '\u2603'*400,token='DO_NOT_DISCLOSE'))
            self.s.db.execute("INSERT INTO events(kind,data) VALUES ('private',?)",(json.dumps({'secret':'DO_NOT_DISCLOSE'}),))
        text=' '.join(self.command('/explore history'))
        self.assertNotIn('DO_NOT_DISCLOSE',text);self.assertNotIn('\x1b',text);self.assertTrue(text.isascii())

    def test_real_guild_outcome_is_visible_only_after_publication_opt_in(self):
        self.s.guilds.command('Scout','create Surveyors')
        self.f.command('/guild expedition start here 1');self.f.state(self.f.conn,1,1)
        self.assertNotIn('completed a public',' '.join(self.command('/explore history')))
        self.f.command('/guild chronicle on')
        self.f.command('/guild expedition start here 1');self.f.state(self.f.conn,1,1)
        text=' '.join(self.command('/explore history'))
        self.assertIn('Surveyors completed a public expedition',text)
        self.assertIn('guild XP; travel was client-reported',text)

    def test_authored_character_change_is_not_reported_as_earned_victory(self):
        from test_character_guides import CharacterGuideTests
        fixture=CharacterGuideTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.f.command('/explore history')
        lines=[bytes.fromhex(r[3]).decode('ascii') for r in fixture.f.conn['chat_history']]
        self.assertIn('authored story change',' '.join(lines));self.assertIn('Authored motive',' '.join(lines))
        # Simulate the prior index bug, retaining the original committed places.
        db=fixture.s.db
        rows=db.execute("SELECT seq,data FROM events WHERE kind='world_memory'").fetchall()
        with db:
            for seq,data in rows:
                if json.loads(data).get('event')=='character_changed':
                    db.execute('DELETE FROM world_memory_place_events WHERE seq=?',(seq,))
            db.execute("DELETE FROM world_memory_metadata WHERE key='character_place_index_v1'")
        fixture.s.close();fixture.f.f.server=fixture.f.f.open();fixture.s=fixture.f.s=fixture.f.f.server
        self.assertEqual(rows,fixture.s.db.execute("SELECT seq,data FROM events WHERE kind='world_memory'").fetchall())
        fixture.f.conn=fixture.f.connect('Scout');fixture.f.command('/explore history')
        self.assertIn('authored story change',' '.join(bytes.fromhex(r[3]).decode('ascii') for r in fixture.f.conn['chat_history']))

if __name__=='__main__':unittest.main()
