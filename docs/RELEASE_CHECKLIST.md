# Linux release candidate checklist

This is a bounded release checklist, not a claim of universal campaign or network fault coverage.

## Required local deliverables

- [ ] Reopening the launcher uses one instance per private worlds root; competing old sessions produce actionable errors rather than stealing locks.
- [ ] Successful shared completion followed by private reward prompts does not falsely demand reset; real interrupted native activity remains explicit.
- [ ] Tag invitation acceptance uses an aligned, human-usable deadline with unchanged consent requirements.
- [ ] Versioned x86-64 Linux archive includes the actual native executable, prebuilt browser launcher, runtime source/data, manifest and checksums; contains no player/account/server private files.
- [ ] Disposable user-local install/update leaves a sentinel save intact, runs prerequisite/version checks and opens the packaged loopback launcher successfully.
- [ ] Native standalone frame/save smoke uses disposable state only.
- [ ] Owner backup, trainer save backup/import and hosted authority restore have recorded disposable rehearsals.
- [ ] Nonsecret service health output and private backup/recovery instructions are available.
- [ ] Source and assets are merged to main; publication points at the verified source commit.

## Human acceptance

- [x] Human plus Hermes joined the same deployed WAN world, saw each other, tagged and completed a shared wild encounter; both returned to the field after normal reward prompts on the pre-release-readiness gameplay build.
- [ ] Normal friend session on the final release candidate. Do not inherit this check from a previous build or from component tests.
- [ ] Windows friend installation and Internet join/play/save/rejoin. External owner by user direction.
- [ ] Representative stock campaign transitions: rival/trainer, gym, healing or blackout, map transition, leave/rejoin. Record individual story-progression limitations.

## Deployment boundary

Do not restart an occupied hosted service or user game to satisfy a checklist. A server deadline change requires a coordinated maintenance activation if current players remain connected. Backups of a live authority require explicit consistency support; an offline-backup tool must refuse rather than create a misleading snapshot. No arbitrary interruption recovery, automatic rollback or full campaign claim follows from a successful normal battle.

## Out of scope

Browser rendering/game capture, new regions/species, AI GM, global story-flag mirroring and high-population throughput are not conditions for this Linux candidate.
