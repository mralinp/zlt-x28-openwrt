#!/usr/bin/env python3
"""Apply a private, NOT-FLASHABLE first-boot management profile to #76 staging.

Stock swconfig, observed MT7531AE VLAN table, static LAN on eth0.3, key-only SSH. No vendor activation or device I/O.
"""
import argparse
import base64
import copy
import io
import json
import posixpath
from pathlib import Path
import struct
import sys
import tarfile

from ab_guard import check as ab_check
from stage_native import digest, load_archive, resolve, validate_parents

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'firmware'))
from inventory import elf_dynamic

ALLOWED_START = {'S00urngd','S10boot','S10system','S11sysctl','S12log','S18x28-switch','S19dropbear','S20network'}
ALLOWED_STOP = {'K50dropbear','K89log','K90boot','K90network','K90umount'}

LAN = 'eth0.3'  # socket 4 = MT7531AE port 4, untagged VLAN 3 (#84)
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


def add_swconfig(tree,stock):
    """Copy stock /sbin/swconfig plus any ELF dependency the tree lacks; every NEEDED must resolve."""
    todo=['sbin/swconfig'];seen=set();added=[]
    while todo:
        name=todo.pop()
        if name in seen:continue
        seen.add(name);chain=[]
        real,data=resolve(stock,name,chain)
        for item in chain:
            if item not in tree:tree[item]=stock[item];added.append(item)
            elif name=='sbin/swconfig':raise ValueError('swconfig path already occupied: '+item)
        if data[:4]!=b'\x7fELF':raise ValueError('not ELF: '+name)
        for need in elf_dynamic(data)[1]:
            options=[d+'/'+need for d in ('lib','usr/lib')]
            have=next((p for p in options if p in tree),None)
            if have:resolve(tree,have)
            else:
                old=next((p for p in options if p in stock),None)
                if old is None:raise ValueError('unresolved swconfig library: '+need)
                todo.append(old)
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
    swconfig_added=add_swconfig(tree,load_archive(io.BytesIO(stock_bytes),'rootfs'))
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
    put('etc/init.d/x28-switch',SWITCH_INIT,0o755)
    link=tarfile.TarInfo('etc/rc.d/S18x28-switch');link.type=tarfile.SYMTYPE;link.linkname='../init.d/x28-switch';tree[link.name]=(link,b'')
    # Physical console only (kernel console=ttyS0,921600): needs the board's UART pads, unlike SSH. Root's password
    # stays locked; this is the single way in if switch/network init fails, since failsafe is removed.
    if 'bin/ash' not in tree:raise ValueError('missing /bin/ash for the console shell')
    put('etc/inittab','::sysinit:/etc/init.d/rcS S boot\n::shutdown:/etc/init.d/rcS K shutdown\nttyS0::askfirst:/bin/ash --login\n')
    put('etc/config/network',f"""config interface 'loopback'
 option device 'lo'
 option proto 'static'
 option ipaddr '127.0.0.1'
 option netmask '255.0.0.0'

config interface 'lan'
 option device '{LAN}'
 option proto 'static'
 option ipaddr '192.168.70.1'
 option netmask '255.255.255.0'
"""+SWITCH_UCI)
    put('etc/config/dropbear',"""config dropbear
 option PasswordAuth 'off'
 option RootPasswordAuth 'off'
 option RootLogin 'on'
 option Port '2222'
 option Interface 'lan'
 option GatewayPorts 'off'
 option mdns '0'
""")
    put('etc/dropbear/authorized_keys',key,0o600)
    rows=tree['etc/shadow'][1].decode().splitlines();found=False;locked=[]
    for row in rows:
        fields=row.split(':')
        if len(fields)!=9:raise ValueError('malformed shadow record')
        fields[1]='!';locked.append(':'.join(fields));found|=fields[0]=='root'
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
            'lan_device':LAN,'switch_table':{str(v):x[0] for v,x in SWITCH.items()},'swconfig_sha256':digest(tree['sbin/swconfig'][1]),'swconfig_added':swconfig_added,'stock_sha256':digest(stock_bytes),'lan_address':'192.168.70.1/24','ssh_port':2222,'public_key_sha256':digest(key.encode()),
            'removed_paths':removed,'enabled_start_links':sorted(n for n in tree if n.startswith('etc/rc.d/S')),
            'limits':['No modem/Wi-Fi/shared mounts','UART console shell (ttyS0, no password) is physical-access root','Switch table is stock-observed, never applied on hardware; physical socket-4 mapping is operator-confirmed only','No DHCP/web UI','Root/key login still needs runtime test','No overlay/UBI/slot/signature readiness']}
    (output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');(output/'INCOMPLETE').unlink()
    return report


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--stage',type=Path,required=True)
    ap.add_argument('--public-key',type=Path,required=True);ap.add_argument('--stock',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();print(json.dumps(integrate(args.stage,args.public_key.read_text(),args.stock,args.output),indent=2))


if __name__=='__main__':main()
