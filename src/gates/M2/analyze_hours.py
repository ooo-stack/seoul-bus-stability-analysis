from common import *
b=units();save(b[LABELS+['V','K','R']],'fixed_segment_roster.csv')
h=read(M/'route_segment_hour_folded.csv.gz').merge(b[LABELS],on=AK,how='inner',validate='many_to_one')
assert not h.duplicated(['month','segment_id','hour']).any()
assert h.high_instability_hour.dtype==bool
ix=pd.MultiIndex.from_product([ALL,b.segment_id,range(24)],names=['month','segment_id','hour'])
p=h.set_index(['month','segment_id','hour'])[['U_hour_sec','U_hour_percentile','high_instability_hour','source_sequence_combinations','source_core_rows']].reindex(ix).reset_index().merge(b[LABELS],on='segment_id',validate='many_to_one')
p['valid']=p.U_hour_sec.notna()&p.U_hour_percentile.notna();p['month_role']=p.month.map(lambda m:'held_date' if m in HELD else 'auxiliary_design' if m=='202608' else 'Main_replication');p['status_reason']=np.where(p.valid,'valid',np.where(p.month.isin(HELD),'held_date','no_stored_Strict_Core_hour'))
p['high_instability_hour']=p.high_instability_hour.astype('boolean');assert p.loc[~p.valid,'high_instability_hour'].isna().all()
save(p,'segment_hour_monthly_panel.csv.gz')
def recur(x,keys):
 rows=[]
 for key,g in x.groupby(keys,sort=False):
  key=key if isinstance(key,tuple) else (key,);r=dict(zip(keys,key))
  for ms,suf in [(MAIN,''),([m for m in MAIN if m!='202601'],'_noJan')]:
   v=g[g.month.isin(ms)&g.valid];r['V_h'+suf]=len(v);r['K_h'+suf]=int(v.high_instability_hour.fillna(False).sum());r['R_h'+suf]=r['K_h'+suf]/len(v) if len(v) else np.nan;r['U_median_h_sec'+suf]=v.U_hour_sec.median();r['valid_months'+suf]=','.join(sorted(v.month))
  rows.append(r)
 return pd.DataFrame(rows)
r=recur(p,['segment_id','hour']).merge(b[LABELS],on='segment_id',validate='many_to_one')
save(r,'segment_hour_recurrence.csv')
summary=[];peakkeys=set()
for sid,g in r.groupby('segment_id',sort=False):
 v=g[g.V_h.gt(0)];maxr=v.R_h.max();peaks=v[v.R_h.eq(maxr)];s={'segment_id':sid,'evaluated_hours':len(v),'R_h_max':maxr,'R_h_max_hours':','.join('%02d'%i for i in peaks.hour),'R_h_max_hour_count':len(peaks),'R_h_max_K_V':';'.join('%02d:%d/%d'%(x.hour,x.K_h,x.V_h) for x in peaks.itertuples()),'hourly_K_V_all':json.dumps({str(x.hour):{'K':x.K_h,'V':x.V_h} for x in g.itertuples()})}
 for x in peaks.itertuples():peakkeys.add((sid,x.hour))
 for suf in ['','_noJan']:
  vv=g[g['V_h'+suf].gt(0)];mm=vv['R_h'+suf].max();hh=vv[vv['R_h'+suf].eq(mm)];s['max_hours'+suf]=','.join('%02d'%i for i in hh.hour)
 summary.append(s)
s=pd.DataFrame(summary).merge(b[LABELS],on='segment_id',validate='one_to_one');save(s,'segment_hour_summary.csv')
rr=r[r.is_diagnostic43].sort_values(['diagnostic_no','hour']);heat=rr.pivot(index='segment_id',columns='hour',values='R_h').reindex(b[b.is_diagnostic43].sort_values('diagnostic_no').segment_id);heat.columns=['%02d시'%h for h in heat.columns];save(heat.reset_index(),'diagnostic43_hourly_heatmap.csv')
# Explicit distributions, with diagonal subset membership rather than independent groups.
rows=[]
for scope,sub in [('diagnostic43',r[r.is_diagnostic43]),('background758',r)]:
 for dong in ['ALL']+sorted(b.dong_code.unique()):
  q=sub if dong=='ALL' else sub[sub.dong_code.eq(dong)]
  for hr,g in q.groupby('hour'):
   v=g[g.V_h.gt(0)];z={'scope':scope,'dong_code':dong,'hour':hr,'total_segments':len(g),'evaluated_segments':len(v),'V_h_median':v.V_h.median(),'V_h_min':v.V_h.min(),'V_h_max':v.V_h.max(),'segments_with_R_h_at_own_max':sum((sid,hr) in peakkeys for sid in g.segment_id)}
   for val in ['R_h','U_median_h_sec']:
    for quant,label in [(.25,'P25'),(.5,'median'),(.75,'P75'),(.9,'P90'),(1,'max')]:z[val+'_'+label]=v[val].quantile(quant)
   rows.append(z)
save(pd.DataFrame(rows),'background758_hourly_summary.csv')
# Pair-level median from every background route, not only diagnostic routes.
bh=h.groupby(['month']+BK+['hour'],sort=False).agg(U_hour_sec=('U_hour_sec','median'),n_routes=('route_id','nunique'),contributing_route_ids=('route_id',lambda a:','.join(sorted(set(a))))).reset_index();ref=read(M/'analysis_inputs/strict_U_reference.csv.gz');bh['U_hour_percentile']=np.nan
for month,idx in bh.groupby('month').groups.items():
 z=ref[ref.month.eq(month)];bh.loc[idx,'U_hour_percentile']=np.interp(np.round(bh.loc[idx,'U_hour_sec'],8),z.U_rounded,z.average_tie_percentile)
bh['high_instability_hour']=bh.U_hour_percentile.ge(75);bh['valid']=True;save(bh,'stop_pair_hour_monthly.csv.gz')
comp=h.merge(bh,on=['month']+BK+['hour'],suffixes=('_A','_B'),validate='many_to_one')
comp['U_A_minus_B_sec']=comp.U_hour_sec_A-comp.U_hour_sec_B
comp['flag_case']=np.select([comp.high_instability_hour_A&comp.high_instability_hour_B,comp.high_instability_hour_A&~comp.high_instability_hour_B,~comp.high_instability_hour_A&comp.high_instability_hour_B],['both_high','A_only_high','B_only_high'],default='neither_high')
comp['flag_agrees']=comp.high_instability_hour_A.eq(comp.high_instability_hour_B);comp['comparison_scope']=np.where(comp.month.eq('202608'),'auxiliary','Main');save(comp,'stop_pair_hourly_comparison.csv')
# Same-month, same-hour layer distributions for background comparison.
lay=[]
for (month,dong,hr),g in h.groupby(['month','dong_code','hour']):
 for scope,q in [('diagnostic43',g[g.is_diagnostic43]),('background758',g)]:
  lay.append({'month':month,'dong_code':dong,'hour':hr,'scope':scope,'evaluated_segments':len(q),'high_segments':int(q.high_instability_hour.sum()),'U_median_sec':q.U_hour_sec.median(),'U_P25_sec':q.U_hour_sec.quantile(.25),'U_P75_sec':q.U_hour_sec.quantile(.75)})
save(pd.DataFrame(lay),'hourly_month_dong_background.csv')
# Prespecified hour pair common-month comparisons, AM/PM and all other hour pairs alike.
common=[]
for sid,g in h[h.month.isin(MAIN)&h.is_diagnostic43].groupby('segment_id'):
 U=g.pivot(index='month',columns='hour',values='U_hour_sec');HI=g.pivot(index='month',columns='hour',values='high_instability_hour')
 for a in range(24):
  for bb in range(a+1,24):
   if a not in U or bb not in U:continue
   q=U[[a,bb]].dropna()
   common.append({'segment_id':sid,'hour_A':a,'hour_B':bb,'common_month_count':len(q),'common_months':','.join(q.index),'U_A_common_median_sec':q[a].median(),'U_B_common_median_sec':q[bb].median(),'R_A_common':HI.loc[q.index,a].mean() if len(q) else np.nan,'R_B_common':HI.loc[q.index,bb].mean() if len(q) else np.nan})
save(pd.DataFrame(common),'hour_pair_common_month_comparison.csv')
sens=rr.copy();sens['level']='hour';sens['R_change_noJan_minus_Main']=sens.R_h_noJan-sens.R_h;sens['U_change_noJan_minus_Main_sec']=sens.U_median_h_sec_noJan-sens.U_median_h_sec;save(sens,'hour_january_sensitivity.csv')
print('HOURS_READY',len(p),'monthly panel;',len(r),'recurrence cells;',len(comp),'A-B monthly hour comparisons',flush=True)
