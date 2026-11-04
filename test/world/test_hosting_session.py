"""Actual HTTPS→native session handoff, with no GUI or native game process."""
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path

from world.hosting import HostedWorldManager, HostingService
from world.hosting_client import HostingClient, write_private
from world.session import DesktopSession


class HostedSessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='hs-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        cert, key = self.root/'cert.pem', self.root/'key.pem'
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes',
                        '-keyout',str(key),'-out',str(cert),'-days','1',
                        '-subj','/CN=localhost'], check=True, capture_output=True)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0))
            port = sock.getsockname()[1]
        self.manager = HostedWorldManager(self.root/'m', cert=cert,key=key,
                advertise_host='localhost', port_start=port,port_end=port,max_worlds=1)
        self.addCleanup(self.manager.close)
        self.service = HostingService(self.manager,('127.0.0.1',0)).start()
        self.addCleanup(self.service.close)
        self.profile = self.root/'owner.json'
        access = dict(self.manager.create_account(),pin=self.manager.pin,
                      endpoint={'host':'localhost','port':self.service.address[1]})
        write_private(self.root/'access.json',access)
        self.owner = HostingClient.enroll(self.root/'access.json',self.profile)
        (self.root/'local').mkdir(mode=0o700)
        self.desktop = DesktopSession(self.root/'local')
        self.addCleanup(self.desktop.close)

    def test_create_disconnect_resume_preserves_the_same_private_profile(self):
        from world.hosting_session import HostedWorldSession
        adapter = HostedWorldSession(self.desktop,self.profile)
        connected = adapter.create('Friends','Alice',request_id='one')
        self.assertEqual(self.desktop.remote_trainer,'Alice')
        self.assertEqual(connected['world']['name'],'Friends')
        self.assertEqual(self.desktop.state.name,connected['key'])
        self.assertFalse(connected['paths']['save'].exists())
        # A sentinel tests non-mutation only; never presented as a native save.
        connected['paths']['save'].write_bytes(b'private-save-preservation-sentinel')
        self.desktop.disconnect()
        returned = adapter.resume(connected['world']['id'])
        self.assertEqual(returned['paths'],connected['paths'])
        self.assertTrue(returned['paths']['save'].read_bytes()==b'private-save-preservation-sentinel')
        self.assertEqual(len(self.owner.list()),1)

    def test_friend_join_hands_off_to_independent_native_profile(self):
        from world.hosting_session import HostedWorldSession
        result = HostedWorldSession(self.desktop,self.profile).create('Friends','Alice',request_id='one')
        join_path = self.root/'friend.json'
        self.owner.invite(result['world']['id'],join_path,request_id='friend')
        (self.root/'guest').mkdir(mode=0o700)
        guest_desktop = DesktopSession(self.root/'guest')
        self.addCleanup(guest_desktop.close)
        guest = HostedWorldSession(guest_desktop).join(join_path,'Bob')
        self.assertEqual(guest['world']['id'],result['world']['id'])
        self.assertEqual(guest_desktop.remote_trainer,'Bob')
        self.assertNotEqual(guest['paths']['profile'],result['paths']['profile'])
        self.assertFalse(guest['paths']['save'].exists())
        self.assertEqual(guest_desktop.state.name,guest['key'])
        self.assertEqual(guest['paths']['config'].stat().st_mode&0o777,0o600)

    def test_connected_session_rejects_mutation_before_any_management_request(self):
        from world.hosting_session import HostedWorldSession
        adapter = HostedWorldSession(self.desktop,self.profile)
        first = adapter.create('Friends','Alice',request_id='one')
        with self.assertRaisesRegex(ValueError,'disconnect'):
            adapter.create('Unexpected','Bob',request_id='two')
        self.assertEqual(len(self.owner.list()),1)
        self.assertEqual(self.desktop.state.name,first['key'])


class HostingClientImportTests(unittest.TestCase):
    def test_https_client_does_not_import_linux_host_authority(self):
        import sys
        result = subprocess.run([sys.executable,'-c',
            "import sys;sys.modules['fcntl']=None;import world.hosting_client;"
            "assert 'world.hosting' not in sys.modules"],
            capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':
    unittest.main()
