"""Real authenticated director execution. Native battle outcomes are explicit fixture reports."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_shared_generated_cave import MemoryAuthority
from world.client import CampaignClient
from world.campaigns import validate

ROOT=Path(__file__).resolve().parents[2]

class WireSocket:
    def __init__(self,server):
        self.server=server;self.conn=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=self)
    def settimeout(self,_):pass
    def connect(self,_):pass
    def makefile(self,_):return self
    def close(self):pass
    def sendall(self,data):
        for line in data.splitlines():self.server._line(self.conn,line)
    def readline(self,limit=65536):
        out=self.conn['out'];end=out.find(b'\n')+1
        if not end:raise AssertionError('authority did not reply')
        row=bytes(out[:min(end,limit)]);del out[:len(row)];return row

class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.s=self.open();self.addCleanup(lambda:self.s.close())
        self.doc=json.loads((ROOT/'examples/emerald_sprint_campaign.json').read_text())
        self.definition=self.admin(dict(command='campaign_publish',definition=self.doc))['definition']
        self.a=self.connect('Alice');self.b=self.connect('Bob');self.counter=0
    def open(self):return MemoryAuthority(self.root/'socket',self.root/'world',persist_generated_cave=True,archive_generated_areas=True)
    def connect(self,name):
        identity=self.s.create_identity(name)
        with patch('world.client.socket.socket',return_value=WireSocket(self.s)):
            return CampaignClient('fixture',name,identity['token'])
    def admin(self,request):
        conn=dict(out=bytearray(),closing=False);self.s._admin_line(conn,json.dumps(request).encode());return json.loads(conn['out'])
    def start(self,client=None,key='start'):
        result=(client or self.a).start_campaign(self.definition,key);self.assertTrue(result['ok'],result);return result
    def act(self,run,action,value=None,client=None,key=None):
        self.counter+=1
        result=(client or self.a).campaign_action(run['run'],run['revision'],action,value,key or 'action_'+str(self.counter))
        self.assertTrue(result['ok'],result);return result
    def battle(self,run,outcome='win'):
        pending=self.act(run,'battle');ticket=pending['state']['pending']['ticket']
        result=self.admin(dict(command='campaign_report',ticket=ticket,outcome=outcome));self.assertTrue(result['ok'],result)
        return self.a.campaign_status(run['run'])
    def reach_battle(self):
        run=self.start();run=self.act(run,'continue');run=self.act(run,'choose','wally');return self.act(run,'recruit',True)

    def test_emerald_sprint_all_battles_choices_recruitment_and_private_ending(self):
        sentinel=self.root/'normal-trainer.sav';sentinel.write_bytes(b'never touched')
        before=self.s.db.execute('SELECT seq,kind,data FROM events').fetchall();run=self.reach_battle()
        run=self.act(run,'squad',['partner','wally']);battles=0
        while run['state']['status']!='completed':
            kind=run['node']['kind']
            if kind=='battle':run=self.battle(run);battles+=1
            elif kind=='recruit':run=self.act(run,'recruit',True);run=self.act(run,'squad',['wally','scout'])
            elif kind=='end':run=self.act(run,'finish')
            else:self.fail('unexpected node')
        self.assertEqual(battles,13);self.assertEqual(run['state']['roster'],['partner','wally','scout'])
        self.assertEqual(sentinel.read_bytes(),b'never touched');self.assertEqual(self.s.db.execute('SELECT seq,kind,data FROM events').fetchall(),before)
        self.assertNotIn('campaign_runs',json.dumps(self.s.inspect()))
        self.assertEqual(self.b.campaign_runs()['runs'],[])
        self.assertEqual(self.a.campaign_runs()['runs'][0]['status'],'completed')
        self.assertEqual(run['native_adapter'],'not_connected')

    def test_identity_frozen_definition_and_exact_request_replay(self):
        run=self.start();again=self.a.start_campaign(self.definition,'start')
        self.assertEqual(again['run'],run['run']);self.assertTrue(again['replayed'])
        self.assertFalse(self.b.campaign_status(run['run'])['ok'])
        self.assertFalse(self.a._request(dict(command='campaign_publish',definition=self.doc))['ok'])
        self.assertFalse(self.b.campaign_action(run['run'],0,'continue',None,'steal')['ok'])
        other=copy.deepcopy(self.doc);other['title']='Different authored run'
        new=self.admin(dict(command='campaign_publish',definition=other))['definition'];self.assertNotEqual(new,self.definition)
        self.assertEqual(self.a.campaign_status(run['run'])['title'],'Emerald Sprint')
        self.assertFalse(self.a.start_campaign(new,'start')['ok'])
        moved=self.act(run,'continue',key='go')
        self.assertFalse(self.a.campaign_action(run['run'],0,'choose','may','stale')['ok'])
        self.assertFalse(self.a.campaign_action(run['run'],moved['revision'],'choose','may','go')['ok'])
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM campaign_runs').fetchone()[0],1)

    def test_pending_ticket_survives_restart_loss_abort_and_retry(self):
        run=self.reach_battle();pending=self.act(run,'battle');ticket=pending['state']['pending']
        self.assertEqual(ticket['squad'],[self.doc['members']['partner']['mon']])
        self.assertIn('no_normal_save_writes',ticket['restrictions'])
        self.assertEqual(ticket['evidence'],'battle_requested_not_started')
        self.assertFalse(self.a.campaign_action(run['run'],pending['revision'],'squad',['wally'],'bad')['ok'])
        self.assertFalse(self.a.campaign_action(run['run'],pending['revision'],'abandon',None,'bad2')['ok'])
        self.assertFalse(self.a._request(dict(command='campaign_report',ticket=ticket['ticket'],outcome='win'))['ok'])
        self.s.close();self.s=self.open();self.a=self.connect('Alice')
        restored=self.a.campaign_status(run['run']);self.assertEqual(restored['state']['pending'],ticket)
        report=dict(command='campaign_report',ticket=ticket['ticket'],outcome='loss')
        result=self.admin(report);self.assertTrue(result['ok']);self.assertTrue(self.admin(report)['replayed'])
        self.assertFalse(self.admin(dict(report,outcome='win'))['ok'])
        failed=self.a.campaign_status(run['run']);self.assertEqual(failed['state']['node'],'boss_0')
        aborted=self.battle(failed,'abort');self.assertEqual(aborted['state']['node'],'boss_0')
        won=self.battle(aborted);self.assertEqual(won['state']['node'],'boss_1')
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM campaign_battles').fetchone()[0],3)

    def test_receipt_and_result_failure_roll_back_and_retry_exactly_once(self):
        run=self.reach_battle();before=copy.deepcopy(run)
        self.s.db.execute("CREATE TRIGGER deny_campaign BEFORE INSERT ON campaign_requests BEGIN SELECT RAISE(ABORT,'fixture'); END")
        reply=self.a.campaign_action(run['run'],run['revision'],'battle',None,'retry')
        self.assertFalse(reply['ok']);self.assertEqual(self.a.campaign_status(run['run']),before)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM campaign_battles').fetchone()[0],0)
        self.s.db.execute('DROP TRIGGER deny_campaign')
        pending=self.act(run,'battle',key='retry');ticket=pending['state']['pending']['ticket']
        self.s.db.execute("CREATE TRIGGER deny_result BEFORE UPDATE ON campaign_battles BEGIN SELECT RAISE(ABORT,'fixture'); END")
        report=dict(command='campaign_report',ticket=ticket,outcome='win')
        self.assertFalse(self.admin(report)['ok']);self.assertEqual(self.a.campaign_status(run['run']),pending)
        self.s.db.execute('DROP TRIGGER deny_result');self.assertTrue(self.admin(report)['ok'])
        self.assertEqual(self.a.campaign_status(run['run'])['state']['node'],'boss_1')

    def test_bad_graph_unknown_species_invalid_actions_and_recruit_decline(self):
        for edit in ('cycle','unreachable','species','choice'):
            bad=copy.deepcopy(self.doc)
            if edit=='cycle':bad['nodes']['boss_0']['next']='opening'
            elif edit=='unreachable':bad['nodes']['unused']=dict(kind='end',text='Unused')
            elif edit=='species':bad['members']['partner']['mon']['species']=999999
            else:bad['nodes']['ally']['options'][1]['id']='wally'
            with self.assertRaises(ValueError):validate(bad)
        run=self.start();self.assertFalse(self.a.campaign_action(run['run'],0,'battle',None,'skip')['ok'])
        run=self.act(run,'continue');run=self.act(run,'choose','may');run=self.act(run,'recruit',False)
        self.assertEqual(run['state']['roster'],['partner'])
        self.assertFalse(self.a.campaign_action(run['run'],run['revision'],'squad',['may'],'not_recruited')['ok'])
        run=self.act(run,'abandon');self.assertEqual(run['state']['status'],'abandoned')
        self.assertTrue(self.a.start_campaign(self.definition,'new_run')['ok'])

if __name__=='__main__':unittest.main()
