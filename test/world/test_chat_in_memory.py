"""Exercise chat routing without opening sockets or touching live profiles."""
import unittest
from unittest.mock import Mock, patch
from world.server import WorldServer
from world.rally import RallyCoordinator


def peer(name, opted_in=True):
    return {'id': name, 'chat': opted_in, 'chat_history': [], 'chat_status': 'ready', 'closing': False, 'seq': -1, 'state': None, 'social': True}


class ChatRoutingTests(unittest.TestCase):
    def setUp(self):
        self.server = WorldServer.__new__(WorldServer)
        self.server.chat_serial = 0
        self.server.peers = {name: peer(name, name != 'legacy') for name in ('alice', 'bob', 'carol', 'legacy')}
        self.server.rally = RallyCoordinator(self.server.peers)
        from world.guild_chat import GuildChat
        from world.server import validate_coords, TRAVEL_FRESH_SECONDS
        self.server.guild_chat = GuildChat(self.server, validate_coords, TRAVEL_FRESH_SECONDS)
        self.server._broadcast = Mock()
        self.server._queue = Mock()
        self.server.revision = 0
        self.server.tiles = []
        self.server.objects = []
        self.server._error = Mock()
        self.alice = self.server.peers['alice']

    def send(self, seq, recipient, message):
        self.server._chat(self.alice, ['CHAT', str(seq), recipient, message.encode().hex()])

    @patch('world.server.time.monotonic', return_value=100)
    def test_private_and_room_chat_only_reach_authorized_recipients(self, _clock):
        self.send(1, 'bob', 'hello privately')
        self.assertEqual(len(self.server.peers['bob']['chat_history']), 1)
        self.assertEqual(self.server.peers['alice']['chat_history'], self.server.peers['bob']['chat_history'])
        self.assertEqual(self.server.peers['carol']['chat_history'], [])
        self.assertEqual(self.server.peers['legacy']['chat_history'], [])
        self.assertNotIn('CHATMSG', self.server._snapshot(self.server.peers['carol']))
        self.assertNotIn('CHAT', self.server._snapshot(self.server.peers['legacy']))
        self.send(2, '*', 'hello everyone')
        self.assertEqual(len(self.server.peers['carol']['chat_history']), 1)
        self.assertEqual(self.server.peers['legacy']['chat_history'], [])

    @patch('world.server.time.monotonic', return_value=100)
    def test_stale_and_unknown_recipients_do_not_publish(self, _clock):
        self.send(1, '*', 'first')
        self.send(1, '*', 'stale')
        self.server._error.assert_called_once_with(self.alice, 'STALE')
        self.send(2, 'legacy', 'private')
        self.assertEqual(self.alice['chat_status'], 'unavailable')
        self.assertEqual(self.server.chat_serial, 1)
        self.assertEqual(len(self.server.peers['bob']['chat_history']), 1)

    @patch('world.server.time.monotonic', return_value=100)
    def test_authenticated_opt_in_uses_current_presence_protocol(self, _clock):
        self.alice['chat'] = False
        self.server._line(self.alice, b'CHAT_ENABLE')
        self.assertTrue(self.alice['chat'])
        self.server._line(self.alice, b'CHAT 1 bob 6869')
        self.assertEqual(self.server.peers['bob']['chat_history'], [(1, 'alice', 'bob', '6869')])
        self.server._line(self.alice, b'CHAT\t2 * 61')
        self.server._error.assert_called_once_with(self.alice, 'MALFORMED')

    def test_server_negotiates_chat_without_changing_legacy_hello(self):
        import sqlite3
        from types import SimpleNamespace
        self.server.db = sqlite3.connect(':memory:')
        self.addCleanup(self.server.db.close)
        self.server.db.execute('CREATE TABLE identities (id TEXT, token TEXT)')
        token = 'ab' * 32
        self.server.db.executemany('INSERT INTO identities VALUES (?, ?)', [('new', token), ('old', token)])
        self.server.peers = {}
        self.server.rally = RallyCoordinator(self.server.peers)
        self.server.host_controls = SimpleNamespace(rejection=lambda name: None)
        self.server.max_players = 8
        self.server._event = Mock()
        for name, role, expected in [('new', 'SOCIALCHAT', True), ('old', 'SOCIAL', False)]:
            conn = {'id': None, 'closing': False, 'state': None}
            self.server._line(conn, f'HELLO 1 {name} {token} {role}'.encode())
            self.assertEqual(conn['id'], name)
            self.assertTrue(conn['social'])
            self.assertEqual(conn['chat'], expected)
        self.assertNotIn('CHAT', self.server._snapshot(self.server.peers['old']))

    def test_invalid_text_and_unopted_sender_rejected(self):
        for payload in ('00', '2020', 'ff', 'a', '61' * 121):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.server._chat(self.alice, ['CHAT', '1', '*', payload])
        with self.assertRaises(ValueError):
            self.server._chat(self.server.peers['legacy'], ['CHAT', '1', '*', '61'])

class ChatKeyBindingTests(unittest.TestCase):
    def test_history_keys_respect_game_remaps_outside_composer(self):
        import subprocess, tempfile
        from pathlib import Path
        from test_save_isolation import function
        root = Path(__file__).resolve().parents[2]
        event = function((root / 'src/platform/world_chat.c').read_text(), 'WorldChat_Event')
        source = r'''
#include <assert.h>
#include <string.h>
#include <stddef.h>
#define WORLD_CHAT_HEIGHT 64
#define SDL_WINDOWEVENT 1
#define SDL_WINDOWEVENT_FOCUS_LOST 2
#define SDL_TEXTINPUT 3
#define SDL_KEYDOWN 4
#define SDLK_PAGEUP 5
#define SDLK_PAGEDOWN 6
#define SDLK_t 7
#define SDLK_RETURN 8
#define SDLK_ESCAPE 9
#define SDLK_BACKSPACE 10
#define KMOD_ALT 1
#define KMOD_GUI 2
#define KMOD_CTRL 4
typedef struct { int type; struct { int event; } window; struct { char text[32]; } text;
 struct { struct { int sym, scancode, mod; } keysym; int repeat; } key; } SDL_Event;
static struct { int editing, releaseKeys; unsigned scroll; char draft[152], hint[96]; } sChat;
static int bound;
static int WorldBridge_Enabled(void) { return 1; }
static int Input_KeyIsBound(int code) { return code == bound; }
static int SDL_GetScancodeFromKey(int code) { return code; }
static void SDL_StopTextInput(void) {}
static void SDL_StartTextInput(void) {}
static void SDL_FlushEvent(int x) { (void)x; }
static void Submit(void) {}
''' + event + r'''
int main(void) {
 SDL_Event e = {0}; e.type=SDL_KEYDOWN; e.key.keysym.sym=SDLK_PAGEUP; e.key.keysym.scancode=SDLK_PAGEUP;
 bound=SDLK_PAGEUP; assert(WorldChat_Event(&e)==0 && sChat.scroll==0);
 bound=0; assert(WorldChat_Event(&e)==1 && sChat.scroll==3);
 e.key.keysym.sym=SDLK_PAGEDOWN; e.key.keysym.scancode=SDLK_PAGEDOWN;
 bound=SDLK_PAGEDOWN; assert(WorldChat_Event(&e)==0 && sChat.scroll==3);
 sChat.editing=1; assert(WorldChat_Event(&e)==1 && sChat.scroll==0);
 return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='chat-keys-') as tmp:
            src, out = Path(tmp) / 'keys.c', Path(tmp) / 'keys'
            src.write_text(source)
            subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', str(src), '-o', str(out)], check=True, capture_output=True)
            subprocess.run([str(out)], check=True, capture_output=True)
