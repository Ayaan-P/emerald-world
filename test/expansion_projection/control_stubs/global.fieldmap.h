#ifndef STUB_FIELDMAP_H
#define STUB_FIELDMAP_H
#define OBJECT_EVENTS_COUNT 4
struct ObjectEvent { unsigned active,isPlayer,invisible,offScreen,facingDirection; struct { int x,y; } currentCoords; };
struct PlayerAvatar { unsigned objectEventId; };
extern struct ObjectEvent gObjectEvents[OBJECT_EVENTS_COUNT]; extern struct PlayerAvatar gPlayerAvatar;
#endif
