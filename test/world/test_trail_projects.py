"""Public exploration opens a shorter physical route without erasing the old place."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
from world.route_artifacts import load
from world.shared_cave import SharedCave
from world.trail_projects import main,_recipe,compile_trail
from test_route_landscape import plan
import test_landmark_survey as fixtures


class TrailProjects(unittest.TestCase):
    wildlife=False
    def setUp(self):
        p=plan();p['loops']=0
        if self.wildlife:p['encounters']=dict(rate=12,wildlife=[dict(species='ZUBAT',level=10)]*12)
        self.original_plan=p
        original=fixtures.LandmarkSurveyTests.send
        protocol=patch.object(fixtures.LandmarkSurveyTests,'send',new=lambda f,c,line:original(f,c,line.replace('CAVE16','CAVE17') if self.wildlife else line))
        protocol.start();self.addCleanup(protocol.stop)
        self.f=fixtures.LandmarkSurveyTests()
        with patch.object(fixtures,'plan',return_value=p):self.f.setUp()
        self.addCleanup(self.f.doCleanups);self.s=self.f.s
        self.old=self.f.revision;self.blob=self.s.db.execute('SELECT template FROM generated_cave').fetchone()[0]

    def request(self,apply=True):
        context=self.s.memory.context(self.s)
        return dict(command='construct_trail' if apply else 'preview_trail',sites=['camp','ruins'],label='Surveyors Causeway',
                    previous_revision=self.old,expected_world_id=context['world_id'],expected_sequence=context['through'])

    def reports(self):
        self.f.command('/explore start')
        self.f.state(self.f.conn,14,20);self.f.command('/explore share camp confirm')
        self.f.state(self.f.conn,95,35);self.f.command('/explore share ruins confirm')

    def leave(self):self.f.send(self.f.conn,f'STATE {self.f.conn["seq"]+1} 0 9 8 8 4 7 1 '+'a'*16+' '+'b'*16)

    def test_actual_shared_discoveries_open_shorter_persistent_walkable_route(self):
        self.reports();before=self.s.db.total_changes
        preview=self.f.f.admin(self.request(False));self.assertTrue(preview['ok'],preview)
        self.assertEqual(self.s.db.total_changes,before);self.assertEqual(self.s.shared_cave.identity,self.old)
        self.assertGreaterEqual(preview['construction']['saved_steps'],4)
        self.assertFalse(self.f.f.admin(self.request())['ok']) # players must leave first
        self.leave();result=self.f.f.admin(self.request());self.assertTrue(result['ok'],result)
        new=result['revision'];cave=self.s.shared_cave
        self.assertEqual(cave.identity,new);self.assertEqual(self.s.memory.place(new),self.s.memory.place(self.old))
        self.assertTrue(all(cave.walkable(*point) for point in result['construction']['path']))
        self.assertEqual(result['construction']['saved_steps'],136)
        self.assertEqual(result['history_evidence'],preview['history_evidence'])
        for y,row in enumerate(SharedCave(self.blob)._rows):
            for x,value in enumerate(row):
                if value==ord('.'):self.assertTrue(cave.walkable(x,y))
        for x,y,w,h in self.original_plan['reservations']:
            for xx in range(x,x+w):
                for yy in range(y,y+h):self.assertEqual(cave._rows[yy][xx],ord('#'))
        if self.wildlife:self.assertEqual(cave.wildlife,SharedCave(self.blob).wildlife)
        artifact=load(self.s,new);self.assertEqual(artifact['report']['new'],[])
        self.assertEqual(set(artifact['report']['retained']),{'camp','orchard','ruins','lookout'})
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM survey_visits WHERE revision=?',(new,)).fetchone()[0],0)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM survey_inherited WHERE revision=?',(new,)).fetchone()[0],2)
        event=[e for e in self.s.memory.history()['events'] if e['event']=='area_activated'][-1]
        self.assertEqual(event['history_evidence'],result['history_evidence'])
        trail=[e for e in self.s.memory.history()['events'] if e['event']=='trail_opened'][-1]
        self.assertEqual((trail['old_steps'],trail['new_steps']),(249,113))
        self.assertEqual(trail['history_evidence'],result['history_evidence'])
        from world.characters import history_feed
        feed=history_feed(self.s.db,{'character_history_cursor':trail['seq']-1})
        self.assertEqual(feed['events'][0]['event'],'trail_opened')
        self.assertEqual((feed['events'][0]['start'],feed['events'][0]['end']),('camp','ruins'))
        self.s.close();self.f.f.server=self.f.f.open();self.s=self.f.s=self.f.f.server;self.f.revision=new;self.f.conn=self.f.connect('Scout')
        self.assertEqual(load(self.s,new),artifact);self.assertEqual(self.s.shared_cave.identity,new)
        self.assertIn('2/4',' '.join(self.s.landmark_survey.lines(self.f.conn)))
        self.f.command('/explore history')
        self.assertTrue(any('Trail opened: camp to ruins' in bytes.fromhex(r[3]).decode() for r in self.f.conn['chat_history']))
        # The authenticated presence path accepts every cell of the new shortcut.
        for point in result['construction']['path']:self.f.state(self.f.conn,*point)
        self.assertFalse(self.f.f.admin(self.request())['ok']) # old-revision retry cannot repeat construction

    def test_private_visits_stale_requests_and_unregistered_sites_cannot_build(self):
        self.f.command('/explore start');self.f.state(self.f.conn,15,20);self.f.state(self.f.conn,95,35)
        self.assertFalse(self.f.f.admin(self.request(False))['ok'])
        self.reports();stale=self.request();self.leave()
        with self.s.db:self.s.memory.append('area_named',dict(place_id=self.s.memory.place(self.old),before='Old',after='Updated'))
        self.assertFalse(self.f.f.admin(stale)['ok'])
        invalid=self.request();invalid['sites']=['camp','unknown']
        self.assertFalse(self.f.f.admin(invalid)['ok'])
        self.assertEqual(self.s.shared_cave.identity,self.old)

    def test_failed_atomic_artifact_write_preserves_geometry_surveys_and_history(self):
        self.reports();self.leave();before=self.s.memory.history();sessions=self.s.db.execute('SELECT * FROM survey_sessions').fetchall()
        self.s.db.execute("CREATE TRIGGER refuse_trail BEFORE INSERT ON route_artifacts BEGIN SELECT RAISE(ABORT,'fixture'); END")
        result=self.f.f.admin(self.request());self.assertFalse(result['ok'])
        self.assertEqual(self.s.shared_cave.identity,self.old);self.assertEqual(self.s.memory.history(),before)
        self.assertEqual(self.s.db.execute('SELECT * FROM survey_sessions').fetchall(),sessions)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM generated_area_archive').fetchone()[0],1)
        self.s.db.execute('DROP TRIGGER refuse_trail')
        self.s.db.execute("CREATE TRIGGER refuse_trail_history BEFORE INSERT ON events WHEN instr(NEW.data,'trail_opened')>0 BEGIN SELECT RAISE(ABORT,'fixture'); END")
        result=self.f.f.admin(self.request());self.assertFalse(result['ok'])
        self.assertEqual(self.s.shared_cave.identity,self.old);self.assertEqual(self.s.memory.history(),before)
        self.assertEqual(self.s.db.execute('SELECT * FROM survey_sessions').fetchall(),sessions)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM generated_area_archive').fetchone()[0],1)

    def test_owner_cli_preview_and_apply_use_real_authority(self):
        self.reports()
        def transport(_socket,request,**kwargs):return self.f.f.admin(request)
        args=['camp','ruins','--label','Surveyors Causeway','--admin-socket','admin']
        with patch('world.client.admin_request',side_effect=transport):self.assertEqual(main(args),0)
        self.assertEqual(self.s.shared_cave.identity,self.old);self.leave()
        with patch('world.client.admin_request',side_effect=transport):self.assertEqual(main(args+['--apply']),0)
        self.assertNotEqual(self.s.shared_cave.identity,self.old)

    def test_existing_resident_and_behavior_rebind_to_the_new_route(self):
        from test_character_guides import CharacterGuideTests
        guide=CharacterGuideTests()
        with patch.object(fixtures,'plan',return_value=self.original_plan):guide.setUp()
        self.addCleanup(guide.doCleanups)
        self.f=guide.f;self.s=guide.s;self.old=self.f.revision
        self.reports();self.leave();before=deepcopy(self.s.module_state['world_characters'])
        result=self.f.f.admin(self.request());self.assertTrue(result['ok'],result)
        self.assertEqual(result['rebound_characters'],['path_guide'])
        self.assertEqual(self.s.module_state['world_characters'],before)
        self.assertEqual(self.s.objects[0]['region_revision'],result['revision'])
        self.assertEqual((self.s.objects[0]['x'],self.s.objects[0]['y']),(15,20))

    def test_mandatory_journey_passages_are_not_silently_bypassed(self):
        from test_route_journeys import plan as journey
        from world.route_artifacts import create
        self.leave();blob,artifact=create(journey())
        revision=self.s._replace_cave(blob,route_artifact=artifact)
        with self.assertRaisesRegex(ValueError,'mandatory-passage'):_recipe(self.s,revision,['camp','east'])

    def test_tampered_recipe_and_no_improvement_are_refused(self):
        recipe=_recipe(self.s,self.old,['camp','ruins'])
        blob,report=compile_trail(self.blob,recipe)
        self.assertGreater(report['added_walkable_tiles'],0)
        with self.assertRaisesRegex(ValueError,'four walking steps'):compile_trail(blob,recipe)
        for key,value in [('start',[True,20]),('protected',[[1000,2]]),('sites',['camp'])]:
            bad=deepcopy(recipe);bad[key]=value
            with self.assertRaises(ValueError):compile_trail(self.blob,bad)

class WildlifeTrailProjects(TrailProjects):
    wildlife=True

if __name__=='__main__':unittest.main()
