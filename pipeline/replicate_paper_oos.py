import sys, warnings, numpy as np, pandas as pd
warnings.filterwarnings("ignore"); sys.path.insert(0,'/Users/opp/Projects/pricewedge/pipeline')
from portfolio_wedges import load_bh
from pwsite.calibrate import discount_factor
from pwsite.portfolio import _cash_flows, _wedge_at_horizon
from pwsite.panel import build_grids
from pwsite.sorts import DECILES
from pwsite.spec_ids import ALL_CHARACTERISTICS
from pwsite.wrds_source import CACHE
import pwsite.config as C
from scipy.optimize import brentq

g=build_grids(); off=g.first-1; rm,rf=g.rm[off:],g.rf[off:]
lam_full=pd.read_csv(CACHE/"portfolio_wedges_paper.csv")["lambda"].iloc[0]
mtj,ncoh=discount_factor(rm,rf,lam_full,C.HORIZON_MONTHS)
cm=g.months[off:off+ncoh]
names=[c for c in ALL_CHARACTERISTICS if c in g.universe.columns]
flip=dict(zip(pd.read_csv(CACHE/"portfolio_wedges_paper.csv")["char"],
              pd.read_csv(CACHE/"portfolio_wedges_paper.csv")["flipped"]))
# the paper's split: formation dates to September 1983, returns to September 1998
first = cm <= 198309
second = ~first
print(f"{ncoh} cohorts {cm[0]}-{cm[-1]}; first half {first.sum()} (to 198309), "
      f"second half {second.sum()}")
ratios={}
for c in names:
    ybh,ybhx=load_bh("paper",c); ybh,ybhx=ybh[off:],ybhx[off:]
    for d in range(DECILES):
        dv,gn=_cash_flows(ybh,ybhx,d,ncoh,C.HORIZON_MONTHS-1,0)
        ratios[(c,d+1)]=_wedge_at_horizon(dv,gn,mtj,C.HORIZON_MONTHS-1,0)[1]
mk_ybh,mk_ybhx=load_bh("paper",names[0]); mk_ybh,mk_ybhx=mk_ybh[off:],mk_ybhx[off:]
def market_ratio(lam):
    m,_=discount_factor(rm,rf,lam,C.HORIZON_MONTHS)
    dv,gn=_cash_flows(mk_ybh,mk_ybhx,DECILES,ncoh,C.HORIZON_MONTHS-1,0)
    return _wedge_at_horizon(dv,gn,m,C.HORIZON_MONTHS-1,0)[1]
def solve(mask):
    f=lambda l: -np.log(np.nanmean(market_ratio(l)[mask]))
    return brentq(f,0.5,12.0,xtol=1e-8) if np.sign(f(0.5))!=np.sign(f(12.0)) else np.nan
def wedges(mask, lam):
    m,_=discount_factor(rm,rf,lam,C.HORIZON_MONTHS)
    out={}
    for c in names:
        ybh,ybhx=load_bh("paper",c); ybh,ybhx=ybh[off:],ybhx[off:]
        for d in range(DECILES):
            dv,gn=_cash_flows(ybh,ybhx,d,ncoh,C.HORIZON_MONTHS-1,0)
            r=_wedge_at_horizon(dv,gn,m,C.HORIZON_MONTHS-1,0)[1]
            out[(c,d+1)]=-np.log(np.nanmean(r[mask]))
    return out
allm=np.ones(ncoh,bool)
for label, lam1, lam2, lamF in [
        ("as published (one price of risk, full sample)", lam_full, lam_full, lam_full),
        ("recalibrated within each half", solve(first), solve(second), lam_full)]:
    w1=wedges(first,lam1); w2=wedges(second,lam2); wF=wedges(allm,lamF)
    keys=[(c,d) for c in names for d in (1,10)]           # the 57x2 extremes
    a=np.array([w1[k] for k in keys]); b=np.array([w2[k] for k in keys]); f=np.array([wF[k] for k in keys])
    ok=np.isfinite(a)&np.isfinite(b)&np.isfinite(f)
    print(f"\n{label}   (lambda: first {lam1:.3f}, second {lam2:.3f})")
    print(f"  corr(first half, full sample)   = {np.corrcoef(a[ok],f[ok])[0,1]:.3f}    paper 0.92")
    print(f"  corr(first half, second half)   = {np.corrcoef(a[ok],b[ok])[0,1]:.3f}    paper 0.77")
    print(f"  first-half mean {a[ok].mean()*100:6.1f}pp sd {a[ok].std()*100:5.1f}   "
          f"second-half mean {b[ok].mean()*100:6.1f}pp sd {b[ok].std()*100:5.1f}")
