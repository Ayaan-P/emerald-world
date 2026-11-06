#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
bool ExpansionControl_BeforeFrame(void); void ExpansionControl_AfterFrame(void);
static uint16_t reg, keys; static unsigned frame, consumed, polls; static void (*state)(FILE*,uint32_t); static bool (*shot)(FILE*);
uint32_t frame_count(void){return frame;}
const uint16_t *frame_pixels(void){static uint16_t pixels[240*160];return pixels;}
volatile uint16_t *gba_io_u16(uint32_t offset){assert(offset==0x130);return &reg;}
int inspect_get(const char *key,char *out,size_t size){snprintf(out,size,"%s",!strcmp(key,"map")?"1.2":!strcmp(key,"pos")?"3,4":"0");return 0;}
bool PlayerControl_Init(const char *p,const char *s,void (*st)(FILE*,uint32_t),bool (*sc)(FILE*)){assert(!strcmp(p,"/tmp/profile/player.sock")&&!strcmp(s,"/tmp/profile/game.sav"));state=st;shot=sc;return true;}
void PlayerControl_BeforeFrame(void){polls++;keys=1;}
void PlayerControl_AfterFrame(uint32_t f){assert(f==1);assert(reg==0x3fe);consumed++;}
uint16_t PlayerControl_Buttons(void){return keys;}
int main(void){setenv("EW_EXPANSION_CONTROL","/tmp/profile/player.sock",1);setenv("EW_EXPANSION_SAVE","/tmp/profile/game.sav",1);
 assert(ExpansionControl_BeforeFrame()); assert(consumed==0);frame=1;ExpansionControl_AfterFrame();assert(polls==1&&reg==0x3fe);assert(ExpansionControl_BeforeFrame());assert(consumed==1);
 FILE *f=tmpfile();assert(f);state(f,frame);rewind(f);char buf[256];assert(fgets(buf,sizeof buf,f));assert(strstr(buf,"\"map\":[1,2]")&&strstr(buf,"\"pos\":[3,4]")&&strstr(buf,"\"battle\":false"));fclose(f);
 f=tmpfile();assert(f&&shot(f));assert(ftell(f)>240*160*3);fclose(f);return 0;}
