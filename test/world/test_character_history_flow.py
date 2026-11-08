"""Trusted example behavior through the real authority; not a sandbox/game pass."""
from concurrent.futures import Future
from copy import deepcopy
import hashlib
import inspect
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from test_shared_generated_cave import MemoryAuthority, BLOB
from world import gm
from world.characters import history_feed, validate_history_cursor
from world.mechanics import Candidate


def researcher(context, state):
    """One test author's script; the runtime contract is not tied to this story."""
    state = deepcopy(state)
    cast = state.setdefault('world_characters', {})
    original_cast = deepcopy(cast)
    story = state.setdefault('researcher_story', {'phase': 'uncreated', 'interaction_seq': 0})
    feed = context.get('character_history', {'events': [], 'through': state.get('character_history_cursor', 0)})
    for event in feed['events']:
        if story['phase'] == 'uncreated' and event['event'] == 'area_activated' and event.get('label') == 'Cedar expedition':
            cast['may'] = dict(version=1, name='May', role='Travelling field researcher',
                goals=['Explore Cedar'], relationships={}, team=[dict(species=277, level=12)],
                status='active', object_id='may', evidence=[event['seq']],
                reason='An authored researcher arrives after Cedar opens')
            story.update(phase='arrived', place=event['place_id'])
        elif (story['phase'] == 'arrived' and event['event'] == 'area_named'
              and event.get('place_id') == story['place']):
            cast['may'].update(version=cast['may']['version']+1, status='away',
                evidence=[event['seq']], reason='The authored researcher departs to survey the changed expedition site')
            story['phase'] = 'away'
        elif (story['phase'] == 'away' and event['event'] == 'area_named'
              and event.get('place_id') == story['place']):
            cast['may'].update(version=cast['may']['version']+1, status='active',
                goals=['Share the new Cedar field notes'], team=[dict(species=278, level=18)],
                evidence=[event['seq']], reason='Authored team growth follows the changed expedition site')
            story['phase'] = 'returned'
    state['character_history_cursor'] = feed['through']
    for event in context.get('interactions', []):
        if event['seq'] <= story['interaction_seq']:
            continue
        story['interaction_seq'] = event['seq']
        if event.get('object') == 'may':
            story['met'] = True
    for identity, character in cast.items():
        old = original_cast.get(identity)
        changed = old is None or {k:v for k,v in old.items() if k!='version'} != {k:v for k,v in character.items() if k!='version'}
        character['version'] = (old['version']+1 if old else 1) if changed else old['version']
    objects = []
    if cast.get('may', {}).get('status') == 'active':
        objects = [dict(id='may', group=0, num=9, x=9, y=8, gfx=8,
            text='Our journey continues.' if story['phase']=='returned' else 'Let us explore Cedar.')]
    return dict(state=state, tiles=[], objects=objects)


class HistoryCharacterFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.server = self.open()
        self.source = 'from copy import deepcopy\n' + inspect.getsource(researcher).replace('def researcher(', 'def update(', 1)
        self.candidate = Candidate(self.source, hashlib.sha256(self.source.encode()).hexdigest())

    def open(self):
        return MemoryAuthority(self.root/'socket', self.root/'world',
            persist_generated_cave=True, archive_generated_areas=True)

    def tearDown(self):
        self.server.close()
        self.temp.cleanup()

    def tick(self):
        context = self.server._context()
        result = researcher(context, self.server.module_state)
        future = Future()
        future.set_result((self.candidate, result))
        cursor = context['interactions'][-1]['seq'] if context['interactions'] else self.server.interaction_cursor
        self.server.job = (future, 'tick', None, cursor)
        self.server.next_tick = float('inf')
        self.server._poll_mechanics()
        self.assertIsNone(self.server.module_error)

    def peer(self):
        identity = self.server.create_identity('Alice')
        conn = dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
        self.server._line(conn, ('HELLO 1 %s %s SOCIALCHAR1' % (identity['id'],identity['token'])).encode())
        self.assertIn(b'WELCOME',conn['out'])
        conn['out'].clear()
        conn.update(state=[0,9,8,8,4,7,1],state_time=time.monotonic())
        return conn

    def send(self, conn, line):
        self.server._line(conn,line.encode())
        result=conn['out'].decode()
        conn['out'].clear()
        return result

    def test_create_meet_battle_depart_restart_and_history_driven_return(self):
        area = self.server._replace_cave(BLOB,label='Cedar expedition')
        seen=[]
        def author(prompt):
            evidence=json.loads(prompt.split('Request and snapshot follow:\n',1)[1])['inspection']
            self.assertEqual(evidence['character_contract']['state_key'],'world_characters')
            self.assertIn('Cedar expedition',json.dumps(evidence['recalled_history']))
            seen.append(evidence)
            return dict(source=self.source,tests='def test_contract():\n    assert callable(update)\n')
        def transport(socket,request,timeout):
            if request['command']=='inspect':return self.server.inspect()
            if request['command']=='world_recall':
                conn=dict(id=None,out=bytearray(),closing=False,sock=object())
                self.server._admin_line(conn,json.dumps(request).encode())
                return json.loads(conn['out'])
            return dict(ok=False,error='Fixture does not claim sandbox deployment')
        with patch('world.gm.admin_request',side_effect=transport):
            report=gm.author_and_deploy(self.root/'author',self.root/'socket',
                'Create a recurring field researcher for Cedar expedition',author)
        self.assertFalse(report['ok'])
        self.assertEqual(Path(report['source_path']).read_text(),self.source)
        self.assertEqual(len(seen),1)
        # Trusted repository fixture executes normally, then enters real atomic
        # authority commit. Generated-code sandbox execution remains untested.
        self.tick()
        self.assertEqual(self.server.objects[0]['id'],'may')
        conn=self.peer()
        self.send(conn,'INTERACT 1 may')
        self.tick()
        self.assertTrue(self.server.module_state['researcher_story']['met'])
        self.assertIn('CHARACTER_BATTLE_V1 2 may 1 1 277 12',self.send(conn,'CHARACTER_CHALLENGE 2 may 1'))
        self.assertIn('CHARACTER_RESULT_ACK',self.send(conn,'CHARACTER_RESULT 2 may 1 1'))
        self.tick()
        self.assertEqual(self.server.module_state['world_characters']['may']['version'],1)
        # A real public place milestone drives departure, not a private win report
        # or the initial talk event that precedes the native consent prompt.
        self.server._replace_cave(BLOB,label='Cedar survey underway')
        self.tick()
        self.assertEqual(self.server.objects,[])
        self.assertEqual(self.server.module_state['world_characters']['may']['status'],'away')
        saved_cursor=self.server.module_state['character_history_cursor']
        self.server.close();self.server=self.open()
        self.assertEqual(self.server.module_state['character_history_cursor'],saved_cursor)
        self.server._replace_cave(BLOB,label='Cedar field station')
        self.tick()
        character=self.server.module_state['world_characters']['may']
        self.assertEqual((character['version'],character['status']),(3,'active'))
        self.assertEqual(character['team'],[dict(species=278,level=18)])
        self.assertEqual(self.server.objects[0]['text'],'Our journey continues.')
        conn=self.peer()
        self.assertIn('CHARACTER_BATTLE_V1 1 may 3 1 278 18',self.send(conn,'CHARACTER_CHALLENGE 1 may 3'))
        self.tick();self.tick()
        self.assertEqual(self.server.module_state['world_characters']['may']['version'],3)
        self.assertEqual(self.server.shared_cave.identity,area)

    def test_ordered_feed_does_not_lose_history_beyond_recent_tail(self):
        self.server._replace_cave(BLOB,label='Cedar expedition')
        for number in range(40):
            self.server._replace_cave(BLOB,label='Station '+str(number))
        self.assertNotIn('Cedar expedition',json.dumps(self.server.memory.context(self.server)))
        self.assertEqual(history_feed(self.server.db,{})['events'][0]['label'],'Cedar expedition')
        feed=history_feed(self.server.db,{})
        self.assertTrue(feed['has_more'])
        self.assertEqual(len(feed['events']),16)
        with self.assertRaises(ValueError):
            validate_history_cursor({}, {'character_history_cursor':self.server.revision},self.server.db)
        self.tick()
        self.assertEqual(self.server.module_state['world_characters']['may']['status'],'active')
        self.assertEqual(self.server.module_state['world_characters']['may']['version'],1)
        prior=self.server.module_state['character_history_cursor']
        self.tick()
        self.assertGreater(self.server.module_state['character_history_cursor'],prior)
        with self.assertRaises(ValueError):
            validate_history_cursor(self.server.module_state,{'character_history_cursor':0},self.server.db)

    def test_feed_excludes_private_reports_and_bounds_large_public_events(self):
        self.server._replace_cave(BLOB,label='Cedar expedition')
        with self.server.db:
            self.server._event('character_battle_report', {'player':'private-name','outcome':1})
            self.server.memory.append('mechanic_changed', dict(before={'objects':[],'tiles':[]},
                after={'objects':[],'tiles':[]}, places=[], note='x'*100000))
        feed=history_feed(self.server.db,{})
        self.assertNotIn('private-name',json.dumps(feed))
        self.assertNotIn('character_battle_report',json.dumps(feed))
        self.assertLess(len(json.dumps(feed)),4096)
        self.assertEqual(feed['events'][-1]['event'],'mechanic_changed')
        self.assertIn('full_event_in_world_history',feed['events'][-1]['details'])



if __name__=='__main__':unittest.main()
