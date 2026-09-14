"""Are portfolio price wedges stable over time, and which sample should the
site use?

Every wedge is -log of the mean, over formation cohorts, of the discounted
fifteen-year cash flow per dollar of price. This script re-estimates all 570
decile wedges on subsets of the cohorts (halves, thirds, "from year X" and
the paper's own window), re-solving the market price of risk on each subset
so the market wedge is zero there as it is on the full sample, and asks:

* how far the cross-section of wedges moves between subsamples, measured
  against the full sample and against the sampling noise of each subsample;
* whether any of it survives at the firm level once the direct mapping is
  refitted on each subsample's wedges.

    python stability.py            # tag "current": cohorts 1964-2011, cash flows to 2025
"""

from __future__ import annotations

import json
import sys
import warnings

import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.stats import spearmanr

warnings.filterwarnings("ignore")
from firm_mapping import fit_ols, predict, standardise           # noqa: E402
from portfolio_wedges import load_bh, MARKET                     # noqa: E402
from pwsite.calibrate import discount_factor                     # noqa: E402
from pwsite.panel import build_grids                             # noqa: E402
from pwsite.portfolio import _cash_flows, _wedge_at_horizon      # noqa: E402
from pwsite.precision import wedge_standard_error                # noqa: E402
from pwsite.sorts import DECILES                                 # noqa: E402
from pwsite.spec_ids import ALL_CHARACTERISTICS                  # noqa: E402
from pwsite.wrds_source import CACHE                             # noqa: E402
import pwsite.config as C                                        # noqa: E402

TAG = sys.argv[1] if len(sys.argv) > 1 else "current"
END = 202512 if TAG == "current" else 201712
H = C.HORIZON_MONTHS
RIDGE = 100.0
DRAWS = 300


def main() -> int:
    # the "current" panel and its caches carry a _today suffix; the default files stop in 2017
    panel = CACHE / ("full_panel_today.parquet" if TAG == "current" else "full_panel.parquet")
    factors = CACHE / ("ff_monthly_today.parquet" if TAG == "current" else "ff_monthly.parquet")
    g = build_grids(panel, factors, 196001, END)
    off = g.first - 1
    rm, rf = g.rm[off:], g.rf[off:]
    table = pd.read_csv(CACHE / f"portfolio_wedges_{TAG}.csv")
    lam_full = float(table["lambda"].iloc[0])
    flipped = dict(zip(table["char"], table["flipped"]))
    _, ncoh = discount_factor(rm, rf, lam_full, H)
    cm = g.months[off:off + ncoh]
    yr = cm // 100
    names = [c for c in ALL_CHARACTERISTICS if (CACHE / "buyandhold" / TAG / f"{c}.npz").exists()]
    v = json.loads((CACHE / "validation.json").read_text())
    verified = {r["char"] for r in v if (r["weight_agreement"] or 0) > 0.85}
    print(f"{ncoh} cohorts {cm[0]}-{cm[-1]}, cash flows to {g.months[-1]}, "
          f"{len(names)} characteristics ({len(verified & set(names))} verified), lambda {lam_full:.4f}")

    # dividends and capital gains per cohort do not depend on lambda; cache them
    flows = {}
    for c in names:
        ybh, ybhx = load_bh(TAG, c)
        ybh, ybhx = ybh[off:], ybhx[off:]
        for d in range(DECILES):
            flows[(c, d + 1)] = _cash_flows(ybh, ybhx, d, ncoh, H - 1, 0)
    ybh, ybhx = load_bh(TAG, names[0])
    market = _cash_flows(ybh[off:], ybhx[off:], MARKET, ncoh, H - 1, 0)
    keys = list(flows)

    def ratios(lam):
        m, _ = discount_factor(rm, rf, lam, H)
        return np.stack([_wedge_at_horizon(dv, gn, m, H - 1, 0)[1] for dv, gn in flows.values()])

    def solve(mask):
        def f(lam):
            m, _ = discount_factor(rm, rf, lam, H)
            return -np.log(np.nanmean(_wedge_at_horizon(market[0], market[1], m, H - 1, 0)[1][mask]))
        return brentq(f, 0.5, 12.0, xtol=1e-8) if np.sign(f(0.5)) != np.sign(f(12.0)) else np.nan

    subs = {
        "full 1964-2011": np.ones(ncoh, bool),
        "paper 1964-2002": cm <= 200212,
        "first half 1964-1987": cm <= 198712,
        "second half 1988-2011": cm > 198712,
        "third 1964-1979": yr <= 1979,
        "third 1980-1995": (yr >= 1980) & (yr <= 1995),
        "third 1996-2011": yr >= 1996,
        "from 1975": yr >= 1975, "from 1980": yr >= 1980, "from 1985": yr >= 1985,
        "from 1990": yr >= 1990, "from 1995": yr >= 1995, "from 2000": yr >= 2000,
    }
    R_full = ratios(lam_full)
    res = {}
    rng = np.random.default_rng(0)
    for label, mask in subs.items():
        lam = solve(mask)
        R = ratios(lam)
        w = -np.log(np.nanmean(R[:, mask], axis=1)) * 100
        w_fixed = -np.log(np.nanmean(R_full[:, mask], axis=1)) * 100
        lag = min(H - 1, int(mask.sum()) - 2)
        se = np.array([wedge_standard_error(R[i, mask], lag)[1] for i in range(len(keys))]) * 100
        # idiosyncratic noise: moving-block bootstrap over the subsample's cohorts,
        # each draw demeaned across portfolios so the common component drops out
        idx = np.flatnonzero(mask); n = len(idx)
        block = min(120, max(12, n // 3))
        draws = np.empty((DRAWS, len(keys)))
        for b in range(DRAWS):
            starts = rng.integers(0, n - block + 1, size=int(np.ceil(n / block)))
            take = np.concatenate([idx[s:s + block] for s in starts])[:n]
            wd = -np.log(np.nanmean(R[:, take], axis=1)) * 100
            draws[b] = wd - np.nanmean(wd)
        se_idio = np.nanstd(draws, axis=0, ddof=1)
        res[label] = dict(mask=mask, lam=lam, w=w, w_fixed=w_fixed, se=se, se_idio=se_idio, n=int(mask.sum()))
        print(f"  {label:24} cohorts {mask.sum():4}  lambda {lam:6.3f}  "
              f"wedge sd {np.nanstd(w):5.1f}  median se {np.nanmedian(se):5.1f}  idiosyncratic {np.nanmedian(se_idio):4.1f}")

    keep = np.array([c in verified for c, _ in keys])
    ext = keep & np.array([d in (1, DECILES) for _, d in keys])
    chars = np.array([c for c, _ in keys]); decs = np.array([d for _, d in keys])

    def compare(a, b, sel):
        a, b = a[sel], b[sel]
        ok = np.isfinite(a) & np.isfinite(b); a, b = a[ok], b[ok]
        slope, icept = np.polyfit(a, b, 1)
        return dict(corr=np.corrcoef(a, b)[0, 1], rank=spearmanr(a, b)[0], slope=slope, icept=icept,
                    rmse=np.sqrt(np.mean((a - b) ** 2)), mad=np.mean(np.abs(a - b)), n=int(ok.sum()))

    def spreads(w):
        out = {}
        for c in names:
            if c not in verified: continue
            i1 = keys.index((c, 1)); i10 = keys.index((c, DECILES))
            lo, hi = (i10, i1) if flipped[c] else (i1, i10)     # long leg first
            out[c] = (w[lo], w[hi], w[lo] - w[hi])
        return out

    full = res["full 1964-2011"]
    sp_full = spreads(full["w"])
    print("\nEach subsample against the full sample, 560 verified portfolios "
          "(lambda re-solved on the subsample)")
    print(f"{'subsample':24}{'corr':>7}{'rank':>7}{'slope':>7}{'icept':>7}{'rmse':>7}{'mad':>6}"
          f" | extremes: {'corr':>5}{'slope':>7} | long-short: {'corr':>5}{'flips':>6}{'mad':>6} | fixed-lambda corr")
    rows = []
    for label, r in res.items():
        s = compare(full["w"], r["w"], keep); e = compare(full["w"], r["w"], ext)
        sp = spreads(r["w"])
        ls_full = np.array([sp_full[c][2] for c in sp]); ls = np.array([sp[c][2] for c in sp])
        flips = int(np.sum(np.sign(ls_full) != np.sign(ls)))
        sfix = compare(full["w"], r["w_fixed"], keep)
        print(f"{label:24}{s['corr']:7.3f}{s['rank']:7.3f}{s['slope']:7.3f}{s['icept']:7.2f}{s['rmse']:7.2f}{s['mad']:6.2f}"
              f" | {e['corr']:14.3f}{e['slope']:7.3f} | {np.corrcoef(ls_full, ls)[0,1]:15.3f}{flips:6d}{np.mean(np.abs(ls_full-ls)):6.2f}"
              f" | {sfix['corr']:7.3f}")
        rows.append(dict(subsample=label, cohorts=r["n"], **{"lambda": r["lam"]}, wedge_sd=np.nanstd(r["w"][keep]),
                         median_se=np.nanmedian(r["se"][keep]), median_se_idio=np.nanmedian(r["se_idio"][keep]),
                         corr_full=s["corr"], rank_full=s["rank"], slope_on_full=s["slope"], icept=s["icept"],
                         rmse_full=s["rmse"], mad_full=s["mad"], corr_extremes=e["corr"], slope_extremes=e["slope"],
                         ls_corr=np.corrcoef(ls_full, ls)[0, 1], ls_sign_flips=flips,
                         ls_mad=np.mean(np.abs(ls_full - ls)), corr_full_fixed_lambda=sfix["corr"]))
    pd.DataFrame(rows).to_csv(CACHE / f"stability_{TAG}_summary.csv", index=False)

    # ---- halves against each other, judged against noise ------------------
    h1, h2 = res["first half 1964-1987"], res["second half 1988-2011"]
    d = (h2["w"] - h1["w"])[keep]
    noise_total = np.sqrt(h1["se"] ** 2 + h2["se"] ** 2)[keep]
    noise_idio = np.sqrt(h1["se_idio"] ** 2 + h2["se_idio"] ** 2)[keep]
    s12 = compare(h1["w"], h2["w"], keep); e12 = compare(h1["w"], h2["w"], ext)
    print(f"\nFirst half against second half (independent cohorts):")
    print(f"  corr {s12['corr']:.3f}  rank {s12['rank']:.3f}  slope of second on first {s12['slope']:.3f}  "
          f"rmse {s12['rmse']:.2f}  (extremes: corr {e12['corr']:.3f} slope {e12['slope']:.3f})")
    print(f"  sd of the change across portfolios {np.nanstd(d):.2f}pp; noise implies "
          f"{np.nanmedian(noise_idio):.2f}pp (idiosyncratic) to {np.nanmedian(noise_total):.2f}pp (total)")
    ti, tt = d / noise_idio, d / noise_total
    print(f"  share of portfolios with |change| > 2 se: {np.nanmean(np.abs(ti) > 2):.0%} on idiosyncratic se, "
          f"{np.nanmean(np.abs(tt) > 2):.0%} on total se")
    var_true = max(np.nanvar(d) - np.nanmean(noise_idio ** 2), 0.0)
    print(f"  variance of the change beyond idiosyncratic noise: {np.sqrt(var_true):.2f}pp sd  "
          f"(cross-sectional sd of wedges {np.nanstd(full['w'][keep]):.1f}pp)")
    sd_true = np.sqrt(max(np.nancov(h1['w'][keep], h2['w'][keep])[0, 1], 0)) if hasattr(np, "nancov") else np.sqrt(max(np.cov(h1['w'][keep], h2['w'][keep])[0, 1], 0))
    exp_corr = sd_true ** 2 / np.sqrt((sd_true ** 2 + np.nanmean(h1['se_idio'][keep] ** 2)) * (sd_true ** 2 + np.nanmean(h2['se_idio'][keep] ** 2)))
    print(f"  the correlation two halves of a CONSTANT cross-section would show, given each half's noise: {exp_corr:.3f}")

    # ---- per characteristic ------------------------------------------------
    per = []
    for c in names:
        if c not in verified: continue
        row = {"char": c}
        for label in ("full 1964-2011", "paper 1964-2002", "first half 1964-1987", "second half 1988-2011",
                      "third 1964-1979", "third 1980-1995", "third 1996-2011", "from 1990"):
            lo, hi, ls = spreads(res[label]["w"])[c]
            tag = {"full 1964-2011": "full", "paper 1964-2002": "paper", "first half 1964-1987": "first1964",
                   "second half 1988-2011": "second1988", "third 1964-1979": "1964", "third 1980-1995": "1980",
                   "third 1996-2011": "1996", "from 1990": "from1990"}[label]
            row[f"long_{tag}"] = lo; row[f"short_{tag}"] = hi; row[f"ls_{tag}"] = ls
        per.append(row)
    per = pd.DataFrame(per)
    per["ls_change_halves"] = per["ls_second1988"] - per["ls_first1964"]
    per.to_csv(CACHE / f"stability_{TAG}_by_characteristic.csv", index=False)
    print("\nLong-short spread by subsample, characteristics ordered by how much it moves between halves (pp):")
    show = per.sort_values("ls_change_halves", key=np.abs, ascending=False)
    cols = ["char", "ls_full", "ls_paper", "ls_first1964", "ls_second1988", "ls_1964", "ls_1980", "ls_1996"]
    print(show[cols].head(12).to_string(index=False, float_format=lambda x: f"{x:6.1f}"))
    print("  ... most stable:")
    print(show[cols].tail(8).to_string(index=False, float_format=lambda x: f"{x:6.1f}"))
    same_sign = np.mean(np.sign(per["ls_first1964"]) == np.sign(per["ls_second1988"]))
    print(f"  long-short keeps its sign across halves for {same_sign:.0%} of characteristics; "
          f"corr of spreads across halves {per['ls_first1964'].corr(per['ls_second1988']):.3f}")

    # ---- firm level: refit the direct mapping on each subsample ------------
    prof = pd.read_csv(CACHE / f"portfolio_profiles_{TAG}.csv")
    regs = [c for c in prof.columns if c not in ("char", "decile") and c in verified]
    prof = prof[prof["char"].isin(verified)]
    ranks = pd.read_parquet(CACHE / f"firm_ranks_{TAG}.parquet")
    have = ranks[regs].notna().all(axis=1)
    R = ranks.loc[have, regs].to_numpy(float); months = ranks.loc[have, "month"].to_numpy()
    recent = months >= 202001
    firm = {}
    for label, r in res.items():
        wmap = dict(zip(keys, r["w"]))
        y = np.array([wmap[(c, d)] for c, d in zip(prof["char"], prof["decile"])])
        X = prof[regs].to_numpy(float); ok = np.isfinite(X).all(1) & np.isfinite(y)
        Z, mn, sc = standardise(X[ok]); beta = fit_ols(Z, y[ok], RIDGE)
        firm[label] = predict(beta, (R - mn) / sc)
    f0 = firm["full 1964-2011"]
    print(f"\nFirm-level wedges from the direct mapping refitted on each subsample, "
          f"{have.sum():,} firm-months ({recent.sum():,} from 2020 on):")
    print(f"{'subsample':24}{'corr':>7}{'rank':>7}{'mean diff':>10}{'sd diff':>9}{'|diff|>10pp':>12} | 2020-25: {'corr':>5}{'mean diff':>10}{'sd diff':>9}")
    frows = []
    for label, f in firm.items():
        dd = f - f0
        c_all = np.corrcoef(f, f0)[0, 1]; rk = spearmanr(f, f0)[0]
        c_rec = np.corrcoef(f[recent], f0[recent])[0, 1]
        print(f"{label:24}{c_all:7.3f}{rk:7.3f}{dd.mean():10.2f}{dd.std():9.2f}{np.mean(np.abs(dd) > 10):12.1%} | "
              f"{c_rec:14.3f}{dd[recent].mean():10.2f}{dd[recent].std():9.2f}")
        frows.append(dict(subsample=label, corr=c_all, rank=rk, mean_diff=dd.mean(), sd_diff=dd.std(),
                          share_abs_diff_gt10=np.mean(np.abs(dd) > 10), corr_recent=c_rec,
                          mean_diff_recent=dd[recent].mean(), sd_diff_recent=dd[recent].std(),
                          wedge_mean=f.mean(), wedge_sd=f.std()))
    pd.DataFrame(frows).to_csv(CACHE / f"stability_{TAG}_firm.csv", index=False)
    # the halves against each other at the firm level
    fa, fb = firm["first half 1964-1987"], firm["second half 1988-2011"]
    print(f"  first half vs second half at the firm level: corr {np.corrcoef(fa, fb)[0,1]:.3f}, "
          f"rank {spearmanr(fa, fb)[0]:.3f}, sd of difference {np.std(fa - fb):.2f}pp (wedge sd {f0.std():.1f}pp)")
    wide = pd.DataFrame({"char": chars, "decile": decs})
    for label, r in res.items():
        wide[label] = r["w"]; wide[label + " se"] = r["se"]
    wide.to_csv(CACHE / f"stability_{TAG}_wedges.csv", index=False)
    print(f"\nwrote raw/stability_{TAG}_summary.csv, _by_characteristic.csv, _firm.csv, _wedges.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
