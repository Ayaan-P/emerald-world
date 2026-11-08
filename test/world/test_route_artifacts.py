"""Actual model-output validation -> admin activation -> durable private survey."""
import base64
import json
import unittest
from unittest.mock import patch
import test_author_routes as fixtures
from test_route_landscape import plan
from test_author_cave import wire
from world import author_routes, landmark_survey
from world.route_artifacts import create, load
from world.server import MAX_ADMIN_LINE


class RouteArtifactTests(fixtures.RouteAuthorTests):
    def test_generated_plan_survives_restart_and_registers_without_original_prompt(self):
        requests=[]
        def transport(sock,request,**kwargs):
            requests.append(request)
            self.assertLess(len(json.dumps(request).encode()),MAX_ADMIN_LINE)
            return self.transport(sock,request,**kwargs)
        with patch('world.client.admin_request',side_effect=transport), \
             patch('world.publish_cave.admin_request',side_effect=transport), \
             patch('world.author_cave.request_validated',side_effect=self.provider):
            self.assertEqual(author_routes.main(['Honor Redwood','--activate-shared','admin','--label','Refuge']),0)
        revision=self.server.shared_cave.identity
        artifact=load(self.server,revision)
        self.assertEqual(artifact['plan'],plan())
        self.assertNotIn('PrivateTrainer',json.dumps(artifact))
        self.assertNotIn('public_history',artifact)
        self.server.close();self.case.server=self.case.open();self.server=self.case.server
        with patch('world.client.admin_request',side_effect=self.transport):
            landmark_survey.main(['--revision',revision,'--admin-socket','admin'])
        sites=json.loads(self.server.db.execute('SELECT sites FROM survey_routes WHERE revision=?',(revision,)).fetchone()[0])
        self.assertEqual({p['id'] for p in sites},{p['id'] for p in plan()['landmarks']})
        # Re-enter after restart using fresh authentication and exact ACK.
        token=self.server.create_identity('Scout')['token']
        conn=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
        def send(line):
            self.server._line(conn,line.encode());self.assertFalse(conn['closing'])
        send(f'HELLO 1 Scout {token} SOCIALCAVE16');send('CHAT_ENABLE')
        send('CAVE GET');send('CAVE ACK '+revision)
        site=sites[0];g,n=self.server.wilds_map
        send(f'STATE 1 {g} {n} {site["x"]} {site["y"]} 4 7 1 '+ 'a'*16+' '+'b'*16)
        before=self.server.memory.history()['events']
        send('CHAT 2 * '+b'/explore start'.hex())
        self.assertEqual(self.server.db.execute('SELECT landmark FROM survey_visits WHERE trainer=?',('Scout',)).fetchone()[0],site['id'])
        self.assertEqual(self.server.memory.history()['events'],before)

    def test_offline_sidecar_registers_exact_archived_revision(self):
        output=self.case.root/'route.ewmap'
        with patch('world.author_cave.request_validated',side_effect=lambda p,v,**kw:v(wire(plan()))):
            self.assertEqual(author_routes.main(['coastal route','--output',str(output)]),0)
        sidecar=output.with_name(output.name+'.route.json')
        artifact=json.loads(sidecar.read_text())
        self.server._replace_cave(output.read_bytes())
        with patch('world.client.admin_request',side_effect=self.transport):
            landmark_survey.main([str(sidecar),'--admin-socket','admin'])
        self.assertEqual(artifact['revision'],self.server.shared_cave.identity)
        with patch('world.author_cave.request_validated') as provider:
            self.assertEqual(author_routes.main(['theme','--output',str(output)]),1)
            provider.assert_not_called()

    def test_tampered_artifact_refuses_before_world_changes(self):
        blob,artifact=create(plan());artifact['report']['landmarks'][1]['x']+=1
        result=self.case.admin(dict(command='replace_cave',template=base64.b64encode(blob).decode(),route_artifact=artifact))
        self.assertFalse(result['ok'])
        self.assertEqual(self.server.shared_cave.identity,self.old)
        self.assertEqual(self.server.db.execute('SELECT count(*) FROM route_artifacts').fetchone()[0],0)

    def test_artifact_is_immutable_and_database_failure_rolls_back_activation(self):
        blob,artifact=create(plan())
        self.server.db.execute("CREATE TRIGGER refuse_artifact BEFORE INSERT ON route_artifacts BEGIN SELECT RAISE(ABORT,'fixture'); END")
        with self.assertRaises(ValueError):self.server._replace_cave(blob,route_artifact=artifact)
        self.assertEqual(self.server.shared_cave.identity,self.old)
        self.assertEqual(len(self.server.list_generated_areas()),1)
        self.server.db.execute('DROP TRIGGER refuse_artifact')
        self.server._replace_cave(blob,route_artifact=artifact)
        renamed=plan();renamed['landmarks'][0]['id']='renamed'
        same_blob,other=create(renamed)
        self.assertEqual(same_blob,blob)
        with self.assertRaisesRegex(ValueError,'already fixed'):
            self.server._replace_cave(same_blob,route_artifact=other)
        artifact['report']['limitations']='fabricated'
        with self.assertRaises(ValueError):self.server._replace_cave(blob,route_artifact=artifact)
        self.assertNotIn('fabricated',json.dumps(load(self.server,self.server.shared_cave.identity)))

if __name__=='__main__':unittest.main()
