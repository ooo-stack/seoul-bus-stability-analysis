"""Relative input/output bindings only. No research formulas or eligibility rules."""
from pathlib import Path
REPOSITORY = Path(__file__).resolve().parent.parent
def workdir(): return REPOSITORY / 'data' / 'work'
def bind(gate):
 w=workdir()
 if gate=='F0SX':return dict(BASE=w,OUT=w/'f0sx_results',WORK=w/'f0sx_work',SOURCES=REPOSITORY/'data/raw/bus')
 if gate=='F0M':return dict(ROOT=w,R=w,O=w/'f0m_results',S=w/'f0m_sources',W=w/'f0m_work',SX=w/'f0m_sources/sx/f0sx_results')
 if gate=='F1A':
  s=w/'f1a_sources';return dict(R=w,O=w/'f1a_results',W=w/'f1a_work',S=s,SX=s/'unpacked/Gate2F0SX_results/f0sx_results',M=s/'unpacked/Gate2F0M_results/f0m_results')
 if gate=='F1C':return dict(ROOT=w,A=w/'f1c_sources/F1A/f1a_results',O=w/'f1c_results')
 if gate=='M1':return dict(ROOT=w/'m1_results',INP=w/'m1_results/analysis_inputs',WORK=w/'m1_work')
 if gate=='M2':return dict(ROOT=w,OUT=w/'m2_results')
 if gate=='M3A':return dict(ROOT=w,OUT=w/'m3a_results',M1=w/'m1_results',M2=w/'m2_results',F0=w/'f0m_results')
 if gate=='M3B':return dict(ROOT=w/'m3b_results',INP=w/'m3b_results/inputs')
 if gate=='M3C':return dict(ROOT=w/'m3c_results',INP=w/'m3c_results/inputs')
 if gate=='C2B':return dict(ROOT=w,R=w,O=w/'Gate4C2B',S=w/'Gate4C2B/staging')
 raise ValueError(gate)
