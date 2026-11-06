#include "world/presence_wire.h"
#include <ctype.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>

int EwValidName(const char *s)
{
    size_t n=0;
    if (!s) return 0;
    while (s[n]) {
        unsigned char c=(unsigned char)s[n++];
        if (n>24 || !((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'||c=='-')) return 0;
    }
    return n!=0;
}
void EwWireInit(struct EwWire *w,const char *own)
{
    memset(w,0,sizeof(*w));
    if (EwValidName(own)) memcpy(w->own,own,strlen(own)+1);
}
static int number(const char *s,uint64_t max,uint64_t *out)
{
    uint64_t n=0;
    if (!*s) return 0;
    while (*s) {
        unsigned d=(unsigned char)*s++-'0';
        if (d>9 || d>max || n>(max-d)/10) return 0;
        n=n*10+d;
    }
    *out=n; return 1;
}
static int parse(struct EwWire *w,char *line)
{
    char *v[12],*p=line; unsigned n=0,i; uint64_t x[7],rev;
    while (*p) {
        while (*p==' ') p++;
        if (!*p) break;
        if (n==12) return 0;
        v[n++]=p;
        while (*p && *p!=' ') p++;
        if (*p) *p++=0;
    }
    if (!n) return 0;
    if (!strcmp(v[0],"ERROR")) return 0;
    if (!strcmp(v[0],"WELCOME")) {
        if (n!=4 || w->welcomed || strcmp(v[1],"1") || strcmp(v[2],w->own) || !number(v[3],UINT64_MAX,&rev)) return 0;
        w->welcomed=1; return 1;
    }
    if (!w->welcomed) return 0;
    if (!strcmp(v[0],"BEGIN")) {
        if (n!=2 || w->collecting || !number(v[1],UINT64_MAX,&rev) || rev<w->live.revision) return 0;
        memset(&w->pending,0,sizeof(w->pending));w->pending.revision=rev;w->collecting=1;return 1;
    }
    if (!strcmp(v[0],"END")) {
        if (n!=1 || !w->collecting) return 0;
        w->live=w->pending;w->collecting=0;return 1;
    }
    if (!w->collecting) return 0;
    if (strcmp(v[0],"PEER")) return 1; /* Other World features are not consumed yet. */
    if (n!=9 || !EwValidName(v[1]) || !strcmp(v[1],w->own) || w->pending.count>=EW_MAX_PEERS) return 0;
    for(i=0;i<w->pending.count;i++) if (!strcmp(w->pending.peers[i].name,v[1])) return 0;
    for(i=0;i<7;i++) if(!number(v[i+2],i<2?255:i<4?1024:i==4?4:i==5?255:1,&x[i])) return 0;
    if(x[4]<1) return 0;
    struct EwPeer *peer=&w->pending.peers[w->pending.count++];
    memcpy(peer->name,v[1],strlen(v[1])+1);
    peer->group=x[0];peer->map=x[1];peer->x=x[2];peer->y=x[3];peer->facing=x[4];peer->graphics=x[5];peer->ready=x[6];
    return 1;
}
int EwWireFeed(struct EwWire *w,const char *bytes,size_t length)
{
    size_t i;
    for(i=0;i<length;i++) {
        unsigned char c=(unsigned char)bytes[i];
        if (c=='\n') {
            if (w->used && w->line[w->used-1]=='\r') w->used--;
            w->line[w->used]=0;
            if(!parse(w,w->line)) return 0;
            w->used=0;
        } else {
            if (c<32 || c>126 || w->used>=EW_LINE_CAP-1) return 0;
            w->line[w->used++]=(char)c;
        }
    }
    return 1;
}
