#!/usr/bin/env python3
"""Guard/rollback checks with fake router commands; no network changes."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HELPER = Path(__file__).resolve().parents[1] / 'experiments/ip-passthrough/x28-passthrough'
FAKE = '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
root = Path(os.environ['TEST_STATE'])
name = Path(sys.argv[0]).name
args = sys.argv[1:]
with (root/'calls').open('a') as f: f.write(json.dumps([name]+args)+'\\n')
def state(name, value=None):
 p=root/name
 if value is not None: p.write_text(value)
 return p.read_text() if p.exists() else ''
public='198.51.100.10'
if name == 'id': print(0)
elif name == 'ifstatus':
 print(json.dumps({'up':True,'proto':'x28_mipc','l3_device':'ccmni1','ipv4-address':[{'address':public}]}))
elif name == 'jsonfilter':
 d=json.load(sys.stdin); expr=args[-1]
 print(d['ipv4-address'][0]['address'] if 'ipv4-address' in expr else str(d[expr[2:]]).lower())
elif name == 'sleep':
 if os.environ.get('INTERRUPT'):
  import signal
  os.kill(os.getppid(),signal.SIGTERM)
 if os.environ.get('CHANGE_WAN'): state('changed','yes')
elif name == 'ip':
 if args[:3] == ['-4','addr','show']:
  print('inet '+('198.51.100.20' if state('changed') else public)+'/29 scope global ccmni1')
 elif 'neigh' in args:
  if not os.environ.get('NO_MAC'): print('192.168.70.117 lladdr 02:00:00:00:00:01 REACHABLE')
 elif args[:3] == ['-4','route','get']:
  print(public+' via 192.168.70.117 dev br-lan src 192.168.70.1' if args[3]==public and state('host')=='added' else ('192.168.70.117 via 1.2.3.4 dev ccmni1' if os.environ.get('OFF_LAN') else '192.168.70.117 dev br-lan src 192.168.70.1'))
 elif args[:3] == ['-4','route','show']:
  if 'local' not in args and os.environ.get('EXISTING_ROUTE'): print(public+' via 192.168.70.200 dev br-lan')
  if 'local' in args and state('local') != 'removed': print('local '+public+' dev ccmni1 proto kernel scope host src '+public)
 elif 'route' in args:
  if 'del' in args and 'local' in args:
   if os.environ.get('FAIL_LOCAL'): sys.exit(1)
   state('local','removed')
  elif 'replace' in args and 'local' in args: state('local','restored')
  elif 'add' in args: state('host','added')
  elif 'del' in args: state('host','removed')
elif name == 'iptables':
 key='nat' if 'POSTROUTING' in args else 'guard'
 if '-I' in args: state(key,'added')
 elif '-D' in args: state(key,'removed')
'''

class PassthroughTests(unittest.TestCase):
 def run_helper(self, peer='192.168.70.117', duration='10', **extra):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory); (root/'calls').touch(); binary=root/'fake'; binary.write_text(FAKE); binary.chmod(0o755)
   for name in ('ip','iptables','ifstatus','jsonfilter','id','sleep'): (root/name).symlink_to(binary)
   env={**os.environ,'PATH':directory+os.pathsep+os.environ['PATH'],'TEST_STATE':directory,**extra}
   result=subprocess.run(['sh','-c','INCLUDE_ONLY=1 . "$1"; run_dir="$TEST_STATE/run"; pt_run "$2" "$3"','test',str(HELPER),peer,duration],env=env,text=True,capture_output=True,timeout=15)
   calls=[json.loads(line) for line in (root/'calls').read_text().splitlines()]
   states={p.name:p.read_text() for p in root.iterdir() if p.is_file() and not p.is_symlink() and p.name not in ('fake','calls')}
   return result,calls,states,(root/'run').exists()

 def test_invalid_inputs_do_not_mutate_network(self):
  for peer,duration in [('192.168.70.117;reboot','10'),('999.1.2.3','10'),('192.168.70.117\n192.168.70.118','10'),('192.168.070.117','10'),('127.0.0.1','10'),('192.168.70.117','0'),('192.168.70.117','999999999999999999999')]:
   with self.subTest(peer=peer,duration=duration):
    result,calls,_,locked=self.run_helper(peer,duration)
    self.assertNotEqual(result.returncode,0)
    self.assertFalse(any(c[0]=='iptables' or ('route' in c and any(x in c for x in ('add','del','replace'))) for c in calls))
    self.assertFalse(locked)

 def test_refuses_unresolved_remote_or_conflicting_peer(self):
  for setting in ('NO_MAC','OFF_LAN','EXISTING_ROUTE'):
   with self.subTest(setting=setting):
    result,calls,_,locked=self.run_helper(**{setting:'1'})
    self.assertNotEqual(result.returncode,0)
    self.assertFalse(any(c[0]=='iptables' for c in calls))
    self.assertFalse(locked)

 def test_termination_restores_nat(self):
  result,_,states,locked=self.run_helper(INTERRUPT='1')
  self.assertNotEqual(result.returncode,0)
  self.assertEqual(states,{'local':'restored','host':'removed','nat':'removed','guard':'removed'})
  self.assertFalse(locked)

 def test_timeout_restores_nat_and_local_delivery(self):
  result,_,states,locked=self.run_helper()
  self.assertEqual(result.returncode,0,result.stderr)
  self.assertEqual(states,{'local':'restored','host':'removed','nat':'removed','guard':'removed'})
  self.assertFalse(locked)

 def test_partial_setup_failure_rolls_back(self):
  result,_,states,locked=self.run_helper(FAIL_LOCAL='1')
  self.assertNotEqual(result.returncode,0)
  self.assertEqual(states['host'],'removed'); self.assertEqual(states['nat'],'removed'); self.assertEqual(states['guard'],'removed')
  self.assertFalse(locked)

 def test_changed_wan_does_not_restore_stale_local_address(self):
  result,calls,states,locked=self.run_helper(CHANGE_WAN='1')
  self.assertNotEqual(result.returncode,0)
  self.assertEqual(states['host'],'removed'); self.assertEqual(states['nat'],'removed')
  self.assertFalse(any('replace' in c and 'local' in c for c in calls))
  self.assertFalse(locked)

if __name__ == '__main__': unittest.main()
