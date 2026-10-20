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

## Branches: GitFlow, no `develop` until the first release

Until **v0.1.0** exists there is only `main`:

```
main ── feature/12-vendorsync-dhcp ──► PR ──► main
     └─ fix/20-lan-lockout ─────────► PR ──► main
```

- `main` is always deployable to a test unit. Tag releases from it.
- Branch names: `feature/<issue>-slug`, `fix/<issue>-slug`, `chore/<issue>-slug`, `docs/<issue>-slug`, `research/<issue>-slug`.
- Branch from `main`, keep branches short-lived, rebase on `main` before opening the PR.
- No direct pushes to `main` after the initial commit; everything goes through a PR.

**At the first release** (v0.1.0): cut `develop` from `main`, then standard GitFlow applies:
`feature/*` branch from and merge into `develop`; `release/x.y.z` from `develop` to `main` (+ tag, merge back);
`hotfix/*` from `main` to `main` and `develop`. Update this file and `CLAUDE.md` in that release PR.

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
