"""Production C eligibility checks. These do not claim native storage gameplay."""
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


class TradeStorageAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Map IDs are generated from the repository data, never hardcoded here.
        subprocess.run(['make', '-C', 'tools/mapjson'], cwd=ROOT,
                       check=True, capture_output=True)
        subprocess.run(['tools/mapjson/mapjson', 'groups', 'emerald',
                        'data/maps/map_groups.json', 'data/maps', 'include/constants'],
                       cwd=ROOT, check=True, capture_output=True)

    def test_storage_script_assembles_with_the_stock_waitstate(self):
        # Assemble the actual new script with production command/special macros.
        # This catches a missing implicit waitstate without inventing bytecodes.
        subprocess.run(['make', '-C', 'tools/preproc'], cwd=ROOT,
                       check=True, capture_output=True)
        text = (ROOT / 'data/event_scripts.s').read_text()
        label = text.index('WorldActivity_EventScript_StoragePC::')
        start = text.rfind('\t.ifdef PORTABLE', 0, label)
        self.assertNotEqual(start, -1)
        body = text[start:text.index('\t.endif', label) + len('\t.endif')]
        wrapper = ('.include "asm/macros.inc"\n.include "asm/macros/event.inc"\n'
                   '.section .text\n' + body + '\n')
        with tempfile.TemporaryDirectory() as directory:
            source = pathlib.Path(directory) / 'storage.s'
            obj = pathlib.Path(directory) / 'storage.o'
            binary = pathlib.Path(directory) / 'storage.bin'
            source.write_text(wrapper)
            expanded = subprocess.run([
                str(ROOT / 'tools/preproc/preproc'), str(source), 'charmap.txt'
            ], cwd=ROOT, check=True, capture_output=True)
            # Match data build flags: PORTABLE belongs to AS, never CPP.
            cpp = subprocess.run(['cpp', '-I', 'include', '-'],
                                 input=expanded.stdout, cwd=ROOT, check=True,
                                 capture_output=True)
            preprocessed = subprocess.run([
                str(ROOT / 'tools/preproc/preproc'), '-ie', str(source), 'charmap.txt'
            ], input=cpp.stdout, cwd=ROOT, check=True, capture_output=True)
            subprocess.run(['as', '--64', '--defsym', 'VER_64BIT=1', '--defsym',
                            'PORTABLE=1', '--defsym', 'MODERN=1', '-o', str(obj)],
                           input=preprocessed.stdout, cwd=ROOT, check=True,
                           capture_output=True)
            symbols = subprocess.run(['nm', str(obj)], check=True,
                                     capture_output=True, text=True).stdout
            values = {line.split()[2]: int(line.split()[0], 16)
                      for line in symbols.splitlines() if len(line.split()) == 3}
            subprocess.run(['objcopy', '-O', 'binary', '-j', '.text', str(obj), str(binary)],
                           check=True, capture_output=True)
            special = values['SPECIAL_ShowPokemonStorageSystemPC']
            self.assertEqual(binary.read_bytes(), bytes([
                values['SCR_OP_LOCKALL'], values['SCR_OP_SPECIAL'],
                special & 255, special >> 8, values['SCR_OP_WAITSTATE'],
                values['SCR_OP_RELEASEALL'], values['SCR_OP_END']]))
            # This is a guard check using the native assembler, not GBA ROM
            # neutrality evidence. No-portability output must omit our entry.
            subprocess.run(['as', '--64', '--defsym', 'VER_64BIT=1',
                            '--defsym', 'MODERN=1', '-o', str(obj)],
                           input=preprocessed.stdout, cwd=ROOT, check=True,
                           capture_output=True)
            symbols = subprocess.run(['nm', str(obj)], check=True,
                                     capture_output=True, text=True).stdout
            self.assertNotIn('WorldActivity_EventScript_StoragePC', symbols)

    def test_center_only_and_idle_field_boundaries(self):
        harness = r'''
#include <assert.h>
#include "src/platform/world_activity.c"

struct Main gMain;
struct PaletteFadeControl gPaletteFade;
u8 gWirelessCommType;
static bool8 scripted, locked;
static int native;
void CB1_Overworld(void) {}
void CB2_Overworld(void) {}
bool8 ScriptContext_IsEnabled(void) { return scripted; }
bool8 ArePlayerFieldControlsLocked(void) { return locked; }
int NativeLink_IsActive(void) { return native; }

/* UI/transport boundaries are spies. Task_Menu itself is production code. */
struct SaveBlock1 *gSaveBlock1Ptr;
struct Pokemon gPlayerParty[PARTY_SIZE];
u8 gPlayerPartyCount;
const u8 WorldActivity_EventScript_StoragePC[] = {0};
static const u8 *startedScript;
static unsigned offers, accepts, aborts, removes, destroys;
static u8 choices, initialCursor, menuHeight;
static bool8 fieldStorageHint;
static s8 selection;
s8 Menu_ProcessInputNoWrap(void) { return selection; }
void ScriptContext_SetupScript(const u8 *script) { startedScript = script; scripted = TRUE; }
void NativeLink_Abort(void) { aborts++; }
void CloseLink(void) {}
void UnlockPlayerFieldControls(void) { locked = FALSE; }
void UnfreezeObjectEvents(void) {}
void BattleSetup_ResumeWorldWildBattle(void) { assert(0); }
void DestroyTask(u8 task) { destroys++; }
void ClearStdWindowAndFrame(u8 window, bool8 copy) {}
void RemoveWindow(u8 window) { removes++; }
u16 AddWindow(const struct WindowTemplate *window) { menuHeight = window->height; return 3; }
u8 CreateTask(TaskFunc func, u8 priority) { assert(func == Task_Menu); return 2; }
u8 InitMenuNormal(u8 window, u8 font, u8 left, u8 top, u8 height, u8 count, u8 initial)
{ choices = count; initialCursor = initial; return initial; }
void SetStandardWindowBorderStyle(u8 window, bool8 copy) {}
bool16 AddTextPrinterParameterized(u8 window, u8 font, const u8 *text,
                                   u8 x, u8 y, u8 speed, TextPrinterCallback callback)
{
    u8 expected[64];
    Encode(expected, "PC mons at a Pokemon Center");
    if (y == 144 && !memcmp(expected, text, sizeof("PC mons at a Pokemon Center")))
        fieldStorageHint = TRUE;
    return FALSE;
}
void CopyWindowToVram(u8 window, u8 mode) {}
u32 GetMonData2(struct Pokemon *mon, s32 field) { return 0; }
int LinkTransport_Offer(const char *peer, unsigned mode) { offers++; return 1; }
int LinkTransport_Accept(uint64_t id) { accepts++; return 1; }
int LinkTransport_Reject(uint64_t id) { return 1; }
int LinkTransport_TagOffer(const char *peer) { offers++; return 1; }
int LinkTransport_TagAccept(uint64_t id) { accepts++; return 1; }
int LinkTransport_TagReject(uint64_t id) { return 1; }
int LinkTransport_TagEnd(void) { return 1; }
const char *LinkTransport_TagPeer(void) { return NULL; }
int LinkTransport_TagInRange(void) { return 0; }

int main(void)
{
    const u16 centers[] = {
        MAP_OLDALE_TOWN_POKEMON_CENTER_1F,
        MAP_DEWFORD_TOWN_POKEMON_CENTER_1F,
        MAP_LAVARIDGE_TOWN_POKEMON_CENTER_1F,
        MAP_FALLARBOR_TOWN_POKEMON_CENTER_1F,
        MAP_VERDANTURF_TOWN_POKEMON_CENTER_1F,
        MAP_PACIFIDLOG_TOWN_POKEMON_CENTER_1F,
        MAP_PETALBURG_CITY_POKEMON_CENTER_1F,
        MAP_SLATEPORT_CITY_POKEMON_CENTER_1F,
        MAP_MAUVILLE_CITY_POKEMON_CENTER_1F,
        MAP_RUSTBORO_CITY_POKEMON_CENTER_1F,
        MAP_FORTREE_CITY_POKEMON_CENTER_1F,
        MAP_LILYCOVE_CITY_POKEMON_CENTER_1F,
        MAP_MOSSDEEP_CITY_POKEMON_CENTER_1F,
        MAP_SOOTOPOLIS_CITY_POKEMON_CENTER_1F,
        MAP_EVER_GRANDE_CITY_POKEMON_CENTER_1F,
        MAP_BATTLE_FRONTIER_POKEMON_CENTER_1F
    };
    for (unsigned i = 0; i < sizeof(centers) / sizeof(*centers); i++)
        assert(TradeStorageLocation(MAP_GROUP(centers[i]), MAP_NUM(centers[i])));
    assert(!TradeStorageLocation(MAP_GROUP(MAP_ROUTE101), MAP_NUM(MAP_ROUTE101)));
    assert(!TradeStorageLocation(MAP_GROUP(MAP_LITTLEROOT_TOWN_BRENDANS_HOUSE_1F),
                                 MAP_NUM(MAP_LITTLEROOT_TOWN_BRENDANS_HOUSE_1F)));
    assert(!TradeStorageLocation(MAP_GROUP(MAP_OLDALE_TOWN_POKEMON_CENTER_2F),
                                 MAP_NUM(MAP_OLDALE_TOWN_POKEMON_CENTER_2F)));
    assert(!TradeStorageLocation(255, 255));
    gMain.callback1 = CB1_Overworld;
    gMain.callback2 = CB2_Overworld;
    sActivity.state = MENU;
    assert(TradeStorageFieldReady());
    for (unsigned state = IDLE; state <= RETURNING; state++) {
        sActivity.state = state;
        assert(TradeStorageFieldReady() == (state == MENU));
    }
    sActivity.state = MENU;
    native = 1; assert(!TradeStorageFieldReady()); native = 0;
    scripted = TRUE; assert(!TradeStorageFieldReady()); scripted = FALSE;
    locked = TRUE; assert(!TradeStorageFieldReady()); locked = FALSE;
    gMain.inBattle = TRUE; assert(!TradeStorageFieldReady()); gMain.inBattle = FALSE;
    gPaletteFade.active = TRUE; assert(!TradeStorageFieldReady()); gPaletteFade.active = FALSE;
    gWirelessCommType = 1; assert(!TradeStorageFieldReady()); gWirelessCommType = 0;
    gMain.callback2 = NULL; assert(!TradeStorageFieldReady());

    /* Selecting storage cleans up only this menu, starts the existing local
     * script, and cannot consent to or offer a native trade. */
    static struct SaveBlock1 save;
    gSaveBlock1Ptr = &save;
    gMain.callback2 = CB2_Overworld;
    save.location.mapGroup = MAP_GROUP(MAP_OLDALE_TOWN_POKEMON_CENTER_1F);
    save.location.mapNum = MAP_NUM(MAP_OLDALE_TOWN_POKEMON_CENTER_1F);
    sActivity.state = MENU;
    sActivity.timer = 1;
    sActivity.window = 3;
    sActivity.task = 2;
    selection = 6;
    Task_Menu(2);
    assert(startedScript == WorldActivity_EventScript_StoragePC);
    assert(sActivity.state == IDLE && !WorldActivity_OwnsFieldInput());
    assert(sActivity.window == WINDOW_NONE && sActivity.task == TASK_NONE);
    assert(removes == 1 && destroys == 1);
    assert(offers == 0 && accepts == 0 && aborts == 0);
    assert(scripted); /* controls now belong to the stock script */

    /* A stale selection after leaving the Center must not open storage. */
    scripted = FALSE;
    startedScript = NULL;
    save.location.mapGroup = MAP_GROUP(MAP_ROUTE101);
    save.location.mapNum = MAP_NUM(MAP_ROUTE101);
    sActivity.state = MENU;
    sActivity.timer = 1;
    Task_Menu(2);
    assert(!startedScript && sActivity.state == IDLE);
    assert(offers == 0 && accepts == 0 && aborts == 0);

    /* Opening A is inert; Cancel follows Tag and remains distinct from PC. */
    sActivity.state = MENU;
    sActivity.timer = 0;
    Task_Menu(2);
    assert(sActivity.state == MENU && !startedScript);
    selection = 5;
    Task_Menu(2);
    assert(sActivity.state == IDLE && !startedScript);
    assert(offers == 0 && accepts == 0 && aborts == 0);

    /* Real menu construction offers storage only in a Center, keeps incoming
     * consent defaulted to No, and explains field party-only access. */
    save.location.mapGroup = MAP_GROUP(MAP_OLDALE_TOWN_POKEMON_CENTER_1F);
    save.location.mapNum = MAP_NUM(MAP_OLDALE_TOWN_POKEMON_CENTER_1F);
    sActivity.state = MENU;
    assert(ShowMenu(FALSE));
    assert(choices == 7 && initialCursor == 0 && menuHeight == 20);
    CloseMenu();
    save.location.mapGroup = MAP_GROUP(MAP_ROUTE101);
    save.location.mapNum = MAP_NUM(MAP_ROUTE101);
    assert(ShowMenu(FALSE));
    assert(choices == 6 && fieldStorageHint);
    CloseMenu();
    sActivity.mode = NATIVE_LINK_TRADE;
    assert(ShowMenu(TRUE));
    assert(choices == 2 && initialCursor == 1);
    CloseMenu();

    /* Existing trade selection still offers, never silently accepts. */
    scripted = FALSE;
    startedScript = NULL;
    sActivity.state = MENU;
    sActivity.timer = 1;
    gPlayerPartyCount = 1;
    selection = 3;
    Task_Menu(2);
    assert(sActivity.state == WAIT_ADMIT && offers == 1 && accepts == 0);
    assert(!startedScript);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            source = pathlib.Path(directory) / 'storage.c'
            binary = pathlib.Path(directory) / 'storage'
            source.write_text(harness)
            result = subprocess.run([
                'gcc', '-std=gnu99', '-DPORTABLE', '-DMODERN=1', '-DNONMATCHING',
                '-DUBFIX', '-DVER_64BIT', '-Werror', '-Werror=implicit-function-declaration',
                '-ffunction-sections', '-fdata-sections', '-iquote', '.', '-iquote', 'include',
                str(source), '-Wl,--gc-sections', '-o', str(binary)
            ], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    unittest.main()
