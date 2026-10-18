from pathlib import Path
import hashlib,json,zipfile
O=Path(__file__).resolve().parent;R=O.parent
# Submission adapter: paths only; the original calculation statements follow.
from seoul_bus_paths import bind as _submission_bind
globals().update(_submission_bind('F1A'))
required=['Gate2F1A_monthly_core_report.md','monthly_dong_metrics.csv','monthly_relationship_summary.csv','monthly_candidate_flags.csv','monthly_core_sample_counts.csv','monthly_QA_exclusions.csv','august_calendar_vs_legacy.csv','monthly_tail_diagnostics.csv']
assert all((O/n).is_file() for n in required)
for p in O.rglob('*.npz'):
 with zipfile.ZipFile(p) as z:assert z.testzip() is None
paths=sorted(p for p in O.rglob('*') if p.is_file() and '__pycache__' not in p.parts and not p.name.endswith('.writing.npz') and p.name!='deliverable_manifest.json')
manifest={str(p.relative_to(O)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths};(O/'deliverable_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2));paths.append(O/'deliverable_manifest.json')
for p in paths:
 if p.suffix in ('.md','.py','.svg') and 'reference' not in p.parts:assert chr(183) not in p.read_text(),p
out=R/'Gate2F1A_results.zip';temp=out.with_suffix('.writing.zip')
with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in paths:z.write(p,'f1a_results/'+str(p.relative_to(O)))
with zipfile.ZipFile(temp) as z:assert z.testzip() is None;assert len(z.namelist())==len(paths)
temp.replace(out);print('PACKAGE_VERIFIED',len(paths),'files',out.stat().st_size,'bytes')
