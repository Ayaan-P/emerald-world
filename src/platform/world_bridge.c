#ifdef PORTABLE
#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <winsock2.h>
#include <windows.h>
#endif
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <errno.h>
#include <limits.h>
#include "platform/native_file.h"
#include "global.h"
#include "global.fieldmap.h"
#include "fieldmap.h"
#include "field_camera.h"
#include "event_object_movement.h"
#include "main.h"
#include "overworld.h"
#include "palette.h"
#include "script.h"
#include "field_message_box.h"
#include "pokemon.h"
#include "sprite.h"
#include "constants/event_objects.h"
#include "constants/map_groups.h"
#include "platform/world_bridge.h"
#include "platform/world_activity.h"
#include "platform/world_catalog.h"
#ifndef _WIN32
#include <unistd.h>
#include <fcntl.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <poll.h>
#endif

#define WB_PEERS 8
#define WB_OBJECTS 8
#define WB_REMOTES (WB_PEERS + WB_OBJECTS)
#define WB_TILES 128
#define WB_BUFFER 65536
#define WB_LOCALID 224
#define WB_MARKER 0x5742

struct Peer { char id[26], text[58]; unsigned group, num, x, y, facing, gfx, ready; };
struct Tile { unsigned group, num, x, y, metatile, collision; };
struct Meeting { unsigned seq, group, num, x, y; char player[25], target[25]; };
struct Snapshot {
    unsigned revision, peerCount, tileCount, objectCount;
    struct Peer peers[WB_REMOTES];
    struct Tile tiles[WB_TILES];
    struct Meeting meeting;
};
struct Remote { char id[26]; u8 object, sprite, group, num; };
struct Applied { struct Tile tile; u16 original, raw; };
static struct {
    bool8 enabled, connected, connecting, staging;
#ifdef _WIN32
    SOCKET fd;
    bool8 winsockStarted;
    unsigned loopbackPort;
    char loopbackToken[65];
#else
    int fd;
#endif
    char socketPath[108], trainer[25], token[65], telemetry[1024];
    char input[WB_BUFFER], output[4096];
    size_t inputSize, outputSize, outputSent;
    unsigned seq, retry, stagedBytes, generation, appliedGeneration;
    bool8 tilesLive;
    struct Snapshot live, stage;
    struct Remote remotes[WB_REMOTES];
    bool8 dialogueActive;
    u16 previousKeys, dialogueKeys;
    char pendingObject[26], dialogueObject[25], dialogueLiteral[58];
    unsigned interactionSeq;
    unsigned shownMeeting, dialogueMeeting, meetingAge, socialCooldown;
    u8 dialogueText[58];
    struct Applied applied[WB_TILES], restored[WB_TILES];
    unsigned appliedCount, restoredCount;
    const struct MapLayout *layout;
    u16 *grid;
    int group, num;
} sWorld;

static bool8 Identifier(const char *s)
{
    size_t i, n = strlen(s);
    if (!n || n > 24) return FALSE;
    for (i = 0; i < n; i++)
        if (!((s[i] >= 'a' && s[i] <= 'z') || (s[i] >= 'A' && s[i] <= 'Z')
           || (s[i] >= '0' && s[i] <= '9') || s[i] == '_' || s[i] == '-')) return FALSE;
    return TRUE;
}

static bool8 Decimal(const char *s, unsigned *value)
{
    unsigned n = 0;
    if (!*s) return FALSE;
    for (; *s; s++) {
        if (*s < '0' || *s > '9' || n > (UINT_MAX - (*s - '0')) / 10) return FALSE;
        n = n * 10 + (*s - '0');
    }
    *value = n;
    return TRUE;
}

/* Decode only literal supported glyphs, never engine text commands. */
static bool8 ObjectText(const char *hex, char text[58])
{
    size_t i, n = strlen(hex), line = 0, lines = 1;
    if (!n || n % 2 || n > 114) return FALSE;
    for (i = 0; i < n / 2; i++) {
        unsigned value = 0, j;
        char c;
        for (j = 0; j < 2; j++) {
            char h = hex[2*i+j];
            if (h >= '0' && h <= '9') value = value * 16 + h - '0';
            else if (h >= 'a' && h <= 'f') value = value * 16 + h - 'a' + 10;
            else return FALSE;
        }
        c = value;
        if (c == '\n') {
            if (!line || ++lines > 2) return FALSE;
            line = 0;
        } else {
            if (!((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z')
               || (c >= '0' && c <= '9') || (c && strchr(" .,!?'-", c)))) return FALSE;
            if (++line > 28) return FALSE;
        }
        text[i] = c;
    }
    text[i] = 0;
    return line != 0;
}

static void EncodeText(const char *text, u8 *out)
{
    for (; *text; text++, out++) {
        char c = *text;
        if (c >= 'A' && c <= 'Z') *out = 0xBB + c - 'A';
        else if (c >= 'a' && c <= 'z') *out = 0xD5 + c - 'a';
        else if (c >= '0' && c <= '9') *out = 0xA1 + c - '0';
        else switch (c) {
        case '\n': *out = 0xFE; break;
        case '.': *out = 0xAD; break;
        case ',': *out = 0xB8; break;
        case '!': *out = 0xAB; break;
        case '?': *out = 0xAC; break;
        case '\'': *out = 0xB4; break;
        case '-': *out = 0xAE; break;
        default: *out = 0; break;
        }
    }
    *out = 0xFF;
}

/* Generated dimensions reject unknown maps before any engine lookup. */
static bool8 MapCoords(unsigned group, unsigned num, unsigned x, unsigned y)
{
    return WorldCatalog_Coords(group, num, x, y);
}

static bool8 Overworld(void)
{
    return gSaveBlock1Ptr && gMapHeader.mapLayout && gBackupMapLayout.map
        && gPlayerAvatar.objectEventId < OBJECT_EVENTS_COUNT
        && gObjectEvents[gPlayerAvatar.objectEventId].active
        && gObjectEvents[gPlayerAvatar.objectEventId].isPlayer
        && gMain.callback2 == CB2_Overworld && !gMain.inBattle;
}

static bool8 Ready(void)
{
    return Overworld() && !gPaletteFade.active && !ArePlayerFieldControlsLocked()
        && !ScriptContext_IsEnabled() && !gPlayerAvatar.tileTransitionState;
}

static bool8 Owned(unsigned slot)
{
    const struct Remote *r = &sWorld.remotes[slot];
    const struct ObjectEvent *o;
    if (!r->id[0] || r->object >= OBJECT_EVENTS_COUNT || r->sprite >= MAX_SPRITES) return FALSE;
    o = &gObjectEvents[r->object];
    return o->active && !o->isPlayer && o->localId == WB_LOCALID + slot
        && o->mapGroup == r->group && o->mapNum == r->num && o->spriteId == r->sprite
        && gSprites[r->sprite].inUse && gSprites[r->sprite].data[0] == r->object
        && gSprites[r->sprite].data[7] == WB_MARKER;
}

static void RemoveRemote(unsigned slot)
{
    struct Remote *r = &sWorld.remotes[slot];
    if (Owned(slot)) {
#ifdef UBFIX
        /* UBFIX makes the missing map template's flag ID zero, not a NULL dereference. */
        RemoveObjectEventByLocalIdAndMap(WB_LOCALID + slot, r->num, r->group);
#else
        /* Same sprite teardown as RemoveObjectEventInternal, without its template lookup. */
        struct SpriteFrameImage image;
        image.size = GetObjectEventGraphicsInfo(gObjectEvents[r->object].graphicsId)->size;
        gSprites[r->sprite].images = &image;
        DestroySprite(&gSprites[r->sprite]);
        gObjectEvents[r->object].active = FALSE;
#endif
    }
    memset(r, 0, sizeof(*r));
}

static bool8 NativeNpcAt(unsigned x, unsigned y)
{
    unsigned i, j;
    for (i = 0; i < OBJECT_EVENTS_COUNT; i++) {
        const struct ObjectEvent *o = &gObjectEvents[i];
        bool8 remote = FALSE;
        if (!o->active || o->isPlayer || o->currentCoords.x != (int)x + MAP_OFFSET
         || o->currentCoords.y != (int)y + MAP_OFFSET) continue;
        for (j = 0; j < WB_REMOTES; j++)
            if (Owned(j) && sWorld.remotes[j].object == i) remote = TRUE;
        if (!remote) return TRUE;
    }
    return FALSE;
}

static bool8 SameGrid(void)
{
    return gSaveBlock1Ptr && sWorld.grid && sWorld.grid == gBackupMapLayout.map
        && sWorld.layout == gMapHeader.mapLayout
        && sWorld.group == gSaveBlock1Ptr->location.mapGroup
        && sWorld.num == gSaveBlock1Ptr->location.mapNum;
}

static bool8 GridCoords(unsigned x, unsigned y)
{
    return gMapHeader.mapLayout && x < (unsigned)gMapHeader.mapLayout->width
        && y < (unsigned)gMapHeader.mapLayout->height
        && x + MAP_OFFSET < (unsigned)gBackupMapLayout.width
        && y + MAP_OFFSET < (unsigned)gBackupMapLayout.height;
}

static u16 Raw(unsigned x, unsigned y)
{
    return gBackupMapLayout.map[(y + MAP_OFFSET) * gBackupMapLayout.width + x + MAP_OFFSET];
}

static void RestoreTiles(void)
{
    unsigned i;
    if (SameGrid()) for (i = 0; i < sWorld.appliedCount; i++) {
        struct Applied a = sWorld.applied[i];
        if (!GridCoords(a.tile.x, a.tile.y)) continue;
        /* A new map load or a local script owns any changed entry. Don't roll it back. */
        if (Raw(a.tile.x, a.tile.y) != a.raw) continue;
        MapGridSetMetatileEntryAt(a.tile.x + MAP_OFFSET, a.tile.y + MAP_OFFSET, a.original);
        if (Overworld()) CurrentMapDrawMetatileAt(a.tile.x + MAP_OFFSET, a.tile.y + MAP_OFFSET);
        a.raw = Raw(a.tile.x, a.tile.y);
        if (sWorld.restoredCount < WB_TILES) sWorld.restored[sWorld.restoredCount++] = a;
    }
    sWorld.appliedCount = 0;
}

static void Disconnect(void)
{
#ifdef _WIN32
    if (sWorld.fd != INVALID_SOCKET) closesocket(sWorld.fd);
    sWorld.fd = INVALID_SOCKET;
#else
    if (sWorld.fd >= 0) close(sWorld.fd);
    sWorld.fd = -1;
#endif
    sWorld.connected = sWorld.connecting = sWorld.staging = FALSE;
    sWorld.inputSize = sWorld.outputSize = sWorld.outputSent = 0;
    sWorld.retry = 30;
    sWorld.live.peerCount = sWorld.live.tileCount = sWorld.live.objectCount = 0;
    sWorld.pendingObject[0] = 0;
    memset(&sWorld.live.meeting, 0, sizeof(sWorld.live.meeting));
    sWorld.generation++;
}

bool8 WorldBridge_Enabled(void) { return sWorld.enabled; }

const char *WorldBridge_TrainerName(void)
{
    return sWorld.enabled ? sWorld.trainer : NULL;
}

bool8 WorldBridge_Init(const char *configPath)
{
    FILE *file;
    char line[1200], key[32], value[1100];
#ifndef _WIN32
    char extra;
#endif
    unsigned seen = 0, i;
    memset(&sWorld, 0, sizeof(sWorld));
#ifdef _WIN32
    sWorld.fd = INVALID_SOCKET;
#else
    sWorld.fd = -1;
#endif
    if (!configPath) return TRUE;
#ifdef _WIN32
    file = NativeFile_Open(configPath, "rb");
#else
    file = NativeFile_Open(configPath, "r");
#endif
    if (!file) return FALSE;
#ifdef _WIN32
    /* Reject embedded NUL and DOS EOF before C-string parsing can hide bytes. */
    {
        int c;
        while ((c = fgetc(file)) != EOF)
            if ((c < 32 && c != '\t' && c != '\r' && c != '\n') || c == 127) goto invalid;
        if (ferror(file) || fseek(file, 0, SEEK_SET)) goto invalid;
    }
#endif
    while (fgets(line, sizeof(line), file)) {
        unsigned bit;
        char *dest;
        size_t size;
        if ((!strchr(line, '\n') && !feof(file)) || strlen(line) > 1150) goto invalid;
        if (line[0] == '#' || line[0] == '\n') continue;
#ifdef _WIN32
        /* Only this allowlist is accepted. No address or hostname is configurable.
         * Paths consume the remainder so a Windows username may contain spaces. */
        {
            char *p = line, *end;
            size_t n;
            while (*p == ' ' || *p == '\t') p++;
            end = p;
            while (*end && !isspace((unsigned char)*end)) end++;
            n = end - p;
            if (!n || n >= sizeof(key) || !*end) goto invalid;
            memcpy(key, p, n); key[n] = 0;
            p = end;
            while (*p == ' ' || *p == '\t') p++;
            end = p + strlen(p);
            while (end > p && (end[-1] == '\n' || end[-1] == '\r')) end--;
            n = end - p;
            if (!n || n >= sizeof(value)) goto invalid;
            memcpy(value, p, n); value[n] = 0;
            if (strcmp(key, "telemetry"))
                for (p = value; *p; p++) if (isspace((unsigned char)*p)) goto invalid;
        }
        if (!strcmp(key, "loopback_port")) {
            if ((seen & 1) || !Decimal(value, &sWorld.loopbackPort)
             || !sWorld.loopbackPort || sWorld.loopbackPort > 65535) goto invalid;
            seen |= 1;
            continue;
        }
        if (!strcmp(key, "loopback_token")) { bit = 16; dest = sWorld.loopbackToken; size = sizeof(sWorld.loopbackToken); }
#else
        if (sscanf(line, "%31s %1099s %c", key, value, &extra) != 2) goto invalid;
        if (!strcmp(key, "socket")) { bit = 1; dest = sWorld.socketPath; size = sizeof(sWorld.socketPath); }
#endif
        else if (!strcmp(key, "trainer")) { bit = 2; dest = sWorld.trainer; size = sizeof(sWorld.trainer); }
        else if (!strcmp(key, "token")) { bit = 4; dest = sWorld.token; size = sizeof(sWorld.token); }
        else if (!strcmp(key, "telemetry")) { bit = 8; dest = sWorld.telemetry; size = sizeof(sWorld.telemetry); }
        else goto invalid;
        if ((seen & bit) || strlen(value) >= size) goto invalid;
        strcpy(dest, value);
        seen |= bit;
    }
#ifdef _WIN32
    if (seen != 31 || strlen(sWorld.loopbackToken) != 64) goto invalid;
    for (i = 0; i < 64; i++) if (!isxdigit((unsigned char)sWorld.loopbackToken[i])) goto invalid;
#else
    if (seen != 15 || sWorld.socketPath[0] != '/') goto invalid;
#endif
    if (ferror(file) || !Identifier(sWorld.trainer) || strlen(sWorld.token) != 64) goto invalid;
    for (i = 0; i < 64; i++) if (!isxdigit((unsigned char)sWorld.token[i])) goto invalid;
    fclose(file);
#ifdef _WIN32
    {
        WSADATA data;
        if (WSAStartup(MAKEWORD(2, 2), &data)) return FALSE;
        if (data.wVersion != MAKEWORD(2, 2)) { WSACleanup(); return FALSE; }
        sWorld.winsockStarted = TRUE;
    }
#endif
    sWorld.enabled = TRUE;
    return TRUE;
invalid:
    fclose(file);
    fprintf(stderr, "Invalid world configuration.\n");
    return FALSE;
}

/* A snapshot is transactional. Malformed/over-limit frames close the connection
 * without publishing any staged peer or tile. Lines and whole snapshots are bounded. */
static bool8 Line(char *line)
{
    char *tokens[12], *save, *p;
    unsigned v[8], n = 0, i;
    for (p = strtok_r(line, " ", &save); p; p = strtok_r(NULL, " ", &save)) {
        if (n == ARRAY_COUNT(tokens)) return FALSE;
        tokens[n++] = p;
    }
    if (!n) return FALSE;
    if (!sWorld.connected) {
        if (n != 4 || strcmp(tokens[0], "WELCOME") || strcmp(tokens[1], "1")
         || strcmp(tokens[2], sWorld.trainer) || !Decimal(tokens[3], &v[0])) return FALSE;
        sWorld.connected = TRUE;
        sWorld.live.revision = v[0];
        return TRUE;
    }
    if (!strcmp(tokens[0], "BEGIN")) {
        if (n != 2 || sWorld.staging || !Decimal(tokens[1], &v[0]) || v[0] < sWorld.live.revision) return FALSE;
        memset(&sWorld.stage, 0, sizeof(sWorld.stage));
        sWorld.stage.revision = v[0];
        sWorld.staging = TRUE;
        sWorld.stagedBytes = 0;
        return TRUE;
    }
    if (!sWorld.staging) return FALSE;
    if (!strcmp(tokens[0], "END")) {
        if (n != 1) return FALSE;
        if (sWorld.live.meeting.seq != sWorld.stage.meeting.seq) sWorld.meetingAge = 0;
        sWorld.live = sWorld.stage;
        sWorld.generation++;
        sWorld.staging = FALSE;
        return TRUE;
    }
    if (!strcmp(tokens[0], "MEET")) {
        struct Meeting *m = &sWorld.stage.meeting;
        if (n != 9 || m->seq || !Decimal(tokens[1], &v[0]) || !v[0]
         || v[0] > sWorld.stage.revision || !Identifier(tokens[2]) || !Identifier(tokens[3])
         || !strcmp(tokens[2], tokens[3]) || strcmp(tokens[8], "explore")
         || (strcmp(tokens[2], sWorld.trainer) && strcmp(tokens[3], sWorld.trainer))) return FALSE;
        for (i = 1; i < 5; i++) if (!Decimal(tokens[i+3], &v[i])) return FALSE;
        if (!MapCoords(v[1],v[2],v[3],v[4])) return FALSE;
        m->seq=v[0]; m->group=v[1]; m->num=v[2]; m->x=v[3]; m->y=v[4];
        strcpy(m->player,tokens[2]); strcpy(m->target,tokens[3]);
        return TRUE;
    }
    if (!strcmp(tokens[0], "PEER")) {
        struct Peer *peer;
        if (n != 9 || !Identifier(tokens[1]) || !strcmp(tokens[1], sWorld.trainer)
         || sWorld.stage.peerCount - sWorld.stage.objectCount == WB_PEERS) return FALSE;
        for (i = 0; i < 7; i++) if (!Decimal(tokens[i + 2], &v[i])) return FALSE;
        if (!MapCoords(v[0], v[1], v[2], v[3]) || v[4] < 1 || v[4] > 4 || v[5] > 255 || v[6] > 1) return FALSE;
        for (i = 0; i < sWorld.stage.peerCount; i++) if (!strcmp(sWorld.stage.peers[i].id, tokens[1])) return FALSE;
        peer = &sWorld.stage.peers[sWorld.stage.peerCount++];
        strcpy(peer->id, tokens[1]);
        peer->group=v[0]; peer->num=v[1]; peer->x=v[2]; peer->y=v[3];
        peer->facing=v[4]; peer->gfx=v[5]; peer->ready=v[6];
        return TRUE;
    }
    if (!strcmp(tokens[0], "OBJECT")) {
        struct Peer *peer;
        char id[26], text[58];
        if (n != 8 || !Identifier(tokens[1]) || sWorld.stage.objectCount == WB_OBJECTS
         || !ObjectText(tokens[7], text)) return FALSE;
        for (i = 0; i < 5; i++) if (!Decimal(tokens[i + 2], &v[i])) return FALSE;
        if (!MapCoords(v[0], v[1], v[2], v[3]) || (v[4] != 7 && v[4] != 8)) return FALSE;
        snprintf(id, sizeof(id), "@%s", tokens[1]);
        for (i = 0; i < sWorld.stage.peerCount; i++) {
            peer = &sWorld.stage.peers[i];
            if (!strcmp(peer->id, id) || (peer->id[0] == '@' && peer->group == v[0]
             && peer->num == v[1] && peer->x == v[2] && peer->y == v[3])) return FALSE;
        }
        peer = &sWorld.stage.peers[sWorld.stage.peerCount++];
        sWorld.stage.objectCount++;
        strcpy(peer->id, id); strcpy(peer->text, text);
        peer->group=v[0]; peer->num=v[1]; peer->x=v[2]; peer->y=v[3];
        peer->gfx=v[4]; peer->facing=1; peer->ready=1;
        return TRUE;
    }
    if (!strcmp(tokens[0], "TILE")) {
        struct Tile *tile;
        if (n != 7 || sWorld.stage.tileCount == WB_TILES) return FALSE;
        for (i = 0; i < 6; i++) if (!Decimal(tokens[i + 1], &v[i])) return FALSE;
        if (!MapCoords(v[0], v[1], v[2], v[3]) || !WorldCatalog_Metatile(v[0], v[1], v[4]) || v[5] > 1) return FALSE;
        for (i = 0; i < sWorld.stage.tileCount; i++) {
            tile = &sWorld.stage.tiles[i];
            if (tile->group == v[0] && tile->num == v[1] && tile->x == v[2] && tile->y == v[3]) return FALSE;
        }
        tile = &sWorld.stage.tiles[sWorld.stage.tileCount++];
        tile->group=v[0]; tile->num=v[1]; tile->x=v[2]; tile->y=v[3]; tile->metatile=v[4]; tile->collision=v[5];
        return TRUE;
    }
    return FALSE;
}

static bool8 SocketOpen(void)
{
#ifdef _WIN32
    return sWorld.fd != INVALID_SOCKET;
#else
    return sWorld.fd >= 0;
#endif
}

static void QueueHello(void)
{
    sWorld.outputSize = snprintf(sWorld.output, sizeof(sWorld.output),
#ifdef _WIN32
        "EWLOCAL1 %s\nHELLO 1 %s %s SOCIAL\n", sWorld.loopbackToken,
#else
        "HELLO 1 %s %s SOCIAL\n",
#endif
        sWorld.trainer, sWorld.token);
}

static void Flush(void)
{
    while (SocketOpen() && sWorld.outputSent < sWorld.outputSize) {
#ifdef _WIN32
        int n = send(sWorld.fd, sWorld.output + sWorld.outputSent,
                     (int)(sWorld.outputSize - sWorld.outputSent), 0);
        if (n == SOCKET_ERROR) {
            int error = WSAGetLastError();
            if (error == WSAEWOULDBLOCK || error == WSAEINTR) return;
            Disconnect(); return;
        }
#else
        ssize_t n;
#ifdef MSG_NOSIGNAL
        n = send(sWorld.fd, sWorld.output + sWorld.outputSent, sWorld.outputSize - sWorld.outputSent, MSG_NOSIGNAL);
#else
        n = send(sWorld.fd, sWorld.output + sWorld.outputSent, sWorld.outputSize - sWorld.outputSent, 0);
#endif
#endif
        if (n > 0) sWorld.outputSent += n;
#ifndef _WIN32
        else if (n < 0 && (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR)) return;
#endif
        else { Disconnect(); return; }
    }
    if (sWorld.outputSent == sWorld.outputSize) sWorld.outputSent = sWorld.outputSize = 0;
}

static void Connect(void)
{
#ifdef _WIN32
    struct sockaddr_in addr;
    u_long nonblocking = 1;
    int result;
    sWorld.fd = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (!SocketOpen()) { sWorld.retry = 30; return; }
    if (ioctlsocket(sWorld.fd, FIONBIO, &nonblocking) == SOCKET_ERROR) { Disconnect(); return; }
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    addr.sin_port = htons((u_short)sWorld.loopbackPort);
    result = connect(sWorld.fd, (struct sockaddr *)&addr, sizeof(addr));
    if (result == SOCKET_ERROR) {
        int error = WSAGetLastError();
        if (error != WSAEWOULDBLOCK && error != WSAEINPROGRESS && error != WSAEALREADY) {
            Disconnect(); return;
        }
    }
#else
    struct sockaddr_un addr;
    int result;
    sWorld.fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (sWorld.fd < 0) { sWorld.retry = 30; return; }
    if (fcntl(sWorld.fd, F_SETFL, O_NONBLOCK) < 0) { Disconnect(); return; }
    fcntl(sWorld.fd, F_SETFD, FD_CLOEXEC);
#ifdef SO_NOSIGPIPE
    { int one = 1; setsockopt(sWorld.fd, SOL_SOCKET, SO_NOSIGPIPE, &one, sizeof(one)); }
#endif
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strcpy(addr.sun_path, sWorld.socketPath);
    result = connect(sWorld.fd, (struct sockaddr *)&addr, sizeof(addr));
    if (result < 0 && errno != EINPROGRESS) { Disconnect(); return; }
#endif
    sWorld.connecting = result < 0;
    sWorld.seq = 0;
    sWorld.shownMeeting = 0;
    QueueHello();
}

static void Receive(bool8 headless)
{
    unsigned budget = 0;
#ifdef _WIN32
    fd_set reads, writes, errors;
    struct timeval timeout;
    int result;
    FD_ZERO(&reads); FD_ZERO(&writes); FD_ZERO(&errors);
    FD_SET(sWorld.fd, &reads);
    FD_SET(sWorld.fd, &errors);
    if (sWorld.connecting) FD_SET(sWorld.fd, &writes);
    timeout.tv_sec = 0;
    timeout.tv_usec = headless ? 1000 : 0;
    result = select(0, &reads, &writes, &errors, &timeout);
    if (result == SOCKET_ERROR) {
        if (WSAGetLastError() != WSAEINTR) Disconnect();
        return;
    }
    if (sWorld.connecting) {
        int error = 0, len = sizeof(error);
        if (!FD_ISSET(sWorld.fd, &writes) && !FD_ISSET(sWorld.fd, &errors)) return;
        if (getsockopt(sWorld.fd, SOL_SOCKET, SO_ERROR, (char *)&error, &len) == SOCKET_ERROR || error) {
            Disconnect(); return;
        }
        sWorld.connecting = FALSE;
    } else if (FD_ISSET(sWorld.fd, &errors)) { Disconnect(); return; }
#else
    struct pollfd pfd;
    pfd.fd = sWorld.fd;
    pfd.events = POLLIN | (sWorld.connecting ? POLLOUT : 0);
    pfd.revents = 0;
    /* Enabled headless execution yields at most 1 ms per frame to the server. */
    if (poll(&pfd, 1, headless ? 1 : 0) < 0) return;
    if (sWorld.connecting) {
        int error = 0;
        socklen_t len = sizeof(error);
        if (!(pfd.revents & (POLLOUT | POLLERR | POLLHUP))) return;
        if (getsockopt(sWorld.fd, SOL_SOCKET, SO_ERROR, &error, &len) < 0 || error) { Disconnect(); return; }
        sWorld.connecting = FALSE;
    }
#endif
    Flush();
    while (SocketOpen() && budget < WB_BUFFER) {
#ifdef _WIN32
        int n;
#else
        ssize_t n;
#endif
        size_t used = 0, i;
        if (sWorld.inputSize == sizeof(sWorld.input) - 1) { Disconnect(); return; }
        n = recv(sWorld.fd, sWorld.input + sWorld.inputSize, (int)(sizeof(sWorld.input) - 1 - sWorld.inputSize), 0);
        if (n < 0) {
#ifdef _WIN32
            int error = WSAGetLastError();
            if (error != WSAEWOULDBLOCK && error != WSAEINTR) Disconnect();
#else
            if (errno != EAGAIN && errno != EWOULDBLOCK && errno != EINTR) Disconnect();
#endif
            return;
        }
        if (!n) { Disconnect(); return; }
        budget += n;
        for (i = sWorld.inputSize; i < sWorld.inputSize + n; i++)
            if ((unsigned char)sWorld.input[i] < 32 && sWorld.input[i] != '\n') { Disconnect(); return; }
        sWorld.inputSize += n;
        for (i = 0; i < sWorld.inputSize; i++) if (sWorld.input[i] == '\n') {
            sWorld.input[i] = 0;
            if (sWorld.staging) {
                sWorld.stagedBytes += i + 1 - used;
                if (sWorld.stagedBytes > WB_BUFFER) { Disconnect(); return; }
            }
            if (!Line(sWorld.input + used)) { Disconnect(); return; }
            used = i + 1;
        }
        if (used) {
            memmove(sWorld.input, sWorld.input + used, sWorld.inputSize - used);
            sWorld.inputSize -= used;
        }
    }
}

/* The server HASH field is a 16-hex-digit opaque FNV-1a change fingerprint,
 * not a cryptographic integrity claim. Authentication uses the separate token. */
static void Fingerprint(const void *data, size_t size, char out[17])
{
    const u8 *p = data;
    u64 hash = 0xcbf29ce484222325ULL;
    size_t i;
    for (i = 0; i < size; i++) hash = (hash ^ p[i]) * 0x100000001b3ULL;
    snprintf(out, 17, "%016llx", (unsigned long long)hash);
}

static void SendState(void)
{
    const struct ObjectEvent *player = NULL;
    char party[17], bag[17];
    bool8 ready;
    if (!sWorld.connected || sWorld.outputSize) return;
    ready = Ready();
    if (ready) player = &gObjectEvents[gPlayerAvatar.objectEventId];
    Fingerprint(gPlayerParty, sizeof(gPlayerParty), party);
    if (gSaveBlock1Ptr)
        Fingerprint(gSaveBlock1Ptr->bagPocket_Items,
                    sizeof(gSaveBlock1Ptr->bagPocket_Items) + sizeof(gSaveBlock1Ptr->bagPocket_KeyItems)
                  + sizeof(gSaveBlock1Ptr->bagPocket_PokeBalls) + sizeof(gSaveBlock1Ptr->bagPocket_TMHM)
                  + sizeof(gSaveBlock1Ptr->bagPocket_Berries), bag);
    else Fingerprint(NULL, 0, bag);
    sWorld.outputSize = snprintf(sWorld.output, sizeof(sWorld.output),
        "STATE %u %d %d %d %d %u %u %u %s %s\n", ++sWorld.seq,
        ready ? gSaveBlock1Ptr->location.mapGroup : 0,
        ready ? gSaveBlock1Ptr->location.mapNum : 0,
        player ? player->currentCoords.x - MAP_OFFSET : 0,
        player ? player->currentCoords.y - MAP_OFFSET : 0,
        player ? player->facingDirection : 1, player ? player->graphicsId : OBJ_EVENT_GFX_BOY_1,
        ready, party, bag);
    Flush();
}

static void SyncEngine(void)
{
    unsigned i, j;
    bool8 updateTiles;
    /* Our own modal owns the field lock. Keep its NPC alive, but do not
     * mutate engine objects or map tiles while the text task is running. */
    if (sWorld.dialogueActive && Overworld()) return;
    if (!Overworld() || gPaletteFade.active || ArePlayerFieldControlsLocked() || ScriptContext_IsEnabled()) {
        if (Overworld()) for (i = 0; i < WB_REMOTES; i++) RemoveRemote(i);
        RestoreTiles();
        sWorld.tilesLive = FALSE;
        return;
    }
    updateTiles = !SameGrid() || !sWorld.tilesLive || sWorld.appliedGeneration != sWorld.generation;
    if (!SameGrid()) {
        sWorld.appliedCount = 0;
        /* The engine may reuse both object and sprite slots after a map load.
         * Ownership also requires the map IDs and our sprite marker. */
        for (i = 0; i < WB_REMOTES; i++) if (!Owned(i)) memset(&sWorld.remotes[i], 0, sizeof(sWorld.remotes[i]));
    }
    if (updateTiles) {
        sWorld.restoredCount = 0;
        RestoreTiles();
    }
    sWorld.layout = gMapHeader.mapLayout;
    sWorld.grid = gBackupMapLayout.map;
    sWorld.group = gSaveBlock1Ptr->location.mapGroup;
    sWorld.num = gSaveBlock1Ptr->location.mapNum;
    for (i = 0; i < WB_REMOTES; i++) {
        struct Remote *r = &sWorld.remotes[i];
        const struct Peer *p = NULL;
        for (j = 0; j < sWorld.live.peerCount; j++)
            if (!strcmp(r->id, sWorld.live.peers[j].id)) p = &sWorld.live.peers[j];
        if (!p || !p->ready || p->group != (unsigned)sWorld.group || p->num != (unsigned)sWorld.num)
            RemoveRemote(i);
        else if (!Owned(i)) memset(r, 0, sizeof(*r));
    }
    for (j = 0; j < sWorld.live.peerCount; j++) {
        const struct Peer *p = &sWorld.live.peers[j];
        struct Remote *r = NULL;
        struct ObjectEvent *o;
        u8 gfx;
        if (!p->ready || p->group != (unsigned)sWorld.group || p->num != (unsigned)sWorld.num || !GridCoords(p->x, p->y)) continue;
        /* Never place a template-less remote over a real scripted NPC. Vanilla
         * could otherwise select our object first when A is passed through. */
        if (NativeNpcAt(p->x, p->y)) {
            for (i = 0; i < WB_REMOTES; i++)
                if (!strcmp(sWorld.remotes[i].id, p->id)) RemoveRemote(i);
            continue;
        }
        for (i = 0; i < WB_REMOTES; i++) if (!strcmp(sWorld.remotes[i].id, p->id)) { r = &sWorld.remotes[i]; break; }
        if (!r) {
            for (i = 0; i < WB_REMOTES; i++) if (!sWorld.remotes[i].id[0]) { r = &sWorld.remotes[i]; break; }
            if (!r) continue;
        }
        /* Standard NPC palettes cannot overwrite the local avatar's palette.
         * The fallback is deliberately a normal trainer, never a dynamic GFX ID. */
        gfx = OBJ_EVENT_GFX_BOY_1;
        if (p->gfx < NUM_OBJ_EVENT_GFX && GetObjectEventGraphicsInfo(p->gfx)->paletteSlot >= PALSLOT_NPC_1
         && GetObjectEventGraphicsInfo(p->gfx)->paletteSlot <= PALSLOT_NPC_4
         && !GetObjectEventGraphicsInfo(p->gfx)->inanimate) gfx = p->gfx;
        if (!r->id[0]) {
            u8 id;
            bool8 collision = FALSE;
            /* Both live objects and map templates must leave this local ID unused. */
            for (id = 0; id < OBJECT_EVENTS_COUNT; id++) if (gObjectEvents[id].active && gObjectEvents[id].localId == WB_LOCALID + i) collision = TRUE;
            if (gMapHeader.events) for (id = 0; id < gMapHeader.events->objectEventCount; id++)
                if (gSaveBlock1Ptr->objectEventTemplates[id].localId == WB_LOCALID + i) collision = TRUE;
            if (collision) continue;
            id = SpawnSpecialObjectEventParameterized(gfx, MOVEMENT_TYPE_NONE, WB_LOCALID + i,
                p->x + MAP_OFFSET, p->y + MAP_OFFSET, MapGridGetElevationAt(p->x + MAP_OFFSET, p->y + MAP_OFFSET));
            if (id >= OBJECT_EVENTS_COUNT) continue;
            strcpy(r->id, p->id);
            r->object = id; r->sprite = gObjectEvents[id].spriteId;
            r->group = p->group; r->num = p->num;
            gSprites[r->sprite].data[7] = WB_MARKER;
        }
        if (!Owned(i)) continue;
        o = &gObjectEvents[r->object];
        /* Changing sprite dimensions after allocation could overwrite OBJ VRAM.
         * Respawn instead when a peer changes graphics. */
        if (o->graphicsId != gfx) { RemoveRemote(i); continue; }
        if (o->currentCoords.x != (int)p->x + MAP_OFFSET || o->currentCoords.y != (int)p->y + MAP_OFFSET)
            MoveObjectEventToMapCoords(o, p->x + MAP_OFFSET, p->y + MAP_OFFSET);
        o->initialCoords = o->currentCoords;
        o->currentElevation = o->previousElevation = MapGridGetElevationAt(p->x + MAP_OFFSET, p->y + MAP_OFFSET);
        if (o->facingDirection != p->facing) ObjectEventTurn(o, p->facing);
    }
    if (!updateTiles) return;
    sWorld.tilesLive = TRUE;
    sWorld.appliedGeneration = sWorld.generation;
    for (i = 0; i < sWorld.live.tileCount; i++) {
        const struct Tile *t = &sWorld.live.tiles[i];
        struct Applied *a;
        if (t->group != (unsigned)sWorld.group || t->num != (unsigned)sWorld.num || !GridCoords(t->x, t->y)
         || !WorldCatalog_Metatile(t->group, t->num, t->metatile)) continue;
        a = &sWorld.applied[sWorld.appliedCount++];
        a->tile = *t;
        a->original = Raw(t->x, t->y);
        MapGridSetMetatileIdAt(t->x + MAP_OFFSET, t->y + MAP_OFFSET, t->metatile | (t->collision ? MAPGRID_IMPASSABLE : 0));
        a->raw = Raw(t->x, t->y);
        CurrentMapDrawMetatileAt(t->x + MAP_OFFSET, t->y + MAP_OFFSET);
    }
}

static bool8 FacingObject(const struct ObjectEvent *p, const struct ObjectEvent *o)
{
    int dx = o->currentCoords.x - p->currentCoords.x;
    int dy = o->currentCoords.y - p->currentCoords.y;
    return ((dx == 0 && dy == 1 && p->facingDirection == DIR_SOUTH)
         || (dx == 0 && dy == -1 && p->facingDirection == DIR_NORTH)
         || (dy == 0 && dx == -1 && p->facingDirection == DIR_WEST)
         || (dy == 0 && dx == 1 && p->facingDirection == DIR_EAST))
        && (!o->currentElevation || !p->currentElevation || o->currentElevation == p->currentElevation);
}

/* This runs only after the game loop, never from the raw key reader. */
static void SyncDialogue(void)
{
    unsigned i, j;
    char talkPeer[25];
    bool8 talk = WorldActivity_TakeTalkRequest(talkPeer);
    const struct Meeting *meeting = &sWorld.live.meeting;
    if (WorldActivity_OwnsFieldInput()) {
        sWorld.shownMeeting = meeting->seq;
        sWorld.pendingObject[0] = 0;
        sWorld.dialogueKeys = 0;
        return;
    }
    if (talk) strcpy(sWorld.pendingObject, talkPeer);
    if (sWorld.socialCooldown) sWorld.socialCooldown--;
    if (sWorld.meetingAge < 180) sWorld.meetingAge++;
    if (sWorld.dialogueActive) {
        if (!Overworld()) {
            /* A reset owns the new UI and its lock, not this old dialogue. */
            sWorld.dialogueActive = FALSE;
        } else if (!sWorld.connected || (sWorld.dialogueMeeting && meeting->seq != sWorld.dialogueMeeting)
                || (sWorld.dialogueKeys && IsFieldMessageBoxHidden())) {
            HideFieldMessageBox();
            UnlockPlayerFieldControls();
            sWorld.dialogueActive = FALSE;
        }
    } else if (meeting->seq && meeting->seq > sWorld.shownMeeting && sWorld.meetingAge < 180
            && Ready() && sWorld.connected && IsFieldMessageBoxHidden()) {
        const struct ObjectEvent *player = &gObjectEvents[gPlayerAvatar.objectEventId];
        int dx = (int)meeting->x + MAP_OFFSET - player->currentCoords.x;
        int dy = (int)meeting->y + MAP_OFFSET - player->currentCoords.y;
        sWorld.shownMeeting = meeting->seq;
        /* Only a committed authority signal can open this native modal. Never
         * interrupt another UI, or show it after the player walks away. */
        if (meeting->group == (unsigned)gSaveBlock1Ptr->location.mapGroup
         && meeting->num == (unsigned)gSaveBlock1Ptr->location.mapNum
         && abs(dx) + abs(dy) <= 1) {
            const char *other = !strcmp(meeting->player, sWorld.trainer) ? meeting->target : meeting->player;
            snprintf(sWorld.dialogueLiteral, sizeof(sWorld.dialogueLiteral), "%s\nLet's explore together!", other);
            EncodeText(sWorld.dialogueLiteral, sWorld.dialogueText);
            if (ShowFieldMessage(sWorld.dialogueText)) {
                strcpy(sWorld.dialogueObject, other);
                sWorld.dialogueMeeting = meeting->seq;
                sWorld.dialogueActive = TRUE;
                LockPlayerFieldControls();
            }
        }
    } else if (sWorld.pendingObject[0] && Ready() && sWorld.connected && !sWorld.outputSize
            && IsFieldMessageBoxHidden()) {
        for (i = 0; i < WB_REMOTES; i++) {
            const struct Remote *r = &sWorld.remotes[i];
            if (strcmp(r->id, sWorld.pendingObject) || !Owned(i)
             || !FacingObject(&gObjectEvents[gPlayerAvatar.objectEventId], &gObjectEvents[r->object])) continue;
            for (j = 0; j < sWorld.live.peerCount; j++) {
                const struct Peer *p = &sWorld.live.peers[j];
                if (strcmp(p->id, r->id) || !p->ready
                 || p->group != (unsigned)gSaveBlock1Ptr->location.mapGroup
                 || p->num != (unsigned)gSaveBlock1Ptr->location.mapNum
                 || (int)p->x + MAP_OFFSET != gObjectEvents[r->object].currentCoords.x
                 || (int)p->y + MAP_OFFSET != gObjectEvents[r->object].currentCoords.y) continue;
                if (r->id[0] != '@') {
                    if (!talk && WorldActivity_Interact(r->id)) break;
                    if (sWorld.socialCooldown) break;
                    SendState();
                    if (sWorld.connected) {
                        sWorld.outputSize += snprintf(sWorld.output + sWorld.outputSize,
                            sizeof(sWorld.output) - sWorld.outputSize, "MEET %u %s\n", ++sWorld.seq, r->id);
                        sWorld.interactionSeq = sWorld.seq;
                        sWorld.socialCooldown = 60;
                        Flush();
                    }
                    break;
                }
                EncodeText(p->text, sWorld.dialogueText);
                if (!ShowFieldMessage(sWorld.dialogueText)) break;
                /* Publish the precise ready position before taking our modal
                 * lock. Both messages share one monotonically increasing seq. */
                SendState();
                if (sWorld.connected) {
                    sWorld.outputSize += snprintf(sWorld.output + sWorld.outputSize,
                        sizeof(sWorld.output) - sWorld.outputSize, "INTERACT %u %s\n", ++sWorld.seq, r->id + 1);
                    sWorld.interactionSeq = sWorld.seq;
                    Flush();
                }
                strcpy(sWorld.dialogueObject, r->id + 1);
                strcpy(sWorld.dialogueLiteral, p->text);
                sWorld.dialogueMeeting = 0;
                sWorld.dialogueActive = TRUE;
                LockPlayerFieldControls();
                break;
            }
            break;
        }
    }
    sWorld.pendingObject[0] = 0;
    sWorld.dialogueKeys = 0;
}

u16 WorldBridge_FilterInput(u16 keys)
{
    unsigned i, j;
    const struct ObjectEvent *p;
    u16 pressed = keys & ~sWorld.previousKeys;
    if (!sWorld.enabled) return keys;
    sWorld.previousKeys = keys;
    if (WorldActivity_OwnsFieldInput()) return keys;
    if (sWorld.dialogueActive) {
        sWorld.dialogueKeys |= pressed & (A_BUTTON | B_BUTTON);
        return keys & (A_BUTTON | B_BUTTON);
    }
    if (!(keys & A_BUTTON) || !Ready() || !IsFieldMessageBoxHidden()) return keys;
    p = &gObjectEvents[gPlayerAvatar.objectEventId];
    /* An ordinary map NPC always wins, even if a remote overlaps it or stands
     * behind it. Never swallow the NPC's A press to protect a farther ghost. */
    for (i = 0; i < OBJECT_EVENTS_COUNT; i++) {
        const struct ObjectEvent *o = &gObjectEvents[i];
        bool8 remote = FALSE;
        if (!o->active || o->isPlayer || !FacingObject(p, o)) continue;
        for (j = 0; j < WB_REMOTES; j++)
            if (Owned(j) && sWorld.remotes[j].object == i) remote = TRUE;
        if (!remote) return keys;
    }
    for (i = 0; i < WB_REMOTES; i++) if (Owned(i)) {
        const struct ObjectEvent *o = &gObjectEvents[sWorld.remotes[i].object];
        int dx = o->currentCoords.x - p->currentCoords.x, dy = o->currentCoords.y - p->currentCoords.y;
        /* Dynamic peers have no map-script template. Do not pass them to the
         * vanilla interaction lookup, including through a counter tile. */
        if ((dx == 0 && dy > 0 && dy <= 2 && p->facingDirection == DIR_SOUTH)
         || (dx == 0 && dy < 0 && dy >= -2 && p->facingDirection == DIR_NORTH)
         || (dy == 0 && dx < 0 && dx >= -2 && p->facingDirection == DIR_WEST)
         || (dy == 0 && dx > 0 && dx <= 2 && p->facingDirection == DIR_EAST)) {
            if ((pressed & A_BUTTON) && FacingObject(p, o))
                strcpy(sWorld.pendingObject, sWorld.remotes[i].id);
            return keys & ~A_BUTTON;
        }
    }
    return keys;
}

void WorldBridge_WriteJSON(FILE *file, u32 frame)
{
    unsigned i, count = 0;
    const struct ObjectEvent *p = Overworld() ? &gObjectEvents[gPlayerAvatar.objectEventId] : NULL;
    fprintf(file, "{\"trainer\":\"%s\",\"frame\":%u,\"connected\":%s,\"revision\":%u,\"ready\":%s,\"map\":[%d,%d],\"pos\":[%d,%d],\"peers\":[",
        sWorld.trainer, frame, sWorld.connected ? "true" : "false", sWorld.live.revision, Ready() ? "true" : "false",
        gSaveBlock1Ptr ? gSaveBlock1Ptr->location.mapGroup : -1, gSaveBlock1Ptr ? gSaveBlock1Ptr->location.mapNum : -1,
        p ? p->currentCoords.x - MAP_OFFSET : 0, p ? p->currentCoords.y - MAP_OFFSET : 0);
    for (i = 0; i < WB_REMOTES; i++) if (Overworld() && Owned(i) && sWorld.remotes[i].id[0] != '@') {
        const struct Remote *r = &sWorld.remotes[i];
        const struct ObjectEvent *o = &gObjectEvents[r->object];
        fprintf(file, "%s{\"trainer\":\"%s\",\"object_id\":%u,\"local_id\":%u,\"sprite_id\":%u,\"gfx\":%u,\"map\":[%u,%u],\"pos\":[%d,%d],\"sprite_pos\":[%d,%d],\"visible\":%s}",
            count++ ? "," : "", r->id, r->object, o->localId, o->spriteId, o->graphicsId, o->mapGroup, o->mapNum,
            o->currentCoords.x - MAP_OFFSET, o->currentCoords.y - MAP_OFFSET,
            gSprites[o->spriteId].x, gSprites[o->spriteId].y, gSprites[o->spriteId].invisible ? "false" : "true");
    }
    fprintf(file, "],\"objects\":[");
    count = 0;
    for (i = 0; i < WB_REMOTES; i++) if (Overworld() && Owned(i) && sWorld.remotes[i].id[0] == '@') {
        const struct Remote *r = &sWorld.remotes[i];
        const struct ObjectEvent *o = &gObjectEvents[r->object];
        fprintf(file, "%s{\"id\":\"%s\",\"object_id\":%u,\"local_id\":%u,\"sprite_id\":%u,\"gfx\":%u,\"map\":[%u,%u],\"pos\":[%d,%d],\"visible\":%s}",
            count++ ? "," : "", r->id + 1, r->object, o->localId, o->spriteId, o->graphicsId, o->mapGroup, o->mapNum,
            o->currentCoords.x - MAP_OFFSET, o->currentCoords.y - MAP_OFFSET, gSprites[o->spriteId].invisible ? "false" : "true");
    }
    fprintf(file, "],\"object_count\":%u,\"dialogue_active\":%s,\"dialogue_object\":\"%s\",\"interaction_seq\":%u,\"dialogue_text\":\"",
        count, sWorld.dialogueActive ? "true" : "false", sWorld.dialogueObject, sWorld.interactionSeq);
    /* Validated literals cannot contain quotes or slashes. Escape their only
     * control character rather than placing raw newlines in telemetry JSON. */
    for (i = 0; sWorld.dialogueLiteral[i]; i++) {
        if (sWorld.dialogueLiteral[i] == '\n') fputs("\\n", file);
        else fputc(sWorld.dialogueLiteral[i], file);
    }
    fprintf(file, "\",\"dialogue_kind\":\"%s\",\"meeting\":", sWorld.dialogueMeeting ? "trainer" : "object");
    if (sWorld.live.meeting.seq) {
        const struct Meeting *m = &sWorld.live.meeting;
        fprintf(file, "{\"seq\":%u,\"player\":\"%s\",\"target\":\"%s\",\"signal\":\"explore\"}",
            m->seq, m->player, m->target);
    } else fputs("null", file);
    fprintf(file, ",\"tiles\":[");
    for (i = 0; i < sWorld.appliedCount; i++) {
        const struct Applied *a = &sWorld.applied[i];
        fprintf(file, "%s{\"map\":[%u,%u],\"pos\":[%u,%u],\"metatile\":%u,\"collision\":%u,\"original\":%u,\"raw\":%u}",
            i ? "," : "", a->tile.group, a->tile.num, a->tile.x, a->tile.y, a->tile.metatile, a->tile.collision,
            a->original, SameGrid() && GridCoords(a->tile.x, a->tile.y) ? Raw(a->tile.x, a->tile.y) : a->raw);
    }
    fprintf(file, "],\"restored_tiles\":[");
    for (i = 0; i < sWorld.restoredCount; i++) {
        const struct Applied *a = &sWorld.restored[i];
        fprintf(file, "%s{\"map\":[%u,%u],\"pos\":[%u,%u],\"original\":%u,\"raw\":%u}",
            i ? "," : "", a->tile.group, a->tile.num, a->tile.x, a->tile.y, a->original, a->raw);
    }
    fprintf(file, "]}");
}

void WorldBridge_Poll(bool8 headless)
{
    if (!sWorld.enabled) return;
    if (!SocketOpen()) {
        if (sWorld.retry) sWorld.retry--;
        else Connect();
    }
    if (SocketOpen()) Receive(headless);
}

void WorldBridge_BeforeFrame(u32 frame, bool8 headless)
{
    (void)frame;
    if (!sWorld.enabled) return;
    WorldBridge_Poll(headless);
    SyncEngine();
}

void WorldBridge_AfterFrame(u32 frame)
{
    FILE *file;
    char path[1100];
    if (!sWorld.enabled) return;
    SyncDialogue();
    SyncEngine();
    if (frame % 6 == 0) SendState();
    snprintf(path, sizeof(path), "%s.tmp", sWorld.telemetry);
    file = NativeFile_Open(path, "w");
    if (!file) return;
    WorldBridge_WriteJSON(file, frame);
    fputc('\n', file);
    if (fclose(file) == 0) {
        NativeFile_Replace(path, sWorld.telemetry);
    }
}

void WorldBridge_PrepareSave(void)
{
    unsigned i;
    if (!sWorld.enabled) return;
    RestoreTiles();
    sWorld.tilesLive = FALSE;
    /* Serialization can run during a warp, outside CB2_Overworld. Owned()
     * protects engine-reused slots without relying on the current callback. */
    for (i = 0; i < WB_REMOTES; i++) RemoveRemote(i);
}

void WorldBridge_Close(void)
{
    unsigned i;
    if (!sWorld.enabled) return;
    RestoreTiles();
    if (Overworld()) for (i = 0; i < WB_REMOTES; i++) RemoveRemote(i);
    Disconnect();
#ifdef _WIN32
    if (sWorld.winsockStarted) {
        WSACleanup();
        sWorld.winsockStarted = FALSE;
    }
#endif
    sWorld.enabled = FALSE;
}
#endif /* PORTABLE */
