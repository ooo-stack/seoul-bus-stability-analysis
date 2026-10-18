import struct
import numpy as np,pandas as pd
from matplotlib.path import Path
def read_shp(base):
 b=base.with_suffix('.dbf').read_bytes();n,h,r=struct.unpack_from('<IHH',b,4);fields=[];j=32
 while b[j]!=13:
  q=b[j:j+32];fields.append((q[:11].split(b'\0')[0].decode(),q[16]));j+=32
 rows=[]
 for i in range(n):
  q=b[h+i*r:h+(i+1)*r];j=1;d={}
  for k,w in fields:d[k]=q[j:j+w].decode('cp949').strip();j+=w
  rows.append(d)
 b=base.with_suffix('.shp').read_bytes();j=100;polys=[]
 while j<len(b):
  _,nw=struct.unpack_from('>ii',b,j);q=b[j+8:j+8+2*nw];assert struct.unpack_from('<i',q)[0]==5
  nr,nv=struct.unpack_from('<2i',q,36);ss=np.frombuffer(q,'<i4',nr,44);xy=np.frombuffer(q,'<f8',nv*2,44+nr*4).reshape(-1,2).copy();polys.append(list(np.split(xy,ss[1:])));j+=8+2*nw
 assert len(polys)==n
 return pd.DataFrame(rows),polys

def locate(xy,codes,polys):
 out=np.full(len(xy),'',object);hits=np.zeros(len(xy),int);edgeall=np.zeros(len(xy),bool)
 for code,rings in sorted(zip(codes,polys)):
  pts=np.vstack(rings);lo=pts.min(axis=0);hi=pts.max(axis=0);ix=np.flatnonzero(np.isfinite(xy).all(axis=1)&(xy>=lo-1e-6).all(axis=1)&(xy<=hi+1e-6).all(axis=1));p=xy[ix];inside=np.zeros(len(ix),bool);edge=inside.copy()
  for r in rings:
   path=Path(r);inside^=path.contains_points(p);edge|=path.contains_points(p,radius=2e-6)!=path.contains_points(p,radius=-2e-6)
  ids=ix[inside|edge];out[ids[out[ids]=='']]=code;hits[ids]+=1;edgeall[ix[edge]]=True
 return out,hits,edgeall