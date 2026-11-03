"""Real socket coverage for opt-in room and direct human chat."""
from pathlib import Path
import os
import socket
import tempfile

import unittest

from world.server import WorldServer


class ChatTests(unittest.TestCase):
    def test_room_and_direct_chat_reach_unready_battle_trainers_only_when_opted_in(self):
        with tempfile.TemporaryDirectory(prefix='emerald-chat-') as tmp:
            server = WorldServer(tmp+'/sock', tmp+'/state')
            identities = {n: server.create_identity(n) for n in ('alice', 'bob', 'carol', 'legacy')}
            server.start()
            sockets = []
            try:
                streams = {}
                for name, identity in identities.items():
                    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    sock.settimeout(2)
                    sock.connect(tmp+'/sock')
                    sockets.append(sock)
                    role = 'SOCIAL'
                    sock.sendall(f"HELLO 1 {name} {identity['token']} {role}\n".encode())
                    stream = sock.makefile('rb')
                    self.addCleanup(stream.close)
                    self.assertTrue(stream.readline().startswith(b'WELCOME 1 '+name.encode()+b' '))
                    if name != 'legacy':
                        sock.sendall(b'CHAT_ENABLE\n')
                    streams[name] = (sock, stream)
                alice = streams['alice'][0]
                # No field-ready state is necessary. Chat must work during battle.
                text = 'Use Thunderbolt! <&> 100%'
                alice.sendall(f'CHAT 1 * {text.encode().hex()}\n'.encode())
                def until(name, needle):
                    stream = streams[name][1]
                    for _ in range(80):
                        line = stream.readline().decode().strip()
                        if needle in line:
                            return line
                    self.fail('chat not delivered to '+name)
                for name in ('alice', 'bob', 'carol'):
                    self.assertEqual(until(name, 'CHATMSG '), f'CHATMSG 1 alice * {text.encode().hex()}')
                alice.sendall(b'CHAT 2 bob 70726976617465\n')
                self.assertEqual(until('bob', 'CHATMSG 2'), 'CHATMSG 2 alice bob 70726976617465')
                with server.lock:
                    self.assertNotIn('70726976617465', server._snapshot(server.peers['carol']))
                    self.assertNotIn('CHAT', server._snapshot(server.peers['legacy']))
                    self.assertEqual(server.db.execute("SELECT count(*) FROM events WHERE kind='chat'").fetchone()[0], 0)
                self.assertFalse(any(Path(tmp+'/state/trainers').rglob('*.sav')))
                # A burst has bounded memory and does not disconnect presence.
                for seq in range(3, 12):
                    alice.sendall(f'CHAT {seq} * 6275727374\n'.encode())
                until('alice', 'CHATSTATUS slow')
                with server.lock:
                    self.assertLessEqual(len(server.peers['alice']['chat_history']), 16)
                    self.assertIn('bob', server.peers)
                # A malformed wire line must not be normalized into valid chat.
                alice.sendall(b'CHAT\t12 * 61\n')
                until('alice', 'ERROR MALFORMED')
            finally:
                for sock in sockets:
                    sock.close()
                server.close()


class NativeChatTests(unittest.TestCase):
    def test_native_composer_uses_text_events_without_pausing_battle_frames(self):
        import subprocess
        root = Path(__file__).resolve().parents[2]
        ui = root/'src/platform/world_chat.c'
        self.assertTrue(ui.exists(), 'native SDL chat composer is missing')
        sysroot = root.parent/'emerald-world-research/deps/sysroot'
        source = r'''#include <assert.h>
#include <string.h>
#include <SDL2/SDL.h>
#include "platform/world_bridge.h"
#include "platform/world_chat.h"
#include "platform/settings.h"
static int enabled=1, sent;
static char recipient[25], message[121];
bool8 WorldBridge_Enabled(void) {return enabled;}
int WorldBridge_ChatSend(const char *target,const char *text) {
 strcpy(recipient,target);strcpy(message,text);sent++;return 1;
}
unsigned WorldBridge_ChatCount(void) {return 1;}
const char *WorldBridge_ChatStatus(void) {return "ready";}
void WorldBridge_ChatLine(unsigned i,char *out,unsigned size) {(void)i;(void)size;strcpy(out,"A");}
const unsigned short gFontSmallLatinGlyphs[256*32]={[0xBB*32]=0x4000};
const unsigned char gFontSmallLatinGlyphWidths[256]={[0xBB]=6};
static void key(int sym) {
 SDL_Event e={0};e.type=SDL_KEYDOWN;e.key.keysym.sym=sym;
 assert(WorldChat_Event(&e));
}
static void text(const char *s) {
 SDL_Event e={0};e.type=SDL_TEXTINPUT;strcpy(e.text.text,s);
 assert(WorldChat_Event(&e));
}
int main(int argc,char **argv) {
 assert(argc==2);
 assert(SDL_Init(SDL_INIT_VIDEO)==0);
 LoadSettings(NULL);
 SDL_Event ordinary={0};ordinary.type=SDL_KEYDOWN;ordinary.key.keysym.sym=SDLK_RETURN;
 assert(!WorldChat_Event(&ordinary)); /* Return remains Emerald's Start key. */
 SDL_Event opening={0};opening.type=SDL_TEXTINPUT;strcpy(opening.text.text,"t");
 assert(SDL_PushEvent(&opening)==1);
 key(SDLK_t);assert(WorldChat_BlocksInput());
 assert(SDL_PeepEvents(&opening,1,SDL_PEEKEVENT,SDL_TEXTINPUT,SDL_TEXTINPUT)==0);
 text("Hello, battle friends!");key(SDLK_RETURN);
 assert(sent==1 && !strcmp(recipient,"*") && !strcmp(message,"Hello, battle friends!"));
 key(SDLK_t);text("/w bob Use Surf!");key(SDLK_RETURN);
 assert(sent==2 && !strcmp(recipient,"bob") && !strcmp(message,"Use Surf!"));
 key(SDLK_t);text("do not send");key(SDLK_ESCAPE);assert(sent==2);
 key(SDLK_t);text("/w bad!id no");key(SDLK_RETURN);assert(sent==2);
 assert(WorldChat_BlocksInput());key(SDLK_ESCAPE);
 key(SDLK_t);text("caf\xc3\xa9");key(SDLK_RETURN);assert(sent==2);
 key(SDLK_ESCAPE);
 LoadSettings(argv[1]);
 Input_ReleaseTestInputs();assert(Input_PressTestInput("key:T"));
 assert(Input_GetTestButtons()==8);
 ordinary.key.keysym.sym=SDLK_t;ordinary.key.keysym.scancode=SDL_SCANCODE_T;
 int consumed=WorldChat_Event(&ordinary);
 int blocked=WorldChat_BlocksInput();
 unsigned delivered=blocked ? 0 : Input_GetTestButtons();
 printf("key_start=T: binding=%u consumed=%d blocks=%d delivered=%u\n",Input_GetTestButtons(),consumed,blocked,delivered);
 fflush(stdout);
 assert(!consumed && !blocked && delivered==8);
 ordinary.key.keysym.mod=KMOD_LCTRL;
 assert(SDL_PushEvent(&opening)==1);
 assert(WorldChat_Event(&ordinary));assert(WorldChat_BlocksInput());
 assert(SDL_PeepEvents(&opening,1,SDL_PEEKEVENT,SDL_TEXTINPUT,SDL_TEXTINPUT)==0);
 text("/w bob Remapped private reply");key(SDLK_RETURN);
 assert(sent==3 && !strcmp(recipient,"bob") && !strcmp(message,"Remapped private reply"));
 assert(Input_KeyIsBound(SDL_SCANCODE_T));
 assert(!Input_KeyIsBound(SDL_SCANCODE_UNKNOWN));
 assert(!Input_KeyIsBound(SDL_NUM_SCANCODES));
 LoadSettings(NULL);Input_ReleaseTestInputs();
 assert(!Input_KeyIsBound(SDL_SCANCODE_T));
 SDL_Window *window=SDL_CreateWindow("test",0,0,240,224,SDL_WINDOW_HIDDEN);
 SDL_Renderer *renderer=SDL_CreateRenderer(window,-1,SDL_RENDERER_SOFTWARE);
 assert(renderer);WorldChat_Draw(renderer);
 unsigned pixels[240*224];
 assert(SDL_RenderReadPixels(renderer,NULL,SDL_PIXELFORMAT_ARGB8888,pixels,240*4)==0);
 /* The packed Latin font stores its leftmost pixel in the high bits. */
 assert((pixels[12*240+3] & 0xFFFFFF)==0xD2EBDC);
 SDL_DestroyRenderer(renderer);SDL_DestroyWindow(window);SDL_Quit();
 return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='emerald-chat-ui-') as tmp:
            c, exe = Path(tmp)/'ui.c', Path(tmp)/'ui'
            c.write_text(source)
            config = Path(tmp)/'remapped.ini'
            config.write_text('key_start = T\n')
            import shlex
            flags = ['-I'+str(sysroot/'usr/include'), '-I'+str(sysroot/'usr/include/x86_64-linux-gnu'),
                     '-L'+str(sysroot/'usr/lib/x86_64-linux-gnu'), '-lSDL2']
            if not (sysroot/'usr/include/SDL2/SDL.h').exists():
                try:
                    flags = shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','sdl2'],text=True))
                except (OSError,subprocess.CalledProcessError):
                    self.skipTest('SDL2 development files required for graphical composer test')
            result = subprocess.run([os.environ.get('CC','cc'),'-std=gnu99','-Wall','-Wextra','-Werror', '-DPORTABLE','-DVER_64BIT','-DMODERN=1',
                                     '-iquote', str(root/'include'), str(c), str(ui), str(root/'src/platform/settings.c'),
                                     *flags, '-o',str(exe)], capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            result = subprocess.run([str(exe),str(config)],env=dict(os.environ,SDL_VIDEODRIVER='dummy'),capture_output=True,text=True,cwd=tmp)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            print(result.stdout.strip())

    def test_native_snapshot_chat_is_atomic_and_rejects_injection(self):
        import subprocess
        from test_save_isolation import function
        root = Path(__file__).resolve().parents[2]
        bridge = (root/'src/platform/world_bridge.c').read_text()
        declarations = bridge[bridge.index('#define WB_PEERS'):bridge.index('static bool8 Identifier')]
        source = '''#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <limits.h>
typedef unsigned char bool8;
typedef unsigned char u8;
typedef unsigned short u16;
#define TRUE 1
#define FALSE 0
#define ARRAY_COUNT(a) (sizeof(a)/sizeof((a)[0]))
static int MapCoords(unsigned g,unsigned n,unsigned x,unsigned y) {return g<35 && n<100 && x<200 && y<200;}
static int WorldCatalog_Metatile(unsigned g,unsigned n,unsigned t) {(void)g;(void)n;return t<1024;}
'''+declarations
        source += 'static void Flush(void) {sWorld.outputSize=0;}\n'
        for name in ('Identifier', 'Decimal', 'ObjectText', 'Line', 'WorldBridge_ChatSend',
                     'WorldBridge_ChatCount', 'WorldBridge_ChatStatus', 'WorldBridge_ChatLine'):
            source += function(bridge, name)
        source += r'''
static int line(const char *s) {char b[1024];strcpy(b,s);return Line(b);}
int main(void) {
 sWorld.connected=1;strcpy(sWorld.trainer,"alice");
 assert(line("BEGIN 1"));
 assert(line("CHATMSG 1 bob * 486920746865726521"));
 assert(line("CHATSTATUS sent"));
 assert(WorldBridge_ChatCount()==0);
 assert(line("END"));
 assert(WorldBridge_ChatCount()==1);
 char rendered[184];WorldBridge_ChatLine(0,rendered,sizeof(rendered));
 assert(!strcmp(rendered,"bob: Hi there!"));
 assert(!strcmp(WorldBridge_ChatStatus(),"sent"));
 assert(WorldBridge_ChatSend("bob","<&> 100%"));
 assert(!strcmp(sWorld.output,"CHAT 1 bob 3c263e2031303025\n"));
 assert(!WorldBridge_ChatSend("bob","\xff"));
 assert(!WorldBridge_ChatSend("bob","line\nbreak"));
 assert(!WorldBridge_ChatSend("bad!id","no"));
 assert(!WorldBridge_ChatSend("*","   "));
 sWorld.outputSize=2;assert(!WorldBridge_ChatSend("*","busy"));sWorld.outputSize=0;
 sWorld.connected=0;assert(!WorldBridge_ChatSend("*","offline"));sWorld.connected=1;
 /* A partial snapshot is not player-visible until END. */
 assert(line("BEGIN 2"));
 assert(!line("CHATMSG 2 bob alice ff"));sWorld.staging=0;
 assert(WorldBridge_ChatCount()==1);
 assert(line("BEGIN 2"));
 assert(!line("CHATMSG 2 bob alice 610a62"));sWorld.staging=0;
 assert(line("BEGIN 2"));
 assert(!line("CHATMSG 2 bob carol 61"));sWorld.staging=0;
 assert(line("BEGIN 2"));
 assert(line("CHATMSG 2 bob alice 61"));
 assert(!line("CHATMSG 2 bob alice 61"));sWorld.staging=0;
 assert(line("BEGIN 2"));assert(!line("CHATSTATUS bogus"));
 return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='emerald-chat-c-') as tmp:
            c, exe = Path(tmp)/'chat.c', Path(tmp)/'chat'
            c.write_text(source)
            result = subprocess.run([os.environ.get('CC','cc'),'-std=gnu99','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            result = subprocess.run([str(exe)],capture_output=True,text=True,cwd=tmp)
            self.assertEqual(result.returncode,0,result.stderr)


if __name__ == '__main__':
    unittest.main()
