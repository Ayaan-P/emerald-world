"""Compile production native formatter/draw functions; stub only UI services."""
import os
from pathlib import Path
import re
import subprocess
from test_save_isolation import function

ROOT = Path(__file__).resolve().parents[2]
ENGINE = Path(os.environ.get('EW_RC7_ENGINE', ROOT / 'engines/expansion-native'))


def build(directory):
    chat = (ENGINE / 'src/world/world_chat.c').read_text()
    bridge = (ENGINE / 'src/world/world_bridge.c').read_text()
    message_match = re.search(r'struct ChatMessage \{[^}]+\};', bridge)
    if message_match is None:
        raise AssertionError('missing native ChatMessage definition')
    message = message_match.group()
    code = r'''
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
typedef void SDL_Renderer;
typedef struct {int x,y,w,h;} SDL_Rect;
#define WORLD_CHAT_HEIGHT 64
#define SDLK_t 0
static struct {int editing,objectives,campaign,watch,objectiveGameInput;unsigned scroll;char hint[96],draft[152];} sChat;
static char sGrassNotice[1];static unsigned sGrassNoticeUntil;
static const char *trainer;
int Input_KeyIsBound(int key){(void)key;return 0;}
int SDL_GetScancodeFromKey(int key){return key;}
unsigned SDL_GetTicks(void){return 0;}
void SDL_SetRenderDrawColor(SDL_Renderer *r,int a,int b,int c,int d){(void)r;(void)a;(void)b;(void)c;(void)d;}
void SDL_RenderFillRect(SDL_Renderer *r,SDL_Rect *s){(void)r;(void)s;}
void WorldApprentice_Tick(void){}
int WorldBridge_Enabled(void){return 1;}
int WorldBridge_ConnectionActive(void){return 1;}
const char *WorldBridge_ChatStatus(void){return "sent";}
const char *WorldBridge_TrainerName(void){return trainer;}
int WorldSupport_Active(void){return 0;}
int WorldSupport_Pending(void){return 0;}
int WorldFieldUI_Active(void){return 0;}
int WorldFieldUI_Enabled(void){return 0;}
int WorldFloorplan_Text(unsigned i,char *s,unsigned n){(void)i;(void)s;(void)n;return 0;}
void WorldSupport_Text(unsigned i,char *s,unsigned n){(void)i;(void)s;(void)n;}
void WorldFieldUI_Text(unsigned i,char *s,unsigned n){(void)i;(void)s;(void)n;}
void WorldBridge_WatchText(unsigned i,char *s,unsigned n){(void)i;(void)s;(void)n;}
void WorldCoreStory_CampaignText(unsigned i,char *s,unsigned n){(void)i;(void)s;(void)n;}
int WorldLight_Available(void){return 0;}
int WorldLight_Enabled(void){return 0;}
int WorldLight_Shining(void){return 0;}
int WorldRouteTrainers_Text(char *s,unsigned n){(void)s;(void)n;return 0;}
int WorldBerryCare_Text(char *s,unsigned n){(void)s;(void)n;return 0;}
/* Fixed glyph metrics isolate selection from font assets/SDL. Full 120-byte
 * authority replies fit the two captured rows; real wrapping remains in Draw. */
static unsigned Width(unsigned char c){(void)c;return 1;}
static void DrawText(SDL_Renderer *r,const char *s,int y){(void)r;if(y==12||y==24)printf("%s",s);}
'''
    code += message + '\nstatic struct {struct {unsigned chatCount;struct ChatMessage chat[16];} live;} sWorld;\n'
    for source, name in ((bridge, 'WorldBridge_ChatLine'), (bridge, 'WorldBridge_ChatCount'),
                         (chat, 'Identifier'), (chat, 'WorldChat_Draw')):
        code += function(source, name)
    code += r'''
int main(int argc,char **argv){
 if(argc<5 || (argc-2)%3 || (argc-2)/3>16)return 2;
 trainer=argv[1];sChat.objectives=1;
 for(int i=2;i<argc;i+=3){
  struct ChatMessage *m=&sWorld.live.chat[sWorld.live.chatCount++];
  snprintf(m->sender,sizeof(m->sender),"%s",argv[i]);
  snprintf(m->target,sizeof(m->target),"%s",argv[i+1]);
  snprintf(m->text,sizeof(m->text),"%s",argv[i+2]);
 }
 WorldChat_Draw(NULL);return 0;
}
'''
    source = directory / 'objectives.c'
    binary = directory / 'objectives'
    source.write_text(code)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', str(source), '-o', str(binary)],
                   check=True, capture_output=True, text=True)
    return binary


def render(binary, trainer, entries):
    args = [str(binary), trainer]
    for _, sender, target, encoded in entries:
        args.extend((sender, target, bytes.fromhex(encoded).decode('ascii')))
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout
