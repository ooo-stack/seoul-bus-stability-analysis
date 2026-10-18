"""Raw route ID/type accounting only; never modifies monthly results."""
from run_month import ALL,O,W
from pathlib import Path
import pandas as pd,json,collections,zipfile,concurrent.futures
jobs={j['source_id']:j for m in ALL['months'] for j in ALL['config'][m]['jobs']}
def scan(job):
 rows=collections.defaultdict(collections.Counter);z=zipfile.ZipFile(job['path'])
 for d in pd.read_csv(z.open(job['member']),encoding='cp949',usecols=['기준_날짜','노선_ID'],dtype=str,keep_default_na=False,chunksize=200000):
  for m,q in d.groupby(d['기준_날짜'].str[:6],sort=False):
   if m in ALL['months']:rows[m].update(q['노선_ID'].value_counts().to_dict())
 return job['kind'],rows
if __name__=='__main__':
 acc=collections.defaultdict(collections.Counter)
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  for kind,rows in pool.map(scan,jobs.values()):
   for month,c in rows.items():acc[(month,kind)].update(c)
 detailed=[];summary=[]
 for m in ALL['months']:
  ma=ALL['masters'][ALL['config'][m]['snapshot']];union=set()
  for kind in ['time','count']:
   counts=acc[(m,kind)];union|=set(counts);total=sum(counts.values());blank=set();unmatched=set();main=set();normal=set()
   for rid,n in sorted(counts.items()):
    if len(rid)!=9 or not rid.isdigit():cat='special_or_invalid_route_ID'
    elif rid not in ma['types']:cat='route_master_unmatched';normal.add(rid);unmatched.add(rid)
    elif not ma['types'][rid]:cat='historical_type_blank';normal.add(rid);blank.add(rid)
    elif rid in ma['allowed']:cat='verified_Main';normal.add(rid);main.add(rid)
    else:cat='verified_nonMain';normal.add(rid)
    detailed.append({'month':m,'data_kind':kind,'route_id':rid,'historical_route_type':ma['types'].get(rid,''),'category':cat,'calendar_raw_rows':int(n),'calendar_raw_row_pct':100*n/total})
   summary.append({'month':m,'data_kind':kind,'raw_all_distinct_route_ID_values':len(counts),'normal_9digit_route_IDs':len(normal),'observed_Main_route_IDs':len(main),'master_Main_route_IDs':len(ma['allowed']),'unknown_type_normal_route_IDs':len(blank|unmatched),'historical_type_blank_IDs':len(blank),'route_master_unmatched_IDs':len(unmatched),'unknown_type_raw_rows':sum(counts[r] for r in blank|unmatched),'unknown_type_raw_row_pct':100*sum(counts[r] for r in blank|unmatched)/total,'calendar_raw_rows':total})
  for row in summary[-2:]:row['both_data_raw_route_ID_union_count']=len(union);row['both_data_normal_route_ID_union_count']=sum(len(r)==9 and r.isdigit() for r in union)
 pd.DataFrame(detailed).to_csv(O/'route_population_detail.csv',index=False,encoding='utf-8-sig');pd.DataFrame(summary).to_csv(O/'monthly_route_population.csv',index=False,encoding='utf-8-sig');print('ROUTE_POPULATION_QA_COMPLETE',flush=True)
