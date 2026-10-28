# Does anything check rootfs content against the signed digest? (#91)

Offline only, 2026-10-29. Inputs: the LK image `mtd38-lk_b.bin` (SHA-256 `0ad94f06...`), the decompressed
kernel `kernel.decompressed` (`e1e2624d...`), the stock config and the stock archive. Continues
[#40](rootfs-signed-content.md). Nothing was run on the router.

## What the signature covers

`rootfs_sig` holds two RSA-PSS certificates; cert2 embeds the SHA-256 and size of the **stock SquashFS**
(`00216f21...`, 31,274,410 bytes). LK verifies the certificates only and hands the pieces to the kernel in
the device tree (`rootfs,pubk/predata/hashvallist/postdata/sigval`). Our SquashFS has a different digest
and size, so it cannot match; the question is whether anything compares.

## Evidence, by stage

| Stage | Finding | Strength |
|---|---|---|
| LK | Strings show one verifier, `rootfs_sig_vfy.c`, with `cert1 verify failed`, `ROOTFS_SIG_VFY Success/Fail`, `rootfs dts write failed`. No message about hashing or comparing a rootfs. | Observed |
| LK | `ubi` appears only in the `ubi.mtd=28/29/42` command-line strings. No byte sequence `UBI#`, `UBI!` or `hsqs`, and no Thumb-2 `movw/movt` pair (3,491 / 237 decoded) builds those constants. LK has no code to parse a UBI volume or SquashFS, so it cannot read or hash the rootfs. | Observed absence; a pointer-built constant would be missed |
| Kernel | 31.1 MB `Image` contains none of `rootfs,hashvallist/pubk/sigval/predata/postdata` or `rootfs_sig`. Config: `CONFIG_MD` off (so no dm-verity), `INTEGRITY_SIGNATURE`, `IMA`, `ASYMMETRIC_KEY_TYPE` all off; `fs-verity`/`dm-verity` strings are generic library text. | Observed |
| Userspace | No stock file reads the handoff properties; `rootfs_sig` appears only as partition names in upgrade scripts (#40). | Observed |
| Secure world | Not inspected; LK's `SECLIB_IMG_VERIFY` is the only visible interface and takes the cert chain. | Unknown |

## Verdict

No component in the normal boot chain that we can see compares the rootfs with the signed digest. Boot
acceptance of a different SquashFS under a **valid** stock `rootfs_sig` is therefore expected but **not
proven**: the secure world and any LK path that builds UBI/SquashFS constants indirectly are unexamined.

## Consequence for the first custom boot

`rootfs_sig_a` already holds the same valid stock certificates as slot B (the A/B signature copies are
identical in the verified backup). A first image that rewrites only `rootfs_a` is exactly the
"valid certificate + different content" experiment. The separate **bad-certificate** experiment (known to
panic and halt LK) answers nothing the first boot needs and should not be run. Leave `rootfs_sig_a`
untouched, so the one remaining unknown is tested with a signature LK accepts.

Expected UART outcomes: `ROOTFS_SIG_VFY Success` followed by the kernel mounting `ubiblock0_0` (accepted), or
a hang/reset before `Starting kernel` with `ROOTFS_SIG_VFY Fail` (a consumer exists; restore via #90). A
kernel panic on mount points at the image, not the signature.

## Not resolved

Secure-world behavior; whether LK reads the rootfs by a route not visible as UBI code; the GPL source
request ([#18](https://github.com/mralinp/zlt-x28-openwrt/issues/18)) would settle both.
