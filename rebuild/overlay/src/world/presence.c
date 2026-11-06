#include "global.h"
#include "world/presence.h"
#ifdef _WIN32
/* The first vertical slice targets the existing Linux local-world transport. */
void EwPresenceTick(void) {}
void EwPresenceShutdown(void) {}
#else
#include "world/presence_wire.h"
#include "world/map_compat.h"
#include "main.h"
#include "overworld.h"
#include "event_object_movement.h"
#include "field_player_avatar.h"
#include "global.fieldmap.h"
#include "script.h"
#include "sprite.h"
#include "pokemon.h"
#include "constants/event_objects.h"
#include <errno.h>
#include <limits.h>
#include <fcntl.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

struct RemoteSprite {
    char name[25];
    u8 sprite, virtualId;
    u16 graphics;
    void (*callback)(struct Sprite *);
};
static struct {
    int initialized, enabled, fd, connecting;
    char socketPath[sizeof(((struct sockaddr_un *)0)->sun_path)];
    char name[25], token[65];
    char out[512]; size_t outUsed, outSent;
    unsigned tick, lastReceive, seq, retry;
    struct EwWire wire;
    struct RemoteSprite remote[EW_MAX_PEERS];
} sPresence;

static int valid_hex(const char *s)
{
    if (strlen(s)!=64) return 0;
    for (unsigned i=0;i<64;i++) {
        unsigned char c=s[i];
        if (!((c>='0'&&c<='9')||(c>='a'&&c<='f')||(c>='A'&&c<='F'))) return 0;
    }
    return 1;
}
static int config(const char *path)
{
    FILE *f=fopen(path,"rb"); char line[1200],key[32],value[1100],extra; unsigned found=0;
    if (!f) return 0;
    /* Reject NUL/control bytes before C string parsing can hide them. */
    {
        int c;
        while ((c=fgetc(f))!=EOF)
            if ((c<32 && c!='\t' && c!='\r' && c!='\n') || c==127) {fclose(f);return 0;}
        if (ferror(f) || fseek(f,0,SEEK_SET)!=0) {fclose(f);return 0;}
    }
    while (fgets(line,sizeof(line),f)) {
        size_t n=strlen(line);
        if ((!n || (line[n-1]!='\n' && !feof(f)))) {fclose(f);return 0;}
        if (line[0]=='#' || line[0]=='\n') continue;
        if (sscanf(line,"%31s %1099s %c",key,value,&extra)!=2) {fclose(f);return 0;}
        if (!strcmp(key,"socket")) {
            if ((found&1) || value[0]!='/' || strlen(value)>=sizeof(sPresence.socketPath)) {fclose(f);return 0;}
            strcpy(sPresence.socketPath,value);found|=1;
        } else if (!strcmp(key,"trainer")) {
            if ((found&2) || !EwValidName(value)) {fclose(f);return 0;}
            strcpy(sPresence.name,value);found|=2;
        } else if (!strcmp(key,"token")) {
            if ((found&4) || !valid_hex(value)) {fclose(f);return 0;}
            strcpy(sPresence.token,value);found|=4;
        } else if (strcmp(key,"telemetry") && strcmp(key,"visible_peers")) {fclose(f);return 0;}
    }
    { int failed=ferror(f); if (fclose(f)!=0) failed=1; if (failed) return 0; }
    return found==7;
}
static int owned(const struct RemoteSprite *r)
{
    return r->name[0] && r->sprite<MAX_SPRITES && gSprites[r->sprite].inUse
        && gSprites[r->sprite].callback==r->callback
        && (u8)gSprites[r->sprite].data[0]==r->virtualId;
}
static void remove_remote(struct RemoteSprite *r)
{
    if (owned(r)) DestroySprite(&gSprites[r->sprite]);
    memset(r,0,sizeof(*r));
}
static void clear_remotes(void)
{
    for (unsigned i=0;i<EW_MAX_PEERS;i++) remove_remote(&sPresence.remote[i]);
}
static void disconnect_world(void)
{
    if (sPresence.fd>=0) close(sPresence.fd);
    sPresence.fd=-1;sPresence.connecting=0;sPresence.outUsed=sPresence.outSent=0;
    sPresence.retry=120;sPresence.seq=0;EwWireInit(&sPresence.wire,sPresence.name);clear_remotes();
}
static void open_world(void)
{
    struct sockaddr_un addr; int flags,r;
    if (sPresence.retry) {sPresence.retry--;return;}
    sPresence.fd=socket(AF_UNIX,SOCK_STREAM,0);
    if (sPresence.fd<0) {sPresence.retry=120;return;}
    flags=fcntl(sPresence.fd,F_GETFL,0);
    if (flags<0 || fcntl(sPresence.fd,F_SETFL,flags|O_NONBLOCK)<0) {disconnect_world();return;}
    memset(&addr,0,sizeof(addr));addr.sun_family=AF_UNIX;strcpy(addr.sun_path,sPresence.socketPath);
    r=connect(sPresence.fd,(struct sockaddr *)&addr,sizeof(addr));
    if (r<0 && errno!=EINPROGRESS) {disconnect_world();return;}
    sPresence.connecting=(r<0);sPresence.lastReceive=sPresence.tick;
    sPresence.outUsed=snprintf(sPresence.out,sizeof(sPresence.out),"HELLO 1 %s %s SOCIAL\n",sPresence.name,sPresence.token);
    sPresence.outSent=0;
}
static void io_world(void)
{
    char input[4096];
    if (sPresence.fd<0) {open_world();return;}
    if (sPresence.connecting) {
        struct pollfd p={sPresence.fd,POLLOUT,0};int error=0;socklen_t size=sizeof(error);
        int r=poll(&p,1,0);
        if (r<0 && errno==EINTR) return;
        if (r<0 || (r && (getsockopt(sPresence.fd,SOL_SOCKET,SO_ERROR,&error,&size)<0 || error))) {disconnect_world();return;}
        if (!r) return;
        sPresence.connecting=0;
    }
    while (sPresence.outSent<sPresence.outUsed) {
        ssize_t n=send(sPresence.fd,sPresence.out+sPresence.outSent,sPresence.outUsed-sPresence.outSent,MSG_NOSIGNAL);
        if (n>0) sPresence.outSent+=n;
        else if (n<0 && errno==EINTR) continue;
        else if (n<0 && (errno==EAGAIN || errno==EWOULDBLOCK)) break;
        else {disconnect_world();return;}
    }
    if (sPresence.outSent==sPresence.outUsed) sPresence.outSent=sPresence.outUsed=0;
    for (unsigned i=0;i<4;i++) {
        ssize_t n=recv(sPresence.fd,input,sizeof(input),0);
        if (n>0) {
            sPresence.lastReceive=sPresence.tick;
            if (!EwWireFeed(&sPresence.wire,input,n)) {disconnect_world();return;}
        } else if (n==0) {disconnect_world();return;}
        else if (errno==EINTR) continue;
        else if (errno==EAGAIN || errno==EWOULDBLOCK) break;
        else {disconnect_world();return;}
    }
    if (sPresence.tick-sPresence.lastReceive>900) disconnect_world();
}
static int field_ready(void)
{
    return gSaveBlock1Ptr && gMapHeader.mapLayout && !gMain.inBattle
        && EwMapSupported(gSaveBlock1Ptr->location.mapGroup,gSaveBlock1Ptr->location.mapNum)
        && gMain.callback2==CB2_Overworld && gPlayerAvatar.objectEventId<OBJECT_EVENTS_COUNT
        && gObjectEvents[gPlayerAvatar.objectEventId].active
        && gObjectEvents[gPlayerAvatar.objectEventId].isPlayer;
}
static void fingerprint(const void *data,size_t len,char out[17])
{
    const u8 *p=data;u64 h=0xcbf29ce484222325ULL;
    for(size_t i=0;i<len;i++) h=(h^p[i])*0x100000001b3ULL;
    snprintf(out,17,"%016llx",(unsigned long long)h);
}
static void publish(void)
{
    char party[17],bag[17];unsigned group=0,map=0,x=0,y=0,face=1,gfx=7,ready=0;
    if (sPresence.fd<0 || sPresence.connecting || !sPresence.wire.welcomed || sPresence.outUsed || sPresence.seq==UINT_MAX) return;
    if (field_ready()) {
        const struct ObjectEvent *player=&gObjectEvents[gPlayerAvatar.objectEventId];
        int px=player->currentCoords.x-MAP_OFFSET,py=player->currentCoords.y-MAP_OFFSET;
        if (px>=0 && py>=0 && px<=1024 && py<=1024 && player->facingDirection>=1 && player->facingDirection<=4 && player->graphicsId<=255) {
            group=gSaveBlock1Ptr->location.mapGroup;map=gSaveBlock1Ptr->location.mapNum;x=px;y=py;
            face=player->facingDirection;gfx=player->graphicsId;ready=!ScriptContext_IsEnabled();
        }
    }
    fingerprint(gPlayerParty,sizeof(gPlayerParty),party);
    if (gSaveBlock1Ptr) fingerprint(&gSaveBlock1Ptr->bag,sizeof(gSaveBlock1Ptr->bag),bag);
    else fingerprint(NULL,0,bag);
    if (!ready) {group=map=x=y=0;face=1;gfx=7;}
    sPresence.outUsed=snprintf(sPresence.out,sizeof(sPresence.out),"STATE %u %u %u %u %u %u %u %u %s %s\n",
        ++sPresence.seq,group,map,x,y,face,gfx,ready,party,bag);
    sPresence.outSent=0;
}
static u16 safe_graphics(unsigned gfx)
{
    switch (gfx) {
    case OBJ_EVENT_GFX_BRENDAN_NORMAL: case OBJ_EVENT_GFX_MAY_NORMAL:
    case OBJ_EVENT_GFX_BRENDAN_MACH_BIKE: case OBJ_EVENT_GFX_MAY_MACH_BIKE:
    case OBJ_EVENT_GFX_BRENDAN_ACRO_BIKE: case OBJ_EVENT_GFX_MAY_ACRO_BIKE:
        return gfx;
    default:return OBJ_EVENT_GFX_BRENDAN_NORMAL;
    }
}
static void render(void)
{
    unsigned i,j;
    if (!field_ready() || sPresence.fd<0 || !sPresence.wire.welcomed) {clear_remotes();return;}
    for(i=0;i<EW_MAX_PEERS;i++) {
        struct RemoteSprite *r=&sPresence.remote[i];
        if (!r->name[0]) continue;
        for(j=0;j<sPresence.wire.live.count;j++) if (!strcmp(r->name,sPresence.wire.live.peers[j].name)) break;
        if(j==sPresence.wire.live.count || !owned(r)
         || sPresence.wire.live.peers[j].group!=gSaveBlock1Ptr->location.mapGroup
         || sPresence.wire.live.peers[j].map!=gSaveBlock1Ptr->location.mapNum) remove_remote(r);
    }
    for(i=0;i<sPresence.wire.live.count;i++) {
        const struct EwPeer *p=&sPresence.wire.live.peers[i];struct RemoteSprite *r=NULL;
        u16 gfx=safe_graphics(p->graphics);s16 x,y;u8 id;
        if (p->group!=gSaveBlock1Ptr->location.mapGroup || p->map!=gSaveBlock1Ptr->location.mapNum) continue;
        for(j=0;j<EW_MAX_PEERS;j++) if (!strcmp(sPresence.remote[j].name,p->name)) {r=&sPresence.remote[j];break;}
        if (r && r->graphics!=gfx) {remove_remote(r);r=NULL;}
        if (!r) {
            for(j=0;j<EW_MAX_PEERS;j++) if (!sPresence.remote[j].name[0]) {r=&sPresence.remote[j];break;}
            if (!r) break;
            id=CreateVirtualObject(gfx,240+j,p->x,p->y,0,p->facing);
            if (id>=MAX_SPRITES) continue;
            strcpy(r->name,p->name);r->sprite=id;r->virtualId=240+j;r->graphics=gfx;r->callback=gSprites[id].callback;
        }
        if (!owned(r)) {memset(r,0,sizeof(*r));continue;}
        x=p->x+MAP_OFFSET;y=p->y+MAP_OFFSET;SetSpritePosToOffsetMapCoords(&x,&y,8,16);
        gSprites[r->sprite].x=x;gSprites[r->sprite].y=y+gSprites[r->sprite].centerToCornerVecY;
        StartSpriteAnim(&gSprites[r->sprite],GetFaceDirectionAnimNum(p->facing));
    }
}
void EwPresenceShutdown(void)
{
    if (sPresence.initialized && sPresence.enabled) disconnect_world();
    memset(&sPresence,0,sizeof(sPresence));sPresence.fd=-1;
}
void EwPresenceTick(void)
{
    if (!sPresence.initialized) {
        const char *path=getenv("EW_WORLD_CONFIG");sPresence.initialized=1;sPresence.fd=-1;
        if (!path || !config(path)) return;
        sPresence.enabled=1;EwWireInit(&sPresence.wire,sPresence.name);
    }
    if (!sPresence.enabled) return;
    sPresence.tick++;io_world();
    if (sPresence.tick%8==0) publish();
    render();
}
#endif
