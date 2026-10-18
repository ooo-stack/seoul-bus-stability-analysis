from c2a_fetch_public import request_file,endpoint,ROOT
from pathlib import Path
import json,concurrent.futures,zipfile,hashlib,re
MONTHS=['202509','202510','202601','202602','202603','202604','202605','202606']
sets=[('LOCAL_PEOPLE_DONG','OA-14991','living_local.html'),('LONG_FOREIGNER_DONG','OA-14992','living_long.html'),('TEMP_FOREIGNER_DONG','OA-14993','living_temp.html')]
jobs=[]
for prefix,infid,html in sets:
 s=(ROOT/html).read_text()
 for m in MONTHS:
  name=f'{prefix}_{m}.zip'
  assert name in s,name
  seq=m[2:]
  assert f"downloadFile('{seq}')" in s
  jobs.append((name,endpoint,{'infId':infid,'infSeq':'3','seq':seq}))
def get(j):
 p=ROOT/j[0]
 if p.exists() and zipfile.is_zipfile(p):return {'name':j[0],'already_present':True,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
 r=request_file(*j,timeout=60)
 if 'error' in r:return r
 r['valid_zip']=zipfile.is_zipfile(p)
 return r
res=[]
with concurrent.futures.ThreadPoolExecutor(3) as ex:
 for f in concurrent.futures.as_completed([ex.submit(get,j) for j in jobs]):
  x=f.result();res.append(x);print(json.dumps(x,ensure_ascii=False),flush=True)
  (ROOT/'living_download_manifest.json').write_text(json.dumps(res,ensure_ascii=False,indent=2))
