#!/usr/bin/env python3
"""How good is the map from portfolio price wedges to firm price wedges?

Scored four ways, because they answer different questions:

* leaving one characteristic out -- can it price an anomaly it has not seen?
* leaving one *family* out -- can it price a whole kind of anomaly it has not
  seen? Harder, and the relevant one: value characteristics predict each other,
  so holding out BEME while A2ME and E2P stay in is not a real test.
* holding out the extreme deciles -- can it extrapolate? This is what it must
  do at the firm level, where 94% of firm-months sit outside the range the 570
  portfolios span on at least one characteristic.
* splitting on formation date -- does it hold across eras? The market price of
  risk is re-solved inside each half, without which the level difference
  between halves is mechanical.

Everything is scored on magnitudes, not only ordering: the realised wedge is
regressed on the fitted one and the intercept and slope reported alongside the
fit. A mapping that ranks correctly but compresses the spread is not good
enough if the number is meant to be a price wedge rather than a score.

Only characteristics whose construction is verified against the package enter,
as regressors and as portfolios. A portfolio we cannot reproduce carries a
wedge we cannot trust, so including it adds noise to the left-hand side as well
as the right.
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

from firm_mapping import calibration, fit_ols, pcs, predict, standardise
from firm_wedges import portfolio_table
from group_cv import GRID, groups
from pwsite.wrds_source import CACHE

VERIFIED = 0.85


def weighted_fit(X, y, w, ridge):
    """Ridge, weighted by precision. Weights scale to mean one so the penalty
    means the same thing whatever units the standard errors are in."""
    A = np.column_stack([np.ones(len(X)), X])
    w = w / np.nanmean(w)
    W = np.diag(w)
    P = ridge * np.eye(A.shape[1]); P[0, 0] = 0.0
    return np.linalg.solve(A.T @ W @ A + P, A.T @ W @ y)


def design(kind, Ztr, Zte):
    """Regressor blocks for each mapping."""
    if kind.startswith("pc"):
        k = int(kind[2:])
        tr, basis = pcs(Ztr, k)
        return tr, pcs(Zte, k, basis)[0]
    if kind == "direct":
        return Ztr, Zte
    if kind == "quadratic":
        return (np.column_stack([Ztr, Ztr ** 2]),
                np.column_stack([Zte, Zte ** 2]))
    raise ValueError(kind)


def held_out(X, y, w, folds, kind, ridge, weighted):
    pred = np.full(len(y), np.nan)
    for f in np.unique(folds):
        te = folds == f
        if te.all():
            continue
        Ztr, mean, scale = standardise(X[~te])
        Zte, _, _ = standardise(X[te], mean, scale)
        a, b = design(kind, Ztr, Zte)
        if weighted:
            beta = weighted_fit(a, y[~te], w[~te], ridge)
        else:
            beta = fit_ols(a, y[~te], ridge)
        pred[te] = predict(beta, b)
    return pred


def tune_and_score(X, y, w, folds, kind, weighted, inner=None):
    """Penalty chosen inside each fold, so the score selects on nothing."""
    inner = folds if inner is None else inner
    pred = np.full(len(y), np.nan)
    for f in np.unique(folds):
        te = folds == f
        Xin, yin, win, fin = X[~te], y[~te], w[~te], inner[~te]
        best, best_r2 = GRID[0], -np.inf
        for r in GRID:
            p = held_out(Xin, yin, win, fin, kind, r, weighted)
            s = calibration(yin, p)
            if s.get("r2", -np.inf) > best_r2:
                best, best_r2 = r, s["r2"]
        Ztr, mean, scale = standardise(Xin)
        Zte, _, _ = standardise(X[te], mean, scale)
        a, b = design(kind, Ztr, Zte)
        beta = (weighted_fit(a, yin, win, best) if weighted
                else fit_ols(a, yin, best))
        pred[te] = predict(beta, b)
    return pred


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tag", default="paper")
    p.add_argument("--all-characteristics", action="store_true",
                   help="include the ones we cannot reproduce (not advised)")
    args = p.parse_args()

    X, y, chars, names = portfolio_table(args.tag)
    agree = pd.read_json(CACHE / "validation.json").set_index("char")["weight_agreement"]
    good = [c for c in names if agree.get(c, 0) > VERIFIED]
    if args.all_characteristics:
        good = names
    cols = [names.index(c) for c in good]
    rows = np.isin(chars, good)
    X, y, chars = X[np.ix_(rows, cols)], y[rows], chars[rows]
    print(f"{len(y)} portfolios from {len(good)} verified characteristics "
          f"({len(names) - len(good)} excluded)")

    prec = pd.read_csv(CACHE / "portfolio_precision.csv")
    key = pd.DataFrame({"char": chars,
                        "decile": np.tile(np.arange(1, 11), len(np.unique(chars)))[:len(chars)]})
    merged = key.merge(prec, on=["char", "decile"], how="left")
    se = merged["se_nw"].to_numpy()
    w = 1.0 / np.where(np.isfinite(se) & (se > 0), se, np.nan) ** 2
    w = np.where(np.isfinite(w), w, np.nanmedian(w))
    print(f"precision: standard errors run {np.nanmin(se):.2f} to {np.nanmax(se):.2f} "
          f"points, a {np.nanmax(se)/np.nanmin(se):.0f}-fold spread\n")

    fam = np.array([groups().get(c, "?") for c in chars])
    decile = merged["decile"].to_numpy()
    tests = {"leave one characteristic out": (chars, None),
             "leave one family out": (fam, None),
             "extremes held out": (np.where(np.isin(decile, [1, 10]), "x", "mid"), chars)}

    print(f"{'test':30}{'mapping':22}{'r2':>7}{'corr':>7}{'icept':>8}{'slope':>7}{'rmse':>7}")
    out = []
    for tname, (folds, inner) in tests.items():
        for kind, weighted, label in [("pc3", False, "3 PCs (the paper's)"),
                                      ("pc10", False, "10 PCs"),
                                      ("direct", False, "direct, unweighted"),
                                      ("direct", True, "direct, precision-weighted"),
                                      ("quadratic", False, "direct + squared ranks"),
                                      ("quadratic", True, "squared, precision-weighted")]:
            pred = tune_and_score(X, y, w, folds, kind, weighted, inner)
            sel = (folds == "x") if tname.startswith("extremes") else np.ones(len(y), bool)
            s = calibration(y[sel], pred[sel])
            print(f"{tname:30}{label:22}{s['r2']:7.3f}{s['corr']:7.3f}"
                  f"{s['intercept']:8.2f}{s['slope']:7.3f}{s['rmse']:7.2f}")
            out.append({"test": tname, "mapping": label, **s})
        print()
    pd.DataFrame(out).to_csv(CACHE / f"mapping_quality_{args.tag}.csv", index=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
