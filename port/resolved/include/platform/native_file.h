#ifndef GUARD_PLATFORM_NATIVE_FILE_H
#define GUARD_PLATFORM_NATIVE_FILE_H
#ifdef PORTABLE
#include <stdio.h>
#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <stdlib.h>
#include <errno.h>

/* SDL2's Windows main and SDL_GetPrefPath supply UTF-8, not the ANSI codepage.
 * Configuration file paths use the same encoding. Convert only at the OS edge. */
static inline wchar_t *NativeFile_Wide(const char *text)
{
    int length;
    wchar_t *wide;
    if (!text) { errno = EINVAL; return NULL; }
    length = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, text, -1, NULL, 0);
    if (!length) { errno = EILSEQ; return NULL; }
    if ((size_t)length > (size_t)-1 / sizeof(*wide)) { errno = ENOMEM; return NULL; }
    wide = malloc((size_t)length * sizeof(*wide));
    if (!wide) { errno = ENOMEM; return NULL; }
    if (!MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, text, -1, wide, length)) {
        free(wide);
        errno = EILSEQ;
        return NULL;
    }
    return wide;
}

static inline FILE *NativeFile_Open(const char *path, const char *mode)
{
    wchar_t *widePath = NativeFile_Wide(path);
    wchar_t *wideMode;
    FILE *file;
    int error;
    if (!widePath) return NULL;
    wideMode = NativeFile_Wide(mode);
    if (!wideMode) { free(widePath); return NULL; }
    file = _wfopen(widePath, wideMode);
    error = errno;
    free(wideMode);
    free(widePath);
    errno = error;
    return file;
}

static inline int NativeFile_Replace(const char *from, const char *to)
{
    wchar_t *wideFrom = NativeFile_Wide(from);
    wchar_t *wideTo;
    int result;
    if (!wideFrom) return -1;
    wideTo = NativeFile_Wide(to);
    if (!wideTo) { free(wideFrom); return -1; }
    /* Same-directory replacement without a delete/read gap. */
    result = MoveFileExW(wideFrom, wideTo, MOVEFILE_REPLACE_EXISTING) ? 0 : -1;
    free(wideTo);
    free(wideFrom);
    return result;
}
#else
static inline FILE *NativeFile_Open(const char *path, const char *mode)
{
    return fopen(path, mode);
}

static inline int NativeFile_Replace(const char *from, const char *to)
{
    return rename(from, to);
}
#endif
#endif /* PORTABLE */
#endif /* GUARD_PLATFORM_NATIVE_FILE_H */
