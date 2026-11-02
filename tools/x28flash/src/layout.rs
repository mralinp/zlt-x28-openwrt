//! The X28 NAND layout (/proc/mtd), backup naming and SHA256SUMS, as tools/recovery/common.py uses them.
use std::collections::HashMap;
use std::fs::File;
use std::io::Read;
use std::path::Path;

use anyhow::{bail, ensure, Context, Result};
use sha2::{Digest, Sha256};

/// /proc/mtd of the test unit (stock and native images share it). The NAND has no partition table the DA
/// can read; partitions sit back to back from 0, which full USB reads matched by hash (docs/RECOVERY.md).
pub const X28_MTD: &str = include_str!("x28-mtd.txt");

#[derive(Debug, Clone, PartialEq)]
pub struct Part {
    pub index: usize,
    pub name: String,
    pub size: u64,
    pub offset: u64,
}

impl Part {
    pub fn image_name(&self) -> String {
        format!("mtd{:02}-{}.bin", self.index, self.name)
    }
}

/// Parse /proc/mtd; strict like common.parse_mtd.
pub fn parse_mtd(text: &str) -> Result<Vec<Part>> {
    let mut parts: Vec<Part> = vec![];
    let mut offset = 0;
    for line in text.lines().skip(1).map(str::trim).filter(|l| !l.is_empty()) {
        let bad = || format!("unexpected /proc/mtd line: {line:?}");
        let (dev, rest) = line.split_once(": ").with_context(bad)?;
        let f: Vec<&str> = rest.split(' ').collect();
        let index: usize = dev.strip_prefix("mtd").and_then(|n| n.parse().ok()).with_context(bad)?;
        ensure!(f.len() == 3 && f[2].len() > 2 && f[2].starts_with('"') && f[2].ends_with('"'), bad());
        let name = &f[2][1..f[2].len() - 1];
        ensure!(name.chars().all(|c| c.is_ascii_alphanumeric() || c == '_'), bad());
        let size = u64::from_str_radix(f[0], 16).with_context(bad)?;
        u64::from_str_radix(f[1], 16).with_context(bad)?;
        ensure!(index == parts.len(), "mtd{index} out of order");
        parts.push(Part { index, name: name.into(), size, offset });
        offset += size;
    }
    ensure!(!parts.is_empty(), "no partitions in /proc/mtd text");
    Ok(parts)
}

/// `sha256  path` lines, as sha256sum writes them.
pub fn parse_sums(text: &str) -> HashMap<String, String> {
    text.lines().filter_map(|l| l.split_once("  ")).map(|(h, p)| (p.to_string(), h.to_string())).collect()
}

pub fn sha256_file(path: &Path) -> Result<String> {
    let mut f = File::open(path).with_context(|| format!("cannot open {}", path.display()))?;
    let mut h = Sha256::new();
    let mut buf = vec![0; 1 << 20];
    loop {
        let n = f.read(&mut buf)?;
        if n == 0 {
            return Ok(hex(&h.finalize()));
        }
        h.update(&buf[..n]);
    }
}

pub fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

/// Expected image hashes from a backup folder (tools/recovery layout: SHA256SUMS + images/), checked
/// against `parts` by its own mtd.txt so a backup of another layout is refused.
pub fn backup_sums(dir: &Path, parts: &[Part]) -> Result<HashMap<String, String>> {
    let mtd = ["mtd.txt", "metadata/mtd.txt"].iter().map(|p| dir.join(p)).find(|p| p.exists());
    let Some(mtd) = mtd else { bail!("{} has no mtd.txt", dir.display()) };
    ensure!(parse_mtd(&std::fs::read_to_string(&mtd)?)? == parts, "backup layout differs from the layout in use");
    let sums = parse_sums(&std::fs::read_to_string(dir.join("SHA256SUMS")).context("backup has no SHA256SUMS")?);
    parts
        .iter()
        .map(|p| {
            let key = format!("images/{}", p.image_name());
            let h = sums.get(&key).with_context(|| format!("backup SHA256SUMS lacks {key}"))?;
            Ok((p.name.clone(), h.clone()))
        })
        .collect()
}

/// Slot A's boot tries from the four copies of the `misc` A/B record (bytes `00 41 42 30`, then 4 x ff, then A:
/// priority, tries, success, up-type), one erase block apart (docs/research/slot-selection.md).
pub fn a_tries(misc: &[u8]) -> Result<[u8; 4]> {
    let mut tries = [0; 4];
    for (n, t) in tries.iter_mut().enumerate() {
        let r = 0x800 + n * 0x40000;
        ensure!(misc.get(r..r + 4) == Some(&b"\0AB0"[..]), "misc copy {n} has no A/B record at {r:#x}");
        *t = misc[r + 9];
    }
    Ok(tries)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn x28_layout_matches_common_py() {
        let p = parse_mtd(X28_MTD).unwrap();
        assert_eq!(p.len(), 51);
        let lk_b = p.iter().find(|x| x.name == "lk_b").unwrap();
        assert_eq!((lk_b.offset, lk_b.image_name().as_str()), (0x1d80_0000, "mtd38-lk_b.bin"));
        assert_eq!(p.last().unwrap().offset + p.last().unwrap().size, 0x3fe8_0000);
        assert_eq!(p.iter().find(|x| x.name == "rootfs_a").unwrap().offset, 0x1360_0000);
    }

    #[test]
    fn bad_mtd_lines_are_refused() {
        for bad in ["mtd1: 00200000 00040000 \"x\"", "mtd0: zz 00040000 \"x\"", "mtd0: 1 2 \"a b\"", "junk"] {
            assert!(parse_mtd(&format!("dev:\n{bad}")).is_err(), "{bad}");
        }
    }

    #[test]
    fn a_tries_reads_all_copies() {
        let mut misc = vec![0xff; 0x100000];
        for n in 0..4 {
            let r = 0x800 + n * 0x40000;
            misc[r..r + 16].copy_from_slice(&[0, 0x41, 0x42, 0x30, 0xff, 0xff, 0xff, 0xff, 0x0f, n as u8, 0, 0, 0x0e, 0, 1, 0]);
        }
        assert_eq!(a_tries(&misc).unwrap(), [0, 1, 2, 3]);
        misc[0x40800] = 0xff;
        assert!(a_tries(&misc).is_err());
    }

    #[test]
    fn sums_and_hash() {
        let s = parse_sums("abc  images/mtd00-preloader.bin\nbad line\n");
        assert_eq!(s["images/mtd00-preloader.bin"], "abc");
        let dir = std::env::temp_dir().join(format!("x28flash-test-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("f"), b"abc").unwrap();
        assert_eq!(sha256_file(&dir.join("f")).unwrap(), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
        std::fs::remove_dir_all(dir).unwrap();
    }
}
