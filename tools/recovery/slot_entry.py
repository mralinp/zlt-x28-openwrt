#!/usr/bin/env python3
"""Guarded rootfs_a / misc entry (#99, #100) around slot_session.py. Dry-run is offline; --write needs approval.

Use the private mtkclient venv Python for --write. No automatic reboot or retry. Merging this file approves
nothing: the typed phrase attests that the owner approved this exact target, mode and image, and that the
gates in docs/research/rootfs-a-write-plan.md hold (including a proven BROM route for any misc session).
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

import slot_session as session
from common import DEFAULT_BACKUP, MTK_HOME, PRIVATE, VENDOR_DA, backup_table, sha256_file
from restore_entry import DA_HASH, LAYOUT_HASH, check_uart, check_unit, claim_restore, host_identity, open_da, save
from write_verify import active_slot

# (target, mode) -> prior runs it consumes: (flag, target, mode, must be verified)
PRIOR = {
    ('rootfs_a', 'identical'): [],
    ('rootfs_a', 'write'): [('prior_identical', 'rootfs_a', 'identical', True)],
    ('rootfs_a', 'restore'): [('resume', 'rootfs_a', 'write', False)],
    ('misc', 'identical'): [('prior_rootfs_a', 'rootfs_a', 'write', True)],
    ('misc', 'write'): [('prior_identical', 'misc', 'identical', True), ('prior_rootfs_a', 'rootfs_a', 'write', True)],
    ('misc', 'restore'): [('resume', 'misc', 'write', False)],
}
MAX_AGE = 86400


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verified_backup(backup, loader):
    """The complete verified backup table and its by-name index; raises on any layout, integrity or DA mismatch."""
    table = backup_table(backup)
    layout = [{k: p[k] for k in ('index', 'name', 'size', 'erase_size', 'offset')} for p in table]
    if digest(json.dumps(layout, sort_keys=True).encode()) != LAYOUT_HASH:
        raise ValueError('backup layout is not this X28 layout')
    for p in table:
        image = Path(p['image'])
        if image.stat().st_size != p['size'] or sha256_file(image) != p['sha256']:
            raise ValueError('backup integrity failure: ' + p['name'])
    by_name = {p['name']: p for p in table}
    if sha256_file(loader) != DA_HASH:
        raise ValueError('DA identity mismatch')
    return table, by_name


def load_inputs(backup, loader, target, mode, candidate_dir):
    """Verified originals, the pinned candidate and the spec; raises on any identity mismatch."""
    table, by_name = verified_backup(backup, loader)
    original = Path(by_name[target]['image']).read_bytes()
    manifest = json.loads((candidate_dir / 'manifest.json').read_text())
    rootfs_a_image = (candidate_dir / 'rootfs-a-experimental.bin').read_bytes()
    rootfs_a_sha = manifest.get('padded_sha256')
    if rootfs_a_sha != digest(rootfs_a_image):
        raise ValueError('candidate does not match its build manifest')
    if target == 'rootfs_a':
        spec, candidate = session.rootfs_a_spec(rootfs_a_sha), rootfs_a_image
    else:
        spec = session.misc_spec(rootfs_a_sha)
        candidate = bytearray(original)
        for off in session.MISC_COPIES:
            candidate[off:off + 16] = session.MISC_AFTER
        candidate = bytes(candidate)
        if digest(candidate) != session.MISC_A_SHA:
            raise ValueError('misc candidate differs from the pinned selection image')
    if mode == 'write':
        spec.validate(original, candidate)  # refuse a bad candidate before any connection or claim
    for name, addr, size, sha in spec.guards:
        p = by_name[name]
        if (p['offset'], p['size']) != (addr, size) or (isinstance(sha, str) and name != 'rootfs_a' and p['sha256'] != sha):
            raise ValueError('guard identity mismatch: ' + name)
    if (by_name[target]['offset'], by_name[target]['size']) != (spec.addr, spec.size):
        raise ValueError('target identity mismatch')
    host = digest(host_identity().encode())
    here = Path(__file__).parent
    tools = b''.join((here / n).read_bytes() for n in ('slot_entry.py', 'slot_session.py', 'restore_entry.py', 'common.py',
                                                      'read_by_name.py', 'write_verify.py', 'setup_mtkclient.py'))
    tools += b''.join((here.parent / 'build' / n).read_bytes() for n in ('package_ubi.py', 'stage_native.py'))
    identity = {'target': target, 'original': spec.original_sha, 'candidate': spec.candidate_sha, 'rootfs_a': rootfs_a_sha,
                'da': DA_HASH, 'host': host, 'tools': digest(tools), 'unit': by_name['proinfo']['sha256']}
    return by_name, table, original, candidate, spec, identity


def load_prior(run, expect, spec, mode, verified):
    """A previous run's receipt, bound to this unit, tools and image, and to a journal that was not edited."""
    run, target = Path(run).resolve(strict=True), spec.name
    if (run / 'restore-claim.json').exists():  # a run claimed for restore is spent, even as a verified prior
        raise ValueError('restore attempt already claimed; separate review required')
    receipt = json.loads((run / 'receipt.json').read_text())
    if (receipt.get('schema') != 2 or receipt.get('run') != str(run) or receipt.get('target') != target
            or receipt.get('mode') != mode
            or {k: receipt.get('identity', {}).get(k) for k in expect} != expect):
        raise ValueError(f'receipt for {target} {mode} does not match this unit, tools or image')
    if verified:
        if receipt.get('status') != 'VERIFIED' or not 0 <= time.time() - receipt.get('created', 0) <= MAX_AGE:
            raise ValueError(f'{target} {mode} evidence is not verified or is older than 24 h')
    elif receipt.get('status') not in ('VERIFIED', 'STOP_UNVERIFIED'):
        raise ValueError('resume needs a finished or stopped write run')
    journal = run / receipt.get('journal', 'missing')
    if journal.name != 'journal.jsonl' or journal.resolve().parent.parent != run:
        raise ValueError('journal outside bound run')
    raw = journal.read_bytes()
    if digest(raw) != receipt.get('journal_hash'):
        raise ValueError('journal changed or incomplete')
    events = [json.loads(line) for line in raw.splitlines()]
    header = {'mode': mode, 'target': target, 'target_offset': spec.addr, 'target_length': spec.size,
              'candidate_sha256': spec.candidate_sha if mode == 'write' else None}
    attempt = {'write_attempt': mode, 'sha256': spec.candidate_sha if mode == 'write' else spec.original_sha}
    if not events or events[0] != header or [e for e in events if 'write_attempt' in e] != [attempt]:
        raise ValueError('journal target, image or write history mismatch; no automatic retry')
    if verified:
        if events[-1].get('status') != 'TARGET_AND_GUARDS_VERIFIED' or \
                [e for e in events if 'write_result' in e] != [{'write_result': mode, 'acknowledged': True}]:
            raise ValueError('prior run did not finish verified')
    return receipt


def phrase(spec, mode, rootfs_a_sha, same_disk):
    # identical and restore write the original; the phrase names the bytes that will land on the target
    image = spec.candidate_sha if mode == 'write' else spec.original_sha
    text = f'WRITE {mode} {spec.name} {image[:12]}'
    if spec.name == 'misc':
        text += f' ROOTFS-A {rootfs_a_sha[:12]} BROM-ROUTE-PROVEN'
    return text + (' SAME-DISK' if same_disk else '')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('target', choices=('rootfs_a', 'misc'))
    ap.add_argument('mode', choices=('identical', 'write', 'restore'))
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--backup', type=Path, default=DEFAULT_BACKUP)
    ap.add_argument('--loader', type=Path, default=VENDOR_DA)
    ap.add_argument('--candidate-dir', type=Path, help='package_ubi output directory of the approved rootfs_a image (all sessions)')
    ap.add_argument('--backup-copy', type=Path, help='verified second complete-captured-partitions.tar')
    ap.add_argument('--uart-log', type=Path)
    ap.add_argument('--prior-identical', type=Path)
    ap.add_argument('--prior-rootfs-a', type=Path, help='verified rootfs_a write run (misc sessions)')
    ap.add_argument('--resume', type=Path, help='stopped or finished write run, restore mode only')
    args = ap.parse_args()
    wanted = PRIOR[(args.target, args.mode)]
    for flag, *_ in wanted:
        if getattr(args, flag) is None:
            raise ValueError(f'{args.target} {args.mode} requires --{flag.replace("_", "-")}')
    for flag in ('prior_identical', 'prior_rootfs_a', 'resume'):
        if getattr(args, flag) is not None and flag not in [w[0] for w in wanted]:
            raise ValueError(f'--{flag.replace("_", "-")} is not valid for {args.target} {args.mode}')
    if args.candidate_dir is None:
        raise ValueError('--candidate-dir (the package_ubi output of the approved rootfs_a) is required for every session')
    backup, loader = args.backup.resolve(strict=True), args.loader.resolve(strict=True)
    parts, table, original, candidate, spec, identity = load_inputs(
        backup, loader, args.target, args.mode, args.candidate_dir.resolve(strict=True))
    rootfs_a_sha = identity['rootfs_a']
    specs = {'rootfs_a': session.rootfs_a_spec(rootfs_a_sha), 'misc': session.misc_spec(rootfs_a_sha)}
    priors = {}
    for flag, target, mode, verified in wanted:
        # Every prior is bound to this unit, host, tools and the same approved rootfs_a image (from the manifest, not a receipt).
        expect = {**identity, 'target': target, 'original': specs[target].original_sha, 'candidate': specs[target].candidate_sha}
        priors[flag] = load_prior(getattr(args, flag), expect, specs[target], mode, verified)
    print(f'{args.mode}: {args.target} only at {spec.addr:#x}, {spec.size:#x} bytes; candidate {spec.candidate_sha[:12]}; no reboot or retry')
    if not args.write:
        print('OFFLINE DRY RUN: no SSH, hardware import, USB command or write; execution gates not checked')
        return
    venv_python = MTK_HOME / 'venv/bin/python'
    if os.path.realpath(sys.executable) != os.path.realpath(venv_python):
        os.execv(venv_python, [str(venv_python), *sys.argv])
    if not args.backup_copy or not args.uart_log:
        raise ValueError('--write requires --backup-copy and --uart-log')
    copy, uart = args.backup_copy.resolve(strict=True), args.uart_log.resolve(strict=True)
    archive = backup / 'complete-captured-partitions.tar'
    expected_archive = (backup / 'ARCHIVE.sha256').read_text().split()[0]
    if copy.samefile(archive) or sha256_file(archive) != expected_archive or sha256_file(copy) != expected_archive:
        raise ValueError('second archive copy is missing, same file, or invalid')
    same_disk = copy.stat().st_dev == archive.stat().st_dev
    check_uart(uart)
    if args.mode != 'restore' and active_slot(table) != 'b':
        raise ValueError('live SSH must confirm B and exact full layout')
    base = PRIVATE / 'usb-probe'
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    if shutil.disk_usage(base).free < 1024 * 1024 * 1024:
        raise ValueError('less than 1 GiB free for captures and sources')
    if not sys.stdin.isatty():
        raise ValueError('typed confirmation needs an interactive terminal')
    expected_phrase = phrase(spec, args.mode, rootfs_a_sha, same_disk)
    print('Confirm UART RX capture continues, stable power, no stock upgrade/FOTA pending, and that the NOT-FLASHABLE marker')
    print('on the candidate is deliberately overridden by the owner. Merging a PR is not approval.')
    if args.target == 'misc':
        print('misc is the LIVE slot selector and is rewritten whole (1 MiB): a power or USB loss can leave no valid record.')
    if same_disk:
        print('WARNING: backup copy is on the same filesystem; host disk loss would lose both copies.')
    if input(f'Type exactly {expected_phrase!r} to attest those checks and authorize this operation: ') != expected_phrase:
        raise ValueError('operation not confirmed')
    run = Path(tempfile.mkdtemp(prefix=f'slot-{args.target}-{args.mode}-', dir=base)).resolve()
    receipt = {'schema': 2, 'run': str(run), 'target': args.target, 'mode': args.mode, 'status': 'STARTED', 'identity': identity,
               'created': time.time(), 'uart': str(uart), 'same_disk_backup': same_disk,
               'priors': {k: str(getattr(args, k).resolve()) for k in priors}}
    save(run, receipt)
    if args.resume:
        claim_restore(args.resume.resolve(), run)
        prior = priors['resume']
        prior['status'] = 'RESTORE_ATTEMPTED'
        save(args.resume.resolve(), prior)  # Consume before connecting: never blindly retry a restore.
    mtk = None
    previous_cwd = Path.cwd()
    try:
        os.chdir(run)
        mtk = open_da(run, loader)
        check_uart(uart)
        check_unit(mtk.daloader, parts['proinfo'], run)
        xml_module = sys.modules.get('mtkclient.Library.DA.xmlflash.xml_lib')
        if xml_module is None or sha256_file(Path(xml_module.__file__)) != identity['host']:
            raise ValueError('loaded XML implementation differs from verified host')
        session.run_session(mtk.daloader, spec, original, candidate, run, mode=args.mode)
        receipt['status'] = 'VERIFIED'
        print('Target and guards verified. No reboot issued; review UART before approving the next step.')
    except BaseException:
        receipt['status'] = 'STOP_UNVERIFIED'
        print('STOP: no retry, slot switch or reboot. Preserve recovery state and private logs.')
        raise
    finally:
        journals = list(run.glob(f'{args.target}-{args.mode}-*/journal.jsonl'))
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
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
        sys.exit(str(error))
