#!/usr/bin/env python3
"""Characteristic profiles of the decile portfolios.

Both ways of getting from portfolio price wedges to firm price wedges need the
same intermediate object: for each of the 570 decile portfolios, where it sits
in the cross-section on each of the 57 characteristics.

A portfolio's profile is the capitalisation-weighted mean, over its member
firms and over formation months, of each characteristic's percentile rank that
month. Ranks rather than levels because the characteristics are not remotely
comparable in units, and percentile ranks are what the firm side can be
evaluated at.

Writes a (570 x 57) matrix alongside the portfolio wedges, and the month-by-
month firm-level rank panel that the firm mapping is evaluated on.
"""

from __future__ import annotations

import argparse
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pwsite.panel import build_grids
from pwsite.sorts import DECILES, MIN_FIRMS, assign_deciles
from pwsite.spec_ids import ALL_CHARACTERISTICS
from pwsite.wrds_source import CACHE


def percentile_ranks(x: np.ndarray) -> np.ndarray:
    """Cross-sectional percentile rank, month by month, ignoring missing values.

    Scaled to [0, 1] among the firms that have the characteristic that month, so
    a firm's profile does not depend on how many firms happen to be missing.
    """
    out = np.full(x.shape, np.nan)
    for t in range(x.shape[0]):
        row = x[t]
        ok = np.isfinite(row)
        n = ok.sum()
        if n < 2:
            continue
        order = np.argsort(row[ok], kind="mergesort")
        ranks = np.empty(n)
        ranks[order] = np.arange(n)
        out[t, np.flatnonzero(ok)] = ranks / (n - 1)
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tag", required=True)
    p.add_argument("--panel", default=None)
    p.add_argument("--factors", default=None)
    p.add_argument("--start", type=int, default=196001)
    p.add_argument("--end", type=int, default=201712)
    p.add_argument("--first-formation", type=int, default=196407)
    args = p.parse_args()

    grids = build_grids(args.panel, args.factors, args.start, args.end,
                        args.first_formation)
    names = [c for c in ALL_CHARACTERISTICS if c in grids.universe.columns]
    print(f"panel {grids.months[0]}-{grids.months[-1]}, {len(names)} characteristics")

    started = time.time()
    values = {c: grids.grid(c) for c in names}
    ranks = {c: percentile_ranks(values[c]) for c in names}
    print(f"ranked in {time.time() - started:.0f}s")

    weight = grids.fixed["PORT_WEGHT"]
    nyse = grids.fixed["exchcd"] == 1
    base = np.isfinite(grids.fixed["Returns"]) & np.isfinite(weight) & np.isfinite(
        grids.fixed["RetX_mb"])
    prior = np.ones(grids.shape, dtype=bool)
    for k, v in grids.fixed.items():
        if k not in {"Returns", "PORT_WEGHT", "RetX_mb"}:
            prior &= np.isfinite(v)

    # Months outside, characteristics inside: the (firms x 57) block of ranks
    # for one month is built once and shared by all 57 sorts, which keeps this
    # to a few hundred megabytes instead of stacking every month at once.
    total = np.zeros((len(names), DECILES, len(names)))
    # A portfolio can be missing one characteristic while having others, so
    # the count is per (sort, decile, characteristic), not per portfolio.
    counts = np.zeros((len(names), DECILES, len(names)))
    started = time.time()
    for t in range(grids.first - 1, len(grids.months)):
        block = np.stack([ranks[c][t - 1] for c in names], axis=1)   # (firms, 57)
        usable = np.isfinite(block)
        w_row = weight[t]
        admissible = base[t] & prior[t - 1]
        for ci, c in enumerate(names):
            present = admissible & np.isfinite(values[c][t - 1])
            if present.sum() <= MIN_FIRMS:
                continue
            members = np.flatnonzero(present)
            deciles = assign_deciles(values[c][t - 1][members], nyse[t - 1][members])
            w = w_row[members][:, None]
            r = block[members]
            good = usable[members]
            for d in range(1, DECILES + 1):
                sel = deciles == d
                if not sel.any():
                    continue
                gw = np.where(good[sel], w[sel], 0.0)
                num = np.sum(np.where(good[sel], r[sel] * w[sel], 0.0), axis=0)
                den = gw.sum(axis=0)
                with np.errstate(invalid="ignore", divide="ignore"):
                    total[ci, d - 1] += np.where(den > 0, num / den, 0.0)
                counts[ci, d - 1] += (den > 0)
        if (t - grids.first + 2) % 60 == 0:
            print(f"  {grids.months[t]}  {time.time() - started:5.0f}s", flush=True)

    with np.errstate(invalid="ignore"):
        profile = np.where(counts > 0, total / counts, np.nan)
    rows = [{"char": names[ci], "decile": d + 1,
             **{names[j]: profile[ci, d, j] for j in range(len(names))}}
            for ci in range(len(names)) for d in range(DECILES)]
    frame = pd.DataFrame(rows)
    out = CACHE / f"portfolio_profiles_{args.tag}.csv"
    frame.to_csv(out, index=False)
    print(f"\nwrote {out}  ({len(frame)} portfolios x {len(names)} characteristics)")

    # The firm-level rank panel the mapping is evaluated on.
    firm = pd.DataFrame({"permno": np.repeat(grids.permnos, len(grids.months)),
                         "month": np.tile(grids.months, len(grids.permnos))})
    for c in names:
        firm[c] = ranks[c].T.ravel()
    firm = firm.dropna(subset=names, how="all")
    firm.to_parquet(CACHE / f"firm_ranks_{args.tag}.parquet", index=False)
    print(f"wrote firm rank panel: {len(firm):,} firm-months")
    return 0


if __name__ == "__main__":
    sys.exit(main())
