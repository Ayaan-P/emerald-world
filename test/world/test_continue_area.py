"""Real geometry commits from history-informed inert proposals, no model calls."""
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from test_shared_generated_cave import MemoryAuthority
import test_shared_terrain_world
from world.continue_area import continue_area


class ContinueAreaTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.server=self.open()
        self.identity=self.server._replace_cave(test_shared_terrain_world.SharedTerrainWorld().blob(),label='Cedar Refuge')
        self.place=self.server.memory.place(self.identity)
        self.server.set_shared_geometry(self.identity,[dict(x=2,y=2,terrain='tall_grass')])
        self.evidence=self.server.memory.history()['events'][-1]['seq']

    def open(self):
        return MemoryAuthority(self.root/'socket',self.root/'world',persist_generated_cave=True,archive_generated_areas=True)

    def tearDown(self):
        self.server.close()
        self.tmp.cleanup()

    def transport(self,_socket,request,**kwargs):
        from admin_transport import admin_request
        return admin_request(self.server, request)

    def author(self,prompt):
        self.assertIn(str(self.evidence),prompt)
        self.assertIn('tall_grass',prompt)
        return dict(tiles=[dict(x=2,y=2,terrain='grass')],history_evidence=[self.evidence])

    def run_builder(self,author=None,apply=True):
        with patch('world.continue_area.admin_request',side_effect=self.transport):
            return continue_area('admin','Restore the refuge clearing using its recorded terrain history',author=author or self.author,apply=apply)

    def test_transport_refuses_chunks_after_authority_closes_connection(self):
        original = self.server._admin_line
        def close_after_response(conn, raw):
            original(conn, raw)
            conn['closing'] = True
        with patch.object(self.server, '_admin_line', side_effect=close_after_response):
            with self.assertRaises(ConnectionResetError):
                self.transport('', dict(command='inspect'))

    def test_real_commit_retains_place_story_template_and_restart_history(self):
        before=self.server.shared_cave.identity
        report=self.run_builder()
        self.assertTrue(report['applied'])
        self.assertTrue(report['commit']['changed'])
        event=self.server.memory.history()['events'][-1]
        self.assertEqual(event['history_evidence'],[self.evidence])
        self.assertEqual(event['tiles'],[dict(x=2,y=2,before='tall_grass',after='grass')])
        self.assertEqual(event['place_id'],self.place)
        self.server.close()
        self.server=self.open()
        self.assertEqual(self.server.shared_cave.identity,before)
        self.assertEqual(self.server.memory.history()['events'][-1],event)
        self.assertEqual(self.server.inspect_shared_terrain(before)['tiles'],[dict(x=2,y=2,terrain='grass')])

    def test_existing_multiplayer_reset_delivers_the_committed_revision(self):
        peers=[]
        for name in ('Alice','Bob'):
            identity=self.server.create_identity(name)
            peer=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
            self.server._line(peer,('HELLO 1 %s %s SOCIALTRAVELCHATRALLYCAVE9T' % (identity['id'],identity['token'])).encode())
            self.server._line(peer,b'CAVE GET')
            self.server._line(peer,('CAVE ACK '+self.identity).encode())
            peer['out'].clear()
            peers.append(peer)
        result=self.run_builder()
        self.assertEqual(result['commit']['reset_queued'],2)
        for peer in peers:
            self.assertIn(b'CAVE RESET',peer['out'])
            self.assertIsNone(peer['cave_ack'])
            peer['out'].clear()
            with patch('world.server.time.monotonic',return_value=peer['cave_next']+1):
                self.server._line(peer,b'CAVE GET')
            self.assertIn(('CAVE TERRAIN %s %d ' % (self.identity,result['commit']['revision'])).encode(),peer['out'])

    def test_preview_is_not_a_commit_and_no_private_state_is_passed(self):
        self.server.create_identity('PrivateTrainer')
        self.server.peers['PrivateTrainer']=dict(closing=False,cave_ack=self.identity,cave_capable=True,state=[0,9,1,1,1,7,1])
        before=self.server.memory.history()
        def author(prompt):
            self.assertNotIn('PrivateTrainer',prompt)
            return self.author(prompt)
        self.assertFalse(self.run_builder(author,apply=False)['applied'])
        self.assertEqual(self.server.memory.history(),before)
        self.server.peers.clear()

    def test_concurrent_edit_and_occupied_area_are_rejected(self):
        def raced(prompt):
            self.server.set_shared_geometry(self.identity,[dict(x=3,y=3,terrain='tall_grass')])
            return self.author(prompt)
        with self.assertRaisesRegex(ValueError,'changed'):
            self.run_builder(raced)
        self.assertNotIn('history_evidence',self.server.memory.history()['events'][-1])
        self.server.create_identity('Visitor')
        self.server.peers['Visitor']=dict(closing=False,cave_capable=True,in_generated_cave=True,state=[0,9,1,1,1,7,1])
        with self.assertRaisesRegex(ValueError,'leave'):
            self.run_builder()
        self.server.peers.clear()

    def test_invalid_proposals_and_history_failure_leave_world_unchanged(self):
        before=self.server.memory.history()
        with self.assertRaisesRegex(ValueError,'unavailable history'):
            self.run_builder(lambda _:dict(tiles=[dict(x=2,y=2,terrain='grass')],history_evidence=[999999]))
        with self.assertRaisesRegex(ValueError,'protected'):
            self.run_builder(lambda _:dict(tiles=[dict(x=1,y=1,terrain='water')],history_evidence=[]))
        with patch.object(self.server.memory,'append',side_effect=sqlite3.OperationalError('full')):
            with self.assertRaisesRegex(ValueError,'persisted'):
                self.run_builder()
        self.assertEqual(self.server.memory.history(),before)
        self.assertEqual(self.server.inspect_shared_terrain(self.identity)['tiles'],[dict(x=2,y=2,terrain='tall_grass')])


if __name__=='__main__':
    unittest.main()
