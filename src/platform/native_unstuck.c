#if defined(PORTABLE) && !defined(_WIN32)
#include <errno.h>
#include <fcntl.h>
#include <sys/file.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include "platform/native_save.h"
#include "platform/native_unstuck.h"

#define COOLDOWN_SECONDS 300u
#define RECORD_SIZE 32u
#define PREFIX "EWUNSTUCK1 "
static char sSavePath[4096];

bool NativeUnstuck_SetSavePath(const char *savePath)
{
    size_t length = savePath ? strlen(savePath) : 0;
    sSavePath[0] = 0;
    if (!length || length >= sizeof(sSavePath) || savePath[0] != '/') return false;
    memcpy(sSavePath, savePath, length + 1);
    return true;
}

enum NativeUnstuckResult NativeUnstuck_ReserveCurrent(uint64_t now, bool boxed, unsigned *remaining)
{
    return NativeUnstuck_Reserve(sSavePath, now, boxed, remaining);
}

enum NativeUnstuckResult NativeUnstuck_Reserve(const char *savePath, uint64_t now,
                                                bool boxed, unsigned *remaining)
{
    char path[4096], canonical[4096], record[RECORD_SIZE + 1];
    struct stat info, saveInfo;
    FILE *file = NULL;
    int fd, created = 0;
    uint64_t previous = 0;
    unsigned i;
    enum NativeUnstuckResult result = NATIVE_UNSTUCK_STORAGE_ERROR;
    if (remaining) *remaining = 0;
    if (!now) return NATIVE_UNSTUCK_BAD_CLOCK;
    if (!savePath || savePath[0] != '/' || !realpath(savePath, canonical)
        || strcmp(canonical, savePath) || lstat(savePath, &saveInfo)
        || !S_ISREG(saveInfo.st_mode) || saveInfo.st_uid != geteuid() || saveInfo.st_nlink != 1
        || snprintf(path, sizeof(path), "%s.unstuck", savePath) >= (int)sizeof(path))
        return result;
    /* Claim a new sidecar exclusively, or validate an existing one before
     * writing. Never treat an unrelated empty file as a new record. */
    fd = open(path, O_RDWR | O_CREAT | O_EXCL | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC, 0600);
    if (fd >= 0) created = 1;
    else if (errno == EEXIST) fd = open(path, O_RDWR | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0) return result;
    if (fstat(fd, &info) || !S_ISREG(info.st_mode) || info.st_uid != geteuid()
        || info.st_nlink != 1 || (info.st_mode & 077)
        || (created ? info.st_size != 0 : info.st_size != RECORD_SIZE)
        || flock(fd, LOCK_EX | LOCK_NB)) { close(fd); return result; }
    file = fdopen(fd, "r+b");
    if (!file) { close(fd); return result; }
    if (!created) {
        if (!NativeSave_Read(file, 0, record, RECORD_SIZE) || memcmp(record, PREFIX, sizeof(PREFIX)-1)
            || record[RECORD_SIZE-1] != '\n') goto done;
        for (i = sizeof(PREFIX)-1; i < RECORD_SIZE-1; i++) {
            unsigned digit;
            if (record[i] < '0' || record[i] > '9') goto done;
            digit = record[i] - '0';
            if (previous > (UINT64_MAX - digit) / 10) goto done;
            previous = previous * 10 + digit;
        }
        if (!boxed && (now < previous || now - previous < COOLDOWN_SECONDS)) {
            if (remaining) *remaining = now < previous ? COOLDOWN_SECONDS : COOLDOWN_SECONDS - (unsigned)(now - previous);
            result = NATIVE_UNSTUCK_COOLDOWN;
            goto done;
        }
    }
    if (snprintf(record, sizeof(record), PREFIX "%020llu\n", (unsigned long long)now) != RECORD_SIZE) goto done;
    if (!NativeSave_Write(file, record, RECORD_SIZE)) goto done;
    result = NATIVE_UNSTUCK_ALLOWED;
done:
    fclose(file);
    return result;
}
#endif
