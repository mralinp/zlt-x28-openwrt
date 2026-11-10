# Workflow

## Tasks are issues
Every piece of work starts as a GitHub issue (use the Task template). No issue, no branch.

**Labels** (kept in `.github/labels.yml`, applied by `scripts/sync-labels.sh`):

| Group | Labels |
|---|---|
| Priority (exactly one) | `P0-critical` (device bricked/locked out, data loss), `P1-high` (blocks a phase), `P2-medium`, `P3-low` |
| Type (exactly one) | `type/feature`, `type/bug`, `type/task`, `type/research`, `type/docs` |
| Area (one or more) | `area/luci`, `area/adapter`, `area/sms-voice`, `area/thermal`, `area/firmware-build`, `area/safety`, `area/tooling` |
| Risk | `risk/brick` (flash, bootloader, partitions), `risk/lockout` (network, SSH, auth), `risk/reboot` |
| State | `blocked`, `needs-info`, `good-first-task` |

**Milestones** map to the plan phases: `Phase 0 safety` ... `Phase 6 release`.

An issue is ready when it has: a goal, acceptance criteria (checkboxes), priority, type, area, milestone.

## Branches: `develop` for work, `main` for releases (since 2026-11-10)

```
develop ── feature/12-vendorsync-dhcp ──► PR ──► develop ──► tag vX.Y.Z-rc.N (pre-release)
        └─ fix/20-lan-lockout ─────────► PR ──► develop ──► tag vX.Y.Z-rc.N (pre-release)
develop ──────────────── PR (merge commit) ──► main ──► tag vX.Y.Z (stable from 1.0.0)
```

- All work branches from `develop` and goes back into it by PR (squash-merge). Releases of `develop` are pre-releases for test units.
- `main` only takes `develop`, by a PR merged with a **merge commit**, not a squash: the release tag on `main` must lead
  back into `develop`'s history, or the next version on `develop` is computed from the wrong base.
- Branch names: `feature/<issue>-slug`, `fix/<issue>-slug`, `chore/<issue>-slug`, `docs/<issue>-slug`, `research/<issue>-slug`.
- Keep branches short-lived, rebase on `develop` before opening the PR. No direct pushes to `develop` or `main`.

## Releases: automatic, from the PR title

`.github/workflows/release.yml` runs on pushes to `develop` and `main` that touch the release inputs (userspace build files, the x28-flasher and the tools it bundles, and their workflows; see its `paths`) and on manual dispatch. Docs-only and CI-only merges build and tag nothing:

1. CI (`ci.yml`), the userspace build (`userspace.yml`) and the x28-flasher builds (`x28-flasher.yml`) run.
2. `scripts/release.py next-version` derives the next SemVer from the Conventional Commits since the newest
   `vX.Y.Z` tag: `type!:` or a `BREAKING CHANGE:` footer → major (minor while on 0.x), `feat` → minor,
   anything else → patch. A `Release-As: X.Y.Z` footer sets the version (how 1.0.0 is cut). On `develop` the
   version gets `-rc.N` (`next-version --pre`): the candidates for the version `main` will release.
3. The tag and a GitHub release are created, with generated notes. `-rc` and 0.x releases are **pre-releases**;
   `main`'s releases from 1.0.0 on are **stable** and marked latest. Routers only offer stable-form `vX.Y.Z`
   images (`x28-update-check`); an `-rc` unit is offered the release of its own version once it is out.

Because PRs are squash-merged, the **PR title becomes the commit and decides the version bump**. CI rejects
PR titles that are not Conventional Commits (`scripts/release.py check-title`).

## Commits
Conventional Commits: `type(scope): summary`, e.g. `feat(adapter): sync dhcp range from vendor`. Reference the issue in the body (`Refs #12`).

## Pull requests
Use the PR template. Required: what and why, linked issue (`Closes #12`), how it was tested (device, commands, output),
safety note if the label is `risk/*` (rollback path), and what is NOT verified. One concern per PR. Squash-merge into `develop`.

## Definition of done
- Acceptance criteria met and checked on a real unit (or stated as unverified).
- Deploy tested with the documented command; reboot-persistence checked when relevant.
- Rollback documented for risky changes; no secrets, vendor blobs, or dumps committed.
- Docs updated (README status table, plan, or notes).

## Changelog

`CHANGELOG.md` has hand-written milestones at the top and the full per-release list at the bottom. After releases land, run
`python3 scripts/changelog.py` (needs `gh`) to refresh the list, add a milestone entry by hand when a stretch of work
completes, and include the file in the next docs PR. `python3 scripts/changelog.py --check` fails if the list is stale.
