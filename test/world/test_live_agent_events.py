"""Owner-only, per-trainer event-state control without any sockets."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_large_generated_cave import DOC
from test_shared_generated_cave import MemoryAuthority
from world import wilds_events,agent_event_control
from world.shared_cave import SharedCave

class LiveAgentEvents(unittest.TestCase):
    def test_admin_targeting_admission_and_queued_semantics(self):
        blob=wilds_events.compile_document({'blueprint':DOC,'cast':[{'gfx':7,'text':'Hello!'}], 'events':{'initial':0,'rules':[{'state':0,'npc':1,'next':1,'text':'Hello!'}]}});identity=SharedCave(blob).identity
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);server=MemoryAuthority(p/'socket',p/'world',cave_template=blob)
            try:
                def connect(name):
                    ident=server.create_identity(name);c={'id':None,'out':bytearray(),'closing':False,'state':None,'seq':0,'sock':object()}
                    server._line(c,('HELLO 1 %s %s SOCIALTRAVELCHATRALLYCAVE9'%(name,ident['token'])).encode());c['out'].clear()
                    server._line(c,b'CAVE GET');c['out'].clear();server._line(c,('CAVE ACK '+identity).encode());c['out'].clear()
                    g,n=server.wilds_map;server._line(c,(f'STATE 1 {g} {n} 1 1 1 7 1 '+('a'*16)+' '+('b'*16)).encode());c['out'].clear();return c
                alice=connect('Alice');bob=connect('Bob')
                def admin_request(_socket,request,**kwargs):
                    self.assertEqual(kwargs['admin_path'],p/'owner.sock');c={'id':None,'out':bytearray(),'closing':False,'sock':object()}
                    server._admin_line(c,json.dumps(request).encode());return json.loads(c['out'])
                with patch('world.agent_event_control.admin_request',side_effect=admin_request):
                    result=agent_event_control.set_state(p/'owner.sock','Alice',identity,5)
                    self.assertTrue(result['ok']);self.assertTrue(result['queued']);self.assertEqual(result['sequence'],1);session=result['session']
                    self.assertEqual(alice['out'],f'CAVE EVENTSET {identity} 1 5\n'.encode());self.assertEqual(bob['out'],b'')
                    self.assertEqual(agent_event_control.status(p/'owner.sock','Alice',identity,session,1)['status'],'queued')
                    server._line(bob,f'CAVE EVENTACK {identity} 1 APPLIED'.encode());self.assertEqual(agent_event_control.status(p/'owner.sock','Alice',identity,session,1)['status'],'queued')
                    server._line(alice,f'CAVE EVENTACK {identity} 1 APPLIED'.encode())
                    self.assertEqual(agent_event_control.status(p/'owner.sock','Alice',identity,session,1)['status'],'applied')
                    server._line(alice,f'CAVE EVENTACK {identity} 1 REJECTED'.encode());self.assertEqual(agent_event_control.status(p/'owner.sock','Alice',identity,session,1)['status'],'applied')
                    self.assertEqual(agent_event_control.status(p/'owner.sock','Bob',identity,session,1)['status'],'unknown')
                    alice['out'].clear();patched=agent_event_control.set_rule(p/'owner.sock','Alice',identity,5,1,6,'Hello!')
                    self.assertTrue(patched['ok']);self.assertEqual(patched['sequence'],2)
                    self.assertEqual(alice['out'],f'CAVE EVENTRULE {identity} 2 5 1 6 48656c6c6f21\n'.encode());self.assertEqual(bob['out'],b'')
                    server._line(alice,f'CAVE EVENTACK {identity} 2 REJECTED'.encode())
                    self.assertEqual(agent_event_control.status(p/'owner.sock','Alice',identity,session,2)['status'],'rejected')
                    self.assertEqual(agent_event_control.status(p/'owner.sock','Alice',identity,'0'*16,2)['status'],'unknown')
                    self.assertEqual(agent_event_control.status(p/'owner.sock','Alice','f'*64,session,2)['status'],'unknown')
                    alice['out'].clear();tile=agent_event_control.set_tile(p/'owner.sock','Alice',identity,1,2,'grass')
                    self.assertTrue(tile['ok']);self.assertEqual(tile['sequence'],3)
                    self.assertEqual(alice['out'],f'CAVE EVENTTILE {identity} 3 1 2 0\n'.encode());self.assertEqual(bob['out'],b'')
                    server._line(alice,f'CAVE EVENTACK {identity} 3 APPLIED'.encode());self.assertEqual(agent_event_control.status(p/'owner.sock','Alice',identity,session,3)['status'],'applied')
                    alice['out'].clear();terrainPatch=[{'x':1,'y':2,'terrain':'grass'},{'x':2,'y':2,'terrain':'tall_grass'}]
                    result=agent_event_control.set_tiles(p/'owner.sock','Alice',identity,terrainPatch);self.assertTrue(result['ok']);self.assertEqual(result['sequence'],4)
                    self.assertEqual(alice['out'],f'CAVE EVENTTILES {identity} 4 02010200020201\n'.encode());self.assertEqual(bob['out'],b'')
                    for bad in ([],terrainPatch+[terrainPatch[0]],[terrainPatch[0],{'x':1,'y':1,'terrain':'grass'}],[terrainPatch[0]]*65):
                        alice['out'].clear();self.assertFalse(agent_event_control.set_tiles(p/'owner.sock','Alice',identity,bad)['ok']);self.assertEqual(alice['out'],b'')

                    for x,y,terrain in ((1,1,'grass'),(2,1,'grass'),(61,61,'grass'),(0,0,'grass'),(1,2,'lava'),(True,2,'grass')):
                        self.assertFalse(agent_event_control.set_tile(p/'owner.sock','Alice',identity,x,y,terrain)['ok'])

                    for npc,text in ((2,'Hello!'),(1,'bad\x01'),(1,'x'*29)):
                        self.assertFalse(agent_event_control.set_rule(p/'owner.sock','Alice',identity,5,npc,6,text)['ok'])

                    for name,ident,state in [('Bob','f'*64,1),('Nobody',identity,1),('Alice',identity,16),('Alice',identity,True)]:
                        self.assertFalse(agent_event_control.set_state(p/'owner.sock',name,ident,state)['ok'])
                    alice['out'].clear();alice['in_generated_cave']=False
                    self.assertFalse(agent_event_control.set_state(p/'owner.sock','Alice',identity,2)['ok']);self.assertEqual(alice['out'],b'')
                    server.peers.pop('Alice');self.assertEqual(agent_event_control.status(p/'owner.sock','Alice',identity,session,2)['status'],'unknown')
                # Ordinary authenticated trainers do not get the owner command path.
                server._line(bob,f'CAVE EVENTSET {identity} 1 3'.encode());self.assertTrue(bob['closing'])
            finally:server.close()
    def test_cli_routes_tile_state_and_status(self):
        with patch('world.agent_event_control.admin_request',return_value={'ok':True}) as send,patch('builtins.print'):
            common=['--admin-socket','/tmp/owner','--trainer','Alice','--area','a'*64]
            self.assertEqual(agent_event_control.main(common+['--x','3','--y','4','--terrain','grass']),0)
            self.assertEqual(send.call_args.args[1]['command'],'set_event_tile')
            with tempfile.TemporaryDirectory() as t:
                f=Path(t)/'tiles.json';f.write_text('[{"x":3,"y":4,"terrain":"grass"}]')
                self.assertEqual(agent_event_control.main(common+['--tiles-file',str(f)]),0)
                self.assertEqual(send.call_args.args[1]['command'],'set_event_tiles')
            self.assertEqual(agent_event_control.main(common+['--state','2']),0)
            self.assertEqual(send.call_args.args[1]['command'],'set_event_state')
            self.assertEqual(agent_event_control.main(common+['--status','1','--session','b'*16]),0)
            self.assertEqual(send.call_args.args[1]['command'],'event_command_status')
            with patch('sys.stderr'),self.assertRaises(SystemExit):agent_event_control.main(common+['--x','3','--terrain','grass'])
