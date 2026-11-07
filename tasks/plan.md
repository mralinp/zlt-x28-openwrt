# X28 unattended test bench and modern-kernel bring-up

Planning draft, 2026-11-01. No hardware operations authorized by this document.

## Objective and first deliverable

Let an agent build an artifact, perform one bounded hardware experiment, capture
UART/USB evidence, and return the X28 to its known-good state. Prove the bench
before attempting a modern kernel. Initial kernel success is a UART initramfs
shell, not working storage, networking or 5G.

Extends [the existing kernel roadmap](../docs/research/x28-mainline-roadmap.md).
Use [current status](../docs/STATUS.md), [recovery evidence](../docs/RECOVERY.md)
and [CLAUDE.md](../CLAUDE.md) for current hardware and workflow constraints.
Implementation tasks belong in GitHub Issues, with the required project labels
and milestone, before implementation branches. The ordered work below is a
planning draft; no issues, branches or PRs have been created for it yet.

## Bench design

The controlling computer has independent internet, stays powered, and controls
only the router's DC supply through a relay rated for its measured supply and
load. Prefer low-voltage DC switching; user installs and verifies the wiring.
Do not select or buy relay hardware until its interface, ratings, default state
and behavior after controller failure are known.

UART and USB remain connected. Verify UART voltage before enabling adapter TX;
existing notes flag possible 1.8 V logic and 921600 8N1. Confirm that attached USB
or UART does not back-power the router when the relay is off. If USB keeps it
powered, a DC relay alone is insufficient; establish controlled USB power or
isolation without losing recovery data access.

Identify adapters by stable device identity, not an assumed tty number. Preserve
timestamped raw UART logs across USB disconnects and reconnections. Capture the
whole power-on sequence, not just the Linux console.

Reuse tools/recovery guarded sessions and receipts; add only the missing relay
control and orchestration. One process owns device access; a second agent may
analyze logs or build offline but cannot concurrently control UART/USB/power.

## Ordered tasks and acceptance evidence

| Task | Deliverable and acceptance | Verification | Depends on |
|---|---|---|---|
| 1. Bench inventory | Relay/controller interface, UART adapter/voltage, USB path, host uptime/sleep policy and independent internet documented; back-power behavior measured | Owner wiring check and passive host inventory; no router power change | None |
| 2. Continuous capture | One timestamped UART capture survives reconnects; USB attach events and device identities recorded; disk/log retention bounded | Capture existing output, simulate host-side capture interruption without rebooting router, confirm restart and exclusive access | 1 |
| 3. Power control | Explicit on/off/state operations, confirmed physical state, defined off interval, no endless toggle command; controller failure behavior recorded | Test relay against a dummy load first, including interrupted command and controller restart; then one owner-authorized router cycle with UART capture | 1, 2 |
| 4. Recovery rehearsal | Verify backup and known-good artifact hashes; demonstrate unattended USB recovery entry and return to current installation, using existing read-only USB probes first | Owner-authorized normal boot -> capture/recovery entry -> USB read/hash -> normal boot, repeated three times; recovery restoration procedure and limits recorded separately | 2, 3 |
| 5. Bounded experiment runner | Persist state and artifact hashes before any power/USB action; one experiment then return; enforce approved action/partition scope, UART timeout, thermal/time budget, exclusive lock and retry ceiling | Simulated boot timeout, lost UART, USB disappearance, process crash and stale receipt all stop safely without unplanned flash or endless power cycles | 4 |
| 6. Offline modern-kernel artifact | Pin an OpenWrt-aligned supported kernel and toolchain after checking current target support; reconcile RAM reservations/boot handoff; build minimal serial initramfs and manifest | Repeat build/hash checks, inspect Image/DTB/initramfs and memory ledger; generic QEMU smoke test only where applicable | Existing roadmap milestones 0–1; independent of 2–5 |
| 7. Boot mechanism proof | Establish how a custom Image/DTB/initramfs can be accepted and how to return; do not assume RAM boot or a bootloader prompt exists | Offline LK/preloader/container/authentication evidence and concrete reviewed load-and-return procedure; stop if mechanism remains unknown | 4, 6 |
| 8. First real kernel boot | One approved attempt reaches UART shell with coherent RAM/timer/interrupt evidence, or yields a reproducible failure log, then returns to known-good installation | Capture complete UART, boot state and return verification; no automatic modem startup or NAND mounts | 5, 7 |

Each task is an issue-sized outcome; split implementation further if necessary.
Likely implementation scope: existing tools/recovery entry points and focused
new relay/capture helpers, plus their failure-path checks. Do not change guarded
recovery tools during a live receipt-bound session.

## Recovery gates and authorization

Current installation is OpenWrt on A, stock B preserved. Verify fresh state
before any experiment; historical reports disagree because the active slot
changed over time. The known recovery tests establish bounded capabilities,
not universal recovery of an arbitrary new kernel or bootloader failure.

Preloader increments A's boot tries. Stock B can repair/erase A when A's tries
exceed 3. Do not deliberately accumulate retries or rely on automatic fallback.
Before allowing cycles, establish authoritative retry reads, a proven allowed
reset route and a return policy that respects this behavior. Unreadable or
unexpected retry/slot state stops the run; it never triggers a guessed write.

Default is offline/read-only. Relay cycles, recovery-entry actions and boots
need the owner's approved bounded procedure under CLAUDE.md. Existing flash
sessions retain their owner-typed per-step approvals and safety review. Planning
a relay does not waive those requirements. A future unattended procedure must
explicitly define its allowed actions; otherwise the runner prepares evidence
and pauses before the action. No preloader/LK/seccfg/misc/calibration changes,
slot conversion, or alteration of stock B is included in this bench plan.

Initial retry policy: zero automatic experimental reboots. After one failed
attempt, follow only the separately proved return procedure; if it fails,
stop and request physical intervention. Host restart resumes from recorded
state and inspection, never by blindly replaying the last write or power action.

## Checkpoints

1. Bench ready: tasks 1–3 verified, including back-power and capture reliability.
2. Recovery ready: task 4 evidence reviewed; explicitly list remaining manual
   recovery actions. If buttons/test points are needed, automate them only as
   a separate electrical/mechanical task or keep a human present.
3. Experiment ready: task 5 failure tests and task 7 boot mechanism pass; owner
   reviews the exact artifact, actions and return path before task 8.
4. Feasibility result: UART shell plus successful return, or a bounded documented
   blocker. Re-estimate further work from this evidence.

## Later kernel milestones

After UART shell and recovery are proven: MT6890 clocks/power/reset and thermal
control -> Ethernet -> PCIe/MT7915 with calibration preserved -> read-only NAND
compatibility -> internal modem lifecycle/CCCI -> DPMAIF data -> stability and
persistent upgrades. Follow the existing roadmap; do not fold all of these into
one bring-up issue. 5G is a separate major milestone, not a UART-boot criterion.

## Estimates and open inputs

Allow roughly 2–5 focused engineering days for bench tooling after hardware is
installed and interfaces are known. A manual recovery-entry requirement or
back-power issue may extend this. Treat the first week of kernel work as a
feasibility timebox, not a promise of a UART shell. Earlier whole-port month
estimates are provisional; there is no measured agent-assisted completion rate.

Need owner input: relay/controller model or preferred interface; UART adapter
and verified voltage; independent internet for the host; whether recovery entry
requires a button or test point; acceptable downtime and whether a second board
is available. These do not block offline artifact preparation.

No relay was operated, device rebooted, partition written, or bootloader changed
while drafting this plan.
