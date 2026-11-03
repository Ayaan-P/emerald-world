#ifdef PORTABLE
#include "platform/player_control.h"
#include <string.h>
#include <stdlib.h>
#include <limits.h>
#include <errno.h>
#ifndef _WIN32
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <time.h>

#define REQUEST_CAP 8192
#define RESPONSE_CAP 65536
static struct {
    int listener, client, dir;
    char name[108], path[108], shot[PATH_MAX];
    dev_t device;
    ino_t inode;
    char input[REQUEST_CAP], output[RESPONSE_CAP];
    size_t used, size, sent;
    unsigned id, remaining;
    uint16_t buttons;
    uint32_t frame;
    unsigned long long deadline;
    bool closeAfterWrite;
    void (*state)(FILE *, uint32_t);
    bool (*capture)(FILE *);
} s = {.listener = -1, .client = -1, .dir = -1};

static unsigned long long Now(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (unsigned long long)ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}

static void Disconnect(void)
{
    if (s.client >= 0) close(s.client);
    s.client = -1;
    s.used = s.size = s.sent = 0;
    s.remaining = s.buttons = 0;
    s.closeAfterWrite = false;
}

void PlayerControl_Close(void)
{
    struct stat st;
    Disconnect();
    if (s.listener >= 0) close(s.listener);
    if (s.dir >= 0) {
        if (!fstatat(s.dir, s.name, &st, AT_SYMLINK_NOFOLLOW)
            && st.st_dev == s.device && st.st_ino == s.inode && S_ISSOCK(st.st_mode))
            unlinkat(s.dir, s.name, 0);
        close(s.dir);
    }
    s.listener = s.dir = -1;
    s.inode = 0;
}

/* Walk from / without following any symlink, including intermediate components. */
static int Parent(const char *path, char *name, size_t size)
{
    char copy[PATH_MAX], *part, *next, *end;
    int fd, child;
    if (!path || path[0] != '/' || strlen(path) >= sizeof(copy)) return -1;
    strcpy(copy, path + 1);
    fd = open("/", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    part = strtok_r(copy, "/", &end);
    if (!part) { close(fd); return -1; }
    while ((next = strtok_r(NULL, "/", &end)) != NULL) {
        if (!strcmp(part, ".") || !strcmp(part, "..")) { close(fd); return -1; }
        child = openat(fd, part, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
        close(fd);
        if (child < 0) return -1;
        fd = child;
        part = next;
    }
    if (!strcmp(part, ".") || !strcmp(part, "..") || strlen(part) >= size) {
        close(fd); return -1;
    }
    strcpy(name, part);
    return fd;
}

bool PlayerControl_Init(const char *path, const char *savePath,
                        void (*state)(FILE *, uint32_t), bool (*shot)(FILE *))
{
    struct sockaddr_un addr;
    struct stat profile, saveDir, existing;
    char saveName[PATH_MAX];
    int fd = -1, oldMask;
    PlayerControl_Close();
    if (!path) return true;
    if (strlen(path) >= sizeof(addr.sun_path) || !state || !shot) goto fail;
    s.dir = Parent(path, s.name, sizeof(s.name));
    fd = Parent(savePath, saveName, sizeof(saveName));
    if (s.dir < 0 || fd < 0 || fstat(s.dir, &profile) || fstat(fd, &saveDir)
        || profile.st_dev != saveDir.st_dev || profile.st_ino != saveDir.st_ino
        || profile.st_uid != geteuid() || (profile.st_mode & 0077)
        || !strcmp(s.name, "screenshot.ppm") || !strcmp(saveName, "screenshot.ppm")
        || !strcmp(s.name, saveName)) goto fail;
    close(fd); fd = -1;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strcpy(addr.sun_path, path);
    if (!fstatat(s.dir, s.name, &existing, AT_SYMLINK_NOFOLLOW)) {
        struct stat checked;
        int probe, result, error;
        if (!S_ISSOCK(existing.st_mode) || existing.st_uid != geteuid()
            || existing.st_nlink != 1) goto fail;
        probe = socket(AF_UNIX, SOCK_STREAM | SOCK_NONBLOCK | SOCK_CLOEXEC, 0);
        if (probe < 0) goto fail;
        result = connect(probe, (struct sockaddr *)&addr, sizeof(addr));
        error = errno;
        close(probe);
        /* Only a refused connection proves staleness. Recheck ownership and
         * identity after probing so a replaced endpoint is never reclaimed. */
        if (result != -1 || error != ECONNREFUSED
            || fstatat(s.dir, s.name, &checked, AT_SYMLINK_NOFOLLOW)
            || !S_ISSOCK(checked.st_mode) || checked.st_uid != geteuid()
            || checked.st_nlink != 1 || checked.st_dev != existing.st_dev
            || checked.st_ino != existing.st_ino
            || unlinkat(s.dir, s.name, 0)) goto fail;
    } else if (errno != ENOENT) goto fail;
    strcpy(s.path, path);
    strcpy(s.shot, path);
    strcpy(strrchr(s.shot, '/') + 1, "screenshot.ppm");
    /* Only printable unescaped paths are returned in the JSON protocol. */
    for (const unsigned char *p = (const unsigned char *)s.shot; *p; p++)
        if (*p < 32 || *p > 126 || *p == '"' || *p == '\\') goto fail;
    s.listener = socket(AF_UNIX, SOCK_STREAM, 0);
    if (s.listener < 0 || fcntl(s.listener, F_SETFL, O_NONBLOCK)
        || fcntl(s.listener, F_SETFD, FD_CLOEXEC)) goto fail;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strcpy(addr.sun_path, path);
    oldMask = umask(0077);
    int bound = bind(s.listener, (struct sockaddr *)&addr, sizeof(addr));
    umask(oldMask);
    if (bound) goto fail;
    if (fstatat(s.dir, s.name, &existing, AT_SYMLINK_NOFOLLOW)) goto fail;
    s.device = existing.st_dev; s.inode = existing.st_ino;
    if (fchmodat(s.dir, s.name, 0600, 0) || listen(s.listener, 1)) goto fail;
    s.state = state; s.capture = shot; s.frame = 0;
    atexit(PlayerControl_Close);
    return true;
fail:
    if (fd >= 0) close(fd);
    PlayerControl_Close();
    fprintf(stderr, "Invalid player control endpoint. Use an unused absolute socket beside an explicit save in its private profile directory.\n");
    return false;
}

static void Space(const char **p)
{
    while (**p == ' ' || **p == '\t' || **p == '\r' || **p == '\n') ++*p;
}
static bool Token(const char **p, char c)
{
    Space(p);
    if (**p != c) return false;
    ++*p; return true;
}
static bool String(const char **p, char *out, size_t cap)
{
    size_t n = 0;
    if (!Token(p, '"')) return false;
    while (**p && **p != '"') {
        unsigned char c = *(*p)++;
        if (c < 32 || c > 126) return false;
        if (c == '\\') {
            c = *(*p)++;
            if (!c) return false;
            if (c == 'u') {
                unsigned v = 0;
                for (int i = 0; i < 4; i++) {
                    char h = **p;
                    if (!h) return false;
                    ++*p;
                    if (h >= '0' && h <= '9') v = v * 16 + h - '0';
                    else if (h >= 'a' && h <= 'f') v = v * 16 + h - 'a' + 10;
                    else if (h >= 'A' && h <= 'F') v = v * 16 + h - 'A' + 10;
                    else return false;
                }
                if (v < 32 || v > 126) return false;
                c = v;
            } else if (c != '"' && c != '\\' && c != '/') return false;
        }
        if (n + 1 >= cap) return false;
        out[n++] = c;
    }
    out[n] = 0;
    return Token(p, '"');
}
static bool Number(const char **p, unsigned *out)
{
    unsigned n = 0;
    Space(p);
    if (**p < '0' || **p > '9') return false;
    if (**p == '0' && (*p)[1] >= '0' && (*p)[1] <= '9') return false;
    while (**p >= '0' && **p <= '9') {
        unsigned d = *(*p)++ - '0';
        if (n > (2147483647U - d) / 10) return false;
        n = n * 10 + d;
    }
    *out = n; return true;
}
static bool Request(const char *p, unsigned *id, unsigned *frames, uint16_t *keys, char *op)
{
    static const char *names[] = {"A", "B", "SELECT", "START", "RIGHT", "LEFT", "UP", "DOWN", "R", "L"};
    unsigned seen = 0;
    *keys = 0; *id = 0; *frames = 0;
    if (!Token(&p, '{')) return false;
    do {
        char key[16]; unsigned flag;
        if (!String(&p, key, sizeof(key)) || !Token(&p, ':')) return false;
        if (!strcmp(key, "id")) flag = 1;
        else if (!strcmp(key, "op")) flag = 2;
        else if (!strcmp(key, "frames")) flag = 4;
        else if (!strcmp(key, "buttons")) flag = 8;
        else return false;
        if (seen & flag) return false;
        seen |= flag;
        if (flag == 1 && !Number(&p, id)) return false;
        if (flag == 2 && !String(&p, op, 16)) return false;
        if (flag == 4 && (!Number(&p, frames) || !*frames || *frames > 120)) return false;
        if (flag == 8) {
            if (!Token(&p, '[')) return false;
            Space(&p);
            if (*p != ']') do {
                char button[16]; unsigned i;
                if (!String(&p, button, sizeof(button))) return false;
                for (i = 0; i < 10 && strcmp(button, names[i]); i++);
                if (i == 10 || (*keys & (1 << i))) return false;
                *keys |= 1 << i;
            } while (Token(&p, ','));
            if (!Token(&p, ']')) return false;
        }
    } while (Token(&p, ','));
    if (!Token(&p, '}')) return false;
    Space(&p);
    if (*p || (seen & 3) != 3) return false;
    if (!strcmp(op, "press")) return seen == 15;
    return seen == 3 && (!strcmp(op, "observe") || !strcmp(op, "screenshot"));
}
static void Error(unsigned id, const char *error)
{
    s.size = snprintf(s.output, sizeof(s.output), "{\"id\":%u,\"ok\":false,\"error\":\"%s\"}\n", id, error);
    s.sent = 0; s.deadline = Now() + 5000;
}
static void Reply(bool screenshot)
{
    FILE *file = fmemopen(s.output, sizeof(s.output), "w");
    if (!file) { Error(s.id, "state_unavailable"); return; }
    fprintf(file, "{\"id\":%u,\"ok\":true,\"state\":", s.id);
    s.state(file, s.frame);
    bool failed = fflush(file) != 0 || ferror(file);
    long end = ftell(file);
    if (!failed && end > 0 && end < RESPONSE_CAP) {
        while (end && (s.output[end - 1] == '\n' || s.output[end - 1] == '\r'
               || s.output[end - 1] == ' ' || s.output[end - 1] == '\t')) end--;
        if (fseek(file, end, SEEK_SET)) failed = true;
    }
    if (screenshot) fprintf(file, ",\"screenshot\":\"%s\"", s.shot);
    fputs("}\n", file);
    long size = ftell(file);
    failed = failed || ferror(file) || size < 0 || size >= RESPONSE_CAP - 1;
    if (fclose(file)) failed = true;
    if (failed) { Error(s.id, "state_too_large"); return; }
    s.size = size; s.sent = 0; s.deadline = Now() + 5000;
}
static void Execute(void)
{
    char op[16]; unsigned id, frames; uint16_t keys;
    bool valid = Request(s.input, &id, &frames, &keys, op);
    if (s.remaining || s.size) {
        /* A pipelined request cancels the hold rather than queueing unbounded work. */
        s.remaining = s.buttons = 0;
        if (s.sent) { Disconnect(); return; }
        Error(id, "busy"); return;
    }
    if (!valid) { Error(id, "malformed"); return; }
    s.id = id;
    if (!strcmp(op, "press")) {
        s.buttons = keys; s.remaining = frames; s.deadline = Now() + 5000;
    } else {
        if (!strcmp(op, "screenshot")) {
            int fd = openat(s.dir, "screenshot.ppm", O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
            /* Replace the fixed output without ever following an existing link. */
            if (fd < 0 && errno == EEXIST) {
                struct stat st;
                if (!fstatat(s.dir, "screenshot.ppm", &st, AT_SYMLINK_NOFOLLOW)
                    && S_ISREG(st.st_mode) && st.st_uid == geteuid() && st.st_nlink == 1
                    && !unlinkat(s.dir, "screenshot.ppm", 0))
                    fd = openat(s.dir, "screenshot.ppm", O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
            }
            if (fd < 0) { Error(id, "screenshot_unavailable"); return; }
            FILE *f = fdopen(fd, "wb");
            if (!f) { close(fd); Error(id, "screenshot_unavailable"); return; }
            bool ok = s.capture(f);
            if (fclose(f)) ok = false;
            if (!ok) { Error(id, "screenshot_unavailable"); return; }
        }
        Reply(!strcmp(op, "screenshot"));
    }
}
void PlayerControl_BeforeFrame(void)
{
    if (s.listener < 0) return;
    int client = accept(s.listener, NULL, NULL);
    if (client >= 0) {
        if (s.client >= 0) {
            const char busy[] = "{\"id\":null,\"ok\":false,\"error\":\"busy\"}\n";
            send(client, busy, sizeof(busy) - 1, MSG_DONTWAIT | MSG_NOSIGNAL);
            close(client);
        } else if (fcntl(client, F_SETFL, O_NONBLOCK) || fcntl(client, F_SETFD, FD_CLOEXEC)) close(client);
        else { s.client = client; s.deadline = Now() + 30000; }
    }
    if (s.client < 0) return;
    if (Now() > s.deadline) { Disconnect(); return; }
    /* One bounded receive and send per frame. No waiting for an agent. */
    ssize_t n = recv(s.client, s.input + s.used, REQUEST_CAP - 1 - s.used, 0);
    if (!n) { Disconnect(); return; }
    if (n < 0 && errno != EAGAIN && errno != EWOULDBLOCK && errno != EINTR) { Disconnect(); return; }
    if (n > 0) {
        if (s.sent) { Disconnect(); return; }
        bool first = s.used == 0;
        s.used += n; s.input[s.used] = 0;
        char *line = memchr(s.input, '\n', s.used);
        if (memchr(s.input, 0, s.used)) { s.used = 0; Error(0, "malformed"); }
        else if (line) {
            if ((size_t)(line - s.input) + 1 != s.used) {
                s.remaining = s.buttons = 0; Error(0, "busy");
            } else { *line = 0; Execute(); }
            s.used = 0;
        } else if (s.used == REQUEST_CAP - 1) {
            s.remaining = s.buttons = 0; s.used = 0; Error(0, "oversized");
            s.closeAfterWrite = true;
        } else if (first && !s.remaining && !s.size) s.deadline = Now() + 5000;
    }
    if (s.size) {
        n = send(s.client, s.output + s.sent, s.size - s.sent, MSG_DONTWAIT | MSG_NOSIGNAL);
        if (n > 0) {
            s.sent += n;
            if (s.sent == s.size) {
                if (s.closeAfterWrite) { Disconnect(); return; }
                s.sent = s.size = 0; s.deadline = Now() + 30000;
            }
        } else if (n < 0 && errno != EAGAIN && errno != EWOULDBLOCK && errno != EINTR) Disconnect();
    }
}
void PlayerControl_AfterFrame(uint32_t frame)
{
    s.frame = frame;
    if (s.remaining && !--s.remaining) { s.buttons = 0; Reply(false); }
}
uint16_t PlayerControl_Buttons(void) { return s.buttons; }
#else
bool PlayerControl_Init(const char *path, const char *savePath,
                        void (*state)(FILE *, uint32_t), bool (*shot)(FILE *))
{
    (void)savePath; (void)state; (void)shot;
    if (path) fprintf(stderr, "Player control requires Unix sockets.\n");
    return path == NULL;
}
void PlayerControl_Close(void) {}
void PlayerControl_BeforeFrame(void) {}
void PlayerControl_AfterFrame(uint32_t frame) { (void)frame; }
uint16_t PlayerControl_Buttons(void) { return 0; }
#endif
#endif
