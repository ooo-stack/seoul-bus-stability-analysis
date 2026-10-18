"""Execute the previously used Gate scripts; this module only stages paths/files."""
from pathlib import Path
import argparse,json,os,shutil,subprocess,sys,zipfile,hashlib
from seoul_bus_paths import REPOSITORY as R,workdir
W=workdir();G=R/'src/gates'
OUT={'F0SX':'f0sx_results','F0M':'f0m_results','F1A':'f1a_results','F1B':'f1b_results','F1C':'f1c_results','M1':'m1_results','M2':'m2_results','M3A':'m3a_results','M3B':'m3b_results','M3C':'m3c_results','C2A':'Gate4C2A','C2B':'Gate4C2B'}
COMMANDS={
'audit':[('F0SX','audit_full_months.py',['inventory']),('F0SX','audit_full_months.py',['scan']),('F0SX','audit_full_months.py',['duplicates']),('F0SX','audit_sequence_records.py',[]),('F0SX','assemble_full_months.py',[]),('F0SX','verify_audit.py',[]),('F0M','prepare_masters.py',[]),('F0M','audit_master_matches.py',[]),('F0M','finalize_readiness.py',[])],
'metrics':[('F1A','prepare_inputs.py',[]),('F1A','run_all.py',[]),('F1A','route_population_QA.py',[]),('F1A','assemble_results.py',[]),('F1A','package_results.py',[])],
'recurrence':[('F1B','reproduce_gate2f1b.py',['--input','{work}/f1a_results','--output','{work}/f1b_results'])],
'robustness':[('F1C','restore_daily_and_fourweek.py',['prepare']),('F1C','restore_daily_and_fourweek.py',[]),('F1C','compute_variants.py',[]),('F1C','assemble_robustness.py',[]),('F1C','verify_artifacts.py',[])],
'segments':[('M1','restore_core_inputs.py',[]),('M1','analyze_segments.py',[]),('M1','verify_outputs.py',[])],
'temporal':[('M2','analyze_hours.py',[]),('M2','restore_daily.py',[]),('M2','analyze_weekdays.py',[]),('M2','summarize_results.py',[]),('M2','verify_results.py',[])],
'pairs':[('M3B','build_nonspatial.py',[]),('M3B','verify_nonspatial.py',[]),('M3C','analyze_evidence.py',[]),('M3C','verify_evidence.py',[])],
'daily':[('C2B','c2b_analyze.py',[]),('C2B','c2b_report.py',[]),('C2B','c2b_verify.py',[])],
'environment-audit':[('M3A','audit_speed.py',[]),('M3A','audit_mapping_order.py',[]),('M3A','audit_geometry_and_routes.py',[]),('M3A','audit_ridership.py',[]),('M3A','audit_road_candidates.py',[]),('M3A','assemble_audit.py',[]),('M3A','verify_audit.py',[])],
'exposure-preparation':[('C2A','c2a_build_exposures.py',['{work}']),('C2A','c2a_finalize_QA.py',[])]}

def read_config():
 p=R/'config.local.json'
 return json.loads(p.read_text()) if p.exists() else {}
def configured(name,default):
 p=Path(read_config().get(name,default));return p if p.is_absolute() else R/p
def copy_file(src,dst):
 src,dst=Path(src),Path(dst)
 if not src.is_file():return
 dst.parent.mkdir(parents=True,exist_ok=True)
 if dst.exists() and src.resolve()==dst.resolve():return
 shutil.copyfile(src,dst)
def directory(src,dst):
 """Alias private directories; Windows without symlink permission uses copies."""
 src,dst=Path(src),Path(dst);src.mkdir(parents=True,exist_ok=True);dst.parent.mkdir(parents=True,exist_ok=True)
 if dst.is_symlink():
  if dst.resolve()==src.resolve():return
  dst.unlink()
 if dst.exists():shutil.copytree(src,dst,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.zip'));return
 try:dst.symlink_to(src,target_is_directory=True)
 except OSError:shutil.copytree(src,dst,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.zip'))
def prepare():
 W.mkdir(parents=True,exist_ok=True)
 cfg=read_config()
 for gate,name in OUT.items():
  dest=W/name;dest.mkdir(exist_ok=True)
  cache=cfg.get('saved_gate_dirs',{}).get(gate)
  if cache:
   p=Path(cache);p=p if p.is_absolute() else R/p
   if p.resolve()!=dest.resolve():
    for f in p.rglob('*'):
     target=dest/f.relative_to(p)
     if f.is_file() and '__pycache__' not in f.parts and f.suffix not in ['.zip','.py','.png'] and not target.exists():copy_file(f,target)
 for n in ['f0sx_work','f0m_work','f1a_work','f1c_work','upload','project_sources','c2b_inputs','c2a_inputs']:(W/n).mkdir(exist_ok=True)
 bus=configured('bus_raw','data/raw/bus');masters=configured('historical_masters','data/raw/masters')
 for sub in ['f0m_sources/raw','f1a_sources/raw','f1c_sources/raw','m2_raw']:directory(bus,W/sub)
 directory(configured('auxiliary_uploads','data/raw/auxiliary'),W/'upload')
 directory(configured('spatial_raw','data/raw/spatial'),W/'project_sources')
 for sub in ['f0m_sources','f1a_sources','m1_inputs','m3a_inputs']:
  target=W/sub/'master_files';target.mkdir(parents=True,exist_ok=True)
  for p in masters.rglob('*.xlsx'):copy_file(p,target/p.name)
  for p in masters.glob('*.zip'):
   copy_file(p,W/sub/p.name)
 # The four August weekly count archives retain their historical alias/hash contract.
 aliases=R/'data/reference/weekly_archive_aliases.json'
 if aliases.exists():
  wanted=json.loads(aliases.read_text());byhash={}
  for p in bus.rglob('*.zip'):
   with p.open('rb') as f:byhash[hashlib.file_digest(f,'sha256').hexdigest()]=p
  for name,digest in wanted.items():
   if digest in byhash:copy_file(byhash[digest],W/name)
 # Historical metadata consumed by the actual preparation scripts.
 copy_file(R/'src/gates/F0M/inherited_geometry_functions.py',W/'f0m_sources/c1/reproduce_gate2c1.py')
 copy_file(R/'data/reference/c1_recovery_diagnostics.json',W/'f0m_sources/c1/recovery_diagnostics.json')
 for n in ['historical_master_package_provenance.json']:copy_file(R/'data/reference'/n,W/'f0m_results'/n)
 mapping={
 'f0m_sources/sx/f0sx_results':'f0sx_results','f1a_sources/unpacked/Gate2F0SX_results/f0sx_results':'f0sx_results','f1a_sources/unpacked/Gate2F0M_results/f0m_results':'f0m_results',
 'f1c_sources/F1A/f1a_results':'f1a_results','f1c_sources/F1B':'f1b_results','f1c_sources/F0SX/f0sx_results':'f0sx_results','f1c_sources/F0M/f0m_results':'f0m_results',
 'm1_work/f1a_results':'f1a_results','m1_work/f0m_results':'f0m_results',
 'm2_sources/Gate3M1_results':'m1_results','m2_sources/Gate2F1A_results/f1a_results':'f1a_results','m2_sources/Gate2F1C_results/f1c_results':'f1c_results','m2_sources/Gate2F1C_results/f1c_sources/F0SX/f0sx_results':'f0sx_results',
 'm3a_sources/Gate3M1_results':'m1_results','m3a_sources/Gate3M2_results':'m2_results','m3a_sources/Gate2F0M_results/f0m_results':'f0m_results'}
 for dst,src in mapping.items():directory(W/src,W/dst)
 for target,stages in [('m3b_results',['M1','M2','M3A']),('m3c_results',['M1','M2','M3B'])]:
  for gate in stages:
   dst=W/target/'inputs'/gate;dst.mkdir(parents=True,exist_ok=True)
   # File copies preserve the original rglob-based source hash audit as well.
   for p in (W/OUT[gate]).iterdir():
    if p.is_file() and p.suffix in ['.csv','.gz','.json']:copy_file(p,dst/p.name)
 for n in ['Gate3M1_rule_freeze.md','freeze_record.json']:copy_file(R/'data/reference'/n,W/'m1_results'/n)
 for p in (R/'docs/frozen').glob('*.md'):
  copy_file(p,W/'f1a_results/reference'/p.name)
  copy_file(p,W/'f0sx_results/reference'/p.name)
 copy_file(R/'docs/frozen/Gate3M3C_rule_record.md',W/'m3c_results/Gate3M3C_rule_record.md')
 for p in (W/'f0sx_results').glob('*.csv'):copy_file(p,W/'f1a_results/reference'/p.name)
 copy_file(R/'outputs/legacy/legacy_August_dong_metrics.csv',W/'f1a_sources/unpacked/Gate2C2_results/dong_supply_reliability_relationship.csv')
 directory(configured('living_and_metadata','data/raw/external/c2a_metadata'),W/'c2a_metadata')
 for n in ['day_calendar.csv','spatial_asset_verification.json','inherited_geometry_functions.py']:
  source=W/('f0sx_results' if n=='day_calendar.csv' else 'f0m_results')/n;copy_file(source,W/'c2a_inputs'/n)
 for p in (W/'f0m_work/boundary/11000').glob('TL_SCCO_GEMD.*'):copy_file(p,W/'c2a_inputs'/p.name)
 directory(configured('official_daily_weather','data/raw/external/official_daily_weather'),W/'c2b_inputs/official_daily_weather')
 copy_file(R/'docs/frozen/C2B_execution_spec_frozen.md',W/'Gate4C2B/execution_spec_frozen.md')
 # Preserve C2A finalized CSV without a new exposure transformation.
 for n in ['living_population_exposure_panel.csv','analysis_calendar_metadata_only.csv']:
  src=W/'Gate4C2A/staging'/n
  if not (W/'Gate4C2A'/n).exists():copy_file(src,W/'Gate4C2A'/n)
 # C2B's existing interface reads the stored M2 ZIP; recreate it locally from saved outputs.
 if (W/'m2_results/fixed_segment_roster.csv').exists():
  with zipfile.ZipFile(W/'c2b_inputs/Gate3M2_results.zip','w',zipfile.ZIP_DEFLATED) as z:
   for p in (W/'m2_results').rglob('*'):
    if p.is_file() and p.suffix not in ['.py','.zip','.png']:z.write(p,p.relative_to(W/'m2_results'))
def readiness(stage):
 needs={
 'audit':[configured('bus_raw','data/raw/bus'),configured('historical_masters','data/raw/masters'),W/'project_sources/02-_-_-.zip',W/'project_sources/04-_-_-.zip']+[W/n for n in ['counts_week.zip','counts_w2.zip','counts_w3.zip','counts_w4.zip']],
 'metrics':[W/'f0m_results/final_month_eligibility.csv',W/'f0sx_results/duplicate_raw_rows.csv',W/'f0sx_results/csv_source_manifest.csv',W/'f0m_results/coordinate_node_diagnostics.csv',R/'outputs/legacy/legacy_August_dong_metrics.csv'],
 'recurrence':[W/'f1a_results/monthly_dong_metrics.csv',W/'f1a_results/deliverable_manifest.json'],
 'robustness':[W/'f1a_results/core_checkpoints',W/'f1a_results/input_contract.json',W/'f1b_results/dong_replication_metrics.csv',W/'f0sx_results/duplicate_raw_rows.csv'],
 'segments':[W/'f1a_results/core_checkpoints',W/'f1a_results/input_contract.json',W/'f0m_results/route_type_history.csv'],
 'temporal':[W/'m1_results/route_segment_hour_folded.csv.gz',W/'m1_results/analysis_inputs/strict_U_reference.csv.gz',W/'f1a_results/core_checkpoints',W/'f0sx_results/csv_source_manifest.csv'],
 'pairs':[W/'m3a_results/segment_environment_match_status.csv',W/'m3a_results/ridership_source_rows_for_primary.csv',W/'m2_results/stop_pair_hourly_comparison.csv',W/'m1_results/segment_hour_detail.csv.gz'],
 'daily':[W/'c2b_inputs/Gate3M2_results.zip',W/'Gate4C2A/living_population_exposure_panel.csv',W/'c2b_inputs/official_daily_weather/official_asos108_daily.csv',W/'c2b_inputs/official_daily_weather/source_manifest.json'],
 'environment-audit':[W/'upload/2026년 6월 서울시 차량통행속도.xlsx',W/'upload/서울특별시 교통소통 표준링크 매핑정보_20250306.xlsx',W/'upload/A008_P_20250814.zip',W/'project_sources/03-A058_L_20260213.zip',W/'m2_results/fixed_segment_roster.csv'],
 'exposure-preparation':[W/'c2a_inputs/day_calendar.csv',W/'c2a_metadata/living_download_manifest.json',W/'c2a_metadata/seoul_station_current_metadata.json',W/'upload/OBS_ASOS_TIM_20261016132020.xls']}
 return [p for p in needs[stage] if not p.exists() or p.is_dir() and not any(p.iterdir())]
def main(stage=None):
 ap=argparse.ArgumentParser(description=__doc__)
 if stage is None:ap.add_argument('stage',choices=COMMANDS)
 ap.add_argument('--run',action='store_true',help='Run the original scripts after input preflight')
 ap.add_argument('--prepare-only',action='store_true',help='Create private path aliases and stop')
 ap.add_argument('--check-inputs',action='store_true')
 args=ap.parse_args();stage=stage or args.stage
 if not any([args.run,args.prepare_only,args.check_inputs]):
  for g,n,a in COMMANDS[stage]:print(g,n,' '.join(a))
  return
 prepare()
 if args.prepare_only:return
 missing=readiness(stage)
 if missing:
  print('INPUTS_REQUIRED: consult data/README.md and config.example.json')
  for p in missing:print(p.relative_to(R) if p.is_relative_to(R) else p.name)
  raise SystemExit(2)
 if not args.run:print('PRECHECK_PASS (existence only; content hashes checked by original scripts)');return
 env=os.environ.copy();env['PYTHONPATH']=str(R/'src')+os.pathsep+env.get('PYTHONPATH','');env['PYTHONDONTWRITEBYTECODE']='1'
 for gate,name,argv in COMMANDS[stage]:
  prepare();cmd=[sys.executable,str(G/gate/name)]+[x.replace('{work}',str(W)) for x in argv]
  subprocess.run(cmd,cwd=W,env=env,check=True)
  if gate=='M3A':
   p=W/'m3a_results';files={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in p.iterdir() if f.is_file() and f.suffix in ['.csv','.gz','.json'] and f.name!='source_manifest.json'}
   (p/'source_manifest.json').write_text(json.dumps({'outputs':files},indent=2))
if __name__=='__main__':main()
