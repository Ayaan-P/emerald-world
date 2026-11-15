# Combined-region defeat recovery

Child of app #440 (4a998006d8bfc77c417915f4eee59738f3dd7da3), paired with
native #89 (ab27552834bf5aa510ea3abc1ebbb94d9e9e62e3). Independent development
stack, not Maya #410/#72 or RC12. Existing combined-region options apply.

Losing in Kanto now invokes the existing Kanto Elite Four reset instead of
Hoenn's league/Briney script. The source region is read before the recovery
warp. Kanto defeats retain Hoenn's abnormal-weather state, and Kanto Teleport
does not relocate Hoenn's Briney. Hoenn behavior and non-combined defaults
remain unchanged. Actual native healing, money loss, last-heal respawn,
battle/follower resets and personal save formats remain unchanged.

This does not add regional respawn slots: the existing personal last-heal
location may be in the other region. It does not prove all post-warp healer
cutscenes or campaign save behavior correct, or implement a full Kanto run.

Validation: 29 focused app tests and two native component tests pass. The latter
compile actual reset/whiteout/Teleport callbacks in three configurations,
checking script selection, order, weather preservation and repeat dispatch.
Native scripts were inspected, not executed in a script-VM test. Full native
link, controller-driven loss/poison/Teleport, save/restart and two-client QA
remain outstanding. No actual saves, donor imports, held actions or live
providers touched.
