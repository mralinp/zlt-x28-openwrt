#!/usr/bin/env python3
"""Test packaged key-only SSH in a network-disabled Linux container.

Uses generated ephemeral keys only. No router or real private key/password access.
Tests direct Dropbear flags, not procd/native-kernel boot or physical networking.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time


def check(condition,message):
    if not condition:raise ValueError(message)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('candidate',type=Path)
    args=ap.parse_args();candidate=args.candidate.resolve()
    check(Path('/.dockerenv').exists() and os.geteuid()==0,'requires isolated Docker root with chroot capability')
    active={p.name for p in Path('/sys/class/net').iterdir() if (p/'flags').is_file() and int((p/'flags').read_text(),16)&1}
    check(active=={'lo'},'refused: only loopback may be up; use --network none')
    manifest=json.loads((candidate/'manifest.json').read_text());sq=(candidate/'rootfs.squashfs').read_bytes()
    check(manifest.get('flashable') is False and (candidate/'NOT-FLASHABLE').is_file(),'candidate must remain non-flashable')
    used=int.from_bytes(sq[40:48],'little')
    check(96<=used<=len(sq) and hashlib.sha256(sq[:used]).hexdigest()==manifest['rootfs_sha256'],'candidate SquashFS digest mismatch')
    with tempfile.TemporaryDirectory(prefix='auth-test-') as temp:
        root=Path(temp)/'root'
        subprocess.run(['unsquashfs','-d',str(root),str(candidate/'rootfs.squashfs')],check=True,stdout=subprocess.DEVNULL)
        def run(args):
            return subprocess.run(['chroot',str(root),*args],input='',capture_output=True,text=True,timeout=20)
        config=run(['/sbin/uci','-c','/etc/config','show','dropbear'])
        check(config.returncode==0,'cannot parse Dropbear config')
        for setting in ("PasswordAuth='off'","RootPasswordAuth='off'","RootLogin='on'","Port='2222'","Interface='lan'"):
            check(setting in config.stdout,'unexpected authentication policy: '+setting)
        root_account=next(row for row in (root/'etc/shadow').read_text().splitlines() if row.startswith('root:'))
        check(root_account.split(':')[1]=='','expected an empty root password (stock OpenWrt; SSH stays key-only)')
        (root/'tmp').mkdir(exist_ok=True);(root/'root').mkdir(exist_ok=True)
        keydir=root/'etc/dropbear';keydir.mkdir(exist_ok=True)
        for name in ('host','client','wrong'):
            generated=run(['/usr/bin/dropbearkey','-t','ed25519','-f','/tmp/'+name])
            check(generated.returncode==0,'ephemeral key generation failed')
        pub=run(['/usr/bin/dropbearkey','-y','-f','/tmp/client'])
        key=next(line for line in pub.stdout.splitlines() if line.startswith('ssh-ed25519 '))
        authorized=keydir/'authorized_keys';authorized.write_text(key+'\n');authorized.chmod(0o600)
        # Same authentication flags as parsed config; override LAN binding to isolated loopback.
        server=subprocess.Popen(['chroot',str(root),'/usr/sbin/dropbear','-F','-E','-s','-g',
                                 '-r','/tmp/host','-p','127.0.0.1:2222'],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
        try:
            time.sleep(0.3)
            check(server.poll() is None,'isolated Dropbear did not start')
            def client(name,marker):
                return run(['/usr/bin/dbclient','-T','-y','-i','/tmp/'+name,'-p','2222','root@127.0.0.1','echo '+marker])
            good=client('client','EXPECTED_KEY_OK')
            check(good.returncode==0 and good.stdout.strip()=='EXPECTED_KEY_OK','authorized key rejected with empty root password')
            wrong=client('wrong','UNEXPECTED_AUTH')
            check(server.poll() is None and wrong.returncode!=0 and 'UNEXPECTED_AUTH' not in wrong.stdout
                  and any(reason in wrong.stderr for reason in ('No auth methods could be used','Permission denied')),
                  'wrong-key test did not produce a live-server authentication rejection')
            authorized.write_text('')
            absent=client('client','UNEXPECTED_AUTH')
            check(server.poll() is None and absent.returncode!=0 and 'UNEXPECTED_AUTH' not in absent.stdout
                  and any(reason in absent.stderr for reason in ('No auth methods could be used','Permission denied')),
                  'empty-authorization test did not produce a live-server authentication rejection')
            print(json.dumps({'result':'PASS','authorized_key':True,'wrong_key_rejected':True,'empty_authorization_rejected':True,
                              'root_password_empty_ssh_still_key_only':True,'candidate_sha256':manifest['rootfs_sha256'],
                              'scope':'direct packaged Dropbear on isolated loopback; no native boot/procd/LAN proof'},indent=2))
        finally:
            server.terminate()
            try:server.wait(timeout=5)
            except subprocess.TimeoutExpired:server.kill();server.wait()
            server.stderr.close()


if __name__=='__main__':main()
