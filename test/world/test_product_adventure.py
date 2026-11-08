"""Product content uses the real authority and kernel mechanic sandbox."""
from concurrent.futures import Future
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest

import test_world_memory as memory_fixture
from unittest.mock import patch
from world.session import SessionError


class Adventure(unittest.TestCase):
    def setUp(self):
        self.f = memory_fixture.WorldMemoryTests(); self.f.setUp(); self.addCleanup(self.f.tearDown)
        self.s = self.f.server
        self.session = SimpleNamespace(server=self.s, state=SimpleNamespace(name='fixture'))
        from world import product_adventure
        self.workshop = product_adventure.AdventureWorkshop()

    def call(self, action, **payload):
        return self.workshop.action(self.session, [dict(key='fixture')], 'adventure_'+action,
                                    dict(world='fixture', **payload))

    def install(self):
        draft = self.call('preview', adventure='lantern-trail')
        return self.call('apply', token=draft['token'], confirmed=True)

    def test_review_installs_real_sandbox_cast_and_survey_once_then_survives_restart(self):
        before = self.s.memory.history()
        draft = self.call('preview', adventure='lantern-trail')
        self.assertIsNone(self.s.shared_cave)
        self.assertEqual(self.s.memory.history()['events'], before['events'])
        self.assertEqual(draft['label'], 'Lantern Trail Outpost')
        self.assertEqual(len(draft['plan']['characters']), 3)
        with self.assertRaises(SessionError):
            self.call('apply', token=draft['token'], confirmed=False)
        result = self.call('apply', token=draft['token'], confirmed=True)
        self.assertTrue(result['saved'])
        self.assertEqual(len(self.s.objects), 3)
        self.assertTrue(all(o['region_revision']==result['registered_revision'] for o in self.s.objects))
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM survey_routes').fetchone()[0], 1)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM survey_visits').fetchone()[0], 0)
        self.assertNotIn('landmark_discovery_shared', [e['event'] for e in self.s.memory.history()['events']])
        saved = deepcopy(self.s.module_state)
        self.s.close(); self.f.server = self.f.open(); self.s = self.f.server
        self.session.server = self.s
        self.assertEqual(self.s.module_state, saved)
        before = self.s.memory.history()
        second = self.install()
        self.assertTrue(second['already_installed'])
        self.assertEqual(before, self.s.memory.history())
        with self.assertRaises(SessionError): self.call('apply', token=draft['token'], confirmed=True)
    def send(self, conn, line):
        conn['out'].clear()
        self.s._line(conn, line.encode())
        self.assertFalse(conn['closing'], conn['out'])
        return conn['out'].decode()

    def connect(self, name='Scout'):
        token = self.s.create_identity(name)['token']
        conn = dict(id=None, out=bytearray(), closing=False, state=None, seq=0, sock=object())
        self.assertIn('WELCOME', self.send(conn, f'HELLO 1 {name} {token} SOCIALCAVE16CHAR1CHARQUEST1CHARREG1CHARWALK1'))
        self.send(conn, 'CHAT_ENABLE')
        self.send(conn, 'CAVE GET')
        self.send(conn, 'CAVE ACK '+self.s.shared_cave.identity)
        self.state(conn, 1, 1)
        return conn

    def state(self, conn, x, y):
        g, n = self.s.wilds_map
        return self.send(conn, f'STATE {conn["seq"]+1} {g} {n} {x} {y} 4 7 1 '+ 'a'*16+' '+'b'*16)

    def command(self, conn, text):
        conn['chat_credit'] = 4
        return self.send(conn, f'CHAT {conn["seq"]+1} * {text.encode().hex()}')

    def tick(self):
        self.s.tick += 1
        candidate = self.s.candidate
        result = self.s.runtime.run(candidate, self.s._context(), self.s.module_state)
        future = Future(); future.set_result((candidate, result))
        self.s.job = (future, 'tick', None, self.s.interaction_cursor)
        self.s.next_tick = float('inf'); self.s._poll_mechanics()
        self.assertIsNone(self.s.module_error)

    def test_private_survey_is_complete_without_chronicle_or_shared_choice(self):
        result = self.install(); conn = self.connect()
        before = self.s.memory.history()
        self.command(conn, '/explore start')
        sites = json.loads(self.s.db.execute('SELECT sites FROM survey_routes').fetchone()[0])
        for site in sites: self.state(conn, site['x'], site['y'])
        self.tick()
        self.assertIn('Survey complete', ' '.join(self.s.landmark_survey.lines(conn)))
        self.assertEqual(self.s.module_state['world_character_chapters']['Mira']['chapter'], 0)
        self.assertEqual(self.s.memory.history()['events'], before['events'])
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM survey_publications').fetchone()[0], 0)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM guilds').fetchone()[0], 0)
        self.s.close(); self.f.server = self.f.open(); self.s = self.f.server
        self.session.server = self.s
        conn = self.connect()
        self.assertIn('4/4', self.s.landmark_survey.lines(conn)[0])
        self.assertEqual(self.s.shared_cave.identity, result['registered_revision'])

    def test_confirmed_choice_walks_ivo_then_archive_updates_mira_and_restart(self):
        result = self.install(); conn = self.connect()
        self.command(conn, '/explore start')
        self.state(conn, 16, 7)
        initial = deepcopy(self.s.module_state['world_characters'])
        self.command(conn, '/explore share wind_lookout'); self.tick()
        self.assertEqual(self.s.module_state['world_characters'], initial)
        self.command(conn, '/explore share wind_lookout confirm'); self.tick()
        self.assertEqual(self.s.module_state['world_character_chapters']['Mira']['chapter'], 1)
        self.assertIn('Ivo', self.s.module_state.get('world_character_controls', {}))
        walk = self.s.module_state['world_character_controls']['Ivo']['walk']
        self.assertEqual(walk['index'], 0)
        self.assertIn('CHARACTER_WALK Ivo', self.s._snapshot(conn))
        # Ready player occupancy delays the short walk without losing it.
        self.state(conn, 17, 8); self.tick()
        self.assertEqual(self.s.module_state['world_character_controls']['Ivo']['walk']['index'], 0)
        self.state(conn, 16, 7); self.tick()
        self.assertEqual(self.s.module_state['world_character_controls']['Ivo']['walk']['index'], 1)
        self.s.close(); self.f.server = self.f.open(); self.s = self.f.server
        self.session.server = self.s
        self.assertEqual(self.s.module_state['world_character_controls']['Ivo']['walk']['index'], 1)
        conn = self.connect(); self.tick(); self.tick()
        self.state(conn, 17, 8)
        version = self.s.module_state['world_characters']['Ivo']['version']
        reply = self.send(conn, f'CHARACTER_CHALLENGE_REGION {conn["seq"]+1} Ivo {version} {result["registered_revision"]}')
        self.assertIn('Ivo 2 1 278 5', reply)
        pending = conn['character_pending']
        self.send(conn, f'CHARACTER_RESULT {pending["seq"]} Ivo 2 0')
        self.state(conn, 27, 19)
        self.command(conn, '/explore share field_archive confirm'); self.tick()
        self.assertEqual(self.s.module_state['world_character_chapters']['Mira']['chapter'], 3)
        self.assertIn('watch notes', next(o['text'] for o in self.s.objects if o['id']=='Mira'))
        public = [e for e in self.s.memory.history()['events'] if e['event']=='landmark_discovery_shared']
        self.assertEqual(len(public), 2)
        self.assertNotIn('Scout', json.dumps(public))
    def test_entry_guide_explains_actual_native_menu_and_starter_requirements(self):
        result = self.call('read')
        self.assertIn('Explore generated area', ' '.join(result['adventures'][0]['guide']))
        self.assertIn('My objectives', ' '.join(result['adventures'][0]['guide']))
        self.assertNotIn('/explore start', ' '.join(result['adventures'][0]['guide']))
        draft = self.call('preview', adventure='lantern-trail')
        self.assertIn('My objectives', draft['plan']['characters'][0]['chapters'][0]['object']['text'])
        self.assertIn('outdoors', ' '.join(result['prerequisites']))
        self.assertIn('on foot', ' '.join(result['prerequisites']))
        self.assertIn('conscious', ' '.join(result['prerequisites']))

    def test_review_includes_exact_optional_walk_and_rematch(self):
        draft = self.call('preview', adventure='lantern-trail')
        motion = draft['plan']['walk']
        self.assertEqual(motion['character'], 'Ivo')
        self.assertEqual(motion['path'], [[17,7], [17,8], [18,8]])
        self.assertEqual(motion['team'], [dict(species=278, level=5)])
        self.assertEqual(motion['landmarks'], ['wind_lookout', 'reed_pool'])

    def test_cast_uses_three_distinct_beginner_species(self):
        draft = self.call('preview', adventure='lantern-trail')
        self.assertEqual([c['chapters'][0]['team'] for c in draft['plan']['characters']],
                         [[dict(species=276, level=4)], [dict(species=278, level=4)], [dict(species=263, level=3)]])

    def test_incomplete_install_is_not_reported_as_idempotent_success(self):
        self.install()
        self.s.db.execute('DELETE FROM survey_routes'); self.s.db.commit()
        with self.assertRaisesRegex(SessionError, 'incomplete|changed'):
            self.call('preview', adventure='lantern-trail')

    def test_stale_occupied_and_sandbox_race_refuse_without_writes(self):
        draft = self.call('preview', adventure='lantern-trail')
        self.s.module_state['unrelated'] = 'changed without public sequence'
        with self.assertRaisesRegex(SessionError, 'changed'):
            self.call('apply', token=draft['token'], confirmed=True)
        draft = self.call('preview', adventure='lantern-trail')
        self.s.peers['fixture'] = dict(closing=False)
        with self.assertRaisesRegex(SessionError, 'occupied'):
            self.call('apply', token=draft['token'], confirmed=True)
        self.s.peers.clear()
        stage = self.s.runtime.stage
        def racing_stage(*args):
            result = stage(*args)
            self.s.module_state['raced'] = True
            return result
        with patch.object(self.s.runtime, 'stage', side_effect=racing_stage):
            with self.assertRaisesRegex(SessionError, 'changed'):
                self.call('apply', token=draft['token'], confirmed=True)
        self.assertIsNone(self.s.shared_cave)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM survey_routes').fetchone()[0], 0)
        self.assertIsNone(self.s.candidate)

    def test_failed_atomic_commit_leaves_no_map_survey_place_or_residents(self):
        draft = self.call('preview', adventure='lantern-trail')
        before = self.s.memory.history()
        self.s.db.execute("CREATE TRIGGER adventure_disk_failure BEFORE INSERT ON module BEGIN SELECT RAISE(ABORT,'fixture disk full'); END")
        with self.assertRaises(SessionError):
            self.call('apply', token=draft['token'], confirmed=True)
        self.assertIsNone(self.s.shared_cave)
        self.assertIsNone(self.s.candidate)
        self.assertEqual(self.s.module_state, {})
        self.assertEqual(self.s.memory.history(), before)
        for table in ('world_places', 'survey_routes', 'generated_area_archive', 'generated_cave', 'module'):
            self.assertEqual(self.s.db.execute('SELECT count(*) FROM '+table).fetchone()[0], 0, table)
        with self.assertRaises(SessionError):
            self.call('apply', token=draft['token'], confirmed=True)
        self.s.close(); self.f.server = self.f.open(); self.s = self.f.server
        self.assertIsNone(self.s.shared_cave)
        self.assertEqual(self.s.module_state, {})

    def test_existing_archived_terrain_and_character_are_preserved(self):
        BLOB = b'EWGMAP0A' + ''.join(['#'*127] + ['#'+'.'*125+'#']*125 + ['#'*127]).encode()
        from world.character_chapters import compile_plan
        old_revision = self.s._replace_cave(BLOB, label='Existing untouched home')
        plan = dict(id='existing_keeper', name='Existing Keeper', role='Guard the old home', origin_evidence=[], chapters=[dict(
            id='home', when=None, goals=['Remain at the old home'], team=[dict(species=277, level=3)], status='active',
            object=dict(id='existing_keeper', group=self.s.wilds_map[0], num=self.s.wilds_map[1], x=8, y=8, gfx=7,
                        text='This is still my home.', region_revision=old_revision), reason='Existing authored character')])
        source = compile_plan(plan, self.s.inspect())
        candidate = self.s.runtime.from_source(source)
        result = self.s.runtime.run(candidate, self.s._context(), {})
        future = Future(); future.set_result((candidate, result))
        self.s.job = (future, 'tick', None, 0); self.s.next_tick = float('inf'); self.s._poll_mechanics()
        self.assertIsNone(self.s.module_error)
        old_character = deepcopy(self.s.module_state['world_characters']['existing_keeper'])
        old_object = deepcopy(self.s.objects[0])
        self.install(); self.tick()
        self.assertEqual(self.s.module_state['world_characters']['existing_keeper'], old_character)
        self.assertIn(old_object, self.s.objects)
        self.assertEqual(self.s.db.execute('SELECT template,label FROM generated_area_archive WHERE identity=?', (old_revision,)).fetchone(), (BLOB, 'Existing untouched home'))
        self.s.activate_generated_area(old_revision)
        self.assertEqual(self.s.shared_cave.identity, old_revision)
        self.assertIn(old_object, self.s.objects)
        result = self.install()
        self.assertTrue(result['already_installed'])
        self.assertEqual(self.s.shared_cave.identity, old_revision)  # repeat import never silently switches maps

    def test_archive_shared_first_does_not_trap_the_public_project(self):
        self.install(); conn = self.connect()
        self.command(conn, '/explore start')
        self.state(conn, 27, 19)
        self.command(conn, '/explore share field_archive confirm'); self.tick()
        self.assertEqual(self.s.module_state['world_character_chapters']['Mira']['chapter'], 5)
        self.state(conn, 16, 7)
        self.command(conn, '/explore share wind_lookout confirm'); self.tick()
        self.assertEqual(self.s.module_state['world_character_chapters']['Mira']['chapter'], 6)
        self.assertIn('watch notes', next(o['text'] for o in self.s.objects if o['id']=='Mira'))

    def test_quiet_branch_wins_even_if_lookout_is_shared_later(self):
        self.install(); conn = self.connect()
        self.command(conn, '/explore start')
        for name, x, y in [('reed_pool',11,19), ('wind_lookout',16,7), ('field_archive',27,19)]:
            self.state(conn, x, y); self.command(conn, '/explore share '+name+' confirm'); self.tick()
        self.assertEqual(self.s.module_state['world_character_chapters']['Mira']['chapter'], 4)
        self.assertIn('Quiet pool notes', next(o['text'] for o in self.s.objects if o['id']=='Mira'))

    def test_resident_guidance_uses_private_survey_without_public_history(self):
        self.install(); conn = self.connect()
        self.command(conn, '/explore start')
        self.state(conn, 3, 3)  # face east toward Mira at the entry
        before = self.s.memory.history()['events']
        self.command(conn, '/explore guide Mira')
        note = self.s.db.execute('SELECT revision,landmark,guide FROM survey_guidance WHERE trainer=?', ('Scout',)).fetchone()
        self.assertEqual(note, (self.s.shared_cave.identity, 'lantern_outpost', 'Mira'))
        self.command(conn, '/explore directions')
        self.assertEqual(self.s.memory.history()['events'], before)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM survey_publications').fetchone()[0], 0)

    def test_mutating_preview_response_cannot_change_reviewed_builtin(self):
        draft = self.call('preview', adventure='lantern-trail')
        draft['plan']['characters'].clear()
        draft['plan']['walk']['team'][0]['level'] = 100
        draft['report']['revision'] = '0'*64
        result = self.call('apply', token=draft['token'], confirmed=True)
        self.assertEqual(len(self.s.objects), 3)
        self.assertNotEqual(result['registered_revision'], '0'*64)
        self.assertEqual(self.s.module_state['world_characters']['Ivo']['team'], [dict(species=278, level=4)])

    def test_local_adapter_returns_selected_world_and_rejects_foreign_fields(self):
        self.assertEqual(self.call('read')['world'], 'fixture')
        with self.assertRaises(SessionError):
            self.workshop.action(self.session, [dict(key='fixture')], 'adventure_read', dict(world='another'))
        with self.assertRaises(SessionError):
            self.workshop.action(self.session, [dict(key='fixture')], 'adventure_preview', dict(world='fixture', adventure='lantern-trail', source='bad'))

    def test_authority_helpers_work_under_reentrant_owner_locks(self):
        from world.product_adventure import preview_adventure, apply_adventure
        with self.s.lock:
            draft = preview_adventure(self.s)
            result = apply_adventure(self.s, draft['token'], True)
        self.assertTrue(result['saved'])

    def test_authority_helpers_are_review_bound_and_accept_only_named_artifact(self):
        from world.product_adventure import read_adventures, preview_adventure, apply_adventure
        self.assertEqual(read_adventures(self.s)['adventures'][0]['id'], 'lantern-trail')
        with self.assertRaises(SessionError): preview_adventure(self.s, 'arbitrary-code')
        draft = preview_adventure(self.s)
        with self.assertRaises(SessionError): apply_adventure(self.s, draft['token'])
        result = apply_adventure(self.s, draft['token'], True)
        self.assertTrue(result['saved'])
        self.assertTrue(read_adventures(self.s)['adventures'][0]['installed'])


if __name__ == '__main__': unittest.main()
