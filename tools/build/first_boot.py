#!/usr/bin/env python3
"""Apply a private, NOT-FLASHABLE first-boot management profile to #76 staging.

Stock swconfig, observed MT7531AE VLAN table, static LAN on br-lan (all four sockets) with DHCP, front LEDs, key-only SSH.
No vendor activation or device I/O.
"""
import argparse
import base64
import copy
import io
import json
import posixpath
import re
from pathlib import Path
import struct
import sys
import tarfile

from ab_guard import check as ab_check
from stage_native import digest, load_archive, resolve, validate_parents

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'firmware'))
from inventory import elf_dynamic

ALLOWED_START = {'S00urngd','S10boot','S10system','S11sysctl','S12log','S18x28-switch','S12rpcd','S19firewall','S19x28-modem','S19dropbear','S19dnsmasq','S20network','S35odhcpd','S50uhttpd','S95done','S96x28-bootok','S99x28-leds'}
ALLOWED_STOP = {'K50dropbear','K89log','K90boot','K90network','K90umount'}

LAN = 'br-lan'
# Sockets 1, 2, 4 (#84: port 4, untagged VLAN 3) and 0, one VLAN each; stock bridges them all into br0 (#122).
LAN_PORTS = ('eth0.1','eth0.2','eth0.3','eth1')
LEDS = Path(__file__).resolve().parents[2]/'package/x28-leds/files'
WIFI = Path(__file__).resolve().parents[2]/'package/x28-wifi/files'
MIPC = Path(__file__).resolve().parents[2]/'package/x28-mipc/files'
LUCI_MIPC = Path(__file__).resolve().parents[2]/'package/luci-proto-x28-mipc'
BOOTOK = Path(__file__).resolve().parents[2]/'package/x28-bootok/files'
MODEM = Path(__file__).resolve().parents[2]/'package/x28-modem/files'
# mt_wifi reads these at interface up; the mtwifi handler rewrites only its keys in them (#127).
# Stock LuCI 23.05 offers WPA only for mac80211/broadcom radios; add the modes the mtwifi handler maps (#127).
LUCI_WIRELESS = 'www/luci-static/resources/view/network/wireless.js'
LUCI_ANCHOR = "else if(hwtype=='broadcom'){"
LUCI_MTWIFI = ("else if(hwtype=='mtwifi'){crypto_modes.push(['psk2','WPA2-PSK',35]);"
               "crypto_modes.push(['sae','WPA3-SAE',31]);crypto_modes.push(['sae-mixed','WPA2-PSK/WPA3-SAE Mixed Mode',30]);"
               "crypto_modes.push(['psk-mixed','WPA-PSK/WPA2-PSK Mixed Mode',22]);}\n")


def luci_mtwifi(js):
    """Stock wireless.js with the mtwifi encryption modes; refuses an unknown LuCI build."""
    if LUCI_MTWIFI in js:return js
    if js.count(LUCI_ANCHOR)!=1:raise ValueError('unexpected LuCI wireless.js: mtwifi patch anchor not found')
    return js.replace(LUCI_ANCHOR,LUCI_MTWIFI+LUCI_ANCHOR)


WIFI_PROFILES = ('etc/wireless/l1profile.dat','etc/wireless/mediatek/mt7915.dbdc.b0.dat','etc/wireless/mediatek/mt7915.dbdc.b1.dat')
# vlan: (ports, untagged port whose PVID is that vlan). Copied from the observed stock table.
SWITCH = {1:('1 5t',1),2:('2 5t',2),3:('4 5t',4),4:('0 6t',0)}
SWITCH_UCI = "\nconfig switch\n option name 'switch0'\n option reset '1'\n option enable_vlan '1'\n" + ''.join(
    f"\nconfig switch_vlan\n option device 'switch0'\n option vlan '{v}'\n option vid '{v}'\n option ports '{ports}'\n"
    f"\nconfig switch_port\n option device 'switch0'\n option port '{port}'\n option pvid '{v}'\n"
    for v,(ports,port) in SWITCH.items())
# Not the vendor initializer: no PHY/GPIO writes, no lan_mgr. The chk lines read back what `load` must have set.
SWITCH_INIT = """#!/bin/sh /etc/rc.common
START=18

fail() { echo "x28-switch: $*" >&2; : > /tmp/x28-switch.failed; return 1; }
chk() { want="$1"; shift; got=$(swconfig dev switch0 "$@" 2>/dev/null) && [ "$(echo $got)" = "$want" ]; }

start() {
	rm -f /tmp/x28-switch.failed
	[ "$(swconfig list 2>/dev/null)" = "Found: switch0 - MT7531AE" ] || { fail "unexpected switch"; return 1; }
	swconfig dev switch0 load network || { fail "load failed"; return 1; }
	chk 1 get enable_vlan || fail "vlan not enabled"
""" + ''.join(f"\tchk '{ports}' vlan {v} get ports || fail 'vlan {v} ports'\n\tchk {v} port {port} get pvid || fail 'port {port} pvid'\n"
              for v,(ports,port) in SWITCH.items()) + """	[ ! -e /tmp/x28-switch.failed ]
}
"""


def add_stock(tree,stock,root,exclusive=False):
    """Copy a stock file plus any ELF dependency the tree lacks; every NEEDED must resolve. A root the tree already
    holds must be identical (exclusive: must be absent)."""
    todo=[root];seen=set();added=[];label=posixpath.basename(root)
    while todo:
        name=todo.pop()
        if name in seen:continue
        seen.add(name);chain=[]
        real,data=resolve(stock,name,chain)
        for item in chain:
            if item not in tree:tree[item]=stock[item];added.append(item)
            elif name==root and (exclusive or tree[item][1]!=stock[item][1]):raise ValueError(label+' path already occupied: '+item)
        if data[:4]!=b'\x7fELF':
            if exclusive:raise ValueError('not ELF: '+name)
            continue
        for need in elf_dynamic(data)[1]:
            options=[d+'/'+need for d in ('lib','usr/lib')]
            have=next((p for p in options if p in tree),None)
            if have:resolve(tree,have)
            else:
                old=next((p for p in options if p in stock),None)
                if old is None:raise ValueError('unresolved '+label+' library: '+need)
                todo.append(old)
    return added


def add_swconfig(tree,stock):
    return add_stock(tree,stock,'sbin/swconfig',exclusive=True)


def add_modem(tree,stock):
    """The vendor modem stack x28-modem starts (#131): its stock init scripts, the binaries they run, the modem
    configuration under vendor/etc."""
    services=re.search(r'^SERVICES="([^"]*)"',(MODEM/'x28-modem.init').read_text(),re.M).group(1).split()
    added=[]
    for service in services:
        script='etc/init.d/'+service
        added+=add_stock(tree,stock,script)
        command=re.search(r'procd_set_param command (/\S+)',stock[script][1].decode())
        if not command:raise ValueError('no command in stock '+script)
        added+=add_stock(tree,stock,command.group(1).lstrip('/'))
    added+=add_stock(tree,stock,'usr/bin/mipc_wan_cli')+add_stock(tree,stock,'etc/quectel-project-version')
    added+=add_stock(tree,stock,'etc/conf/apns-conf_8.xml')  # the SIM's APN list x28-apn reads; without it wan loops on NO_SIM_APN (#141)
    for name in sorted(stock):
        if (name=='vendor' or name.startswith('vendor/etc')) and name not in tree:tree[name]=stock[name];added.append(name)
    return added


def public_key(text):
    lines=text.strip().splitlines()
    if len(lines)!=1:raise ValueError('exactly one public key required')
    fields=lines[0].split()
    if len(fields)<2 or fields[0] not in ('ssh-ed25519','ssh-rsa'):
        raise ValueError('only plain ed25519/RSA public keys are supported; no options/private keys')
    try:
        data=base64.b64decode(fields[1],validate=True);pos=0;parts=[]
        while pos<len(data):
            size=struct.unpack_from('>I',data,pos)[0];pos+=4
            if size>len(data)-pos:raise ValueError('truncated key')
            parts.append(data[pos:pos+size]);pos+=size
        if parts[0]!=fields[0].encode():raise ValueError('key type mismatch')
        if fields[0]=='ssh-ed25519' and (len(parts)!=2 or len(parts[1])!=32):raise ValueError('bad ed25519 key')
        if fields[0]=='ssh-rsa':
            if len(parts)!=3 or not parts[1] or not parts[2] or parts[1][0]&128 or parts[2][0]&128:
                raise ValueError('invalid positive RSA integers')
            exponent=int.from_bytes(parts[1],'big');modulus=int.from_bytes(parts[2],'big')
            if exponent<3 or exponent%2==0 or modulus.bit_length()<2048 or modulus%2==0:
                raise ValueError('invalid RSA parameters')
    except (IndexError,struct.error,base64.binascii.Error) as error:
        raise ValueError('invalid public key') from error
    return fields[0]+' '+fields[1]+'\n'


def integrate(stage,key,stock_path,output):
    key=public_key(key)
    if output.exists():raise FileExistsError(output)
    manifest=json.loads((stage/'manifest.json').read_text());raw=(stage/'rootfs-staging.tar.gz').read_bytes()
    if manifest.get('flashable') is not False or not (stage/'NOT-FLASHABLE').is_file() or digest(raw)!=manifest.get('archive_sha256'):
        raise ValueError('staging identity/marker mismatch')
    stock_bytes=Path(stock_path).read_bytes()
    tree=load_archive(io.BytesIO(raw));removed=[]
    stock=load_archive(io.BytesIO(stock_bytes),'rootfs')
    swconfig_added=add_swconfig(tree,stock)
    modem_added=add_modem(tree,stock)
    bootok_added=add_stock(tree,stock,'sbin/dd-nand')  # the vendor writer x28-bootok uses on one misc byte (#145)
    for name in WIFI_PROFILES:
        if name not in stock or not stock[name][0].isfile():raise ValueError('missing stock Wi-Fi profile: '+name)
        tree[name]=stock[name]
    for name in list(tree):
        if (name.startswith(('etc/rc.d/','etc/uci-defaults/','etc/board.d/','lib/upgrade/','etc/dropbear/'))
            or 'zmtk_boot_done' in name or (name.startswith('lib/preinit/') and 'failsafe' in name)):
            keep=name.startswith('etc/rc.d/') and name.split('/')[-1] in ALLOWED_START|ALLOWED_STOP
            if keep:
                meta=tree[name][0];service=name.split('/')[-1][3:]
                target=posixpath.normpath(posixpath.join('etc/rc.d',meta.linkname))
                expected='etc/init.d/'+service
                if not meta.issym() or target!=expected or expected not in tree or not tree[expected][0].isfile() or not tree[expected][0].mode&0o111:
                    raise ValueError('redirected or invalid startup link: '+name)
            if not keep:
                removed.append(name);del tree[name]
    for required in ('etc/rc.d/S19dropbear','etc/rc.d/S20network','etc/init.d/dropbear','etc/init.d/network'):
        if required not in tree:raise ValueError('required management service missing: '+required)
    def put(name,text,mode=0o644):
        info=tarfile.TarInfo(name);info.mode=mode;info.uid=info.gid=0
        data=text.encode();info.size=len(data);tree[name]=(info,data)
    if 'lib/preinit/00_preinit.conf' in tree:
        config=tree['lib/preinit/00_preinit.conf'][1].decode()
        put('lib/preinit/00_preinit.conf',config+'\npi_preinit_no_failsafe="y"\n')
    def enable(start,service):
        if 'etc/init.d/'+service not in tree:raise ValueError('missing service: '+service)
        link=tarfile.TarInfo(f'etc/rc.d/S{start}{service}');link.type=tarfile.SYMTYPE;link.linkname='../init.d/'+service;tree[link.name]=(link,b'')
    put('etc/init.d/x28-switch',SWITCH_INIT,0o755);enable(18,'x28-switch')
    put('sbin/x28-leds',(LEDS/'x28-leds').read_text(),0o755)
    # The staged boot script runs `wifi config` once when /etc/config/wireless is missing: WPA2 with a random key.
    put('lib/netifd/wireless/mtwifi.sh',(WIFI/'mtwifi.sh').read_text(),0o755)
    put('lib/wifi/mtwifi.sh',(WIFI/'mtwifi.detect').read_text())
    if LUCI_WIRELESS in tree:put(LUCI_WIRELESS,luci_mtwifi(tree[LUCI_WIRELESS][1].decode()))
    # Cellular WAN as a stock-looking netifd protocol (#135): the proto handler, its APN helper and the LuCI form.
    put('lib/netifd/proto/x28_mipc.sh',(MIPC/'x28_mipc.sh').read_text(),0o755)
    put('sbin/x28-apn',(MIPC/'x28-apn').read_text(),0o755)
    put('www/luci-static/resources/protocol/x28_mipc.js',(LUCI_MIPC/'htdocs/luci-static/resources/protocol/x28_mipc.js').read_text())
    put('usr/share/rpcd/acl.d/luci-proto-x28-mipc.json',(LUCI_MIPC/'root/usr/share/rpcd/acl.d/luci-proto-x28-mipc.json').read_text())
    put('etc/config/system',"""config system
 option hostname 'x28'
 option timezone 'UTC'
 option ttylogin '0'
 option log_size '64'
 option urandom_seed '0'
""")
    put('etc/init.d/x28-modem',(MODEM/'x28-modem.init').read_text(),0o755);enable(19,'x28-modem')
    put('etc/init.d/x28-leds',(LEDS/'x28-leds.init').read_text(),0o755);enable(99,'x28-leds')
    enable(19,'dnsmasq');enable(35,'odhcpd')
    enable(12,'rpcd');enable(19,'firewall');enable(50,'uhttpd')  # LuCI and NAT (#141)
    put('etc/init.d/x28-bootok',(BOOTOK/'x28-bootok.init').read_text(),0o755);enable(96,'x28-bootok')
    enable(95,'done')  # `mount_root done`: without it mount_root discards the overlay at every boot (#143)
    # Stock defaults plus IPv6 on the LAN (#126): RA and DHCPv6 from the /64 the cellular WAN hands to netifd.
    put('etc/config/dhcp',"""config dnsmasq
 option domainneeded '1'
 option boguspriv '1'
 option localise_queries '1'
 option rebind_protection '1'
 option rebind_localhost '1'
 option local '/lan/'
 option domain 'lan'
 option expandhosts '1'
 option cachesize '1000'
 option authoritative '1'
 option readethers '1'
 option leasefile '/tmp/dhcp.leases'
 option resolvfile '/tmp/resolv.conf.d/resolv.conf.auto'
 option nonwildcard '1'
 option localservice '1'
 option ednspacket_max '1232'

config dhcp 'lan'
 option interface 'lan'
 option start '100'
 option limit '150'
 option leasetime '12h'
 option ra 'server'
 option dhcpv6 'server'
 list ra_flags 'managed-config'
 list ra_flags 'other-config'

config dhcp 'wan'
 option interface 'wan'
 option ignore '1'
""")
    # CONFIG_NAMESPACES is off in the vendor kernel: with ujail present procd jails dnsmasq/sysntpd and they exit (#122).
    for name in [n for n in tree if n=='sbin/ujail' or n.startswith('usr/lib/opkg/info/procd-ujail.')]:
        removed.append(name);del tree[name]
    if 'usr/lib/opkg/status' in tree:  # or opkg would still list it and could reinstall it
        stanzas=tree['usr/lib/opkg/status'][1].decode().split('\n\n')
        put('usr/lib/opkg/status','\n\n'.join(x for x in stanzas if not x.startswith('Package: procd-ujail\n')))
    # Physical console only (kernel console=ttyS0,921600): needs the board's UART pads, unlike SSH. This is the single
    # way in if switch/network init fails, since failsafe is removed.
    if 'bin/ash' not in tree:raise ValueError('missing /bin/ash for the console shell')
    put('etc/inittab','::sysinit:/etc/init.d/rcS S boot\n::shutdown:/etc/init.d/rcS K shutdown\nttyS0::askfirst:/bin/ash --login\n')
    put('etc/config/network',f"""config interface 'loopback'
 option device 'lo'
 option proto 'static'
 option ipaddr '127.0.0.1'
 option netmask '255.0.0.0'

config device
 option name '{LAN}'
 option type 'bridge'
"""+''.join(f" list ports '{p}'\n" for p in LAN_PORTS)+f"""
config interface 'lan'
 option device '{LAN}'
 option proto 'static'
 option ipaddr '192.168.70.1'
 option netmask '255.255.255.0'
 option ip6assign '64'

config interface 'wan'
 option proto 'x28_mipc'
"""+SWITCH_UCI)
    put('etc/config/dropbear',"""config dropbear
 option PasswordAuth 'off'
 option RootPasswordAuth 'off'
 option RootLogin 'on'
 option Port '22'
 option Interface 'lan'
 option GatewayPorts 'off'
 option mdns '0'
""")
    put('etc/dropbear/authorized_keys',key,0o600)
    # Like stock OpenWrt root starts with an empty password so LuCI can log in and ask for one; dropbear stays key-only.
    rows=tree['etc/shadow'][1].decode().splitlines();found=False;locked=[]
    for row in rows:
        fields=row.split(':')
        if len(fields)!=9:raise ValueError('malformed shadow record')
        fields[1]='' if fields[0]=='root' else '!';locked.append(':'.join(fields));found|=fields[0]=='root'
    if not found:raise ValueError('missing root account')
    put('etc/shadow','\n'.join(locked)+'\n',0o600)
    put('etc/rc.local','#!/bin/sh\nexit 0\n',0o755)
    put('etc/fstab','# First-boot profile: no shared partition mounts.\n')
    put('etc/config/fstab','# No shared volumes or swap enabled.\n')
    validate_parents(tree)
    ab_check(tree)  # #87: refuse a profile whose boot path can reach flash or the other slot
    output.mkdir(parents=True,mode=0o700);(output/'NOT-FLASHABLE').write_text('Management profile only; overlay, UBI, signature/slot and hardware readiness unverified.\n');(output/'INCOMPLETE').touch()
    archive=output/'rootfs-management.tar.gz'
    with tarfile.open(archive,'x:gz') as tar:
        for name,(info,data) in sorted(tree.items()):
            meta=copy.copy(info);tar.addfile(meta,io.BytesIO(data) if meta.isfile() else None)
    report={'flashable':False,'input_stage_sha256':digest(raw),'archive_sha256':digest(archive.read_bytes()),
            'lan_device':LAN,'lan_ports':list(LAN_PORTS),'switch_table':{str(v):x[0] for v,x in SWITCH.items()},'swconfig_sha256':digest(tree['sbin/swconfig'][1]),'swconfig_added':swconfig_added,'modem_added':modem_added,'bootok_added':bootok_added,'stock_sha256':digest(stock_bytes),'lan_address':'192.168.70.1/24','ssh_port':22,'public_key_sha256':digest(key.encode()),
            'removed_paths':removed,'enabled_start_links':sorted(n for n in tree if n.startswith('etc/rc.d/S')),
            'limits':['Modem stack from stock, started by x28-modem; reboot persistence unverified (#131)','UART console shell (ttyS0, no password) is physical-access root','Switch table is stock-observed, never applied on hardware; physical socket-4 mapping is operator-confirmed only','No web UI','LEDs show no-service without the modem stack','Root/key login still needs runtime test','No overlay/UBI/slot/signature readiness']}
    (output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');(output/'INCOMPLETE').unlink()
    return report


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--stage',type=Path,required=True)
    ap.add_argument('--public-key',type=Path,required=True);ap.add_argument('--stock',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();print(json.dumps(integrate(args.stage,args.public_key.read_text(),args.stock,args.output),indent=2))


if __name__=='__main__':main()
