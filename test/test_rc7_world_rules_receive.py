"""Test production RC7 rule-message application in memory, without sockets."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from test.world.test_save_isolation import function
ROOT=Path(__file__).resolve().parents[1]
ENGINE=Path(os.environ.get('EW_RC7_ENGINE', ROOT/'engines/expansion-native'))
class RuleReceive(unittest.TestCase):
 def test_rule_applies_only_during_negotiation(self):
  bridge=(ENGINE/'src/world/world_bridge.c').read_text()
  code=r'''
#include <assert.h>
#include "platform/world_rules_wire.h"
#define TRUE 1
#define FALSE 0
static struct {bool8 rulesProbe,rulesPending;} sWorld;
static unsigned seen, seenEnabled, seenSeed;
void WildShuffle_SetWorldRule(int e,unsigned s){seen++;seenEnabled=e;seenSeed=s;}
'''+function(bridge,'HandleRulesLine')+r'''
int main(void){
 char *good[]={"RULES","1","4","1","7"};
 char *bad[]={"RULES","1","4","1","21"};
 assert(!HandleRulesLine(5,good));assert(!seen);
 sWorld.rulesProbe=TRUE;sWorld.rulesPending=TRUE;
 assert(!HandleRulesLine(5,bad));assert(sWorld.rulesPending && !seen);
 assert(HandleRulesLine(5,good));assert(!sWorld.rulesPending && seen==1 && seenEnabled==1 && seenSeed==7);
 assert(!HandleRulesLine(5,good));assert(seen==1);return 0;
}'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'gba').mkdir();(p/'gba/types.h').write_text('typedef unsigned char bool8;\n');(p/'global.h').write_text('#include "gba/types.h"\n#define TRUE 1\n#define FALSE 0\n');(p/'test.c').write_text(code)
   q=subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-DPORTABLE','-I'+str(p),'-I'+str(ENGINE/'include'),str(ENGINE/'src/world/world_rules_wire.c'),str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True)
   self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
