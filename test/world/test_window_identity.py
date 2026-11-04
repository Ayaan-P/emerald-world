"""Compile the actual SDL input/title seams without SDL, a display, or saves.

Only SDL event delivery and adjacent modules are stubbed. The functions under
regression are extracted verbatim from sdl2.c and compiled with warnings fatal.
"""
import ctypes
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/platform/sdl2.c"


def function(source, name):
    match = re.search(r"^[\w *]+\b" + name + r"\([^;]*?\)\s*\{", source, re.M)
    if match is None:
        raise AssertionError(f"Missing production function {name}")
    start = match.start()
    depth = 1
    end = match.end()
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


HARNESS = r'''
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint16_t u16;
#define NULL_WINDOW ((void *)0)
#define FALSE 0
#define SDL_QUIT 1
#define SDL_KEYDOWN 2
#define SDL_CONTROLLERDEVICEADDED 3
#define SDL_CONTROLLERDEVICEREMOVED 4
#define SDL_WINDOWEVENT 5
#define SDL_WINDOWEVENT_SIZE_CHANGED 6
#define SDL_WINDOW_FULLSCREEN 1
#define SDLK_r 10
#define SDLK_p 11
#define SDLK_F11 12
#define KMOD_LCTRL 1
#define KMOD_RCTRL 2
#define DISPLAY_WIDTH 240
#define DISPLAY_HEIGHT 160
typedef struct {
    int type;
    struct { struct { int sym, mod; } keysym; } key;
    struct { int event, data1, data2; } window;
} SDL_Event;
static SDL_Event next;
static int pending;
static void *sdlWindow;
static const char *sPlayerControlPath;
static bool sTestMode, sWorldBootstrap;
static u16 sTestButtons;
static bool isRunning, paused, speedUp, videoScaleChanged;
static unsigned int videoScale;
static double timeScale;
static u16 localButtons, remoteButtons;
static int localReads, resets, fullscreen;
static const char *trainer;
static int chatBlocks;
static unsigned WindowHeight(void) { return DISPLAY_HEIGHT; }
static int WorldChat_BlocksInput(void) { return chatBlocks; }
static int WorldChat_Event(const SDL_Event *event) { return chatBlocks && event->type == SDL_KEYDOWN; }
void TestChat(int blocks) { chatBlocks = blocks; }
static int SDL_PollEvent(SDL_Event *event) {
    if (!pending) return 0;
    *event = next; pending = 0; return 1;
}
static unsigned SDL_GetWindowFlags(void *window) { (void)window; return 0; }
static void Input_HandleEvent(SDL_Event *event) { (void)event; }
static void RequestSoftReset(void) { resets++; }
static void ToggleFullscreen(void) { fullscreen++; }
static u16 Input_GetButtons(bool *fast) {
    localReads++;
    if (fast) *fast = true;
    return localButtons;
}
static u16 PlayerControl_Buttons(void) { return remoteButtons; }
void TestReset(int ai, unsigned local, unsigned remote) {
    sPlayerControlPath = ai ? "/private/control.sock" : NULL;
    localButtons = local; remoteButtons = remote;
    sTestMode = sWorldBootstrap = false; sTestButtons = 0;
    isRunning = true; paused = speedUp = videoScaleChanged = false;
    videoScale = 1; timeScale = 1.0;
    localReads = resets = fullscreen = pending = 0;
    chatBlocks = 0;
    trainer = NULL;
}
void TestEvent(int type, int key, int mod) {
    memset(&next, 0, sizeof(next)); next.type = type;
    next.key.keysym.sym = key; next.key.keysym.mod = mod; pending = 1;
}
void TestResize(void) {
    memset(&next, 0, sizeof(next)); next.type = SDL_WINDOWEVENT;
    next.window.event = SDL_WINDOWEVENT_SIZE_CHANGED;
    next.window.data1 = 720; next.window.data2 = 480; pending = 1;
}
void TestScript(int mode, unsigned keys) {
    sTestMode = mode == 1; sWorldBootstrap = mode == 2; sTestButtons = keys;
}
int TestLocalReads(void) { return localReads; }
int TestResets(void) { return resets; }
int TestPaused(void) { return paused; }
int TestRunning(void) { return isRunning; }
int TestFullscreen(void) { return fullscreen; }
int TestScale(void) { return videoScaleChanged ? (int)videoScale : 0; }
double TestTimeScale(void) { return timeScale; }
'''


class WindowIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text()
        cls.scratch = tempfile.TemporaryDirectory(prefix="emerald-window-")
        cls.addClassCleanup(cls.scratch.cleanup)
        cls.lib = cls.compile("input", HARNESS + "\n" + "\n".join(
            function(cls.source, name) for name in ("ProcessEvents", "Platform_GetKeyInput")))
        cls.lib.Platform_GetKeyInput.restype = ctypes.c_uint16
        cls.lib.TestTimeScale.restype = ctypes.c_double

    @classmethod
    def compile(cls, name, content):
        path = Path(cls.scratch.name) / (name + ".c")
        path.write_text(content)
        output = path.with_suffix(".so")
        subprocess.run(["cc", "-shared", "-fPIC", "-std=gnu99", "-Wall", "-Wextra",
                        "-Werror", str(path), "-o", str(output)], check=True,
                       capture_output=True, text=True)
        return ctypes.CDLL(str(output))

    def test_ai_input_excludes_physical_keyboard_and_controller(self):
        self.lib.TestReset(1, 0x3ff, 0x10)
        self.assertEqual(self.lib.Platform_GetKeyInput(), 0x10)
        self.assertEqual(self.lib.TestLocalReads(), 0)
        self.lib.TestReset(1, 0x3ff, 0)
        self.assertEqual(self.lib.Platform_GetKeyInput(), 0)
        self.assertEqual(self.lib.TestLocalReads(), 0)

    def test_human_input_remains_local(self):
        self.lib.TestReset(0, 0x21, 0)
        self.assertEqual(self.lib.Platform_GetKeyInput(), 0x21)
        self.assertEqual(self.lib.TestLocalReads(), 1)

    def test_chat_neutralizes_game_input_without_pausing(self):
        self.lib.TestReset(0, 0x3ff, 0)
        self.lib.TestChat(1)
        self.lib.TestEvent(2, 10, 1)
        self.lib.ProcessEvents()
        self.assertEqual(self.lib.Platform_GetKeyInput(), 0)
        self.assertEqual(self.lib.TestResets(), 0)
        self.assertEqual(self.lib.TestPaused(), 0)
        self.assertEqual(self.lib.TestTimeScale(), 1.0)
        self.assertEqual(self.lib.TestLocalReads(), 0)

    def test_ai_events_cannot_pause_reset_or_fast_forward(self):
        self.lib.TestReset(1, 0x3ff, 0)
        for key in (10, 11):
            self.lib.TestEvent(2, key, 1)
            self.lib.ProcessEvents()
        self.assertEqual(self.lib.TestResets(), 0)
        self.assertEqual(self.lib.TestPaused(), 0)
        self.assertEqual(self.lib.TestLocalReads(), 0)
        self.assertEqual(self.lib.TestTimeScale(), 1.0)

    def test_human_gameplay_shortcuts_still_work(self):
        self.lib.TestReset(0, 0, 0)
        self.lib.TestEvent(2, 10, 1)
        self.lib.ProcessEvents()
        self.lib.TestEvent(2, 11, 2)
        self.lib.ProcessEvents()
        self.assertEqual(self.lib.TestResets(), 1)
        self.assertEqual(self.lib.TestPaused(), 1)
        self.assertEqual(self.lib.TestTimeScale(), 5.0)

    def test_ai_window_management_remains_available(self):
        self.lib.TestReset(1, 0, 0)
        self.lib.TestEvent(2, 12, 0)
        self.lib.ProcessEvents()
        self.assertEqual(self.lib.TestFullscreen(), 1)
        self.lib.TestResize()
        self.lib.ProcessEvents()
        self.assertEqual(self.lib.TestScale(), 3)
        self.lib.TestEvent(1, 0, 0)
        self.lib.ProcessEvents()
        self.assertEqual(self.lib.TestRunning(), 0)

    def test_native_window_title_uses_configured_identity_and_explicit_role(self):
        title = self.compile("title", '''
#include <stdio.h>
static const char *sPlayerControlPath;
static const char *trainer;
static const char *WorldBridge_TrainerName(void) { return trainer; }
''' + function(self.source, "WindowTitle") + '''
const char *TestTitle(const char *name, int ai) {
    trainer = name;
    sPlayerControlPath = ai ? "/private/token/control.sock" : NULL;
    return WindowTitle();
}
''')
        title.TestTitle.argtypes = [ctypes.c_char_p, ctypes.c_int]
        title.TestTitle.restype = ctypes.c_char_p
        for name, ai, expected in (
            (b"ayaan", 0, b"Emerald World | ayaan | Human"),
            (b"hermes", 1, b"Emerald World | hermes | AI player"),
            (b"hermes", 0, b"Emerald World | hermes | Human"),
            (b"ayaan", 1, b"Emerald World | ayaan | AI player"),
            (None, 0, b"Emerald World | Local trainer | Human"),
            (None, 1, b"Emerald World | Local trainer | AI player"),
            (b"x" * 24, 1, b"Emerald World | " + b"x" * 24 + b" | AI player"),
        ):
            with self.subTest(name=name, ai=ai):
                self.assertEqual(title.TestTitle(name, ai), expected)
        main = function(self.source, "main")
        self.assertRegex(main, r"SDL_CreateWindow\(WindowTitle\(\),")
        self.assertLess(main.index("WorldBridge_Init("), main.index("SDL_CreateWindow("))

    def test_bridge_accessor_returns_only_enabled_configured_identity(self):
        bridge = (ROOT / "src/platform/world_bridge.c").read_text()
        header = (ROOT / "include/platform/world_bridge.h").read_text()
        self.assertIn("const char *WorldBridge_TrainerName(void);", header)
        accessor = self.compile("identity", '''
#include <stddef.h>
#include <string.h>
static struct { int enabled; char trainer[25]; char token[65]; } sWorld;
''' + function(bridge, "WorldBridge_TrainerName") + '''
const char *TestIdentity(int enabled) {
    sWorld.enabled = enabled;
    strcpy(sWorld.trainer, "ayaan");
    strcpy(sWorld.token, "private-token-must-not-be-displayed");
    return WorldBridge_TrainerName();
}
''')
        accessor.TestIdentity.argtypes = [ctypes.c_int]
        accessor.TestIdentity.restype = ctypes.c_char_p
        self.assertIsNone(accessor.TestIdentity(0))
        self.assertEqual(accessor.TestIdentity(1), b"ayaan")

    def test_scripted_bootstrap_and_headless_input_remain_available(self):
        for mode in (1, 2):
            self.lib.TestReset(1, 0x3ff, 0x10)
            self.lib.TestScript(mode, 0x80)
            self.assertEqual(self.lib.Platform_GetKeyInput(), 0x80)
            self.assertEqual(self.lib.TestLocalReads(), 0)


if __name__ == "__main__":
    unittest.main()
