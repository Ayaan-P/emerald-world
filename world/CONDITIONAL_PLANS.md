# Result-conditioned actor plans

An independently authored actor plan can now choose different supported actions from its own actual tool results without requiring another model call between every branch. This is a general execution primitive, not a predefined character arc, autonomous model activation or new permission.

Each step retains `id`, `tool`, `args` and `after`. It may additionally specify `when: {step: "prior", path: "/outcome", equals: "expected"}`. The named prior step must be a declared dependency. JSON pointers can inspect bounded nested fields or array indices in that successful receipt. Equality is literal and type-strict; a missing field does not equal null, and true does not equal 1. No expressions, scripts or access to unrelated receipts/private state are supported.

A matching step invokes its ordinary capability, with all existing preconditions and transactional/staged admission. A nonmatching condition records `skipped` with `executed: false`, without calling the tool. Descendants of skipped steps also skip. Hard blocked results still halt the entire plan and require an explicit new plan; conditions cannot catch a denial and retry it. Pending effects still require their actual completion adapter. There are no implicit loops, unconditional joins of mutually exclusive branches, new model calls or increased six-step/size limits.

## Actual effect and author integration

The component demonstration uses a real generated-world observation and the existing shared native weather capability: differing observed weather selects one of two different admitted changes, and compatible player snapshots contain the resulting weather wire. This proves conditional execution over actual state, not a claim that NPCs control weather as a fictional power. Authors can compose the same primitive with their other available social, environmental or gameplay capabilities; every capability keeps its existing scope.

The existing direct-provider author prompt and runtime discovery describe the syntax. Fake Claude/OpenAI transport tests preserve and validate conditional plans. The fuller worker/staging/replan tests also include a conditional population step, but both provider subtests currently skip because this environment cannot start their required mechanic sandbox; that end-to-end author loop is not verified here. No live provider call is performed. The plan ID and receipts persist through restart, so successful actions and skipped branches do not replay.

## Candidate boundaries

Based on #377 `e751b0fd90f17296acccc100de92370a67511d5d`, with unchanged native #55 `babbe0e3272120523d509cecf22705f158429586`. Not based on released RC12; Maya owns integration/QA/release. All denied uploads and the uncertain outdoor-region publication remain untouched. The inherited spectating mitigation remains in place and live direct-provider sessions remain prohibited pending their separate finite-budget correction.

Validation covers real branch effects, differing initial state, restart, skipped descendants, hard-failure halting, strict comparisons and invalid dependencies. Component and fake-provider verification is not linked rendered gameplay or live model acceptance.
