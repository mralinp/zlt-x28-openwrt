# Reverse engineering and clean-room rules

How this project treats reverse engineering, the private SDK and the proprietary MediaTek userspace, so an open replacement can reach official OpenWrt. This is project policy and a summary of general principles, **not legal advice**; rules differ by country, and anything to be published or shipped deserves a check by a lawyer or a free-software legal body (for example the Software Freedom Conservancy).

## Why this matters

| Piece | Licence situation | What we do |
|---|---|---|
| Vendor Linux 4.19 kernel and its drivers | GPL-2 | May be read, ported and published. |
| MIPC library (`libmipc_msg`, `mipc_wan_cli`), `ccci_fsd`, other modem userspace | proprietary, no source | Used as binaries in the native image today. Not acceptable for official OpenWrt; an open replacement is a goal (#607). |
| The vendor SDK (`sdk-fg360/`) | some files marked confidential and proprietary to MediaTek; reached the owner after support ended | Private use only: study, comparison, private builds. Its files and code do not go into this repository. |
| Observations from our own unit (traces, behaviour, measurements) | ours | Published. |

## The rule that keeps a replacement clean

A clean room separates **information**, not people or countries.

1. **Spec writer.** May read the SDK, disassemble binaries and trace the live interfaces. Produces a *functional specification* only: message IDs, field layouts, call order, state machine, timing, error handling. No pasted decompiler output, no code structure copied from the vendor, no vendor comments or identifiers beyond what interoperability needs.
2. **Implementer.** Writes the code from that specification alone. Has not read the proprietary code, the SDK or the disassembly, and does not look at the spec writer's working notes.
3. **Log.** Record who saw what and what was handed over. A neutral review of the spec before hand-over helps.
4. Facts and interfaces are generally not protected by copyright; code and its expressive structure are. That is why the split works.

Maintainers who have read the SDK or disassembly (as the owner and the assistant working on this repository have) are **spec writers, not implementers**, for MIPC and `ccci_fsd`.

## What does not work

- **Geography.** Having someone in a country with weak rules decompile freely and write the *code*, then using it elsewhere, does not clean it. Copyright follows where the copying, use and distribution happen. Code written after reading the proprietary source or disassembly can be a derivative of it, wherever its author sat.
- **Engineered ignorance.** Arranging not to know how code was made does not protect the user; in UK law, for example, dealing in infringing copies is an offence when one knows *or has reason to believe* they infringe, and a pipeline built to avoid knowing counts against good faith.
- **A public copy of the SDK.** A third party posting files does not grant a right to redistribute them, and the confidential markings remain. It makes discussing them easier, not copying them.

## Other things that apply independently of copyright

- **Contract and confidentiality**: any NDA or licence terms attached to how the SDK was obtained.
- **Decompilation for interoperability** is permitted in the EU, the UK and the US under conditions (the UK's CDPA s50B, for instance, limits it to what is needed for interoperability, information not otherwise available, and no use to build a substantially similar program; the US has fair-use and DMCA interoperability exceptions). Read the exact text for your country.
- **Sanctions and export rules** can apply to working with people or services in some countries. Check before exchanging work or money.

## What this repository publishes

Every fact in a published doc has one of these origins; record it when adding facts:

| Origin | May publish? |
|---|---|
| Observed on our own unit (traces, behaviour, measurements) | Yes |
| GPL kernel source (names, structures, offsets) | Yes, with the file named |
| Open-source tools output (Ghidra on our own dump), as findings and offsets only | Yes; no decompiled code, no dump |
| SDK-only material (non-GPL files, confidential markings) | No code or files; at most a pointer, per the owner's decision |
| Firmware or modem image dumps | No (kept private) |

Open items:
- Audit where each MIPC message ID published for `x28-nrband` (for example 0x40d, 0x411 and the TLV numbers in `docs/NATIVE-CELLULAR.md`) came from, and mark each as observed or SDK-derived.
- Note the provenance of the modem-header fields in `docs/research/memory-accounting.md` (names taken from the GPL kernel driver's structure definition).
- The spec itself (AP to modem interface), written from observable behaviour only.

Related: #301 (modem memory), #606 (modem image analysis), #607 (this document).
