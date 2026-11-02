//! Preloader/BROM commands, as mtkclient 7cb40e7 sends them (`Port.run_handshake`, `mtk_preloader.py`).
//! Only read-only queries plus SEND_DA/JUMP_DA (RAM). No register or memory writes exist here.
use std::thread::sleep;
use std::time::Duration;

use anyhow::{bail, ensure, Result};

use crate::usb::{Link, MPS};

const GET_HW_CODE: u8 = 0xFD;
const GET_TARGET_CONFIG: u8 = 0xD8;
const GET_BL_VER: u8 = 0xFE;
const SEND_DA: u8 = 0xD7;
const JUMP_DA: u8 = 0xD5;

pub struct Target {
    pub hw_code: u16,
    pub hw_ver: u16,
    /// Bit 0 SBC, 1 SLA, 2 DAA, 4 root cert, 5/6 memory read/write auth. The X28 reports 0.
    pub config: u32,
    pub brom: bool,
}

fn u16be(l: &mut impl Link) -> Result<u16> {
    let b = l.read(2)?;
    Ok(u16::from_be_bytes([b[0], b[1]]))
}

fn u32be(l: &mut impl Link) -> Result<u32> {
    let b = l.read(4)?;
    Ok(u32::from_be_bytes([b[0], b[1], b[2], b[3]]))
}

fn echo(l: &mut impl Link, data: &[u8]) -> Result<()> {
    l.write(data)?;
    let got = l.read(data.len())?;
    ensure!(got == data, "preloader did not echo {data:02x?} (got {got:02x?})");
    Ok(())
}

/// Start sequence a0 0a 50 05, each byte answered by its complement.
pub fn handshake(l: &mut impl Link, brom_pid: bool) -> Result<()> {
    if !brom_pid {
        l.write(&[0xa0])?; // mtkclient sends a lone first byte to preloader ports
    }
    for _ in 0..5 {
        if [0xa0u8, 0x0a, 0x50, 0x05]
            .iter()
            .all(|&b| l.write(&[b]).is_ok() && l.read(1).map(|r| r[0] == !b).unwrap_or(false))
        {
            return Ok(());
        }
        l.drain();
    }
    bail!("no handshake: is this the modem's preloader port, freshly powered on?")
}

pub fn identify(l: &mut impl Link) -> Result<Target> {
    echo(l, &[GET_HW_CODE])?;
    let v = u32be(l)?;
    echo(l, &[GET_TARGET_CONFIG])?;
    let config = u32be(l)?;
    let status = u16be(l)?;
    ensure!(status <= 0xff, "GET_TARGET_CONFIG failed: status {status:#06x}");
    l.write(&[GET_BL_VER])?;
    let brom = l.read(1)?[0] == GET_BL_VER; // BROM echoes the command, the preloader answers its version
    Ok(Target { hw_code: (v >> 16) as u16, hw_ver: v as u16, config, brom })
}

/// XOR of little-endian 16-bit words, zero-padded to even length (mtkclient `prepare_data`).
pub fn checksum(data: &[u8]) -> u16 {
    data.chunks(2).fold(0, |x, w| x ^ u16::from_le_bytes([w[0], *w.get(1).unwrap_or(&0)]))
}

/// Upload DA stage 1 (signature included) into SRAM at `addr`.
pub fn send_da(l: &mut impl Link, addr: u32, data: &[u8], sig_len: u32) -> Result<()> {
    echo(l, &[SEND_DA])?;
    echo(l, &addr.to_be_bytes())?;
    echo(l, &(data.len() as u32).to_be_bytes())?;
    echo(l, &sig_len.to_be_bytes())?;
    let status = u16be(l)?;
    ensure!(status <= 0xff, "SEND_DA refused: status {status:#06x} (0x1d0d means SLA is on)");
    let mut pos = 0;
    for chunk in data.chunks(MPS) {
        l.write(chunk)?;
        pos += chunk.len();
        if pos % 0x2000 == 0 {
            l.write(&[])?;
        }
    }
    l.write(&[])?;
    sleep(Duration::from_millis(120));
    let (sum, status) = (u16be(l)?, u16be(l)?);
    ensure!(sum == 0 || sum == checksum(data), "DA upload checksum mismatch ({sum:#06x} vs {:#06x})", checksum(data));
    ensure!(status <= 0xff, "DA upload failed: status {status:#06x}");
    Ok(())
}

pub fn jump_da(l: &mut impl Link, addr: u32) -> Result<()> {
    echo(l, &[JUMP_DA])?;
    l.write(&addr.to_be_bytes())?;
    let back = u32be(l)?;
    ensure!(back == addr, "JUMP_DA answered {back:#x}, expected {addr:#x}");
    let status = u16be(l)?;
    ensure!(status == 0, "JUMP_DA failed: status {status:#06x}");
    sleep(Duration::from_millis(100));
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::fake::Fake;

    #[test]
    fn handshake_and_identify_match_mtkclient_bytes() {
        let mut f = Fake::new(&[
            &[0x5f, 0xf5, 0xaf, 0xfa],             // complements of a0 0a 50 05
            &[0xfd], &[0x09, 0x92, 0xca, 0x01],    // hw code 0x992, hw ver 0xca01
            &[0xd8], &[0, 0, 0, 0], &[0, 0],       // target config 0, status 0
            &[0x05],                                // preloader version (not an echo of 0xfe)
        ]);
        handshake(&mut f, false).unwrap();
        let t = identify(&mut f).unwrap();
        assert_eq!((t.hw_code, t.hw_ver, t.config, t.brom), (0x992, 0xca01, 0, false));
        assert_eq!(f.sent(), vec![vec![0xa0], vec![0xa0], vec![0x0a], vec![0x50], vec![0x05],
                                  vec![0xfd], vec![0xd8], vec![0xfe]]);
    }

    #[test]
    fn handshake_gives_up_on_wrong_device() {
        let mut f = Fake::new(&[&[0u8; 32]]);
        assert!(handshake(&mut f, true).is_err());
    }

    #[test]
    fn send_da_chunks_zlps_and_checks_sum() {
        let da = vec![0x11u8; 0x2000 + 3];
        let sum = checksum(&da).to_be_bytes();
        let mut f = Fake::new(&[&[0xd7], &[0, 0x20, 0, 0], &[0, 0, 0x20, 3], &[0, 0, 1, 0], &[0, 0],
                                &sum, &[0, 0]]);
        send_da(&mut f, 0x200000, &da, 0x100).unwrap();
        let sent = f.sent();
        let zlps: Vec<usize> = sent.iter().enumerate().filter(|(_, w)| w.is_empty()).map(|(i, _)| i).collect();
        assert_eq!(zlps, vec![4 + 16, 4 + 18]); // after 0x2000 bytes (16 packets) and at the end
        assert!(sent[4..].iter().all(|w| w.len() <= MPS));

        let mut f = Fake::new(&[&[0xd7], &[0, 0x20, 0, 0], &[0, 0, 0, 2], &[0, 0, 1, 0], &[0, 0], &[0x12, 0x34], &[0, 0]]);
        assert!(send_da(&mut f, 0x200000, &[1, 2], 0x100).is_err());
    }

    #[test]
    fn send_da_stops_when_sla_is_required() {
        let mut f = Fake::new(&[&[0xd7], &[0, 0x20, 0, 0], &[0, 0, 0, 2], &[0, 0, 1, 0], &[0x1d, 0x0d]]);
        assert!(send_da(&mut f, 0x200000, &[1, 2], 0x100).is_err());
        assert_eq!(f.sent().len(), 4); // nothing uploaded
    }

    #[test]
    fn checksum_pads_odd_length() {
        assert_eq!(checksum(&[0x01, 0x02, 0x03]), 0x0201 ^ 0x0003);
    }
}
