//! Scripted link for host tests: replays device bytes, records every host transfer.
use std::collections::VecDeque;

use anyhow::{bail, Result};

use crate::usb::Link;

pub struct Fake {
    rx: VecDeque<u8>,
    tx: Vec<Vec<u8>>,
}

impl Fake {
    pub fn new(device_says: &[&[u8]]) -> Fake {
        Fake { rx: device_says.concat().into(), tx: vec![] }
    }

    pub fn sent(&self) -> Vec<Vec<u8>> {
        self.tx.clone()
    }

    pub fn unread(&self) -> usize {
        self.rx.len()
    }
}

impl Link for Fake {
    fn write(&mut self, data: &[u8]) -> Result<()> {
        self.tx.push(data.to_vec());
        Ok(())
    }

    fn read(&mut self, n: usize) -> Result<Vec<u8>> {
        if self.rx.len() < n {
            bail!("USB timeout");
        }
        Ok(self.rx.drain(..n).collect())
    }

    fn drain(&mut self) {
        self.rx.clear();
    }
}
