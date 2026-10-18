"""Restore already computed Core rows from keys and arrays; no reanalysis."""
from pathlib import Path
import argparse,pandas as pd,numpy as np
p=argparse.ArgumentParser();p.add_argument('--month',required=True);p.add_argument('--output',required=True);a=p.parse_args();root=Path(__file__).resolve().parent;d=root/'core_checkpoints'/a.month;keys=pd.read_csv(d/'segment_keys.csv.gz',dtype=str,keep_default_na=False);v=np.load(d/'segment_hour_core.npz');out=keys.iloc[v['segment_index']].reset_index(drop=True);out.insert(0,'month',a.month)
for c,n in [('hour','hour'),('positive_days','positive_days'),('P50','P50_sec'),('P90','P90_sec'),('U','U_sec'),('strict','Strict_Spatial_Core')]:out[n]=v[c]
for i,w in enumerate(v['week_names']):out['weekly_positive_days_'+str(w)]=v['weekly_positive_days'][:,i]
out.to_csv(a.output,index=False,encoding='utf-8-sig',float_format='%.15g',compression='infer');print(len(out),'existing Core rows restored')
