from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,os,gzip,zipfile,struct
ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent;M1=ROOT/'m3a_sources/Gate3M1_results';M2=ROOT/'m3a_sources/Gate3M2_results';F0=ROOT/'m3a_sources/Gate2F0M_results/f0m_results'
# Submission adapter: paths only; the original calculation statements follow.
from seoul_bus_paths import bind as _submission_bind
globals().update(_submission_bind('M3A'))
MAIN=['202509','202510','202601','202602','202603','202604','202605','202606'];MONTHS=MAIN+['202608'];AK=['dong_code','route_id','departure_node','arrival_node'];BK=['dong_code','departure_node','arrival_node']
SPEED=ROOT/'upload/2026년 6월 서울시 차량통행속도.xlsx';MAPPING=ROOT/'upload/서울특별시 교통소통 표준링크 매핑정보_20250306.xlsx';RIDER=ROOT/'upload/2026년_버스노선별_정류장별_시간대별_승하차_인원_정보(06월).csv';MASTER=next((ROOT/'m3a_inputs').rglob('서울시버스 정보.zip'))
INTERSECTION=ROOT/'upload/A008_P_20250814.zip';LANE=ROOT/'project_sources/03-A058_L_20260213.zip'
def sha(p):
 with open(p,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def atomic(p,data):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.writing')
 with t.open('wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
 os.replace(t,p);assert p.read_bytes()==data

def save(df,name):
 data=df.to_csv(index=False,float_format='%.15g').encode('utf-8-sig');atomic(OUT/name,gzip.compress(data,mtime=0) if name.endswith('.gz') else data)
def dump(v,n):atomic(OUT/n,(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode())
def read(p):return pd.read_csv(p,dtype={k:str for k in AK+['month','snapshot','node_id','source_id']},low_memory=False)

def units():
 b=read(M2/'fixed_segment_roster.csv');assert len(b)==758 and b.is_diagnostic43.sum()==43;return b

def read_shape(path):
 with zipfile.ZipFile(path) as z:
  dbf=z.read(next(n for n in z.namelist() if n.endswith('.dbf')));shp=z.read(next(n for n in z.namelist() if n.endswith('.shp')));prj=z.read(next(n for n in z.namelist() if n.endswith('.prj'))).decode();cpg=z.read(next(n for n in z.namelist() if n.endswith('.cpg'))).decode().strip()
 n,hlen,rlen=struct.unpack_from('<IHH',dbf,4);fields=[];j=32
 while dbf[j]!=13:
  q=dbf[j:j+32];fields.append((q[:11].split(b'\0')[0].decode(),chr(q[11]),q[16],q[17]));j+=32
 attrs=[]
 for i in range(n):
  row=dbf[hlen+i*rlen:hlen+(i+1)*rlen];j=1;r={'feature_row':i+1,'dbf_deleted':row[:1]==b'*'}
  for k,t,w,dec in fields:r[k]=row[j:j+w].decode('cp949').strip();j+=w
  attrs.append(r)
 typ=struct.unpack_from('<i',shp,32)[0];j=100;geoms=[]
 while j<len(shp):
  recnum,nwords=struct.unpack_from('>ii',shp,j);q=shp[j+8:j+8+2*nwords];tt=struct.unpack_from('<i',q)[0]
  if tt==0:g=[]
  elif tt==1:g=[np.array(struct.unpack_from('<2d',q,4)).reshape(1,2)]
  elif tt==3:
   nr,nv=struct.unpack_from('<2i',q,36);starts=np.frombuffer(q,'<i4',nr,44);xy=np.frombuffer(q,'<f8',nv*2,44+nr*4).reshape(-1,2).copy();g=list(np.split(xy,starts[1:]))
  else:raise ValueError('Unsupported shape record: '+str(tt))
  geoms.append(g);j+=8+2*nwords
 assert len(attrs)==len(geoms)==n
 return pd.DataFrame(attrs),geoms,{'rows':n,'shape_type':typ,'bounds':list(struct.unpack_from('<4d',shp,36)),'fields':fields,'prj':prj,'encoding':cpg,'deleted_rows':sum(x['dbf_deleted'] for x in attrs),'empty_geometries':sum(not x for x in geoms),'multipart_records':sum(len(x)>1 for x in geoms)}
