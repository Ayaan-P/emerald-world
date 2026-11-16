import json
import unittest
from world.shared_outdoor_palette import paint_biome, add_ponds, add_trail
from world.shared_cave import SharedCave


class SharedTrailTests(unittest.TestCase):
    def setUp(self):
        rows=['#'*127]+['#'+'.'*125+'#']*125+['#'*127]
        proposal={'rows':rows,'spawn':[1,1],'exit':[125,125]}
        self.blob,_=add_ponds(paint_biome(proposal,'grassland',32),32,5)

    def test_trail_changes_palette_not_collision(self):
        before=SharedCave(self.blob)
        out,steps,changed=add_trail(self.blob,'sand',3)
        self.assertEqual((out,steps,changed),add_trail(self.blob,'sand',3))
        after=SharedCave(out)
        self.assertGreater(steps,0); self.assertGreater(changed,0)
        self.assertEqual(before._rows,after._rows)
        self.assertEqual(after.version,17)
        self.assertEqual(after.palette[1*127+1],ord('.'))
        for i,b in enumerate(before.palette):
            if b in (ord('#'),ord('r')): self.assertEqual(after.palette[i],b)
        self.assertIn(ord('s'),after.palette)

    def test_bad_arguments_and_unreachable_are_rejected(self):
        for terrain,width in [('water',1),('sand',2),('grass',True)]:
            with self.assertRaises(ValueError): add_trail(self.blob,terrain,width)
        blocked=bytearray(self.blob); blocked[8+127+1]=ord('#')
        with self.assertRaises(ValueError): add_trail(bytes(blocked),'sand',1)

    def test_real_author_plan(self):
        import test_actor_runtime as fixture
        from world import actor_runtime as runtime
        case=fixture.ActorRuntimeTests(); case.setUp(); self.addCleanup(case.doCleanups)
        server=case.s;server.archive_generated_areas=True;server.persist_generated_cave=True
        blueprint=dict(rooms=[[3,3,20,18],[75,80,25,20]],links=[[0,1]],entrance_room=0,exit_room=1,style='rooms',seed=357,corridor_width=3)
        args=dict(label='Trail',layout='connected_shapes',blueprint=json.dumps(blueprint,separators=(',',':')),biome='meadow',seed=42,ponds=2,trail='sand',trail_width=3)
        case.apply(dict(id='trail',purpose='Create a route.',steps=[dict(id='create',tool='world.create_trailed_landscape',args=args,after=[])]))
        self.assertEqual(runtime.tick(server,now=10)['status'],'succeeded')
        self.assertEqual(server.shared_cave.version,17)
        self.assertIn(ord('s'),server.shared_cave.palette)

class NetworkTrailTests(unittest.TestCase):
    def test_actor_network_connects_all_landmarks(self):
        import test_actor_runtime as fixture
        from world import actor_runtime as runtime
        case=fixture.ActorRuntimeTests();case.setUp();self.addCleanup(case.doCleanups)
        server=case.s;server.archive_generated_areas=True;server.persist_generated_cave=True
        plan=dict(seed=11,landmarks=[dict(id='grove',x=20,y=90,radius=5),dict(id='pond',x=90,y=25,radius=5)],reservations=[],loops=0)
        args=dict(label='Crossroads',layout='clearings',blueprint=json.dumps(plan,separators=(',',':')),biome='meadow',seed=22,ponds=3,trail='sand',trail_width=1)
        case.apply(dict(id='network',purpose='Connect outdoor clearings.',steps=[dict(id='create',tool='world.create_landscape_network',args=args,after=[])]))
        self.assertEqual(runtime.tick(server,now=10)['status'],'succeeded')
        cave=server.shared_cave
        self.assertEqual(cave.version,17)
        for site in plan['landmarks']:
            self.assertTrue(cave.walkable(site['x'],site['y']))
            self.assertEqual(cave.palette[site['y']*127+site['x']],ord('s'))
        self.assertEqual(cave.palette[127+1],ord('.'))

    def test_invalid_endpoint_rejected(self):
        for p in [((-1,3),(1,1)),((True,3),(1,1)),((1,1),(126,1))]:
            with self.assertRaises(ValueError):add_trail(SharedTrailTests_blob(),'sand',1,endpoints=p)

def SharedTrailTests_blob():
    rows=['#'*127]+['#'+'.'*125+'#']*125+['#'*127]
    return paint_biome(dict(rows=rows,spawn=[1,1],exit=[125,125]),'meadow',1)

class WatercourseTests(unittest.TestCase):
    def test_repeatable_connected_water_and_protected_sites(self):
        from world.shared_outdoor_palette import add_watercourse
        before=SharedTrailTests_blob();out,count=add_watercourse(before,7,protected_points=[(50,50)])
        self.assertEqual((out,count),add_watercourse(before,7,protected_points=[(50,50)]))
        cave=SharedCave(out);self.assertEqual(cave.version,17)
        self.assertGreaterEqual(count,8);self.assertTrue(cave.walkable(50,50))
        self.assertEqual(cave.palette.count(ord('#'))-SharedCave(before).palette.count(ord('#')),count)
        for i,prior in enumerate(SharedCave(before).palette):
            if prior in (ord('#'),ord('r')):self.assertEqual(cave.palette[i],prior)

    def test_agent_creates_routed_landscape_with_watercourse(self):
        import test_actor_runtime as fixture
        from world import actor_runtime as runtime
        case=fixture.ActorRuntimeTests();case.setUp();self.addCleanup(case.doCleanups)
        server=case.s;server.archive_generated_areas=True;server.persist_generated_cave=True
        plan=dict(seed=11,landmarks=[dict(id='grove',x=20,y=90,radius=10),dict(id='pond',x=90,y=25,radius=10)],reservations=[],loops=0)
        args=dict(label='Creek',layout='clearings',blueprint=json.dumps(plan,separators=(',',':')),biome='meadow',seed=22,ponds=0,trail='sand',trail_width=1)
        case.apply(dict(id='creek',purpose='Make a place to explore.',steps=[dict(id='create',tool='world.create_watercourse_landscape',args=args,after=[])]))
        self.assertEqual(runtime.tick(server,now=10)['status'],'succeeded')
        cave=server.shared_cave;self.assertEqual(cave.version,17)
        for site in plan['landmarks']:
            self.assertTrue(cave.walkable(site['x'],site['y']))
            self.assertEqual(cave.palette[site['y']*127+site['x']],ord('s'))

    def test_ponds_watercourse_and_marked_network_survive_authority_restart(self):
        import test_actor_runtime as fixture
        from world import actor_runtime as runtime
        case=fixture.ActorRuntimeTests();case.setUp();self.addCleanup(case.doCleanups)
        server=case.s;server.archive_generated_areas=True;server.persist_generated_cave=True
        plan=dict(seed=11,landmarks=[dict(id='grove',x=20,y=90,radius=10),dict(id='ridge',x=90,y=25,radius=10)],reservations=[],loops=0)
        args=dict(label='Creek and ponds',layout='clearings',blueprint=json.dumps(plan,separators=(',',':')),biome='meadow',seed=1,ponds=3,trail='sand',trail_width=1)
        case.apply(dict(id='waters',purpose='Create a connected place.',steps=[dict(id='create',tool='world.create_watercourse_landscape',args=args,after=[])]))
        outcome=runtime.tick(server,now=10)
        self.assertEqual(outcome['status'],'succeeded')
        event=next(e for e in server.memory.history()['events'] if e['seq']==outcome['seq'])
        report=event['result']['report']
        self.assertEqual(report['ponds_created'],3)
        self.assertEqual(report['pond_placement'],'walkable_ground_v2')
        self.assertGreaterEqual(report['watercourse_tiles'],8)
        self.assertEqual(report['marked_routes'],report['routes'])
        cave=server.shared_cave
        self.assertEqual(cave.version,17)
        for site in plan['landmarks']:
            self.assertTrue(cave.walkable(site['x'],site['y']))
        from collections import deque
        seen={(1,1)}; pending=deque(seen)
        while pending:
            x,y=pending.popleft()
            for point in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
                if point not in seen and cave.walkable(*point):
                    seen.add(point);pending.append(point)
        self.assertIn((125,125),seen)
        for site in plan['landmarks']:self.assertIn((site['x'],site['y']),seen)
        before=cave.identity,bytes(cave.palette)
        server.close();holder=case.f.f.f.case;holder.server=holder.open();case.s=holder.server
        self.assertEqual((case.s.shared_cave.identity,bytes(case.s.shared_cave.palette)),before)

class LandmarkTerrainTests(unittest.TestCase):
    def test_distinct_clearings_preserve_geometry_and_reject_invalid_zones(self):
        from world.route_landscape import compile_plan
        from world.shared_outdoor_palette import paint_landmarks
        plan=dict(seed=11,landmarks=[dict(id='grove',x=20,y=90,radius=10),dict(id='ridge',x=90,y=25,radius=10)],reservations=[],loops=0)
        raw,report=compile_plan(plan);cells=raw[8:]
        base=paint_biome(dict(rows=[cells[i*127:(i+1)*127].decode() for i in range(127)],spawn=[1,1],exit=[125,125]),'meadow',1)
        zones={'grove':'long_grass','ridge':'sand'}
        out=paint_landmarks(base,report['landmarks'],zones)
        self.assertEqual(out,paint_landmarks(base,report['landmarks'],zones))
        before,after=SharedCave(base),SharedCave(out)
        self.assertEqual(before._rows,after._rows)
        self.assertEqual(after.palette[90*127+20],ord('g'))
        self.assertEqual(after.palette[25*127+90],ord('s'))
        for bad in ({'missing':'sand'},{'entry':'grass'},{'grove':'water'},[],{'grove':None}):
            with self.assertRaises(ValueError):paint_landmarks(base,report['landmarks'],bad)

    def test_character_creates_multi_terrain_area_with_water_and_routes(self):
        import test_actor_runtime as fixture
        from world import actor_runtime as runtime
        case=fixture.ActorRuntimeTests();case.setUp();self.addCleanup(case.doCleanups)
        server=case.s;server.archive_generated_areas=True;server.persist_generated_cave=True
        plan=dict(seed=11,landmarks=[dict(id='grove',x=20,y=90,radius=10),dict(id='ridge',x=90,y=25,radius=10)],reservations=[],loops=0)
        args=dict(label='Grove and ridge',layout='clearings',blueprint=json.dumps(plan,separators=(',',':')),biome='meadow',seed=1,ponds=3,trail='sand',trail_width=1,zones=json.dumps({'grove':'long_grass','ridge':'sand'}))
        case.apply(dict(id='landmarks',purpose='Create distinctive connected places.',steps=[dict(id='create',tool='world.create_landmark_landscape',args=args,after=[])]))
        result=runtime.tick(server,now=10);self.assertEqual(result['status'],'succeeded')
        event=next(e for e in server.memory.history()['events'] if e['seq']==result['seq'])
        report=event['result']['report']
        self.assertEqual(report['landmark_terrain'],{'grove':'long_grass','ridge':'sand'})
        self.assertEqual(report['ponds_created'],3);self.assertGreaterEqual(report['watercourse_tiles'],8)
        cave=server.shared_cave
        self.assertEqual(cave.version,17)
        self.assertIn(ord('g'),cave.palette);self.assertIn(ord('s'),cave.palette)
        for site in plan['landmarks']:self.assertTrue(cave.walkable(site['x'],site['y']))

    def test_owner_registers_survey_on_painted_landscape(self):
        import test_actor_runtime as fixture
        import test_landmark_survey as survey
        from admin_transport import admin_request
        from world import actor_runtime as runtime
        case=fixture.ActorRuntimeTests();case.setUp();self.addCleanup(case.doCleanups)
        s=case.s;s.archive_generated_areas=True;s.persist_generated_cave=True
        plan=dict(seed=11,landmarks=[dict(id='grove',x=20,y=90,radius=10),dict(id='ridge',x=90,y=25,radius=10)],reservations=[],loops=0)
        args=dict(label='Survey landscape',layout='clearings',blueprint=json.dumps(plan,separators=(',',':')),biome='meadow',seed=1,ponds=3,trail='sand',trail_width=1,zones=json.dumps({'grove':'long_grass','ridge':'sand'}))
        case.apply(dict(id='surveyland',purpose='Create a route.',steps=[dict(id='create',tool='world.create_landmark_landscape',args=args,after=[])]))
        self.assertEqual(runtime.tick(s,now=10)['status'],'succeeded')
        revision=s.shared_cave.identity
        self.assertFalse(admin_request(s,dict(command='register_survey',plan=plan))['ok'])
        self.assertTrue(admin_request(s,dict(command='register_survey',plan=plan,revision=revision))['ok'])
        self.assertEqual(s.db.execute('SELECT count(*) FROM survey_routes WHERE revision=?',(revision,)).fetchone()[0],1)
        h=survey.LandmarkSurveyTests();h.s=s;h.revision=revision
        token=s.create_identity('SurveyScout')['token'];h.conn=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
        h.send(h.conn,'HELLO 1 SurveyScout '+token+' SOCIALCAVE17');h.send(h.conn,'CHAT_ENABLE');h.send(h.conn,'CAVE GET');h.send(h.conn,'CAVE ACK '+revision)
        h.state(h.conn,20,90);h.command('/explore start');self.assertEqual(h.count(),1)
        h.command('/explore share grove confirm')
        event=s.memory.history()['events'][-1]
        self.assertEqual((event['event'],event['revision'],event['landmark']),('landmark_discovery_shared',revision,'grove'))
        changed=dict(plan,landmarks=[dict(id='grove',x=40,y=40,radius=4),plan['landmarks'][1]])
        self.assertFalse(admin_request(s,dict(command='register_survey',plan=changed,revision=revision))['ok'])
