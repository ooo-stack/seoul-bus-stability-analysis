import numpy as np

def meridian(p,e,a=6378137.):
    return a*((1-e/4-3*e**2/64-5*e**3/256)*p-(3*e/8+3*e**2/32+45*e**3/1024)*np.sin(2*p)+(15*e**2/256+45*e**3/1024)*np.sin(4*p)-35*e**3/3072*np.sin(6*p))

def forward_tm(lon,lat,lon0,k,fe,fn):
    a=6378137.;fl=1/298.257222101;e=fl*(2-fl);ep=e/(1-e);p=np.deg2rad(lat);p0=np.deg2rad(38.)
    N=a/np.sqrt(1-e*np.sin(p)**2);T=np.tan(p)**2;C=ep*np.cos(p)**2;A=np.cos(p)*np.deg2rad(lon-lon0)
    x=fe+k*N*(A+(1-T+C)*A**3/6+(5-18*T+T*T+72*C-58*ep)*A**5/120)
    y=fn+k*(meridian(p,e)-meridian(p0,e)+N*np.tan(p)*(A*A/2+(5-T+9*C+4*C*C)*A**4/24+(61-58*T+T*T+600*C-330*ep)*A**6/720))
    return np.column_stack([x,y])

def inverse_tm(xy,lon0,k,fe,fn):
    a=6378137.;fl=1/298.257222101;e=fl*(2-fl);ep=e/(1-e);e1=(1-np.sqrt(1-e))/(1+np.sqrt(1-e))
    M=meridian(np.deg2rad(38.),e)+(xy[:,1]-fn)/k;mu=M/(a*(1-e/4-3*e**2/64-5*e**3/256))
    phi=mu+(3*e1/2-27*e1**3/32)*np.sin(2*mu)+(21*e1**2/16-55*e1**4/32)*np.sin(4*mu)+151*e1**3/96*np.sin(6*mu)+1097*e1**4/512*np.sin(8*mu)
    N=a/np.sqrt(1-e*np.sin(phi)**2);R=a*(1-e)/(1-e*np.sin(phi)**2)**1.5;T=np.tan(phi)**2;C=ep*np.cos(phi)**2;D=(xy[:,0]-fe)/(N*k)
    lat=phi-N*np.tan(phi)/R*(D*D/2-(5+3*T+10*C-4*C*C-9*ep)*D**4/24+(61+90*T+298*C+45*T*T-252*ep-3*C*C)*D**6/720)
    lon=np.deg2rad(lon0)+(D-(1+2*T+C)*D**3/6+(5-2*C+28*T-3*C*C+8*ep+24*T*T)*D**5/120)/np.cos(phi)
    return np.column_stack([np.rad2deg(lon),np.rad2deg(lat)])
