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
static void Digest(const u8 *cells, char hex[65])
{
    static const u8 magic[8]={'E','W','G','M','A','P','0','1'};
    static const char alphabet[]="0123456789abcdef";
    u32 state[8]={0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
    /* 969 bytes + 0x80 + length fits exactly sixteen 64-byte blocks. */
    u8 block[64]; unsigned i,j,offset; const unsigned length=8+WORLD_CAVE_CELLS;
    for(offset=0;offset<1024;offset+=64) {
        memset(block,0,sizeof(block));
        for(i=0;i<64;i++) {
            unsigned p=offset+i;
            if(p<8) block[i]=magic[p];
            else if(p<length) block[i]=cells[p-8];
            else if(p==length) block[i]=0x80;
        }
        if(offset==960) {
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
static bool8 ValidId(const char *id)
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
    if (!wire || !t || n<2 || n>5) return -1;
    for(i=0;i<n;i++) if (!t[i]) return -1;
    if (strcmp(t[0],"CAVE")) return -1;
    if (n==3 && !strcmp(t[1],"BEGIN")) {
        if(wire->active || !ValidId(t[2])) return -1;
        memcpy(wire->id,t[2],65);wire->nextRow=0;wire->active=TRUE;return 0;
    }
    if(!wire->active || n<3 || strcmp(wire->id,t[2])) return -1;
    if(n==5 && !strcmp(t[1],"ROW")) {
        const char *p=t[3];
        if(!*p || (p[0]=='0' && p[1])) return -1;
        while(*p) { if(*p<'0'||*p>'9'||index>31) return -1; index=index*10+(*p++-'0'); }
        if(index!=wire->nextRow || index>=WORLD_CAVE_SIDE || strlen(t[4])!=WORLD_CAVE_SIDE) return -1;
        for(i=0;i<WORLD_CAVE_SIDE;i++) if(t[4][i]!='.' && t[4][i]!='#') return -1;
        memcpy(wire->cells+index*WORLD_CAVE_SIDE,t[4],WORLD_CAVE_SIDE);wire->nextRow++;return 0;
    }
    if(n==3 && !strcmp(t[1],"END")) {
        if(wire->nextRow!=WORLD_CAVE_SIDE) return -1;
        Digest(wire->cells,digest);
        if(strcmp(digest,wire->id)) return -1;
        wire->active=FALSE;return 1;
    }
    return -1;
}
#endif
