#!/usr/bin/env python3
"""Does a firm-level price wedge predict what happens next?

The cross-validation criteria ask whether a mapping reproduces portfolio wedges
it was not fitted to. This asks something the portfolios cannot: if a firm's
wedge says it is overpriced, does it subsequently underperform?

That is the criterion the website's numbers ultimately answer to, and it is the
only one evaluated on firms rather than on portfolios -- so it is also the only
one that penalises a mapping for extrapolating badly, which is the failure the
portfolio-level tests are blind to.

Firms are sorted into deciles on their wedge each month and tracked forward.
Both weightings are reported: capitalisation weighting is what the wedges
aggregate to, equal weighting is where the extrapolation is worst.
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from firm_mapping import fit_ols, pcs, predict, standardise
from firm_wedges import portfolio_table
from group_cv import groups
from pwsite.panel import build_grids
from pwsite.wrds_source import CACHE

VERIFIED = 0.85
HORIZONS = [12, 36, 60]


def build_firm_wedges(tag: str, kinds: list[str]) -> dict[str, pd.DataFrame]:
    X, y, chars, names = portfolio_table(tag)
    agree = pd.read_json(CACHE / "validation.json").set_index("char")["weight_agreement"]
    good = [c for c in names if agree.get(c, 0) > VERIFIED]
    cols = [names.index(c) for c in good]
    rows = np.isin(chars, good)
    X, y = X[np.ix_(rows, cols)], y[rows]
    ranks = pd.read_parquet(CACHE / f"firm_ranks_{tag}.parquet")
    have = ranks[good].notna().all(axis=1)
    R = ranks.loc[have, good].to_numpy(float)
    base = ranks.loc[have, ["permno", "month"]]
    out = {}
    Z, mean, scale = standardise(X)
    Zf = (R - mean) / scale
    for kind in kinds:
        if kind.startswith("pc"):
            k = int(kind[2:])
            comps, basis = pcs(Z, k)
            beta = fit_ols(comps, y, 0.0)
            fitted = predict(beta, pcs(Zf, k, basis)[0])
        else:
            beta = fit_ols(Z, y, 100.0)
            fitted = predict(beta, Zf)
        out[kind] = base.assign(wedge=fitted)
    print(f"{len(good)} verified characteristics; {have.sum():,} firm-months priced")
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tag", default="paper")
    args = p.parse_args()

    kinds = ["pc3", "pc10", "direct"]
    wedges = build_firm_wedges(args.tag, kinds)

    g = build_grids()
    ret = g.grid("ret")
    months = g.months
    index = {m: i for i, m in enumerate(months)}
    col = {p_: i for i, p_ in enumerate(g.permnos)}
    # Forward compounded returns at each horizon.
    log1p = np.log1p(ret)
    forward = {}
    for h in HORIZONS:
        rolled = pd.DataFrame(log1p).rolling(h, min_periods=h).sum().to_numpy()
        shifted = np.full_like(rolled, np.nan)
        shifted[:-h] = rolled[h:]
        forward[h] = np.expm1(shifted)
    cap = g.grid("cap")

    print(f"\n{'mapping':10}{'horizon':>9}{'weighting':>12}"
          f"{'decile 1':>10}{'decile 10':>11}{'1 minus 10':>12}{'monotone':>10}")
    out = []
    for kind in kinds:
        w = wedges[kind]
        r = w["month"].map(index); c = w["permno"].map(col)
        ok = r.notna() & c.notna()
        r = r[ok].astype(int).to_numpy(); c = c[ok].astype(int).to_numpy()
        val = w.loc[ok, "wedge"].to_numpy()
        grid_w = np.full(g.shape, np.nan); grid_w[r, c] = val
        for h in HORIZONS:
            fwd = forward[h]
            for weighting in ("cap", "equal"):
                means = np.full((len(months), 10), np.nan)
                for t in range(len(months)):
                    x = grid_w[t]; y_ = fwd[t]; wt = cap[t] if weighting == "cap" else np.ones_like(x)
                    m = np.isfinite(x) & np.isfinite(y_) & np.isfinite(wt)
                    if m.sum() < 100:
                        continue
                    q = pd.qcut(x[m], 10, labels=False, duplicates="drop")
                    for d in range(10):
                        s = q == d
                        if s.sum() == 0:
                            continue
                        ww = wt[m][s]
                        means[t, d] = np.average(y_[m][s], weights=ww)
                avg = np.nanmean(means, axis=0) * 100
                mono = np.all(np.diff(avg) <= 0) or np.all(np.diff(avg) >= 0)
                print(f"{kind:10}{h:>7}m{weighting:>12}{avg[0]:10.1f}{avg[9]:11.1f}"
                      f"{avg[0]-avg[9]:12.1f}{str(mono):>10}")
                out.append({"mapping": kind, "horizon": h, "weighting": weighting,
                            **{f"d{i+1}": avg[i] for i in range(10)},
                            "spread": avg[0] - avg[9]})
        print()
    pd.DataFrame(out).to_csv(CACHE / f"mapping_expost_{args.tag}.csv", index=False)
    print("Decile 1 is the most negative wedge (most underpriced), decile 10 the")
    print("most positive. If wedges are mispricing that resolves, decile 1 should")
    print("outperform, so a positive '1 minus 10' is the expected sign.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
