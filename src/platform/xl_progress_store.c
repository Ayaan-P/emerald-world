#include "platform/xl_progress_store.h"
#include <string.h>
#if defined(PORTABLE) && !defined(_WIN32)
#include "platform/native_save.h"
#include <stdint.h>
#include <stdio.h>
#include <sys/stat.h>
#include <unistd.h>
#include <errno.h>
#define PAYLOAD_SIZE (1 + 64 * (6 + 64))
#define HEADER_SIZE 12
#define SNAPSHOT_SIZE (HEADER_SIZE + PAYLOAD_SIZE)
static FILE *sFile;
static unsigned char sJournal[2][SNAPSHOT_SIZE];
static unsigned sCurrent;
static uint32_t get32(const unsigned char *p){return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static void put32(unsigned char *p,uint32_t v){p[0]=v;p[1]=v>>8;p[2]=v>>16;p[3]=v>>24;}
static uint32_t checksum(const unsigned char *p){uint32_t h=2166136261u;size_t i;for(i=0;i<SNAPSHOT_SIZE;i++)if(i<8||i>=12){h^=p[i];h*=16777619u;}return h;}
static bool valid(const unsigned char *p){return !memcmp(p,"XLP2",4) && get32(p+8)==checksum(p);}
void XLProgressStore_Close(void){if(sFile){fclose(sFile);sFile=NULL;}memset(sJournal,0,sizeof(sJournal));sCurrent=0;}
bool XLProgressStore_Init(const char *savePath,bool enabled,void *payload,size_t size)
{
    char path[4096];struct stat info;bool a,b;
    if(!enabled || !savePath || !payload || size!=PAYLOAD_SIZE || sFile)return false;
    if(snprintf(path,sizeof(path),"%s.generated-story",savePath)>=(int)sizeof(path))return false;
    sFile=NativeSave_Open(path);if(!sFile)return false;
    if(fstat(fileno(sFile),&info)!=0 || (info.st_mode&077)!=0)goto fail;
    memset(sJournal,0,sizeof(sJournal));sCurrent=0;
    if(info.st_size==0){memset(payload,0,size);return true;}
    if(info.st_size!=(off_t)sizeof(sJournal) || !NativeSave_Read(sFile,0,sJournal,sizeof(sJournal)))goto fail;
    a=valid(sJournal[0]);b=valid(sJournal[1]);if(!a&&!b)goto fail;
    sCurrent=b && (!a || (int32_t)(get32(sJournal[1]+4)-get32(sJournal[0]+4))>0);
    memcpy(payload,sJournal[sCurrent]+HEADER_SIZE,size);return true;
fail:
    XLProgressStore_Close();return false;
}
static bool write_slot(unsigned slot,const unsigned char *data)
{
    size_t done=0;int fd=fileno(sFile);struct stat info;
    if(fstat(fd,&info)!=0 || !S_ISREG(info.st_mode) || info.st_nlink!=1 || info.st_uid!=geteuid() || (info.st_mode&077)!=0)return false;
    while(done<SNAPSHOT_SIZE){ssize_t n=pwrite(fd,data+done,SNAPSHOT_SIZE-done,(off_t)(slot*SNAPSHOT_SIZE+done));
        if(n<0 && errno==EINTR)continue;
        if(n<=0)return false;
        done+=(size_t)n;
    }
    while(fsync(fd)!=0)if(errno!=EINTR)return false;
    return true;
}
bool XLProgressStore_Save(const void *payload,size_t size)
{
    unsigned next;struct stat info;uint32_t sequence;
    if(!sFile || !payload || size!=PAYLOAD_SIZE)return false;
    if(fstat(fileno(sFile),&info)!=0 || (info.st_mode&077)!=0){XLProgressStore_Close();return false;}
    next=sCurrent^1;sequence=valid(sJournal[sCurrent])?get32(sJournal[sCurrent]+4)+1:1;
    memset(sJournal[next],0,SNAPSHOT_SIZE);memcpy(sJournal[next],"XLP2",4);put32(sJournal[next]+4,sequence);memcpy(sJournal[next]+HEADER_SIZE,payload,size);put32(sJournal[next]+8,checksum(sJournal[next]));
    if(!write_slot(next,sJournal[next])){XLProgressStore_Close();return false;}
    sCurrent=next;return true;
}
#else
bool XLProgressStore_Init(const char *path,bool enabled,void *payload,size_t size){(void)path;(void)enabled;(void)payload;(void)size;return false;}
bool XLProgressStore_Save(const void *payload,size_t size){(void)payload;(void)size;return false;}
void XLProgressStore_Close(void){}
#endif
