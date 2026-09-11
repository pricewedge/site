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

TAG="current"
g=build_grids("../raw/full_panel_today.parquet","../raw/ff_monthly_today.parquet",196001,202512)
off=g.first-1; rm,rf=g.rm[off:],g.rf[off:]
lam_full=pd.read_csv(CACHE/f"portfolio_wedges_{TAG}.csv")["lambda"].iloc[0]
mtj,ncoh=discount_factor(rm,rf,lam_full,C.HORIZON_MONTHS)
cm=g.months[off:off+ncoh]
from scipy.optimize import brentq
mkt_ybh,mkt_ybhx=load_bh(TAG,[c for c in ALL_CHARACTERISTICS if c in g.universe.columns][0])
mkt_ybh,mkt_ybhx=mkt_ybh[off:],mkt_ybhx[off:]
def market_ratio(lam):
    m,_=discount_factor(rm,rf,lam,C.HORIZON_MONTHS)
    dv,gn=_cash_flows(mkt_ybh,mkt_ybhx,DECILES,ncoh,C.HORIZON_MONTHS-1,0)
    return _wedge_at_horizon(dv,gn,m,C.HORIZON_MONTHS-1,0)[1]
def solve_sub(mask):
    # the price of risk that zeroes the market wedge over just these cohorts
    f=lambda l: -np.log(np.nanmean(market_ratio(l)[mask]))
    lo,hi=0.5,12.0
    if np.sign(f(lo))==np.sign(f(hi)): return np.nan
    return brentq(f,lo,hi,xtol=1e-8)
print(f"{ncoh} cohorts, {cm[0]} to {cm[-1]}; cash flows run to {g.months[-1]}")
names=[c for c in ALL_CHARACTERISTICS if c in g.universe.columns]
ratios={}
for c in names:
    ybh,ybhx=load_bh(TAG,c); ybh,ybhx=ybh[off:],ybhx[off:]
    for d in range(DECILES):
        dv,gn=_cash_flows(ybh,ybhx,d,ncoh,C.HORIZON_MONTHS-1,0)
        ratios[(c,d+1)]=_wedge_at_horizon(dv,gn,mtj,C.HORIZON_MONTHS-1,0)[1]
vals={c:g.grid(c) for c in names}; rk={c:percentile_ranks(vals[c]) for c in names}
w=g.fixed["PORT_WEGHT"]; nyse=g.fixed["exchcd"]==1
base=np.isfinite(g.fixed["Returns"])&np.isfinite(w)&np.isfinite(g.fixed["RetX_mb"])
prior=np.ones(g.shape,bool)
for k,v in g.fixed.items():
    if k not in {"Returns","PORT_WEGHT","RetX_mb"}: prior&=np.isfinite(v)
def profiles(lo,hi):
    tot=np.zeros((len(names),DECILES,len(names))); cnt=np.zeros_like(tot)
    for t in range(g.first-1,len(g.months)):
        if not (lo<=g.months[t]<hi): continue
        blk=np.stack([rk[c][t-1] for c in names],axis=1); good=np.isfinite(blk)
        adm=base[t]&prior[t-1]
        for ci,c in enumerate(names):
            pres=adm&np.isfinite(vals[c][t-1])
            if pres.sum()<=MIN_FIRMS: continue
            mem=np.flatnonzero(pres); dec=assign_deciles(vals[c][t-1][mem],nyse[t-1][mem])
            ww=w[t][mem][:,None]; rr=blk[mem]; gg=good[mem]
            for d in range(1,DECILES+1):
                sel=dec==d
                if not sel.any(): continue
                den=np.where(gg[sel],ww[sel],0.0).sum(0); num=np.where(gg[sel],rr[sel]*ww[sel],0.0).sum(0)
                tot[ci,d-1]+=np.where(den>0,num/den,0.0); cnt[ci,d-1]+=(den>0)
    return np.where(cnt>0,tot/cnt,np.nan)
print(f"\n{'split':10}{'train':>7}{'test':>6}{'test calendar':>16}  {'mapping':10}{'r2':>7}{'corr':>7}{'slope':>7}{'rmse':>7}")
for SPLIT in (198501,199001,199501,199810):
    tr=cm<SPLIT; te=~tr
    if te.sum()<30 or tr.sum()<100: continue
    Pe,Pl=profiles(0,SPLIT),profiles(SPLIT,10**9)
    fl=lambda P: np.array([P[ci,d] for ci in range(len(names)) for d in range(DECILES)])
    lam_tr, lam_te = solve_sub(tr), solve_sub(te)
    def wedges(mask, lam):
        m,_=discount_factor(rm,rf,lam,C.HORIZON_MONTHS)
        out=[]
        for c in names:
            ybh,ybhx=load_bh(TAG,c); ybh,ybhx=ybh[off:],ybhx[off:]
            for d in range(DECILES):
                dv,gn=_cash_flows(ybh,ybhx,d,ncoh,C.HORIZON_MONTHS-1,0)
                r=_wedge_at_horizon(dv,gn,m,C.HORIZON_MONTHS-1,0)[1]
                out.append(-np.log(np.nanmean(r[mask]))*100)
        return np.array(out)
    ye=wedges(tr,lam_tr); yl=wedges(te,lam_te)
    print(f"  price of risk: train {lam_tr:.3f}  test {lam_te:.3f}  (full sample {lam_full:.3f})")
    Xe,Xl=fl(Pe),fl(Pl)
    ok=np.isfinite(Xe).all(1)&np.isfinite(Xl).all(1)&np.isfinite(ye)&np.isfinite(yl)
    Xe,Xl,ye,yl=Xe[ok],Xl[ok],ye[ok],yl[ok]
    Ztr,mn,sc=standardise(Xe); Zte,_,_=standardise(Xl,mn,sc)
    end=min(g.months[-1], (SPLIT//100+15)*100+SPLIT%100)
    cal=f"{SPLIT}-{g.months[-1]}"
    print(f"  train wedges: mean {ye.mean():7.1f} sd {ye.std():6.1f}   "
          f"test wedges: mean {yl.mean():7.1f} sd {yl.std():6.1f}")
    for lab,pred in [("pc3",None),("pc10",None),("direct r=100",None)]:
        if lab=="pc3": a,bs=pcs(Ztr,3); p=predict(fit_ols(a,ye,0.0),pcs(Zte,3,bs)[0])
        elif lab=="pc10": a,bs=pcs(Ztr,10); p=predict(fit_ols(a,ye,0.0),pcs(Zte,10,bs)[0])
        else: p=predict(fit_ols(Ztr,ye,100.0),Zte)
        s=calibration(yl,p)
        print(f"{SPLIT:<10}{tr.sum():>7}{te.sum():>6}{cal:>16}  {lab:10}{s['r2']:7.3f}{s['corr']:7.3f}{s['slope']:7.3f}{s['rmse']:7.2f}")
    print()
