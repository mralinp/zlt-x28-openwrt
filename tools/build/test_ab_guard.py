#!/usr/bin/env python3
import io
import tarfile
import unittest
import ab_guard as g


def tree(files,links=()):
    t={}
    for name,data in files.items():
        m=tarfile.TarInfo(name);m.size=len(data);m.mode=0o755;t[name]=(m,data)
    for name,target in links:
        m=tarfile.TarInfo(name);m.type=tarfile.SYMTYPE;m.linkname=target;t[name]=(m,b'')
    return t


BASE={'etc/init.d/network':b'#!/bin/sh /etc/rc.common\nstart(){ . /lib/functions.sh; }\n','lib/functions.sh':b'#!/bin/sh\nlog(){ :; }\n',
      'etc/inittab':b'::sysinit:/etc/init.d/rcS S boot\n','etc/init.d/rcS':b'#!/bin/sh\n'}
LINK=[('etc/rc.d/S20network','../init.d/network')]


class GuardTests(unittest.TestCase):
    def test_clean_boot_path_passes(self):
        self.assertIn('lib/functions.sh',g.check(tree(BASE,LINK)))

    def test_every_writer_form_is_caught_in_an_enabled_script(self):
        for bad in (b'ab_image_sync "_b"',b'mtd write - rootfs',b'mtd -p 262144 write - x',b'nandwrite /dev/mtd1 f',b'sysupgrade -n f',
                    b'/sbin/sysupgrade f',b'dd if=x of=/dev/mtd3',b'set_bootctrl 1 2',b'platform_do_upgrade f',b'ubiupdatevol /dev/ubi0_0 f',
                    b'dd-nand of=x',b'fw_setenv a b',b'ubirmvol /dev/ubi0 -n 1',b'ubiattach -m 3',b'flash_eraseall /dev/mtd3',b'mtd erase misc',b'mtd unlock misc'):
            t=tree({**BASE,'etc/init.d/network':b'#!/bin/sh /etc/rc.common\n'+bad+b'\n'},LINK)
            with self.assertRaises(ValueError,msg=bad):g.check(t)

    def test_writer_in_a_sourced_library_is_caught(self):
        t=tree({**BASE,'lib/functions.sh':b'#!/bin/sh\nab_image_sync _a\n'},LINK)
        with self.assertRaises(ValueError):g.check(t)

    def test_unreferenced_script_and_plain_reads_are_not_flagged(self):
        t=tree({**BASE,'usr/bin/tool':b'#!/bin/sh\nab_image_sync x\n','lib/functions.sh':b'#!/bin/sh\nP=/dev/mtdblock\n[ -f /sysupgrade.tgz ]\n'},LINK)
        g.check(t)

    def test_upgrade_helpers_and_boot_done_paths_refused_even_if_unreferenced(self):
        for extra in ('lib/upgrade/bootctrl.sh','etc/init.d/zmtk_boot_done'):
            with self.assertRaises(ValueError):g.check(tree({**BASE,extra:b'x'},LINK))

    def test_hotplug_cron_and_rclocal_are_roots(self):
        for root in ('etc/hotplug.d/iface/10-x','etc/crontabs/root','etc/rc.local','etc/uci-defaults/90-x','lib/preinit/80_x'):
            with self.assertRaises(ValueError,msg=root):g.check(tree({**BASE,root:b'#!/bin/sh\nmtd write a b\n'},LINK))


if __name__=='__main__':unittest.main()
