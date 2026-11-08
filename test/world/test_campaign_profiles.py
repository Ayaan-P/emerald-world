"""Real profile files/locks and sandbox command construction; no native launch."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from world.campaign_profiles import campaign_profile,adapter_command,result_report,validate_ticket,RESTRICTIONS
from world.launcher import profile_paths


def ticket():
    return dict(schema=1,ticket='a'*32,run='b'*32,definition='c'*64,node='boss_0',
                squad=[dict(species=252,level=50)],enemy=[dict(species=299,level=50)],
                adapter='isolated_frontier_campaign_v1',evidence='battle_requested_not_started',restrictions=RESTRICTIONS[:])

class CampaignProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.world=self.root/'world';self.world.mkdir(mode=0o700)
        self.normal=profile_paths(self.world,'Alice',engine='expansion-native')
        self.normal['profile'].mkdir(parents=True,mode=0o700);self.normal['save'].write_bytes(b'normal trainer save')
        self.seed=self.root/'starter.sav';self.seed.write_bytes(b'explicit disposable starter')
    def test_profile_seed_resume_lock_and_no_normal_profile_mount(self):
        t=ticket()
        with campaign_profile(self.world,'Alice',t,seed_save=self.seed) as prepared:
            self.assertEqual(prepared['paths']['save'].read_bytes(),self.seed.read_bytes())
            self.assertNotEqual(prepared['paths']['save'],self.normal['save'])
            self.assertEqual(prepared['ticket'].stat().st_mode&0o777,0o600)
            with self.assertRaises(ValueError):
                with campaign_profile(self.world,'Bob',t):pass
            with patch('world.campaign_profiles.subprocess.run',return_value=subprocess.CompletedProcess([],0,'EW_CAMPAIGN 1\n','')) as probe:
                command=adapter_command('/usr/bin/false',prepared)
            probe_command=probe.call_args.args[0]
            for arguments in (command,probe_command):
                self.assertIn('--unshare-all',arguments);self.assertNotIn('--world-config',arguments)
                self.assertNotIn(str(self.normal['save']),arguments);self.assertNotIn(str(self.normal['profile']),arguments)
                self.assertNotIn(str(self.world/'admin.sock'),arguments)
            self.assertIn(str(prepared['ticket']),command)
            self.assertIn('--campaign-result',command)
            prepared['paths']['save'].write_bytes(b'campaign-only progress')
        with campaign_profile(self.world,'Alice',t) as resumed:self.assertEqual(resumed['paths']['save'].read_bytes(),b'campaign-only progress')
        self.assertEqual(self.normal['save'].read_bytes(),b'normal trainer save')
        self.assertEqual(self.seed.read_bytes(),b'explicit disposable starter')
        with self.assertRaises(ValueError):
            with campaign_profile(self.world,'Alice',t,seed_save=self.seed):pass

    def test_owner_definition_ticket_conflicts_and_symlinks_refuse(self):
        t=ticket()
        with campaign_profile(self.world,'Alice',t):pass
        for trainer,changed in [('Bob',t),('Alice',dict(t,definition='d'*64)),('Alice',dict(t,node='other'))]:
            with self.assertRaises(ValueError):
                with campaign_profile(self.world,trainer,changed):pass
        other=dict(t,run='e'*32);root=self.world/'.campaign-runs'/other['run'];root.symlink_to(self.normal['profile'])
        with self.assertRaises(ValueError):
            with campaign_profile(self.world,'Alice',other):pass
        self.assertEqual(self.normal['save'].read_bytes(),b'normal trainer save')

    def test_unsupported_engine_and_result_cannot_claim_battle_or_restore(self):
        with campaign_profile(self.world,'Alice',ticket()) as prepared:
            for output in ('','EW_CAMPAIGN 2','ordinary game started'):
                with patch('world.campaign_profiles.subprocess.run',return_value=subprocess.CompletedProcess([],0,output,'')):
                    with self.assertRaisesRegex(ValueError,'campaign launch refused'):adapter_command('/usr/bin/false',prepared)
            good=dict(schema=1,ticket='a'*32,outcome='win',party_restored=True)
            for bad in (dict(good,ticket='f'*32),dict(good,party_restored=False),dict(good,outcome='unknown')):
                prepared['result'].write_text(json.dumps(bad));prepared['result'].chmod(0o600)
                with self.assertRaises(ValueError):result_report(prepared)
            prepared['result'].write_text(json.dumps(good))
            self.assertEqual(result_report(prepared),dict(command='campaign_report',ticket='a'*32,outcome='win'))
            prepared['result'].chmod(0o644)
            with self.assertRaises(ValueError):result_report(prepared)
            prepared['result'].unlink();prepared['result'].symlink_to(self.normal['save'])
            with self.assertRaises(OSError):result_report(prepared)

    def test_untrusted_contract_fields_and_unseeded_profile_do_not_copy_online(self):
        for change in ({'run':'../normal'},{'schema':True},{'restrictions':[]},{'squad':[dict(species=True,level=50)]}):
            with self.assertRaises(ValueError):validate_ticket(dict(ticket(),**change))
        with campaign_profile(self.world,'Alice',ticket()) as prepared:self.assertFalse(prepared['paths']['save'].exists())
        self.assertEqual(self.normal['save'].read_bytes(),b'normal trainer save')

if __name__=='__main__':unittest.main()
