// Ghidra post-script: analyze this unit's ORIGINAL LK; never changes firmware bytes.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import java.math.BigInteger;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HexFormat;

public class LkAuthentication extends GhidraScript {
    private static final long BASE = 0x83fffe00L;
    private static final String SHA = "0ad94f065ebcfeefd157640d179b1b52779829a85179d07d38dd818b79007156";
    private static final long[] ENTRIES = {
        0xee12, 0x1e508, 0x248c2, 0x24ace, 0x280c2, 0x2843a,
        0x284de, 0x2856a, 0x18b98, 0x8c5a, 0x2488e, 0x28028,
        0x266ac, 0x25c48, 0x25a2e, 0x24764, 0x27f84
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
        for (long off : ENTRIES) {
            Address addr = toAddr(BASE + off);
            disassemble(addr);
            if (getFunctionAt(addr) == null && createFunction(addr, null) == null)
                throw new IllegalStateException("Could not create function at " + addr);
        }
        analyzeAll(currentProgram);
        DecompInterface dc = new DecompInterface();
        try {
            if (!dc.openProgram(currentProgram)) throw new IllegalStateException(dc.getLastMessage());
            for (long off : ENTRIES) {
                Function f = getFunctionAt(toAddr(BASE + off));
                println("FUNCTION file=0x" + Long.toHexString(off) + " VA=" + f.getEntryPoint());
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
}
