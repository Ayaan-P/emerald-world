"""Exercise the real native chat submission gate, without SDL or sockets."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]

class GuildChatGate(unittest.TestCase):
 def test_private_commands_never_fall_back_to_old_public_chat(self):
  source=(ROOT/'src/platform/world_chat.c').read_text()
  start=source.index('static int Identifier(');end=source.index('\nint WorldChat_Event(',start)
  funcs=source[start:end]
  pre=r'''
#include <stdio.h>
#include <string.h>
#include <assert.h>
static struct {int editing,releaseKeys;unsigned scroll;char draft[152],hint[96];} sChat;
static const char *history[16];static unsigned count,sent;static char sentText[152],sentTarget[25];
#define WORLD_CHAT_HEIGHT 64
#define SDL_TEXTINPUT 1
int WorldBridge_Enabled(void){return 1;}
void SDL_FlushEvent(int kind){(void)kind;}
void SDL_StartTextInput(void){}
const char *WorldBridge_TrainerName(void){return "Alice";}
unsigned WorldBridge_ChatCount(void){return count;}
void WorldBridge_ChatLine(unsigned i,char *out,unsigned size){snprintf(out,size,"%s",history[i]);}
int WorldBridge_ChatSend(const char *target,const char *text){sent++;strcpy(sentText,text);strcpy(sentTarget,target);return 1;}
void SDL_StopTextInput(void){}
'''
  main=r'''
int main(void){
 assert(WorldChat_OpenGuild()==1);assert(sChat.editing==1);assert(!strcmp(sChat.draft,"/guild help"));
 assert(WorldChat_OpenGuild()==0);sChat.editing=0;
 assert(WorldChat_OpenTradeBoard()==1);assert(!strcmp(sChat.draft,"/trade help"));sChat.editing=0;
 strcpy(sChat.draft,"/trade contact 123");Submit();assert(sent==0);
 strcpy(sChat.draft,"/trade help");Submit();assert(sent==1);assert(!strcmp(sentText,"/trade help"));
 history[0]="Alice > Alice: Trade: protocol 1";count=1;
 strcpy(sChat.draft,"/g secret plans");Submit();assert(sent==1);
 strcpy(sChat.draft,"/trade contact 123");Submit();assert(sent==2);count=0;sent=0;
 strcpy(sChat.draft,"/g secret plans");Submit();assert(sent==0);assert(strstr(sChat.hint,"/guild help"));
 strcpy(sChat.draft,"/guild post secret plans");Submit();assert(sent==0);
 history[0]="Mallory > Alice: Guild: protocol 1";count=1;
 strcpy(sChat.draft,"/g secret plans");Submit();assert(sent==0);
 strcpy(sChat.draft,"/guild help");Submit();assert(sent==1);assert(!strcmp(sentText,"/guild help"));
 history[1]="Alice > Alice: Guild: protocol 1";count=2;
 strcpy(sChat.draft,"/trade contact 123");Submit();assert(sent==1);
 strcpy(sChat.draft,"/g secret plans");Submit();assert(sent==2);assert(!strcmp(sentText,"/g secret plans"));
 count=0;strcpy(sChat.draft,"/w Bob hello");Submit();assert(sent==3);assert(!strcmp(sentTarget,"Bob"));
 strcpy(sChat.draft,"normal chat");Submit();assert(sent==4);assert(!strcmp(sentTarget,"*"));
 return 0;
}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'gate.c').write_text(pre+funcs+main)
   build=subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror',str(p/'gate.c'),'-o',str(p/'gate')],capture_output=True,text=True)
   self.assertEqual(build.returncode,0,build.stderr)
   run=subprocess.run([str(p/'gate')],capture_output=True,text=True)
   self.assertEqual(run.returncode,0,run.stderr)
if __name__=='__main__':unittest.main()
