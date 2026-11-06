# Mainline integration and backlog

This records the reconciliation after [PR #205](https://github.com/Ayaan-P/emerald-world/pull/205), which promoted polished RC6 and its RC5 base to main. It is a historical integration boundary, not a live backlog query or a future release promise.

## Source versus release

- `main` gained the integrated source at merge `49b1d74670c1897b2518e4bd146bb8d4b04e8936`.
- RC5 was published separately as [v0.2.0-rc.5](https://github.com/Ayaan-P/emerald-world/releases/tag/v0.2.0-rc.5). Its release branch/tag preceded the mainline promotion.
- The polished RC6 candidate is source on main. An RC6 asset publication is a separate operation and is not established by PR #205.
- Older RC4 battle-engine experiments remain put aside. Their existence in other branches/worktrees does not put them in RC6.

## Original Dot PRs reconciled

The following original PRs were open after their implementation had already landed. Their current heads were checked before closing, and each closure links PR #205. They are **accepted into the combined codebase**, not rejected features. Their GitHub lifecycle is **closed as already integrated**, not a claim that each original stacked PR received a separate merge commit.

### Exact heads already reachable from main

- #168: shared generated cave authority.
- #171–174: native OAM/tile-bank capacity, matching trainer appearance and smoother presence.
- #175–187: generated cave styles, autotiling, encounter profiles, wildlife, large caves and launcher authoring.
- #188–191: persistence, generated outdoors, sharing and saved-area archive.
- #192–200: guides/casts, interaction graphs and live owner state/rule changes with client outcomes.

These are 31 PRs with exact Git ancestry evidence. Their branches were retained, including branches still used as bases by later work.

### Equivalent or reconciled integration changes

- #159: cancellable solo save import is already present in the current launcher.
- #164–166: owned medicine, reserve medicine and six-Pokémon switching feature-head patches have equivalent cherry-picked changes on main. Their older RC3 branch ancestry was integrated separately.
- #170: presence batching was reconciled into the combined authority. Main retains the exact batching regression fixture and integrated scheduler, rather than the original branch tip.

Those five PRs were closed with the different evidence stated explicitly. This does not certify the deferred whole-candidate six-party/medicine/storage gameplay paths. See [RC5](RELEASE_RC5.md) and [RC6](RELEASE_RC6.md) acceptance limits.

In total, 36 already-integrated PRs were verified closed. No new source changes were introduced by closing them.

## Work deliberately left separate

At reconciliation time these Dot drafts were not included and remain open:

- #156 and #158: Unstuck destination/cooldown foundation and offline action.
- #161–163: optional EXP/TM changes, move split and Mega Evolution work. These are not automatically approved by mainline cleanup or a product-direction goal.
- #201–204: live terrain control, atomic patches, durable shared terrain and observation/client reports. These extend beyond the RC6 integration cutoff.

Other older non-Dot PRs were not bulk-closed. Branch cleanup, issue closure and integrating new functionality are separate decisions.

## Live queries

```sh
git fetch origin main
gh pr list --state open --limit 100
gh run list --branch main --limit 20
gh release list
```

A current head can differ from the head originally reviewed. Exact ancestry can be checked with `git merge-base --is-ancestor <head-sha> origin/main`. Cherry-picked or manually reconciled work requires patch/source review as well. An old green CI result is not current revision acceptance. An integrated feature's original `_DRAFT` document may remain useful even after its PR has closed.
