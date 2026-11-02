//! x28flash: read-only USB backup for the ZLT X28 (MT6890) through its preloader and download agent.
//! Phase 1 of issue #240: detect, read the layout, dump and verify. There is no write path.
mod brom;
mod da;
#[cfg(test)]
mod fake;
mod layout;
mod usb;

use std::fs;
use std::io::{self, Write};
use std::path::{Path, PathBuf};
use std::process::ExitCode;
use std::thread::sleep;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use anyhow::{bail, ensure, Context, Result};
use clap::{Parser, Subcommand};
use console::style;
use dialoguer::{Confirm, Input, Select};
use indicatif::{MultiProgress, ProgressBar, ProgressStyle};
use sha2::{Digest, Sha256};

use layout::Part;
use usb::Link;

/// Read-only USB backup tool for the ZLT X28. Run without arguments for a guided session.
///
/// The modem's USB-C port needs a USB-A-to-C cable. Linux: run as root or add a udev rule for 0e8d:2000.
/// Windows: the preloader port needs the WinUSB driver (e.g. via Zadig) instead of the serial driver.
#[derive(Parser)]
#[command(version)]
struct Cli {
    #[command(subcommand)]
    cmd: Option<Cmd>,
}

#[derive(Subcommand)]
enum Cmd {
    /// Wait for the preloader, handshake and show the chip and boot-security config (no download agent).
    Detect,
    /// Print the partition layout (offline).
    Partitions {
        /// /proc/mtd text from the unit instead of the built-in X28 layout
        #[arg(long)]
        mtd: Option<PathBuf>,
    },
    /// Read partitions over USB into a new folder with SHA256SUMS. Read-only.
    Dump {
        /// Download agent: DA_BR.bin from the community X28 SP Flash Tool package (see docs/RECOVERY.md)
        #[arg(long)]
        da: PathBuf,
        /// Output folder (must not exist); default x28-backup-<date>-<time>
        #[arg(long)]
        out: Option<PathBuf>,
        /// Only these partitions, comma-separated (default: all)
        #[arg(long, value_delimiter = ',')]
        only: Vec<String>,
        /// Compare each image with a verified backup folder (SHA256SUMS + mtd.txt)
        #[arg(long)]
        backup: Option<PathBuf>,
        #[arg(long)]
        mtd: Option<PathBuf>,
        /// Skip the confirmation prompt
        #[arg(long)]
        yes: bool,
    },
    /// Re-hash a dump folder against its SHA256SUMS, and optionally against another backup (offline).
    Verify {
        dir: PathBuf,
        #[arg(long)]
        backup: Option<PathBuf>,
    },
}

fn ok(msg: impl std::fmt::Display) {
    println!("{} {msg}", style("✔").green().bold());
}

fn note(msg: impl std::fmt::Display) {
    println!("{} {msg}", style("›").cyan().bold());
}

fn spinner(msg: &str) -> ProgressBar {
    let pb = ProgressBar::new_spinner().with_message(msg.to_string());
    pb.set_style(ProgressStyle::with_template("{spinner:.cyan} {msg} {elapsed:.dim}").unwrap());
    pb.enable_steady_tick(Duration::from_millis(80));
    pb
}

fn bytes(n: u64) -> String {
    format!("{:.1} MiB", n as f64 / (1 << 20) as f64)
}

/// UTC "YYYYmmddTHHMMSS" (no date crate for one timestamp; Howard Hinnant's civil-from-days).
fn timestamp() -> String {
    let s = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs() as i64;
    let z = s.div_euclid(86400) + 719_468;
    let (era, doe) = (z.div_euclid(146_097), z.rem_euclid(146_097));
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146_096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let (d, m) = (doy - (153 * mp + 2) / 5 + 1, if mp < 10 { mp + 3 } else { mp - 9 });
    let y = yoe + era * 400 + i64::from(m <= 2);
    let t = s.rem_euclid(86400);
    format!("{y:04}{m:02}{d:02}T{:02}{:02}{:02}", t / 3600, t / 60 % 60, t % 60)
}

fn load_layout(mtd: Option<&Path>) -> Result<Vec<Part>> {
    match mtd {
        Some(p) => layout::parse_mtd(&fs::read_to_string(p).with_context(|| format!("cannot read {}", p.display()))?),
        None => layout::parse_mtd(layout::X28_MTD),
    }
}

/// Wait for a freshly powered preloader, handshake and check it is an X28 with boot security off.
fn connect() -> Result<(usb::Usb, brom::Target)> {
    if usb::find().is_some() {
        let pb = spinner("A MediaTek port is already connected: unplug the modem's power (it must start fresh)…");
        while usb::find().is_some() {
            sleep(Duration::from_millis(100));
        }
        pb.finish_and_clear();
    }
    let pb = spinner("Waiting for the preloader (0e8d:2000). Plug in the modem's power now…");
    let info = loop {
        if let Some(i) = usb::find() {
            break i;
        }
        sleep(Duration::from_millis(50));
    };
    pb.set_message("Handshaking…");
    let mut port = usb::Usb::open(&info)?;
    brom::handshake(&mut port, info.product_id() == usb::PID_BROM)?;
    port.set_timeout(Duration::from_secs(5));
    let t = brom::identify(&mut port)?;
    pb.finish_and_clear();
    ok(format!(
        "Connected: hw code {:#x}, hw ver {:#x}, {} mode, target config {:#x}",
        t.hw_code, t.hw_ver, if t.brom { "BROM" } else { "preloader" }, t.config
    ));
    ensure!(t.hw_code == da::HW_CODE, "this is not an MT6890 (hw code {:#x}); x28flash only knows the ZLT X28", t.hw_code);
    ensure!(!t.brom, "BROM mode is untested on the X28; power-cycle without holding any key to get the preloader");
    ensure!(t.config == 0, "boot security is on (target config {:#x}); the X28 tested here has it off", t.config);
    Ok((port, t))
}

fn detect() -> Result<bool> {
    connect()?;
    note("No download agent was loaded and nothing was written, but the preloader may have counted this power-on as a");
    note("boot try for slot A: cycle the power, let A boot fully (x28-bootok resets the count) before another session.");
    Ok(true)
}

fn partitions(mtd: Option<&Path>) -> Result<bool> {
    let parts = load_layout(mtd)?;
    println!("{:>3}  {:<18} {:>12} {:>12}", "mtd", "name", "offset", "size");
    for p in &parts {
        println!("{:>3}  {:<18} {:>#12x} {:>12}", p.index, p.name, p.offset, bytes(p.size));
    }
    let end = parts.last().map_or(0, |p| p.offset + p.size);
    note(format!("{} partitions, {} ({end:#x}){}", parts.len(), bytes(end),
                 if mtd.is_none() { ", built-in X28 layout" } else { "" }));
    Ok(true)
}

struct HashWriter<W: Write> {
    w: W,
    h: Sha256,
}

impl<W: Write> Write for HashWriter<W> {
    fn write(&mut self, b: &[u8]) -> io::Result<usize> {
        let n = self.w.write(b)?;
        self.h.update(&b[..n]);
        Ok(n)
    }
    fn flush(&mut self) -> io::Result<()> {
        self.w.flush()
    }
}

fn load_da(path: &Path) -> Result<da::Loader> {
    let file = fs::read(path).with_context(|| format!("cannot read the download agent {}", path.display()))?;
    let sha = layout::hex(&Sha256::digest(&file));
    ensure!(sha == da::DA_SHA256,
            "{} is not the DA this tool was tested with (sha256 {sha}, expected {}). Use DA_BR.bin from the \
             community X28 package; see docs/RECOVERY.md", path.display(), da::DA_SHA256);
    da::parse_loader(&file)
}

fn dump(da_path: &Path, out: Option<PathBuf>, only: &[String], backup: Option<&Path>, mtd: Option<&Path>, yes: bool) -> Result<bool> {
    let loader = load_da(da_path)?;
    ok(format!("Download agent verified (sha256 {}…)", &da::DA_SHA256[..12]));
    let layout = load_layout(mtd)?;
    let end = layout.last().map_or(0, |p| p.offset + p.size);
    for name in only {
        ensure!(layout.iter().any(|p| &p.name == name), "no partition {name:?} (see `x28flash partitions`)");
    }
    let parts: Vec<Part> = layout.iter().filter(|p| only.is_empty() || only.contains(&p.name)).cloned().collect();
    let expected = backup.map(|b| layout::backup_sums(b, &layout)).transpose()?;
    if let Some(b) = backup {
        ok(format!("Backup layout and checksums loaded from {}", b.display()));
    }
    let total: u64 = parts.iter().map(|p| p.size).sum();
    let out = out.unwrap_or_else(|| PathBuf::from(format!("x28-backup-{}", timestamp().replace('T', "-"))));

    println!();
    note(format!("Reading {} partition(s), {} into {}", parts.len(), bytes(total), out.display()));
    note(format!("About {} min at the measured 0.6 MB/s. Read-only: nothing on the modem is changed.",
                 total / 600_000 / 60 + 1));
    note("The modem is offline (no internet) until you cycle its power afterwards.");
    note("The images hold this unit's identity and credentials: keep them private.");
    if !yes && !Confirm::new().with_prompt("Unplug the modem's power now. Ready to start?").default(true).interact()? {
        return Ok(false);
    }

    fs::create_dir(&out).with_context(|| format!("cannot create {} (it must not exist yet)", out.display()))?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(&out, fs::Permissions::from_mode(0o700))?;
    }
    fs::create_dir(out.join("images"))?;
    fs::write(out.join("mtd.txt"), mtd.map_or(Ok(layout::X28_MTD.to_string()), fs::read_to_string)?)?;

    let (mut port, _) = connect()?;
    let pb = spinner("Loading the download agent into the modem's RAM…");
    port.set_timeout(Duration::from_secs(30));
    let mut session = da::start(port, &loader, &timestamp())?;
    let nand = session.nand_info()?;
    pb.finish_and_clear();
    ok(format!("Download agent running: NAND {} total, page {:#x}, block {:#x}, spare {:#x}",
               bytes(nand.total_size), nand.page_size, nand.block_size, nand.spare_size));
    ensure!(nand.page_size == 0x1000 && nand.block_size == 0x40000 && nand.total_size >= end,
            "NAND geometry does not match the X28 layout (needs {end:#x} bytes)");

    // Boot-tries guard (CLAUDE.md): stock B erases A once A's tries pass 3, and a download-mode power-on may count
    // as a try. 1 can be this session's own power-on; 2 or more means sessions were chained without a good boot.
    let misc = layout.iter().find(|p| p.name == "misc").context("layout has no misc partition")?;
    let mut buf = vec![];
    session.read_flash(misc.offset, misc.size, &mut buf, |_| ())?;
    let tries = layout::a_tries(&buf)?;
    fs::write(out.join("misc-tries.txt"), format!("slot A tries per misc copy at session start: {tries:?}\n"))?;
    ensure!(tries.iter().all(|&t| t < 2),
            "slot A boot tries are {tries:?}: an earlier session was not followed by a good boot. Stop here: \
             cycle the power, let slot A boot fully and check its tries are 0 (docs/TESTING.md 27) before retrying");
    ok(format!("Slot A boot tries {tries:?} (saved in misc-tries.txt)"));

    let mp = MultiProgress::new();
    let all = mp.add(ProgressBar::new(total));
    all.set_style(ProgressStyle::with_template("{prefix:>12.bold} [{bar:30.cyan/blue}] {bytes}/{total_bytes} {bytes_per_sec} eta {eta}")
        .unwrap().progress_chars("=> "));
    all.set_prefix("total");
    let (mut sums, mut failed, mut diffs) = (String::new(), vec![], vec![]);
    let started = Instant::now();
    for (i, p) in parts.iter().enumerate() {
        let path = out.join("images").join(p.image_name());
        let tmp = path.with_extension("part");
        all.set_message(p.name.clone());
        mp.println(format!("{} [{}/{}] {} ({})", style("›").cyan(), i + 1, parts.len(), p.name, bytes(p.size)))?;
        let mut w = HashWriter { w: io::BufWriter::new(fs::File::create(&tmp)?), h: Sha256::new() };
        let res = session.read_flash(p.offset, p.size, &mut w, |n| all.inc(n)).and_then(|n| {
            w.flush()?;
            Ok(n)
        });
        match res {
            Ok(n) if n == p.size => {
                fs::rename(&tmp, &path)?;
                let sha = layout::hex(&w.h.finalize());
                sums.push_str(&format!("{sha}  images/{}\n", p.image_name()));
                let tag = match expected.as_ref().map(|e| e[&p.name] == sha) {
                    Some(true) => style("MATCH").green().to_string(),
                    Some(false) => {
                        diffs.push(p.name.clone());
                        style("DIFF").yellow().to_string()
                    }
                    None => String::new(),
                };
                mp.println(format!("{} {:<18} {}… {tag}", style("✔").green(), p.name, &sha[..16]))?;
            }
            Ok(n) => bail!("{}: read {n:#x} of {:#x} bytes", p.name, p.size),
            Err(e) => {
                // A failed READ-FLASH leaves the DA session in an unknown state: stop, keep what is done.
                mp.println(format!("{} {}: {e:#}", style("✖").red(), p.name))?;
                failed.push(p.name.clone());
                break;
            }
        }
    }
    all.finish_and_clear();
    fs::write(out.join("SHA256SUMS"), &sums)?;
    if !session.log.is_empty() {
        fs::write(out.join("da.log"), session.log.join("\n") + "\n")?;
    }

    println!();
    let done = sums.lines().count();
    ok(format!("{done}/{} partition(s) read in {:.0?} into {}", parts.len(), started.elapsed(), out.display()));
    if expected.is_some() {
        note(format!("{} MATCH, {} DIFF against the backup{}", done - diffs.len(), diffs.len(),
                     if diffs.is_empty() { String::new() } else { format!(": {}", diffs.join(", ")) }));
        if !diffs.is_empty() {
            note("Partitions the firmware writes while running (nvdata, protect1/2, user_config, productinfo, \
                  user_data, the active rootfs) are expected to differ between boots.");
        }
    }
    if !failed.is_empty() {
        println!("{} stopped at {}; re-run with --only for the rest after a power cycle", style("✖").red(), failed.join(", "));
    }
    note("Cycle the modem's power to boot it normally.");
    Ok(failed.is_empty() && done == parts.len())
}

fn verify(dir: &Path, backup: Option<&Path>) -> Result<bool> {
    let sums = layout::parse_sums(&fs::read_to_string(dir.join("SHA256SUMS")).context("no SHA256SUMS in that folder")?);
    let theirs = match backup {
        Some(b) => layout::parse_sums(&fs::read_to_string(b.join("SHA256SUMS")).context("backup has no SHA256SUMS")?),
        None => Default::default(),
    };
    let mut keys: Vec<&String> = sums.keys().collect();
    keys.sort();
    let (mut bad, mut diff) = (0, 0);
    for k in keys {
        let got = layout::sha256_file(&dir.join(k))?;
        let own = got == sums[k];
        let other = theirs.get(k).map(|h| *h == got);
        bad += usize::from(!own);
        diff += usize::from(other == Some(false));
        let mark = if own { style("✔").green() } else { style("✖").red() };
        let vs = match other {
            Some(true) => style("MATCH").green().to_string(),
            Some(false) => style("DIFF").yellow().to_string(),
            None if backup.is_some() => style("not in backup").dim().to_string(),
            None => String::new(),
        };
        println!("{mark} {k:<36} {vs}");
    }
    ok(format!("{} image(s): {bad} corrupt{}", sums.len(), if backup.is_some() { format!(", {diff} differ from the backup") } else { String::new() }));
    Ok(bad == 0)
}

fn guided() -> Result<bool> {
    println!("{}  read-only USB backup for the ZLT X28\n", style(format!("x28flash {}", env!("CARGO_PKG_VERSION"))).bold().cyan());
    let choices = ["Back up every partition", "Back up some partitions", "Detect the modem only", "Show the partition layout", "Verify a backup folder"];
    let pick = Select::new().with_prompt("What do you want to do?").items(&choices).default(0).interact()?;
    let ask_da = || -> Result<PathBuf> {
        Ok(Input::<String>::new().with_prompt("Path to DA_BR.bin").interact_text()?.trim().into())
    };
    match pick {
        0 => dump(&ask_da()?, None, &[], None, None, false),
        1 => {
            let names: Vec<String> = Input::<String>::new()
                .with_prompt("Partitions (comma-separated, e.g. lk_b,boot_a)")
                .interact_text()?
                .split(',')
                .map(|s| s.trim().to_string())
                .collect();
            dump(&ask_da()?, None, &names, None, None, false)
        }
        2 => detect(),
        3 => partitions(None),
        _ => verify(Path::new(Input::<String>::new().with_prompt("Backup folder").interact_text()?.trim()), None),
    }
}

fn main() -> ExitCode {
    let res = match Cli::parse().cmd {
        None => guided(),
        Some(Cmd::Detect) => detect(),
        Some(Cmd::Partitions { mtd }) => partitions(mtd.as_deref()),
        Some(Cmd::Dump { da, out, only, backup, mtd, yes }) => dump(&da, out, &only, backup.as_deref(), mtd.as_deref(), yes),
        Some(Cmd::Verify { dir, backup }) => verify(&dir, backup.as_deref()),
    };
    match res {
        Ok(true) => ExitCode::SUCCESS,
        Ok(false) => ExitCode::FAILURE,
        Err(e) => {
            eprintln!("{} {e:#}", style("✖ error:").red().bold());
            ExitCode::FAILURE
        }
    }
}

#[cfg(test)]
mod tests {
    #[test]
    fn timestamp_is_well_formed() {
        let t = super::timestamp();
        assert_eq!((t.len(), &t[8..9]), (15, "T"));
        assert!(t[..4].parse::<u32>().unwrap() >= 2026);
    }
}
