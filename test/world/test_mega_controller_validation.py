"""Execute the production move reply guards and retained request layout."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[2]

class MegaControllerValidation(unittest.TestCase):
    def test_move_bit_survives_wire_but_requires_announced_permission(self):
        source = (ROOT / 'src/battle_controllers.c').read_text()
        start = source.index('    case CONTROLLER_TWORETURNVALUES:')
        end = source.index('    case CONTROLLER_DRAWPARTYSTATUSSUMMARY:', start)
        wire = source[start:end]
        start = source.index('        if (request[0] == CONTROLLER_CHOOSEMOVE)', source.index('static bool8 NativeBattleReplyValid'))
        end = source.index('        return request[0] == CONTROLLER_CHOOSEACTION', start)
        reply = source[start:end]
        program = r'''
#include <assert.h>
#include <stdint.h>
typedef uint8_t u8;
#define FALSE 0
#define TRUE 1
#define PORTABLE 1
#define CONTROLLER_TWORETURNVALUES 1
#define CONTROLLER_DRAWPARTYSTATUSSUMMARY 2
#define CONTROLLER_CHOOSEMOVE 3
#define B_COMM_TO_ENGINE 0
#define B_ACTION_UNK_14 14
#define B_ACTION_USE_MOVE 0
#define B_ACTION_EXEC_SCRIPT 10
#define MAX_MON_MOVES 4
#define MAX_BATTLERS_COUNT 4
#define MEGA_MOVE_CHOICE_BIT 128
int allowed,announcedSeen;
int MegaGame_ValidateMoveChoice(u8 b,u8 c,u8 t){(void)b;return (c&127)<4 && t<4 && (!(c&128)||allowed);}
int MegaGame_ReplyAllowed(u8 b,u8 announced){(void)b;announcedSeen=announced;return allowed && announced==1;}
int wireValid(u8 *data){int bufferId=0;switch(data[0]){
''' + wire + r'''
}return 1;}
int replyValid(u8 *data,u8 *request){u8 battler=0;
''' + reply + r'''
return 0;}
int main(void){u8 data[4]={1,10,128,1},request[4]={3,0,0,1};
 assert(wireValid(data));allowed=1;assert(replyValid(data,request));assert(announcedSeen==1);
 request[3]=0;assert(!replyValid(data,request));request[3]=1;
 allowed=0;assert(!replyValid(data,request));
 for(int c=0;c<256;c++){data[2]=c;assert(wireValid(data)==((c&127)<4));}
 data[2]=255;data[3]=255;assert(wireValid(data));assert(replyValid(data,request));
 data[2]=128;data[3]=4;assert(!wireValid(data));assert(!replyValid(data,request));
 data[2]=0;data[3]=1;assert(replyValid(data,request));return 0;}
'''
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)
            (path / 'test.c').write_text(program)
            result = subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(path/'test.c'),'-o',str(path/'test')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            result = subprocess.run([str(path/'test')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('sNativeBattleRequest[MAX_BATTLERS_COUNT][4]', source)

if __name__ == '__main__':
    unittest.main()
