// Local Ghidra database experiment only: no firmware export or device operations.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

public class LkBootAuthPreview extends GhidraScript {
    private static final long BASE = 0x83fffe00L;
    private static final String SHA = "0ad94f065ebcfeefd157640d179b1b52779829a85179d07d38dd818b79007156";
    private static final long[] SITES = {0xeedc, 0xef72};
    private static final long[] TARGETS = {0xef0e, 0xef84};

    @Override public void run() throws Exception {
        String[] args = getScriptArgs();
        require(args.length == 1 && Set.of("original", "apply", "verify").contains(args[0]),
            "Require original, apply or verify mode");
        String mode = args[0];
        byte[] original = Files.readAllBytes(Path.of(currentProgram.getExecutablePath()));
        require(original.length == 0x200000 && digest(original).equals(SHA), "Unknown source LK");
        require(currentProgram.getLanguageID().toString().equals("ARM:LE:32:v8") &&
            currentProgram.getMinAddress().getOffset() == BASE, "Wrong language or raw base");
        require(original[0xeedc] == 0x17 && original[0xeedd] == (byte)0xd0 &&
            original[0xef72] == 0x07 && original[0xef73] == (byte)0xd0, "Wrong original instructions");
        byte[] preview = original.clone();
        preview[0xeedd] = (byte)0xe0;
        preview[0xef73] = (byte)0xe0;
        require(Arrays.equals(mappedBytes(), mode.equals("verify") ? preview : original),
            "Mapped bytes are not the expected original/preview; refusing unknown or repeated patch");

        if (mode.equals("apply")) {
            checkInstructions(false);
            for (long offset : SITES) {
                Address addr = toAddr(BASE + offset);
                clearListing(addr, addr.add(1));
                currentProgram.getMemory().setByte(addr.add(1), (byte)0xe0);
                disassemble(addr);
            }
        }
        checkInstructions(!mode.equals("original"));
        require(Arrays.equals(mappedBytes(), mode.equals("original") ? original : preview),
            "Unexpected byte changes outside the two branch instructions");
        require(Arrays.equals(Files.readAllBytes(Path.of(currentProgram.getExecutablePath())), original),
            "Source file changed");
        if (!mode.equals("verify")) annotate(mode.equals("apply"));
        DecompInterface dc = new DecompInterface();
        try {
            require(dc.openProgram(currentProgram), "Cannot open decompiler");
            DecompileResults result = dc.decompileFunction(getFunctionAt(toAddr(BASE + 0xee12)), 60, monitor);
            require(result.decompileCompleted(), "Cannot decompile boot/recovery loader");
            println(result.getDecompiledFunction().getC());
        } finally { dc.dispose(); }
        println("BOOT AUTH " + mode.toUpperCase() + " VERIFIED: mapped SHA-256 " + digest(mappedBytes()));
        println("Source file unchanged; no firmware export or device operation performed");
    }

    private void annotate(boolean patched) throws Exception {
        String status = patched ? "LOCAL DATABASE PATCH PREVIEW; NOT FLASH-READY" : "ORIGINAL LK; NO PATCH";
        currentProgram.getOptions("X28 Review").setString("Status", status);
        currentProgram.getOptions("X28 Review").setString("Mapped SHA-256", digest(mappedBytes()));
        if (patched) {
            FunctionIterator functions = currentProgram.getFunctionManager().getFunctions(true);
            while (functions.hasNext()) {
                Function function = functions.next();
                String note = function.getComment();
                if (note != null && note.contains("No firmware patch applied.")) {
                    note = note.replace("No firmware patch applied.", status + "; only file eedc/ef72 changed.");
                    function.setComment(note);
                    setPlateComment(function.getEntryPoint(), note);
                }
            }
        }
        Function caller = getFunctionAt(toAddr(BASE + 0x4448));
        require(caller != null, "Analyze original LK before adding the preview");
        caller.setParentNamespace(currentProgram.getSymbolTable().getOrCreateNameSpace(
            currentProgram.getGlobalNamespace(), "Boot", SourceType.USER_DEFINED));
        caller.setName("prepare_kernel_from_selected_image", SourceType.USER_DEFINED);
        caller.setComment("ANALYST-ASSIGNED NAME. File 0x4448. Calls loader(1) at 4466 for mode 2/recovery; " +
            "loader(0) at 4496 otherwise/boot. Handoff preparation at file 3e3a is not fully audited.");
        mark(0xee12, "00 START HERE", status + ". Boot AND recovery loader. Rootfs checker stays separate. " +
            "Preloader acceptance and custom-kernel boot UNKNOWN. Imported source bytes remain original; " +
            (patched ? "the preview exists only in this program database. " : "all mapped bytes are unchanged. ") +
            "Report: docs/research/lk-boot-auth-preview.md");
        mark(0xee58, "Policy call preserved", "Original policy call remains intact, including security-state initialization.");
        mark(0xeedc, "Boot authentication branches", patched ?
            "PATCH: 17 d0 -> 17 e0 (BEQ -> B), same target VA 8400ed0e. Skips certificate/header checks." :
            "ORIGINAL: 17 d0, BEQ 8400ed0e. Only zero policy skips certificate/header checks.");
        mark(0xef72, "Boot authentication branches", patched ?
            "PATCH: 07 d0 -> 07 e0 (BEQ -> B), same target VA 8400ed84. Skips payload authentication." :
            "ORIGINAL: 07 d0, BEQ 8400ed84. Only zero policy skips payload authentication.");
        mark(0x248c2, "Rootfs unchanged", "Rootfs certificate wrapper and its fatal failure path are unchanged.");
        mark(0x3fe00, "Separate payload untouched", "MTK header names the second payload aee_lk, size 0x3ede4; " +
            "payload starts file 0x40000. Its load/execution path is UNKNOWN. Do not reuse first-payload VAs here.");
    }

    private void mark(long offset, String category, String note) {
        Address addr = toAddr(BASE + offset);
        setPlateComment(addr, note);
        currentProgram.getBookmarkManager().setBookmark(addr, BookmarkType.NOTE, category, note);
    }

    private void checkInstructions(boolean patched) throws Exception {
        for (int i = 0; i < SITES.length; i++) {
            Instruction ins = getInstructionAt(toAddr(BASE + SITES[i]));
            require(ins != null && ins.getLength() == 2 &&
                ins.getMnemonicString().equals(patched ? "b" : "beq") &&
                Arrays.equals(ins.getFlows(), new Address[]{toAddr(BASE + TARGETS[i])}),
                "Wrong branch at file 0x" + Long.toHexString(SITES[i]));
        }
    }

    private byte[] mappedBytes() throws Exception {
        byte[] bytes = new byte[0x200000];
        require(currentProgram.getMemory().getBytes(toAddr(BASE), bytes) == bytes.length, "Short mapping");
        return bytes;
    }

    private String digest(byte[] bytes) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }

    private void require(boolean condition, String message) {
        if (!condition) throw new IllegalStateException(message);
    }
}
