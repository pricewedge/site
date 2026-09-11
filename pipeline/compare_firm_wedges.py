#!/usr/bin/env python3
"""How close the rebuilt firm-level wedges come to the ones the site serves.

`PWshare.mat` holds the paper's own firm-level wedges, 642 months by 24,742
securities, for each of the eight specifications. This lines ours up against
them firm by firm and month by month.

Reported per specification and per firm, because an average correlation can
hide a mapping that works for large firms and not for small ones.
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.io as sio

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pwsite import config as C
from pwsite.wrds_source import CACHE

CELLS = {"pc3": (0, 0), "ff5": (0, 1)}


def published_long(cell: tuple[int, int]) -> pd.DataFrame:
    mat = sio.loadmat(C.PW_SHARE)
    grid = mat["PWshare"][cell]
    permnos = mat["columnPERMNOS"].ravel().astype(int)
    months = mat["rowdates"].ravel().astype(int)
    rows, cols = np.nonzero(np.isfinite(grid))
    return pd.DataFrame({"permno": permnos[cols], "month": months[rows],
                         "published": grid[rows, cols] * 100.0})


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tag", default="paper")
    p.add_argument("--mappings", default="pc3,ff5,direct")
    args = p.parse_args()

    reference = published_long(CELLS["pc3"])
    print(f"published pc3-equity-full: {len(reference):,} firm-months, "
          f"{reference.permno.nunique():,} securities\n")

    summary = []
    for mapping in args.mappings.split(","):
        path = CACHE / f"firm_wedges_{args.tag}_{mapping}.parquet"
        if not path.exists():
            print(f"{mapping}: not built"); continue
        ours = pd.read_parquet(path).rename(columns={"wedge": "ours"})
        both = ours.merge(reference, on=["permno", "month"], how="inner")
        if both.empty:
            print(f"{mapping}: no overlap"); continue
        a, b = both["published"].to_numpy(), both["ours"].to_numpy()
        A = np.column_stack([np.ones(len(b)), b])
        beta, *_ = np.linalg.lstsq(A, a, rcond=None)
        resid = a - (beta[0] + beta[1] * b)
        # Per firm, then averaged, so one huge firm-month does not dominate.
        per_firm = both.groupby("permno").apply(
            lambda g: g["ours"].corr(g["published"]) if len(g) > 24 else np.nan)
        row = {"mapping": mapping, "overlap": len(both),
               "firms": both.permno.nunique(),
               "corr": float(np.corrcoef(a, b)[0, 1]),
               "median_firm_corr": float(per_firm.median()),
               "share_firm_corr_above_0.8": float((per_firm > 0.8).mean()),
               "intercept": float(beta[0]), "slope": float(beta[1]),
               "r2": float(1 - (resid ** 2).sum() / ((a - a.mean()) ** 2).sum()),
               "rmse": float(np.sqrt(((a - b) ** 2).mean())),
               "mean_ours": float(b.mean()), "mean_published": float(a.mean()),
               "sd_ours": float(b.std()), "sd_published": float(a.std())}
        summary.append(row)
        print(f"{mapping}: {len(both):,} overlapping firm-months, "
              f"{both.permno.nunique():,} firms")
        print(f"   correlation {row['corr']:.3f}   median per-firm "
              f"{row['median_firm_corr']:.3f}   "
              f"{100*row['share_firm_corr_above_0.8']:.0f}% of firms above 0.8")
        print(f"   published = {beta[0]:+.2f} + {beta[1]:.3f} x ours   "
              f"r2 {row['r2']:.3f}   rmse {row['rmse']:.1f}pp")
        print(f"   level: ours {b.mean():+.1f}pp (sd {b.std():.1f}), "
              f"published {a.mean():+.1f}pp (sd {a.std():.1f})\n")

    pd.DataFrame(summary).to_csv(CACHE / f"firm_comparison_{args.tag}.csv", index=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
