"""Compile the production RC7 HELLO formatter, with no socket transport."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from test.world.test_save_isolation import function
ROOT=Path(__file__).resolve().parents[1]
ENGINE=Path(os.environ.get('EW_RC7_ENGINE', ROOT/'engines/expansion-native'))
class RuleHello(unittest.TestCase):
 def test_probe_can_fall_back_to_legacy_role(self):
  source=(ENGINE/'src/world/world_bridge.c').read_text()
  code=r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef unsigned char bool8;
#define TRUE 1
#define FALSE 0
#define GENERATED_MAP_READY 0
#define WORLD_EXTENDED_OBJECTS 0
static struct { bool8 rulesProbe,rulesLegacy,rallyProbe,rallyLegacy,travelProbe,travelLegacy,chatProbe,chatLegacy; char trainer[25],token[65],output[4096];int outputSize; } sWorld;
'''+function(source,'RulesProbeRejected')+function(source,'QueueHello')+r'''
int main(void){
 strcpy(sWorld.trainer,"alice");strcpy(sWorld.token,"token");
 QueueHello(0);assert(sWorld.rulesProbe);assert(strstr(sWorld.output,"SOCIALTRAVELCHATRALLYRULES1\n"));
 char *other[]={"ERROR","RULES_REQUIRED"};assert(!RulesProbeRejected(2,other));
 char *legacy[]={"ERROR","AUTH"};assert(RulesProbeRejected(2,legacy)); QueueHello(0);assert(!sWorld.rulesProbe);
 assert(strstr(sWorld.output,"SOCIALTRAVELCHATRALLY\n"));assert(!strstr(sWorld.output,"RULES1"));
 return 0;
}'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.c').write_text(code)
   q=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True)
   self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],capture_output=True,text=True)
   self.assertEqual(q.returncode,0,q.stderr)
