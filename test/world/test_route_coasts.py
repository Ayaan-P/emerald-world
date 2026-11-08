"""Player-visible coastal geometry in the existing shared native XL format."""
import unittest
import os, subprocess, tempfile
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
from test_route_landscape import plan
from test_author_cave import wire
from world.route_landscape import compile_plan
from world.shared_cave import SharedCave
from world.author_routes import author

class RouteCoasts(unittest.TestCase):
    def test_forms_and_rotations_change_real_geometry_without_losing_landmarks(self):
        revisions=set()
        for form in ('lagoon','cove','headland'):
            for facing in ('east','south','west','north'):
                p=plan();p['loops']=0
                p['landmarks'][0].update(radius=10,landform=form,facing=facing)
                blob,report=compile_plan(p);cave=SharedCave(blob)
                self.assertEqual(cave.version,16)
                self.assertEqual((blob,report),compile_plan(p))
                revisions.add(cave.identity)
                self.assertGreater(len(report['protected_coastal_water']),0)
                for x,y in report['protected_coastal_water']:
                    self.assertFalse(cave.walkable(x,y))
                for site in p['landmarks']:self.assertTrue(cave.walkable(site['x'],site['y']))
                for route in report['routes']:
                    self.assertFalse(set(map(tuple,route['path'])) & set(map(tuple,report['protected_coastal_water'])))
        self.assertEqual(len(revisions),12)

    def test_lagoon_requires_a_real_shore_detour(self):
        p=plan();p['loops']=0;p['landmarks'][0].update(radius=10,landform='lagoon')
        blob,report=compile_plan(p);cave=SharedCave(blob)
        self.assertFalse(cave.walkable(20,20)) # actual water pool east of camp center
        self.assertTrue(cave.walkable(15,20))
        self.assertTrue(cave.walkable(24,20))
        self.assertTrue(cave.walkable(20,24)) # shore remains connected around pool
        with patch('world.author_cave.request_validated',side_effect=lambda prompt,validate,**kw:validate(wire(p))) as provider:
            authored,_=author('A sheltered lagoon camp and contrasting headlands')
        self.assertEqual(authored,blob)
        self.assertIn('lagoon',provider.call_args.args[0])

    @unittest.skipUnless(os.environ.get('EW_NATIVE_SOURCE'),'set EW_NATIVE_SOURCE to verified Expansion source')
    def test_actual_native_codec_accepts_coasts_and_rejects_corruption(self):
        engine=Path(os.environ['EW_NATIVE_SOURCE'])
        code=r'''#include <stdio.h>
#include <string.h>
#include "global.h"
#include "platform/world_cave_wire.h"
int main(void){struct WorldCaveWire w={0};char line[512],*parts[5],*p,*save;int r=0;while(fgets(line,sizeof(line),stdin)){unsigned n=0;line[strcspn(line,"\n")]=0;for(p=strtok_r(line," ",&save);p&&n<5;p=strtok_r(NULL," ",&save))parts[n++]=p;r=WorldCaveWire_Feed(&w,n,(const char *const*)parts);if(r<0)return 2;}return r==1&&w.version==16&&w.nextRow==127?0:3;}'''
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'global.h').write_text('#include <stdint.h>\ntypedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef int bool8;\n#define TRUE 1\n#define FALSE 0\n')
            (root/'codec.c').write_text(code)
            subprocess.run(['cc','-std=gnu99','-Wall','-Wextra','-Werror','-DPORTABLE','-DGENERATED_WORLD_XL=1',
                '-iquote',str(root),'-iquote',str(engine/'include'),str(engine/'src/world/world_cave_wire.c'),str(root/'codec.c'),'-o',str(root/'codec')],check=True,capture_output=True)
            for form in ('lagoon','cove','headland'):
                p=plan();p['loops']=0;p['landmarks'][0].update(radius=10,landform=form)
                blob,_=compile_plan(p);frames=SharedCave(blob).frames()
                run=lambda value:subprocess.run([str(root/'codec')],input=value,text=True,capture_output=True).returncode
                self.assertEqual(run(frames),0)
                lines=frames.splitlines();parts=lines[21].split();row=parts[-1];parts[-1]=row[:15]+('#' if row[15]=='.' else '.')+row[16:];lines[21]=' '.join(parts)
                self.assertNotEqual(run('\n'.join(lines)+'\n'),0)

    def test_overlap_and_small_forms_are_rejected(self):
        p=plan();p['landmarks'][0].update(landform='cove',radius=3)
        with self.assertRaises(ValueError):compile_plan(p)
        p=plan();p['landmarks'][0]['landform']='mountain'
        with self.assertRaises(ValueError):compile_plan(p)
        p=plan();p['landmarks'][1]=dict(id='overlap',x=20,y=20,radius=6,landform='lagoon')
        with self.assertRaises(ValueError):compile_plan(p)

if __name__=='__main__':unittest.main()
