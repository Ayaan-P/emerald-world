#ifdef PORTABLE
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <time.h>

#ifdef _WIN32
#define NOMINMAX // global.h has its own
#include <windows.h>
#endif

#include <SDL2/SDL.h>

#include "platform/native_file.h"
#ifndef _WIN32
#include "platform/native_save.h"
#endif
#include "global.h"
#include "platform/generated_map.h"
#include "platform.h"
#include "rtc.h"
#include "gba/defines.h"
#include "gba/m4a_internal.h"
#include "cgb_audio.h"
#include "gba/flash_internal.h"
#include "platform/dma.h"
#include "platform/framedraw.h"
#include "platform/settings.h"
#include "platform/system.h"
#include "platform/test_state.h"
#include "platform/world_bridge.h"
#include "platform/world_chat.h"
#include "platform/world_activity.h"
#include "platform/player_control.h"
#include "platform/native_link.h"
#include "platform/link_transport.h"
#include "platform/dexnav_native.h"
#include "link.h"

extern void (*const gIntrTable[])(void);

SDL_Thread *mainLoopThread;
SDL_Window *sdlWindow;
SDL_Renderer *sdlRenderer;
SDL_Texture *sdlTexture;
SDL_sem *vBlankSemaphore;
SDL_atomic_t isFrameAvailable;
bool speedUp = false;
unsigned int videoScale = 1;
bool videoScaleChanged = false;
bool isRunning = true;
bool paused = false;
double simTime = 0;
double lastGameTime = 0;
double curGameTime = 0;
double fixedTimestep = 1.0 / 60.0; // 16.666667ms
double timeScale = 1.0;
struct SiiRtcInfo internalClock;

static FILE *sSaveFile = NULL;
static const char *sSavePath;
static const char *sSettingsPath;
static char *sDataDir;

// Headless test mode, see RunTestMode()
static bool sTestMode = false;
static FILE *sTestInput;
static FILE *sTestHashes;
static const char *sTestShotDir;
static u32 sTestShotEvery;
static time_t sTestClockBase = 1767268800; // 2026-01-01 12:00:00 UTC
static u32 sTestFrame;
static u64 sTestAudioHash;
static FILE *sTestAudio;
static FILE *sTestState;
static const char *sWorldConfigPath;
static const char *sWorldInputPath;
static const char *sGeneratedMapPath;
static bool sGeneratedProgress;
static const char *sWorldShotPath;
static bool sWorldBootstrap;
static u32 sWorldFrame;
static const char *sPlayerControlPath;

static unsigned WindowHeight(void)
{
    return DISPLAY_HEIGHT + (WorldBridge_Enabled() ? WORLD_CHAT_HEIGHT : 0);
}

extern void AgbMain(void);

int DoMain(void *param);
void ProcessEvents(void);
void VDraw(SDL_Texture *texture);

static bool ReadSaveFile(const char *path);
static bool StoreSaveFile(void);
static void CloseSaveFile(void);

static void InitInternalClock(void);
static void UpdateInternalClock(void);

static bool ParseArgs(int argc, char **argv);
static void WriteWavHeader(FILE *file, u32 dataSize);
static void FindDataFiles(void);
static void ToggleFullscreen(void);
static int RunTestMode(void);
static bool ReadTestInput(u16 *outKeys);
static void WriteFramebufferPPM(const uint16_t *image, const char *path);
static void WorldBootstrapFrame(void);
static bool PlayerScreenshot(FILE *file);
static bool WriteFramebufferStream(const uint16_t *image, FILE *file);

static const char *WindowTitle(void)
{
    static char title[96];
    const char *trainer = WorldBridge_TrainerName();

    // This labels the validated local configuration, not connection status.
    snprintf(title, sizeof(title), "Emerald World | %s | %s",
             trainer != NULL ? trainer : "Local trainer",
             sPlayerControlPath != NULL ? "AI player" : "Human");
    return title;
}

static bool BeginNativeFrame(bool8 headless)
{
    WorldBridge_Poll(headless);
    LinkTransport_Pump();
    return NativeLink_BeforeFrame(gSendCmd);
}

/* SDL2 main/windows/SDL_windows_main.c converts CommandLineToArgvW output
 * with WIN_StringToUTF8W before calling SDL_main (the SDL.h main macro).
 * Keep argv and SDL_GetPrefPath UTF-8; NativeFile_Open performs the OS conversion. */
static bool LoadGeneratedMapTemplate(const char *path)
{
    static const u8 magic1[8] = { 'E', 'W', 'G', 'M', 'A', 'P', '0', '1' };
#if GENERATED_CAVE_PROFILES
    static const u8 magic2[8] = { 'E', 'W', 'G', 'M', 'A', 'P', '0', '2' };
#endif
#if GENERATED_CAVE_WILDLIFE
    static const u8 magic3[8] = { 'E', 'W', 'G', 'M', 'A', 'P', '0', '3' };
#endif
#if GENERATED_MAP_LARGE
    static const u8 magic4[8] = { 'E', 'W', 'G', 'M', 'A', 'P', '0', '4' };
#if GENERATED_MAP_WILDS
    static const u8 magic6[8] = { 'E', 'W', 'G', 'M', 'A', 'P', '0', '6' };
#if GENERATED_WORLD_XL
    static const u8 magicXL[8] = { 'E', 'W', 'G', 'M', 'A', 'P', '0', 'A' };
    static const u8 magicXLPalette[8] = { 'E', 'W', 'G', 'M', 'A', 'P', '0', 'D' };
#if GENERATED_WILDS_CAST
    static const u8 magicXLCast[8] = { 'E', 'W', 'G', 'M', 'A', 'P', '0', 'B' };
#if GENERATED_WILDS_EVENTS
    static const u8 magicXLEvents[8] = { 'E', 'W', 'G', 'M', 'A', 'P', '0', 'C' };
    static const u8 magicXLPaintedEvents[8] = { 'E', 'W', 'G', 'M', 'A', 'P', '0', 'E' };
#endif
#endif
#endif
#if GENERATED_WILDS_GUIDE
    static const u8 magic7[8] = { 'E', 'W', 'G', 'M', 'A', 'P', '0', '7' };
#if GENERATED_WILDS_CAST
    static const u8 magic8[8] = { 'E', 'W', 'G', 'M', 'A', 'P', '0', '8' };
#if GENERATED_WILDS_EVENTS
    static const u8 magic9[8] = { 'E', 'W', 'G', 'M', 'A', 'P', '0', '9' };
#endif
#endif
#endif
#endif
#if GENERATED_CAVE_WILDLIFE
    static const u8 magic5[8] = { 'E', 'W', 'G', 'M', 'A', 'P', '0', '5' };
#endif
#if GENERATED_WORLD_XL
#if GENERATED_WILDS_EVENTS
    u8 bytes[8 + GENERATED_EVENT_BYTES + GENERATED_CAST_BYTES + GENERATED_XL_MAP_BYTES];
#elif GENERATED_WILDS_CAST
    u8 bytes[8 + GENERATED_CAST_BYTES + GENERATED_XL_MAP_BYTES];
#else
    u8 bytes[8 + GENERATED_XL_MAP_BYTES];
#endif
#elif GENERATED_WILDS_EVENTS
    u8 bytes[8 + GENERATED_EVENT_BYTES + GENERATED_CAST_BYTES + GENERATED_LARGE_MAP_TEMPLATE_BYTES];
#elif GENERATED_WILDS_CAST
    u8 bytes[8 + GENERATED_CAST_BYTES + GENERATED_LARGE_MAP_TEMPLATE_BYTES];
#elif GENERATED_WILDS_GUIDE
    u8 bytes[8 + GENERATED_GUIDE_BYTES + GENERATED_LARGE_MAP_TEMPLATE_BYTES];
#else
    u8 bytes[9 + GENERATED_WILDLIFE_BYTES + GENERATED_LARGE_MAP_TEMPLATE_BYTES];
#endif
#else
    u8 bytes[9 + GENERATED_WILDLIFE_BYTES + GENERATED_MAP_TEMPLATE_BYTES];
#endif
    FILE *file = NativeFile_Open(path, "rb");
    size_t count;
    int extra;
    bool8 valid = FALSE;
    if (!file) return false;
    count = fread(bytes, 1, sizeof(bytes), file);
    extra = fgetc(file);
    if (extra == EOF && !ferror(file))
    {
        if (count == 8 + GENERATED_MAP_TEMPLATE_BYTES && !memcmp(bytes, magic1, 8))
            valid = GeneratedMap_StageTemplate(bytes + 8, GENERATED_MAP_TEMPLATE_BYTES);
#if GENERATED_CAVE_PROFILES
        else if (count == 9 + GENERATED_MAP_TEMPLATE_BYTES && !memcmp(bytes, magic2, 8)
              && bytes[8] <= 3 && GeneratedMap_StageTemplate(bytes + 9, GENERATED_MAP_TEMPLATE_BYTES))
            valid = GeneratedMap_SetEncounterProfile(bytes[8]);
#endif
#if GENERATED_CAVE_WILDLIFE
        else if (count == 9 + GENERATED_WILDLIFE_BYTES + GENERATED_MAP_TEMPLATE_BYTES
              && !memcmp(bytes, magic3, 8) && bytes[8] <= 3
              && GeneratedMap_ValidateWildlife(bytes + 9, GENERATED_WILDLIFE_BYTES)
              && GeneratedMap_StageTemplate(bytes + 9 + GENERATED_WILDLIFE_BYTES, GENERATED_MAP_TEMPLATE_BYTES))
            valid = GeneratedMap_SetEncounterProfile(bytes[8])
                 && GeneratedMap_SetWildlife(bytes + 9, GENERATED_WILDLIFE_BYTES);
#endif
#if GENERATED_MAP_LARGE
        else if (count == 8 + GENERATED_LARGE_MAP_TEMPLATE_BYTES && !memcmp(bytes, magic4, 8))
            valid = GeneratedMap_StageLargeTemplate(bytes + 8, GENERATED_LARGE_MAP_TEMPLATE_BYTES);
#if GENERATED_MAP_WILDS
        else if (count == 8 + GENERATED_LARGE_MAP_TEMPLATE_BYTES && !memcmp(bytes, magic6, 8))
            valid = GeneratedMap_StageWildsTemplate(bytes + 8, GENERATED_LARGE_MAP_TEMPLATE_BYTES);
#if GENERATED_WORLD_XL
        else if (count == 8 + GENERATED_XL_MAP_BYTES && !memcmp(bytes, magicXL, 8))
            valid = GeneratedMap_StageXLWilds(bytes + 8, GENERATED_XL_MAP_BYTES);
        else if (count == 8 + GENERATED_XL_MAP_BYTES && !memcmp(bytes, magicXLPalette, 8))
            valid = GeneratedMap_StageXLPalette(bytes + 8, GENERATED_XL_MAP_BYTES);
#if GENERATED_WILDS_CAST
        else if (count == 8 + GENERATED_CAST_BYTES + GENERATED_XL_MAP_BYTES && !memcmp(bytes, magicXLCast, 8))
            valid = GeneratedMap_StageXLCast(bytes + 8, GENERATED_CAST_BYTES, bytes + 8 + GENERATED_CAST_BYTES, GENERATED_XL_MAP_BYTES);
#if GENERATED_WILDS_EVENTS
        else if (count == 8 + GENERATED_EVENT_BYTES + GENERATED_CAST_BYTES + GENERATED_XL_MAP_BYTES && !memcmp(bytes, magicXLEvents, 8))
            valid = GeneratedMap_StageXLEvents(bytes + 8, GENERATED_EVENT_BYTES, bytes + 8 + GENERATED_EVENT_BYTES, GENERATED_CAST_BYTES, bytes + 8 + GENERATED_EVENT_BYTES + GENERATED_CAST_BYTES, GENERATED_XL_MAP_BYTES);
        else if (count == 8 + GENERATED_EVENT_BYTES + GENERATED_CAST_BYTES + GENERATED_XL_MAP_BYTES && !memcmp(bytes, magicXLPaintedEvents, 8))
            valid = GeneratedMap_StageXLPaintedEvents(bytes + 8, GENERATED_EVENT_BYTES, bytes + 8 + GENERATED_EVENT_BYTES, GENERATED_CAST_BYTES, bytes + 8 + GENERATED_EVENT_BYTES + GENERATED_CAST_BYTES, GENERATED_XL_MAP_BYTES);
#endif
#endif
#endif
#if GENERATED_WILDS_GUIDE
        else if (count == 8 + GENERATED_GUIDE_BYTES + GENERATED_LARGE_MAP_TEMPLATE_BYTES && !memcmp(bytes, magic7, 8))
            valid = GeneratedMap_StageGuidedWilds(bytes + 8, GENERATED_GUIDE_BYTES, bytes + 8 + GENERATED_GUIDE_BYTES, GENERATED_LARGE_MAP_TEMPLATE_BYTES);
#if GENERATED_WILDS_CAST
        else if (count == 8 + GENERATED_CAST_BYTES + GENERATED_LARGE_MAP_TEMPLATE_BYTES && !memcmp(bytes, magic8, 8))
            valid = GeneratedMap_StageCastWilds(bytes + 8, GENERATED_CAST_BYTES, bytes + 8 + GENERATED_CAST_BYTES, GENERATED_LARGE_MAP_TEMPLATE_BYTES);
#if GENERATED_WILDS_EVENTS
        else if (count == 8 + GENERATED_EVENT_BYTES + GENERATED_CAST_BYTES + GENERATED_LARGE_MAP_TEMPLATE_BYTES && !memcmp(bytes, magic9, 8))
            valid = GeneratedMap_StageEventWilds(bytes + 8, GENERATED_EVENT_BYTES, bytes + 8 + GENERATED_EVENT_BYTES, GENERATED_CAST_BYTES, bytes + 8 + GENERATED_EVENT_BYTES + GENERATED_CAST_BYTES, GENERATED_LARGE_MAP_TEMPLATE_BYTES);
#endif
#endif
#endif
#endif
#if GENERATED_CAVE_WILDLIFE
        else if (count == 9 + GENERATED_WILDLIFE_BYTES + GENERATED_LARGE_MAP_TEMPLATE_BYTES
              && !memcmp(bytes, magic5, 8) && bytes[8] <= 3
              && GeneratedMap_ValidateWildlife(bytes + 9, GENERATED_WILDLIFE_BYTES)
              && GeneratedMap_StageLargeTemplate(bytes + 9 + GENERATED_WILDLIFE_BYTES, GENERATED_LARGE_MAP_TEMPLATE_BYTES))
            valid = GeneratedMap_SetEncounterProfile(bytes[8])
                 && GeneratedMap_SetWildlife(bytes + 9, GENERATED_WILDLIFE_BYTES);
#endif
#endif
    }
    if (fclose(file) != 0) valid = FALSE;
    return valid;
}

bool8 Platform_ReloadGeneratedMap(void)
{
    return !sGeneratedMapPath || LoadGeneratedMapTemplate(sGeneratedMapPath);
}

int main(int argc, char **argv)
{
    if (!ParseArgs(argc, argv))
        return 1;
    if (sGeneratedProgress && !sGeneratedMapPath)
    {
        fprintf(stderr, "Generated story progress requires an offline generated map.\n");
        return 1;
    }
    if (sGeneratedMapPath && (sWorldConfigPath || !LoadGeneratedMapTemplate(sGeneratedMapPath)))
    {
        fprintf(stderr, "Generated map unavailable: use a valid offline template and enable the experimental feature.\n");
        return 1;
    }

    if (sPlayerControlPath != NULL && sTestMode)
    {
        fprintf(stderr, "Player control requires real-time graphical mode.\n");
        return 1;
    }
    if (!PlayerControl_Init(sPlayerControlPath, sSavePath, WriteTestState, PlayerScreenshot))
        return 1;

    if (!WorldBridge_Init(sWorldConfigPath))
        return 1;
    if (!LinkTransport_Init(sWorldConfigPath))
        return 1;
    if (sWorldInputPath != NULL || sWorldShotPath != NULL)
    {
        if (!WorldBridge_Enabled() || sTestMode || sWorldInputPath == NULL)
        {
            fprintf(stderr, "World bootstrap requires --world-config and --world-input in graphical mode.\n");
            return 1;
        }
        sTestInput = NativeFile_Open(sWorldInputPath, "r");
        if (sTestInput == NULL)
        {
            fprintf(stderr, "Could not open world bootstrap input.\n");
            return 1;
        }
        sWorldBootstrap = true;
    }

    // Open an output console on Windows. The test mode keeps stdout, which the
    // headless tests can read the game's state from.
#ifdef _WIN32
    if (!sTestMode)
    {
        AllocConsole() ;
        AttachConsole( GetCurrentProcessId() ) ;
        freopen( "CON", "w", stdout ) ;
    }
#endif

    // The test mode only uses files it's given, apart from the save
    if (!sTestMode)
        FindDataFiles();
    else if (sSavePath == NULL)
        sSavePath = "pokeemerald.sav";
    LoadSettings(sSettingsPath);
    if (!ReadSaveFile(sSavePath))
    {
        fprintf(stderr, "Could not open the trainer save.\n");
#ifndef _WIN32
        fprintf(stderr, "%s\n", NativeSave_OpenError());
#endif
        return 1;
    }
    DexNavNative_Init(sSavePath, !sTestMode);
    if (sGeneratedProgress && !GeneratedMap_InitXLProgress(sSavePath, TRUE))
        fprintf(stderr, "Generated story progress is session-only: private sidecar unavailable.\n");
    // Before AgbMain, whose RtcInit reads it
    InitInternalClock();

    if (sTestMode)
        return RunTestMode();

    if(SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO | SDL_INIT_GAMECONTROLLER) < 0)
    {
        DBGPRINTF("SDL could not initialize! SDL_Error: %s\n", SDL_GetError());
        return 1;
    }

    // Text events belong only to an explicitly opened chat composer. SDL may
    // otherwise queue the opening T as draft content before the first open.
    SDL_StopTextInput();

    // Mappings for controllers SDL doesn't know, from https://github.com/mdqinc/SDL_GameControllerDB
    {
        char path[1024];
        FILE *mappings;

        snprintf(path, sizeof(path), "%sgamecontrollerdb.txt", sDataDir);
        mappings = NativeFile_Open(path, "r");
        if (mappings != NULL)
        {
            fclose(mappings);
            if (SDL_GameControllerAddMappingsFromFile(path) < 0)
                fprintf(stderr, "Could not read %s: %s\n", path, SDL_GetError());
        }
    }

    videoScale = gSettings.scale;
    sdlWindow = SDL_CreateWindow(WindowTitle(), SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED, DISPLAY_WIDTH * videoScale, WindowHeight() * videoScale,
                                 SDL_WINDOW_SHOWN | SDL_WINDOW_RESIZABLE | (gSettings.fullscreen ? SDL_WINDOW_FULLSCREEN_DESKTOP : 0));
    if (sdlWindow == NULL)
    {
        DBGPRINTF("Window could not be created! SDL_Error: %s\n", SDL_GetError());
        return 1;
    }

    sdlRenderer = SDL_CreateRenderer(sdlWindow, -1, SDL_RENDERER_PRESENTVSYNC);
    if (sdlRenderer == NULL)
    {
        DBGPRINTF("Renderer could not be created! SDL_Error: %s\n", SDL_GetError());
        return 1;
    }

    SDL_SetRenderDrawColor(sdlRenderer, 255, 255, 255, 255);
    SDL_RenderClear(sdlRenderer);
    SDL_SetHint(SDL_HINT_RENDER_SCALE_QUALITY, "0");
    SDL_RenderSetLogicalSize(sdlRenderer, DISPLAY_WIDTH, WindowHeight());
    // Whole pixels only, with borders in fullscreen
    SDL_RenderSetIntegerScale(sdlRenderer, SDL_TRUE);

    sdlTexture = SDL_CreateTexture(sdlRenderer,
                                   SDL_PIXELFORMAT_ABGR1555,
                                   SDL_TEXTUREACCESS_STREAMING,
                                   DISPLAY_WIDTH, DISPLAY_HEIGHT);
    if (sdlTexture == NULL)
    {
        DBGPRINTF("Texture could not be created! SDL_Error: %s\n", SDL_GetError());
        return 1;
    }

    simTime = curGameTime = lastGameTime = SDL_GetPerformanceCounter();

    isFrameAvailable.value = 0;
    vBlankSemaphore = SDL_CreateSemaphore(0);

    SDL_AudioSpec want;

    SDL_memset(&want, 0, sizeof(want)); /* or SDL_zero(want) */
    want.freq = AUDIO_SAMPLE_RATE;
    want.format = AUDIO_F32;
    want.channels = 2;
    want.samples = 1024;
    cgb_audio_init(want.freq);


    if (SDL_OpenAudio(&want, 0) < 0)
        SDL_Log("Failed to open audio: %s", SDL_GetError());
    else
    {
        if (want.format != AUDIO_F32) /* we let this one thing change. */
            SDL_Log("We didn't get Float32 audio format.");
        SDL_PauseAudio(0);
    }

    AgbMain();

    double accumulator = 0.0;

    bool isGameStepDrawn = false;
    while (isRunning)
    {
        double deltaTime;

        ProcessEvents();
        LinkTransport_Pump();

        curGameTime = SDL_GetPerformanceCounter();
        deltaTime = (double)((curGameTime - lastGameTime) / (double)SDL_GetPerformanceFrequency());
        deltaTime *= timeScale; //apply speedup

        if (!paused)
        {
            accumulator += deltaTime;

            isGameStepDrawn = false;

            while (accumulator >= fixedTimestep)
            {
                if (!BeginNativeFrame(FALSE))
                {
                    // A network wait is not elapsed game time to catch up later.
                    accumulator = 0;
                    break;
                }
                //run game logic, draw frame and process DMAs and vblank
                WorldBootstrapFrame();
                PlayerControl_BeforeFrame();
                WorldBridge_BeforeFrame(sWorldFrame, FALSE);
                ENTER_VBLANK(); //you must be in VBlank before running a game tick
                if (!RunMainLoop())
                {
                    NativeLink_Reset();
                    // Soft reset: drop the old sound, and start the next frame with MainLoop
                    WorldActivity_Update();
                    WorldBridge_AfterFrame(sWorldFrame++);
                    PlayerControl_AfterFrame(sWorldFrame);
                    SDL_ClearQueuedAudio(1);
                    accumulator -= fixedTimestep;
                    continue;
                }
                WorldActivity_Update();
                WorldBridge_AfterFrame(sWorldFrame++);
                if (!isGameStepDrawn)
                {
                    VDraw(sdlTexture);
                    //SDL_RenderClear(sdlRenderer);
                    isGameStepDrawn = true;
                }
                RunDMAsAndVBlank();
                // The sound engine runs once a frame, like in the GBA's VBlank
                // interrupt, so the music keeps time with the game
                AudioUpdate();
                NativeLink_AfterFrame();

                PlayerControl_AfterFrame(sWorldFrame);

                accumulator -= fixedTimestep;
            }

            if (videoScaleChanged)
            {
                SDL_SetWindowSize(sdlWindow, DISPLAY_WIDTH * videoScale, WindowHeight() * videoScale);
                videoScaleChanged = false;
            }
        }

        lastGameTime = curGameTime;

        {
            SDL_Rect game = {0, WindowHeight() - DISPLAY_HEIGHT, DISPLAY_WIDTH, DISPLAY_HEIGHT};
            SDL_RenderCopy(sdlRenderer, sdlTexture, NULL, &game);
            WorldChat_Draw(sdlRenderer);
        }
        SDL_RenderPresent(sdlRenderer);
    }

    LinkTransport_Close();
    WorldBridge_Close();
    CloseSaveFile();

    SDL_DestroyWindow(sdlWindow);
    PlayerControl_Close();
    SDL_Quit();
    return 0;
}

static bool ReadSaveFile(const char *path)
{
#ifdef _WIN32
    // Keep the platform's existing path handling unchanged.
    sSaveFile = NativeFile_Open(path, "r+b");
    if (sSaveFile == NULL)
        sSaveFile = NativeFile_Open(path, "w+b");
#else
    // Own this inode for the entire game, including each ordinary menu save.
    sSaveFile = NativeSave_Open(path);
#endif
    if (sSaveFile == NULL)
        return false;

    if (fseek(sSaveFile, 0, SEEK_END) != 0)
        goto fail;
    long fileSize = ftell(sSaveFile);
    if (fileSize < 0 || fseek(sSaveFile, 0, SEEK_SET) != 0)
        goto fail;
    size_t bytesToRead = (size_t)fileSize < sizeof(FLASH_BASE) ? (size_t)fileSize : sizeof(FLASH_BASE);
    size_t bytesRead = fread(FLASH_BASE, 1, bytesToRead, sSaveFile);
    if (bytesRead != bytesToRead)
        goto fail;
    memset(FLASH_BASE + bytesRead, 0xFF, sizeof(FLASH_BASE) - bytesRead);
    return true;

fail:
    fclose(sSaveFile);
    sSaveFile = NULL;
    return false;
}

static bool StoreSaveFile(void)
{
#ifndef _WIN32
    return NativeSave_Write(sSaveFile, FLASH_BASE, sizeof(FLASH_BASE));
#else
    if (sSaveFile != NULL)
    {
        fseek(sSaveFile, 0, SEEK_SET);
        fwrite(FLASH_BASE, 1, sizeof(FLASH_BASE), sSaveFile);
        fflush(sSaveFile);
    }
    return true;
#endif
}

bool8 Platform_StoreSaveFile(void)
{
    if (GeneratedMap_IsInside()) return FALSE;
    return StoreSaveFile();
}

void Platform_ReadFlash(u16 sectorNum, u32 offset, u8 *dest, u32 size)
{
    DBGPRINTF("ReadFlash(sectorNum=0x%04X,offset=0x%08X,size=0x%02X)\n",sectorNum,offset,size);
#ifndef _WIN32
    // Reads and writes must agree on the lifetime-owned save, even if its path
    // has been renamed or replaced while this game is running.
    if (!NativeSave_Read(sSaveFile, ((size_t)sectorNum << gFlash->sector.shift) + offset, dest, size))
        puts("Error reading save file.");
#else
    FILE * savefile = NativeFile_Open(sSavePath, "r+b");
    if (savefile == NULL)
    {
        puts("Error opening save file.");
        return;
    }
    if (fseek(savefile, (sectorNum << gFlash->sector.shift) + offset, SEEK_SET))
    {
        fclose(savefile);
        return;
    }
    if (fread(dest, 1, size, savefile) != size)
    {
        fclose(savefile);
        return;
    }
    fclose(savefile);
#endif
}

static u64 HashBytes(u64 hash, const void *data, size_t size)
{
    const u8 *bytes = data;

    // FNV-1a
    for (size_t i = 0; i < size; i++)
        hash = (hash ^ bytes[i]) * 0x100000001B3ull;
    return hash;
}

void Platform_QueueAudio(float *audioBuffer, s32 samplesPerFrame)
{
    if (sTestMode)
    {
        sTestAudioHash = HashBytes(sTestAudioHash, audioBuffer, samplesPerFrame);
        if (sTestAudio != NULL)
            fwrite(audioBuffer, 1, samplesPerFrame, sTestAudio);
    }
    else
    {
        // The game makes a frame of sound every frame, and the device plays it
        // at the same rate, so the queue only needs fixing when the two come
        // apart. After a stall it runs dry: start it again with a little silence
        // in front, so the next frames don't run dry too. When the game gets
        // ahead, like when it's sped up, drop what can't be played in time.
        static const float sSilence[MIXED_AUDIO_BUFFER_SIZE * 2];
        Uint32 queued = SDL_GetQueuedAudioSize(1);

        if (queued > (Uint32)samplesPerFrame * 8)
            return;
        if (queued == 0)
        {
            for (int i = 0; i < 3; i++)
                SDL_QueueAudio(1, sSilence, samplesPerFrame);
        }
        SDL_QueueAudio(1, audioBuffer, samplesPerFrame);
    }
}


static void CloseSaveFile()
{
    if (sSaveFile != NULL)
    {
        fclose(sSaveFile);
        sSaveFile = NULL;
    }
}

// The GBA buttons in the headless test mode, from its input file
static u16 sTestButtons;

void ProcessEvents(void)
{
    SDL_Event event;

    while (SDL_PollEvent(&event))
    {
        if (sPlayerControlPath == NULL && WorldChat_Event(&event)) continue;
        switch (event.type)
        {
        case SDL_QUIT:
            isRunning = false;
            break;
        case SDL_KEYDOWN:
            switch (event.key.keysym.sym)
            {
            case SDLK_r:
                if (sPlayerControlPath == NULL && (event.key.keysym.mod & (KMOD_LCTRL | KMOD_RCTRL)))
                {
                    RequestSoftReset();
                }
                break;
            case SDLK_p:
                if (sPlayerControlPath == NULL && (event.key.keysym.mod & (KMOD_LCTRL | KMOD_RCTRL)))
                {
                    paused = !paused;
                }
                break;
            case SDLK_F11:
                ToggleFullscreen();
                break;
            }
            break;
        case SDL_CONTROLLERDEVICEADDED:
        case SDL_CONTROLLERDEVICEREMOVED:
            Input_HandleEvent(&event);
            break;
        case SDL_WINDOWEVENT:
            // Keep the window a whole multiple of the GBA screen
            if (event.window.event == SDL_WINDOWEVENT_SIZE_CHANGED
             && !(SDL_GetWindowFlags(sdlWindow) & SDL_WINDOW_FULLSCREEN))
            {
                unsigned int w = event.window.data1;
                unsigned int h = event.window.data2;
                
                videoScale = 0;
                if (w / DISPLAY_WIDTH > videoScale)
                    videoScale = w / DISPLAY_WIDTH;
                if (h / WindowHeight() > videoScale)
                    videoScale = h / WindowHeight();
                if (videoScale < 1)
                    videoScale = 1;

                videoScaleChanged = true;
            }
            break;
        }
    }

    // Physical speed-up belongs to the human window, never the AI controller.
    speedUp = false;
    if (sPlayerControlPath == NULL && !WorldChat_BlocksInput())
        Input_GetButtons(&speedUp);
    timeScale = speedUp ? 5.0 : 1.0;
}

static void ToggleFullscreen(void)
{
    bool fullscreen = !(SDL_GetWindowFlags(sdlWindow) & SDL_WINDOW_FULLSCREEN);

    SDL_SetWindowFullscreen(sdlWindow, fullscreen ? SDL_WINDOW_FULLSCREEN_DESKTOP : 0);
}

u16 Platform_GetKeyInput(void)
{
    if (sTestMode || sWorldBootstrap)
        return sTestButtons;
    // A configured AI controller owns its input even while idle or disconnected.
    if (sPlayerControlPath != NULL)
        return PlayerControl_Buttons();
    if (WorldChat_BlocksInput()) return 0;
    return Input_GetButtons(NULL);
}

void VDraw(SDL_Texture *texture)
{
    static uint16_t image[DISPLAY_WIDTH * DISPLAY_HEIGHT];

    memset(image, 0, sizeof(image));
    DrawFrame(image);
    SDL_UpdateTexture(texture, NULL, image, DISPLAY_WIDTH * sizeof (Uint16));
    REG_VCOUNT = 161; // prep for being in VBlank period
}

int DoMain(void *data)
{
    AgbMain();
    return 0;
}

void VBlankIntrWait(void)
{
    return;
}

u8 BinToBcd(u8 bin)
{
    int placeCounter = 1;
    u8 out = 0;
    do
    {
        out |= (bin % 10) * placeCounter;
        placeCounter *= 16;
    }
    while ((bin /= 10) > 0);

    return out;
}

void Platform_GetStatus(struct SiiRtcInfo *rtc)
{
    rtc->status = internalClock.status;
}

void Platform_SetStatus(struct SiiRtcInfo *rtc)
{
    internalClock.status = rtc->status;
}

static void InitInternalClock(void)
{
    memset(&internalClock, 0, sizeof(internalClock));
    internalClock.status = SIIRTCINFO_24HOUR;
    UpdateInternalClock();
}

static void UpdateInternalClock(void)
{
    struct tm *now;

    if (sTestMode)
    {
        // Deterministic clock: advances one second every 60 frames
        time_t rawTime = sTestClockBase + sTestFrame / 60;
        now = gmtime(&rawTime);
    }
    else
    {
        time_t rawTime = time(NULL);
        now = localtime(&rawTime);
    }

    internalClock.year = BinToBcd(now->tm_year - 100);
    internalClock.month = BinToBcd(now->tm_mon + 1);
    internalClock.day = BinToBcd(now->tm_mday);
    internalClock.dayOfWeek = BinToBcd(now->tm_wday);
    internalClock.hour = BinToBcd(now->tm_hour);
    internalClock.minute = BinToBcd(now->tm_min);
    internalClock.second = BinToBcd(now->tm_sec);
}

void Platform_GetDateTime(struct SiiRtcInfo *rtc)
{
    UpdateInternalClock();

    rtc->year = internalClock.year;
    rtc->month = internalClock.month;
    rtc->day = internalClock.day;
    rtc->dayOfWeek = internalClock.dayOfWeek;
    rtc->hour = internalClock.hour;
    rtc->minute = internalClock.minute;
    rtc->second = internalClock.second;
    DBGPRINTF("GetDateTime: %d-%02d-%02d %02d:%02d:%02d\n", ConvertBcdToBinary(rtc->year),
                                                         ConvertBcdToBinary(rtc->month),
                                                         ConvertBcdToBinary(rtc->day),
                                                         ConvertBcdToBinary(rtc->hour),
                                                         ConvertBcdToBinary(rtc->minute),
                                                         ConvertBcdToBinary(rtc->second));
}

void Platform_SetDateTime(struct SiiRtcInfo *rtc)
{
    internalClock.month = rtc->month;
    internalClock.day = rtc->day;
    internalClock.dayOfWeek = rtc->dayOfWeek;
    internalClock.hour = rtc->hour;
    internalClock.minute = rtc->minute;
    internalClock.second = rtc->second;
}

void Platform_GetTime(struct SiiRtcInfo *rtc)
{
    UpdateInternalClock();

    rtc->hour = internalClock.hour;
    rtc->minute = internalClock.minute;
    rtc->second = internalClock.second;
    DBGPRINTF("GetTime: %02d:%02d:%02d\n", ConvertBcdToBinary(rtc->hour),
                                        ConvertBcdToBinary(rtc->minute),
                                        ConvertBcdToBinary(rtc->second));
}

void Platform_SetTime(struct SiiRtcInfo *rtc)
{
    internalClock.hour = rtc->hour;
    internalClock.minute = rtc->minute;
    internalClock.second = rtc->second;
}

void Platform_SetAlarm(u8 *alarmData)
{
    // The game never sets an alarm
}

// All options take a value. Anything else is ignored, like before there were
// options, so e.g. a file dropped onto the executable doesn't stop the game.
static bool ParseArgs(int argc, char **argv)
{
    for (int i = 1; i < argc; i++)
    {
        const char *arg = argv[i];
        const char *value = (i + 1 < argc) ? argv[i + 1] : NULL;

        if ((!value || !strncmp(value, "--", 2)) && !strcmp(arg, "--player-control"))
        {
            fprintf(stderr, "Missing player control option value.\n");
            return false;
        }
        if (value == NULL && (!strcmp(arg, "--world-config") || !strcmp(arg, "--world-input") || !strcmp(arg, "--world-shot") || !strcmp(arg, "--generated-map") || !strcmp(arg, "--generated-progress")))
        {
            fprintf(stderr, "Missing world option value.\n");
            return false;
        }
        if (strncmp(arg, "--", 2) != 0 || value == NULL)
        {
            fprintf(stderr, "Ignoring argument: %s\n", arg);
            continue;
        }
        i++;

        if (strcmp(arg, "--save") == 0)
        {
            sSavePath = value;
        }
        else if (strcmp(arg, "--player-control") == 0)
        {
            if (sPlayerControlPath != NULL)
                return false;
            sPlayerControlPath = value;
        }
        else if (strcmp(arg, "--generated-map") == 0)
        {
            if (sGeneratedMapPath != NULL || !strncmp(value, "--", 2)) return false;
            sGeneratedMapPath = value;
        }
        else if (strcmp(arg, "--generated-progress") == 0)
        {
            if (sGeneratedProgress || strcmp(value,"on")) return false;
            sGeneratedProgress = true;
        }
        else if (strcmp(arg, "--world-config") == 0)
        {
            sWorldConfigPath = value;
        }
        else if (strcmp(arg, "--world-input") == 0)
        {
            sWorldInputPath = value;
        }
        else if (strcmp(arg, "--world-shot") == 0)
        {
            sWorldShotPath = value;
        }
        else if (strcmp(arg, "--config") == 0)
        {
            sSettingsPath = value;
        }
        else if (strcmp(arg, "--test-input") == 0)
        {
            sTestMode = true;
            sTestInput = (strcmp(value, "-") == 0) ? stdin : NativeFile_Open(value, "r");
            if (sTestInput == NULL)
            {
                fprintf(stderr, "Could not open test input %s\n", value);
                return false;
            }
        }
        else if (strcmp(arg, "--test-hashes") == 0)
        {
            sTestHashes = NativeFile_Open(value, "w");
            if (sTestHashes == NULL)
            {
                fprintf(stderr, "Could not open hash output %s\n", value);
                return false;
            }
        }
        else if (strcmp(arg, "--test-shots") == 0)
        {
            sTestShotDir = value;
        }
        else if (strcmp(arg, "--test-state") == 0)
        {
            sTestState = (strcmp(value, "-") == 0) ? stdout : NativeFile_Open(value, "w");
            if (sTestState == NULL)
            {
                fprintf(stderr, "Could not open state output %s\n", value);
                return false;
            }
        }
        else if (strcmp(arg, "--test-audio") == 0)
        {
            sTestAudio = NativeFile_Open(value, "wb");
            if (sTestAudio == NULL)
            {
                fprintf(stderr, "Could not open audio output %s\n", value);
                return false;
            }
            WriteWavHeader(sTestAudio, 0);
        }
        else if (strcmp(arg, "--test-shot-every") == 0)
        {
            sTestShotEvery = strtoul(value, NULL, 10);
        }
        else if (strcmp(arg, "--test-time") == 0)
        {
            sTestClockBase = strtoll(value, NULL, 10);
        }
        else
        {
            fprintf(stderr, "Ignoring unknown option: %s %s\n", arg, value);
        }
    }
    return true;
}

// The save and the settings go in the user's data folder, unless there's a save
// in the current directory, where earlier versions kept it
static void FindDataFiles(void)
{
    static char savePath[1024], settingsPath[1024];
    FILE *oldSave = NativeFile_Open("pokeemerald.sav", "rb");

    if (oldSave != NULL)
        fclose(oldSave);
    else
        sDataDir = SDL_GetPrefPath("", "pokeemerald");
    if (sDataDir == NULL)
        sDataDir = SDL_strdup("");

    if (sSavePath == NULL)
    {
        snprintf(savePath, sizeof(savePath), "%spokeemerald.sav", sDataDir);
        sSavePath = savePath;
    }
    if (sSettingsPath == NULL)
    {
        snprintf(settingsPath, sizeof(settingsPath), "%spokeemerald.ini", sDataDir);
        sSettingsPath = settingsPath;
    }
    printf("Save file: %s\nSettings: %s\n", sSavePath, sSettingsPath);
}

// Reads the keys to hold for the next frame from the test input. Each line is
// "<frames> <buttons>", where buttons is "-" or names joined by '+', e.g.
// "30 A+UP". Besides the GBA buttons, names can be keys and controller inputs,
// which go through the bindings in the settings, like "key:Z" or "pad:lefty-".
// Lines starting with '#' are ignored. Returns false at the end.
static bool ReadTestInput(u16 *outKeys)
{
    static const struct { const char *name; u16 key; } sButtons[] = {
        {"A", A_BUTTON}, {"B", B_BUTTON}, {"SELECT", SELECT_BUTTON}, {"START", START_BUTTON},
        {"RIGHT", DPAD_RIGHT}, {"LEFT", DPAD_LEFT}, {"UP", DPAD_UP}, {"DOWN", DPAD_DOWN},
        {"R", R_BUTTON}, {"L", L_BUTTON},
    };
    static u32 sHoldFrames;
    static u16 sHoldKeys;
    static bool sStateWritten;
    char line[256];

    while (sHoldFrames == 0)
    {
        char buttons[200];

        // The state after the last line's frames, for a driver that decides
        // what to press next from it (see test/headless/driver.py)
        if (sTestState != NULL && !sStateWritten)
        {
            WriteTestState(sTestState, sTestFrame);
            sStateWritten = true;
        }
        if (fgets(line, sizeof(line), sTestInput) == NULL)
            return false;
        if (line[0] == '#' || sscanf(line, "%u %199s", &sHoldFrames, buttons) != 2)
        {
            sHoldFrames = 0;
            continue;
        }

        sStateWritten = false;
        sHoldKeys = 0;
        Input_ReleaseTestInputs();
        for (char *name = strtok(buttons, "+"); name != NULL; name = strtok(NULL, "+"))
        {
            size_t i;

            if (strcmp(name, "-") == 0 || Input_PressTestInput(name))
                continue;
            for (i = 0; i < ARRAY_COUNT(sButtons); i++)
            {
                if (strcmp(name, sButtons[i].name) == 0)
                {
                    sHoldKeys |= sButtons[i].key;
                    break;
                }
            }
            if (i == ARRAY_COUNT(sButtons))
                fprintf(stderr, "Unknown button in test input: %s\n", name);
        }
    }

    sHoldFrames--;
    *outKeys = sHoldKeys | Input_GetTestButtons();
    return true;
}

// A WAV file header for the test mode's audio: 32-bit float stereo, with
// dataSize bytes of samples after it
static void WriteWavHeader(FILE *file, u32 dataSize)
{
    u8 header[44];
    u32 fields[] = {36 + dataSize, 16, 3 | (2 << 16), AUDIO_SAMPLE_RATE, AUDIO_SAMPLE_RATE * 8, 8 | (32 << 16), dataSize};

    memcpy(header, "RIFF", 4);
    memcpy(header + 8, "WAVEfmt ", 8);
    memcpy(header + 36, "data", 4);
    // Little-endian, like every platform the port runs on
    memcpy(header + 4, &fields[0], 4);
    memcpy(header + 16, &fields[1], 16);
    memcpy(header + 32, &fields[5], 4);
    memcpy(header + 40, &fields[6], 4);
    fwrite(header, 1, sizeof(header), file);
}

static void WriteFramebufferPPM(const uint16_t *image, const char *path)
{
    FILE *file = NativeFile_Open(path, "wb");
    if (file == NULL)
    {
        fprintf(stderr, "Could not write screenshot %s\n", path);
        return;
    }

    WriteFramebufferStream(image, file);
    fclose(file);
}

static bool WriteFramebufferStream(const uint16_t *image, FILE *file)
{
    fprintf(file, "P6\n%d %d\n255\n", DISPLAY_WIDTH, DISPLAY_HEIGHT);
    for (int i = 0; i < DISPLAY_WIDTH * DISPLAY_HEIGHT; i++)
    {
        // ABGR1555
        u8 rgb[3] = {
            (image[i] & 0x1F) << 3,
            ((image[i] >> 5) & 0x1F) << 3,
            ((image[i] >> 10) & 0x1F) << 3,
        };
        fwrite(rgb, 1, sizeof(rgb), file);
    }
    return !ferror(file);
}

static bool PlayerScreenshot(FILE *file)
{
    static uint16_t image[DISPLAY_WIDTH * DISPLAY_HEIGHT];
    memset(image, 0, sizeof(image));
    DrawFrame(image);
    return WriteFramebufferStream(image, file);
}

static void WriteTestScreenshot(const uint16_t *image)
{
    char path[512];
    snprintf(path, sizeof(path), "%s/frame_%06u.ppm", sTestShotDir, sTestFrame);
    WriteFramebufferPPM(image, path);
}

// Graphical bootstrap uses the same input grammar, without changing the clock,
// SDL setup or normal frame cadence. Human keyboard control resumes at EOF.
static void WorldBootstrapFrame(void)
{
    static uint16_t image[DISPLAY_WIDTH * DISPLAY_HEIGHT];
    if (!sWorldBootstrap || ReadTestInput(&sTestButtons))
        return;
    if (sWorldShotPath != NULL)
    {
        memset(image, 0, sizeof(image));
        DrawFrame(image);
        WriteFramebufferPPM(image, sWorldShotPath);
    }
    fclose(sTestInput);
    sTestInput = NULL;
    sWorldBootstrap = false;
    sTestButtons = 0;
    Input_ReleaseTestInputs();
}

// Runs the game without a window or audio device until the test input ends.
// Every frame runs one audio update and uses a fixed clock, so the output only
// depends on the input and the save file. Writes "<frame> <video hash> <audio
// hash>" per frame, which lets two builds be compared frame by frame.
static int RunTestMode(void)
{
    static uint16_t image[DISPLAY_WIDTH * DISPLAY_HEIGHT];

    cgb_audio_init(AUDIO_SAMPLE_RATE);
    AgbMain();

    for (sTestFrame = 0; ReadTestInput(&sTestButtons); sTestFrame++)
    {
        bool ranFrame;

        while (!BeginNativeFrame(TRUE))
        {
#ifdef _WIN32
            Sleep(1);
#else
            struct timespec delay = {0, 1000000};
            nanosleep(&delay, NULL);
#endif
        }
        WorldBridge_BeforeFrame(sTestFrame, TRUE);
        ENTER_VBLANK();
        ranFrame = RunMainLoop();
        WorldActivity_Update();
        WorldBridge_AfterFrame(sTestFrame);
        memset(image, 0, sizeof(image));
        DrawFrame(image);
        REG_VCOUNT = 161;
        sTestAudioHash = 0xCBF29CE484222325ull;
        // After a soft reset, the next frame starts with MainLoop, like at startup
        if (ranFrame)
        {
            RunDMAsAndVBlank();
            AudioUpdate();
            NativeLink_AfterFrame();
        }
        else
            NativeLink_Reset();

        if (sTestHashes != NULL)
            fprintf(sTestHashes, "%u %016llx %016llx\n", sTestFrame,
                    (unsigned long long)HashBytes(0xCBF29CE484222325ull, image, sizeof(image)),
                    (unsigned long long)sTestAudioHash);
        if (sTestShotDir != NULL && sTestShotEvery != 0 && sTestFrame % sTestShotEvery == 0)
            WriteTestScreenshot(image);
    }

    if (sTestShotDir != NULL)
        WriteTestScreenshot(image);
    if (sTestHashes != NULL)
        fclose(sTestHashes);
    if (sTestAudio != NULL)
    {
        long size = ftell(sTestAudio);

        fseek(sTestAudio, 0, SEEK_SET);
        WriteWavHeader(sTestAudio, size - 44);
        fclose(sTestAudio);
    }
    fclose(sTestInput);
    LinkTransport_Close();
    WorldBridge_Close();
    CloseSaveFile();
    return 0;
}
#endif // PORTABLE
