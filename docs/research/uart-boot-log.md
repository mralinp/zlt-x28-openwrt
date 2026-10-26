# UART boot log: slot choice and signature checks

Findings for [#2](https://github.com/mralinp/zlt-x28-openwrt/issues/2) and
[#3](https://github.com/mralinp/zlt-x28-openwrt/issues/3). Source: a read-only capture of the console at
**921600 8N1** during a power-cycle of a live unit (2026-10-26). Nothing was sent to the board; the
adapter's TX was not connected. The raw log stays outside the repo; the excerpt below keeps only the boot-security
lines (numbers are line numbers in the raw capture) and was checked for MAC addresses, IMEI/IMSI and serials.

## What the log proves

| Question | Answer from the log |
|---|---|
| Which slot boots? | **Slot B.** `[QL_AB] metadata.slots[0].priority:14, slots[1].priority:15` then `[AB] ab_suffix: _b, ab_retry: 0, ab_boot_success: 1`; the kernel command line has `bootslot=b` and `ubi.mtd=42` (`rootfs_b`). |
| Is the A/B record in `misc` the real selector? | **Yes, consistent with it.** The 14/15 pair matches the bytes read from `misc` in [BOOT-FLOW.md](../BOOT-FLOW.md) (candidate 1). It does not prove the other two candidates are unused. |
| Does the boot chain verify signatures? | **Yes, in two places.** The preloader verifies `loader_ext_b`, `sspm_b`, `lk_b`, `tee_b` (ATF), `mcupm_b` and `pi_img_b` ("cert verify ... ok"). LK then verifies `boot_b` (the kernel image), the modem images (`md1rom`, `md1dsp`, `md1drdi`), the tinysys firmware and the `medhw-*` and `dpm*` blobs, and ends with **`[SBC] ROOTFS_SIG_VFY Success`** just before the kernel starts. |
| Is secure boot enforced? | **Not settled.** Every SBC line is followed by `sbc_en = 0`, and the log shows `SEC CFG is valid. Lock state is 1`, `sboot_state = 0x1`, `lock_state(default) = 0x4`, `[BLDR] Tool connection is unlocked`, `sec_boot_check=7`. These can mean "checks run and pass but are not enforced" or the opposite. Only booting a modified image from slot A (with a way back) settles it. |
| Boot timing | `bootprof.pl_t=1200` and `bootprof.lk_t=5860` are passed to the kernel (the unit is not stated in the log; they look like milliseconds, i.e. LK about 5.9 s). |

## Other things worth knowing

- The kernel command line still carries `initcall_debug=1 loglevel=8` (noisy boot logging) and a `ramoops`
  region at `0x42880000` with a 0x40000 console buffer. `ramoops` keeps crash logs across a warm reboot, which is
  the place to look after an unexplained reset (`/sys/fs/pstore`, empty so far).
- After boot the console prints a stream of vendor debug lines (`mtk_logger` SPM wake-ups, the PHY temperature
  once a second, the watchdog kick every 5 s). That is CPU and flash-log work we can remove later (#9).
- `lk2` does not exist (`[BLDR] lk2 partition not found`), and `[DOE_ENV] read_env_area fail` is printed and ignored.

## Not proven

- Whether a rootfs or boot image signed with another key (or unsigned) would boot, and what a failed check does
  (refuse, fall back to the other slot, or only log). This is the question that gates a custom image.
- Whether `ab_retry` counting makes a failed boot fall back to slot A. The log shows the retry counter at 0 after
  a good boot, nothing more.
- Which pad of the 3-hole footprint in [RECOVERY.md](../RECOVERY.md#uart-debug-console-2-in-progress) carries
  TX and what the logic level is. The capture worked through the owner's adapter and level shifting; those wiring
  details were not recorded in this session and should be added when known.

## Excerpt (boot-security lines only)

```text
  302: [QL_AB] metadata.slots[0].priority:14,metadata.slots[1].priority:15.
  303: [AB] ab_suffix: _b, ab_retry: 0, ab_boot_success: 1
  304: [AB] ab_up_type: 0
  314: [SEC] reading seccfg
  318: [LIB] SEC CFG 'v4' exists
  320: [LIB] SEC CFG is valid. Lock state is 1
  324: [SEC_POLICY] sboot_state = 0x1
  325: [SEC_POLICY] lock_state(default) = 0x4
  327: sbc_en = 0
  329: [SBC] cert verify, part = loader_ext_b, img = loader_ext_dram...ok
  672: #T#seclib_brom_meta_mode=0
  673: [BLDR] Tool connection is unlocked
  694: #T#sec_boot_check=7
  713: [SEC_POLICY] sboot_state = 0x1
  714: [SEC_POLICY] lock_state(default) = 0x4
  721: sbc_en = 0
  723: [SBC] cert verify, part = sspm_b, img = tinysys-sspm...ok
  734: [BLDR] lk2 partition not found
  735: [BLDR] lk active = 0, lk2 active = 0
  736: [BLDR] Loading LK Partition...
  739: [SEC_POLICY] sboot_state = 0x1
  740: [SEC_POLICY] lock_state(default) = 0x4
  747: sbc_en = 0
  749: [SBC] cert verify, part = lk_b, img = lk...ok
  760: [SEC_POLICY] sboot_state = 0x1
  761: [SEC_POLICY] lock_state(default) = 0x4
  768: sbc_en = 0
  770: [SBC] cert verify, part = tee_b, img = atf...ok
  783: [SEC_POLICY] sboot_state = 0x1
  784: [SEC_POLICY] lock_state(default) = 0x4
  791: sbc_en = 0
  793: [SBC] cert verify, part = mcupm_b, img = tinysys-mcupm-RV33_A...ok
  830: [SEC_POLICY] sboot_state = 0x1
  831: [SEC_POLICY] lock_state(default) = 0x4
  838: sbc_en = 0
  840: [SBC] cert verify, part = pi_img_b, img = pi_img...ok
  898: BOOT_MODE: 0
  941: [BLDR] Others, jump to ATF
  943: [BLDR] jump to 0x44000000
  954: [SEC_INIT] sec_func_init -- fail to search rominfo
  957: [SBC] lk_main_dtb cert chain vfy pass
  960: [SBC] image lk_main_dtb auth pass
  964: [SBC] boot_b cert chain vfy pass
  966: [SBC] image mt6890 auth pass
  969: [SBC] spmfw cert chain vfy pass
  971: [SBC] image spmfw auth pass
  975: [SBC] md1rom cert chain vfy pass
  977: [SBC] image md1rom auth pass
  980: [SBC] md1dsp cert chain vfy pass
  982: [SBC] image md1dsp auth pass
  985: [SBC] md1drdi cert chain vfy pass
  987: [SBC] image md1drdi auth pass
  990: [SBC] tinysys-medmcu-RV33_A cert chain vfy pass
  992: [SBC] image tinysys-medmcu-RV33_A auth pass
  995: [SBC] medhw-gc0-pm cert chain vfy pass
  997: [SBC] image medhw-gc0-pm auth pass
 1000: [SBC] medhw-gc0-dm cert chain vfy pass
 1002: [SBC] image medhw-gc0-dm auth pass
 1005: [SBC] medhw-gc1-pm cert chain vfy pass
 1007: [SBC] image medhw-gc1-pm auth pass
 1010: [SBC] medhw-gc1-dm cert chain vfy pass
 1012: [SBC] image medhw-gc1-dm auth pass
 1015: [SBC] medhw-gc2-pm cert chain vfy pass
 1017: [SBC] image medhw-gc2-pm auth pass
 1020: [SBC] medhw-gc2-dm cert chain vfy pass
 1022: [SBC] image medhw-gc2-dm auth pass
 1025: [SBC] dpmpm cert chain vfy pass
 1027: [SBC] image dpmpm auth pass
 1030: [SBC] dpmdm cert chain vfy pass
 1032: [SBC] image dpmdm auth pass
 1034: [SBC] ROOTFS_SIG_VFY Success
 1069: Kernel command line (whitespace collapsed):
        console=tty0 console=ttyS0,921600n1 root=/dev/ubiblock0_0 rootfstype=squashfs ubi.mtd=42 init=/etc/preinit loglevel=8 androidboot.selinux=permissive androidboot.hardware=mt6890 initcall_debug=1 ramoops.mem_address=0x42880000 ramoops.mem_size=0xe0000 ramoops.pmsg_size=0x10000 ramoops.console_size=0x40000 mtk_printk_ctrl.disable_uart=0 bootslot=b androidboot.hardware=mt6890 bootprof.pl_t=1200 bootprof.logo_t=0 bootprof.lk_t=5860
```

## Reproduce

Read-only, with a 3.3 V USB-serial adapter and a level path that never drives the board:

```text
board TX pad -> level shifter (1.8 V side) -> adapter RX      GND common      adapter TX left unconnected
```

A stdlib-only capture (opens the port read-only, so nothing can be written; macOS, adjust the device path):

```python
import os, sys, time, termios, select
dev, out, secs = "/dev/cu.usbserial-0001", "boot.log", 300
fd = os.open(dev, os.O_RDONLY | os.O_NOCTTY | os.O_NONBLOCK)
a = termios.tcgetattr(fd)
a[0] = a[1] = a[3] = 0
a[2] = (a[2] & ~(termios.CSIZE | termios.PARENB | termios.CSTOPB | termios.CRTSCTS)) | termios.CS8 | termios.CREAD | termios.CLOCAL
a[4] = a[5] = 921600
a[6][termios.VMIN] = 0; a[6][termios.VTIME] = 0
termios.tcsetattr(fd, termios.TCSANOW, a)
t0 = time.time()
with open(out, "wb") as f:
    while time.time() - t0 < secs:
        if select.select([fd], [], [], 0.5)[0]:
            f.write(os.read(fd, 4096)); f.flush()
```

Start it, then power-cycle the board: the preloader and LK print in the first seconds.
