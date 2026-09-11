#!/usr/bin/env python3
"""Leave a whole family of anomalies out, not just one characteristic.

Leaving out BEME while assets-to-market, earnings-to-price and sales-to-price
stay in the training set is not a hard test: the neighbours carry the
prediction. Leaving out the whole value family is, and it is the test that
matches what the mapping is asked to do for a firm, whose combination of
characteristics belongs to no family in particular.

Also reported: holding out the extreme deciles. Fitting on deciles two to nine
and predicting one and ten asks whether the mapping extrapolates, which is
exactly what it must do at the firm level, where 94% of firm-months sit outside
the range of the 570 portfolios on at least one characteristic.
"""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from firm_mapping import calibration, fit_ols, pcs, predict, standardise
from firm_wedges import portfolio_table
from pwsite.wrds_source import CACHE

GRID = [0, 1, 3, 10, 30, 100, 300, 1000, 3000]


def groups() -> dict[str, str]:
    spec = json.load(open(Path(__file__).parent / "pwsite/spec/characteristics.json"))
    return {c["id"]: c.get("group", "?") for c in spec["characteristics"]}


def held_out(X, y, folds, kind, ridge):
    """Prediction for every row, each made without its own fold."""
    pred = np.full(len(y), np.nan)
    for f in np.unique(folds):
        test = folds == f
        if test.all():
            continue
        Ztr, mean, scale = standardise(X[~test])
        Zte, _, _ = standardise(X[test], mean, scale)
        if kind == "direct":
            beta = fit_ols(Ztr, y[~test], ridge)
            pred[test] = predict(beta, Zte)
        else:
            k = int(kind[2:])
            comps, basis = pcs(Ztr, k)
            beta = fit_ols(comps, y[~test], 0.0)
            pred[test] = predict(beta, pcs(Zte, k, basis)[0])
    return pred


def nested_direct(X, y, folds, inner_folds=None):
    """Penalty chosen inside each fold, so the test selects on nothing.

    `inner_folds` is how the training rows are split to choose the penalty. It
    defaults to the outer folds, which works whenever there are several; a
    two-way design leaves only one training fold, so the caller passes
    something finer -- characteristic identity.
    """
    pred = np.full(len(y), np.nan)
    picked = []
    inner_folds = folds if inner_folds is None else inner_folds
    for f in np.unique(folds):
        test = folds == f
        Xin, yin, fin = X[~test], y[~test], inner_folds[~test]
        best = max(GRID, key=lambda r: (lambda s: s.get("r2", -np.inf))(
            calibration(yin, held_out(Xin, yin, fin, "direct", r))))
        picked.append(best)
        Ztr, mean, scale = standardise(Xin)
        Zte, _, _ = standardise(X[test], mean, scale)
        pred[test] = predict(fit_ols(Ztr, yin, best), Zte)
    return pred, picked


def main() -> int:
    tag = sys.argv[1] if len(sys.argv) > 1 else "paper"
    X, y, chars, names = portfolio_table(tag)
    profile = pd.read_csv(CACHE / f"portfolio_profiles_{tag}.csv")
    wedges = pd.read_csv(CACHE / f"portfolio_wedges_{tag}.csv")
    # Rebuild the decile label in the same row order portfolio_table produced.
    rows = []
    for _, r in wedges.iterrows():
        legs = [r[f"d{i}"] for i in range(1, 11)]
        if r["flipped"]:
            legs = legs[::-1]
        for d, v in enumerate(legs, start=1):
            rows.append({"char": r["char"], "decile": d, "pw": v})
    merged = profile.merge(pd.DataFrame(rows), on=["char", "decile"], how="inner")
    keep = np.isfinite(merged[names].to_numpy(float)).all(axis=1) & merged["pw"].notna()
    decile = merged.loc[keep, "decile"].to_numpy()

    family = groups()
    fam = np.array([family.get(c, "?") for c in chars])
    print(f"{len(y)} portfolios, {len(np.unique(fam))} families\n")
    for f in np.unique(fam):
        print(f"  {f:20} {(fam == f).sum():3} portfolios, "
              f"{len(np.unique(chars[fam == f])):2} characteristics")

    designs = {"leave one characteristic out": chars,
               "leave one family out": fam,
               "extremes held out (fit on deciles 2-9)":
                   np.where((decile == 1) | (decile == 10), "extreme", "middle")}

    print(f"\n{'test':40}{'mapping':14}{'r2':>7}{'corr':>7}{'icept':>8}{'slope':>7}{'rmse':>7}")
    out = []
    for label, folds in designs.items():
        for kind in ["pc3", "pc10", "direct"]:
            if kind == "direct":
                inner = chars if label.startswith("extremes") else None
                pred, picked = nested_direct(X, y, folds, inner)
                note = f"(penalty {sorted(set(picked))})"
            else:
                pred, note = held_out(X, y, folds, kind, 0.0), ""
            if label.startswith("extremes"):
                sel = folds == "extreme"      # score only the held-out rows
                s = calibration(y[sel], pred[sel])
            else:
                s = calibration(y, pred)
            print(f"{label:40}{kind:14}{s['r2']:7.3f}{s['corr']:7.3f}"
                  f"{s['intercept']:8.2f}{s['slope']:7.3f}{s['rmse']:7.2f}  {note}")
            out.append({"test": label, "mapping": kind, **s})
        print()
    pd.DataFrame(out).to_csv(CACHE / f"group_cv_{tag}.csv", index=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
