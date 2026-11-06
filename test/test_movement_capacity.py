"""Exercise the actual movement state helpers at the expanded native capacity.

This isolates state logic from the game engine; it is not a gameplay test.
"""
from pathlib import Path
import re
import os
import subprocess
import tempfile
import unittest

SOURCE=Path(__file__).resolve().parents[1]/'port/resolved/src/script_movement.c'

def function(source, name):
    m=re.search(r'(?m)^(?:static )?(?:u8|bool8|bool32|void) '+name+r'\([^;]*\)\n\{',source)
    if not m:
        raise AssertionError('missing function '+name)
    depth=1; i=m.end()
    while depth:
        if source[i]=='{':depth+=1
        elif source[i]=='}':depth-=1
        i+=1
    return source[m.start():i]

class MovementCapacity(unittest.TestCase):
 def test_high_slots_and_completion(self):
  source=SOURCE.read_text()
  names=['GetMovementScriptIdFromObjectEventId','ClearMovementScriptFinished',
         'SetMovementScriptFinished','IsMovementScriptFinished','ScriptMovement_IsAllObjectMovementFinished']
  funcs='\n'.join(function(source,n) for n in names)
  c='''#include <stdint.h>\n#include <assert.h>\n#define PORTABLE 1\n#define WORLD_EXTENDED_OBJECTS 1\n#define OBJECT_EVENTS_COUNT 48\n#define TASK_NONE 255\n#define TRUE 1\n#define FALSE 0\ntypedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef uint64_t u64;\ntypedef int bool8; typedef int bool32;\nstruct Task { short data[16]; }; static struct Task gTasks[1];\nstatic u8 sWorldMovementObjectIds[OBJECT_EVENTS_COUNT];\nstatic u64 sWorldMovementFinished;\nstatic u8 GetMoveObjectsTaskId(void) { return 0; }\n'''+funcs+'''\nint main(void) {\n for (int i=0;i<48;i++) sWorldMovementObjectIds[i]=255;\n sWorldMovementObjectIds[47]=42;\n assert(GetMovementScriptIdFromObjectEventId(0,42)==47);\n assert(!ScriptMovement_IsAllObjectMovementFinished());\n SetMovementScriptFinished(0,47); assert(IsMovementScriptFinished(0,47));\n assert(ScriptMovement_IsAllObjectMovementFinished());\n ClearMovementScriptFinished(0,47); assert(!IsMovementScriptFinished(0,47));\n assert(!ScriptMovement_IsAllObjectMovementFinished());\n return 0; }\n'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d); (p/'test.c').write_text(c)
   subprocess.run(['cc','-std=c11','-fsanitize=undefined,address','-fno-omit-frame-pointer',str(p/'test.c'),'-o',str(p/'test')],check=True,capture_output=True)
   subprocess.run([str(p/'test')],check=True,env=dict(os.environ, ASAN_OPTIONS='detect_leaks=0'))
