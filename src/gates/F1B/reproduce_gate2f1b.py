#!/usr/bin/env python3
"""Gate 2-F1B: saved F1A monthly results only; no raw data or new thresholds."""
from pathlib import Path
from itertools import combinations
import argparse, hashlib, json, shutil, zipfile
import numpy as np
import pandas as pd

REP = ['202509','202510','202601','202602','202603','202604','202605','202606']
ALL = REP + ['202608']
NOJAN = [m for m in REP if m != '202601']
HELD = ['202511','202512','202607']
SCOPES = {'main_replication_8':REP, 'all_eligible_9_auxiliary':ALL,
          'january_excluded_7_sensitivity':NOJAN}
DTYPES = {'dong_code':str,'dong_code10':str,'month':str,'candidate':'boolean'}

def read(path):
    return pd.read_csv(path, dtype=DTYPES, float_precision='round_trip')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def corr(x,y,spearman=False):
    q=pd.concat([x.rename('x'),y.rename('y')],axis=1).dropna()
    if len(q)<2 or q.x.nunique()<2 or q.y.nunique()<2:
        return np.nan, len(q)
    if spearman:
        q=q.round(8).rank(method='average')
    return float(q.x.corr(q.y)), len(q)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--input',type=Path,default=Path(__file__).resolve().parent/'inputs')
    ap.add_argument('--output',type=Path,default=Path(__file__).resolve().parent)
    args=ap.parse_args(); src=args.input.resolve(); out=args.output.resolve()
    out.mkdir(parents=True,exist_ok=True)
    def save(df,name,index=False):
        df.to_csv(out/name,index=index,encoding='utf-8-sig',na_rep='',float_format='%.17g')
    def dump(obj,name):
        (out/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

    files=['monthly_dong_metrics.csv','monthly_candidate_flags.csv',
           'monthly_relationship_summary.csv','Gate2F1A_monthly_core_report.md',
           'reference/multi_month_analysis_spec.md','reference/Gate2F0D_design_freeze.md']
    manifest=json.loads((src/'deliverable_manifest.json').read_text())
    for f in files:
        assert sha(src/f)==manifest[f], f'F1A manifest mismatch: {f}'
    d=read(src/'monthly_dong_metrics.csv')
    flags=read(src/'monthly_candidate_flags.csv')
    s=read(src/'monthly_relationship_summary.csv').set_index('month')
    assert set(d.month)==set(ALL) and len(d)==9*427
    assert not d.duplicated(['dong_code','month']).any()
    ids=d[['dong_code','dong_code10','dong_name']].drop_duplicates().sort_values('dong_code').set_index('dong_code')
    assert len(ids)==427 and ids.index.is_unique
    assert ids.dong_code10.str.len().eq(10).all() and ids.index.str.len().tolist()==[8]*427
    f=d.set_index(['month','dong_code']).sort_index()
    ff=flags.set_index(['month','dong_code']).sort_index()
    assert f.candidate.equals(ff.candidate)
    for m in ALL:
        t=d[d.month.eq(m)]
        assert set(t.dong_code)==set(ids.index)
        both=t.U_sec.notna() & t.C2_count.notna()
        assert t.candidate.isna().equals(~both)
        expected=((t.U_percentile>=75)&(t.C2_percentile>=75)).astype('boolean').mask(~both,pd.NA)
        assert t.candidate.equals(expected)
        for field,label in [('U_sec','U'),('C2_count','C2')]:
            assert np.allclose(t[label+'_percentile'],t[field].round(8).rank(method='average',pct=True)*100,equal_nan=True)
        assert int(t.candidate.sum())==int(s.loc[m,'candidate_count'])
        assert int(both.sum())==int(s.loc[m,'valid_both_dongs'])
        p,n=corr(t.set_index('dong_code').C2_count,t.set_index('dong_code').U_sec)
        r,_=corr(t.set_index('dong_code').C2_count,t.set_index('dong_code').U_sec,True)
        assert np.isclose(p,s.loc[m,'Pearson_C2_U'],atol=1e-12)
        assert np.isclose(r,s.loc[m,'Spearman_C2_U'],atol=1e-12)
    assert int(s.loc['202608','candidate_count'])==38
    assert d[(d.month=='202601') & d.candidate.isna()].dong_code.nunique()==5

    u=d.pivot(index='dong_code',columns='month',values='U_sec').reindex(ids.index)
    c=d.pivot(index='dong_code',columns='month',values='C2_count').reindex(ids.index)
    up=d.pivot(index='dong_code',columns='month',values='U_percentile').reindex(ids.index)
    cp=d.pivot(index='dong_code',columns='month',values='C2_percentile').reindex(ids.index)
    cand=d.pivot(index='dong_code',columns='month',values='candidate').reindex(ids.index)
    metrics=ids.copy()
    def recurrence(months):
        valid=u[months].notna() & c[months].notna()
        v=valid.sum(axis=1).astype(int)
        # Missing entries are not evaluated. True membership is counted only on valid months.
        k=cand[months].eq(True).where(valid).sum(axis=1,min_count=1).fillna(0).astype(int)
        r=k.div(v.where(v>0))
        assert (k<=v).all()
        return v,k,r
    for suffix,months in [('rep',REP),('all',ALL),('rep_noJan',NOJAN)]:
        v,k,r=recurrence(months)
        metrics['V_'+suffix]=v; metrics['K_'+suffix]=k; metrics['R_'+suffix]=r
    metrics['U_median_percentile_rep']=up[REP].median(axis=1)
    metrics['C2_median_percentile_rep']=cp[REP].median(axis=1)
    metrics['U_valid_months_rep']=up[REP].notna().sum(axis=1)
    metrics['C2_valid_months_rep']=cp[REP].notna().sum(axis=1)
    metrics['U_median_percentile_rep_noJan']=up[NOJAN].median(axis=1)
    metrics['C2_median_percentile_rep_noJan']=cp[NOJAN].median(axis=1)
    metrics['candidate_months_rep']=[','.join(m for m in REP if pd.notna(cand.at[g,m]) and bool(cand.at[g,m])) for g in metrics.index]
    metrics['unavailable_months_rep']=[','.join(m for m in REP if pd.isna(cand.at[g,m])) for g in metrics.index]
    metrics['august_candidate']=cand['202608']
    assert int(metrics.K_rep.sum())==int(s.loc[REP,'candidate_count'].sum())
    assert int(metrics.K_all.sum())==int(s.loc[ALL,'candidate_count'].sum())
    assert (metrics.V_rep.value_counts().to_dict()=={8:422,7:5})
    assert metrics.V_rep_noJan.eq(7).all()
    assert (metrics.K_rep-metrics.K_rep_noJan).isin([0,1]).all()
    save(metrics.reset_index(),'dong_replication_metrics.csv')
    ordered=metrics.sort_values(['K_rep','R_rep','U_median_percentile_rep','C2_median_percentile_rep','dong_code'],ascending=[False,False,False,False,True])
    save(ordered.reset_index(),'high_recurrence_exploratory_regions.csv')
    august=ordered[ordered.august_candidate.eq(True)].copy()
    assert len(august)==38
    august['august_U_sec']=u['202608']; august['august_C2_count']=c['202608']
    august['august_U_percentile']=up['202608']; august['august_C2_percentile']=cp['202608']
    save(august.reset_index(),'august_candidate_replication.csv')

    distributions=[]; coverage=[]; summaries=[]
    def summary(scope,population,metric,values):
        x=pd.Series(values,dtype=float).dropna()
        if len(x)==0:
            stats={k:None for k in ['min','P25','median','P75','P90','max']}
        else:
            stats={'min':float(x.min()),'P25':float(x.quantile(.25)), 'median':float(x.median()),
                   'P75':float(x.quantile(.75)),'P90':float(x.quantile(.90)),'max':float(x.max())}
        summaries.append({'scope':scope,'population':population,'metric':metric,'n':len(x),**stats,
                          'positive_n':int((x>0).sum()),'negative_n':int((x<0).sum()),'zero_n':int((x==0).sum())})
    for scope,months in SCOPES.items():
        suffix={'main_replication_8':'rep','all_eligible_9_auxiliary':'all','january_excluded_7_sensitivity':'rep_noJan'}[scope]
        k=metrics['K_'+suffix];v=metrics['V_'+suffix];r=metrics['R_'+suffix]
        for pop,mask in [('all_427_dongs',pd.Series(True,index=metrics.index)),('fully_evaluable_dongs',v.eq(len(months)))]:
            for n in range(len(months)+1):
                distributions.append({'scope':scope,'population':pop,'available_months':len(months),'K':n,
                                      'dong_count':int((mask & v.gt(0) & k.eq(n)).sum()),'population_dongs':int(mask.sum()),
                                      'zero_evaluable_dongs':int((mask & v.eq(0)).sum())})
            summary(scope,pop,'R',r[mask])
        for vn in range(len(months)+1):
            coverage.append({'scope':scope,'available_months':len(months),'V':vn,'dong_count':int(v.eq(vn).sum())})
            for kn in range(vn+1):
                if vn==0: continue
                distributions.append({'scope':scope,'population':'V_stratum_'+str(vn),'available_months':len(months),'K':kn,
                                      'dong_count':int((v.eq(vn)&k.eq(kn)).sum()),'population_dongs':int(v.eq(vn).sum()),
                                      'zero_evaluable_dongs':0})
        summary(scope,'monthly_C2_U','Spearman',s.loc[months,'Spearman_C2_U'])
        summary(scope,'monthly_C2_U','Pearson',s.loc[months,'Pearson_C2_U'])
    for k in range(9):
        distributions.append({'scope':'main_replication_8','population':'august_calendar_candidates','available_months':8,
                              'K':k,'dong_count':int(august.K_rep.eq(k).sum()),'population_dongs':38,'zero_evaluable_dongs':int(august.V_rep.eq(0).sum())})
    summary('main_replication_8','august_calendar_candidates','R',august.R_rep)
    dist=pd.DataFrame(distributions)
    save(dist,'candidate_recurrence_distribution.csv')
    save(pd.DataFrame(coverage),'evaluable_month_distribution.csv')

    monthly=[]
    for m in ALL:
        row=s.loc[m].to_dict();row['month']=m
        row['analysis_role']='main_replication' if m in REP else 'design_month_auxiliary'
        row['main_replication_included']=m in REP
        row['january_sensitivity_included']=m in NOJAN
        row['held']=False;monthly.append(row)
    for m in HELD:
        monthly.append({'month':m,'analysis_role':'held_date_NA','main_replication_included':False,
                        'january_sensitivity_included':False,'held':True})
    relationship=pd.DataFrame(monthly).sort_values('month')
    save(relationship,'monthly_relationship_replication.csv')

    jac=[];pairs=[]
    for a,b in combinations(ALL,2):
        va=u[a].notna()&c[a].notna();vb=u[b].notna()&c[b].notna();v=va&vb
        # Sets consist only of confirmed True memberships; NA is never a False flag.
        sa=set(cand.index[cand[a].eq(True).fillna(False)])
        sb=set(cand.index[cand[b].eq(True).fillna(False)])
        ev=set(v.index[v]); ca=sa&ev; cb=sb&ev
        union=sa|sb;commonunion=ca|cb
        jac.append({'month_a':a,'month_b':b,'pair_role':'main_replication' if b!='202608' else 'august_vs_replication',
                    'common_valid_dongs':int(v.sum()),'candidate_count_a':len(sa),'candidate_count_b':len(sb),
                    'intersection_count':len(sa&sb),'union_count':len(union),'Jaccard':len(sa&sb)/len(union) if union else np.nan,
                    'candidate_count_a_common_valid':len(ca),'candidate_count_b_common_valid':len(cb),
                    'intersection_common_valid':len(ca&cb),'union_common_valid':len(commonunion),
                    'Jaccard_common_valid':len(ca&cb)/len(commonunion) if commonunion else np.nan,
                    'not_common_evaluable_dongs':int((~v).sum()),
                    'candidate_union_not_common_evaluable':len(union-ev)})
        for metric,panel in [('U',u),('C2',c)]:
            val,n=corr(panel[a],panel[b],True)
            pairs.append({'metric':metric,'month_a':a,'month_b':b,'pair_role':'main_replication' if b!='202608' else 'august_vs_replication',
                          'common_valid_dongs':n,'Spearman':val})
    jac=pd.DataFrame(jac);pairs=pd.DataFrame(pairs)
    assert len(jac[jac.pair_role=='main_replication'])==28
    assert len(jac[jac.pair_role=='august_vs_replication'])==8
    save(jac,'monthly_candidate_jaccard.csv')
    save(pairs,'monthly_rank_correlation_pairs.csv')
    for scope,months in SCOPES.items():
        mask=jac.month_a.isin(months)&jac.month_b.isin(months)
        for metric in ['Jaccard','Jaccard_common_valid']:
            summary(scope,'unique_month_pairs',metric,jac.loc[mask,metric])
        for metric in ['U','C2']:
            p=pairs[(pairs.metric==metric)&pairs.month_a.isin(months)&pairs.month_b.isin(months)]
            summary(scope,'unique_month_pairs',metric+'_rank_Spearman',p.Spearman)
            matrix=pd.DataFrame(np.nan,index=months,columns=months);nmat=matrix.copy()
            for m in months:
                panel=u if metric=='U' else c
                diag,n=corr(panel[m],panel[m],True);matrix.at[m,m]=diag;nmat.at[m,m]=n
            for row in p.itertuples():
                matrix.at[row.month_a,row.month_b]=matrix.at[row.month_b,row.month_a]=row.Spearman
                nmat.at[row.month_a,row.month_b]=nmat.at[row.month_b,row.month_a]=row.common_valid_dongs
            matrix.index.name=nmat.index.name='month'
            suffix='' if scope=='main_replication_8' else ('_all9_auxiliary' if scope=='all_eligible_9_auxiliary' else '_noJan_sensitivity')
            save(matrix,'monthly_'+metric+'_rank_correlation'+suffix+'.csv',index=True)
            save(nmat.astype(int),'monthly_'+metric+'_rank_common_valid'+suffix+'.csv',index=True)
    for metric in ['Jaccard','Jaccard_common_valid']:
        summary('august_vs_replication','unique_month_pairs',metric,jac.loc[jac.pair_role=='august_vs_replication',metric])

    sensitivity=metrics[['dong_code10','dong_name','V_rep','K_rep','R_rep','V_rep_noJan','K_rep_noJan','R_rep_noJan',
                         'U_median_percentile_rep','C2_median_percentile_rep','U_median_percentile_rep_noJan','C2_median_percentile_rep_noJan']].copy()
    sensitivity['January_candidate']=cand['202601']
    sensitivity['January_evaluable']=cand['202601'].notna()
    sensitivity['K_change_noJan_minus_Main']=sensitivity.K_rep_noJan-sensitivity.K_rep
    sensitivity['V_change_noJan_minus_Main']=sensitivity.V_rep_noJan-sensitivity.V_rep
    sensitivity['R_change_noJan_minus_Main']=sensitivity.R_rep_noJan-sensitivity.R_rep
    save(sensitivity.reset_index(),'january_exclusion_sensitivity.csv')
    pearson,n=corr(metrics.R_rep,metrics.R_rep_noJan)
    spearman,_=corr(metrics.R_rep,metrics.R_rep_noJan,True)
    maxmain=set(metrics.index[metrics.K_rep.eq(metrics.K_rep.max())])
    maxnojan=set(metrics.index[metrics.K_rep_noJan.eq(metrics.K_rep_noJan.max())])
    janqa={'Pearson_R_Main_vs_noJan':pearson,'Spearman_R_Main_vs_noJan':spearman,'common_valid_dongs':n,
           'Main_max_K':int(metrics.K_rep.max()),'Main_max_K_dongs':len(maxmain),'noJan_max_K':int(metrics.K_rep_noJan.max()),
           'noJan_max_K_dongs':len(maxnojan),'max_K_group_intersection':len(maxmain&maxnojan),'max_K_group_union':len(maxmain|maxnojan),
           'R_change_min':float(sensitivity.R_change_noJan_minus_Main.min()),'R_change_max':float(sensitivity.R_change_noJan_minus_Main.max()),
           'R_absolute_change_median':float(sensitivity.R_change_noJan_minus_Main.abs().median()),
           'R_absolute_change_P90':float(sensitivity.R_change_noJan_minus_Main.abs().quantile(.9))}
    save(pd.DataFrame([janqa]),'january_sensitivity_summary.csv')
    save(pd.crosstab(metrics.K_rep,metrics.K_rep_noJan).reindex(index=range(9),columns=range(8),fill_value=0).rename_axis(index='K_rep',columns='K_rep_noJan'),
         'january_K_cross_tabulation.csv',index=True)
    summary('january_excluded_7_sensitivity','all_427_dongs','R_change_noJan_minus_Main',sensitivity.R_change_noJan_minus_Main)
    summary('january_excluded_7_sensitivity','all_427_dongs','R_absolute_change',sensitivity.R_change_noJan_minus_Main.abs())
    summaries=pd.DataFrame(summaries);save(summaries,'replication_summary.csv')

    # Explicit 12-month panel for NA review. Held months remain NA, including metrics and candidate.
    panel=d[['month','dong_code','dong_code10','dong_name','U_sec','C2_count','U_percentile','C2_percentile','candidate']].copy()
    panel['status']='eligible';panel['role']=panel.month.map(lambda m:'main_replication' if m in REP else 'design_month_auxiliary')
    for m in HELD:
        h=ids.reset_index();h['month']=m;h['status']='held_date';h['role']='held_date_NA'
        for col in ['U_sec','C2_count','U_percentile','C2_percentile']:h[col]=np.nan
        h['candidate']=pd.Series(pd.NA,index=h.index,dtype='boolean')
        panel=pd.concat([panel,h],ignore_index=True)
    panel=panel.sort_values(['dong_code','month'])
    assert len(panel)==12*427
    assert panel.loc[panel.status.eq('held_date'),['U_sec','C2_count','U_percentile','C2_percentile','candidate']].isna().all().all()
    save(panel,'candidate_month_panel.csv')

    # Independent event-count check does not rely on the pivot aggregation above.
    for code,sub in d.groupby('dong_code'):
        for suffix,months in [('rep',REP),('all',ALL),('rep_noJan',NOJAN)]:
            t=sub[sub.month.isin(months)];v=sum(pd.notna(x) for x in t.candidate)
            k=sum(bool(x) for x in t.candidate if pd.notna(x))
            assert metrics.at[code,'V_'+suffix]==v and metrics.at[code,'K_'+suffix]==k
            assert np.isclose(metrics.at[code,'R_'+suffix],k/v) if v else pd.isna(metrics.at[code,'R_'+suffix])
    for scope,months in SCOPES.items():
        assert dist[(dist.scope==scope)&(dist.population=='all_427_dongs')].dong_count.sum()==427
    assert dist[dist.population=='august_calendar_candidates'].dong_count.sum()==38
    assert len(metrics)==427 and metrics.index.is_unique
    qa={'status':'PASS','input_F1A_monthly_rows':len(d),'dong_count':427,'Main_months':REP,'auxiliary_months':ALL,
        'January_exclusion_months':NOJAN,'held_NA_months':HELD,'August_candidates':38,
        'Main_V_distribution':{str(k):int(v) for k,v in metrics.V_rep.value_counts().sort_index().items()},
        'candidate_threshold_unchanged':True,'F1A_candidates_and_correlations_reconciled':True,
        'input_manifest_verified':True,'independent_K_V_R_loop_verified':True,'held_months_NA_verified':True,
        'Main_unique_pairs':28,'August_pairs':8,'raw_reprocessing':False,'new_final_candidate_threshold':False,
        'max_Jaccard_common_valid_difference':float((jac.Jaccard-jac.Jaccard_common_valid).abs().max()),
        'versions':{'python':__import__('platform').python_version(),'pandas':pd.__version__,'numpy':np.__version__}}
    dump(qa,'verification_results.json')
    dump({'inputs':{f:sha(src/f) for f in files},'manifest_sha256':sha(src/'deliverable_manifest.json'),
          'scope':'Only saved monthly dong results; no raw data or Core arrays used.'},'source_manifest.json')
    dump(janqa,'january_sensitivity_summary.json')
    print('K_MAIN',metrics.K_rep.value_counts().sort_index().to_dict())
    print('AUGUST_K',august.K_rep.value_counts().sort_index().to_dict())
    print(summaries.to_string(index=False))
    print('JANUARY_SENSITIVITY',json.dumps(janqa,ensure_ascii=False))
    print('MAX_K_GROUP\n',ordered[ordered.K_rep.eq(ordered.K_rep.max())][['dong_name','K_rep','V_rep','R_rep','K_rep_noJan']].to_string(index=False))
    print('VERIFICATION_PASS')

if __name__=='__main__':
    main()
