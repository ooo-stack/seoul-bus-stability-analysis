from pathlib import Path
import hashlib,json,os,gzip
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
# Submission adapter: paths only; the original calculation statements follow.
from seoul_bus_paths import bind as _submission_bind
globals().update(_submission_bind('M2'))
M=ROOT/'m2_sources/Gate3M1_results';A=ROOT/'m2_sources/Gate2F1A_results/f1a_results';C=ROOT/'m2_sources/Gate2F1C_results/f1c_results';D=ROOT/'m2_sources/Gate3M2D_design_package'
M=OUT/'inputs/M1' if (OUT/'inputs/M1').exists() else M
A=A if A.exists() else OUT/'inputs/F1A'
C=C if C.exists() else OUT/'inputs/F1C'
D=OUT/'inputs/M2D' if (OUT/'inputs/M2D').exists() else D
MAIN=['202509','202510','202601','202602','202603','202604','202605','202606'];ALL=['202509','202510','202511','202512','202601','202602','202603','202604','202605','202606','202607','202608'];HELD={'202511','202512','202607'}
AK=['dong_code','route_id','departure_node','arrival_node'];BK=['dong_code','departure_node','arrival_node'];SK=['route_id','departure_node','arrival_node','departure_sequence','arrival_sequence']
RAWK=['노선_ID','출발_정류장_ID','도착_정류장_ID','출발_정류장_순서','도착_정류장_순서'];VC=['운행시간_%02d시'%h for h in range(24)]
def read(p):return pd.read_csv(p,dtype={c:str for c in ['month','date','snapshot']+AK+SK},low_memory=False)
def sha(p):
 with open(p,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(df,name):
 data=df.to_csv(index=False,float_format='%.15g').encode('utf-8-sig');blob=gzip.compress(data,mtime=0) if name.endswith('.gz') else data
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.tmp')
 with t.open('wb') as f:f.write(blob);f.flush();os.fsync(f.fileno())
 os.replace(t,p)
 if name.endswith('.gz'):assert gzip.decompress(p.read_bytes())==data

def dump(o,name):
 (OUT/name).write_text(json.dumps(o,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def units():
 b=read(M/'route_segment_recurrence.csv');b=b[b.V.gt(0)].sort_values(AK).reset_index(drop=True);b['segment_id']=['A%04d'%(i+1) for i in range(len(b))]
 p=read(M/'dong_max_recurrence_route_segments.csv')[AK].copy();p['diagnostic_no']=np.arange(1,len(p)+1)
 b=b.merge(p,on=AK,how='left',validate='one_to_one');b['is_diagnostic43']=b.diagnostic_no.notna();assert len(b)==758 and b.is_diagnostic43.sum()==43
 return b
LABELS=AK+['segment_id','diagnostic_no','is_diagnostic43','dong_name','route_name','departure_name','arrival_name']
