"""Execute the pre-frozen microscopic exploratory rule on restored Core U values."""
from pathlib import Path
import json,hashlib,gzip,os
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parent;INP=ROOT/'analysis_inputs'
# Submission adapter: paths only; the original calculation statements follow.
from seoul_bus_paths import bind as _submission_bind
globals().update(_submission_bind('M1'))
MAIN=['202509','202510','202601','202602','202603','202604','202605','202606']
MONTHS=['202509','202510','202511','202512','202601','202602','202603','202604','202605','202606','202607','202608']
HELD={'202511','202512','202607'}
DONG={'11140520':'소공동','11140570':'필동','11620695':'신림동','11680510':'신사동(강남구)','11680610':'대치2동','11680660':'개포1동','11710650':'잠실본동','11710710':'잠실6동','11710720':'잠실7동'}
AK=['dong_code','route_id','departure_node','arrival_node'];BK=['dong_code','departure_node','arrival_node']
freeze=json.loads((ROOT/'freeze_record.json').read_text());assert hashlib.sha256((ROOT/'Gate3M1_rule_freeze.md').read_bytes()).hexdigest()==freeze['rule_sha256']
h=pd.read_csv(INP/'target_hour_core.csv.gz',dtype={c:str for c in ['month','snapshot','dong_code','route_id','departure_node','arrival_node','departure_sequence','arrival_sequence']},keep_default_na=False,low_memory=False)
ref=pd.read_csv(INP/'strict_U_reference.csv.gz',dtype={'month':str})
presence=pd.read_csv(INP/'strict_unit_presence.csv.gz',dtype=str,keep_default_na=False)
def pct(month,values):
 r=ref[ref.month.eq(month)];return np.interp(np.round(np.asarray(values,dtype=float),8),r.U_rounded,r.average_tie_percentile)
def join_unique(values):return ' | '.join(sorted({str(v) for v in values if str(v)}))
def write(df,name):
 data=df.to_csv(index=False,float_format='%.10g').encode('utf-8-sig');blob=gzip.compress(data,mtime=0) if name.endswith('.gz') else data
 target=ROOT/name;temp=ROOT/(name+'.tmp')
 with temp.open('wb') as f:f.write(blob);f.flush();os.fsync(f.fileno())
 os.replace(temp,target)
 if name.endswith('.gz'):assert gzip.decompress(target.read_bytes())==data
assert set(h.dong_code)<=set(DONG)
# Preserve original sequence-key/hour observations for the next Gate.
write(h,'segment_hour_detail.csv.gz')
h['sequence_pair']=h.departure_sequence+'>'+h.arrival_sequence
ah=h.groupby(['month']+AK+['hour'],sort=False).agg(U_hour_sec=('U_sec','median'),source_sequence_combinations=('sequence_pair','nunique'),source_core_rows=('U_sec','size')).reset_index()
ah['U_hour_percentile']=np.nan
for m,idx in ah.groupby('month').groups.items():ah.loc[idx,'U_hour_percentile']=pct(m,ah.loc[idx,'U_hour_sec'])
ah['high_instability_hour']=ah.U_hour_percentile.ge(75)
write(ah,'route_segment_hour_folded.csv.gz')
a=ah.groupby(['month']+AK,sort=False).agg(U_sec=('U_hour_sec','median'),valid_hours=('hour','nunique'),high_instability_hours=('high_instability_hour','sum'),max_sequence_combinations_per_hour=('source_sequence_combinations','max'),source_core_hour_rows=('source_core_rows','sum')).reset_index()
details=h.groupby(['month']+AK,sort=False).agg(snapshot=('snapshot','first'),dong_name=('dong_name','first'),route_name=('route_name',join_unique),route_type=('route_type',join_unique),departure_name=('departure_name',join_unique),arrival_name=('arrival_name',join_unique),sequence_pairs=('sequence_pair',join_unique)).reset_index()
a=a.merge(details,on=['month']+AK,validate='one_to_one')
b=a.groupby(['month']+BK,sort=False).agg(U_sec=('U_sec','median'),valid_routes=('route_id','nunique'),route_ids=('route_id',join_unique),route_names=('route_name',join_unique),snapshot=('snapshot','first'),dong_name=('dong_name','first'),departure_name=('departure_name',join_unique),arrival_name=('arrival_name',join_unique)).reset_index()
for df in [a,b]:
 df['U_percentile']=np.nan
 for m,idx in df.groupby('month').groups.items():df.loc[idx,'U_percentile']=pct(m,df.loc[idx,'U_sec'])
 df['high_instability_month']=df.U_percentile.ge(75).astype('boolean')
 df['segment_length_m']=np.nan;df['length_status']='verified_physical_segment_length_not_available'
def panel(df,keys,kind):
 entities=df[keys].drop_duplicates();grid=entities.merge(pd.DataFrame({'month':MONTHS}),how='cross')
 p=grid.merge(df,on=keys+['month'],how='left',validate='one_to_one')
 p['high_instability_month']=p.high_instability_month.astype('boolean')
 p['unit_type']=kind;p['main_replication_month']=p.month.isin(MAIN);p['january_QA_month']=p.month.isin(set(MAIN)-{'202601'})
 p['analysis_role']=p.month.map(lambda m:'held_date' if m in HELD else ('design_month_auxiliary' if m=='202608' else 'main_replication'))
 p['evaluation_status']=np.where(p.U_sec.notna(),'evaluated','no_valid_core_in_target_dong')
 p.loc[p.month.isin(HELD),'evaluation_status']='held_date'
 # Detect another frozen arrival-dong context without creating a new assignment.
 if kind=='route_segment':lk=['month','route_id','departure_node','arrival_node']
 else:lk=['month','departure_node','arrival_node']
 loc=presence.groupby(lk,sort=False).dong_code.agg(lambda s:','.join(sorted(set(s)))).reset_index(name='observed_arrival_dongs_in_strict_core')
 p=p.merge(loc,on=lk,how='left',validate='many_to_one')
 mask=p.U_sec.isna() & ~p.month.isin(HELD) & p.observed_arrival_dongs_in_strict_core.notna()
 p.loc[mask,'evaluation_status']='different_frozen_arrival_dong'
 p['dong_name']=p.dong_code.map(DONG)
 assert p.loc[p.U_sec.isna(),'high_instability_month'].isna().all()
 assert not p.loc[p.month.isin(HELD),'U_sec'].notna().any()
 return p.sort_values(keys+['month']).reset_index(drop=True)
ap=panel(a,AK,'route_segment');bp=panel(b,BK,'stop_pair')
def recurrence(p,keys):
 out=p[keys].drop_duplicates().set_index(keys)
 for months,suffix in [(MAIN,''),([m for m in MAIN if m!='202601'],'_noJan')]:
  g=p[p.month.isin(months)].groupby(keys,sort=False)
  counts=g.agg(V=('U_sec','count'),K=('high_instability_month',lambda v:int(v.dropna().sum())))
  counts['R']=counts.K.div(counts.V.where(counts.V.ne(0)))
  out=out.join(counts.rename(columns={k:k+suffix for k in ['V','K','R']}))
 for field,prefix in [('U_sec','U'),('U_percentile','percentile'),('high_instability_month','high')]:
  piv=p.pivot(index=keys,columns='month',values=field);piv.columns=[prefix+'_'+m for m in piv.columns];out=out.join(piv)
 evaluated=p[p.U_sec.notna()].sort_values('month')
 repcols=['snapshot','month','departure_name','arrival_name']+(['route_name','route_type'] if 'route_id' in keys else ['route_names'])
 labels=evaluated.groupby(keys,sort=False)[repcols].first().rename(columns={'month':'label_month','snapshot':'label_snapshot'})
 out=out.join(labels).reset_index();out['dong_name']=out.dong_code.map(DONG)
 out['segment_length_m']=np.nan;out['length_status']='verified_physical_segment_length_not_available'
 namehist=evaluated.groupby(keys,sort=False).apply(lambda g:json.dumps({r.month:{'departure':r.departure_name,'arrival':r.arrival_name,'routes':r.route_name if hasattr(r,'route_name') else r.route_names} for r in g.itertuples(index=False)},ensure_ascii=False),include_groups=False).rename('monthly_name_history').reset_index()
 out=out.merge(namehist,on=keys,validate='one_to_one')
 out['U_median_valid_rep_months']=p[p.month.isin(MAIN)].groupby(keys).U_sec.median().reindex(out.set_index(keys).index).to_numpy()
 out['U_percentile_median_valid_rep_months']=p[p.month.isin(MAIN)].groupby(keys).U_percentile.median().reindex(out.set_index(keys).index).to_numpy()
 return out.sort_values(['K','R']+keys,ascending=[False,False]+[True]*len(keys),na_position='last').reset_index(drop=True)
ar=recurrence(ap,AK);br=recurrence(bp,BK)
write(ap,'route_segment_monthly_instability.csv');write(bp,'stop_pair_monthly_instability.csv')
write(ar,'route_segment_recurrence.csv');write(br,'stop_pair_recurrence.csv')
# Comparison of route-level and pair-level monthly flags; shared data, not independent validation.
comp=a.merge(b[['month']+BK+['U_sec','U_percentile','high_instability_month']],on=['month']+BK,suffixes=('_route','_pair'),validate='many_to_one')
comp['both_high']=comp.high_instability_month_route & comp.high_instability_month_pair
comp['route_only_high']=comp.high_instability_month_route & ~comp.high_instability_month_pair
comp['pair_only_high']=~comp.high_instability_month_route & comp.high_instability_month_pair
comp['neither_high']=~comp.high_instability_month_route & ~comp.high_instability_month_pair
cm=[];dcon=[];sens=[];kd=[];vd=[]
for code,name in DONG.items():
 aa=ar[ar.dong_code.eq(code)&ar.V.gt(0)];bb=br[br.dong_code.eq(code)&br.V.gt(0)]
 row={'dong_code':code,'dong_name':name,'analyzable_route_segments':len(aa),'ever_high_route_segments':int(aa.K.gt(0).sum()),'ever_high_route_segment_fraction':float(aa.K.gt(0).mean()),'K_max':int(aa.K.max()),'K_max_group_count':int(aa.K.eq(aa.K.max()).sum()),'route_segments_R_equal_1':int(aa.R.eq(1).sum()),'analyzable_stop_pairs':len(bb),'ever_high_stop_pairs':int(bb.K.gt(0).sum()),'stop_pair_K_max':int(bb.K.max())}
 for q,label in [(.25,'P25'),(.5,'median'),(.75,'P75'),(.9,'P90'),(1,'max')]:row['R_'+label]=float(aa.R.quantile(q))
 cc=comp[comp.dong_code.eq(code)&comp.month.isin(MAIN)]
 for field in ['both_high','route_only_high','pair_only_high','neither_high']:row[field+'_monthly_rows']=int(cc[field].sum())
 row['route_pair_monthly_comparisons']=len(cc);row['route_pair_flag_agreement']=float((cc.high_instability_month_route==cc.high_instability_month_pair).mean())
 for m in MAIN:
  c=cc[cc.month.eq(m)];sA=set(c.loc[c.high_instability_month_route,['departure_node','arrival_node']].itertuples(index=False,name=None));sB=set(b.loc[b.dong_code.eq(code)&b.month.eq(m)&b.high_instability_month,['departure_node','arrival_node']].itertuples(index=False,name=None))
  cm.append({'dong_code':code,'dong_name':name,'month':m,'route_high_projected_pairs':len(sA),'pair_high_pairs':len(sB),'intersection':len(sA&sB),'union':len(sA|sB),'Jaccard':len(sA&sB)/len(sA|sB) if sA|sB else np.nan})
 for typ,df in [('route_segment',aa),('stop_pair',bb)]:
  for k in range(9):kd.append({'dong_code':code,'dong_name':name,'unit_type':typ,'scope':'Main_8','K':k,'units':int(df.K.eq(k).sum())})
  for v in range(9):vd.append({'dong_code':code,'dong_name':name,'unit_type':typ,'scope':'Main_8','V':v,'units':int(df.V.eq(v).sum())})
  keys=AK if typ=='route_segment' else BK
  s=df[df.K.eq(df.K.max())];eligible=df[df.V_noJan.gt(0)];q=eligible[eligible.K_noJan.eq(eligible.K_noJan.max())]
  A=set(s[keys].itertuples(index=False,name=None));B=set(q[keys].itertuples(index=False,name=None))
  sens.append({'dong_code':code,'dong_name':name,'unit_type':typ,'K_max_main':int(df.K.max()),'max_group_main':len(A),'K_max_noJan':int(eligible.K_noJan.max()),'max_group_noJan':len(B),'max_group_intersection':len(A&B),'max_group_union':len(A|B),'max_group_Jaccard':len(A&B)/len(A|B),'main_max_group_with_R_noJan_1':int(s.R_noJan.eq(1).sum()),'main_max_group_not_evaluable_noJan':int(s.V_noJan.eq(0).sum())})
 dcon.append(row)
write(pd.DataFrame(dcon),'dong_segment_concentration.csv')
write(pd.DataFrame(cm),'route_pair_monthly_agreement.csv');write(pd.DataFrame(sens),'january_segment_sensitivity.csv')
write(pd.DataFrame(kd),'segment_K_distribution.csv');write(pd.DataFrame(vd),'segment_V_distribution.csv')
diag=ar.merge(br[BK+['V','K','R']].rename(columns={'V':'pair_V','K':'pair_K','R':'pair_R'}),on=BK,how='left',validate='many_to_one')
write(diag,'segment_diagnostic_list.csv')
heat=pd.concat([ap[['month']+AK+['dong_name','unit_type','U_sec','U_percentile','high_instability_month','evaluation_status']],bp.assign(route_id='')[['month']+AK+['dong_name','unit_type','U_sec','U_percentile','high_instability_month','evaluation_status']]],ignore_index=True)
write(heat,'segment_month_heatmap_data.csv')
# All local K maxima, ties preserved, for report tables rather than a Top-N list.
mx=pd.concat([ar[ar.dong_code.eq(code)&ar.V.gt(0)&ar.K.eq(ar.loc[ar.dong_code.eq(code)&ar.V.gt(0),'K'].max())] for code in DONG],ignore_index=True)
write(mx,'dong_max_recurrence_route_segments.csv')
target_keys=ar[['route_id','departure_node','arrival_node']].drop_duplicates()
target_presence=presence.merge(target_keys,on=['route_id','departure_node','arrival_node'],how='inner',validate='many_to_one')
mobility=target_presence.groupby(['route_id','departure_node','arrival_node']).dong_code.nunique();write(mobility[mobility.gt(1)].reset_index(name='distinct_frozen_arrival_dongs'),'frozen_arrival_dong_changes.csv')
assert ar.K.le(ar.V).all() and br.K.le(br.V).all()
assert ar.loc[ar.V.eq(0),'R'].isna().all() and br.loc[br.V.eq(0),'R'].isna().all()
assert ar.K_noJan.le(ar.V_noJan).all() and br.K_noJan.le(br.V_noJan).all()
for p,keys in [(ap,AK),(bp,BK)]:assert not p.duplicated(keys+['month']).any()
assert set(ar.dong_code)==set(DONG) and set(br.dong_code)==set(DONG)
result={'rule_sha256':freeze['rule_sha256'],'all_target_hour_rows':len(h),'target_route_hour_folded_rows':len(ah),'route_month_evaluated_rows':len(a),'pair_month_evaluated_rows':len(b),'route_units_any_scope':len(ar),'pair_units_any_scope':len(br),'target_dongs':DONG,'held_NA_preserved':True,'August_separate':True,'Core_U_recomputed':False,'new_spatial_assignment':False,'physical_length_available':False,'main_route_units':int(ar.V.gt(0).sum()),'main_pair_units':int(br.V.gt(0).sum())}
(ROOT/'segment_computation_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False));print(pd.DataFrame(dcon).to_string(index=False))
