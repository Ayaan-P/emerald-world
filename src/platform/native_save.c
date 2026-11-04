#if defined(PORTABLE) && !defined(_WIN32)
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>
#include "platform/native_save.h"

FILE *NativeSave_Open(const char *path)
{
    struct stat info;
    FILE *stream;
    int error;
    /* Never retry a failed existing-file open with a truncating create. The
     * nonblocking flag also makes a FIFO fail before the game starts. */
    int fd = open(path, O_RDWR | O_CREAT | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC, 0600);
    if (fd < 0)
        return NULL;
    if (fstat(fd, &info) != 0)
        goto fail;
    if (!S_ISREG(info.st_mode) || info.st_nlink != 1 || info.st_uid != geteuid()
        || info.st_size > INT_MAX)
    {
        errno = EINVAL;
        goto fail;
    }
    if (flock(fd, LOCK_EX | LOCK_NB) != 0)
        goto fail;
    stream = fdopen(fd, "r+b");
    if (stream != NULL)
        return stream;
fail:
    error = errno;
    close(fd);
    errno = error;
    return NULL;
}

const char *NativeSave_OpenError(void)
{
    /* Fixed text only. Never include a save path or operating-system echo. */
    switch (errno)
    {
    case EAGAIN:
        return "This save is open in another game. Close that game before retrying.";
    case ELOOP:
    case EINVAL:
        return "Choose your own regular save file without links.";
    default:
        return "Check that the save file and its folder exist and are writable.";
    }
}

bool NativeSave_Read(FILE *stream, size_t offset, void *destination, size_t size)
{
    unsigned char *bytes = destination;
    size_t done = 0;
    if (stream == NULL || offset > LONG_MAX || size > (size_t)LONG_MAX - offset)
        return false;
    /* Flash reads use the lifetime-owned inode, not a path that may now name
     * another file. pread does not disturb buffered save-write positioning. */
    while (done < size)
    {
        ssize_t count = pread(fileno(stream), bytes + done, size - done, (off_t)(offset + done));
        if (count < 0 && errno == EINTR)
            continue;
        if (count <= 0)
            return false;
        done += count;
    }
    return true;
}

bool NativeSave_Write(FILE *stream, const void *source, size_t size)
{
    struct stat info;
    if (stream == NULL || fstat(fileno(stream), &info) != 0)
        return false;
    // Startup ownership can change while the game runs. An unlinked stream
    // cannot persist a save, and a new alias must not receive private writes.
    if (!S_ISREG(info.st_mode) || info.st_nlink != 1 || info.st_uid != geteuid())
    {
        errno = EINVAL;
        return false;
    }
    // A later explicit retry may recover after space or permissions are fixed.
    clearerr(stream);
    if (fseek(stream, 0, SEEK_SET) != 0
     || fwrite(source, 1, size, stream) != size
     || fflush(stream) != 0)
        return false;
    // The game may acknowledge a save only after this owned file is durable.
    // Keep its inode lock rather than replacing the file behind another owner.
    while (fsync(fileno(stream)) != 0)
        if (errno != EINTR)
            return false;
    return true;
}
#endif
