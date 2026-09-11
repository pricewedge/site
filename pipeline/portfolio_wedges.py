#!/usr/bin/env python3
"""Price wedges for every characteristic's decile portfolios.

Runs the sorts, calibrates the market price of risk on whatever sample it is
given, and writes the wedge for all ten deciles plus the market. The paper
reports only the long and short legs; this keeps the whole cross-section,
because the firm-level mapping in `firm_wedges.py` needs it.

The buy-and-hold arrays are cached per characteristic, so a rerun that only
changes the discount factor or the horizon costs nothing.

    ./.venv/bin/python portfolio_wedges.py --tag paper
    ./.venv/bin/python portfolio_wedges.py --tag current --end 202512 \
        --panel ../raw/full_panel_today.parquet --factors ../raw/ff_monthly_today.parquet
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pwsite import config as C
from pwsite.calibrate import discount_factor, solve_lambda, wedge
from pwsite.panel import build_grids
from pwsite.sorts import DECILES, sort_characteristic
from pwsite.spec_ids import ALL_CHARACTERISTICS
from pwsite.wrds_source import CACHE

MARKET = DECILES          # index of the whole-universe portfolio


def buy_and_hold_path(tag: str, name: str) -> Path:
    return CACHE / "buyandhold" / tag / f"{name}.npz"


def run_sorts(grids, tag: str, names: list[str], refresh: bool = False) -> list[str]:
    """Sort and track each characteristic, caching the result."""
    done = []
    for name in names:
        path = buy_and_hold_path(tag, name)
        if path.exists() and not refresh:
            done.append(name)
            continue
        if name not in grids.universe.columns:
            print(f"  {name:9} not on the panel, skipped", flush=True)
            continue
        x = grids.grid(name)
        if np.isfinite(x).sum() < 100_000:
            print(f"  {name:9} only {np.isfinite(x).sum():,} values, skipped", flush=True)
            continue
        started = time.time()
        result = sort_characteristic(x, grids.fixed, grids.rf, first_month=grids.first)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path,
                            ybh=result.ybh.astype(np.float32),
                            ybhx=result.ybhx.astype(np.float32))
        print(f"  {name:9} sorted in {time.time() - started:5.0f}s", flush=True)
        done.append(name)
    return done


def load_bh(tag: str, name: str) -> tuple[np.ndarray, np.ndarray]:
    """Buy-and-hold returns, padded to the row offset the discount factor expects."""
    with np.load(buy_and_hold_path(tag, name)) as z:
        return z["ybh"].astype(float), z["ybhx"].astype(float)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tag", required=True, help="name for this run's cached output")
    p.add_argument("--panel", default=None)
    p.add_argument("--factors", default=None)
    p.add_argument("--start", type=int, default=196001)
    p.add_argument("--end", type=int, default=201712)
    p.add_argument("--first-formation", type=int, default=196407)
    p.add_argument("--horizon", type=int, default=C.HORIZON_MONTHS)
    p.add_argument("--chars", default=None)
    p.add_argument("--refresh", action="store_true")
    args = p.parse_args()

    grids = build_grids(args.panel, args.factors, args.start, args.end,
                        args.first_formation)
    print(f"panel: {len(grids.months)} months {grids.months[0]}-{grids.months[-1]}, "
          f"{len(grids.permnos):,} firms; formation starts {grids.months[grids.first-1]}")

    names = args.chars.split(",") if args.chars else ALL_CHARACTERISTICS
    print(f"\nsorting {len(names)} characteristics")
    built = run_sorts(grids, args.tag, names, args.refresh)

    # The sorts start at the first formation month; the discount factor is
    # indexed from there too, so both are trimmed to the same origin.
    offset = grids.first - 1
    rm, rf = grids.rm[offset:], grids.rf[offset:]
    print(f"\ncalibrating the market price of risk on {len(rm)} months")
    ybh, ybhx = load_bh(args.tag, built[0])
    lam = solve_lambda(ybh[offset:], ybhx[offset:], rm, rf, MARKET, args.horizon)
    mtj, cohorts = discount_factor(rm, rf, lam, args.horizon)
    market = wedge(ybh[offset:], ybhx[offset:], MARKET, mtj, cohorts, args.horizon)
    print(f"  lambda = {lam:.12f}   market wedge = {market:.3e}   "
          f"{cohorts} formation cohorts")

    rows = []
    for name in built:
        ybh, ybhx = load_bh(args.tag, name)
        ybh, ybhx = ybh[offset:], ybhx[offset:]
        legs = {p: wedge(ybh, ybhx, p, mtj, cohorts, args.horizon) * 100
                for p in range(DECILES + 1)}
        rows.append({"char": name, "lambda": lam, "cohorts": cohorts,
                     **{f"d{p+1}": legs[p] for p in range(DECILES)},
                     "market": legs[MARKET],
                     "long_short": legs[0] - legs[DECILES - 1]})
    table = pd.DataFrame(rows)
    out = CACHE / f"portfolio_wedges_{args.tag}.csv"
    table.to_csv(out, index=False)
    print(f"\nwrote {out} ({len(table)} characteristics)")
    print(table[["char", "d1", "d10", "long_short"]].head(12).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
