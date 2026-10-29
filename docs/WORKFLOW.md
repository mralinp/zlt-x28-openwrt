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

## Branches: trunk-based, every merge to `main` is a release

There is only `main` (no `develop`, no `release/*` branches):

```
main ── feature/12-vendorsync-dhcp ──► PR ──► main ──► tag vX.Y.Z + GitHub release
     └─ fix/20-lan-lockout ─────────► PR ──► main ──► tag vX.Y.Z + GitHub release
```

- `main` is always deployable to a test unit.
- Branch names: `feature/<issue>-slug`, `fix/<issue>-slug`, `chore/<issue>-slug`, `docs/<issue>-slug`, `research/<issue>-slug`.
- Branch from `main`, keep branches short-lived, rebase on `main` before opening the PR.
- No direct pushes to `main` after the initial commit; everything goes through a PR.

## Releases: automatic, from the PR title

`.github/workflows/release.yml` runs on every push to `main` (the same flow as the maintainer's other projects):

1. CI (`ci.yml`) and the userspace build (`userspace.yml`) run.
2. `scripts/release.py next-version` derives the next SemVer from the Conventional Commits since the last
   `vX.Y.Z` tag: `type!:` or a `BREAKING CHANGE:` footer → major (minor while on 0.x), `feat` → minor,
   anything else → patch. The first release is **v0.1.0**.
3. The tag and a GitHub release are created, with generated notes. **Every 0.x release is a pre-release**
   (beta). Assets are the open userspace rootfs, its manifest and `SHA256SUMS`, never vendor files.

Because PRs are squash-merged, the **PR title becomes the commit and decides the version bump**. CI rejects
PR titles that are not Conventional Commits (`scripts/release.py check-title`).

## Commits
Conventional Commits: `type(scope): summary`, e.g. `feat(adapter): sync dhcp range from vendor`. Reference the issue in the body (`Refs #12`).

## Pull requests
Use the PR template. Required: what and why, linked issue (`Closes #12`), how it was tested (device, commands, output),
safety note if the label is `risk/*` (rollback path), and what is NOT verified. One concern per PR. Squash-merge into `main`.

## Definition of done
- Acceptance criteria met and checked on a real unit (or stated as unverified).
- Deploy tested with the documented command; reboot-persistence checked when relevant.
- Rollback documented for risky changes; no secrets, vendor blobs, or dumps committed.
- Docs updated (README status table, plan, or notes).

## Changelog

`CHANGELOG.md` has hand-written milestones at the top and the full per-release list at the bottom. After releases land, run
`python3 scripts/changelog.py` (needs `gh`) to refresh the list, add a milestone entry by hand when a stretch of work
completes, and include the file in the next docs PR. `python3 scripts/changelog.py --check` fails if the list is stale.
