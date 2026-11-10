# Independent co-op campaign roles

This app-only draft follows #387 at 0ebb52c590761b30c50838444c90fb901ee75406. It is on the divergent feature stack, not released RC12. Native remains #56 at 739be20ecf1101f84cc2fb272587978350955b6d. Frozen #384/#56, Maya's integration, and pending denied uploads are untouched.

## Play together without repeating every task

A configured author can publish a campaign with a split stage using the existing world.publish_battle_campaign capability. The existing in-game campaign board offers Host shared; other players join its code through the current shared-run command. Once the party has the required size, the speaker begins and every player chooses their own unclaimed role on the native board. No host assigns another player's task. Choices are fixed for this stage; anyone may cancel the whole run.

After everyone chooses, each player independently explores or battles normally. A role is either an existing world trainer battle, optionally with existing shop/tutor preparation, or a voluntary check-in at an ordinary-map destination. The board displays the player's own task and opponent location. Battles still use the existing native challenge/result protocol; visits require fresh ready presence at the exact point. A player cannot credit a different role's task. Completed players can continue normal play while others finish.

Only after all tasks report does the party regroup into its shared route choice. Any reported loss selects the authored loss routes; otherwise win routes apply. Players advise and the speaker chooses, as before. A later split stage opens fresh role selection. Ordinary campaign stages remain unchanged and require each member to perform that ordinary stage.

## Authoring

A split node has exactly `roles`, `win` and `loss`. Roles is a dictionary of 2–4 unique lowercase IDs. Each role is either `{opponent: EXISTING_TRAINER, preparation?: EXISTING_OPTIONS}` or `{visit: {label: TEXT, point: [group,num,x,y]}}`. Win/loss are ordinary outgoing node ID lists. No nested split stages. Existing immutable IDs, acyclic/reachable graph, native map bounds and real trainer/preparation validators apply. Split stages in one campaign must all match the actual party size when beginning. Such campaigns cannot start solo.

No fixed story or example content is automatically installed. The public campaign document describes optional content, not outcomes. Player role assignments, participation and results remain in the existing private shared-run/save-lineage records; they are not automatically public history or model-author context.

## Truth, persistence and limits

Each member retains a separate save binding and history, including the role actually completed. Role claims and readiness transition commit atomically. Existing native board tokens bind to the entire group state, so an option shown before someone else claims a role expires. Deployment, unfinished tasks and completed waiting members survive authority database restart. Other saves cannot advance those records. Leaving cancels for all; no forced reassignment, timeouts or fabricated offline completion.

Results are client attestations, not server-verified victories. Check-ins establish reported fresh presence, not verified travel or learned lore. Shared progress grants no rewards and edits no original Pokémon, bag, story flags or parties. Battle losses and preparation retain stock native mechanics. A role destination is bounds-checked, not automatically proven reachable; authors and final QA must choose playable points. No synchronized multi-player battle or native rendered playtest is claimed.

Tests exercise the actual existing challenge/result and CORE CAMP board transport, role selection conflicts, mixed tasks, two locations, four members, repeated deployment, preparation, cancellation, loss/abort/replay, save isolation, database restart, and real author runtime publication with scripted test inputs. No live provider calls. Maya owns integration and linked/native playtesting.
