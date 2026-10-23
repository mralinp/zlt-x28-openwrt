#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify/decompress a captured partition set; never creates a flash command/image."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tarfile

def validate(partitions):
    seen=set()
    for p in partitions:
        if p['index'] in seen or not re.fullmatch(r'[A-Za-z0-9_]+',p['name']):
            raise ValueError('Duplicate index or invalid partition name')
        seen.add(p['index'])
        expected=f"mtd{p['index']:02d}-{p['name']}.bin.gz"
        if p['file']!=expected or p['size']<=0 or p['bytes_read']!=p['size']:
            raise ValueError('Unexpected filename or incomplete recorded capture')
        if not re.fullmatch('[0-9a-f]{64}',p['sha256_uncompressed']):
            raise ValueError('Invalid SHA-256')
    if seen!=set(range(51)):raise ValueError('Expected all 51 X28 partitions')

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while block:=f.read(1024*1024):h.update(block)
    return h.hexdigest()

def prepare(source,output):
    manifest=json.loads((source/'manifest.json').read_text())
    validate(manifest['partitions'])
    if output.exists():raise ValueError('Output must not exist')
    for p in manifest['partitions']:
        path=source/p['file']
        if not path.is_file() or path.is_symlink():raise ValueError('Missing or linked input')
    output.mkdir(parents=True,mode=0o700)
    (output/'INCOMPLETE').write_text('Preparation has not completed. Do not use for recovery.\n')
    for sub in ('images','original-compressed','metadata'):(output/sub).mkdir(mode=0o700)
    verified=[]
    for p in sorted(manifest['partitions'],key=lambda p:p['index']):
        compressed=source/p['file']; raw=output/'images'/p['file'][:-3]
        h=hashlib.sha256();size=0
        with gzip.open(compressed,'rb') as src,raw.open('xb') as dst:
            os.chmod(raw,0o600)
            while block:=src.read(1024*1024):
                size+=len(block)
                if size>p['size']:raise ValueError('Decompressed image exceeds recorded size')
                h.update(block);dst.write(block)
        if size!=p['size'] or h.hexdigest()!=p['sha256_uncompressed']:
            raise ValueError('Captured image hash/size mismatch: '+p['name'])
        copied=output/'original-compressed'/p['file'];shutil.copy2(compressed,copied);copied.chmod(0o600)
        compressed_hash=digest(copied)
        assert compressed_hash==digest(compressed)
        verified.append({**p,'raw_file':'images/'+raw.name,'compressed_file':'original-compressed/'+p['file'],
                         'sha256_compressed':compressed_hash,'verified_bytes':size})
        print('VERIFIED',p['index'],p['name'],size,flush=True)
    for name in ('manifest.json','mtd.txt','cmdline.txt','mounts.txt','meminfo.txt','openwrt-release.txt'):
        shutil.copy2(source/name,output/'metadata'/name);(output/'metadata'/name).chmod(0o600)
    report={'partition_count':len(verified),'total_main_data_bytes':sum(p['verified_bytes'] for p in verified),
            'capture_date':'2026-10-20','preparation_date':'2026-10-21',
            'capture_command':'nanddump --bb=padbad -q /dev/mtdN',
            'oob_included':False,'ecc_disabled':False,'restore_tested':False,
            'flashable_whole_device_image_created':False,'partitions':verified}
    (output/'verified-manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    (output/'SHA256SUMS').write_text(''.join(p['sha256_uncompressed']+'  '+p['raw_file']+'\n'+p['sha256_compressed']+'  '+p['compressed_file']+'\n' for p in verified))
    (output/'RECOVERY-LIMITS.md').write_text('''# Complete captured partition set; recovery NOT proven

All 51 main-data captures were decompressed and verified against the original manifest. Raw images and original gzip captures are preserved. The capture was taken on 2026-10-20; it does not include later configuration changes.

These are per-partition recovery inputs, NOT a sysupgrade/factory/whole-chip image. Do not upload them to LuCI, concatenate them, or write all partitions blindly. No flash commands are provided or executed.

The original command used ECC and padbad, and omitted OOB. Marked bad blocks would be replaced by FF. No capture-time bad-block map was recorded. Device geometry sampled later is not a capture-time map.

YAFFS2 tag placement (OOB versus vendor in-band), raw-NAND restore/ECC format, absolute partition addresses, boot security/signatures, preloader/bootloader handling and A/B selection remain unverified. Writable partitions were captured live without a filesystem snapshot/freeze, so cross-partition and in-partition consistency is not guaranteed. Corrected ECC notices in the manifest are retained; they are not uncorrectable errors.

A matching stock firmware package or a device-specific verified NAND-aware restoration procedure, proven UART/USB/bootloader access and a tested restore on spare hardware are still required before relying on this set as a recovery method. Data partitions contain device identity, calibration, SIM-related data and credentials: keep this directory private, offline and out of Git. Preserve another copy on separate storage.

The tar archive contains original compressed captures and metadata only; the images directory contains their uncompressed equivalents. The archive is a backup container, not a flashing format. Extraction of filesystem files does not improve the recoverability of the original partition bytes.
''')
    archive=output/'complete-captured-partitions.tar'
    with tarfile.open(archive,'x') as tar:
        for name in ('original-compressed','metadata','verified-manifest.json','SHA256SUMS','RECOVERY-LIMITS.md'):
            tar.add(output/name,arcname=name,recursive=True)
    with tarfile.open(archive) as tar:
        for p in verified:
            member=tar.extractfile(p['compressed_file']);h=hashlib.sha256()
            while block:=member.read(1024*1024):h.update(block)
            if h.hexdigest()!=p['sha256_compressed']:raise ValueError('Archive verification failed')
    (output/'ARCHIVE.sha256').write_text(digest(archive)+'  '+archive.name+'\n')
    (output/'INCOMPLETE').unlink()
    print('COMPLETE',len(verified),'partitions;',report['total_main_data_bytes'],'main-data bytes; archive verified')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();prepare(args.source,args.output)
