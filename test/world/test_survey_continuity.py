"""Actual construction retains evidence for unchanged sites, not invented visits."""
import json
import unittest
from unittest.mock import patch
import test_landmark_survey as survey
from world.route_artifacts import load


def route():
    return dict(seed=19,loops=0,reservations=[],landmarks=[
        dict(id='lagoon',x=35,y=35,radius=20,landform='lagoon'),
        dict(id='camp',x=95,y=95,radius=8)])

BUILD=dict(x=41,y=33,width=5,height=5,gate='west',reservations=[])

class SurveyContinuity(unittest.TestCase):
    def setUp(self):
        self.f=survey.LandmarkSurveyTests()
        with patch.object(survey,'plan',side_effect=route):self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        # setUp registers an exact plan against bytes-only publication.
        # Registration itself must retain the recipe used by construction.
        self.s=self.f.s
        self.assertEqual(load(self.s,self.s.shared_cave.identity)['plan'],route())
        self.old=self.s.shared_cave.identity
        self.f.command('/explore start')
        self.f.state(self.f.conn,35,35);self.f.state(self.f.conn,95,95)
        self.assertEqual(self.f.count(),2)
        self.f.send(self.f.conn,f'STATE {self.f.conn["seq"]+1} 0 9 8 8 4 7 1 '+'a'*16+' '+'b'*16)

    def build(self):
        context=self.s.memory.context(self.s)
        return self.f.f.admin(dict(command='construct_outpost',plan=BUILD,label='Lagoon station',
            previous_revision=self.old,expected_world_id=context['world_id'],expected_sequence=context['through']))

    def test_growth_restart_preserves_only_unchanged_private_evidence(self):
        # No original plan file or fresh authoring is available after restart.
        self.s.close();self.f.f.server=self.f.f.open();self.s=self.f.s=self.f.f.server
        result=self.build();self.assertTrue(result['ok'],result);new=result['revision']
        artifact=load(self.s,new)
        self.assertEqual(artifact['schema'],2)
        self.assertEqual(artifact['report']['retained'],['camp'])
        self.assertEqual(artifact['report']['changed'],['lagoon'])
        self.assertEqual(self.s.memory.place(new),self.s.memory.place(self.old))
        self.assertEqual(self.s.db.execute('SELECT landmark,source_revision FROM survey_inherited WHERE revision=?',(new,)).fetchall(),[('camp',self.old)])
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM survey_visits WHERE revision=?',(new,)).fetchone()[0],0)
        self.assertEqual(self.f.count(),2)  # original observations remain intact
        self.assertFalse(any(e['event']=='landmark_discovery_shared' for e in self.s.memory.history()['events']))
        self.s.close();self.f.f.server=self.f.f.open();self.s=self.f.s=self.f.f.server
        self.f.revision=new;self.f.conn=self.f.connect('Scout')
        registered=self.f.f.admin(dict(command='register_survey',revision=new))
        self.assertTrue(registered['ok']);self.assertEqual(registered['landmarks'],3)
        lines=self.s.landmark_survey.lines(self.f.conn)
        self.assertIn('unchanged landmarks',' '.join(lines));self.assertIn('1/3',' '.join(lines))
        self.f.state(self.f.conn,35,35)
        self.assertIn('2/3',' '.join(self.s.landmark_survey.lines(self.f.conn)))
        site=next(p for p in artifact['report']['landmarks'] if p['id'] in artifact['report']['new'])
        self.f.state(self.f.conn,site['x'],site['y'])
        self.assertIn('Survey complete',' '.join(self.s.landmark_survey.lines(self.f.conn)))
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM survey_publications').fetchone()[0],0)
        # A different player has no inherited progress.
        other=self.f.connect('Other');self.assertIn('/explore start',self.s.landmark_survey.lines(other)[0])

    def test_inhabited_settlement_commit_also_derives_survey(self):
        from types import SimpleNamespace
        from test_settlement_plans import SettlementFlow, FixtureRuntime, plan
        self.s.create_identity('Founder')
        self.s.guilds.command('Founder','create Builders')
        self.s.guilds.command('Founder','chronicle on')
        self.s.guilds.command('Founder','expedition start LittlerootTown 1')
        self.s.guilds.visit('Founder','LittlerootTown')
        outcome=self.s.memory.history()['events'][-1]['seq']
        p=plan();p['construction']=BUILD
        memory=self.s.memory.context(self.s)
        self.s.runtime=FixtureRuntime()
        result=SettlementFlow.transport(SimpleNamespace(server=self.s),'',dict(command='found_settlement',
            plan=p,outcome_seq=outcome,previous_revision=self.old,
            expected_world_id=memory['world_id'],expected_sequence=memory['through']))
        self.assertTrue(result['ok'],result)
        self.assertEqual(load(self.s,result['revision'])['report']['changed'],['lagoon'])
        self.assertTrue(any(obj['id']=='outpost_steward' for obj in self.s.objects))
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM survey_inherited WHERE revision=?',(result['revision'],)).fetchone()[0],1)

    def test_failed_continuity_write_rolls_back_map_artifact_and_sessions(self):
        self.s.db.execute("CREATE TRIGGER refuse_inherited BEFORE INSERT ON survey_inherited BEGIN SELECT RAISE(ABORT,'fixture'); END")
        result=self.build();self.assertFalse(result['ok'])
        self.assertEqual(self.s.shared_cave.identity,self.old)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM route_artifacts').fetchone()[0],1)
        self.assertEqual(self.s.db.execute('SELECT revision FROM survey_sessions WHERE trainer=?',('Scout',)).fetchone()[0],self.old)
        self.assertEqual(self.f.count(),2)

    def test_differently_registered_landmark_never_inherits_evidence(self):
        sites=json.loads(self.s.db.execute('SELECT sites FROM survey_routes WHERE revision=?',(self.old,)).fetchone()[0])
        next(site for site in sites if site['id']=='camp')['x']+=1
        with self.s.db:self.s.db.execute('UPDATE survey_routes SET sites=? WHERE revision=?',(json.dumps(sites),self.old))
        result=self.build();self.assertTrue(result['ok'])
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM survey_inherited WHERE revision=?',(result['revision'],)).fetchone()[0],0)

    def test_derived_artifact_replays_geometry_and_rejects_tampered_ancestry(self):
        result=self.build();self.assertTrue(result['ok']);new=result['revision']
        artifact=load(self.s,new);artifact['report']['retained'].append('lagoon')
        with self.s.db:self.s.db.execute('UPDATE route_artifacts SET artifact=? WHERE revision=?',(json.dumps(artifact),new))
        with self.assertRaisesRegex(ValueError,'invalid derived'):load(self.s,new)

class WildlifeSurveyContinuity(SurveyContinuity):
    def setUp(self):
        original_route=route
        original_send=survey.LandmarkSurveyTests.send
        def wildlife_route():
            p=original_route()
            p['encounters']=dict(rate=12,wildlife=[dict(species='ZUBAT',level=10)]*12)
            return p
        route_patch=patch(__name__+'.route',side_effect=wildlife_route)
        send_patch=patch.object(survey.LandmarkSurveyTests,'send',
            new=lambda fixture,conn,line:original_send(fixture,conn,line.replace('CAVE16','CAVE17')))
        route_patch.start();send_patch.start()
        self.addCleanup(route_patch.stop);self.addCleanup(send_patch.stop)
        super().setUp()
        self.assertEqual(self.s.shared_cave.version,17)

if __name__=='__main__':unittest.main()
