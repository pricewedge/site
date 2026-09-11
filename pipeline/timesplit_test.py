import sys, warnings, numpy as np, pandas as pd
warnings.filterwarnings("ignore"); sys.path.insert(0,'/Users/opp/Projects/pricewedge/pipeline')
from firm_mapping import standardise, fit_ols, predict, calibration, pcs
from portfolio_wedges import load_bh
from pwsite.calibrate import discount_factor
from pwsite.portfolio import _cash_flows, _wedge_at_horizon
from pwsite.panel import build_grids
from pwsite.sorts import DECILES, MIN_FIRMS, assign_deciles
from pwsite.spec_ids import ALL_CHARACTERISTICS
from pwsite.wrds_source import CACHE
from portfolio_profiles import percentile_ranks
import pwsite.config as C

SPLIT = 199810      # the paper's out-of-sample cut
g = build_grids(); off = g.first-1
rm, rf = g.rm[off:], g.rf[off:]
lam = pd.read_csv(CACHE/"portfolio_wedges_paper.csv")["lambda"].iloc[0]
mtj, ncoh = discount_factor(rm, rf, lam, C.HORIZON_MONTHS)
cohort_month = g.months[off:off+ncoh]
early = cohort_month < SPLIT
print(f"{ncoh} formation cohorts, {early.sum()} before {SPLIT} and {(~early).sum()} after")

names=[c for c in ALL_CHARACTERISTICS if c in g.universe.columns]
rows=[]
for c in names:
    ybh,ybhx = load_bh("paper", c); ybh,ybhx = ybh[off:], ybhx[off:]
    for d in range(DECILES):
        dv,gain = _cash_flows(ybh,ybhx,d,ncoh,C.HORIZON_MONTHS-1,0)
        _, ratio = _wedge_at_horizon(dv,gain,mtj,C.HORIZON_MONTHS-1,0)
        rows.append({"char":c,"decile":d+1,
                     "pw_early": -np.log(np.nanmean(ratio[early])) * 100,
                     "pw_late":  -np.log(np.nanmean(ratio[~early])) * 100})
pw=pd.DataFrame(rows)
print(f"wedges: early mean {pw.pw_early.mean():.1f}pp (sd {pw.pw_early.std():.1f}), "
      f"late mean {pw.pw_late.mean():.1f}pp (sd {pw.pw_late.std():.1f})")

# Profiles computed separately on each half, so nothing from the test period
# enters the training design.
vals={c:g.grid(c) for c in names}; ranks={c:percentile_ranks(vals[c]) for c in names}
w=g.fixed["PORT_WEGHT"]; nyse=g.fixed["exchcd"]==1
base=np.isfinite(g.fixed["Returns"])&np.isfinite(w)&np.isfinite(g.fixed["RetX_mb"])
prior=np.ones(g.shape,bool)
for k,v in g.fixed.items():
    if k not in {"Returns","PORT_WEGHT","RetX_mb"}: prior&=np.isfinite(v)
def profiles(lo,hi):
    tot=np.zeros((len(names),DECILES,len(names))); cnt=np.zeros_like(tot)
    for t in range(g.first-1,len(g.months)):
        if not (lo<=g.months[t]<hi): continue
        blk=np.stack([ranks[c][t-1] for c in names],axis=1); good=np.isfinite(blk)
        adm=base[t]&prior[t-1]
        for ci,c in enumerate(names):
            pres=adm&np.isfinite(vals[c][t-1])
            if pres.sum()<=MIN_FIRMS: continue
            mem=np.flatnonzero(pres)
            dec=assign_deciles(vals[c][t-1][mem],nyse[t-1][mem])
            ww=w[t][mem][:,None]; rr=blk[mem]; gg=good[mem]
            for d in range(1,DECILES+1):
                sel=dec==d
                if not sel.any(): continue
                den=np.where(gg[sel],ww[sel],0.0).sum(axis=0)
                num=np.where(gg[sel],rr[sel]*ww[sel],0.0).sum(axis=0)
                tot[ci,d-1]+=np.where(den>0,num/den,0.0); cnt[ci,d-1]+=(den>0)
    return np.where(cnt>0,tot/cnt,np.nan)
P_early=profiles(0,SPLIT); P_late=profiles(SPLIT,10**9)
def flat(P):
    return np.array([P[ci,d] for ci in range(len(names)) for d in range(DECILES)])
Xe,Xl=flat(P_early),flat(P_late)
ye=pw.pw_early.to_numpy(); yl=pw.pw_late.to_numpy()
ok=np.isfinite(Xe).all(1)&np.isfinite(Xl).all(1)&np.isfinite(ye)&np.isfinite(yl)
Xe,Xl,ye,yl=Xe[ok],Xl[ok],ye[ok],yl[ok]
print(f"{ok.sum()} portfolios usable in both halves\n")
print(f"{'mapping':12}{'r2':>8}{'corr':>7}{'intercept':>11}{'slope':>8}{'rmse':>8}")
Ztr,mn,sc=standardise(Xe); Zte,_,_=standardise(Xl,mn,sc)
for lab,fit,ap in [("3 PCs", lambda: pcs(Ztr,3), lambda b,bs: predict(b,pcs(Zte,3,bs)[0])),
                   ("10 PCs", lambda: pcs(Ztr,10), lambda b,bs: predict(b,pcs(Zte,10,bs)[0]))]:
    a,basis=fit(); beta=fit_ols(a,ye,0.0); s=calibration(yl,ap(beta,basis))
    print(f"{lab:12}{s['r2']:8.3f}{s['corr']:7.3f}{s['intercept']:11.3f}{s['slope']:8.3f}{s['rmse']:8.2f}")
for r in (0,30,100,300):
    beta=fit_ols(Ztr,ye,r); s=calibration(yl,predict(beta,Zte))
    print(f"{'direct r='+str(r):12}{s['r2']:8.3f}{s['corr']:7.3f}{s['intercept']:11.3f}{s['slope']:8.3f}{s['rmse']:8.2f}")
