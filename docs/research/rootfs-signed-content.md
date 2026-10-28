# What LK authenticates, and the device-test gate (#40)

Read-only analysis, 2026-10-28, this X28's OEM 1.5.13 backup and running slot B.
The [failure-path analysis](../BOOT-FLOW.md#lk-failure-path-offline-analysis-2026-10-28-40)
remains valid: a returned verification error reaches panic/halt. This report identifies the signed
content; it does **not** establish enforcement when actual rootfs bytes differ.

## Evidence identity

Inputs are under `private/recovery/20261020-capture-prepared-20261021/images/`:

| File | SHA-256 |
|---|---|
| `mtd38-lk_b.bin` | `0ad94f065ebcfeefd157640d179b1b52779829a85179d07d38dd818b79007156` |
| `mtd41-rootfs_sig_b.bin` | `1ebb121adfbac5603dca0e65c3b276a315fda1450bdbd573f3c600b5f399d4b6` |
| `mtd42-rootfs_b.bin` | `c4e3f3d25b3aefca70995c070faa177931a61738b4997acd52a6446daee4cf01` |

The signature partition's A/B copies are identical. All ranges are end exclusive.
LK offsets below use `VA = 0x84000000 + file offset - 0x200`; other offsets name their own input.

## Observed: the verifier reads the signature partition

The wrapper at LK `0x248c2` constructs the `rootfs_sig` name (string `0x38f5e`) with the slot suffix
helper at `0x84cc`, passes zero initial offset at `0x248fe–0x24900`, and calls `0x2856a` at `0x24908`.
The four calls to reader `0x28a1a` use that same name:

| LK call site | Signature-partition offset | Length | Content in this dump |
|---|---|---|---|
| `0x28642` | `0` | `0x200` | cert1 MTK header |
| `0x286ba` | `0` | `0x8b0` | cert1 header + aligned DER payload |
| `0x2879e` | `0x8b0` | `0x200` | cert2 MTK header |
| `0x2880e` | `0x8b0` | `0x5b0` | cert2 header + aligned DER payload |

`0x28a2c` resolves the name through `0x16868`; `0x28a40` calls the bounded partition reader
`0x168fc`. That reader compares the requested span against object size at `0x1691e–0x16940`,
then dispatches through its read callback at `0x16948`. The header parser at `0x27cca` extracts
header size and rounds payload size to the alignment (`0x27d16–0x27d2c`). In the original bytes:
cert1 header `[0,0x200)`, DER `[0x200,0x8ad)`, next header `0x8b0`;
cert2 header `[0x8b0,0xab0)`, DER `[0xab0,0xe5d)`, aligned end `0xe60`.
The remaining signature-partition bytes are `0xff`.

## Observed: signatures authenticate certificate messages

Cert1 processing calls shared helper `0x26df2` at `0x26c8a`; cert2 processing calls it at `0x2707e`.
`0x26e1a` calls `0x27400` to obtain the first nested DER SEQUENCE and its full encoded length
(pointer/length stores at `0x275de` and `0x275ec`). SHA-256 at `0x26e68–0x26e72` hashes this span.
`0x26e28` obtains the signature BIT STRING through `0x26004`, and `0x26e84` requires 256 bytes.
RSA processing at `0x26eb6` is followed by PSS verification at `0x26ee8` (callee `0x25306`);
its trailer check and final digest comparison are at `0x253d8` and `0x25538`.

The parameters are RSA-2048, SHA-256, MGF1-SHA256, salt length 32. Independent host checks
using both Python integer arithmetic and the `openssl` CLI (LibreSSL 3.3.6) verified these original-byte ranges:

| Object in `mtd41-rootfs_sig_b.bin` | Signed TBS message | Signature |
|---|---|---|
| cert1 | `[0x204,0x760)` (1372 bytes) | `[0x7ad,0x8ad)` (256 bytes) |
| cert2 | `[0xab4,0xd10)` (604 bytes) | `[0xd5d,0xe5d)` (256 bytes) |

TBS SHA-256: cert1 `0613ffd6cabeee51a20184d67baa3079917104165261af7d8ef17f1bfc2ae1c6`;
cert2 `5a0bec8488b1978acffbab52f9e175a013793f440ce0b6055f42549a79039988`.
Cert1's custom extension SPKI `[0x3f0,0x516)` exactly equals cert2's SPKI `[0xb65,0xc8b)`.
These signature checks corroborate the encoded key binding; they are not an independent audit of
LK's hardware trust anchor. Internally, cert1 key comparison at `0x266ac` depends on SBC state
(branch at `0x266cc`): hashed-key comparison for nonzero, raw-key comparison for zero. Certificate
signature verification subsequently remains unconditional. The wrapper's fatal returned-error path
has no SBC gate; that does not mean all internal key policy is SBC-independent.

## Observed: the authenticated digest describes the stock SquashFS

Cert2's OID `2.16.886.2454.2.6` precedes a BIT STRING whose 32 digest bytes occupy signature-partition
`[0xcc9,0xce9)`. OID `2.16.886.2454.2.8` precedes the INTEGER at `[0xd0c,0xd10)`, value
`0x1dd35aa` = **31,274,410**. These fields are inside the signed cert2 TBS.
The OIDs' official vendor semantic names have not been recovered.

Reconstructing UBI volume 0 from `mtd42-rootfs_b.bin` gives 124 consecutive LEBs (PEB `0x40000`,
data offset `0x2000`, LEB `0x3e000`). Every selected EC/VID header CRC passes, with no duplicate
logical block number. The reconstructed volume starts with SquashFS magic `hsqs`; its little-endian
`bytes_used` at superblock offset 40 equals **31,274,410**. SHA-256 of exactly that prefix is:

```text
00216f21e84f908f5f862de55af51375fdf032dbf413e98b160d9ab2d65a9c44
```

This exactly equals the certificate digest. Hashing the 4096-byte-rounded length or all 124 LEBs
gives different results. This is a match to logical SquashFS content, not the whole UBI partition
or the writable overlay. No original dump was modified.

## Observed: live handoff and active rootfs match

Key-only, read-only SSH reads of `/proc/device-tree/chosen/rootfs,*` gave:

| Property | Length | Exact source in signature partition |
|---|---:|---|
| `predata` | 533 | `[0xab4,0xcc9)` |
| `hashvallist` | 32 | `[0xcc9,0xce9)` |
| `postdata` | 39 | `[0xce9,0xd10)` |
| `sigval` | 256 | `[0xd5d,0xe5d)` |
| `pubk` | 520 | Decoded RSA modulus/exponent matching cert2 SPKI |

`predata + hashvallist + postdata` equals the exact 604-byte signed cert2 TBS. The public-key
structure holds a 256-byte big-endian modulus, LE length 256 at `0x100`, exponent `01 00 01`
at `0x104`, zero padding `[0x107,0x204)`, and LE exponent length 3 at `0x204`.
The active read-only rootfs prefix also produced the digest above:

```sh
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes router \
  'head -c 31274410 /dev/ubiblock0_0 | sha256sum; grep " /rom " /proc/mounts'
```

Output: the matching SHA-256, plus `/dev/root /rom squashfs ro,relatime 0 0`.
No reboot, tracing change, partition write, or vendor helper was used. A host-only one-bit mutation
of the extracted TBS digest was rejected by `openssl`; the original input stayed unchanged.

**Inference:** LK's reported success authenticates metadata containing a digest and size that match
the real stock rootfs. The four traced partition reads fetch certificates; the shared signature helper
hashes certificate TBS bytes. This does not demonstrate an LK read/hash of the rootfs payload itself.
Exporting the metadata provides enough information for a later consumer to validate the signed
message, but does not prove that such a consumer runs. Existing bounded kernel/userspace searches
remain negative, not proof of non-enforcement. A matching stock rootfs cannot test failure policy.

## Reproduce the content match offline

Run from the repository root; this snippet only reads files and prints a digest. It is specific to
this verified backup and deliberately asserts its expected geometry and digest:

```python
from pathlib import Path
import hashlib, struct, zlib
base = Path("private/recovery/20261020-capture-prepared-20261021/images")
raw = (base / "mtd42-rootfs_b.bin").read_bytes()
sig = (base / "mtd41-rootfs_sig_b.bin").read_bytes()
assert hashlib.sha256(raw).hexdigest() == "c4e3f3d25b3aefca70995c070faa177931a61738b4997acd52a6446daee4cf01"
assert hashlib.sha256(sig).hexdigest() == "1ebb121adfbac5603dca0e65c3b276a315fda1450bdbd573f3c600b5f399d4b6"
blocks = {}
for pos in range(0, len(raw), 0x40000):
    ec = raw[pos:pos + 64]
    if ec[:4] != b"UBI#":
        continue
    assert (zlib.crc32(ec[:60]) ^ 0xffffffff) & 0xffffffff == struct.unpack_from(">I", ec, 60)[0]
    vid_offset, data_offset = struct.unpack_from(">II", ec, 16)
    assert data_offset == 0x2000 and 64 <= vid_offset <= data_offset - 64
    vid = raw[pos + vid_offset:pos + vid_offset + 64]
    if vid[:4] != b"UBI!":
        continue
    assert (zlib.crc32(vid[:60]) ^ 0xffffffff) & 0xffffffff == struct.unpack_from(">I", vid, 60)[0]
    volume, number = struct.unpack_from(">II", vid, 8)
    if volume == 0:
        assert number not in blocks
        blocks[number] = raw[pos + data_offset:pos + 0x40000]
assert sorted(blocks) == list(range(124))
squashfs = b"".join(blocks[number] for number in range(124))
assert squashfs[:4] == b"hsqs"
length = struct.unpack_from("<Q", squashfs, 40)[0]
assert length == int.from_bytes(sig[0xd0c:0xd10], "big") == 31274410
digest = hashlib.sha256(squashfs[:length]).digest()
assert digest == sig[0xcc9:0xce9]
print(length, digest.hex())
```

For independent PSS checking, extract the cert2 ranges above and SPKI `[0xb65,0xc8b)` into
host temporary files, convert SPKI with `openssl pkey -pubin -inform DER`, and verify:

```sh
openssl dgst -sha256 -verify cert2-pub.pem -signature cert2-sig.bin \
  -sigopt rsa_padding_mode:pss -sigopt rsa_pss_saltlen:32 \
  -sigopt rsa_mgf1_md:sha256 cert2-tbs.der
```

Expected: `Verified OK`. This checks the signature using the extracted public key, not LK's trust anchor.

## Next device tests: gate reached, no destructive test authorized

1. **Read-only positive baseline: passed.** The live hash, signed metadata, offline signatures,
   and stock backup agree. This is suitable as a preflight for later experiments, not permission to flash.
2. **Recovery first (#4): not demonstrated.** The existing `write_verify.py lk_a` dry run passed:
   active B, verified 2 MiB source at offset `0x11200000`, guards `mcupm_a`, `tee_a`, `lk_b`, `misc`,
   and `boot_para`. No USB connection or write occurred. Rewriting identical bytes would not prove
   erase behavior or restoration of changed data; a separate recoverable unit remains the documented
   place for that proof. UART read access is established, but UART does not itself restore NAND.
3. **Separate failure experiments, after recovery proof and explicit approval.** A bad certificate tests
   LK's error/halt/watchdog/slot behavior. A valid stock certificate paired with different rootfs bytes
   tests content enforcement. The latter must remain structurally valid and mountable: UBI, SquashFS,
   or decompression failure alone would not establish a cryptographic rejection. UART evidence must
   distinguish those outcomes. These experiments answer different questions and must not be combined.
   Neither has been constructed or deployed here as a flashable test image.
4. **Preserve recovery state.** Before any slot-A boot experiment, identify the exact slot-switch method
   and every metadata write, and prevent or account for stock `zmtk_boot_done` copying the booted slot
   over the other slot. A second stock slot is not a guaranteed rollback. Re-read target and guards;
   stop on an unexpected difference. Any plan must include exact restore artifacts, ranges, and a
   recovery route independent of the experimental boot.

The user confirmed on 2026-10-28 that this is still the only X28. An independent router-safety
review approved the documentation/read-only baseline and retained the failure-test stop below.

**Current verdict:** GO for the completed read-only baseline; NO-GO for a modified-image boot on the
only unit while changed-data restoration and safe slot selection remain unproven. No risky command
sequence is supplied as though it were ready. The next decision is the recoverable test hardware and
restore demonstration, not another round of speculative NAND call tracing.
