# Combined-region building interactions

Child of app #438 (`d2a41ccab2f4dfa92f3406615c99398d52e622a2`), paired with
native #87 (`3eef28c1e88ca88682acdf2dd5bd856767aef58e`). Not RC12/Maya's
#410/#72 integration. Existing development-only combined-region build options
are unchanged; no new server rule or automatic save migration.

Current native code already supports Kanto Fly destinations/visit flags, heal
locations and trainer/scene banks. This pair corrects mixed-game dispatch in
ordinary buildings rather than inventing another campaign framework:

- Existing 31 FireRed door-animation entries now accompany 55 Emerald entries
  in combined builds. Selection still matches metatile and actual tileset;
  existing native door tasks, warps and collision remain authoritative.
- PC recognition/on/off tiles use the active map's FireRed layout attribute,
  rather than the Emerald executable's compile-time identity. FireRed building
  and player-house PCs use their own native definitions; Hoenn PCs stay intact.
  Existing storage menus and all party/inventory/save transactions are unchanged.
- The field-map title labels the current region correctly. This does not add
  destinations, bypass visited-city checks or grant Fly eligibility.

No new donor assets, maps, story flags or rewards. Pure Emerald/standalone
FireRed dispatch is retained. No held files/actions or live provider sessions.

Verification: 29 focused app tests pass. Two new native component tests compile
six executables across Emerald, FireRed and combined configurations; actual door
table/lookup and PC callbacks run against asset/map boundary fixtures. Four
prior badge-migration component tests also pass locally. There is no full native
link, rendered animation, storage-controller session, region campaign traversal,
save/reload integration or two-client QA. Missing door entries are a source
finding, not a confirmed live softlock; native warp scripts may already finish
without their visual animation. No claim that storage was globally unusable or
that Kanto's campaign is complete. Maya owns integrated gameplay QA.
