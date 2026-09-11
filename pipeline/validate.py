#!/usr/bin/env python3
"""Check the rebuilt pipeline against the paper's published results.

Two checks, and the second is only meaningful because of the first.

**Decile weights.** The replication package ships `datas_all_charP`, whose
slots 41-51 hold each decile's share of market capitalisation for every
formation month and every one of the 57 characteristics. That series depends
only on how a characteristic is built and sorted -- not on the 241-month
tracking, not on the discount factor -- and there are 462 months of it per
characteristic. It is the sharpest available test of a characteristic's
construction, and it is what found the momentum timing error, the split
adjustment in dSOUT, and the high-low reading of SPREAD.

**Price wedges.** Each characteristic then runs through the sorts and the
discount factor to a long-leg and short-leg wedge, compared against Table 1.

Agreement on the first predicts agreement on the second, which is the point: a
characteristic whose decile weights match the package's reproduces its wedge,
and one whose weights do not, does not.

    ./.venv/bin/python validate.py
    ./.venv/bin/python validate.py --chars BEME,Q,SPREAD
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

from pwsite import config as C
from pwsite.portfolio import _cash_flows, _stochastic_discount_factor, _wedge_at_horizon
from pwsite.sorts import DECILES, MIN_FIRMS, assign_deciles, sort_characteristic
from pwsite.wrds_source import CACHE

FORMATION_MONTHS = 462   # months with a full 180-month resolution horizon
WELL_BUILT = 0.85        # decile-weight agreement above which a build is trusted


def _package_root() -> Path:
    """Locate the replication package from `pipeline/.source-path`.

    That file may name either the package itself or the folder holding it, so
    both are accepted rather than making the reader remember which.
    """
    marker = Path(__file__).resolve().parent / ".source-path"
    if not marker.exists():
        raise SystemExit("pipeline/.source-path is missing; it must name the folder "
                         "holding the JFE replication package.")
    base = Path(marker.read_text().strip())
    for candidate in (base, base / "JFE/JFE_final/ReplicationPackage"):
        if (candidate / "DataIN/crsp.mat").exists():
            return candidate
    raise SystemExit(f"No DataIN/crsp.mat under {base}; check pipeline/.source-path.")


def published(root: Path):
    """Table 1's wedges, its characteristic ordering, and the decile weights."""
    import openpyxl
    import scipy.io as sio

    mat = sio.loadmat(root / "DataIN/crsp.mat",
                      variable_names=["alpha1", "datas_all_charP"])
    weights = mat["datas_all_charP"][:FORMATION_MONTHS, 40:50, :]
    alpha = mat["alpha1"].ravel()

    table1 = next((p for p in (root.parent.parent / "Table 1.xlsx",
                               root.parent / "Table 1.xlsx",
                               root / "Table 1.xlsx") if p.exists()), None)
    if table1 is None:
        raise SystemExit(f"Table 1.xlsx not found near {root}.")
    book = openpyxl.load_workbook(table1, read_only=True, data_only=True)
    aliases = {"R122": "R_12_2", "R127": "R_12_7", "R62": "R_6_2",
               "R21": "R_2_1", "R3613": "R_36_13", "BETAd": "BETA_d"}
    wedges, order = {}, {}
    for row in book["Tabelle1"].iter_rows(min_row=3, values_only=True):
        if row and row[0]:
            name = aliases.get(str(row[0]).strip(), str(row[0]).strip())
            wedges[name] = (float(row[11]), float(row[12]))
            order[name] = int(row[2]) - 1
    book.close()
    return wedges, order, alpha, weights


def panel():
    """The firm-by-month grids the sorts run on."""
    full = pd.read_parquet(CACHE / "full_panel.parquet")
    full["permno"] = full["permno"].astype("int64")
    factors = pd.read_parquet(CACHE / "ff_monthly.parquet")
    factors["month"] = factors["date"].dt.year * 100 + factors["date"].dt.month

    from pwsite.panel import ordinary_common
    universe = full[
        ordinary_common(full) & (full.month >= 196001) & (full.month <= 201712)
    ]
    months = np.array(sorted(universe.month.unique()))
    permnos = np.array(sorted(universe.permno.unique()))
    rows = universe.month.map({v: i for i, v in enumerate(months)}).to_numpy()
    cols = universe.permno.map({v: i for i, v in enumerate(permnos)}).to_numpy()
    shape = (len(months), len(permnos))

    def grid(column: str) -> np.ndarray:
        out = np.full(shape, np.nan)
        out[rows, cols] = universe[column].to_numpy(dtype=float)
        return out

    rf = factors.set_index("month").reindex(months)["rf"].to_numpy(dtype=float)
    exchange = np.full(shape, np.nan)
    exchange[rows, cols] = np.where(universe["primaryexch"].to_numpy() == "N", 1.0, 2.0)

    # The ten variables a firm must have before it can enter any sort.
    fixed = {
        "Returns": grid("ret") - rf[:, None],
        "PORT_WEGHT": grid("prevcap"),
        "BEME": np.where(grid("BEME") < 0, np.nan, grid("BEME")),
        "Q": grid("Q"), "R_12_2": grid("R_12_2"), "PROF": grid("PROF"),
        "I2A": grid("I2A"), "RetX_mb": grid("retx") - rf[:, None],
        "exchcd": exchange, "BookDebt2": grid("BookDebt2"),
    }
    first = int(np.searchsorted(months, 196407)) + 1
    return universe, months, grid, rf, fixed, first


def decile_weights(x, months, fixed, first) -> np.ndarray:
    """Each decile's share of the sortable universe's capitalisation, by month."""
    returns, weight, gain = fixed["Returns"], fixed["PORT_WEGHT"], fixed["RetX_mb"]
    lagged = [k for k in fixed if k not in {"Returns", "PORT_WEGHT", "RetX_mb"}]
    out = np.full((len(months), DECILES), np.nan)
    for t in range(first - 1, len(months)):
        present = np.isfinite(returns[t]) & np.isfinite(weight[t]) & np.isfinite(gain[t])
        for name in lagged:
            present &= np.isfinite(fixed[name][t - 1])
        present &= np.isfinite(x[t - 1])
        if present.sum() <= MIN_FIRMS:
            continue
        members = np.flatnonzero(present)
        deciles = assign_deciles(x[t - 1][members], fixed["exchcd"][t - 1][members] == 1)
        w0 = weight[t][members]
        total = np.nansum(w0)
        for p in range(1, DECILES + 1):
            out[t, p - 1] = np.nansum(w0[deciles == p]) / total
    return out[first - 1:]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chars", help="comma-separated subset to check")
    args = parser.parse_args()

    root = _package_root()
    wedges, order, alpha, weights = published(root)
    universe, months, grid, rf, fixed, first = panel()

    wanted = args.chars.split(",") if args.chars else sorted(order)
    targets = [c for c in wanted if c in universe.columns]
    mtj, cohorts, _ = _stochastic_discount_factor(0)
    horizon = C.HORIZON_MONTHS - 1

    print(f"{len(targets)} characteristics\n")
    print(f"{'char':9}{'PW long':>9}{'paper':>7}{'diff':>6}"
          f"{'PW short':>10}{'paper':>7}{'diff':>6}{'weights':>9}")
    print("-" * 64)
    rows = []
    for name in targets:
        x = grid(name)
        k = order[name]
        result = sort_characteristic(x, fixed, rf, first_month=first)
        ybh, ybhx = result.ybh[first - 1:], result.ybhx[first - 1:]
        pad = np.full((C.FIRST_FORMATION_ROW - 1,) + ybh.shape[1:], np.nan)
        ybh, ybhx = np.vstack([pad, ybh]), np.vstack([pad, ybhx])
        share = decile_weights(x, months, fixed, first)

        # Decile 1 is the highest characteristic value; the package flips the
        # ordering wherever the one-month alpha says the low leg is the
        # positive-alpha one, so that decile 1 is always the long leg.
        if alpha[k] < 0:
            ybh, ybhx = ybh.copy(), ybhx.copy()
            ybh[:, 0:DECILES, :] = ybh[:, DECILES - 1::-1, :]
            ybhx[:, 0:DECILES, :] = ybhx[:, DECILES - 1::-1, :]
            share = share[:, ::-1]

        n = min(FORMATION_MONTHS, share.shape[0])
        mine, theirs = share[:n] * 100, weights[:n, :, k] * 100
        usable = np.isfinite(mine[:, 0]) & np.isfinite(theirs[:, 0])
        agreement = (np.mean([np.corrcoef(mine[usable, j], theirs[usable, j])[0, 1]
                              for j in range(DECILES)]) if usable.sum() > 10 else np.nan)

        legs = {p: _wedge_at_horizon(*_cash_flows(ybh, ybhx, p, cohorts, horizon),
                                     mtj, horizon, 0)[0] * 100 for p in (0, DECILES - 1)}
        long_paper, short_paper = wedges[name]
        print(f"{name:9}{legs[0]:9.1f}{long_paper:7.1f}{legs[0] - long_paper:+6.1f}"
              f"{legs[9]:10.1f}{short_paper:7.1f}{legs[9] - short_paper:+6.1f}"
              f"{agreement:9.3f}")
        rows.append({"char": name, "long": legs[0], "long_paper": long_paper,
                     "short": legs[9], "short_paper": short_paper,
                     "weight_agreement": agreement})

    table = pd.DataFrame(rows)
    table.to_json(CACHE / "validation.json", orient="records", indent=1)
    trusted = table[table.weight_agreement > WELL_BUILT]

    def summarise(label: str, frame: pd.DataFrame) -> None:
        print(f"\n{label} ({len(frame)})")
        print(f"  mean |difference|   long {np.nanmean(abs(frame.long - frame.long_paper)):5.2f}pp"
              f"   short {np.nanmean(abs(frame.short - frame.short_paper)):5.2f}pp")
        print(f"  correlation         long {frame.long.corr(frame.long_paper):5.3f}"
              f"   short {frame.short.corr(frame.short_paper):5.3f}")

    summarise("all characteristics", table)
    summarise(f"those whose decile weights agree above {WELL_BUILT}", trusted)
    weak = table[table.weight_agreement <= WELL_BUILT]
    if len(weak):
        print("\n  built differently from the package: "
              + ", ".join(f"{r.char} ({r.weight_agreement:.2f})"
                          for r in weak.sort_values("weight_agreement").itertuples()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
