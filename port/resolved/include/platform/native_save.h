#ifndef GUARD_PLATFORM_NATIVE_SAVE_H
#define GUARD_PLATFORM_NATIVE_SAVE_H

#if defined(PORTABLE) && !defined(_WIN32)
#include <stdio.h>
#include <stddef.h>
#include <stdbool.h>

/* The stream owns an exclusive inode lock until fclose. */
FILE *NativeSave_Open(const char *path);
const char *NativeSave_OpenError(void);
bool NativeSave_Read(FILE *stream, size_t offset, void *destination, size_t size);
bool NativeSave_Write(FILE *stream, const void *source, size_t size);
#endif

#endif
