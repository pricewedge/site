import sys, warnings, numpy as np, pandas as pd
warnings.filterwarnings("ignore"); sys.path.insert(0,'/Users/opp/Projects/pricewedge/pipeline')
from firm_mapping import standardise, fit_ols, predict, calibration, pcs
from firm_wedges import portfolio_table
X, y, chars, names = portfolio_table("paper")
GRID=[0,1,3,10,30,100,300,1000,3000]
print(f"{len(y)} portfolios, {len(names)} characteristics, {len(np.unique(chars))} folds\n")

def loco(ridge, Xs, ys, cs):
    pred=np.full(len(ys),np.nan)
    for c in np.unique(cs):
        te=cs==c
        Ztr,mn,sc=standardise(Xs[~te]); Zte,_,_=standardise(Xs[te],mn,sc)
        pred[te]=predict(fit_ols(Ztr,ys[~te],ridge),Zte)
    return pred

# (a) what was reported: penalty picked on the same folds it is scored on
scores={r: calibration(y, loco(r,X,y,chars))["r2"] for r in GRID}
best=max(scores,key=scores.get)
print(f"penalty chosen on the outer folds: {best}  ->  r2 {scores[best]:.3f}   (optimistic)")

# (b) nested: inside each outer fold, pick the penalty using only the other 56
pred=np.full(len(y),np.nan); chosen=[]
for c in np.unique(chars):
    te=chars==c
    Xin,yin,cin=X[~te],y[~te],chars[~te]
    inner={r: calibration(yin, loco(r,Xin,yin,cin))["r2"] for r in GRID}
    r=max(inner,key=inner.get); chosen.append(r)
    Ztr,mn,sc=standardise(Xin); Zte,_,_=standardise(X[te],mn,sc)
    pred[te]=predict(fit_ols(Ztr,yin,r),Zte)
s=calibration(y,pred)
print(f"nested (penalty chosen inside each fold):      r2 {s['r2']:.3f}   "
      f"slope {s['slope']:.3f}  intercept {s['intercept']:+.3f}  rmse {s['rmse']:.2f}pp")
import collections
print(f"  penalties chosen across the 57 folds: {dict(collections.Counter(chosen))}")

# the same nested treatment for the principal-component mappings, for a fair race
for k in (3,10):
    pred=np.full(len(y),np.nan)
    for c in np.unique(chars):
        te=chars==c
        Ztr,mn,sc=standardise(X[~te]); Zte,_,_=standardise(X[te],mn,sc)
        a,basis=pcs(Ztr,k); b=pcs(Zte,k,basis)[0]
        pred[te]=predict(fit_ols(a,y[~te],0.0),b)
    s2=calibration(y,pred)
    print(f"{k:2d} principal components (no penalty to tune): r2 {s2['r2']:.3f}   "
          f"slope {s2['slope']:.3f}  intercept {s2['intercept']:+.3f}  rmse {s2['rmse']:.2f}pp")
