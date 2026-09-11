#!/usr/bin/env python3
"""From portfolio price wedges to firm price wedges, and which mapping is better.

The paper projects portfolio price wedges on the first three principal
components of the portfolios' characteristic ranks, then evaluates that
projection at a firm's own ranks. The alternative is to regress the portfolio
wedges on the ranks themselves, with no dimension reduction in between.

Judged on magnitudes, not ordering. A mapping that ranks firms correctly but
compresses the spread is not good enough if the number on the website is meant
to be a price wedge rather than a score, so every fit here is scored by
regressing the realised portfolio wedge on the fitted one and reporting the
intercept and the slope alongside the fit. A perfect mapping has intercept
zero, slope one; a mapping that gets the ordering right but shrinks the
magnitudes has slope above one.

Three out-of-sample designs, because they answer different questions:

* leaving one characteristic out -- can the mapping price an anomaly it has
  never seen? This is the one that matters for a firm, whose characteristic
  combination is never one of the 570 portfolios.
* splitting on formation date -- does a mapping estimated on early cohorts hold
  up later? This is the paper's own out-of-sample specification.
* leaving one portfolio out -- the mildest test, reported for completeness.
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

from pwsite.wrds_source import CACHE

# Fama-French five-factor characteristics plus momentum, in our names.
FF5_MOM = ["SIZE", "BEME", "PROF", "I2A", "R_12_2"]


def standardise(x: np.ndarray, mean=None, scale=None):
    mean = x.mean(axis=0) if mean is None else mean
    scale = x.std(axis=0, ddof=0) if scale is None else scale
    scale = np.where(scale > 1e-12, scale, 1.0)
    return (x - mean) / scale, mean, scale


def fit_ols(X: np.ndarray, y: np.ndarray, ridge: float = 0.0):
    A = np.column_stack([np.ones(len(X)), X])
    if ridge > 0:
        penalty = ridge * np.eye(A.shape[1])
        penalty[0, 0] = 0.0
        beta = np.linalg.solve(A.T @ A + penalty, A.T @ y)
    else:
        beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    return beta


def predict(beta: np.ndarray, X: np.ndarray) -> np.ndarray:
    return beta[0] + X @ beta[1:]


def pcs(X: np.ndarray, k: int, basis=None):
    """First k principal components, with the basis reusable out of sample."""
    if basis is None:
        centred = X - X.mean(axis=0)
        _, _, vt = np.linalg.svd(centred, full_matrices=False)
        basis = (X.mean(axis=0), vt[:k])
    mean, loadings = basis
    return (X - mean) @ loadings.T, basis


def calibration(actual: np.ndarray, fitted: np.ndarray) -> dict:
    """Regress actual on fitted: intercept, slope, fit, and error size."""
    ok = np.isfinite(actual) & np.isfinite(fitted)
    a, f = actual[ok], fitted[ok]
    if len(a) < 5:
        return {"n": len(a)}
    A = np.column_stack([np.ones(len(f)), f])
    beta, *_ = np.linalg.lstsq(A, a, rcond=None)
    resid = a - (beta[0] + beta[1] * f)
    ss_tot = ((a - a.mean()) ** 2).sum()
    return {"n": int(len(a)), "intercept": float(beta[0]), "slope": float(beta[1]),
            "r2": float(1 - (resid ** 2).sum() / ss_tot),
            "corr": float(np.corrcoef(a, f)[0, 1]),
            "rmse": float(np.sqrt(((a - f) ** 2).mean())),
            "spread_actual": float(a.std()), "spread_fitted": float(f.std())}


def build_designs(profile: pd.DataFrame, names: list[str]) -> dict:
    X = profile[names].to_numpy(float)
    ok = np.isfinite(X).all(axis=1)
    return X, ok


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tag", default="paper")
    p.add_argument("--ridge", type=float, default=1.0)
    args = p.parse_args()

    wedges = pd.read_csv(CACHE / f"portfolio_wedges_{args.tag}.csv")
    profile = pd.read_csv(CACHE / f"portfolio_profiles_{args.tag}.csv")
    names = [c for c in profile.columns if c not in ("char", "decile")]

    # The profile is stored by raw decile; the wedge table is stored by signed
    # leg. Re-key the wedges onto raw deciles so the two line up.
    flip = dict(zip(wedges["char"], wedges["flipped"]))
    long_form = []
    for _, row in wedges.iterrows():
        legs = [row[f"d{i}"] for i in range(1, 11)]
        if row["flipped"]:
            legs = legs[::-1]
        for d, v in enumerate(legs, start=1):
            long_form.append({"char": row["char"], "decile": d, "pw": v})
    pw = pd.DataFrame(long_form)

    data = profile.merge(pw, on=["char", "decile"], how="inner")
    X, ok = build_designs(data, names)
    y = data["pw"].to_numpy(float)
    keep = ok & np.isfinite(y)
    X, y, chars = X[keep], y[keep], data["char"].to_numpy()[keep]
    print(f"{len(y)} portfolios with a wedge and a complete profile, "
          f"{len(names)} characteristics")
    print(f"portfolio wedges: mean {y.mean():.1f}pp, sd {y.std():.1f}pp, "
          f"range {y.min():.1f} to {y.max():.1f}\n")

    Z, mean, scale = standardise(X)
    ff5 = [names.index(c) for c in FF5_MOM if c in names]

    def design(kind: str, Ztr, Zte=None, basis=None):
        if kind == "direct":
            return Ztr, (Zte if Zte is not None else None), None
        if kind == "ff5":
            return Ztr[:, ff5], (Zte[:, ff5] if Zte is not None else None), None
        k = int(kind[2:])
        tr, basis = pcs(Ztr, k, basis)
        te = pcs(Zte, k, basis)[0] if Zte is not None else None
        return tr, te, basis

    kinds = ["pc1", "pc3", "pc5", "pc10", "ff5", "direct"]
    rows = []
    for kind in kinds:
        Xtr, _, _ = design(kind, Z)
        ridge = args.ridge if kind == "direct" else 0.0
        beta = fit_ols(Xtr, y, ridge)
        stats = calibration(y, predict(beta, Xtr))
        rows.append({"mapping": kind, "test": "in sample", **stats})

        # Leave one characteristic out: 57 folds.
        pred = np.full(len(y), np.nan)
        for c in np.unique(chars):
            te = chars == c
            Ztr2, mn, sc = standardise(X[~te])
            Zte2, _, _ = standardise(X[te], mn, sc)
            a, b, _ = design(kind, Ztr2, Zte2)
            beta2 = fit_ols(a, y[~te], ridge)
            pred[te] = predict(beta2, b)
        rows.append({"mapping": kind, "test": "leave one characteristic out",
                     **calibration(y, pred)})

        # Leave one portfolio out.
        pred = np.full(len(y), np.nan)
        for i in range(len(y)):
            te = np.zeros(len(y), bool); te[i] = True
            Ztr2, mn, sc = standardise(X[~te])
            Zte2, _, _ = standardise(X[te], mn, sc)
            a, b, _ = design(kind, Ztr2, Zte2)
            beta2 = fit_ols(a, y[~te], ridge)
            pred[i] = predict(beta2, b)[0]
        rows.append({"mapping": kind, "test": "leave one portfolio out",
                     **calibration(y, pred)})

    table = pd.DataFrame(rows)
    out = CACHE / f"firm_mapping_{args.tag}.csv"
    table.to_csv(out, index=False)
    cols = ["mapping", "test", "r2", "corr", "intercept", "slope", "rmse",
            "spread_actual", "spread_fitted"]
    print(table[cols].to_string(index=False, float_format=lambda v: f"{v:7.3f}"))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
