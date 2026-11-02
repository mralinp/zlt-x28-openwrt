//! Download agent: the loader file format and the V6 "xmlflash" protocol, as mtkclient 7cb40e7 speaks it
//! with the X28 patches from tools/recovery/setup_mtkclient.py. Read commands only: the command builder
//! below is the single place XML is made, and it has no write, erase, format, boot-mode or reboot command.
use std::io::Write;

use anyhow::{bail, ensure, Context, Result};

use crate::brom;
use crate::usb::Link;

/// Quectel T750 DA_BR.bin from the community X28 package (docs/RECOVERY.md); the only DA that reads this NAND.
pub const DA_SHA256: &str = "c3d9058aeb56373eaadc5868ce93198fb99a9cbf876a30f876714e9007d66d56";
pub const HW_CODE: u16 = 0x992;
const MAGIC: u32 = 0xFEEE_EEEF;
const DT_PROTOCOL_FLOW: u32 = 1;
const DT_MESSAGE: u32 = 2;

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Region {
    pub buf: u32,
    pub len: u32,
    pub addr: u32,
    pub sig_len: u32,
}

/// The two stages of the loader entry for `HW_CODE` in an MTK_DA_v6 file.
pub struct Loader {
    pub da1: Vec<u8>,
    pub da1_addr: u32,
    pub da1_sig: u32,
    /// Stage 2 without its signature, as mtkclient sends it.
    pub da2: Vec<u8>,
    pub da2_addr: u32,
}

fn le16(b: &[u8], at: usize) -> u16 {
    u16::from_le_bytes([b[at], b[at + 1]])
}

fn le32(b: &[u8], at: usize) -> u32 {
    u32::from_le_bytes(b[at..at + 4].try_into().unwrap())
}

/// mtkclient `DAconfig.parse_da_loader`: header 0x68, count at 0x68, entries of 0xDC from 0x6C.
pub fn parse_loader(file: &[u8]) -> Result<Loader> {
    ensure!(file.len() > 0x6C && file[..0x68].windows(9).any(|w| w == b"MTK_DA_v6"), "not an MTK_DA_v6 loader");
    let count = le32(file, 0x68) as usize;
    for i in 0..count.min(64) {
        let e = 0x6C + i * 0xDC;
        ensure!(e + 0xDC <= file.len(), "loader entry table is truncated");
        if le16(file, e + 2) != HW_CODE {
            continue;
        }
        let regions = le16(file, e + 18) as usize;
        ensure!(regions >= 3, "loader entry has {regions} regions, need 3");
        let region = |n: usize| {
            let r = e + 20 + n * 20;
            Region { buf: le32(file, r), len: le32(file, r + 4), addr: le32(file, r + 8), sig_len: le32(file, r + 16) }
        };
        let (r1, r2) = (region(1), region(2));
        let slice = |r: Region| -> Result<&[u8]> {
            let (start, end) = (r.buf as usize, r.buf as usize + r.len as usize);
            ensure!(end <= file.len() && r.sig_len < r.len, "loader region {r:x?} is out of bounds");
            Ok(&file[start..end])
        };
        let da2 = slice(r2)?;
        return Ok(Loader {
            da1: slice(r1)?.to_vec(),
            da1_addr: r1.addr,
            da1_sig: r1.sig_len,
            da2: da2[..da2.len() - r2.sig_len as usize].to_vec(),
            da2_addr: r2.addr,
        });
    }
    bail!("loader has no entry for hw code {HW_CODE:#x}")
}

/// The XML `<field>` text, or "" (mtkclient `get_field`).
pub fn field<'a>(xml: &'a str, name: &str) -> &'a str {
    let (open, close) = (format!("<{name}>"), format!("</{name}>"));
    xml.find(&open)
        .map(|s| s + open.len())
        .and_then(|s| xml[s..].find(&close).map(|e| &xml[s..s + e]))
        .unwrap_or("")
}

fn hex(s: &str) -> Result<u64> {
    u64::from_str_radix(s.trim().trim_start_matches("0x"), 16).with_context(|| format!("bad hex {s:?}"))
}

/// mtkclient `XMLCmd.create_cmd`.
fn cmd(name: &str, version: &str, arg: &str, adv: &str) -> String {
    let wrap = |tag: &str, body: &str| if body.is_empty() { String::new() } else { format!("<{tag}>{body}</{tag}>") };
    format!(
        "<?xml version=\"1.0\" encoding=\"utf-8\"?><da><version>{version}</version><command>CMD:{name}</command>{}{}</da>",
        wrap("arg", arg),
        wrap("adv", adv)
    )
}

// The fixed MEM:// addresses are host-buffer placeholders the DA echoes back; copied from mtkclient.
const HOST_CAPS: &str = "<host_capability>CMD:DOWNLOAD-FILE^1@CMD:FILE-SYS-OPERATION^1@CMD:PROGRESS-REPORT^1@CMD:UPLOAD-FILE^1@</host_capability>";
const RUNTIME: &str = "<checksum_level>NONE</checksum_level><battery_exist>AUTO-DETECT</battery_exist>\
<da_log_level>INFO</da_log_level><log_channel>UART</log_channel><system_os>LINUX</system_os>";
const HW_INFO_ARG: &str = "<target_file>MEM://0x7fe83c138700:0x200000</target_file>";
const USB_SPEED_ARG: &str = "<target_file>MEM://0x7fe8463ed240:0x40</target_file>";

#[derive(Debug, PartialEq)]
enum Reply {
    Start,
    End(String),
    /// CMD:DOWNLOAD-FILE: the DA wants `len` bytes from us in `packet`-sized pieces.
    Download { len: usize, packet: usize },
    /// CMD:UPLOAD-FILE: the DA is about to send us data.
    Upload,
}

#[derive(Debug, PartialEq)]
enum Sent {
    Done,
    Unsupported,
    Accepted,
    Download { len: usize, packet: usize },
}

#[derive(Debug, Default, PartialEq)]
pub struct Nand {
    pub page_size: u64,
    pub block_size: u64,
    pub spare_size: u64,
    pub total_size: u64,
}

pub struct Da<L: Link> {
    pub l: L,
    /// DT_MESSAGE log lines the DA sent.
    pub log: Vec<String>,
}

impl<L: Link> Da<L> {
    pub fn new(l: L) -> Self {
        Da { l, log: vec![] }
    }

    fn xsend(&mut self, payload: &[u8]) -> Result<()> {
        let mut hdr = MAGIC.to_le_bytes().to_vec();
        hdr.extend(DT_PROTOCOL_FLOW.to_le_bytes());
        hdr.extend((payload.len() as u32).to_le_bytes());
        self.l.write(&hdr)?;
        self.l.write(payload)
    }

    /// Strings go out NUL-terminated; mtkclient's "OK\0" therefore travels as OK\0\0.
    fn xsend_str(&mut self, s: &str) -> Result<()> {
        self.xsend(&[s.as_bytes(), b"\0"].concat())
    }

    fn ack(&mut self) -> Result<()> {
        self.xsend_str("OK\0")
    }

    fn ack_value(&mut self, n: usize) -> Result<()> {
        self.xsend_str(&format!("OK@{n:#x}\0"))
    }

    /// Next protocol-flow payload length; DA log messages in between are collected.
    fn xread(&mut self) -> Result<usize> {
        loop {
            let h = self.l.read(12)?;
            ensure!(le32(&h, 0) == MAGIC, "DA sent a packet with a wrong magic");
            let (kind, len) = (le32(&h, 4), le32(&h, 8) as usize);
            match kind {
                DT_PROTOCOL_FLOW => return Ok(len),
                DT_MESSAGE => {
                    let m = self.l.read(len)?; // 4-byte priority, then the text
                    self.log.push(String::from_utf8_lossy(&m[4.min(m.len())..]).trim_end_matches('\0').into());
                }
                _ => bail!("DA sent unknown packet type {kind}"),
            }
        }
    }

    fn response(&mut self) -> Result<String> {
        let n = self.xread()?;
        Ok(String::from_utf8_lossy(&self.l.read(n)?).trim_end_matches('\0').to_string())
    }

    fn response_data(&mut self) -> Result<Vec<u8>> {
        let n = self.xread()?;
        self.l.read(n)
    }

    /// mtkclient `get_command_result`, for the replies a read session meets.
    fn reply(&mut self) -> Result<Reply> {
        let mut data = self.response()?;
        if field(&data, "command") == "CMD:PROGRESS-REPORT" {
            self.ack()?;
            loop {
                let r = self.response()?;
                self.ack()?;
                if r == "OK!EOT" {
                    break;
                }
            }
            data = self.response()?;
        }
        match field(&data, "command") {
            "CMD:START" => {
                self.ack()?;
                Ok(Reply::Start)
            }
            "CMD:END" => {
                let result = field(&data, "result");
                let msg = field(&data, "message");
                Ok(Reply::End(if result != "OK" && !msg.is_empty() { msg } else { result }.to_string()))
            }
            "CMD:DOWNLOAD-FILE" => {
                // source_file is MEM://<host addr>:<length>
                let len = hex(field(&data, "source_file").rsplit(':').next().unwrap_or(""))? as usize;
                let packet = hex(field(&data, "packet_length"))? as usize;
                ensure!(packet > 0, "DA asked for packets of 0 bytes");
                self.ack()?;
                Ok(Reply::Download { len, packet })
            }
            "CMD:UPLOAD-FILE" => {
                self.ack()?;
                Ok(Reply::Upload)
            }
            _ => bail!("unexpected DA reply: {}", data.chars().take(200).collect::<String>()),
        }
    }

    fn expect_start(&mut self) -> Result<()> {
        match self.reply()? {
            Reply::Start => Ok(()),
            r => bail!("DA: expected CMD:START, got {r:?}"),
        }
    }

    /// END(OK) -> ack -> START, the tail of every command.
    fn finish(&mut self) -> Result<()> {
        match self.reply()? {
            Reply::End(r) if r == "OK" => {
                self.ack()?;
                self.expect_start()
            }
            r => bail!("DA: command failed: {r:?}"),
        }
    }

    /// mtkclient `send_command`. `noack` commands are followed by a data phase the caller runs.
    fn send(&mut self, xml: &str, noack: bool) -> Result<Sent> {
        self.xsend_str(xml)?;
        let resp = self.response()?;
        if resp == "ERR!UNSUPPORTED" {
            ensure!(matches!(self.reply()?, Reply::End(_)), "DA: no END after ERR!UNSUPPORTED");
            self.ack()?;
            self.expect_start()?;
            return Ok(Sent::Unsupported);
        }
        ensure!(resp == "OK", "DA refused {}: {resp}", field(xml, "command"));
        if noack {
            return Ok(Sent::Accepted);
        }
        match self.reply()? {
            Reply::End(r) if r == "OK" => {
                self.ack()?;
                self.expect_start()?;
                Ok(Sent::Done)
            }
            Reply::Download { len, packet } => Ok(Sent::Download { len, packet }),
            r => bail!("DA: {} failed: {r:?}", field(xml, "command")),
        }
    }

    /// Setup commands; this DA refuses some of them (logged on the unit), which is harmless.
    fn setup(&mut self, xml: &str) -> Result<()> {
        match self.send(xml, false)? {
            Sent::Done | Sent::Unsupported => Ok(()),
            s => bail!("DA: unexpected {s:?} for {}", field(xml, "command")),
        }
    }

    /// Send `data` for a CMD:DOWNLOAD-FILE (mtkclient `upload`, with the X28 patch: no extra ACK at the end).
    fn upload(&mut self, data: &[u8], packet: usize) -> Result<()> {
        self.ack_value(data.len())?;
        ensure!(self.response()? == "OK", "DA did not accept the upload length");
        for chunk in data.chunks(packet) {
            self.ack_value(0)?;
            let r = self.response()?;
            ensure!(r.contains("OK"), "DA upload: {}", field(&r, "message"));
            self.xsend(chunk)?;
            ensure!(self.response()?.contains("OK"), "DA upload chunk rejected");
        }
        self.finish()
    }

    /// Receive a CMD:UPLOAD-FILE payload into memory (mtkclient `download`).
    fn download(&mut self) -> Result<Vec<u8>> {
        let len = self.download_len()?;
        let mut data = Vec::with_capacity(len);
        while data.len() < len {
            data.extend(self.response_data()?);
        }
        self.ack()?;
        ensure!(data.len() == len, "DA sent {} bytes, announced {len}", data.len());
        Ok(data)
    }

    fn download_len(&mut self) -> Result<usize> {
        let r = self.response()?;
        let Some(n) = r.strip_prefix("OK@") else { bail!("DA: expected OK@<length>, got {r:?}") };
        let len = hex(n)? as usize;
        self.ack()?;
        ensure!(self.response()?.contains("OK"), "DA did not start the transfer");
        self.ack()?;
        Ok(len)
    }

    /// DA1 is running: set it up, load DA2, set up again (mtkclient `upload_da1` + `upload_da`).
    /// Skipped on purpose: GET-SYS-PROPERTY DA.SLA (refused here, and mtkclient then times out on a
    /// read; the X28 patch treats it as "off"), EMMC-CONTROL (eMMC only), and the DA extensions.
    pub fn boot(&mut self, loader: &Loader, host_info: &str) -> Result<()> {
        self.expect_start()?;
        self.setup(&cmd("SET-RUNTIME-PARAMETER", "1.1", RUNTIME, "<initialize_dram>YES</initialize_dram>"))?;
        self.setup(&cmd("HOST-SUPPORTED-COMMANDS", "1.0", HOST_CAPS, ""))?;
        self.setup(&cmd("NOTIFY-INIT-HW", "1.0", "", ""))?;
        self.setup(&cmd("SET-HOST-INFO", "1.0", &format!("<info>{host_info}</info>"), ""))?;
        let a = loader.da2_addr;
        let boot_to = format!(
            "<at_address>{a:#x}</at_address><jmp_address>{a:#x}</jmp_address><source_file>MEM://0x7fe83c09a04c:{:#x}</source_file>",
            loader.da2.len()
        );
        match self.send(&cmd("BOOT-TO", "1.0", &boot_to, ""), false)? {
            Sent::Download { len, packet } if len == loader.da2.len() => self.upload(&loader.da2, packet)?,
            s => bail!("DA: BOOT-TO answered {s:?}"),
        }
        self.setup(&cmd("HOST-SUPPORTED-COMMANDS", "1.0", HOST_CAPS, ""))?;
        self.setup(&cmd("NOTIFY-INIT-HW", "1.0", "", ""))?;
        self.setup(&cmd("CAN-HIGHER-USB-SPEED", "1.0", USB_SPEED_ARG, ""))
    }

    /// GET-HW-INFO; this DA leaves page_parity_size empty, which is not read here (X28 patch).
    pub fn nand_info(&mut self) -> Result<Nand> {
        ensure!(self.send(&cmd("GET-HW-INFO", "1.0", HW_INFO_ARG, ""), true)? == Sent::Accepted, "GET-HW-INFO refused");
        ensure!(self.reply()? == Reply::Upload, "GET-HW-INFO: no data");
        let xml = String::from_utf8_lossy(&self.download()?).to_string();
        self.finish()?;
        ensure!(field(&xml, "storage") == "NAND", "storage is {:?}, expected NAND", field(&xml, "storage"));
        Ok(Nand {
            page_size: hex(field(&xml, "page_size"))?,
            block_size: hex(field(&xml, "block_size"))?,
            spare_size: hex(field(&xml, "spare_size"))?,
            total_size: hex(field(&xml, "total_size"))?,
        })
    }

    /// READ-FLASH NAND-WHOLE (mtkclient `readflash` + `download_raw`). Returns bytes written to `out`.
    pub fn read_flash(&mut self, offset: u64, length: u64, out: &mut impl Write, mut progress: impl FnMut(u64)) -> Result<u64> {
        let arg = format!(
            "<partition>NAND-WHOLE</partition><offset>{offset:#x}</offset><length>{length:#x}</length><target_file>ROM_0</target_file>"
        );
        ensure!(self.send(&cmd("READ-FLASH", "1.0", &arg, ""), true)? == Sent::Accepted, "READ-FLASH refused");
        ensure!(self.reply()? == Reply::Upload, "READ-FLASH: no data");
        let len = self.download_len()? as u64;
        ensure!(len == length, "DA offers {len:#x} bytes, asked for {length:#x}");
        let (mut got, mut ended) = (0u64, false);
        while got < len {
            let chunk = self.response_data()?;
            ensure!(!chunk.is_empty() && got + chunk.len() as u64 <= len, "DA sent a bad chunk at {got:#x}");
            out.write_all(&chunk)?;
            got += chunk.len() as u64;
            progress(chunk.len() as u64);
            self.ack()?;
            // After each chunk the DA reports status; after the last one that is CMD:END.
            let s = self.response()?;
            if field(&s, "command") == "CMD:END" {
                ensure!(field(&s, "result") == "OK", "READ-FLASH ended early: {}", field(&s, "message"));
                ended = true;
            } else {
                ensure!(s.contains("OK"), "READ-FLASH chunk status: {s}");
            }
            self.ack()?;
            if ended {
                break;
            }
        }
        ensure!(got == len, "READ-FLASH stopped at {got:#x} of {len:#x}");
        let tail = if ended { self.expect_start() } else { self.finish() };
        tail?;
        Ok(got)
    }
}

/// Everything from the handshaken preloader to a DA ready for reads.
pub fn start<L: Link>(mut l: L, loader: &Loader, host_info: &str) -> Result<Da<L>> {
    brom::send_da(&mut l, loader.da1_addr, &loader.da1, loader.da1_sig)?;
    brom::jump_da(&mut l, loader.da1_addr)?;
    let mut da = Da::new(l);
    da.boot(loader, host_info)?;
    Ok(da)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::fake::Fake;

    fn pkt(kind: u32, payload: &[u8]) -> Vec<u8> {
        [&MAGIC.to_le_bytes()[..], &kind.to_le_bytes(), &(payload.len() as u32).to_le_bytes(), payload].concat()
    }

    fn s(text: &str) -> Vec<u8> {
        pkt(1, &[text.as_bytes(), b"\0"].concat())
    }

    fn xml(body: &str) -> Vec<u8> {
        s(&format!("<?xml version=\"1.0\" encoding=\"utf-8\"?><host><version>1.0</version>{body}</host>"))
    }

    fn start() -> Vec<u8> {
        xml("<command>CMD:START</command>")
    }

    fn end_ok() -> Vec<u8> {
        [xml("<command>CMD:END</command><result>OK</result>"), start()].concat()
    }

    fn upload_file() -> Vec<u8> {
        xml("<command>CMD:UPLOAD-FILE</command><arg><checksum>CHK_NO</checksum><info></info><target_file>ROM_0</target_file><packet_length>0x1000</packet_length></arg>")
    }

    /// Host packets after splitting header/payload pairs, as text where they are text.
    fn host_says(f: &Fake) -> Vec<String> {
        f.sent().chunks(2).map(|p| String::from_utf8_lossy(&p[1]).trim_end_matches('\0').to_string()).collect()
    }

    #[test]
    fn field_extracts_and_defaults() {
        assert_eq!(field("<a><b>x</b></a>", "b"), "x");
        assert_eq!(field("<page_parity_size></page_parity_size>", "page_parity_size"), "");
        assert_eq!(field("<a>", "b"), "");
    }

    #[test]
    fn commands_match_mtkclient_xml() {
        assert_eq!(cmd("NOTIFY-INIT-HW", "1.0", "", ""),
                   "<?xml version=\"1.0\" encoding=\"utf-8\"?><da><version>1.0</version><command>CMD:NOTIFY-INIT-HW</command></da>");
        assert!(cmd("SET-RUNTIME-PARAMETER", "1.1", RUNTIME, "<initialize_dram>YES</initialize_dram>")
            .ends_with("<system_os>LINUX</system_os></arg><adv><initialize_dram>YES</initialize_dram></adv></da>"));
    }

    #[test]
    fn ack_framing_is_byte_exact() {
        let mut da = Da::new(Fake::new(&[]));
        da.ack().unwrap();
        da.ack_value(0x2db10).unwrap();
        let sent = da.l.sent();
        assert_eq!(sent[0], [0xEF, 0xEE, 0xEE, 0xFE, 1, 0, 0, 0, 4, 0, 0, 0]);
        assert_eq!(sent[1], b"OK\0\0");
        assert_eq!(sent[3], b"OK@0x2db10\0\0");
    }

    #[test]
    fn unsupported_command_is_acked_and_resynced() {
        let dev = [s("ERR!UNSUPPORTED"), xml("<command>CMD:END</command><result>ERR!UNSUPPORTED</result>"), start()].concat();
        let mut da = Da::new(Fake::new(&[&dev]));
        assert_eq!(da.send(&cmd("CAN-HIGHER-USB-SPEED", "1.0", USB_SPEED_ARG, ""), false).unwrap(), Sent::Unsupported);
        assert_eq!(host_says(&da.l)[1..], ["OK", "OK"]);
        assert_eq!(da.l.unread(), 0);
    }

    #[test]
    fn log_messages_are_skipped() {
        let dev = [pkt(2, b"\x01\0\0\0hello\0"), s("OK"), end_ok()].concat();
        let mut da = Da::new(Fake::new(&[&dev]));
        assert_eq!(da.send(&cmd("NOTIFY-INIT-HW", "1.0", "", ""), false).unwrap(), Sent::Done);
        assert_eq!(da.log, ["hello"]);
    }

    #[test]
    fn upload_sends_no_extra_ack() {
        let data = vec![7u8; 0x1800];
        let mut dev = s("OK");
        for _ in 0..2 {
            dev.extend([s("OK"), s("OK")].concat());
        }
        dev.extend(end_ok());
        let mut da = Da::new(Fake::new(&[&dev]));
        da.upload(&data, 0x1000).unwrap();
        let said = host_says(&da.l);
        assert_eq!(said[0], "OK@0x1800");
        assert_eq!((said[1].as_str(), said[2].len(), said[4].len()), ("OK@0x0", 0x1000, 0x800));
        // after the last chunk: exactly one ACK for END and one for START, nothing before them
        assert_eq!(said[5..], ["OK", "OK"]);
        assert_eq!(da.l.unread(), 0);
    }

    #[test]
    fn hw_info_tolerates_empty_parity_field() {
        let info = b"<?xml version=\"1.0\" encoding=\"utf-8\"?><da_hw_info><storage>NAND</storage><nand><block_size>0x40000</block_size>\
<page_size>0x1000</page_size><spare_size>0x40</spare_size><total_size>0x3ff00000</total_size><page_parity_size></page_parity_size></nand></da_hw_info>";
        let dev = [s("OK"), upload_file(), s(&format!("OK@{:#x}", info.len())), s("OK"), pkt(1, info), end_ok()].concat();
        let mut da = Da::new(Fake::new(&[&dev]));
        let n = da.nand_info().unwrap();
        assert_eq!(n, Nand { page_size: 0x1000, block_size: 0x40000, spare_size: 0x40, total_size: 0x3ff00000 });
        assert_eq!(da.l.unread(), 0);
    }

    fn read_session(chunks: &[&[u8]]) -> Vec<u8> {
        let total: usize = chunks.iter().map(|c| c.len()).sum();
        let mut dev = [s("OK"), upload_file(), s(&format!("OK@{total:#x}")), s("OK")].concat();
        for (i, c) in chunks.iter().enumerate() {
            dev.extend(pkt(1, c));
            dev.extend(if i + 1 == chunks.len() { xml("<command>CMD:END</command><result>OK</result>") } else { s("OK") });
        }
        dev.extend(start());
        dev
    }

    #[test]
    fn read_flash_streams_all_chunks() {
        let dev = read_session(&[&[1; 0x1000], &[2; 0x1000], &[3; 0x10]]);
        let mut da = Da::new(Fake::new(&[&dev]));
        let (mut out, mut seen) = (vec![], 0);
        assert_eq!(da.read_flash(0x1d800000, 0x2010, &mut out, |n| seen += n).unwrap(), 0x2010);
        assert_eq!((out.len(), seen, out[0x1000], out[0x2000]), (0x2010, 0x2010, 2, 3));
        assert!(host_says(&da.l)[0].contains("<offset>0x1d800000</offset><length>0x2010</length>"));
        assert_eq!(da.l.unread(), 0);
    }

    #[test]
    fn read_flash_rejects_wrong_length_and_failed_end() {
        let dev = read_session(&[&[1; 0x10]]);
        let mut da = Da::new(Fake::new(&[&dev]));
        assert!(da.read_flash(0, 0x20, &mut vec![], |_| ()).is_err());

        let mut dev = [s("OK"), upload_file(), s("OK@0x20"), s("OK"), pkt(1, &[0; 0x10])].concat();
        dev.extend(xml("<command>CMD:END</command><result>ERR</result><message>ecc</message>"));
        let mut da = Da::new(Fake::new(&[&dev]));
        assert!(da.read_flash(0, 0x20, &mut vec![], |_| ()).is_err());
    }

    fn fake_loader() -> Vec<u8> {
        let mut f = vec![0u8; 0x400];
        f[..9].copy_from_slice(b"MTK_DA_v6");
        f[0x68] = 1;
        let e = 0x6C;
        f[e + 2..e + 4].copy_from_slice(&HW_CODE.to_le_bytes());
        f[e + 18] = 3;
        for (n, (buf, len, addr, sig)) in [(0, 0, 0, 0), (0x200u32, 0x80u32, 0x200000u32, 0x10u32), (0x300, 0x40, 0x40000000, 0x10)]
            .into_iter()
            .enumerate()
        {
            let r = e + 20 + n * 20;
            for (k, v) in [buf, len, addr, 0, sig].into_iter().enumerate() {
                f[r + k * 4..r + k * 4 + 4].copy_from_slice(&v.to_le_bytes());
            }
        }
        f
    }

    #[test]
    fn loader_regions_are_parsed_and_bounded() {
        let l = parse_loader(&fake_loader()).unwrap();
        assert_eq!((l.da1.len(), l.da1_addr, l.da1_sig, l.da2.len(), l.da2_addr), (0x80, 0x200000, 0x10, 0x30, 0x40000000));
        let mut bad = fake_loader();
        bad[0x6C + 20 + 20 + 7] = 0xff; // DA1 length beyond the file
        assert!(parse_loader(&bad).is_err());
        assert!(parse_loader(b"not a loader").is_err());
    }

    #[test]
    fn whole_boot_matches_the_unit_log_order() {
        let loader = parse_loader(&fake_loader()).unwrap();
        let refused = [s("ERR!UNSUPPORTED"), xml("<command>CMD:END</command><result>ERR!UNSUPPORTED</result>"), start()].concat();
        let ok = [s("OK"), end_ok()].concat();
        let download = xml("<command>CMD:DOWNLOAD-FILE</command><arg><checksum>CHK_NO</checksum><info>2nd-DA</info>\
<source_file>MEM://0x7fe83c09a04c:0x30</source_file><packet_length>0x1000</packet_length></arg>");
        let dev = [start(), refused.clone(), refused.clone(), ok.clone(), ok.clone(),
                   s("OK"), download, s("OK"), s("OK"), s("OK"), end_ok(),
                   refused.clone(), ok, refused].concat();
        let mut da = Da::new(Fake::new(&[&dev]));
        da.boot(&loader, "20261102T120000").unwrap();
        let commands: Vec<String> = host_says(&da.l).iter().map(|x| field(x, "command").to_string()).filter(|c| !c.is_empty()).collect();
        assert_eq!(commands, ["CMD:SET-RUNTIME-PARAMETER", "CMD:HOST-SUPPORTED-COMMANDS", "CMD:NOTIFY-INIT-HW", "CMD:SET-HOST-INFO",
                              "CMD:BOOT-TO", "CMD:HOST-SUPPORTED-COMMANDS", "CMD:NOTIFY-INIT-HW", "CMD:CAN-HIGHER-USB-SPEED"]);
        assert_eq!(da.l.unread(), 0);
    }

    /// Checks the real DA when X28FLASH_DA points at it (it is never committed).
    #[test]
    fn real_da_if_present() {
        let Ok(path) = std::env::var("X28FLASH_DA") else { return };
        let file = std::fs::read(path).unwrap();
        let l = parse_loader(&file).unwrap();
        // docs/RECOVERY.md and the unit's mtkclient log: DA1 at 0x200000, DA2 0x2db10 bytes at 0x40000000
        assert_eq!((l.da1_addr, l.da2.len(), l.da2_addr), (0x200000, 0x2db10, 0x40000000));
    }

    #[test]
    fn only_read_commands_exist() {
        // Phase 1 must stay read-only: an allowlist of every DA command and preloader opcode the crate can send.
        let files = [include_str!("da.rs"), include_str!("brom.rs"), include_str!("usb.rs"), include_str!("main.rs"),
                     include_str!("layout.rs")];
        let code: Vec<&str> = files.iter().map(|f| f.split("#[cfg(test)]\nmod tests").next().unwrap()).collect();
        let mut names: Vec<&str> = code.iter().flat_map(|f| f.split("cmd(\"").skip(1)).map(|c| &c[..c.find('"').unwrap()]).collect();
        names.sort();
        names.dedup();
        assert_eq!(names, ["BOOT-TO", "CAN-HIGHER-USB-SPEED", "GET-HW-INFO", "HOST-SUPPORTED-COMMANDS", "NOTIFY-INIT-HW",
                           "READ-FLASH", "SET-HOST-INFO", "SET-RUNTIME-PARAMETER"]);
        // XML is only built by cmd(): exactly one "<command>" template in the source.
        let all = code.concat();
        assert_eq!(all.matches("<command>").count(), 1);
        let opcodes: Vec<&str> = code[1].lines().filter(|l| l.starts_with("const ") && l.contains(": u8 = 0x")).collect();
        let values: Vec<String> = opcodes.iter().map(|l| l.rsplit("0x").next().unwrap().trim_end_matches(';').to_uppercase()).collect();
        assert_eq!(values, ["FD", "D8", "FE", "D7", "D5"]);
        // the only literal byte sent outside the consts is the handshake's lone 0xa0
        assert_eq!(code[1].matches("write(&[0x").count(), 1, "raw preloader opcode outside the consts");
    }
}
