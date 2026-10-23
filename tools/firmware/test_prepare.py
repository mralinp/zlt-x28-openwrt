# SPDX-License-Identifier: MIT
import copy,importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('prepare',Path(__file__).with_name('prepare_recovery.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
valid=[{'index':i,'name':'p'+str(i),'file':f'mtd{i:02d}-p{i}.bin.gz','size':4096,'bytes_read':4096,'sha256_uncompressed':'0'*64} for i in range(51)]
m.validate(valid)
for transform in ('missing','duplicate','path','size','hash'):
 p=copy.deepcopy(valid)
 if transform=='missing':p.pop()
 elif transform=='duplicate':p[1]['index']=0
 elif transform=='path':p[0]['file']='../x.gz'
 elif transform=='size':p[0]['bytes_read']=1
 else:p[0]['sha256_uncompressed']='bad'
 try:m.validate(p)
 except ValueError:pass
 else:raise AssertionError(transform)
print('PASS valid set; missing/duplicate/path/size/hash errors rejected')
