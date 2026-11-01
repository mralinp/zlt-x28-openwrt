// Ghidra post-script: analyze this unit's ORIGINAL LK; never changes firmware bytes.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.pcode.*;
import java.math.BigInteger;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HexFormat;

public class LkAuthentication extends GhidraScript {
    private static final long BASE = 0x83fffe00L;
    private static final String SHA = "0ad94f065ebcfeefd157640d179b1b52779829a85179d07d38dd818b79007156";
    private record Site(long offset, String group, String name, String note) {}
    private static final Site[] SITES = {
        new Site(0xee12, "Boot", "load_boot_or_recovery_image", "Selects boot/recovery plus slot suffix. Policy gates certificate, header and payload authentication. See calls eef0/eefc/ef7c; errors assert at f004/f026/f048."),
        new Site(0x1e508, "Boot", "load_named_partition_image", "Generic image loader. Shares certificate/header/payload helpers with boot and boot_para; these helpers are not boot-only patch points."),
        new Site(0x248c2, "Rootfs", "verify_rootfs_certificates_or_panic", "START HERE: rootfs_sig plus slot suffix. Calls certificate verifier at 24908; nonzero result asserts. Does not establish a hash of actual SquashFS bytes."),
        new Site(0x24ace, "Policy", "partition_authentication_required", "START HERE: partition policy dispatch. Inputs S and L select a policy word's low bit. Default and boot words are 0,2,1,2. Do not equate this result with printed sbc_en."),
        new Site(0x280c2, "Boot", "verify_image_certificate_chain", "Initializes shared authentication state, parses metadata, reads certificates and invokes verification helpers. Returns error; caller chooses fatal behavior."),
        new Site(0x2843a, "Boot", "verify_image_header_sha256", "Checks header length, computes SHA-256 and compares 32 bytes against certificate-derived state. Mismatch returns 0x101010; length mismatch 0x101012."),
        new Site(0x284de, "Boot", "authenticate_image_payload", "START HERE: computes 32-byte authentication result and compares saved expected result. Monitor-backed calculation semantics remain partly unresolved. Failure is returned to caller."),
        new Site(0x2856a, "Rootfs", "verify_rootfs_certificate_chain", "Reads certificates from rootfs_sig. Success publishes metadata buffer/length; failure clears outputs. Removing only a panic call is not a reviewed safe bypass."),
        new Site(0x18b98, "Failure", "assertion_panic", "Prints assertion/panic and enters terminal helper. Traced failure callers do not return normally."),
        new Site(0x8c5a, "Failure", "platform_terminal_action", "For rootfs panic arguments r0=0,r1=9: disables interrupts at 8c7c and spins at 8c7e. Other argument-dependent actions are not fully classified."),
        new Site(0x2488e, "Policy", "get_lock_policy_input_L", "Obtains state through 28eb8. State 3 maps to L=0; other states/error map to L=1. L is an analyst label, not a proven hardware lock bit."),
        new Site(0x28028, "Policy", "get_secure_policy_input_S", "Writes resolve_sboot_configuration(1) to caller output. S is an analyst label; current runtime writers/state remain unexamined."),
        new Site(0x266ac, "Crypto", "authenticate_certificate_public_key", "Prints sbc_en. Zero selects OEM-key comparison; nonzero selects hashed-key comparison. Certificate signatures are verified elsewhere, not disabled by this branch."),
        new Site(0x25c48, "Policy", "read_sbc_status_register_bit", "Returns (*(u32*)0x51ec0060 & 3) >> 1. Hardware semantics and fuse interpretation are not independently established."),
        new Site(0x25a2e, "Crypto", "sha256_buffer", "SHA-256 initial-state constants and 32-byte output corroborate identification. Analyst name, not recovered vendor symbol."),
        new Site(0x24764, "Crypto", "compute_payload_auth_result_via_monitor", "Produces payload authentication result through helpers including monitor service 0x8200010e at call 2484e. Full secure-world/transformation semantics UNKNOWN."),
        new Site(0x27f84, "Policy", "resolve_sboot_configuration", "Config at file 3e380 is originally 0x11, returning S=1. Config 0 returns 0; 0x22 consults SBC register helper. Runtime writes to config not audited.")
    };

    @Override public void run() throws Exception {
        byte[] original = Files.readAllBytes(Path.of(currentProgram.getExecutablePath()));
        String hash = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(original));
        if (original.length != 0x200000 || !hash.equals(SHA))
            throw new IllegalArgumentException("Refusing unknown LK input: " + hash);
        if (!currentProgram.getLanguageID().toString().equals("ARM:LE:32:v8") ||
            currentProgram.getMinAddress().getOffset() != BASE)
            throw new IllegalArgumentException("Require ARM:LE:32:v8 and raw base 0x83fffe00");
        byte[] mapped = new byte[original.length];
        if (currentProgram.getMemory().getBytes(toAddr(BASE), mapped) != mapped.length ||
            !Arrays.equals(original, mapped))
            throw new IllegalArgumentException("Analysis memory differs from original file");
        println("INPUT VERIFIED " + hash + "; file offset zero maps to " + toAddr(BASE));

        // Only the private analysis database gets Thumb context, instructions and function metadata.
        if (getInstructionAt(toAddr(BASE + 0x277a)) == null) {
            currentProgram.getProgramContext().setValue(
                currentProgram.getLanguage().getRegister("TMode"),
                toAddr(BASE + 0x277a), toAddr(BASE + 0x2ef00), BigInteger.ONE);
            disassemble(toAddr(BASE + 0x277a));
        }
        for (Site site : SITES) {
            Address addr = toAddr(BASE + site.offset());
            disassemble(addr);
            if (getFunctionAt(addr) == null && createFunction(addr, null) == null)
                throw new IllegalStateException("Could not create function at " + addr);
        }
        analyzeAll(currentProgram);
        for (Site site : SITES) {
            Address addr = toAddr(BASE + site.offset());
            Function f = getFunctionAt(addr);
            Namespace ns = currentProgram.getSymbolTable().getOrCreateNameSpace(
                currentProgram.getGlobalNamespace(), site.group(), SourceType.USER_DEFINED);
            f.setParentNamespace(ns);
            f.setName(site.name(), SourceType.USER_DEFINED);
            String note = "ANALYST-ASSIGNED NAME, NOT VENDOR SOURCE. Original file offset 0x" +
                Long.toHexString(site.offset()) + ".\n" + site.note() + "\nNo firmware patch applied. Report: docs/research/lk-authentication-ghidra.md";
            f.setComment(note);
            setPlateComment(addr, note);
            currentProgram.getBookmarkManager().setBookmark(addr, BookmarkType.NOTE, site.group(), site.note());
            if (!f.getName().equals(site.name()) || !note.equals(f.getComment()))
                throw new IllegalStateException("Annotation readback failed at " + addr);
        }
        label(0x3e09c, "partition_auth_policy_table", "15 rows, 32 bytes each: four name pointers and four policy words.");
        label(0x3e380, "sboot_configuration", "Original value 0x11; software policy input, not a proven hardware fuse value.");
        label(0x5e458, "image_auth_header_state", "Shared runtime state populated by certificate-chain processing, VA 0x8405e258; raw-file backing here is not proof of initial runtime data.");
        label(0x5e710, "image_expected_payload_auth_result", "Runtime expected 32-byte payload authentication result, VA 0x8405e510; monitor path semantics partly unresolved.");
        label(0x5e734, "image_expected_header_sha256", "Runtime expected 32-byte header digest, VA 0x8405e534.");
        label(0x5da94, "verified_rootfs_metadata_buffer", "Runtime pointer exported on successful rootfs certificate verification, VA 0x8405d894.");
        label(0x5da98, "verified_rootfs_metadata_length", "Runtime length exported on successful rootfs certificate verification, VA 0x8405d898.");
        mark(0xee12, "01 Start here", "Boot image: follow Policy then certificate/header/payload checks; this is separate from Rootfs.");
        mark(0x248c2, "01 Start here", "Rootfs certificates: follow verifier return to assertion/halt. No custom kernel acceptance is established.");
        mark(0xeed8, "Boot failure branches", "r9 holds policy result; zero skips certificate/header checks.");
        mark(0xef6e, "Boot failure branches", "Zero policy skips payload authentication; nonzero reaches ef7c.");
        mark(0xf004, "Boot failure branches", "Certificate-check error reaches assertion_panic.");
        mark(0xf026, "Boot failure branches", "Header-check error reaches assertion_panic.");
        mark(0xf048, "Boot failure branches", "Payload-check error reaches assertion_panic.");
        mark(0x2490c, "Rootfs failure branches", "Verifier return compared with zero; error follows assertion route at 24932..24950.");
        mark(0x8c7e, "Failure", "Interrupt-disabled infinite loop in traced panic path. Original bytes unchanged.");
        if (currentProgram.getMemory().getBytes(toAddr(BASE), mapped) != mapped.length ||
            !Arrays.equals(original, mapped))
            throw new IllegalStateException("Analysis unexpectedly changed firmware bytes");
        println("ANNOTATIONS VERIFIED: 17 named functions, comments and navigation bookmarks; mapped bytes unchanged");
        DecompInterface dc = new DecompInterface();
        try {
            if (!dc.openProgram(currentProgram)) throw new IllegalStateException(dc.getLastMessage());
            int namedVariables = 0;
            namedVariables += variables(dc, 0xee12,
                "param_1", "boot_mode_selector", "iVar2", "authentication_required",
                "iVar3", "android_boot_header_buffer", "iVar4", "boot_partition_handle",
                "iVar5", "image_read_buffer", "iVar7", "full_image_read_count",
                "pcVar8", "selected_image_name", "uVar9", "page_size",
                "local_30", "partition_name_word0");
            namedVariables += variables(dc, 0x1e508,
                "param_1", "partition_alias", "param_2", "image_name", "param_3", "destination_buffer",
                "puVar3", "partition_header_buffer", "local_50", "image_payload_bytes",
                "local_48", "partition_name_word0");
            namedVariables += variables(dc, 0x248c2,
                "local_30", "signature_partition_name_word0", "local_14", "metadata_buffer",
                "local_18", "metadata_bytes");
            namedVariables += variables(dc, 0x24ace,
                "param_1", "partition_name", "bVar1", "authentication_required",
                "iVar3", "secure_policy_query_status", "pbVar4", "selected_policy_field",
                "puVar5", "row_name_cursor", "iVar6", "policy_row_index",
                "local_20", "lock_policy_L", "local_1c", "secure_policy_S");
            namedVariables += variables(dc, 0x280c2,
                "param_1", "partition_name", "param_2", "image_name", "param_3", "image_header_buffer",
                "param_4", "image_header_bytes", "param_5", "image_offset_low",
                "param_6", "image_offset_high", "param_7", "verification_option_unresolved",
                "cVar1", "image_name_character", "iVar2", "certificate_buffer",
                "local_48", "supplied_image_name");
            namedVariables += variables(dc, 0x2843a,
                "param_1", "header_buffer", "param_2", "header_bytes",
                "iVar1", "authentication_status", "iVar2", "digest_compare_status",
                "local_38", "computed_header_digest_word0");
            namedVariables += variables(dc, 0x284de,
                "param_1", "payload_buffer", "param_2", "payload_bytes",
                "iVar1", "authentication_status", "local_30", "computed_payload_auth_word0");
            namedVariables += variables(dc, 0x2856a,
                "param_1", "signature_partition_name", "param_3", "read_offset_low",
                "param_4", "read_offset_high", "param_5", "metadata_buffer_out",
                "param_6", "metadata_length_out", "iVar1", "certificate_buffer",
                "iVar2", "metadata_buffer", "iVar3", "verification_status",
                "uVar4", "certificate_total_bytes", "iVar5", "next_certificate_offset_low",
                "iVar6", "next_certificate_offset_high", "local_30", "size_limit_error",
                "local_28", "metadata_bytes");
            namedVariables += variables(dc, 0x2488e,
                "param_1", "lock_policy_L_out", "iVar1", "state_query_status",
                "uVar2", "query_status", "uVar3", "lock_policy_L", "local_14", "reported_lock_state");
            namedVariables += variables(dc, 0x28028,
                "param_1", "secure_policy_S_out", "uVar1", "secure_policy_S");
            namedVariables += variables(dc, 0x266ac,
                "param_1", "key_encoding_buffer", "param_2", "key_encoding_bytes",
                "param_3", "parsed_public_key", "uVar1", "logged_sbc_status", "uVar3", "dump_byte_index");
            namedVariables += variables(dc, 0x25a2e,
                "param_1", "input_buffer", "param_2", "remaining_input_bytes", "param_3", "digest_out",
                "iVar1", "buffer_fill_bytes", "uVar2", "hash_status", "uVar3", "chunk_bytes",
                "bVar4", "bit_count_carry", "local_98", "bit_count_low", "local_94", "bit_count_high",
                "local_90", "sha256_state_0", "local_8c", "sha256_state_1",
                "local_88", "sha256_state_2", "local_84", "sha256_state_3",
                "local_80", "sha256_state_4", "local_7c", "sha256_state_5",
                "local_78", "sha256_state_6", "local_74", "sha256_state_7",
                "local_70", "block_fill_bytes", "auStack_6c", "block_workspace");
            namedVariables += variables(dc, 0x24764,
                "param_1", "input_buffer", "param_2", "input_bytes", "param_3", "length_delta",
                "param_4", "result_words_out", "param_5", "result_capacity_bytes",
                "uVar1", "monitor_input_address", "iVar4", "block_buffer_address",
                "uVar5", "aligned_input_bytes", "local_34", "monitor_return_words");
            namedVariables += variables(dc, 0x27f84,
                "param_1", "log_chip_classification", "iVar1", "sbc_status");
            dc.flushCache();
            if (currentProgram.getMemory().getBytes(toAddr(BASE), mapped) != mapped.length ||
                !Arrays.equals(original, mapped))
                throw new IllegalStateException("Variable annotations changed firmware bytes");
            println("VARIABLES VERIFIED: " + namedVariables + " analyst role names; mapped bytes unchanged");
            for (Site site : SITES) {
                Function f = getFunctionAt(toAddr(BASE + site.offset()));
                println("FUNCTION file=0x" + Long.toHexString(site.offset()) + " VA=" + f.getEntryPoint() + " " + f.getName(true));
                ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(f.getEntryPoint());
                while (refs.hasNext()) {
                    Reference ref = refs.next();
                    println("REFERENCE " + ref.getReferenceType() + " file=0x" +
                        Long.toHexString(ref.getFromAddress().getOffset() - BASE));
                }
                DecompileResults result = dc.decompileFunction(f, 60, monitor);
                if (!result.decompileCompleted()) throw new IllegalStateException(result.getErrorMessage());
                println(result.getDecompiledFunction().getC());
                InstructionIterator it = currentProgram.getListing().getInstructions(f.getBody(), true);
                while (it.hasNext()) {
                    Instruction ins = it.next();
                    println("ASM file=0x" + Long.toHexString(ins.getAddress().getOffset() - BASE) + " " + ins);
                }
            }
            println("ANALYSIS COMPLETE; no firmware patch or export performed");
        } finally {
            dc.dispose();
        }
    }

    private int variables(DecompInterface dc, long offset, String... pairs) throws Exception {
        Function f = getFunctionAt(toAddr(BASE + offset));
        dc.flushCache();
        DecompileResults result = dc.decompileFunction(f, 60, monitor);
        if (!result.decompileCompleted()) throw new IllegalStateException(result.getErrorMessage());
        for (int i = 0; i < pairs.length; i += 2) {
            HighSymbol found = null;
            var symbols = result.getHighFunction().getLocalSymbolMap().getSymbols();
            while (symbols.hasNext()) {
                HighSymbol symbol = symbols.next();
                if (symbol.getName().equals(pairs[i]) || symbol.getName().equals(pairs[i + 1])) {
                    if (found != null) throw new IllegalStateException("Ambiguous variable " + pairs[i]);
                    found = symbol;
                }
            }
            if (found == null) throw new IllegalStateException("Missing variable " + f.getName(true) + ":" + pairs[i]);
            // Preserve recovered types/storage; names do not assert an original C prototype or struct layout.
            HighFunctionDBUtil.updateDBVariable(found, pairs[i + 1], null, SourceType.USER_DEFINED);
            boolean persisted = false;
            for (Variable variable : f.getAllVariables()) {
                if (variable.getName().equals(pairs[i + 1])) {
                    variable.setComment("Analyst role name; inferred from the original function's use sites. Types remain decompiler-derived.");
                    persisted = true;
                }
            }
            if (!persisted) throw new IllegalStateException("Variable readback failed: " + pairs[i + 1]);
        }
        return pairs.length / 2;
    }

    private void label(long offset, String name, String note) throws Exception {
        Address addr = toAddr(BASE + offset);
        createLabel(addr, name, true);
        setPlateComment(addr, "ANALYST LABEL: " + note);
    }

    private void mark(long offset, String category, String note) {
        Address addr = toAddr(BASE + offset);
        setEOLComment(addr, note);
        currentProgram.getBookmarkManager().setBookmark(addr, BookmarkType.NOTE, category, note);
    }
}
