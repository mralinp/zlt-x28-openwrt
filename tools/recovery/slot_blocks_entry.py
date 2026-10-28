#!/usr/bin/env python3
"""Guarded entry for the block-granular sessions (#113, #114). Dry-run is offline; --write needs approval.

  sig-block identical --block K      rehearsal: identical rewrite of one 256 KiB block of rootfs_sig_a (K = 1..3)
  misc-blocks probe                  all four misc copies get distinct A priorities but still select B
  misc-blocks probe-restore --resume restore the original misc, blockwise
  misc-blocks select --last-copy K   the real A selection, blockwise, copy K written last
  misc-blocks select-restore --resume

Plan: docs/research/misc-probe-plan.md. Use the private mtkclient venv Python for --write. No automatic reboot or
retry. Merging this file approves nothing; the typed phrase attests the owner's approval of this exact session.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

import slot_blocks as blocks
import slot_entry as entry
import slot_session as session
from common import DEFAULT_BACKUP, MTK_HOME, PRIVATE, VENDOR_DA, sha256_file
from restore_entry import check_uart, check_unit, claim_restore, host_identity, open_da, save
from write_verify import active_slot

digest = entry.digest
# (target, mode) -> (flag, kind, must be verified); kinds: sig, probe, select, rootfs_a
PRIOR = {
    ('sig-block', 'identical'): [],
    ('misc-blocks', 'probe'): [('prior_sig_block', 'sig', True)],
    ('misc-blocks', 'probe-restore'): [('resume', 'probe', False)],
    ('misc-blocks', 'select'): [('prior_probe', 'probe', True), ('prior_rootfs_a', 'rootfs_a', True)],
    ('misc-blocks', 'select-restore'): [('resume', 'select', False)],
}
KIND_MODE = {'probe': 'write', 'select': 'write', 'probe-restore': 'restore', 'select-restore': 'restore'}


def order_for(mode, last_copy, resumed_order=None):
    if mode.endswith('restore'):
        return tuple(resumed_order)
    if mode == 'probe':
        return (4, 3, 2, 1)
    if last_copy not in (1, 2, 3, 4):
        raise ValueError('select needs --last-copy 1..4 (the copy the probe showed the preloader trusts)')
    return tuple([c for c in (4, 3, 2, 1) if c != last_copy] + [last_copy])


def check_blocks_journal(raw, header, step_mode, order, sha_of, verified):
    """The blockwise journal must show exactly the planned copies, in order, acknowledged; verified needs a clean end."""
    events = [json.loads(line) for line in raw.splitlines()]
    if not events or events[0] != header:
        raise ValueError('journal header mismatch')
    attempts = [e for e in events if 'write_attempt' in e]
    results = [e for e in events if 'write_result' in e]
    want = [{'write_attempt': step_mode, 'copy': c, 'sha256': sha_of(c)} for c in order]
    if attempts != want[:len(attempts)] or not attempts:
        raise ValueError('unexpected write history; no automatic retry')
    if verified:
        if attempts != want or results != [{'write_result': step_mode, 'copy': c, 'acknowledged': True} for c in order] \
                or events[-1].get('status') != 'TARGET_AND_GUARDS_VERIFIED':
            raise ValueError('prior run did not finish verified')


def load_blocks_prior(run, expect, header, kind, order, sha_of, verified):
    run = Path(run).resolve(strict=True)
    if (run / 'restore-claim.json').exists():
        raise ValueError('restore attempt already claimed; separate review required')
    receipt = json.loads((run / 'receipt.json').read_text())
    if (receipt.get('schema') != 3 or receipt.get('run') != str(run) or receipt.get('target') != 'misc-blocks'
            or receipt.get('mode') != kind or {k: receipt.get('identity', {}).get(k) for k in expect} != expect
            or receipt.get('order') != list(order)):
        raise ValueError('receipt does not match this unit, tools, image or order')
    if verified:
        if receipt.get('status') != 'VERIFIED' or not 0 <= time.time() - receipt.get('created', 0) <= entry.MAX_AGE:
            raise ValueError('evidence is not verified or is older than 24 h')
    elif receipt.get('status') not in ('VERIFIED', 'STOP_UNVERIFIED'):
        raise ValueError('resume needs a finished or stopped write run')
    journal = run / receipt.get('journal', 'missing')
    if journal.name != 'journal.jsonl' or journal.resolve().parent.parent != run:
        raise ValueError('journal outside bound run')
    raw = journal.read_bytes()
    if digest(raw) != receipt.get('journal_hash'):
        raise ValueError('journal changed or incomplete')
    check_blocks_journal(raw, header, 'write', order, sha_of, verified)
    return receipt


def phrase(target, mode, image_sha, extra, same_disk):
    text = f'WRITE {mode} {target} {image_sha[:12]}' + extra
    return text + (' SAME-DISK' if same_disk else '')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('target', choices=('sig-block', 'misc-blocks'))
    ap.add_argument('mode', choices=('identical', 'probe', 'probe-restore', 'select', 'select-restore'))
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--block', type=int)
    ap.add_argument('--last-copy', type=int)
    ap.add_argument('--backup', type=Path, default=DEFAULT_BACKUP)
    ap.add_argument('--loader', type=Path, default=VENDOR_DA)
    ap.add_argument('--candidate-dir', type=Path, help='package_ubi output of the approved rootfs_a (select, optional for probe)')
    ap.add_argument('--backup-copy', type=Path)
    ap.add_argument('--uart-log', type=Path)
    ap.add_argument('--prior-sig-block', type=Path)
    ap.add_argument('--prior-probe', type=Path)
    ap.add_argument('--prior-rootfs-a', type=Path)
    ap.add_argument('--resume', type=Path)
    args = ap.parse_args()
    if (args.target, args.mode) not in PRIOR:
        raise ValueError(f'{args.mode} is not a {args.target} mode')
    wanted = PRIOR[(args.target, args.mode)]
    for flag, *_ in wanted:
        if getattr(args, flag) is None:
            raise ValueError(f'{args.target} {args.mode} requires --{flag.replace("_", "-")}')
    for flag in ('prior_sig_block', 'prior_probe', 'prior_rootfs_a', 'resume'):
        if getattr(args, flag) is not None and flag not in [w[0] for w in wanted]:
            raise ValueError(f'--{flag.replace("_", "-")} is not valid for {args.target} {args.mode}')
    if (args.target == 'sig-block') != (args.block is not None):
        raise ValueError('--block is for sig-block only, and required there')
    if args.mode in ('select', 'select-restore') and args.candidate_dir is None:
        raise ValueError(f'{args.mode} needs --candidate-dir (the approved rootfs_a)')
    backup, loader = args.backup.resolve(strict=True), args.loader.resolve(strict=True)
    table, parts = entry.verified_backup(backup, loader)
    host = digest(host_identity().encode())
    here = Path(__file__).parent
    tools = b''.join((here / n).read_bytes() for n in ('slot_blocks_entry.py', 'slot_blocks.py', 'slot_entry.py', 'slot_session.py',
                                                      'restore_entry.py', 'common.py', 'read_by_name.py', 'write_verify.py', 'setup_mtkclient.py'))
    base_id = {'da': entry.DA_HASH, 'host': host, 'tools': digest(tools), 'unit': parts['proinfo']['sha256']}
    rootfs_a_sha = None
    if args.candidate_dir is not None:
        manifest = json.loads((args.candidate_dir / 'manifest.json').read_text())
        if manifest.get('padded_sha256') != digest((args.candidate_dir / 'rootfs-a-experimental.bin').read_bytes()):
            raise ValueError('candidate does not match its build manifest')
        rootfs_a_sha = manifest['padded_sha256']
    order = None
    if args.target == 'sig-block':
        sig_a = Path(parts['rootfs_sig_a']['image']).read_bytes()
        spec, block = blocks.sig_block_spec(sig_a, args.block)
        identity = {'target': spec.name, 'original': spec.original_sha, 'candidate': spec.candidate_sha, 'rootfs_a': session.ROOTFS_A_SHA, **base_id}
        image_sha, extra = spec.original_sha, ''
    else:
        before = Path(parts['misc']['image']).read_bytes()
        after = blocks.probe_image(before) if args.mode.startswith('probe') else blocks.select_image(before)
        after_sha = digest(after)
        resumed = None
        if args.resume is not None:
            resumed = json.loads((args.resume / 'receipt.json').read_text()).get('order')
            if not isinstance(resumed, list):
                raise ValueError('resumed receipt has no order')
        order = order_for(args.mode, args.last_copy, resumed)
        # select: exactly the written candidate. select-restore: also stock B's repair copy. probe: stock A or the candidate.
        rootfs_a_ok = {'select': (rootfs_a_sha,), 'select-restore': (rootfs_a_sha, session.ROOTFS_A_SHA, session.ROOTFS_B_SHA)}.get(
            args.mode, tuple(x for x in (session.ROOTFS_A_SHA, rootfs_a_sha) if x))
        guards = blocks.misc_guards(rootfs_a_ok)
        identity = {'target': 'misc-blocks', 'original': session.MISC_SHA, 'candidate': after_sha, 'rootfs_a': rootfs_a_sha or session.ROOTFS_A_SHA, **base_id}
        image_sha = after_sha if not args.mode.endswith('restore') else session.MISC_SHA
        extra = f' ORDER {"".join(map(str, order))}' + (f' ROOTFS-A {rootfs_a_sha[:12]}' if args.mode == 'select' else '') + ' BROM-ROUTE-PROVEN'
    priors = {}
    for flag, kind, verified in wanted:
        run = getattr(args, flag)
        if kind == 'sig':
            sig_spec, _ = blocks.sig_block_spec(Path(parts['rootfs_sig_a']['image']).read_bytes(), json.loads((Path(run) / 'receipt.json').read_text()).get('block'))
            priors[flag] = entry.load_prior(run, {**base_id, 'target': sig_spec.name, 'original': sig_spec.original_sha,
                                                  'candidate': sig_spec.candidate_sha, 'rootfs_a': session.ROOTFS_A_SHA}, sig_spec, 'identical', True)
        elif kind == 'rootfs_a':  # produced by slot_entry.py: bound to the unit, host and approved image, not to this script's hash
            priors[flag] = entry.load_prior(run, {'target': 'rootfs_a', 'candidate': rootfs_a_sha, 'rootfs_a': rootfs_a_sha, 'da': base_id['da'],
                                                  'host': base_id['host'], 'unit': base_id['unit']}, session.rootfs_a_spec(rootfs_a_sha), 'write', True)
        else:
            receipt_order = tuple((json.loads((Path(run) / 'receipt.json').read_text()).get('order')) or ())
            if kind == 'probe' and receipt_order != (4, 3, 2, 1):
                raise ValueError('probe runs use the fixed order 4,3,2,1')
            prior_after = blocks.probe_image(before) if kind == 'probe' else blocks.select_image(before)
            prior_sha, new_blocks = digest(prior_after), blocks.blocks(prior_after)
            header = {'mode': 'write', 'target': 'misc', 'order': list(receipt_order), 'before_sha': session.MISC_SHA, 'after_sha': prior_sha}
            expect = {**base_id, 'target': 'misc-blocks', 'original': session.MISC_SHA, 'candidate': prior_sha}
            priors[flag] = load_blocks_prior(run, expect, header, kind, receipt_order, lambda c, nb=new_blocks: digest(nb[c - 1]), verified)
    if args.target == 'sig-block':
        print(f'identical: rootfs_sig_a block {args.block} at {spec.addr:#x}, {spec.size:#x} bytes; no reboot or retry')
    else:
        print(f'{args.mode}: misc blockwise, copies in order {list(order)}, image {image_sha[:12]}; no reboot or retry')
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
    if not args.mode.endswith('restore') and active_slot(table) != 'b':
        raise ValueError('live SSH must confirm B and exact full layout')
    base = PRIVATE / 'usb-probe'
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    if shutil.disk_usage(base).free < 2 * 1024 ** 3:
        raise ValueError('less than 2 GiB free for captures and sources')
    if not sys.stdin.isatty():
        raise ValueError('typed confirmation needs an interactive terminal')
    expected_phrase = phrase(spec.name if args.target == 'sig-block' else 'misc-blocks', args.mode, image_sha, extra, same_disk)
    print('Confirm UART RX capture continues, stable power and no stock upgrade/FOTA pending. Merging a PR is not approval.')
    if args.target == 'misc-blocks':
        print('misc is the LIVE slot selector: one 256 KiB block is rewritten at a time, the others are re-read after each step.')
    if input(f'Type exactly {expected_phrase!r} to attest those checks and authorize this operation: ') != expected_phrase:
        raise ValueError('operation not confirmed')
    run = Path(tempfile.mkdtemp(prefix=f'blocks-{args.target}-{args.mode}-', dir=base)).resolve()
    receipt = {'schema': 3 if args.target == 'misc-blocks' else 2, 'run': str(run), 'target': 'misc-blocks' if args.target == 'misc-blocks' else spec.name,
               'mode': 'identical' if args.target == 'sig-block' else args.mode, 'status': 'STARTED', 'identity': identity, 'created': time.time(),
               'uart': str(uart), 'same_disk_backup': same_disk, 'order': list(order) if order else None,
               'block': args.block, 'priors': {k: str(getattr(args, k).resolve()) for k in priors}}
    save(run, receipt)
    if args.resume:
        claim_restore(args.resume.resolve(), run)
        prior = priors['resume']
        prior['status'] = 'RESTORE_ATTEMPTED'
        save(args.resume.resolve(), prior)
    mtk = None
    previous_cwd = Path.cwd()
    try:
        os.chdir(run)
        mtk = open_da(run, loader)
        check_uart(uart)
        check_unit(mtk.daloader, parts['proinfo'], run)
        xml_module = sys.modules.get('mtkclient.Library.DA.xmlflash.xml_lib')
        if xml_module is None or sha256_file(Path(xml_module.__file__)) != host:
            raise ValueError('loaded XML implementation differs from verified host')
        if args.target == 'sig-block':
            session.run_session(mtk.daloader, spec, block, block, run, mode='identical')
        else:
            blocks.run_blockwise(mtk.daloader, before, after, after_sha, order, run,
                                 mode='restore' if args.mode.endswith('restore') else 'write', guards=guards)
        receipt['status'] = 'VERIFIED'
        print('Verified. No reboot issued; review UART before approving the next step.')
    except BaseException:
        receipt['status'] = 'STOP_UNVERIFIED'
        print('STOP: no retry, slot switch or reboot. Preserve recovery state and private logs.')
        raise
    finally:
        journals = list(run.glob('*/journal.jsonl'))
        if len(journals) == 1:
            receipt['journal'] = str(journals[0].relative_to(run))
            receipt['journal_hash'] = sha256_file(journals[0])
        try:
            save(run, receipt)
        finally:
            try:
                if mtk:
                    mtk.port.close()
            finally:
                os.chdir(previous_cwd)
                print(f'Private entry record: {run}')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
        sys.exit(str(error))
