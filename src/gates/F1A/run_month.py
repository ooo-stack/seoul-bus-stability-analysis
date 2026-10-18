"""F1A monthly independent Core. Frozen linear quantiles and original C2 order."""
from pathlib import Path
import pandas as pd,numpy as np,json,pickle,zipfile,collections,warnings,sys,time,os
R=Path(__file__).resolve().parent.parent;O=R/'f1a_results';W=R/'f1a_work'
# Submission adapter: paths only; the original calculation statements follow.
from seoul_bus_paths import bind as _submission_bind
globals().update(_submission_bind('F1A'))
with open(W/'input_contract.pkl','rb') as f:ALL=pickle.load(f)
K={'time':['노선_ID','출발_정류장_ID','도착_정류장_ID','출발_정류장_순서','도착_정류장_순서'],'count':['노선_ID','정류장_ID','정류장_순서']}
VC={'time':[f'운행시간_{h:02}시' for h in range(24)],'count':[f'버스운행횟수_{h:02}시' for h in range(24)]}
def atomic_npz(p,**arrays):
 tmp=p.with_suffix('.writing.npz')
 with open(tmp,'wb') as f:
  np.savez_compressed(f,**arrays);f.flush();os.fsync(f.fileno())
 with zipfile.ZipFile(tmp) as z:assert z.testzip() is None
 tmp.replace(p)
def dump(x,p):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=lambda v:v.item() if isinstance(v,np.generic) else str(v)))
def linear_rows(sorted_rows,n,p):
 t=(n-1)*p;lo=np.floor(t).astype(int);hi=np.ceil(t).astype(int);f=t-lo;ix=np.arange(len(n));a=sorted_rows[ix,lo];b=sorted_rows[ix,hi];d=b-a;v=a+d*f;ix2=f>=.5;v[ix2]=b[ix2]-d[ix2]*(1-f[ix2]);return v

def run(month):
 start=time.time();cfg=ALL['config'][month];ma=ALL['masters'][cfg['snapshot']];days=cfg['days'];D=len(days);di={d:i for i,d in enumerate(days)};out=O/'core_checkpoints'/month;out.mkdir(parents=True,exist_ok=True);qa=[];pool=[];routehistory=[];stats={};keys=[];index={};cap=100000
 panel=np.full((cap,D,24),np.nan,np.float64);present=np.zeros((cap,D),bool);normal_candidate_keys=set();held_coordinate_keys=set();two3keys=set()
 def audit(stage,kind,q,mask=None,denom=None,scope='common_planned',note=''):
  n=len(q) if mask is None else int(np.asarray(mask).sum());qa.append({'month':month,'data_kind':kind,'scope':scope,'stage':stage,'rows':n,'denominator_rows':denom if denom is not None else len(q),'rate_pct':100*n/(denom if denom is not None else len(q)) if (denom if denom is not None else len(q)) else np.nan,'note':note})
 def batches(kind):
  sidroutes=set();mainroutes=set();unknownroutes=set();calrows=unkrows=commonrows=commonunk=0
  for job in cfg['jobs']:
   if job['kind']!=kind:continue
   cols=['기준_날짜']+K[kind]+VC[kind];dtype={c:str for c in ['기준_날짜']+K[kind]};dtype.update({c:np.float64 for c in VC[kind]});z=zipfile.ZipFile(job['path']);offset=0
   for df in pd.read_csv(z.open(job['member']),encoding='cp949',usecols=cols,dtype=dtype,keep_default_na=False,na_values={c:[''] for c in VC[kind]},chunksize=100000):
    assert len(df.index)==0 or df.index[0]==offset;offset+=len(df)
    q=df[df['기준_날짜'].str[:6]==month].copy();calrows+=len(q);sidroutes.update(q['노선_ID']);known=q['노선_ID'].map(ma['types']).fillna('').ne('');unknownroutes.update(q.loc[~known,'노선_ID']);mainroutes.update(q.loc[q['노선_ID'].isin(ma['allowed']),'노선_ID']);unkrows+=int((~known).sum())
    q=q[q['기준_날짜'].isin(di)].copy();base=len(q);commonrows+=base;known=q['노선_ID'].map(ma['types']).fillna('').ne('');commonunk+=int((~known).sum());audit('raw_common_rows',kind,q)
    drops=ALL['skip'].get(job['source_id'],{});reasons=pd.Series((q.index+2).map(drops),index=q.index);audit('exact_duplicate_removed',kind,q,reasons.eq('exact_duplicate'),base);q=q[~reasons.eq('exact_duplicate')].copy();reasons=pd.Series((q.index+2).map(drops),index=q.index);audit('conflict_rows_after_dedup_held',kind,q,reasons.eq('conflict_pending'),base);q=q[~reasons.eq('conflict_pending')].copy()
    ids=K[kind][:3] if kind=='time' else K[kind][:2];seq=K[kind][3:] if kind=='time' else K[kind][2:]
    special=q['노선_ID'].eq('0')
    if kind=='count':special|=q['정류장_ID'].str.fullmatch(r'\d{4}')|q['정류장_순서'].eq('999')
    audit('special_ID_held',kind,q,special,base);q=q[~special].copy()
    ok=pd.Series(True,index=q.index)
    for c in ids:ok&=q[c].str.fullmatch(r'\d{9}')
    audit('unknown_ID_format_held',kind,q,~ok,base);q=q[ok].copy()
    integer=pd.Series(True,index=q.index)
    for c in seq:integer&=q[c].str.fullmatch(r'[+-]?\d+')
    audit('noninteger_sequence_held',kind,q,~integer,base);q=q[integer].copy();sv=q[seq].astype(np.int64);positive=sv.gt(0).all(axis=1);audit('nonpositive_sequence_held',kind,q,~positive,base);q=q[positive].copy();sv=sv.loc[q.index]
    if kind=='time':
     adj=(sv.iloc[:,1]-sv.iloc[:,0]).eq(1);audit('nonadjacent_sequence_held',kind,q,~adj,base);q=q[adj].copy()
     flag=q['출발_정류장_순서'].eq('2')&q['도착_정류장_순서'].eq('3');two3keys.update(q.loc[flag,K[kind]].itertuples(index=False,name=None));audit('fixed_2_to_3_excluded',kind,q,flag,base);q=q[~flag].copy()
    known=q['노선_ID'].map(ma['types']).fillna('').ne('');audit('unknown_type_after_structure_excluded',kind,q,~known,base);allowed=q['노선_ID'].isin(ma['allowed']);audit('non_Main_type_or_unknown_excluded',kind,q,~allowed,base);q=q[allowed].copy();pbase=len(q)
    if kind=='time':
     dep=(q['노선_ID']+'|'+q['출발_정류장_ID']+'|'+q['출발_정류장_순서']).isin(ma['triples']);arr=(q['노선_ID']+'|'+q['도착_정류장_ID']+'|'+q['도착_정류장_순서']).isin(ma['triples']);match=dep&arr
     audit('departure_exact_master_unmatched',kind,q,~dep,pbase);audit('arrival_exact_master_unmatched',kind,q,~arr,pbase)
    else:match=(q['노선_ID']+'|'+q['정류장_ID']+'|'+q['정류장_순서']).isin(ma['triples'])
    audit('exact_master_any_unmatched',kind,q,~match,pbase,note='denominator: structurally valid Main type rows after fixed exclusions');q=q[match].copy()
    if len(q):yield q
  stats[kind]={'calendar_raw_rows':calrows,'calendar_route_IDs':len(sidroutes),'calendar_Main_observed_IDs':len(mainroutes),'calendar_unknown_type_IDs':len(unknownroutes),'calendar_unknown_type_rows':unkrows,'calendar_unknown_type_row_pct':100*unkrows/calrows,'common_raw_rows':commonrows,'common_unknown_type_rows':commonunk,'common_unknown_type_row_pct':100*commonunk/commonrows,'master_Main_IDs':len(ma['allowed']),'master_unknown_type_IDs':sum(not t for t in ma['types'].values())}
 for q in batches('time'):
  kvals=list(q[K['time']].itertuples(index=False,name=None));new=list(dict.fromkeys(k for k in kvals if k not in index))
  for k in new:index[k]=len(keys);keys.append(k)
  assert len(keys)<=cap,'Panel capacity unexpectedly exceeded; no silent truncation'
  ix=np.fromiter((index[k] for k in kvals),np.int32,len(kvals));dx=q['기준_날짜'].map(di).to_numpy(np.int32);assert len(np.unique(ix*D+dx))==len(ix) and not present[ix,dx].any(),'Unresolved duplicate observation'
  a=q[VC['time']].to_numpy(np.float64);assert not (np.isfinite(a)&(a<0)).any(),'Unexpected negative time value'
  audit('time_zero_cells_after_master', 'time',q,note=str(int((a==0).sum())));qa[-1]['cells']=int((a==0).sum());qa[-1]['rows']=0;qa[-1]['rate_pct']=np.nan
  a[(a<=0)|~np.isfinite(a)]=np.nan;pool.append(a[np.isfinite(a)]);panel[ix,dx,:]=a;present[ix,dx]=True
  coordinate=q['출발_정류장_ID'].isin(ma['held_nodes'])|q['도착_정류장_ID'].isin(ma['held_nodes']);held_coordinate_keys.update(q.loc[coordinate,K['time']].itertuples(index=False,name=None));audit('coordinate_held_time_rows_before_repetition', 'time',q,coordinate,len(q))
 S=len(keys);panel=panel[:S].copy();present=present[:S].copy();keyframe=pd.DataFrame(keys,columns=K['time']);pos=np.isfinite(panel);n=pos.sum(axis=1);weekly=[];core=n>=cfg['L']
 for week,minimum in sorted(cfg['week_min'].items()):
  wi=[di[d] for d in days if cfg['day_weeks'][d]==week];wc=pos[:,wi,:].sum(axis=1);weekly.append(wc);core&=wc>=minimum
 si,hi=np.where(core);assert len(si)>0;X=panel.transpose(0,2,1)[si,hi,:];count=n[si,hi];sortedX=np.sort(np.where(np.isfinite(X),X,np.inf),axis=1);p50=linear_rows(sortedX,count,.5);p90=linear_rows(sortedX,count,.9);u=p90-p50
 sample=np.linspace(0,len(X)-1,min(1000,len(X)),dtype=int);assert np.allclose(p50[sample],np.nanquantile(X[sample],.5,axis=1,method='linear'),atol=1e-10,rtol=1e-12) and np.allclose(p90[sample],np.nanquantile(X[sample],.9,axis=1,method='linear'),atol=1e-10,rtol=1e-12)
 assert (u>=-1e-10).all() and (count>=cfg['L']).all()
 dep=keyframe['출발_정류장_ID'].map(ma['inside']).fillna('');arr=keyframe['도착_정류장_ID'].map(ma['inside']).fillna('');strictkey=dep.ne('')&arr.ne('');strict=strictkey.to_numpy()[si]
 keyframe['dep_dong_code']=dep;keyframe['arr_dong_code']=arr;keyframe['spatial_coordinate_hold']=keyframe['출발_정류장_ID'].isin(ma['held_nodes'])|keyframe['도착_정류장_ID'].isin(ma['held_nodes']);keyframe.to_csv(out/'segment_keys.csv.gz',index=False,compression='gzip',encoding='utf-8-sig')
 weekvalues=np.column_stack([a[si,hi] for a in weekly]).astype(np.uint8)
 atomic_npz(out/'segment_hour_core.npz',segment_index=si.astype(np.int32),hour=hi.astype(np.uint8),positive_days=count.astype(np.uint8),weekly_positive_days=weekvalues,week_names=np.array(sorted(cfg['week_min'])),P50=p50,P90=p90,U=u,strict=strict)
 # Tail QA on positive values; fixed policy and structure exclusions, no new trimming.
 tails=[]
 for scope,values in [('policy_after_master_before_repetition',np.concatenate(pool)),('policy_time_Core',X[np.isfinite(X)])]:
  qs=np.quantile(values,[.5,.9,.99,.999],method='linear');tails.append({'month':month,'status':'calculated','scope':scope,'positive_value_cells':len(values),'P50_sec':qs[0],'P90_sec':qs[1],'P99_sec':qs[2],'P99_9_sec':qs[3],'max_sec':values.max()})
 pd.DataFrame(tails).to_csv(out/'tail.csv',index=False,encoding='utf-8-sig');del X,sortedX,pool,panel,pos,weekly
 # Supply roster uses BOTH policy Core endpoints, independently of Strict opposite endpoint.
 validsegments=np.flatnonzero(core.any(axis=1));ep=[]
 for node,seq,dong in [('출발_정류장_ID','출발_정류장_순서','dep_dong_code'),('도착_정류장_ID','도착_정류장_순서','arr_dong_code')]:
  a=keyframe.iloc[validsegments][['노선_ID',node,seq,dong]].copy();a.columns=['route_id','node_id','sequence','dong_code'];ep.append(a)
 endpoints=pd.concat(ep).drop_duplicates();roster=endpoints[endpoints.dong_code.ne('')].copy().reset_index(drop=True);assert not roster.duplicated(['route_id','node_id','sequence']).any()
 rosterIndex={tuple(k):i for i,k in enumerate(roster[['route_id','node_id','sequence']].itertuples(index=False,name=None))};cn=len(roster);cp=np.full((cn,D,24),np.nan);cpres=np.zeros((cn,D),bool)
 for q in batches('count'):
  ii=np.fromiter((rosterIndex.get(k,-1) for k in q[K['count']].itertuples(index=False,name=None)),np.int32,len(q));matched=ii>=0;a=q.loc[matched,VC['count']].to_numpy(np.float64);ix=ii[matched];dx=q.loc[matched,'기준_날짜'].map(di).to_numpy(np.int32)
  assert not cpres[ix,dx].any() and len(np.unique(ix*D+dx))==len(ix),'Unresolved count duplicate'
  finite=np.isfinite(a);assert not (a[finite]<0).any() and np.equal(a[finite],np.floor(a[finite])).all(),'Count definition incompatible';assert not (a[finite]==0).any(),'New explicit zero requires structural verification per F0D'
  cp[ix,dx,:]=a;cpres[ix,dx]=True
 roster['rs_id']=pd.factorize(pd.MultiIndex.from_frame(roster[['route_id','node_id']]))[0];rs=roster.drop_duplicates('rs_id').sort_values('rs_id').reset_index(drop=True);nr=len(rs);vs=np.full((nr,D,24),np.nan);partial=0;seqsizes=roster.groupby('rs_id').size()
 for rsid,ixs in roster.groupby('rs_id').indices.items():
  a=cp[ixs];nv=np.isfinite(a).sum(axis=0);total=np.nansum(a,axis=0);total[nv==0]=np.nan;vs[rsid]=total;partial+=int(((nv>0)&(nv<len(ixs))).sum())
 with warnings.catch_warnings():warnings.simplefilter('ignore',RuntimeWarning);representative=np.nanmedian(vs,axis=1)
 observed=np.isfinite(vs).sum(axis=1);positive=(vs>0).sum(axis=1);expected=nr*24
 atomic_npz(out/'supply_route_stop_hour.npz',representative_count=representative,observed_days=observed.astype(np.uint8),positive_days=positive.astype(np.uint8));rs.to_csv(out/'supply_route_stop_keys.csv.gz',index=False,compression='gzip',encoding='utf-8-sig');roster.to_csv(out/'supply_roster_positions.csv.gz',index=False,compression='gzip',encoding='utf-8-sig')
 B=ALL['boundary'];metrics=B[['ADMI_CD','EMD_CD','ADMI_NM']].rename(columns={'ADMI_CD':'dong_code','EMD_CD':'dong_code10','ADMI_NM':'dong_name'}).copy().set_index('dong_code');metrics['month']=month;metrics['snapshot']=cfg['snapshot'];metrics['N_planned']=cfg['N'];metrics['common_days']=D;metrics['L_main']=cfg['L'];metrics['month_role']='design_month' if month=='202608' else 'temporal_reproducibility_month'
 spatial=pd.DataFrame({'segment_index':si[strict],'hour':hi[strict],'U':u[strict],'dong_code':arr.iloc[si[strict]].to_numpy()});sg=spatial.groupby('dong_code');metrics['U_sec']=sg.U.median();metrics['strict_Core_combinations']=sg.size();metrics['strict_segment_count']=spatial.drop_duplicates(['dong_code','segment_index']).groupby('dong_code').size()
 keystrict=keyframe.iloc[np.unique(si[strict])].copy();metrics['strict_route_count']=keystrict.groupby('arr_dong_code')['노선_ID'].nunique();metrics['strict_arrival_stop_count']=keystrict.groupby('arr_dong_code')['도착_정류장_ID'].nunique();metrics['strict_stop_pair_count']=keystrict.drop_duplicates(['arr_dong_code','출발_정류장_ID','도착_정류장_ID']).groupby('arr_dong_code').size()
 reps=pd.DataFrame(representative);reps['dong_code']=rs.dong_code;reps['node_id']=rs.node_id;sumrs=reps[list(range(24))].sum(axis=1,min_count=1);reps['observed_representative_sum']=sumrs;st=reps.groupby(['dong_code','node_id']).observed_representative_sum.sum(min_count=1);metrics['C2_count']=st.groupby(level=0).median();metrics['supply_target_stop_count']=roster.groupby('dong_code').node_id.nunique();metrics['supply_observed_stop_count']=st.dropna().groupby(level=0).size();metrics['supply_route_count']=roster.groupby('dong_code').route_id.nunique()
 ov=pd.DataFrame({'dong_code':np.repeat(rs.dong_code.to_numpy(),24),'observed_days':observed.ravel(),'positive_days':positive.ravel(),'rep_valid':np.isfinite(representative).ravel()});og=ov.groupby('dong_code');metrics['supply_expected_hour_cells']=og.size();metrics['supply_observed_hour_cells']=og.rep_valid.sum();metrics['supply_observed_hour_cells_pct']=100*metrics.supply_observed_hour_cells/metrics.supply_expected_hour_cells;metrics['supply_observed_days_min']=ov[ov.rep_valid].groupby('dong_code').observed_days.min();metrics['supply_observed_days_median']=ov[ov.rep_valid].groupby('dong_code').observed_days.median()
 countcols=['strict_Core_combinations','strict_segment_count','strict_route_count','strict_arrival_stop_count','strict_stop_pair_count','supply_target_stop_count','supply_observed_stop_count','supply_route_count','supply_expected_hour_cells','supply_observed_hour_cells']
 metrics[countcols]=metrics[countcols].fillna(0).astype(int);metrics['U_missing_reason']=np.where(metrics.U_sec.isna(),'no_eligible_Strict_Core','');metrics['C2_missing_reason']=np.where(metrics.C2_count.isna(),'no_observed_supply_roster','')
 for field,label in [('C2_count','C2'),('U_sec','U')]:metrics[label+'_percentile']=100*metrics[field].round(8).rank(method='average',pct=True);metrics[label+'_percentile_denominator']=metrics[field].notna().sum()
 both=metrics.C2_count.notna()&metrics.U_sec.notna();candidate=pd.Series(pd.NA,index=metrics.index,dtype='boolean');candidate[both]=(metrics.loc[both,'C2_percentile']>=75)&(metrics.loc[both,'U_percentile']>=75);metrics['candidate']=candidate;metrics.reset_index().to_csv(out/'dong_metrics.csv',index=False,encoding='utf-8-sig',float_format='%.15g')
 samplecounts={'month':month,'snapshot':cfg['snapshot'],'N_planned':cfg['N'],'common_days':D,'L_main':cfg['L'],'policy_master_matched_segments':S,'policy_time_Core_combinations':int(len(si)),'policy_time_Core_segments':int(len(validsegments)),'strict_Core_combinations':int(strict.sum()),'strict_Core_segments':int(len(keystrict)),'coordinate_held_NODEs':len(ma['held_nodes']),'coordinate_held_segments_before_repetition':len(held_coordinate_keys),'coordinate_held_policy_Core_segments':int(keyframe.iloc[validsegments].spatial_coordinate_hold.sum()),'fixed_2_to_3_segments_excluded':len(two3keys),'coordinate_held_supply_endpoint_stops':int(endpoints.loc[endpoints.node_id.isin(ma['held_nodes']),'node_id'].nunique()),'supply_roster_positions':cn,'supply_route_stops':nr,'supply_repeated_sequence_route_stops':int((seqsizes>1).sum()),'supply_partial_sequence_date_hour_cells':partial,'supply_roster_date_rows_possible':cn*D,'supply_roster_date_rows_present':int(cpres.sum()),'supply_roster_date_rows_absent':int((~cpres).sum()),'supply_present_row_blank_hour_cells':int((np.isnan(cp)&cpres[:,:,None]).sum()),'supply_valid_representative_hour_cells':int(np.isfinite(representative).sum()),'supply_expected_representative_hour_cells':expected,'supply_representative_hour_cells_observed_fewer_than_L':int(((observed<cfg['L'])&np.isfinite(representative)).sum()),'seconds':time.time()-start}
 dump(samplecounts,out/'sample_counts.json');dump(stats,out/'route_population.json');pd.DataFrame(qa).to_csv(out/'qa_chunks.csv',index=False,encoding='utf-8-sig');print('DONE',month,'Core',len(si),'Strict',strict.sum(),'U',metrics.U_sec.notna().sum(),'C2',metrics.C2_count.notna().sum(),'candidate',int(candidate.sum()),'sec',round(time.time()-start,1),flush=True)
 return month
if __name__=='__main__':run(sys.argv[1])
