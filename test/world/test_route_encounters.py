"""Real immutable XL wildlife bytes, negotiation, history and persistence."""
from copy import deepcopy
import json
import os, subprocess, tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import test_world_memory as fixtures
from test_route_journeys import plan as journey
from test_author_cave import wire
from world import author_routes
from world.route_landscape import compile_plan
from world.shared_cave import SharedCave
from world.route_characters import bind_landmarks
from test_character_chapters import plan as character_plan


def plan():
    p=journey()
    p['encounters']=dict(rate=12,wildlife=[dict(species=name,level=level) for name,level in
        [('ZUBAT',8),('ZUBAT',9),('GEODUDE',8),('GEODUDE',10),('ROGGENROLA',9),('WOOBAT',10),
         ('NOIBAT',12),('CARBINK',12),('SABLEYE',13),('SABLEYE',14),('AXEW',14),('DEINO',15)]])
    return p

class RouteEncounterTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.WorldMemoryTests();self.f.setUp();self.addCleanup(self.f.tearDown)
        self.s=self.f.server

    def send(self,c,line):
        c['out'].clear();self.s._line(c,line.encode());self.assertFalse(c['closing'],c['out'])
        return c['out'].decode()

    def connect(self,name,cap):
        token=self.s.create_identity(name)['token']
        c=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
        self.assertIn('WELCOME',self.send(c,f'HELLO 1 {name} {token} SOCIAL{cap}'))
        return c

    def test_population_changes_identity_not_geometry_and_uses_real_slot_weights(self):
        p=plan();blob,report=compile_plan(p);cave=SharedCave(blob)
        self.assertEqual((cave.version,cave.side,cave.cohort),(17,127,'expansion-native'))
        self.assertEqual(sum(x['slot_percent'] for x in report['encounter_population']),100)
        self.assertEqual(cave.wildlife[0],12)
        self.assertEqual(len(blob),16174)
        changed=deepcopy(p);changed['encounters']['wildlife'][-1]['level']=16
        other,_=compile_plan(changed)
        self.assertNotEqual(SharedCave(other).identity,cave.identity)
        self.assertEqual(other[45:],blob[45:])
        self.assertIn('XLWILDLIFE',cave.frames())
        self.assertIn('CAVE WILD '+cave.identity,cave.frames())
        for offset,value in ((8,0),(11,101),(9,0)):
            bad=bytearray(blob);bad[offset]=value
            if offset==9:bad[10]=0
            with self.assertRaises(ValueError):SharedCave(bytes(bad))
        from world.frontier_outposts import compile_outpost
        with self.assertRaises(ValueError):compile_outpost(blob,{})
        p['encounters']['wildlife'][0]['species']='NOT_A_SPECIES'
        with self.assertRaises(ValueError):compile_plan(p)

    def test_old_client_refuses_table_new_client_acknowledges_and_restart_preserves_it(self):
        blob,report=compile_plan(plan());revision=self.s._replace_cave(blob,label='Echoing Sanctuary')
        old=self.connect('Old','CAVE16');new=self.connect('New','CAVE17')
        self.assertEqual(self.send(old,'CAVE GET'),'CAVE NONE\n')
        self.assertEqual(self.send(new,'CAVE GET'),SharedCave(blob).frames())
        self.assertIn('CAVE OK',self.send(new,'CAVE ACK '+revision))
        g,n=self.s.wilds_map
        self.send(new,f'STATE 1 {g} {n} 20 20 4 7 1 '+'a'*16+' '+'b'*16)
        self.assertEqual(self.s._region_scope(new),revision)
        self.assertEqual(self.s.landmark_survey.register(plan())['revision'],revision)
        self.s.landmark_survey.handle(new,'/explore start')
        p=character_plan();p['chapters']=[p['chapters'][0]]
        obj=bind_landmarks(p,blob,report,{'arrival':'camp'})['chapters'][0]['object']
        self.assertEqual(obj['region_revision'],revision)
        self.s.close();self.f.server=self.f.open();self.s=self.f.server
        saved=self.s.memory.inspect_saved_place(self.s,revision)
        self.assertEqual(saved['encounters']['rate'],12)
        self.assertEqual(sum(p['slot_percent'] for p in saved['encounters']['population']),100)
        self.assertNotIn('New',json.dumps(saved['encounters']))
        self.assertEqual(self.s.shared_cave.wildlife,SharedCave(blob).wildlife)
        self.assertEqual(self.s.shared_cave.frames(),SharedCave(blob).frames())

    @unittest.skipUnless(os.environ.get('EW_NATIVE_SOURCE'),'set EW_NATIVE_SOURCE to CAVE17 Expansion source')
    def test_actual_native_decoder_binds_authored_population_and_routes(self):
        engine=Path(os.environ['EW_NATIVE_SOURCE'])
        source=(engine/'src/world/world_cave_wire.c').read_text().replace('#include "global.h"','')
        code=r'''#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef int bool8;
#define TRUE 1
#define FALSE 0
#define PORTABLE 1
#define GENERATED_WORLD_XL 1
#define GENERATED_CAVE_WILDLIFE 1
#define GENERATED_MAP_LARGE 1
#define GENERATED_CAVE_PROFILES 1
'''+source+r'''
int main(void){struct WorldCaveWire w={0};char line[512];int r=0;while(fgets(line,sizeof(line),stdin)){char *t[8],*p;unsigned n=0;line[strcspn(line,"\r\n")]=0;for(p=strtok(line," ");p;p=strtok(NULL," ")){if(n==8)return 3;t[n++]=p;}r=WorldCaveWire_Feed(&w,n,(const char*const*)t);if(r<0)return 2;}return r==1&&w.version==17&&w.nextRow==127&&w.wildlife[0]==12?0:4;}'''
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'codec.c').write_text(code)
            subprocess.run(['cc','-std=gnu99','-Wall','-Wextra','-Werror','-iquote',str(engine/'include'),str(root/'codec.c'),'-o',str(root/'codec')],check=True,capture_output=True)
            blob,_=compile_plan(plan());frames=SharedCave(blob).frames()
            run=lambda text:subprocess.run([str(root/'codec')],input=text,text=True,capture_output=True).returncode
            self.assertEqual(run(frames),0)
            lines=frames.splitlines();words=lines[1].split();words[-1]='0d'+words[-1][2:];lines[1]=' '.join(words)
            self.assertNotEqual(run('\n'.join(lines)+'\n'),0)
            lines=frames.splitlines();self.assertNotEqual(run('\n'.join([lines[0]]+lines[2:])+'\n'),0)

    def test_explicit_author_mode_publishes_history_bound_population(self):
        from test_shared_generated_cave import BLOB
        self.s._replace_cave(BLOB,label='Old Sanctuary')
        seq=self.s.memory.history()['events'][-1]['seq']
        def transport(_socket,request,**kw):return self.f.admin(request)
        def provider(prompt,validate,**kw):
            self.assertIn('area_activated',prompt)
            self.assertIn('DEINO',prompt)
            return validate(wire(plan()))
        with patch('world.client.admin_request',side_effect=transport), \
             patch('world.publish_cave.admin_request',side_effect=transport), \
             patch('world.author_cave.request_validated',side_effect=provider):
            self.assertEqual(author_routes.main(['Echoing cave wildlife among sanctuary routes','--encounters',
                '--activate-shared','admin','--label','Echoing Sanctuary']),0)
        self.assertEqual(self.s.shared_cave.version,17)
        self.assertIn(seq,self.s.memory.history()['events'][-1]['history_evidence'])
        with patch('world.author_cave.request_validated',side_effect=lambda p,v,**kw:v(wire(plan()))):
            with self.assertRaises(ValueError):author_routes.author('Geometry only')

if __name__=='__main__':unittest.main()
