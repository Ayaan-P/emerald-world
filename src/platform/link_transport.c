#ifdef PORTABLE
#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <winsock2.h>
#include <windows.h>
#else
#include <unistd.h>
#include <fcntl.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <poll.h>
#endif
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <inttypes.h>
#include <errno.h>
#include "platform/native_file.h"
#include "platform/native_link.h"
#include "platform/link_transport.h"
#define QUEUE_CAP 65536
static struct {
#ifdef _WIN32
    SOCKET fd;
    int winsock;
    unsigned port;
    char capability[65];
#else
    int fd;
#endif
    int initialized, enabled, connecting, ready;
    unsigned retry;
    char path[108], trainer[25], token[65], telemetry[1024];
    char output[QUEUE_CAP], input[513];
    size_t queued, sent, used;
    uint64_t session, accepting;
    unsigned mode, slot, offered;
    struct LinkTransportInvitation pending;
} sLink;

static int Identifier(const char *p)
{
    size_t n = 0;
    if (!p || !*p) return 0;
    for (; *p; p++, n++)
        if (!((*p >= 'A' && *p <= 'Z') || (*p >= 'a' && *p <= 'z')
           || (*p >= '0' && *p <= '9') || *p == '_' || *p == '-')) return 0;
    return n <= 24;
}
static int Decimal(const char *p, uint64_t max, uint64_t *value)
{
    uint64_t n = 0;
    if (!*p) return 0;
    for (; *p; p++) {
        unsigned digit = (unsigned char)*p - '0';
        if (digit > 9 || n > (max - digit) / 10 || digit > max) return 0;
        n = n * 10 + digit;
    }
    *value = n;
    return 1;
}
static int Hex(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}
static int Token(const char *p)
{
    unsigned i;
    if (strlen(p) != 64) return 0;
    for (i = 0; i < 64; i++)
        if (Hex(p[i]) < 0 && !(p[i] >= 'A' && p[i] <= 'F')) return 0;
    return 1;
}
static int SocketOpen(void)
{
#ifdef _WIN32
    return sLink.initialized && sLink.fd != INVALID_SOCKET;
#else
    return sLink.initialized && sLink.fd >= 0;
#endif
}
static void Disconnect(void)
{
    if (SocketOpen()) {
#ifdef _WIN32
        closesocket(sLink.fd);
#else
        close(sLink.fd);
#endif
    }
#ifdef _WIN32
    sLink.fd = INVALID_SOCKET;
#else
    sLink.fd = -1;
#endif
    sLink.enabled = sLink.ready = sLink.connecting = 0;
    sLink.queued = sLink.sent = sLink.used = 0;
    NativeLink_EndSession(sLink.session);
    sLink.session = sLink.accepting = 0;
    sLink.offered = 0;
    sLink.mode = sLink.slot = 0;
    memset(&sLink.pending, 0, sizeof(sLink.pending));
}
void LinkTransport_Close(void)
{
    if (!sLink.initialized) return;
    Disconnect();
    NativeLink_Init(NULL, NULL);
#ifdef _WIN32
    if (sLink.winsock) WSACleanup();
#endif
    memset(&sLink, 0, sizeof(sLink));
}
static int Queue(const char *line)
{
    size_t n = strlen(line), remaining = sLink.queued - sLink.sent;
    if (n > QUEUE_CAP - remaining) return 0;
    if (sLink.sent) memmove(sLink.output, sLink.output + sLink.sent, remaining);
    sLink.sent = 0;
    memcpy(sLink.output + remaining, line, n);
    sLink.queued = remaining + n;
    return 1;
}
static int Emit(void *context, const struct NativeLinkEvent *e)
{
    static const char hex[] = "0123456789abcdef";
    char words[33], line[256];
    unsigned i;
    (void)context;
    if (!sLink.ready || !e || e->kind < 1 || e->kind > 5
     || !e->session || e->session != sLink.session || e->mode != sLink.mode
     || e->slot != sLink.slot) return 0;
    for (i = 0; i < 16; i++) {
        unsigned byte = (e->command[i / 2] >> ((i % 2) * 8)) & 255;
        words[2*i] = hex[byte >> 4]; words[2*i+1] = hex[byte & 15];
    }
    words[32] = 0;
    snprintf(line, sizeof(line), "L EVENT %u %" PRIu64 " %u %u %" PRIu32 " %" PRIu32 " %u %s\n",
        e->kind, e->session, e->mode, e->slot, e->generation, e->round, e->linkType, words);
    return Queue(line);
}
/* Same config allowlist, field bounds and whitespace grammar as presence.
 * Validate the entire byte stream before C-string parsing (including comments). */
static int Config(const char *path)
{
    FILE *f = NativeFile_Open(path, "rb");
    char line[1200];
    unsigned seen = 0;
    int c, good = 0;
    uint32_t code = 0, minimum = 0;
    unsigned continuation = 0;
    if (!f) return 0;
    while ((c = fgetc(f)) != EOF) {
        if (continuation) {
            if (c < 0x80 || c > 0xbf) goto done;
            code = (code << 6) | (c & 63);
            if (!--continuation && (code < minimum || code > 0x10ffff || (code >= 0xd800 && code <= 0xdfff))) goto done;
        } else if (c >= 0x80) {
            if (c >= 0xc2 && c <= 0xdf) { continuation = 1; code = c & 31; minimum = 0x80; }
            else if (c >= 0xe0 && c <= 0xef) { continuation = 2; code = c & 15; minimum = 0x800; }
            else if (c >= 0xf0 && c <= 0xf4) { continuation = 3; code = c & 7; minimum = 0x10000; }
            else goto done;
        } else if ((c < 32 && c != '\t' && c != '\r' && c != '\n') || c == 127) goto done;
    }
    if (continuation || ferror(f) || fseek(f, 0, SEEK_SET)) goto done;
    while (fgets(line, sizeof(line), f)) {
        char *p = line, *key, *value, *end, *dest;
        unsigned bit;
        size_t size;
        if ((!strchr(line, '\n') && !feof(f)) || strlen(line) > 1150) goto done;
        if (line[0] == '#' || line[0] == '\n') continue;
        while (*p == ' ' || *p == '\t') p++;
        key = p;
        while (*p && *p != ' ' && *p != '\t' && *p != '\r' && *p != '\n') p++;
        if (!*p || p - key > 31) goto done;
        *p++ = 0;
        while (*p == ' ' || *p == '\t') p++;
        value = p; end = p + strlen(p);
        while (end > p && (end[-1] == '\n' || end[-1] == '\r')) *--end = 0;
#ifndef _WIN32
        while (end > p && (end[-1] == ' ' || end[-1] == '\t')) *--end = 0;
#endif
        if (!*value || strlen(value) > 1099) goto done;
        for (p = value; *p; p++)
            if (*p == '\r' || *p == '\n'
#ifdef _WIN32
             || (strcmp(key, "telemetry") && (*p == ' ' || *p == '\t'))
#else
             || *p == ' ' || *p == '\t'
#endif
            ) goto done;
#ifdef _WIN32
        if (!strcmp(key, "loopback_port")) {
            uint64_t port;
            if ((seen & 1) || !Decimal(value, 65535, &port) || !port) goto done;
            sLink.port = (unsigned)port; seen |= 1; continue;
        }
        if (!strcmp(key, "loopback_token")) { bit = 16; dest = sLink.capability; size = sizeof(sLink.capability); }
#else
        if (!strcmp(key, "socket")) { bit = 1; dest = sLink.path; size = sizeof(sLink.path); }
#endif
        else if (!strcmp(key, "trainer")) { bit = 2; dest = sLink.trainer; size = sizeof(sLink.trainer); }
        else if (!strcmp(key, "token")) { bit = 4; dest = sLink.token; size = sizeof(sLink.token); }
        else if (!strcmp(key, "telemetry")) { bit = 8; dest = sLink.telemetry; size = sizeof(sLink.telemetry); }
        else goto done;
        if ((seen & bit) || strlen(value) >= size) goto done;
        strcpy(dest, value); seen |= bit;
    }
#ifdef _WIN32
    if (seen != 31 || !Token(sLink.capability)) goto done;
#else
    if (seen != 15 || sLink.path[0] != '/') goto done;
#endif
    good = !ferror(f) && Identifier(sLink.trainer) && Token(sLink.token);
done:
    fclose(f);
    return good;
}
static int WouldBlock(void)
{
#ifdef _WIN32
    int error = WSAGetLastError();
    return error == WSAEWOULDBLOCK || error == WSAEINTR;
#else
    return errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR;
#endif
}
static void RetryDisconnect(void)
{
    Disconnect();
    /* Reconnect the channel only. No invitations, consent, or queued commands
     * survive loss of the authenticated presence binding. */
    sLink.enabled = 1;
    sLink.retry = 60;
}
static int Connect(void)
{
    int result;
    char hello[256];
#ifdef _WIN32
    {
        struct sockaddr_in addr;
        u_long nonblock = 1;
        sLink.fd = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
        if (!SocketOpen() || ioctlsocket(sLink.fd, FIONBIO, &nonblock)) goto fail;
        memset(&addr, 0, sizeof(addr)); addr.sin_family = AF_INET;
        addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK); addr.sin_port = htons(sLink.port);
        result = connect(sLink.fd, (struct sockaddr *)&addr, sizeof(addr));
        if (result && WSAGetLastError() != WSAEWOULDBLOCK && WSAGetLastError() != WSAEINPROGRESS) goto fail;
        snprintf(hello, sizeof(hello), "EWLOCAL1 %s\n", sLink.capability);
        Queue(hello);
    }
#else
    {
        struct sockaddr_un addr;
        int flags;
        sLink.fd = socket(AF_UNIX, SOCK_STREAM, 0);
        if (!SocketOpen()) goto fail;
        flags = fcntl(sLink.fd, F_GETFL, 0);
        if (flags < 0 || fcntl(sLink.fd, F_SETFL, flags | O_NONBLOCK) < 0) goto fail;
        memset(&addr, 0, sizeof(addr)); addr.sun_family = AF_UNIX;
        if (strlen(sLink.path) >= sizeof(addr.sun_path)) goto fail;
        strcpy(addr.sun_path, sLink.path);
        result = connect(sLink.fd, (struct sockaddr *)&addr, sizeof(addr));
        if (result && errno != EINPROGRESS) goto fail;
    }
#endif
    sLink.connecting = result != 0;
    sLink.enabled = 1;
    snprintf(hello, sizeof(hello), "HELLO 1 %s %s LINK\n", sLink.trainer, sLink.token);
    Queue(hello);
    return 1;
fail:
    RetryDisconnect();
    return 0;
}
int LinkTransport_Init(const char *configPath)
{
    LinkTransport_Close();
    if (!configPath) return 1;
    memset(&sLink, 0, sizeof(sLink));
    sLink.initialized = 1;
#ifdef _WIN32
    sLink.fd = INVALID_SOCKET;
#else
    sLink.fd = -1;
#endif
    if (!Config(configPath)) { LinkTransport_Close(); return 0; }
#ifdef _WIN32
    {
        WSADATA data;
        if (WSAStartup(MAKEWORD(2,2), &data)) { LinkTransport_Close(); return 0; }
        sLink.winsock = 1;
        if (data.wVersion != MAKEWORD(2,2)) { LinkTransport_Close(); return 0; }
    }
#endif
    NativeLink_Init(Emit, NULL);
    sLink.enabled = 1;
    Connect();
    return 1;
}
int LinkTransport_Ready(void) { return sLink.ready; }
const struct LinkTransportInvitation *LinkTransport_PendingInvitation(void)
{
    return sLink.pending.id ? &sLink.pending : NULL;
}
int LinkTransport_Offer(const char *target, unsigned mode)
{
    char line[64];
    if (!sLink.ready || sLink.session || sLink.pending.id || sLink.offered
     || !Identifier(target) || !strcmp(target, sLink.trainer) || mode < 1 || mode > 3) return 0;
    snprintf(line, sizeof(line), "L OFFER %u %s\n", mode, target);
    if (!Queue(line)) return 0;
    sLink.offered = mode;
    return 1;
}
int LinkTransport_Accept(uint64_t session)
{
    char line[64];
    if (!sLink.ready || !session || session != sLink.pending.id || sLink.accepting || sLink.session) return 0;
    snprintf(line, sizeof(line), "L ACCEPT %" PRIu64 "\n", session);
    if (!Queue(line)) return 0;
    sLink.accepting = session;
    return 1;
}
int LinkTransport_Reject(uint64_t session)
{
    char line[64];
    if (!sLink.ready || !session || session != sLink.pending.id || sLink.accepting) return 0;
    snprintf(line, sizeof(line), "L REJECT %" PRIu64 "\n", session);
    if (!Queue(line)) return 0;
    memset(&sLink.pending, 0, sizeof(sLink.pending));
    return 1;
}
static int Words(const char *hex, uint16_t words[8])
{
    unsigned i;
    if (strlen(hex) != 32) return 0;
    memset(words, 0, 16);
    for (i = 0; i < 16; i++) {
        int hi = Hex(hex[2*i]), lo = Hex(hex[2*i+1]);
        if (hi < 0 || lo < 0) return 0;
        words[i/2] |= (uint16_t)((hi*16+lo) << ((i%2)*8));
    }
    return 1;
}
static int Line(char *line)
{
    char *t[10], *p = line;
    unsigned n = 0;
    uint64_t sid, a, b, c;
    while (*p) {
        if (n == 10 || *p == ' ') return 0;
        t[n++] = p;
        while (*p && *p != ' ') p++;
        if (*p) { *p++ = 0; if (!*p) return 0; }
    }
    if (n == 2 && !strcmp(t[0], "ERROR") && !strcmp(t[1], "PRESENCE")) return 2;
    if (!sLink.ready) {
        if (n != 5 || strcmp(t[0], "WELCOME") || strcmp(t[1], "1")
         || strcmp(t[2], sLink.trainer) || !Decimal(t[3], UINT32_MAX, &a) || strcmp(t[4], "LINK")) return 0;
        sLink.ready = 1; return 1;
    }
    if (n < 3 || strcmp(t[0], "L")) return 0;
    if (!strcmp(t[1], "ERROR")) {
        /* Fixed protocol codes, never arbitrary server-provided UI text. */
        static const char *const codes[] = {
            "busy", "capacity", "offline", "invalid", "denied", "not_found", "conflict", "expired", "unavailable", "rate_limited",
            "clock_regressed", "conflicting_duplicate", "invalid_actor", "invalid_commands", "invalid_generation",
            "invalid_kind", "invalid_link_generation", "invalid_link_type", "invalid_max_steps", "invalid_presence",
            "invalid_session", "invalid_state", "invalid_step", "invalid_time", "invalid_timeout", "link_type_mismatch",
            "not_adjacent", "not_host", "not_member", "not_ready", "not_target", "self_offer", "unknown_session"
        };
        unsigned i;
        if (n != 3) return 0;
        for (i = 0; i < sizeof(codes)/sizeof(codes[0]); i++) if (!strcmp(t[2], codes[i])) {
            if (sLink.session) return 0;
            sLink.offered = 0;
            sLink.accepting = 0;
            memset(&sLink.pending, 0, sizeof(sLink.pending));
            return 1;
        }
        return 0;
    }
    if (!strcmp(t[1], "COMMIT")) {
        uint16_t matrix[2][8];
        if (n != 8 || !Decimal(t[2], 3, &a) || !a || !Decimal(t[3], UINT64_MAX, &sid) || !sid
         || sid != sLink.session || !Decimal(t[4], UINT32_MAX, &b) || !Decimal(t[5], UINT32_MAX, &c)
         || !Words(t[6], matrix[0]) || !Words(t[7], matrix[1])) return 0;
        return NativeLink_Feed((unsigned)a, sid, (uint32_t)b, (uint32_t)c, matrix) >= 0;
    }
    if (!Decimal(t[2], UINT64_MAX, &sid) || !sid) return 0;
    if (!strcmp(t[1], "OFFER")) {
        if (n != 5 || !Decimal(t[3], 3, &a) || !a || !Identifier(t[4]) || !strcmp(t[4], sLink.trainer)
         || sLink.session || sLink.offered) return 0;
        if (sLink.pending.id && (sLink.pending.id != sid || sLink.pending.mode != a || strcmp(sLink.pending.name,t[4]))) return 0;
        sLink.pending.id = sid; sLink.pending.mode = (unsigned)a; strcpy(sLink.pending.name,t[4]); return 1;
    }
    if (!strcmp(t[1], "ADMIT")) {
        if (n != 5 || !Decimal(t[3], 3, &a) || !a || !Decimal(t[4], 1, &b)) return 0;
        if (sLink.session) return sid == sLink.session && a == sLink.mode && b == sLink.slot;
        if (!((sLink.accepting == sid && sLink.pending.mode == a) || sLink.offered == a)) return 0;
        sLink.session = sid; sLink.mode = (unsigned)a; sLink.slot = (unsigned)b;
        if (!NativeLink_Admit(sid, (unsigned)a, (unsigned)b)) return 0;
        sLink.offered = 0; sLink.accepting = 0; memset(&sLink.pending, 0, sizeof(sLink.pending)); return 1;
    }
    if (!strcmp(t[1], "ABORT") && n == 3) {
        if (sid == sLink.session) {
            NativeLink_EndSession(sid);
            sLink.session = 0; sLink.mode = sLink.slot = 0;
        }
        if (sid == sLink.pending.id) { sLink.accepting = 0; memset(&sLink.pending, 0, sizeof(sLink.pending)); }
        return 1;
    }
    return 0;
}
void LinkTransport_Pump(void)
{
    unsigned budget;
    if (!sLink.enabled) return;
    if (!SocketOpen()) {
        if (sLink.retry) { sLink.retry--; return; }
        if (!Connect()) return;
    }
    if (sLink.connecting) {
        int error = 0;
#ifdef _WIN32
        fd_set writes, errors;
        struct timeval timeout = {0,0};
        int size = sizeof(error), result;
        FD_ZERO(&writes); FD_ZERO(&errors); FD_SET(sLink.fd, &writes); FD_SET(sLink.fd, &errors);
        result = select(0, NULL, &writes, &errors, &timeout);
        if (result < 0) { Disconnect(); return; }
        if (!result) return;
        if (getsockopt(sLink.fd, SOL_SOCKET, SO_ERROR, (char *)&error, &size) || error) { RetryDisconnect(); return; }
#else
        struct pollfd fd = {sLink.fd, POLLOUT, 0};
        socklen_t size = sizeof(error);
        int result = poll(&fd, 1, 0);
        if (result < 0) { if (errno != EINTR) Disconnect(); return; }
        if (!result) return;
        if (getsockopt(sLink.fd, SOL_SOCKET, SO_ERROR, &error, &size) || error) { RetryDisconnect(); return; }
#endif
        sLink.connecting = 0;
    }
    for (budget = 0; sLink.sent < sLink.queued && budget < 64; budget++) {
        int count;
#ifdef _WIN32
        count = send(sLink.fd, sLink.output+sLink.sent, (int)(sLink.queued-sLink.sent), 0);
#else
        count = (int)send(sLink.fd, sLink.output+sLink.sent, sLink.queued-sLink.sent, MSG_NOSIGNAL);
#endif
        if (count < 0 && WouldBlock()) break;
        if (count <= 0) { RetryDisconnect(); return; }
        sLink.sent += (size_t)count;
    }
    if (sLink.sent == sLink.queued) sLink.sent = sLink.queued = 0;
    for (budget = 0; budget < 8192; budget++) {
        char ch;
        int count = (int)recv(sLink.fd, &ch, 1, 0);
        if (count < 0 && WouldBlock()) break;
        if (count <= 0) { RetryDisconnect(); return; }
        if (ch == '\n') {
            int parsed;
            sLink.input[sLink.used] = 0;
            parsed = Line(sLink.input);
            if (parsed == 2) { RetryDisconnect(); return; }
            if (!parsed) { Disconnect(); return; }
            sLink.used = 0;
        } else {
            if ((unsigned char)ch < 32 || (unsigned char)ch > 126 || sLink.used == 512) { Disconnect(); return; }
            sLink.input[sLink.used++] = ch;
        }
    }
    if (sLink.ready) NativeLink_Pump();
}
#endif
