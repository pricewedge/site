"""The level test for firm-level wedges: do firms realise the wedge they are assigned?

Every candidate firm wedge sorts firms into deciles each month, at NYSE
breakpoints, exactly as a characteristic would. Each decile is then held as a
portfolio for fifteen years, equal- and value-weighted, and its realised wedge
(-log of the mean discounted cash flow per dollar over the formation cohorts,
same SDF and lambda as Table 1) is compared with the mean wedge the mapping
assigned to its members. A mapping whose levels can be trusted shows a slope
of one and an intercept of zero. The equal-weighted version is the one that
matters for a website that reports one firm at a time; the value-weighted
version says whether the mapping respects the calibration that makes the
value-weighted market wedge zero.

Two samples: in-sample, where the mapping is fitted and evaluated on all
cohorts; and out of sample, where it is fitted on cohorts formed before
--split and evaluated on the cohorts formed after.

    python realised_levels.py --tag paper
needs portfolio_wedges.py --tag paper (and --weighting equal), portfolio_profiles.py
--tag paper (and --weighting equal), and writes raw/realised_levels_<tag>_{deciles,summary}.csv.
"""

from __future__ import annotations

import argparse
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
from compare_firm_wedges import CELLS, published_long                    # noqa: E402
from firm_mapping import fit_ols, predict, standardise                    # noqa: E402
from portfolio_wedges import MARKET, load_bh                              # noqa: E402
from pwsite.calibrate import discount_factor                              # noqa: E402
from pwsite.panel import build_grids                                      # noqa: E402
from pwsite.portfolio import _cash_flows, _wedge_at_horizon               # noqa: E402
from pwsite.sorts import DECILES, assign_deciles, sort_characteristic     # noqa: E402
from pwsite.spec_ids import ALL_CHARACTERISTICS                           # noqa: E402
from pwsite.wrds_source import CACHE                                      # noqa: E402
import pwsite.config as C                                                 # noqa: E402

H = C.HORIZON_MONTHS


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tag", default="paper")
    p.add_argument("--end", type=int, default=201712)
    p.add_argument("--panel", default=None)
    p.add_argument("--factors", default=None)
    p.add_argument("--split", type=int, default=198801)
    p.add_argument("--ridges", default="100,300")
    args = p.parse_args()
    ridges = [float(r) for r in args.ridges.split(",")]

    g = build_grids(args.panel, args.factors, 196001, args.end)
    off = g.first - 1
    rm, rf = g.rm[off:], g.rf[off:]
    lam = float(pd.read_csv(CACHE / f"portfolio_wedges_{args.tag}.csv")["lambda"].iloc[0])
    mtj, ncoh = discount_factor(rm, rf, lam, H)
    cm = g.months[off:off + ncoh]
    early, late, full = cm < args.split, cm >= args.split, np.ones(ncoh, bool)
    names = [c for c in ALL_CHARACTERISTICS if c in g.universe.columns]
    col = {x: i for i, x in enumerate(g.permnos)}; row = {m: i for i, m in enumerate(g.months)}
    weight = g.fixed["PORT_WEGHT"]; nyse = g.fixed["exchcd"] == 1
    fixed = {"VW": g.fixed, "EW": dict(g.fixed)}
    fixed["EW"]["PORT_WEGHT"] = np.where(np.isfinite(weight), 1.0, np.nan)

    flows = {}
    for tag in (args.tag, f"{args.tag}_ew"):
        for c in names:
            ybh, ybhx = load_bh(tag, c); ybh, ybhx = ybh[off:], ybhx[off:]
            for d in range(DECILES):
                flows[(tag, c, d + 1)] = _cash_flows(ybh, ybhx, d, ncoh, H - 1, 0)
    ybh, ybhx = load_bh(args.tag, names[0])
    market = _cash_flows(ybh[off:], ybhx[off:], MARKET, ncoh, H - 1, 0)

    def ratios(tag, m):
        return {(c, d): _wedge_at_horizon(dv, gn, m, H - 1, 0)[1] for (t, c, d), (dv, gn) in flows.items() if t == tag}

    def solve(mask):
        from scipy.optimize import brentq
        def f(l):
            m, _ = discount_factor(rm, rf, l, H)
            return -np.log(np.nanmean(_wedge_at_horizon(market[0], market[1], m, H - 1, 0)[1][mask]))
        return brentq(f, 0.5, 12.0, xtol=1e-8)

    R = {"VW": ratios(args.tag, mtj), "EW": ratios(f"{args.tag}_ew", mtj)}
    prof = {"VW": pd.read_csv(CACHE / f"portfolio_profiles_{args.tag}.csv"),
            "EW": pd.read_csv(CACHE / f"portfolio_profiles_{args.tag}_ew.csv")}
    ranks = pd.read_parquet(CACHE / f"firm_ranks_{args.tag}.parquet")
    have = ranks[names].notna().all(axis=1)
    Rf = ranks.loc[have, names].to_numpy(float); key = ranks.loc[have, ["permno", "month"]]
    print(f"{ncoh} cohorts, lambda {lam:.4f}; {have.sum():,} firm-months with all {len(names)} characteristics")

    def design(kinds, mask, Rs=None):
        Rs = R if Rs is None else Rs
        X, y = [], []
        for k in kinds:
            t = pd.DataFrame([{"char": c, "decile": d, "pw": -np.log(np.nanmean(r[mask])) * 100}
                              for (c, d), r in Rs[k].items()])
            m = prof[k].merge(t, on=["char", "decile"])
            ok = np.isfinite(m[names].to_numpy(float)).all(1) & m["pw"].notna()
            X.append(m.loc[ok, names].to_numpy(float)); y.append(m.loc[ok, "pw"].to_numpy(float))
        return np.vstack(X), np.concatenate(y)

    def direct(kinds, ridge, mask, Rs=None):
        X, y = design(kinds, mask, Rs); Z, mn, sc = standardise(X); b = fit_ols(Z, y, ridge)
        f = key.copy(); f["wedge"] = predict(b, (Rf - mn) / sc); return f

    def pc3_paper(mask):
        """The paper's own construction: 114 extremes, covariance PCA, EW profiles."""
        X, y = design(["EW"], mask)
        t = pd.DataFrame([{"char": c, "decile": d} for (c, d) in R["EW"]])
        # rows of design() follow prof["EW"] merged order; recompute the extremes flag the same way
        m = prof["EW"].merge(pd.DataFrame([{"char": c, "decile": d, "pw": 0.0} for (c, d) in R["EW"]]), on=["char", "decile"])
        ok = np.isfinite(m[names].to_numpy(float)).all(1)
        ext = m.loc[ok, "decile"].isin([1, DECILES]).to_numpy()
        # use the value-weighted wedges as the paper does, on the extremes only
        _, yv = design(["VW"], mask)
        Xe, ye = X[ext], yv[ext]; mu = Xe.mean(0)
        _, _, Vt = np.linalg.svd(Xe - mu, full_matrices=False); V3 = Vt[:3]
        A = np.column_stack([np.ones(len(ye)), (Xe - mu) @ V3.T]); beta = np.linalg.lstsq(A, ye, rcond=None)[0]
        f = key.copy(); f["wedge"] = beta[0] + (Rf - mu) @ (V3.T @ beta[1:]); return f

    def to_grid(df):
        x = np.full(g.shape, np.nan); r = df["month"].map(row); c = df["permno"].map(col); ok = r.notna() & c.notna()
        x[r[ok].astype(int).to_numpy(), c[ok].astype(int).to_numpy()] = df.loc[ok, "wedge"].to_numpy(); return x

    deciles_out, summary = [], []

    def realised(f, mask, candidate, sample, m_eval=None):
        m_eval = mtj if m_eval is None else m_eval
        x = to_grid(f); res = {}
        for wl in ("EW", "VW"):
            r = sort_characteristic(x, fixed[wl], g.rf, first_month=g.first); ybh, ybhx = r.ybh[off:], r.ybhx[off:]
            res[wl] = [-np.log(np.nanmean(_wedge_at_horizon(*_cash_flows(ybh, ybhx, d, ncoh, H - 1, 0), m_eval, H - 1, 0)[1][mask])) * 100
                       for d in list(range(DECILES)) + [MARKET]]
        tot = np.zeros(DECILES); totw = np.zeros(DECILES); cnt = np.zeros(DECILES)
        for t in range(g.first - 1, len(g.months)):
            if t - off >= ncoh or not mask[t - off]: continue
            v = x[t - 1]; ok = np.isfinite(v) & np.isfinite(weight[t]) & np.isfinite(g.fixed["Returns"][t])
            if ok.sum() < 250: continue
            mem = np.flatnonzero(ok); dec = assign_deciles(v[mem], nyse[t - 1][mem])
            for d in range(1, DECILES + 1):
                s = dec == d
                if s.any():
                    tot[d - 1] += v[mem][s].mean(); totw[d - 1] += np.average(v[mem][s], weights=weight[t][mem][s]); cnt[d - 1] += 1
        fitted = {"EW": tot / np.maximum(cnt, 1), "VW": totw / np.maximum(cnt, 1)}
        # aggregate coherence over the evaluation months: cap-weighted and equal mean of the fitted wedge
        months_eval = set(cm[mask]); sel = f["month"].isin(months_eval).to_numpy()
        fm = f.loc[sel].merge(pd.DataFrame({"permno": np.repeat(g.permnos, len(g.months)), "month": np.tile(g.months, len(g.permnos)),
                                              "w": weight.T.ravel()}), on=["permno", "month"], how="left")
        ew_mean = float(fm["wedge"].mean()); vw_mean = float(np.average(fm["wedge"], weights=fm["w"].fillna(0)))
        for wl in ("EW", "VW"):
            b = np.polyfit(fitted[wl], res[wl][:10], 1)
            summary.append(dict(candidate=candidate, sample=sample, weighting=wl, slope=b[0], intercept=b[1],
                                rmse=float(np.sqrt(np.mean((np.polyval(b, fitted[wl]) - res[wl][:10]) ** 2))),
                                mad=float(np.mean(np.abs(fitted[wl] - np.array(res[wl][:10])))),
                                universe_realised=res[wl][10], fitted_mean_ew=ew_mean, fitted_mean_vw=vw_mean))
            for d in range(DECILES):
                deciles_out.append(dict(candidate=candidate, sample=sample, weighting=wl, decile=d + 1,
                                        fitted=fitted[wl][d], realised=res[wl][d]))
        e, v = summary[-2], summary[-1]
        print(f"  {candidate:44} {sample:10} EW slope {e['slope']:.2f} icept {e['intercept']:+6.1f} | VW slope {v['slope']:.2f} icept {v['intercept']:+6.1f} | "
              f"fitted mean EW {ew_mean:6.1f} VW {vw_mean:6.1f} | realised universe EW {e['universe_realised']:6.1f} VW {v['universe_realised']:5.1f}", flush=True)

    cands = {}
    if args.tag == "paper":
        pub = published_long(CELLS["pc3"]); cands["published PWshare (PC3, EW profiles)"] = lambda mask: pub.rename(
            columns={c: "wedge" for c in pub.columns if c not in ("permno", "month")})
    cands["PC3 on 114 extremes, EW profiles (paper's construction)"] = pc3_paper
    for rd in ridges:
        cands[f"direct ridge {rd:g}: VW wedges, VW profiles"] = (lambda rd: lambda mask: direct(["VW"], rd, mask))(rd)
        cands[f"direct ridge {rd:g}: EW wedges, EW profiles"] = (lambda rd: lambda mask: direct(["EW"], rd, mask))(rd)
        cands[f"direct ridge {rd:g}: VW and EW stacked"] = (lambda rd: lambda mask: direct(["VW", "EW"], rd, mask))(rd)
    print("\nin sample: fitted and realised on all cohorts")
    for name, make in cands.items():
        realised(make(full), full, name, "in-sample")
    print(f"\nout of sample: fitted on cohorts before {args.split}, realised on cohorts from {args.split}, lambda held at {lam:.3f}")
    for name, make in cands.items():
        realised(make(early) if not name.startswith("published") else make(full), late, name, "out-of-sample, full lambda")
    lam_e, lam_l = solve(early), solve(late)
    m_e, _ = discount_factor(rm, rf, lam_e, H); m_l, _ = discount_factor(rm, rf, lam_l, H)
    R_e = {"VW": ratios(args.tag, m_e), "EW": ratios(f"{args.tag}_ew", m_e)}
    print(f"\nout of sample with lambda re-solved: fitted at lambda {lam_e:.3f} (early market wedge zero), "
          f"realised at lambda {lam_l:.3f} (late market wedge zero)")
    for name, make in cands.items():
        if name.startswith("published"):
            realised(make(full), late, name, "out-of-sample, lambda per half", m_eval=m_l); continue
        f = (direct(["VW"], float(name.split()[2].rstrip(':')), early, R_e) if "VW wedges" in name else
             direct(["EW"], float(name.split()[2].rstrip(':')), early, R_e) if "EW wedges" in name else
             direct(["VW", "EW"], float(name.split()[2].rstrip(':')), early, R_e) if "stacked" in name else None)
        if f is None: continue
        realised(f, late, name, "out-of-sample, lambda per half", m_eval=m_l)
    pd.DataFrame(deciles_out).to_csv(CACHE / f"realised_levels_{args.tag}_deciles.csv", index=False)
    pd.DataFrame(summary).to_csv(CACHE / f"realised_levels_{args.tag}_summary.csv", index=False)
    print(f"\nwrote raw/realised_levels_{args.tag}_deciles.csv and _summary.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
