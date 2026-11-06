"""Offline C tests for the carried battle header and sender checks.

Controller payload validation and real multiplayer are deliberately outside
this narrow fixture. Constants are extracted from the pinned donor header.
"""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
DONOR=Path(os.environ.get('BULK_DONOR',ROOT/'engines/expansion-native'))

def function(source,name):
 m=re.search(r'(?m)^static (?:u8|bool8) '+name+r'\([^;]*\)\n\{',source)
 if not m: raise AssertionError('missing '+name)
 depth=1; i=m.end()
 while depth:
  if source[i]=='{':depth+=1
  elif source[i]=='}':depth-=1
  i+=1
 return source[m.start():i]

@unittest.skipUnless((DONOR/'include/battle_controllers.h').exists(), "pinned donor checkout is not present")
class ExpansionBattleHeader(unittest.TestCase):
 def test_valid_and_invalid_headers_and_senders(self):
  header=(DONOR/'include/battle_controllers.h').read_text()
  start=header.rindex('enum {',0,header.index('B_COMM_TO_CONTROLLER'))
  end=header.index('};',start)+2; comm=header[start:end]
  source=(ROOT/'port/resolved/src/battle_controllers.c').read_text()
  start=source.index('enum\n{\n    LINK_BUFF_BUFFER_ID');end=source.index('};',start)+2; offsets=source[start:end]
  funcs='\n'.join(function(source,n) for n in ['NativeBattleMaster','NativeBattleOwner','NativeBattleSourceValid','NativeBattleHeaderValid'])
  c='''#include <stdint.h>\n#include <assert.h>\ntypedef uint8_t u8; typedef uint16_t u16; typedef int bool8;\n#define TRUE 1\n#define FALSE 0\n#define MAX_BATTLERS_COUNT 4\n#define BIT_SIDE 1\n#define BATTLE_TYPE_IS_MASTER 1\n#define BATTLE_TYPE_BATTLE_TOWER 2\nstatic unsigned gBattleTypeFlags=1; static int coop=0,local=0,players=2;\nstatic u8 GetMultiplayerId(void){return local;}\nstatic u8 GetLinkPlayerCount(void){return players;}\nstatic bool8 WorldCoop_IsBattle(void){return coop;}\nstatic bool8 NativeBattleCommandValid(const u8 *p,u16 n,u8 b){(void)p;(void)n;(void)b;return 1;}\n'''+comm+'\n'+offsets+'\n'+funcs+'''\nint main(void){\n u8 p[16]={0}; p[LINK_BUFF_SIZE_LO]=8; p[LINK_BUFF_ACTIVE_BATTLER]=1;\n p[LINK_BUFF_BUFFER_ID]=B_COMM_TO_ENGINE;\n assert(NativeBattleHeaderValid(p,16));\n assert(NativeBattleSourceValid(p,1)); assert(!NativeBattleSourceValid(p,0));\n p[LINK_BUFF_ACTIVE_BATTLER]=4; assert(!NativeBattleHeaderValid(p,16));\n p[LINK_BUFF_ACTIVE_BATTLER]=1; p[LINK_BUFF_SIZE_LO]=7; assert(!NativeBattleHeaderValid(p,16));\n p[LINK_BUFF_SIZE_LO]=8; p[LINK_BUFF_BUFFER_ID]=B_COMM_CONTROLLER_IS_DONE; p[LINK_BUFF_DATA]=1;\n assert(NativeBattleHeaderValid(p,16)); assert(NativeBattleSourceValid(p,1)); assert(!NativeBattleSourceValid(p,0));\n p[LINK_BUFF_DATA]=2; assert(!NativeBattleHeaderValid(p,16));\n p[LINK_BUFF_BUFFER_ID]=B_COMM_TO_ENGINE;p[LINK_BUFF_ACTIVE_BATTLER]=2;coop=1;\n assert(NativeBattleSourceValid(p,1)); assert(!NativeBattleSourceValid(p,0));\n players=3;assert(!NativeBattleSourceValid(p,1));return 0; }\n'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.c').write_text(c)
   result=subprocess.run(['cc','-std=c11','-fsanitize=undefined,address','-fno-omit-frame-pointer',str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
   result=subprocess.run([str(p/'test')],capture_output=True,text=True,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0'))
   self.assertEqual(result.returncode,0,result.stderr)
