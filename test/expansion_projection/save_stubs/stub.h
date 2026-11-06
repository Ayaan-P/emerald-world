#ifndef SAVE_STUB_H
#define SAVE_STUB_H
typedef unsigned char bool8; typedef unsigned int u32;
#define TRUE 1
extern u32 gDamagedSaveSectors;
int frame_flush_save(void); int NativeLink_IsActive(void);
#endif
