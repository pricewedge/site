#!/usr/bin/env python3
"""Firm-level price wedges from the portfolio-level mapping.

Fits the chosen mapping on the 570 decile portfolios and evaluates it at each
firm's own characteristic percentile ranks, month by month.

The shrinkage is not a detail. Regressing portfolio wedges on all 57 ranks
unpenalised fits well in sample and generalises badly -- out of sample its
slope against the realised wedge is 0.75, so it overstates how mispriced an
unfamiliar firm is by a third. Penalised at the level that maximises
out-of-sample fit, the same regression is both the most accurate mapping
available and essentially unbiased in magnitude.
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

from firm_mapping import FF5_MOM, calibration, fit_ols, pcs, predict, standardise
from pwsite.wrds_source import CACHE

RIDGE_GRID = [0, 1, 3, 10, 30, 100, 300, 1000]


def portfolio_table(tag: str):
    """Portfolio wedges keyed to raw deciles, with their characteristic profiles."""
    wedges = pd.read_csv(CACHE / f"portfolio_wedges_{tag}.csv")
    profile = pd.read_csv(CACHE / f"portfolio_profiles_{tag}.csv")
    names = [c for c in profile.columns if c not in ("char", "decile")]
    rows = []
    for _, r in wedges.iterrows():
        legs = [r[f"d{i}"] for i in range(1, 11)]
        if r["flipped"]:
            legs = legs[::-1]        # back to raw decile order
        for d, v in enumerate(legs, start=1):
            rows.append({"char": r["char"], "decile": d, "pw": v})
    merged = profile.merge(pd.DataFrame(rows), on=["char", "decile"], how="inner")
    X = merged[names].to_numpy(float)
    y = merged["pw"].to_numpy(float)
    keep = np.isfinite(X).all(axis=1) & np.isfinite(y)
    return X[keep], y[keep], merged["char"].to_numpy()[keep], names


def choose_ridge(X, y, chars) -> tuple[float, dict]:
    """Pick the penalty that fits best on characteristics the mapping never saw."""
    best = (None, -np.inf, None)
    for ridge in RIDGE_GRID:
        pred = np.full(len(y), np.nan)
        for c in np.unique(chars):
            test = chars == c
            Ztr, mean, scale = standardise(X[~test])
            Zte, _, _ = standardise(X[test], mean, scale)
            pred[test] = predict(fit_ols(Ztr, y[~test], ridge), Zte)
        stats = calibration(y, pred)
        if stats["r2"] > best[1]:
            best = (ridge, stats["r2"], stats)
    return best[0], best[2]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tag", default="paper")
    p.add_argument("--mapping", default="direct", choices=["direct", "pc3", "ff5"])
    p.add_argument("--ridge", type=float, default=None)
    args = p.parse_args()

    X, y, chars, names = portfolio_table(args.tag)
    print(f"{len(y)} portfolios, {len(names)} characteristics")

    if args.mapping == "direct":
        ridge = args.ridge
        if ridge is None:
            ridge, stats = choose_ridge(X, y, chars)
            print(f"penalty chosen out of sample: {ridge}  "
                  f"(r2 {stats['r2']:.3f}, slope {stats['slope']:.3f})")
        Z, mean, scale = standardise(X)
        beta = fit_ols(Z, y, ridge)
        basis = None
    elif args.mapping == "ff5":
        cols = [names.index(c) for c in FF5_MOM if c in names]
        Z, mean, scale = standardise(X)
        beta = fit_ols(Z[:, cols], y, 0.0)
        basis = ("ff5", cols)
    else:
        Z, mean, scale = standardise(X)
        comps, basis = pcs(Z, 3)
        beta = fit_ols(comps, y, 0.0)

    ranks = pd.read_parquet(CACHE / f"firm_ranks_{args.tag}.parquet")
    have = ranks[names].notna().all(axis=1)
    print(f"firm-months with all {len(names)} characteristics: "
          f"{have.sum():,} of {len(ranks):,} ({100*have.mean():.1f}%)")

    R = ranks.loc[have, names].to_numpy(float)
    Zf = (R - mean) / scale
    if args.mapping == "ff5":
        fitted = predict(beta, Zf[:, basis[1]])
    elif args.mapping == "pc3":
        fitted = predict(beta, pcs(Zf, 3, basis)[0])
    else:
        fitted = predict(beta, Zf)

    out = ranks.loc[have, ["permno", "month"]].copy()
    out["wedge"] = fitted
    path = CACHE / f"firm_wedges_{args.tag}_{args.mapping}.parquet"
    out.to_parquet(path, index=False)
    print(f"\nwrote {path}: {len(out):,} firm-months, "
          f"{out.permno.nunique():,} firms, {out.month.min()}-{out.month.max()}")
    print(f"wedge: mean {out.wedge.mean():.1f}pp, sd {out.wedge.std():.1f}pp, "
          f"10th/90th {out.wedge.quantile(.1):.1f}/{out.wedge.quantile(.9):.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
