//! USB transport: the preloader's CDC data interface through nusb (no libusb).
use std::collections::VecDeque;
use std::time::Duration;

use anyhow::{bail, Context, Result};
use nusb::transfer::{Buffer, Bulk, ControlOut, ControlType, In, Out, Recipient, TransferError};
use nusb::{DeviceInfo, Endpoint, Interface, MaybeFuture};

pub const VID: u16 = 0x0e8d;
pub const PID_PRELOADER: u16 = 0x2000;
pub const PID_BROM: u16 = 0x0003;
/// Bulk max packet size of the X28 preloader (0x200 in its descriptors); the preloader upload is chunked by it.
pub const MPS: usize = 512;

/// What the protocol code needs from a link; tests implement it with a scripted fake.
pub trait Link {
    /// One bulk OUT transfer; an empty slice sends a zero-length packet.
    fn write(&mut self, data: &[u8]) -> Result<()>;
    /// Exactly `n` bytes from the bulk IN stream.
    fn read(&mut self, n: usize) -> Result<Vec<u8>>;
    /// Drop anything pending on the IN side (handshake retry).
    fn drain(&mut self) {}
    fn set_timeout(&mut self, _t: Duration) {}
}

pub fn find() -> Option<DeviceInfo> {
    nusb::list_devices().wait().ok()?.find(|d| {
        d.vendor_id() == VID && matches!(d.product_id(), PID_PRELOADER | PID_BROM)
    })
}

pub struct Usb {
    _comm: Interface,
    out: Endpoint<Bulk, Out>,
    inp: Endpoint<Bulk, In>,
    buf: VecDeque<u8>,
    timeout: Duration,
}

impl Usb {
    pub fn open(info: &DeviceInfo) -> Result<Usb> {
        let dev = info.open().wait().context("cannot open the USB device (permissions? see --help)")?;
        // Interface 0 is CDC control, 1 is CDC data with bulk 0x01/0x81 (descriptors logged on the unit).
        let comm = dev.detach_and_claim_interface(0).wait().context("cannot claim USB interface 0")?;
        let data = dev.detach_and_claim_interface(1).wait().context("cannot claim USB interface 1")?;
        // Same CDC setup as mtkclient: 921600 8N1, then RTS. It ignores failures, so do we.
        let line = [0x00, 0x10, 0x0e, 0x00, 0, 0, 8];
        for (request, value, payload) in [(0x20u8, 0u16, &line[..]), (0x22, 2, &[][..])] {
            let _ = comm
                .control_out(
                    ControlOut { control_type: ControlType::Class, recipient: Recipient::Interface,
                                 request, value, index: 0, data: payload },
                    Duration::from_secs(1),
                )
                .wait();
        }
        Ok(Usb {
            out: data.endpoint::<Bulk, Out>(0x01)?,
            inp: data.endpoint::<Bulk, In>(0x81)?,
            _comm: comm,
            buf: VecDeque::new(),
            timeout: Duration::from_millis(500),
        })
    }
}

fn check(status: Result<(), TransferError>) -> Result<()> {
    match status {
        Ok(()) => Ok(()),
        Err(TransferError::Cancelled) => bail!("USB timeout"),
        Err(e) => bail!("USB error: {e}"),
    }
}

impl Link for Usb {
    fn write(&mut self, data: &[u8]) -> Result<()> {
        let c = self.out.transfer_blocking(Buffer::from(data.to_vec()), self.timeout);
        check(c.status)?;
        if c.actual_len != data.len() {
            bail!("USB short write: {} of {} bytes", c.actual_len, data.len());
        }
        Ok(())
    }

    fn read(&mut self, n: usize) -> Result<Vec<u8>> {
        while self.buf.len() < n {
            // Ask for exactly what is missing (rounded to whole packets) so a transfer ends when the
            // device stops sending and waits for us, like mtkclient's sized reads.
            let want = (n - self.buf.len()).div_ceil(MPS) * MPS;
            let c = self.inp.transfer_blocking(Buffer::new(want), self.timeout);
            check(c.status)?;
            self.buf.extend(&c.buffer[..c.actual_len]);
        }
        Ok(self.buf.drain(..n).collect())
    }

    fn drain(&mut self) {
        self.buf.clear();
        let _ = self.inp.transfer_blocking(Buffer::new(MPS), Duration::from_millis(50));
    }

    fn set_timeout(&mut self, t: Duration) {
        self.timeout = t;
    }
}
