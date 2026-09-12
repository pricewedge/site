import sys, warnings, numpy as np, pandas as pd
warnings.filterwarnings("ignore"); sys.path.insert(0,'/Users/opp/Projects/pricewedge/pipeline')
from firm_mapping import standardise, fit_ols, predict, calibration, pcs, FF5_MOM
from firm_wedges import portfolio_table
from pwsite.wrds_source import CACHE

X,y,chars,names = portfolio_table("paper")
prof=pd.read_csv(CACHE/"portfolio_profiles_paper.csv")
wed=pd.read_csv(CACHE/"portfolio_wedges_paper.csv")
rows=[]
for _,r in wed.iterrows():
    legs=[r[f"d{i}"] for i in range(1,11)]
    if r["flipped"]: legs=legs[::-1]
    for d,v in enumerate(legs,1): rows.append({"char":r["char"],"decile":d,"pw":v})
m=prof.merge(pd.DataFrame(rows),on=["char","decile"])
keep=np.isfinite(m[names].to_numpy(float)).all(1)&m["pw"].notna()
dec=m.loc[keep,"decile"].to_numpy()
ext=(dec==1)|(dec==10)
print(f"the paper extracts its principal components from the 57x2 extreme deciles:")
print(f"  our extreme portfolios: {ext.sum()}   all portfolios: {len(y)}\n")

def insample(Xs, ys, kind):
    Z,_,_=standardise(Xs)
    if kind.startswith("pc"):
        k=int(kind[2:]); A,_=pcs(Z,k)
    elif kind=="ff5":
        A=Z[:,[names.index(c) for c in FF5_MOM if c in names]]
    else:
        A=Z[:,[names.index(kind)]]
    b=fit_ols(A,ys,0.0); f=predict(b,A)
    ss=((ys-ys.mean())**2).sum()
    return 1-((ys-f)**2).sum()/ss

paper={"pc3":0.76,"pc6":0.77,"ff5":0.74,"BEME":0.67,"SIZE":0.29,"PROF":0.00,"I2A":0.37,"R_12_2":0.22}
print(f"{'model':10}{'ours, 114 extremes':>20}{'paper':>8}{'diff':>7}   {'ours, all 570':>14}")
for k,v in paper.items():
    a=insample(X[ext],y[ext],k); b=insample(X,y,k)
    print(f"{k:10}{a:20.3f}{v:8.2f}{a-v:+7.2f}   {b:14.3f}")
