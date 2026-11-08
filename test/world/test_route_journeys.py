"""Authored fork/rejoin journeys constrained by the actual final walking graph."""
from collections import deque
from copy import deepcopy
import os
import unittest
from unittest.mock import patch
from world.route_landscape import compile_plan
from world.author_routes import author
from world.shared_cave import SharedCave
from test_author_cave import wire


def plan():
    return dict(seed=19,loops=0,reservations=[],
        landmarks=[dict(id=n,x=x,y=y,radius=6) for n,x,y in
                   [('camp',20,20),('west',30,75),('east',75,30),('sanctuary',90,90)]],
        journey=dict(connections=[['entry','camp'],['camp','west'],['west','sanctuary'],
                                  ['camp','east'],['east','sanctuary'],['sanctuary','exit']],
                     required=['camp','sanctuary']))


def reachable(blob,site):
    cells=blob[8:];blocked={(x,y) for x in range(127) for y in range(127)
                           if (x-site['x'])**2+(y-site['y'])**2<=site['radius']**2}
    seen={(1,1)};queue=deque(seen)
    while queue:
        x,y=queue.popleft()
        for p in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
            a,b=p
            if 0<=a<127 and 0<=b<127 and cells[b*127+a]==46 and p not in blocked and p not in seen:
                seen.add(p);queue.append(p)
    return (125,125) in seen


class RouteJourneys(unittest.TestCase):
    def test_actual_fork_rejoin_requires_camp_and_sanctuary_not_either_branch(self):
        p=plan();blob,report=compile_plan(p)
        self.assertEqual(SharedCave(blob).version,16)
        self.assertEqual(len(report['routes']),6)
        self.assertTrue(all(route['kind']=='authored' for route in report['routes']))
        self.assertEqual((blob,report),compile_plan(p))
        for site in p['landmarks']:
            self.assertEqual(reachable(blob,site),site['id'] in ('west','east'))
        with patch('world.author_cave.request_validated',side_effect=lambda prompt,validate,**kw:validate(wire(p))):
            self.assertEqual(author('Two approaches to a shared sanctuary')[0],blob)

    def test_impossible_required_passage_and_disconnected_graph_rejected(self):
        p=plan();p['journey']['required'].append('west')
        with self.assertRaisesRegex(ValueError,'bypassed'):compile_plan(p)
        p=plan();p['journey']['connections']=p['journey']['connections'][:-1]
        with self.assertRaisesRegex(ValueError,'connect every'):compile_plan(p)
        p=plan();p['journey']['connections'].append(['camp','entry'])
        with self.assertRaisesRegex(ValueError,'duplicate'):compile_plan(p)
        p=plan();p['loops']=1
        with self.assertRaises(ValueError):compile_plan(p)

    def test_shortcut_is_actual_new_walkable_geometry(self):
        p=plan();old,_=compile_plan(p)
        p['journey']['connections'].insert(-1,['camp','sanctuary'])
        new,report=compile_plan(p)
        self.assertNotEqual(old,new)
        self.assertEqual(len(report['routes']),7)
        self.assertGreater(sum(c==46 for c in new),sum(c==46 for c in old))

    def test_shared_discovery_can_ground_authoritative_journey_publication(self):
        import test_landmark_survey
        from world.author_routes import main
        f=test_landmark_survey.LandmarkSurveyTests();f.setUp();self.addCleanup(f.doCleanups)
        f.command('/explore start');f.state(f.conn,15,20);f.command('/explore share camp confirm')
        evidence=f.s.memory.history()['events'][-1]
        f.send(f.conn,f'STATE {f.conn["seq"]+1} 0 9 8 8 4 7 1 '+'a'*16+' '+'b'*16)
        def transport(_socket,request,**kwargs):return f.f.admin(request)
        def provider(prompt,validate,**kwargs):
            self.assertIn('landmark_discovery_shared',prompt)
            self.assertNotIn('Scout',prompt)
            return validate(wire(plan()))
        with patch('world.client.admin_request',side_effect=transport), \
             patch('world.publish_cave.admin_request',side_effect=transport), \
             patch('world.author_cave.request_validated',side_effect=provider):
            self.assertEqual(main(['Build two approaches beyond the shared camp','--activate-shared','admin','--label','Twin Approaches']),0)
        self.assertEqual(f.s.shared_cave.identity,compile_plan(plan())[1]['revision'])
        self.assertIn(evidence['seq'],f.s.memory.history()['events'][-1]['history_evidence'])

    @unittest.skipUnless(os.environ.get('EW_NATIVE_SOURCE'),'set EW_NATIVE_SOURCE to verified Expansion source')
    def test_journeys_use_actual_native_codec_with_coastal_landmarks(self):
        import test_route_coasts
        case=test_route_coasts.RouteCoasts()
        with patch.object(test_route_coasts,'plan',side_effect=plan):
            case.test_actual_native_codec_accepts_coasts_and_rejects_corruption()

if __name__=='__main__':unittest.main()
