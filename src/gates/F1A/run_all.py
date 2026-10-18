from pathlib import Path
import concurrent.futures,sys
from run_month import run,ALL,O
if __name__=='__main__':
 months=sys.argv[1:] or ALL['months']
 with concurrent.futures.ProcessPoolExecutor(max_workers=2) as pool:
  future={pool.submit(run,m):m for m in months}
  for f in concurrent.futures.as_completed(future):
   m=future[f]
   try:f.result()
   except Exception:
    print('FAILED',m,flush=True);raise
 print('ALL_REQUESTED_MONTHS_COMPLETE',flush=True)
