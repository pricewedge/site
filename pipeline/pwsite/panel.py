"""The firm-by-month grids the sorts run on.

`validate.py` grew its own copy of this against a fixed 1964-2017 window. This
is the same construction with the window and the source file as arguments, so
the sorts can run on a sample that extends past the paper's.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .wrds_source import CACHE

def ordinary_common(frame: pd.DataFrame) -> pd.Series:
    """US common stock on NYSE, AMEX or Nasdaq -- the paper's sample.

    In CRSP's older schema this is share codes 10 and 11. The CIZ tables
    replace those with four separate fields, and getting only two of them right
    is not close enough: filtering on share type and security type alone admits
    non-US-incorporated firms, REITs, closed-end funds and exchange-traded
    products, which between them are 2,061 extra securities and 9% of market
    capitalisation over 1960-2017.

    The difference is not cosmetic. Adding the other two conditions moves
    agreement with the package's published decile weights up for 20 of 22
    characteristics tested, PM from 0.82 to 0.97 and PROF from 0.87 to 0.98,
    and brings the security count to 24,227 against the package's own 24,742
    over a longer window.
    """
    return (
        (frame["sharetype"] == "NS")
        & (frame["securitytype"] == "EQTY")
        & (frame["securitysubtype"] == "COM")
        & (frame["usincflg"] == "Y")
        & frame["issuertype"].isin(["CORP", "ACOR"])
        & frame["primaryexch"].isin(["N", "A", "Q", "R"])
    )


# A firm must have all ten of these before it can enter any sort.
FIXED = ["Returns", "PORT_WEGHT", "BEME", "Q", "R_12_2", "PROF", "I2A",
         "RetX_mb", "exchcd", "BookDebt2"]


@dataclass
class Grids:
    universe: pd.DataFrame
    months: np.ndarray
    permnos: np.ndarray
    fixed: dict[str, np.ndarray]
    rf: np.ndarray
    rm: np.ndarray
    first: int          # 1-based row of the first formation month
    shape: tuple[int, int]
    _rows: np.ndarray
    _cols: np.ndarray

    def grid(self, column: str) -> np.ndarray:
        out = np.full(self.shape, np.nan)
        out[self._rows, self._cols] = self.universe[column].to_numpy(dtype=float)
        return out


def build_grids(panel: str | Path = None, factors: str | Path = None,
                start: int = 196001, end: int = 201712,
                first_formation: int = 196407) -> Grids:
    """Lay the characteristic panel out as (month, firm) arrays."""
    panel = Path(panel) if panel else CACHE / "full_panel.parquet"
    factors = Path(factors) if factors else CACHE / "ff_monthly.parquet"

    full = pd.read_parquet(panel)
    full["permno"] = full["permno"].astype("int64")
    ff = pd.read_parquet(factors)
    ff["month"] = ff["date"].dt.year * 100 + ff["date"].dt.month

    universe = full[
        ordinary_common(full) & (full.month >= start) & (full.month <= end)
    ].copy()

    months = np.array(sorted(universe.month.unique()))
    permnos = np.array(sorted(universe.permno.unique()))
    rows = universe.month.map({v: i for i, v in enumerate(months)}).to_numpy()
    cols = universe.permno.map({v: i for i, v in enumerate(permnos)}).to_numpy()
    shape = (len(months), len(permnos))

    def grid(column: str) -> np.ndarray:
        out = np.full(shape, np.nan)
        out[rows, cols] = universe[column].to_numpy(dtype=float)
        return out

    aligned = ff.set_index("month").reindex(months)
    rf = aligned["rf"].to_numpy(dtype=float)
    rm = aligned["mktrf"].to_numpy(dtype=float)

    exchange = np.full(shape, np.nan)
    exchange[rows, cols] = np.where(universe["primaryexch"].to_numpy() == "N", 1.0, 2.0)

    fixed = {
        "Returns": grid("ret") - rf[:, None],
        "PORT_WEGHT": grid("prevcap"),
        # Negative book equity is discarded rather than sorted on.
        "BEME": np.where(grid("BEME") < 0, np.nan, grid("BEME")),
        "Q": grid("Q"), "R_12_2": grid("R_12_2"), "PROF": grid("PROF"),
        "I2A": grid("I2A"), "RetX_mb": grid("retx") - rf[:, None],
        "exchcd": exchange, "BookDebt2": grid("BookDebt2"),
    }
    first = int(np.searchsorted(months, first_formation)) + 1
    return Grids(universe=universe, months=months, permnos=permnos, fixed=fixed,
                 rf=rf, rm=rm, first=first, shape=shape, _rows=rows, _cols=cols)
