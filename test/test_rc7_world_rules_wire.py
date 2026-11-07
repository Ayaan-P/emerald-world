"""Validate actual Expansion world-rule wire parser without sockets."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
ENGINE = Path(os.environ.get('EW_RC7_ENGINE', ROOT / 'engines/expansion-native'))
class WorldRulesWire(unittest.TestCase):
    def test_bounded_messages(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); (p/'gba').mkdir()
            (p/'gba/types.h').write_text('typedef unsigned char bool8;\n')
            (p/'global.h').write_text('#include "gba/types.h"\n#define TRUE 1\n#define FALSE 0\n')
            (p/'test.c').write_text(r'''
#include <assert.h>
#include "platform/world_rules_wire.h"
int main(void){
 unsigned r=99,e=99,s=99;
 char *good[]={"RULES","1","12","1","7"};
 assert(WorldRules_ParseWire(5,good,&r,&e,&s) && r==12 && e==1 && s==7);
 char *badseed[]={"RULES","1","0","1","21"}; assert(!WorldRules_ParseWire(5,badseed,&r,&e,&s));
 char *zero[]={"RULES","1","0","0","0"}; assert(!WorldRules_ParseWire(5,zero,&r,&e,&s));
 char *badbool[]={"RULES","1","0","2","1"}; assert(!WorldRules_ParseWire(5,badbool,&r,&e,&s));
 char *overflow[]={"RULES","1","2147483648","1","1"}; assert(!WorldRules_ParseWire(5,overflow,&r,&e,&s));
 char *sign[]={"RULES","1","-1","1","1"}; assert(!WorldRules_ParseWire(5,sign,&r,&e,&s));
 assert(!WorldRules_ParseWire(4,good,&r,&e,&s));
 assert(!WorldRules_ParseWire(5,good,0,&e,&s)); return 0;
}''')
            q=subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-DPORTABLE','-I'+str(p),'-I'+str(ENGINE/'include'),str(ENGINE/'src/world/world_rules_wire.c'),str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True)
            self.assertEqual(q.returncode,0,q.stderr)
            q=subprocess.run([str(p/'test')],capture_output=True,text=True)
            self.assertEqual(q.returncode,0,q.stderr)
