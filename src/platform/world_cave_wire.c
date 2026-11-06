#ifdef PORTABLE
#include "global.h"
#include "platform/world_cave_wire.h"
#include <string.h>

/* SHA-256 binds the authenticated authority's ID to all template bytes. */
static const u32 k[64] = {
 0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
 0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
 0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
 0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
 0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
 0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
 0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
 0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
};
static u32 R(u32 x, unsigned n) { return (x >> n) | (x << (32 - n)); }
static void Block(u32 state[8], const u8 block[64])
{
    u32 w[64], a,b,c,d,e,f,g,h,t1,t2;
    unsigned i;
    for (i=0;i<16;i++) w[i]=((u32)block[i*4]<<24)|((u32)block[i*4+1]<<16)|((u32)block[i*4+2]<<8)|block[i*4+3];
    for (;i<64;i++) w[i]=(R(w[i-2],17)^R(w[i-2],19)^(w[i-2]>>10))+w[i-7]
        +(R(w[i-15],7)^R(w[i-15],18)^(w[i-15]>>3))+w[i-16];
    a=state[0];b=state[1];c=state[2];d=state[3];e=state[4];f=state[5];g=state[6];h=state[7];
    for(i=0;i<64;i++) {
        t1=h+(R(e,6)^R(e,11)^R(e,25))+((e&f)^((~e)&g))+k[i]+w[i];
        t2=(R(a,2)^R(a,13)^R(a,22))+((a&b)^(a&c)^(b&c));
        h=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2;
    }
    state[0]+=a;state[1]+=b;state[2]+=c;state[3]+=d;
    state[4]+=e;state[5]+=f;state[6]+=g;state[7]+=h;
}
static void Digest(const u8 *cells, u8 version, u8 profile, const u8 *wildlife, const u8 *guide, const u8 *cast, const u8 *events, char hex[65])
{
    static const u8 magic[8]={'E','W','G','M','A','P','0','1'};
    static const char alphabet[]="0123456789abcdef";
    u32 state[8]={0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
    u8 block[64]; unsigned i,j,offset; const unsigned extra = (version == 9 || version == 12) ? WORLD_CAVE_EVENT_BYTES + WORLD_CAVE_CAST_BYTES : version == 8 ? WORLD_CAVE_CAST_BYTES : version == 7 ? WORLD_CAVE_GUIDE_BYTES : (version == 3 || version == 5) ? 38 : version == 2 ? 1 : 0;
    const unsigned count = version == 12 ? WORLD_CAVE_XL_CELLS : version >= 4 ? WORLD_CAVE_LARGE_CELLS : WORLD_CAVE_CELLS;
    const unsigned length=8+extra+count, padded=((length+9+63)/64)*64;
    for(offset=0;offset<padded;offset+=64) {
        memset(block,0,sizeof(block));
        for(i=0;i<64;i++) {
            unsigned p=offset+i;
            if(p<8) block[i]=(p==7 && version>=2) ? (version==12 ? 'C' : '0' + version) : magic[p];
            else if((version==9 || version==12) && p<8+WORLD_CAVE_EVENT_BYTES) block[i]=events[p-8];
            else if((version==9 || version==12) && p<8+WORLD_CAVE_EVENT_BYTES+WORLD_CAVE_CAST_BYTES) block[i]=cast[p-8-WORLD_CAVE_EVENT_BYTES];
            else if(version==8 && p<8+WORLD_CAVE_CAST_BYTES) block[i]=cast[p-8];
            else if(version==7 && p<8+WORLD_CAVE_GUIDE_BYTES) block[i]=guide[p-8];
            else if(extra && p==8) block[i]=profile;
            else if((version==3 || version==5) && p<46) block[i]=wildlife[p-9];
            else if(p<length) block[i]=cells[p-8-extra];
            else if(p==length) block[i]=0x80;
        }
        if(offset==padded-64) {
            u32 bits=length*8;
            block[60]=bits>>24;block[61]=bits>>16;block[62]=bits>>8;block[63]=bits;
        }
        Block(state,block);
    }
    for(i=0;i<8;i++) for(j=0;j<4;j++) {
        u8 byte=(state[i]>>(24-j*8))&0xff;
        hex[(i*4+j)*2]=alphabet[byte>>4];hex[(i*4+j)*2+1]=alphabet[byte&15];
    }
    hex[64]=0;
}
void WorldCaveWire_XLEventDigest(const u8 *events,const u8 *cast,const u8 *cells,char hex[65])
{
    Digest(cells,12,0,NULL,NULL,cast,events,hex);
}
bool8 WorldCaveWire_ValidId(const char *id)
{
    unsigned i;
    if (!id || strlen(id)!=WORLD_CAVE_ID) return FALSE;
    for(i=0;i<WORLD_CAVE_ID;i++) if(!((id[i]>='0'&&id[i]<='9')||(id[i]>='a'&&id[i]<='f'))) return FALSE;
    return TRUE;
}
void WorldCaveWire_Reset(struct WorldCaveWire *wire) { if(wire) memset(wire,0,sizeof(*wire)); }
int WorldCaveWire_Feed(struct WorldCaveWire *wire, unsigned n, const char *const *t)
{
    unsigned i, index=0;
    char digest[65];
    if (!wire || !t || n<2 || n>7) return -1;
    for(i=0;i<n;i++) if (!t[i]) return -1;
    if (strcmp(t[0],"CAVE")) return -1;
    if (n==3 && !strcmp(t[1],"BEGIN")) {
        if(wire->active || !WorldCaveWire_ValidId(t[2])) return -1;
        memcpy(wire->id,t[2],65);wire->nextRow=0;wire->version=1;wire->profile=0;wire->active=TRUE;return 0;
    }
#if GENERATED_WILDS_EVENTS
    if (n==4 && !strcmp(t[1],"BEGIN") && !strcmp(t[3],"EVENTS")) {
        if(wire->active || !WorldCaveWire_ValidId(t[2])) return -1;
        memcpy(wire->id,t[2],65);wire->nextRow=0;wire->version=9;wire->profile=0;wire->castSeen=FALSE;wire->nextEventChunk=0;wire->active=TRUE;
#if GENERATED_WILDS_SHARED_TERRAIN
        wire->terrainSeen=FALSE;
#if GENERATED_WILDS_LARGE_TERRAIN
        wire->terrainChunkNext=wire->terrainChunkTotal=0;wire->terrainLargeFraming=FALSE;wire->terrainSize=0;
#endif
#endif
        return 0;
    }
#endif
#if GENERATED_WILDS_CAST
    if (n==4 && !strcmp(t[1],"BEGIN") && !strcmp(t[3],"CAST")) {
        if(wire->active || !WorldCaveWire_ValidId(t[2])) return -1;
        memcpy(wire->id,t[2],65);wire->nextRow=0;wire->version=8;wire->profile=0;wire->castSeen=FALSE;wire->active=TRUE;return 0;
    }
#endif
#if GENERATED_WILDS_GUIDE
    if (n==4 && !strcmp(t[1],"BEGIN") && !strcmp(t[3],"GUIDE")) {
        if(wire->active || !WorldCaveWire_ValidId(t[2])) return -1;
        memcpy(wire->id,t[2],65);wire->nextRow=0;wire->version=7;wire->profile=0;wire->guideSeen=FALSE;wire->active=TRUE;return 0;
    }
#endif
#if GENERATED_MAP_WILDS
    if (n==4 && !strcmp(t[1],"BEGIN") && !strcmp(t[3],"WILDS")) {
        if(wire->active || !WorldCaveWire_ValidId(t[2])) return -1;
        memcpy(wire->id,t[2],65);wire->nextRow=0;wire->version=6;wire->profile=0;wire->active=TRUE;return 0;
    }
#endif
#if GENERATED_MAP_LARGE
    if (n==4 && !strcmp(t[1],"BEGIN") && !strcmp(t[3],"LARGE")) {
        if(wire->active || !WorldCaveWire_ValidId(t[2])) return -1;
        memcpy(wire->id,t[2],65);wire->nextRow=0;wire->version=4;wire->profile=0;wire->active=TRUE;return 0;
    }
#endif
#if GENERATED_CAVE_PROFILES
    if (n==4 && !strcmp(t[1],"BEGIN")) {
        if(wire->active || !WorldCaveWire_ValidId(t[2]) || strlen(t[3]) != 1 || t[3][0]<'0' || t[3][0]>'3') return -1;
        memcpy(wire->id,t[2],65);wire->nextRow=0;wire->version=2;wire->profile=t[3][0]-'0';wire->active=TRUE;return 0;
    }
#endif
#if GENERATED_CAVE_WILDLIFE
    if (n==5 && !strcmp(t[1],"BEGIN")) {
        if(wire->active || !WorldCaveWire_ValidId(t[2]) || strlen(t[3])!=1 || t[3][0]<'0' || t[3][0]>'3') return -1;
        if (strcmp(t[4],"3")
#if GENERATED_MAP_LARGE
         && strcmp(t[4],"5")
#endif
        ) return -1;
        memcpy(wire->id,t[2],65);wire->nextRow=0;wire->version=t[4][0]-'0';wire->profile=t[3][0]-'0';wire->wildlifeSeen=FALSE;wire->active=TRUE;return 0;
    }
#endif
    if(!wire->active || n<3 || strcmp(wire->id,t[2])) return -1;
#if GENERATED_CAVE_WILDLIFE
    if(n==4 && !strcmp(t[1],"WILD")) {
        if((wire->version!=3 && wire->version!=5) || wire->wildlifeSeen || wire->nextRow || strlen(t[3])!=WORLD_CAVE_WILDLIFE_BYTES*2) return -1;
        for(i=0;i<WORLD_CAVE_WILDLIFE_BYTES*2;i++) {
            char c=t[3][i]; unsigned v;
            if(c>='0' && c<='9') v=c-'0'; else if(c>='a' && c<='f') v=c-'a'+10; else return -1;
            if(!(i&1)) wire->wildlife[i/2]=v<<4; else wire->wildlife[i/2]|=v;
        }
        wire->wildlifeSeen=TRUE;return 0;
    }
#endif
#if GENERATED_WILDS_CAST
    if(n==4 && !strcmp(t[1],"CAST")) {
        if((wire->version!=8 && wire->version!=9) || wire->castSeen || wire->nextRow || strlen(t[3])!=WORLD_CAVE_CAST_BYTES*2) return -1;
        for(i=0;i<WORLD_CAVE_CAST_BYTES*2;i++) {
            char c=t[3][i];unsigned v;
            if(c>='0' && c<='9') v=c-'0'; else if(c>='a' && c<='f') v=c-'a'+10; else return -1;
            if(!(i&1)) wire->cast[i/2]=v<<4; else wire->cast[i/2]|=v;
        }
        wire->castSeen=TRUE;return 0;
    }
#endif
#if GENERATED_WILDS_EVENTS
    if(n==5 && !strcmp(t[1],"EVENTS")) {
        unsigned chunk=wire->nextEventChunk, bytes=chunk<5 ? 256 : 186;
        if(wire->version!=9 || !wire->castSeen || wire->nextRow || chunk>=6 || strlen(t[3])!=1 || t[3][0]!=(char)('0'+chunk) || strlen(t[4])!=bytes*2) return -1;
        for(i=0;i<bytes*2;i++) {char c=t[4][i];unsigned v;
            if(c>='0' && c<='9')v=c-'0';else if(c>='a' && c<='f')v=c-'a'+10;else return -1;
            if(!(i&1))wire->events[chunk*256+i/2]=v<<4;else wire->events[chunk*256+i/2]|=v;
        }
        wire->nextEventChunk++;return 0;
    }
#endif
#if GENERATED_WILDS_SHARED_TERRAIN
    if(n==5 && !strcmp(t[1],"TERRAIN")) {
        const char *p=t[3];unsigned revision=0,length=strlen(t[4]);
        if(wire->version!=9 || !wire->castSeen || wire->nextEventChunk!=6 || wire->terrainSeen || wire->nextRow || !*p || (p[0]=='0' && p[1]) || length<2 || length>386 || (length&1))return -1;
        while(*p) {if(*p<'0'||*p>'9'||revision>(2147483647U-(unsigned)(*p-'0'))/10)return -1;revision=revision*10+(*p++-'0');}
        for(i=0;i<length;i++){char c=t[4][i];unsigned v;if(c>='0'&&c<='9')v=c-'0';else if(c>='a'&&c<='f')v=c-'a'+10;else return -1;
            if(!(i&1))wire->terrain[i/2]=v<<4;else wire->terrain[i/2]|=v;}
        if(wire->terrain[0]>64 || length!=2*(1+3*(unsigned)wire->terrain[0]) || (revision==0 && wire->terrain[0]!=0))return -1;
#if !GENERATED_WILDS_SHARED_GEOMETRY
        if(revision>0 && wire->terrain[0]==0)return -1;
#endif
        wire->terrainSize=length/2;wire->terrainRevision=revision;wire->terrainSeen=TRUE;return 0;
    }
#endif
#if GENERATED_WILDS_LARGE_TERRAIN
    if(n==7 && !strcmp(t[1],"TERRAINH")) {
        const char *p=t[3];unsigned revision=0,chunk,total,length=strlen(t[6]),bytes,i,offset,count;
        if(wire->version!=9 || !wire->castSeen || wire->nextEventChunk!=6 || wire->terrainSeen || wire->nextRow || !*p || (p[0]=='0' && p[1]))return -1;
        while(*p){if(*p<'0'||*p>'9'||revision>(2147483647U-(unsigned)(*p-'0'))/10)return -1;revision=revision*10+(*p++-'0');}
        if(strlen(t[4])!=1 || t[4][0]<'0' || t[4][0]>'7' || strlen(t[5])!=1 || t[5][0]<'1' || t[5][0]>'8')return -1;
        chunk=t[4][0]-'0';total=t[5][0]-'0';
        if(chunk!=wire->terrainChunkNext || chunk>=total || !length || length>400 || (length&1) || (chunk+1<total && length!=400))return -1;
        if(!chunk){wire->terrainRevision=revision;wire->terrainChunkTotal=total;wire->terrainSize=0;wire->terrainLargeFraming=TRUE;}
        else if(wire->terrainRevision!=revision || wire->terrainChunkTotal!=total)return -1;
        bytes=length/2;offset=wire->terrainSize;if(offset+bytes>WORLD_CAVE_TERRAIN_MAX_BYTES)return -1;
        for(i=0;i<length;i++){char c=t[6][i];unsigned v;if(c>='0'&&c<='9')v=c-'0';else if(c>='a'&&c<='f')v=c-'a'+10;else return -1;
            if(!(i&1))wire->terrain[offset+i/2]=v<<4;else wire->terrain[offset+i/2]|=v;}
        wire->terrainSize+=bytes;wire->terrainChunkNext++;
        if(wire->terrainChunkNext==total){
            if(wire->terrain[0]==255){if(wire->terrainSize<3)return -1;count=wire->terrain[1]|((unsigned)wire->terrain[2]<<8);offset=3;if(count<=64||count>512)return -1;}
            else {count=wire->terrain[0];offset=1;if(count>64)return -1;}
            if(wire->terrainSize!=offset+3*count || (revision==0 && count!=0))return -1;
            wire->terrainSeen=TRUE;
        }
        return 0;
    }
#endif
#if GENERATED_WILDS_GUIDE
    if(n==4 && !strcmp(t[1],"GUIDE")) {
        if(wire->version!=7 || wire->guideSeen || wire->nextRow || strlen(t[3])!=WORLD_CAVE_GUIDE_BYTES*2) return -1;
        for(i=0;i<WORLD_CAVE_GUIDE_BYTES*2;i++) {
            char c=t[3][i];unsigned v;
            if(c>='0' && c<='9') v=c-'0'; else if(c>='a' && c<='f') v=c-'a'+10; else return -1;
            if(!(i&1)) wire->guide[i/2]=v<<4; else wire->guide[i/2]|=v;
        }
        wire->guideSeen=TRUE;return 0;
    }
#endif
    if(n==5 && !strcmp(t[1],"ROW")) {
        const char *p=t[3];
        const unsigned side = wire->version>=4 ? WORLD_CAVE_LARGE_SIDE : WORLD_CAVE_SIDE;
        if((wire->version==3 || wire->version==5) && !wire->wildlifeSeen) return -1;
        if(wire->version==7 && !wire->guideSeen) return -1;
#if GENERATED_WILDS_CAST
        if(wire->version==8 && !wire->castSeen) return -1;
#if GENERATED_WILDS_EVENTS
        if(wire->version==9 && (!wire->castSeen || wire->nextEventChunk!=6)) return -1;
#endif
#endif
        if(!*p || (p[0]=='0' && p[1])) return -1;
        while(*p) { if(*p<'0'||*p>'9'||index>63) return -1; index=index*10+(*p++-'0'); }
        if(index!=wire->nextRow || index>=side || strlen(t[4])!=side) return -1;
        for(i=0;i<side;i++) if(t[4][i]!='.' && t[4][i]!='#') return -1;
        memcpy(wire->cells+index*side,t[4],side);wire->nextRow++;return 0;
    }
    if(n==3 && !strcmp(t[1],"END")) {
        if(wire->nextRow!=(wire->version>=4 ? WORLD_CAVE_LARGE_SIDE : WORLD_CAVE_SIDE) || ((wire->version==3 || wire->version==5) && !wire->wildlifeSeen) || (wire->version==7 && !wire->guideSeen)) return -1;
#if GENERATED_WILDS_CAST
        if(wire->version==8 && !wire->castSeen) return -1;
#if GENERATED_WILDS_EVENTS
        if(wire->version==9 && (!wire->castSeen || wire->nextEventChunk!=6)) return -1;
        Digest(wire->cells,wire->version,wire->profile,wire->wildlife,wire->guide,wire->cast,wire->events,digest);
#else
        Digest(wire->cells,wire->version,wire->profile,wire->wildlife,wire->guide,wire->cast,NULL,digest);
#endif
#else
        Digest(wire->cells,wire->version,wire->profile,wire->wildlife,wire->guide,NULL,NULL,digest);
#endif
        if(strcmp(digest,wire->id)) return -1;
        wire->active=FALSE;return 1;
    }
    return -1;
}
#endif
