"""Unchanged F0S quantile function, exact full-value histograms, linear interpolation."""
import numpy as np
def quantile(hist,q):
 if not hist:return None
 items=sorted(hist.items());vs=np.array([x[0] for x in items]);cs=np.cumsum([x[1] for x in items]);n=int(cs[-1]);pos=(n-1)*q;lo=int(np.floor(pos));hi=int(np.ceil(pos));v0=vs[np.searchsorted(cs,lo+1)];v1=vs[np.searchsorted(cs,hi+1)];return float(v0+(v1-v0)*(pos-lo))
