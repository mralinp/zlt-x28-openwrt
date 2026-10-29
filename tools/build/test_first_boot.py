#!/usr/bin/env python3
import base64
import io
import json
import os
import subprocess
from pathlib import Path
import struct
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import first_boot as f


def put(t,name,data):
    m=tarfile.TarInfo(name);m.size=len(data);m.mode=0o755 if name.startswith('etc/init.d/') else 0o644;t.addfile(m,io.BytesIO(data))


def elf(needed):
    strtab=b'\0'+b''.join(n.encode()+b'\0' for n in needed);offsets=[];pos=1
    for n in needed:offsets.append(pos);pos+=len(n)+1
    dyn=b''.join(struct.pack('<qQ',1,o) for o in offsets)+struct.pack('<qQ',5,176)+struct.pack('<qQ',0,0)
    size=176+len(strtab)+len(dyn)
    head=b'\x7fELF\x02\x01\x01'+bytes(9)+struct.pack('<HHIQQQIHHHHHH',3,183,1,0,64,0,0,64,56,2,64,0,0)
    ph=struct.pack('<IIQQQQQQ',1,5,0,0,0,size,size,0x1000)+struct.pack('<IIQQQQQQ',2,6,176+len(strtab),176+len(strtab),0,len(dyn),len(dyn),8)
    return head+ph+strtab+dyn


FAKE_SWCONFIG=r'''#!/usr/bin/env python3
import json,os,re,sys
state=os.environ['FAKE_SW_STATE'];mode=os.environ.get('FAKE_SW_MODE','')
a=sys.argv[1:]
if a==['list']:
    print('Found: switch0 - '+('MT7531AX' if mode=='wrong' else 'MT7531AE'));sys.exit(0)
assert a[:2]==['dev','switch0'],a
a=a[2:]
if a[0]=='load':
    if mode=='loadfail':sys.exit(1)
    d={'vlan':{},'pvid':{},'enable_vlan':'0'}
    for block in re.split(r'\n(?=config )',open(os.environ['FAKE_SW_CONFIG']).read()):
        o=dict(re.findall(r"option (\w+) '([^']*)'",block))
        if block.startswith('config switch_vlan'):d['vlan'][o['vlan']]=o['ports']
        if block.startswith('config switch_port'):d['pvid'][o['port']]=o['pvid']
        if block.startswith('config switch\n'):d['enable_vlan']=o['enable_vlan']
    if mode=='drift':d['vlan']['3']='3 5t'
    json.dump(d,open(state,'w'));sys.exit(0)
d=json.load(open(state))
if a==['get','enable_vlan']:print(d['enable_vlan'])
elif a[0]=='vlan' and a[2:]==['get','ports']:print(d['vlan'][a[1]]+' ')
elif a[0]=='port' and a[2:]==['get','pvid']:print(d['pvid'][a[1]])
else:sys.exit(2)
'''


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.stage=self.root/'stage';self.stage.mkdir()
        self.archive=self.stage/'rootfs-staging.tar.gz'
        with tarfile.open(self.archive,'w:gz') as t:
            for name,data in {'etc/inittab':b'ttyS0::askfirst:/bin/sh\n','etc/shadow':b'root:::0:99999:7:::\nservice:old:0:0:99999:7:::\n',
                              'etc/init.d/dropbear':b'PasswordAuth RootPasswordAuth', 'etc/init.d/network':b'network', 'etc/init.d/dnsmasq':b'dnsmasq', 'etc/init.d/odhcpd':b'odhcpd',
                              'www/luci-static/resources/view/network/wireless.js':b"if(hwtype=='mac80211'){x}\nelse if(hwtype=='broadcom'){y}",
                              'sbin/ujail':b'jail', 'usr/lib/opkg/info/procd-ujail.list':b'/sbin/ujail',
                              'usr/lib/opkg/status':b'Package: procd\nStatus: installed\n\nPackage: procd-ujail\nStatus: installed\n\nPackage: zlib\n',
                              'etc/uci-defaults/99-unsafe':b'mtd write', 'etc/rc.local':b'mtd write',
                              'etc/fstab':b'/dev/other /data ubifs rw 0 0',
                              'etc/rc.d/S99zmtk_boot_done':b'unsafe', 'etc/board.d/02_network':b'generic',
                              'lib/upgrade/platform.sh':b'unsafe', 'lib/preinit/99_10_failsafe_login':b'ash --login', 'lib/preinit/00_preinit.conf':b'pi_preinit_no_failsafe=""\n','lib/libc.so':b'musl','bin/ash':b'busybox'}.items():put(t,name,data)
            m=tarfile.TarInfo('etc/rc.d/S19dropbear');m.type=tarfile.SYMTYPE;m.linkname='../init.d/dropbear';t.addfile(m)
            m=tarfile.TarInfo('etc/rc.d/S20network');m.type=tarfile.SYMTYPE;m.linkname='../init.d/network';t.addfile(m)
        (self.stage/'manifest.json').write_text(json.dumps({'flashable':False,'archive_sha256':f.digest(self.archive.read_bytes())}))
        (self.stage/'NOT-FLASHABLE').touch()
        blob=struct.pack('>I',11)+b'ssh-ed25519'+struct.pack('>I',32)+b'K'*32
        self.key='ssh-ed25519 '+base64.b64encode(blob).decode()+' local comment\n'
        self.output=self.root/'output'
        self.stock=self.root/'stock.tar.gz'
        with tarfile.open(self.stock,'w:gz') as t:
            put(t,'rootfs/sbin/swconfig',elf(['libuci.so','libnl-tiny.so','libc.so']))
            put(t,'rootfs/usr/lib/libnl-tiny.so',elf(['libc.so']));put(t,'rootfs/lib/libuci.so',elf(['libc.so']))
            for name in f.WIFI_PROFILES:put(t,'rootfs/'+name,b'Default\nSSID1=stock\n')

    def test_policy_removes_shells_unsafe_services_and_defines_key_only_lan(self):
        r=f.integrate(self.stage,self.key,self.stock,self.output)
        tree=f.load_archive(self.output/'rootfs-management.tar.gz')
        self.assertNotIn('etc/rc.d/S99zmtk_boot_done',tree)
        self.assertNotIn('lib/upgrade/platform.sh',tree)
        self.assertNotIn('etc/uci-defaults/99-unsafe',tree)
        self.assertNotIn('lib/preinit/99_10_failsafe_login',tree)
        self.assertIn(b'pi_preinit_no_failsafe="y"',tree['lib/preinit/00_preinit.conf'][1])
        self.assertEqual([l for l in tree['etc/inittab'][1].decode().splitlines() if 'askfirst' in l],['ttyS0::askfirst:/bin/ash --login'])
        self.assertNotIn('login.sh',tree['etc/inittab'][1].decode())
        net=tree['etc/config/network'][1].decode()
        self.assertIn("option name 'br-lan'\n option type 'bridge'\n list ports 'eth0.1'\n list ports 'eth0.2'\n list ports 'eth0.3'\n list ports 'eth1'",net)
        self.assertIn("config interface 'lan'\n option device 'br-lan'",net)
        self.assertEqual(tree['etc/rc.d/S19dnsmasq'][0].linkname,'../init.d/dnsmasq')
        self.assertEqual(tree['etc/rc.d/S35odhcpd'][0].linkname,'../init.d/odhcpd')
        self.assertIn(" option ip6assign '64'",net)
        dhcp=tree['etc/config/dhcp'][1].decode()
        self.assertIn("config dhcp 'lan'\n option interface 'lan'",dhcp)
        self.assertIn(" option ra 'server'\n option dhcpv6 'server'",dhcp)
        self.assertEqual(tree['usr/lib/opkg/status'][1],b'Package: procd\nStatus: installed\n\nPackage: zlib\n')
        self.assertNotIn('sbin/ujail',tree);self.assertNotIn('usr/lib/opkg/info/procd-ujail.list',tree)
        self.assertEqual(tree['etc/rc.d/S99x28-leds'][0].linkname,'../init.d/x28-leds')
        self.assertIn('/dev/tz_gpio_leds',tree['sbin/x28-leds'][1].decode())
        self.assertEqual(tree['sbin/x28-leds'][0].mode,0o755)
        for name in f.WIFI_PROFILES:self.assertEqual(tree[name][1],b'Default\nSSID1=stock\n')
        js=tree[f.LUCI_WIRELESS][1].decode()
        self.assertIn("else if(hwtype=='mtwifi'){crypto_modes.push(['psk2'",js)
        self.assertEqual(f.luci_mtwifi(js),js)  # idempotent
        with self.assertRaises(ValueError):f.luci_mtwifi('changed LuCI')
        self.assertIn('add_driver mtwifi',tree['lib/netifd/wireless/mtwifi.sh'][1].decode())
        self.assertIn('append DRIVERS "mtwifi"',tree['lib/wifi/mtwifi.sh'][1].decode())
        self.assertIn(b"option PasswordAuth 'off'",tree['etc/config/dropbear'][1])
        self.assertEqual(tree['etc/dropbear/authorized_keys'][0].mode,0o600)
        self.assertTrue(all(row.split(b':')[1]==b'!' for row in tree['etc/shadow'][1].splitlines()))
        self.assertNotIn(b'mtd',tree['etc/rc.local'][1])
        self.assertFalse(r['flashable'])

    def test_switch_profile_ships_swconfig_table_and_single_early_owner(self):
        r=self.integrate_ok()
        tree=r[0]
        self.assertTrue(tree['sbin/swconfig'][0].isfile())
        self.assertIn('usr/lib/libnl-tiny.so',tree)
        self.assertEqual(tree['etc/rc.d/S18x28-switch'][0].linkname,'../init.d/x28-switch')
        self.assertNotIn('lib/network/switch.sh',tree)
        net=tree['etc/config/network'][1].decode()
        for v,(ports,port) in f.SWITCH.items():
            self.assertIn(f" option vlan '{v}'\n option vid '{v}'\n option ports '{ports}'",net)
            self.assertIn(f" option port '{port}'\n option pvid '{v}'",net)
        self.assertNotIn('mii_mgr',tree['etc/init.d/x28-switch'][1].decode())
        self.assertNotIn('gpio',tree['etc/init.d/x28-switch'][1].decode())
        self.assertEqual(r[1]['switch_table']['3'],'4 5t')

    def integrate_ok(self):
        report=f.integrate(self.stage,self.key,self.stock,self.output)
        return f.load_archive(self.output/'rootfs-management.tar.gz'),report

    def run_init(self,mode):
        tree,_=self.integrate_ok()
        bin=self.root/'bin';bin.mkdir()
        (bin/'swconfig').write_text(FAKE_SWCONFIG);(bin/'swconfig').chmod(0o755)
        (self.root/'network').write_bytes(tree['etc/config/network'][1])
        script=tree['etc/init.d/x28-switch'][1].decode().split('\n',1)[1]
        env={**os.environ,'PATH':f'{bin}:{os.environ["PATH"]}','FAKE_SW_STATE':str(self.root/'state'),
             'FAKE_SW_CONFIG':str(self.root/'network'),'FAKE_SW_MODE':mode}
        # /tmp marker path is rewritten so the test never touches the host's /tmp
        script=script.replace('/tmp/x28-switch.failed',str(self.root/'failed'))
        return subprocess.run(['sh','-c',script+'\nstart'],env=env,capture_output=True,text=True)

    def test_init_passes_only_when_readback_matches(self):
        self.assertEqual(self.run_init('').returncode,0)

    def test_init_fails_on_wrong_switch_load_error_or_readback_drift(self):
        for mode in ('wrong','loadfail','drift'):
            self.setUp()  # fresh output dir per mode
            r=self.run_init(mode)
            self.assertNotEqual(r.returncode,0,mode)
            self.assertTrue((self.root/'failed').exists(),mode)

    def test_missing_or_unresolved_swconfig_library_refused(self):
        with tarfile.open(self.stock,'w:gz') as t:
            put(t,'rootfs/sbin/swconfig',elf(['libnope.so']))
        with self.assertRaises(ValueError):f.integrate(self.stage,self.key,self.stock,self.output)
        self.assertFalse(self.output.exists())

    def test_bad_keys_refused_before_output(self):
        for key in ('PRIVATE KEY',self.key+self.key,'ssh-ed25519 !!!!'):
            with self.assertRaises(ValueError):f.integrate(self.stage,key,self.stock,self.output)
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
            with self.assertRaises(ValueError):f.integrate(self.stage,self.key,self.stock,self.output)
        self.assertFalse(self.output.exists())

    def test_console_shell_needs_ash(self):
        with tarfile.open(self.archive,'w:gz') as t:
            for name in ('etc/inittab','etc/shadow','etc/init.d/dropbear','etc/init.d/network','lib/libc.so'):put(t,name,b'root:::0:99999:7:::\n' if name=='etc/shadow' else b'x')
            for link in ('S19dropbear','S20network'):
                m=tarfile.TarInfo('etc/rc.d/'+link);m.type=tarfile.SYMTYPE;m.linkname='../init.d/'+link[3:];t.addfile(m)
        (self.stage/'manifest.json').write_text(json.dumps({'flashable':False,'archive_sha256':f.digest(self.archive.read_bytes())}))
        with self.assertRaises(ValueError):f.integrate(self.stage,self.key,self.stock,self.output)
        self.assertFalse(self.output.exists())

    def test_existing_output_is_not_overwritten(self):
        self.output.mkdir()
        with self.assertRaises(FileExistsError):f.integrate(self.stage,self.key,self.stock,self.output)

    def test_changed_stage_and_existing_output_fail_closed(self):
        with self.archive.open('ab') as stream:stream.write(b'changed')
        with self.assertRaises(ValueError):f.integrate(self.stage,self.key,self.stock,self.output)
        self.assertFalse(self.output.exists())


if __name__=='__main__':unittest.main()
