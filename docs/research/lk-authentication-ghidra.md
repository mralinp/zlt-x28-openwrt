# LK authentication paths in Ghidra (#207)

2026-11-01. **Analysis only: no instruction patch, firmware export, flash write, security change or reboot.**
The owner chose to identify both paths before selecting any patch. This report separates rootfs-certificate
verification from boot-image authentication; bypassing one would not establish bypass of the other.

## Input and method

Original `private/recovery/20261020-capture-prepared-20261021/images/mtd25-lk_a.bin`, 2,097,152 bytes,
SHA-256 `0ad94f065ebcfeefd157640d179b1b52779829a85179d07d38dd818b79007156`. The original B copy is identical.
Local Ghidra **12.1.4 PUBLIC**, `ARM:LE:32:v8:default`, BinaryLoader, raw base `0x83fffe00`.
Thus **VA = file offset + 0x83fffe00**, including the 0x200-byte partition header. The ARM stub enters
Thumb at file `0x277a`; the script seeds Thumb context in the first code region, not in the duplicate payload.
All offsets below are original-file offsets unless explicitly labelled VA. Names such as `FUN_840282de`
are Ghidra-generated names, not recovered vendor symbols. Pseudocode is not original C.

The reproduction script validates the original file's size/hash, processor, mapping and complete mapped
bytes before analysis. It creates disassembly/function metadata in a private Ghidra database; it has no
firmware byte-write, export, SSH or flashing operation. Assembly is the control-flow evidence: inferred
parameter lists can omit stack arguments, particularly on calls to the non-returning assertion handler.

## New read-only device observation

On 2026-11-01, key-only SSH with `BatchMode=yes` and `StrictHostKeyChecking=yes` read `/proc/cmdline`,
`/proc/mtd`, `uname -a` and `sha256sum` on the partitions below. Slot A was running (`bootslot=a`,
`ubi.mtd=29`), kernel `4.19.205 #0 SMP Fri Dec 22 12:10:12 UTC 2023`. Every hash matched the original dump:

| Partition(s) | SHA-256 |
|---|---|
| `mtd0` preloader | `0f59889f3a11410fce4cea6fabab22b94a0d113e02c1d6fbbbe7f23c1205d950` |
| `mtd1` preloader backup | `cf1c2226273bd56d6e19c9973ad46a3da70788ed7a65fb9c5d38c16285232eba` |
| `mtd14` seccfg | `c70bcbad6d98b2c08b64c4994de4dd03f11577a1679c7b19d3308533498e6b39` |
| `mtd25`, `mtd38` LK A/B | `0ad94f065ebcfeefd157640d179b1b52779829a85179d07d38dd818b79007156` |
| `mtd27`, `mtd40` boot A/B | `c8cc8244078cb6539c72842540250bc7ca40b8fb9b66123a6bd85a529e47b120` |
| `mtd28`, `mtd41` rootfs signatures A/B | `1ebb121adfbac5603dca0e65c3b276a315fda1450bdbd573f3c600b5f399d4b6` |

A separate read of LK-A `[0x2490c,0x24954)` matched the original bytes. `[0x8c7c,0x8c80)` was
`72 b6 fe e7`, the original interrupt-disable/spin sequence. **CONFIRMED:** no retained byte patch in these
partitions relative to our capture. This cannot rule out an earlier patch that was restored, a RAM-only
patch, or a modification predating the capture. These are new observations, not claims about historical receipts.

## 1. Rootfs-certificate path

Ghidra corroborates the [previous failure-path analysis](../BOOT-FLOW.md#lk-failure-path-offline-analysis-2026-10-28-40):

| File offset (VA) | Observed behavior |
|---|---|
| `0x248c2` (`0x840246c2`) | Constructs `rootfs_sig` plus selected suffix; calls verifier at `0x24908`. |
| `0x2856a` (`0x8402836a`) | Reads and verifies the certificate chain; publishes output buffer/length on success. |
| `0x2490c` | Compares return value with zero; equality takes the normal return/output path. |
| `0x24932–0x24950` | Nonzero result invokes assertion handler `0x18b98`, expression `err == 0`. |
| `0x18b98`, `0x8c5a` | Panic printing and halt path; `cpsid i` at `0x8c7c`, self-branch at `0x8c7e`. |

**INFERRED from control flow:** a returned certificate-verification error is fatal here; it is neither
log-only nor an immediate A/B fallback. No deliberately invalid certificate was booted. Replacing a panic
call with NOPs alone is not a reviewed bypass: failure clears outputs, and downstream metadata consumers
would still need analysis. No such patch was made.

The signed message/digest ranges and independent RSA-PSS checks remain in
[rootfs-signed-content.md](rootfs-signed-content.md). Booting changed SquashFS under original certificates
demonstrates that particular content combination works; it does not demonstrate acceptance of an unsigned kernel.

## 2. Boot-image path

**CONFIRMED static path:** function `0xee12` (VA `0x8400ec12`) selects the string `boot` or `recovery`,
appends the selected suffix and reads an Android-style boot image. It reads page size from header offset
`0x24`, computes the page-rounded component span and performs the following checks when its policy result is nonzero:

| Call site | Callee file offset (VA) | Observed work / error propagation |
|---|---|---|
| `0xee58` | `0x24ace` (`0x840248ce`) | Obtains the partition authentication policy; result saved in `r9`. |
| `0xeef0` | `0x280c2` (`0x84027ec2`) | Parses image/certificate headers, verifies certificate chain; nonzero at `0xeef4–0xeef6` branches to assertion sequence ending at `0xf004`. |
| `0xeefc` | `0x2843a` (`0x8402823a`) | Header authentication; nonzero tested at `0xef08–0xef0a`, assertion call at `0xf026`. |
| `0xef7c` | `0x284de` (`0x840282de`) | Payload authentication; nonzero at `0xef80–0xef82` branches to assertion ending at `0xf048`. |

The guard before the certificate/header calls is at `0xeed8–0xeedc`; the payload guard is at
`0xef6e–0xef72`. The assertions call the same panic handler as the rootfs wrapper. This establishes an
error-to-panic route **when the policy enables these checks**, not a hardware failure experiment.

The three callees are shared: cross-references also lead to `0x8a28` (reads `boot_para`) and `0x1e508`
(generic image loader). They must not be treated as boot-only patch points.

### What the three checks do

- **Certificate chain, `0x280c2`:** initializes shared authentication state, parses image metadata,
  reads certificate headers/payloads via a partition-reader callback and calls certificate helpers at
  `0x2685e` and `0x26f0e`. Success prints the format at `0x398ee`; failure prints `0x3990b` and returns
  the error. The call at `0x28422` clears a separate state area through `0x25e34`; it is not itself the
  caller's panic. Deeper crypto/trust-anchor validation is not closed by this pass.
- **Header, `0x2843a`:** checks the supplied length against saved header length, computes SHA-256
  through `0x25a2e`, then compares 32 bytes with saved certificate-derived state at VA `0x8405e534`
  using `0x27ba8`. Mismatch returns `0x101010`; length mismatch returns `0x101012`. Success/failure
  formats are at `0x3992f`/`0x3994f`. SHA-256 identification is supported by the standard initial-state
  constants in `0x25a2e`, in addition to the 32-byte comparison.
- **Payload, `0x284de`:** calls `0x24764` at `0x28508` for a 32-byte result, then compares it with
  saved state at VA `0x8405e510` at `0x2851c`. Mismatch sets `0x101010` at `0x28522–0x28526` and
  returns failure after printing `0x39990`; success at `0x2854e` prints `0x39977` and returns zero.
  `0x24764` passes SMC service `0x8200010e` to the monitor-call wrapper at `0x2484e`. Secure-monitor implementation and the full
  transformed-data semantics are not established here; do not describe this as a fully audited plain
  SHA-256-over-kernel operation.

### The policy gate is separate from the printed SBC value

`0x24ace` matches up to four partition-name strings per 32-byte row, defaulting to row zero if none
matches. Its table starts at file `0x3e09c` (VA `0x8403de9c`); the `boot` row is `0x3e13c`.
The default and boot rows both have four policy words **`0, 2, 1, 2`**, whose low bit is returned.
Thus a suffixed name falling back to the default has the same values in this dump.

Let `S` be the value written by `0x28028`, and `L` the value written by `0x2488e`:

| S | L | Row-relative field selected | Returned bit for default/boot |
|---|---|---|---|
| 0 | 0 | `+0x14` | 0 |
| 0 | nonzero | `+0x10` | 0 |
| 1 | 0 | `+0x1c` | 0 |
| 1 | nonzero | `+0x18` | 1 |

Other S values return zero in the inspected dispatch. A null partition-name argument returns one.
`0x2488e` calls `0x28eb8`: state 3 maps to L=0; other returned states or an error map to L=1.
The upstream state source is not fully audited, so L is deliberately not labelled a proven hardware lock bit.

`0x28028` calls `0x27f84(1)`. That helper reads the configuration word at file `0x3e380`
(VA `0x8403e180`): **the original file contains `0x11`**, which returns S=1. Configuration 0 returns
S=0; configuration `0x22` consults `0x25c48`; invalid values invoke an assertion.
`0x25c48`, also used by the `sbc_en` printer in `0x266ac`, reads `(*(u32 *)0x51ec0060 & 3) >> 1`.

**INFERRED:** the original `0x11` configuration can enable this software policy independently of a
printed `sbc_en = 0`, depending on L. Runtime writers of the configuration/state and the hardware register's
authoritative semantics remain unexamined. This is not a fuse-state determination or proof of unsigned-image acceptance.

## Patch decision and remaining boundaries

**No patch selected, implemented, exported, flashed or hardware-tested in #207.** There are no modified
instruction offsets to report. Rootfs-certificate failure handling and boot certificate/header/payload
authentication have different callers, outputs and state. The policy function also serves other loaders.

Before proposing any patch: settle the active first/duplicate LK payload, trace runtime policy/configuration
writers and secure-monitor services, bind the exact boot container/certificate coverage and inspect callers'
required output state. Preloader authentication of a modified LK remains a separate constraint. Retain the
original kernel until a separately reviewed artifact, restoration plan and exact device approval exist.

Ghidra's unused packaged-type/cache maintenance attempted writes under `/var/tmp/ali-ghidra` and was denied
by the sandbox. The script still reached its explicit completion marker and saved the analysis database.
This limitation and decompiler signature warnings are not evidence of a firmware write or authentication bypass.

## Validation performed

The checked-in script ran locally against the original input: `INPUT VERIFIED`, all 17 function reports,
one `ANALYSIS COMPLETE`, and no `REPORT SCRIPT ERROR`. A separate import of a 12-byte synthetic non-firmware
file was refused as unknown input before analysis. Importing the original bytes at the wrong raw base
`0x84000000` was also refused before analysis. Logs were checked for the intended refusal and absence of
the success markers, rather than relying on Ghidra's process exit status. The original input's SHA-256
remained unchanged. The script was safety-reviewed for absence of firmware-write/export/device operations.
This is static analysis, not execution of LK or a modified boot image.

## Reproduce locally

Requires an existing Ghidra installation and supported JDK. Choose a **new private project directory**;
the command creates analysis files, never modifies the input dump. Keep the project/log outside Git.
For example, with `GHIDRA` and `JAVA_HOME` set to their installed paths:

```sh
mkdir -p private/research/207-lk-ghidra/project private/research/207-lk-ghidra/home
JAVA_TOOL_OPTIONS="-Duser.home=$PWD/private/research/207-lk-ghidra/home" \
  "$GHIDRA/support/analyzeHeadless" "$PWD/private/research/207-lk-ghidra/project" lk \
  -import "$PWD/private/recovery/20261020-capture-prepared-20261021/images/mtd25-lk_a.bin" \
  -loader BinaryLoader -loader-baseAddr 0x83fffe00 -processor ARM:LE:32:v8 -cspec default \
  -noanalysis -scriptPath "$PWD/tools/firmware" -postScript LkAuthentication.java \
  > private/research/207-lk-ghidra/analysis.log 2>&1
```

Check for `INPUT VERIFIED`, the 17 `FUNCTION file=` entries and `ANALYSIS COMPLETE`, and inspect any
`REPORT SCRIPT ERROR`: the headless process exit status alone is not sufficient to prove script success.
The script refuses unknown input hashes, a wrong mapping/language or changed analysis-memory bytes.
To inspect graphically, open the resulting `.gpr`, double-click the imported program, then press G and
enter a VA from the tables above. Do not export a patched binary as part of this reproduction.
