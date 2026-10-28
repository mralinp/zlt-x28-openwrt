#!/usr/bin/env python3
import base64
import io
import json
from pathlib import Path
import struct
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import first_boot as f


def put(t,name,data):
    m=tarfile.TarInfo(name);m.size=len(data);m.mode=0o755 if name.startswith('etc/init.d/') else 0o644;t.addfile(m,io.BytesIO(data))


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.stage=self.root/'stage';self.stage.mkdir()
        self.archive=self.stage/'rootfs-staging.tar.gz'
        with tarfile.open(self.archive,'w:gz') as t:
            for name,data in {'etc/inittab':b'ttyS0::askfirst:/bin/sh\n','etc/shadow':b'root:::0:99999:7:::\nservice:old:0:0:99999:7:::\n',
                              'etc/init.d/dropbear':b'PasswordAuth RootPasswordAuth', 'etc/init.d/network':b'network',
                              'etc/uci-defaults/99-unsafe':b'mtd write', 'etc/rc.local':b'mtd write',
                              'etc/fstab':b'/dev/other /data ubifs rw 0 0',
                              'etc/rc.d/S99zmtk_boot_done':b'unsafe', 'etc/board.d/02_network':b'generic',
                              'lib/upgrade/platform.sh':b'unsafe', 'lib/preinit/99_10_failsafe_login':b'ash --login', 'lib/preinit/00_preinit.conf':b'pi_preinit_no_failsafe=""\n'}.items():put(t,name,data)
            m=tarfile.TarInfo('etc/rc.d/S19dropbear');m.type=tarfile.SYMTYPE;m.linkname='../init.d/dropbear';t.addfile(m)
            m=tarfile.TarInfo('etc/rc.d/S20network');m.type=tarfile.SYMTYPE;m.linkname='../init.d/network';t.addfile(m)
        (self.stage/'manifest.json').write_text(json.dumps({'flashable':False,'archive_sha256':f.digest(self.archive.read_bytes())}))
        (self.stage/'NOT-FLASHABLE').touch()
        blob=struct.pack('>I',11)+b'ssh-ed25519'+struct.pack('>I',32)+b'K'*32
        self.key='ssh-ed25519 '+base64.b64encode(blob).decode()+' local comment\n'
        self.output=self.root/'output'

    def test_policy_removes_shells_unsafe_services_and_defines_key_only_lan(self):
        r=f.integrate(self.stage,self.key,'eth1',self.output)
        tree=f.load_archive(self.output/'rootfs-management.tar.gz')
        self.assertNotIn('etc/rc.d/S99zmtk_boot_done',tree)
        self.assertNotIn('lib/upgrade/platform.sh',tree)
        self.assertNotIn('etc/uci-defaults/99-unsafe',tree)
        self.assertNotIn('lib/preinit/99_10_failsafe_login',tree)
        self.assertIn(b'pi_preinit_no_failsafe="y"',tree['lib/preinit/00_preinit.conf'][1])
        self.assertNotIn('askfirst',tree['etc/inittab'][1].decode())
        self.assertIn(b"option device 'eth1'",tree['etc/config/network'][1])
        self.assertIn(b"option PasswordAuth 'off'",tree['etc/config/dropbear'][1])
        self.assertEqual(tree['etc/dropbear/authorized_keys'][0].mode,0o600)
        self.assertTrue(all(row.split(b':')[1]==b'!' for row in tree['etc/shadow'][1].splitlines()))
        self.assertNotIn(b'mtd',tree['etc/rc.local'][1])
        self.assertFalse(r['flashable'])

    def test_bad_keys_and_interface_injection_refused_before_output(self):
        for key in ('PRIVATE KEY',self.key+self.key,'ssh-ed25519 !!!!'):
            with self.assertRaises(ValueError):f.integrate(self.stage,key,'eth1',self.output)
        for dev in ('eth1;reboot','ccmni1','eth0\n','eth0.9999'):
            with self.assertRaises(ValueError):f.integrate(self.stage,self.key,dev,self.output)
        self.assertFalse(self.output.exists())

    def test_allowlisted_startup_name_cannot_redirect_or_be_regular_script(self):
        for redirect in (True,False):
            with tarfile.open(self.archive,'w:gz') as t:
                put(t,'etc/init.d/dropbear',b'safe')
                m=tarfile.TarInfo('etc/rc.d/S19dropbear')
                if redirect:
                    m.type=tarfile.SYMTYPE;m.linkname='../init.d/unsafe';t.addfile(m)
                else:
                    m.size=6;t.addfile(m,io.BytesIO(b'unsafe'))
            (self.stage/'manifest.json').write_text(json.dumps({'flashable':False,'archive_sha256':f.digest(self.archive.read_bytes())}))
            with self.assertRaises(ValueError):f.integrate(self.stage,self.key,'eth1',self.output)
        self.assertFalse(self.output.exists())

    def test_existing_output_is_not_overwritten(self):
        self.output.mkdir()
        with self.assertRaises(FileExistsError):f.integrate(self.stage,self.key,'eth1',self.output)

    def test_changed_stage_and_existing_output_fail_closed(self):
        with self.archive.open('ab') as stream:stream.write(b'changed')
        with self.assertRaises(ValueError):f.integrate(self.stage,self.key,'eth1',self.output)
        self.assertFalse(self.output.exists())


if __name__=='__main__':unittest.main()
