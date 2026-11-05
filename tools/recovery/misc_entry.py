#!/usr/bin/env python3
"""Guarded misc entry for units other than the first (#327): select slot A on this unit's own record, over USB.

Same gates as slot_entry.py misc (receipts, typed phrase, neighbour guards, one write, no retry or reboot), with the pins and
the A-selection computed from the unit's verified backup instead of the first unit's constants. It lives in its own file on
purpose: slot_entry.py and slot_session.py are hashed into every receipt, so editing them would invalidate the rootfs_a write
receipt a misc session consumes. Nothing here changes those files, and this file is not in that hash. The first run on a unit
is `identical`, which rewrites misc with its own bytes and shows whether the download agent acknowledges the write.

The USB route to misc is unproven (block writes were never acknowledged on the first unit, docs/TESTING.md 28). Merging this
file approves nothing: the typed phrase attests that the owner approved this exact target, mode and image.
"""
import argparse
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

import slot_entry as entry
import slot_session as session
from common import DEFAULT_BACKUP, PRIVATE, VENDOR_DA, ensure_venv, sha256_file
from restore_entry import check_uart, check_unit, claim_restore, open_da, save
from write_verify import active_slot

digest = session.digest


def a_selected(record):
    """The vendor's change_slot_info "_b" (docs/research/slot-selection.md) on a stock B-selected record: A priority 0f, tries 03,
    success 00, flag 00; B priority 0e with its own tries, success and flag kept."""
    if len(record) != 16 or not session.MISC_B_SELECTED.fullmatch(record):
        raise ValueError('misc record is not the stock B-selected record')
    return record[:8] + bytes([0x0f, 0x03, 0x00, 0x00, 0x0e]) + record[13:]


def misc_candidate(original):
    """The four-copy A selection of this unit's own misc; every other byte stays."""
    out = bytearray(original)
    for off in session.MISC_COPIES:
        out[off:off + 16] = a_selected(original[off:off + 16])
    return bytes(out)


def validate_misc(original, candidate):
    try:
        expected = misc_candidate(original)
    except ValueError:
        raise ValueError('misc original is not the expected B-selected record') from None
    if expected != candidate:
        raise ValueError('misc candidate is not exactly the four-copy A selection')


def unit_misc_spec(rootfs_a_sha, pins, candidate_sha):
    """slot_session.misc_spec with this unit's pins: select A (write) or return to B (restore)."""
    if len(rootfs_a_sha) != 64 or rootfs_a_sha in (pins['rootfs_a'], pins['rootfs_b']):
        raise ValueError('misc session needs the approved new rootfs_a hash')
    common = session.common_guards(pins)
    rootfs_a = ('rootfs_a', 0x13600000, 0x4000000)
    # After a fallback, stock B's ab_image_sync may have copied B over A: rootfs_a then equals rootfs_b.
    return session.Spec('misc', 0x700000, 0x100000, pins['misc'], (*common, (*rootfs_a, rootfs_a_sha)), validate_misc, candidate_sha,
                        (*common, (*rootfs_a, (rootfs_a_sha, pins['rootfs_a'], pins['rootfs_b']))))


def phrase(spec, mode, rootfs_a_sha, same_disk, no_ssh, no_uart, original):
    """slot_entry's phrase minus its BROM-ROUTE-PROVEN claim, which is not true for this route: the USB route to misc is unproven.
    Names the A flag change when this unit's record has one, so the owner types it."""
    text = entry.phrase(spec, mode, rootfs_a_sha, same_disk, no_ssh, no_uart).replace('BROM-ROUTE-PROVEN', 'MISC-USB-ROUTE-UNPROVEN')
    flag = original[session.MISC_COPIES[0] + 11]
    return text.replace(' MISC-USB-ROUTE-UNPROVEN', f' MISC-USB-ROUTE-UNPROVEN A-FLAG-{flag:02X}-TO-00' if flag else ' MISC-USB-ROUTE-UNPROVEN')


def load(backup, loader, candidate_dir):
    """(by_name, table, original, candidate, spec, rootfs_spec, identity). Loading as rootfs_a identical reuses slot_entry's
    identity (unit, host, DA, tools, rootfs_a) and its checks of the backup, the DA and the approved image."""
    by_name, table, _, _, rootfs_spec, identity, _ = entry.load_inputs(backup, loader, 'rootfs_a', 'identical', candidate_dir)
    images = {n: Path(by_name[n]['image']).read_bytes() for n in ('misc', 'rootfs_a', 'rootfs_b', 'boot_para')}
    if any(digest(images[n]) != by_name[n]['sha256'] for n in images):  # the bytes verified_backup hashed, not a second read
        raise ValueError('backup image changed after verification')
    pins = session.unit_pins(images)
    original = images['misc']
    candidate = misc_candidate(original)
    spec = unit_misc_spec(identity['rootfs_a'], pins, digest(candidate))
    for name, addr, size, sha in spec.guards:  # the same identity checks slot_entry makes for its guards
        p = by_name[name]
        if name == 'rootfs_b':
            if p['offset'] != addr or size > p['size'] or digest(Path(p['image']).read_bytes()[:size]) != sha:
                raise ValueError('prefix guard identity mismatch: ' + name)
            continue
        if (p['offset'], p['size']) != (addr, size) or (isinstance(sha, str) and name != 'rootfs_a' and p['sha256'] != sha):
            raise ValueError('guard identity mismatch: ' + name)
    if (by_name['misc']['offset'], by_name['misc']['size']) != (spec.addr, spec.size):
        raise ValueError('target identity mismatch')
    return by_name, table, original, candidate, spec, rootfs_spec, {**identity, 'target': 'misc', 'original': spec.original_sha, 'candidate': spec.candidate_sha}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('mode', choices=('identical', 'write', 'restore'))
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--backup', type=Path, default=DEFAULT_BACKUP)
    ap.add_argument('--loader', type=Path, default=VENDOR_DA)
    ap.add_argument('--candidate-dir', type=Path, required=True, help='package_ubi output of the rootfs_a image now on rootfs_a')
    ap.add_argument('--backup-copy', type=Path, help='verified second complete-captured-partitions.tar')
    ap.add_argument('--uart-log', type=Path)
    ap.add_argument('--no-uart', action='store_true', help='no UART log; the way back is a USB restore from the backup')
    ap.add_argument('--no-ssh', action='store_true', help='no live SSH slot check; the USB read of misc must equal the backup instead')
    ap.add_argument('--prior-identical', type=Path)
    ap.add_argument('--prior-rootfs-a', type=Path, help='verified rootfs_a write run')
    ap.add_argument('--resume', type=Path, help='stopped or finished misc write run, restore mode only')
    args = ap.parse_args()
    wanted = entry.PRIOR[('misc', args.mode)]
    for flag, *_ in wanted:
        if getattr(args, flag) is None:
            raise ValueError(f'misc {args.mode} requires --{flag.replace("_", "-")}')
    for flag in ('prior_identical', 'prior_rootfs_a', 'resume'):
        if getattr(args, flag) is not None and flag not in [w[0] for w in wanted]:
            raise ValueError(f'--{flag.replace("_", "-")} is not valid for misc {args.mode}')
    if args.no_uart and args.uart_log:
        raise ValueError('--no-uart excludes --uart-log')
    if args.no_ssh and args.mode == 'restore':
        raise ValueError('--no-ssh is for identical/write; restore does not use the live-slot check')
    backup, loader = args.backup.resolve(strict=True), args.loader.resolve(strict=True)
    parts, table, original, candidate, spec, rootfs_spec, identity = load(backup, loader, args.candidate_dir.resolve(strict=True))
    rootfs_a_sha = identity['rootfs_a']
    if args.mode == 'write':
        spec.validate(original, candidate)  # refuse a bad candidate before any connection or claim
    specs = {'rootfs_a': rootfs_spec, 'misc': spec}
    priors = {}
    for flag, target, mode, verified in wanted:
        # Every prior is bound to this unit, host, tools and the same approved rootfs_a image (from the manifest, not a receipt).
        expect = {**identity, 'target': target, 'original': specs[target].original_sha, 'candidate': specs[target].candidate_sha}
        priors[flag] = entry.load_prior(getattr(args, flag), expect, specs[target], mode, verified)
    print(f'{args.mode}: misc only at {spec.addr:#x}, {spec.size:#x} bytes; candidate {spec.candidate_sha[:12]}; no reboot or retry')
    print(f'record per copy: {original[session.MISC_COPIES[0]:session.MISC_COPIES[0] + 16].hex()} -> {candidate[session.MISC_COPIES[0]:session.MISC_COPIES[0] + 16].hex()}'
          + ('' if args.mode != 'identical' else '  (identical writes the unchanged record)'))
    print('misc_entry.py sha256 ' + sha256_file(Path(__file__)))
    if not args.write:
        print('OFFLINE DRY RUN: no SSH, hardware import, USB command or write; execution gates not checked')
        return
    ensure_venv()
    if not args.backup_copy or not (args.uart_log or args.no_uart):
        raise ValueError('--write requires --backup-copy and --uart-log (or --no-uart)')
    copy, uart = args.backup_copy.resolve(strict=True), args.uart_log.resolve(strict=True) if args.uart_log else None
    archive = backup / 'complete-captured-partitions.tar'
    expected_archive = (backup / 'ARCHIVE.sha256').read_text().split()[0]
    if copy.samefile(archive) or sha256_file(archive) != expected_archive or sha256_file(copy) != expected_archive:
        raise ValueError('second archive copy is missing, same file, or invalid')
    same_disk = copy.stat().st_dev == archive.stat().st_dev
    if uart:
        check_uart(uart)
    else:
        print('NO UART: no boot log will exist. If the unit does not boot nothing can be diagnosed; the way back is a USB restore from your backup.')
    if args.no_ssh:
        print('NO SSH: the live slot is not confirmed by the running system; it rests on the USB read of misc matching your backup.')
    elif args.mode != 'restore' and active_slot(table) != 'b':
        raise ValueError('live SSH must confirm B and exact full layout')
    probe_dir = PRIVATE / 'usb-probe'
    probe_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    if shutil.disk_usage(probe_dir).free < 1024 * 1024 * 1024:
        raise ValueError('less than 1 GiB free for captures and sources')
    if not sys.stdin.isatty():
        raise ValueError('typed confirmation needs an interactive terminal')
    expected_phrase = phrase(spec, args.mode, rootfs_a_sha, same_disk, args.no_ssh, args.no_uart, original)
    print(('Confirm stable power' if args.no_uart else 'Confirm UART RX capture continues, stable power') + ', and no stock upgrade/FOTA pending.')
    print('misc is the LIVE slot selector and is rewritten whole (1 MiB): a power or USB loss can leave no valid record.')
    print('The USB route to misc is unproven: block writes were never acknowledged on the first unit. If a block is erased and its write is')
    print('not acknowledged, that copy is blank or partial, and restore uses the same USB path, so it can fail the same way. The last resort')
    print('is then BROM or test-point access. Treat any unacknowledged write in `identical` as a stop before `write`. Merging a PR is not approval.')
    if same_disk:
        print('WARNING: backup copy is on the same filesystem; host disk loss would lose both copies.')
    if input(f'Type exactly {expected_phrase!r} to attest those checks and authorize this operation: ') != expected_phrase:
        raise ValueError('operation not confirmed')
    run = Path(tempfile.mkdtemp(prefix=f'slot-misc-{args.mode}-', dir=probe_dir)).resolve()
    receipt = {'schema': 2, 'run': str(run), 'target': 'misc', 'mode': args.mode, 'status': 'STARTED', 'identity': identity,
               'created': time.time(), 'uart': str(uart) if uart else None, 'no_uart': args.no_uart, 'no_ssh': args.no_ssh,
               'same_disk_backup': same_disk, 'misc_entry': sha256_file(Path(__file__)), 'priors': {k: str(getattr(args, k).resolve()) for k in priors}}
    save(run, receipt)
    mtk = None
    previous_cwd = Path.cwd()
    try:
        os.chdir(run)
        mtk = open_da(run, loader)
        if uart:
            check_uart(uart)
        check_unit(mtk.daloader, parts['proinfo'], run)
        xml_module = sys.modules.get('mtkclient.Library.DA.xmlflash.xml_lib')
        if xml_module is None or sha256_file(Path(xml_module.__file__)) != identity['host']:
            raise ValueError('loaded XML implementation differs from verified host')
        if args.resume:  # claimed only once the DA, unit identity and host library are verified, and just before the session
            claim_restore(args.resume.resolve(), run)
            prior = priors['resume']
            prior['status'] = 'RESTORE_ATTEMPTED'
            save(args.resume.resolve(), prior)
        session.run_session(mtk.daloader, spec, original, candidate, run, mode=args.mode)
        receipt['status'] = 'VERIFIED'
        print('Target and guards verified. No reboot issued; review the next step before power-cycling.')
    except BaseException:
        receipt['status'] = 'STOP_UNVERIFIED'
        print('STOP: no retry, slot switch or reboot. Preserve recovery state and private logs.')
        raise
    finally:
        journals = list(run.glob(f'misc-{args.mode}-*/journal.jsonl'))
        if len(journals) == 1:
            receipt['journal'] = str(journals[0].relative_to(run))
            receipt['journal_hash'] = sha256_file(journals[0])
        try:
            save(run, receipt)
        finally:
            try:
                if mtk:
                    mtk.port.close()  # Host USB close only; no DA shutdown or device reboot.
            finally:
                os.chdir(previous_cwd)
                print(f'Private entry record: {run}')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError) as error:
        sys.exit(str(error))
