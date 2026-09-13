"""BETA_d over a window of the firm's own trading days, from the daily file.

Appendix Table A.1 gives the estimator, the sum of the coefficients on the
market excess return and its lag (Dimson 1979), and no window. The published
decile weights pointed at about a year of daily data; the paper's own panel
pins it down as a window of the firm's last BETA_ROWS trading days ending on
the month's last trading day, with the market's lag taken over the firm's
own rows. A window on the market calendar, which shortens the sample for a
thinly traded firm, agrees with the panel less well (76% of firm-months
within 1% against 85%), and so does any other length: 248 or 250 rows halve
the agreement. The firm-months that miss the 1% mark have betas below 0.2 in
absolute value, where a relative criterion is harsh; the rank correlation
with the panel is 1.0000.

Built from raw/daily_raw (returns) and raw/ff_daily.parquet (the market
factor and the risk-free rate), from rolling cross-moment sums, so there is
no per-firm-month regression loop.
"""

from __future__ import annotations

import glob
from pathlib import Path

import numpy as np
import pandas as pd

from .wrds_source import CACHE

BETA_ROWS = 249         # trading days of the firm in the window
BETA_MIN_ROWS = 10      # the panel carries betas for firms with far fewer than 249 days
LAG_ON_FIRM_ROWS = True # the market's lag is its value on the firm's previous row


def _returns(years: list[int] | None = None) -> pd.DataFrame:
    files = sorted(glob.glob(str(CACHE / "daily_raw" / "*.parquet")))
    if years:
        files = [f for f in files if int(Path(f).stem) in years]
    d = pd.concat([pd.read_parquet(f, columns=["permno", "d", "r"]) for f in files],
                  ignore_index=True).rename(columns={"d": "date"})
    return d.sort_values(["permno", "date"]).reset_index(drop=True)


def build(years: list[int] | None = None) -> pd.DataFrame:
    ff = pd.read_parquet(CACHE / "ff_daily.parquet", columns=["date", "mktrf", "rf"])
    ff = ff.dropna(subset=["mktrf"]).sort_values("date").reset_index(drop=True)
    ff["mktrf_callag"] = ff["mktrf"].shift(1)
    d = _returns(years).merge(ff, on="date", how="inner")
    d = d.sort_values(["permno", "date"]).reset_index(drop=True)
    g = d.groupby("permno", sort=False)
    x = d["mktrf"].to_numpy()
    xl = (g["mktrf"].shift(1) if LAG_ON_FIRM_ROWS else d["mktrf_callag"]).to_numpy()
    y = d["r"].to_numpy(float) - d["rf"].to_numpy()
    P = pd.DataFrame({"one": 1.0, "x": x, "xl": xl, "y": y, "xx": x * x, "xlxl": xl * xl,
                      "xxl": x * xl, "xy": x * y, "xly": xl * y}, index=d.index)
    P = P.where(P.notna().all(axis=1))
    S = P.groupby(d["permno"]).transform(
        lambda s: s.rolling(BETA_ROWS, min_periods=BETA_MIN_ROWS).sum())
    d["month"] = (d["date"].dt.year * 100 + d["date"].dt.month).astype("int32")
    last = d.groupby(["permno", "month"]).tail(1).index
    S = S.loc[last]
    A = np.stack([np.stack([S["one"], S["x"], S["xl"]], 1),
                  np.stack([S["x"], S["xx"], S["xxl"]], 1),
                  np.stack([S["xl"], S["xxl"], S["xlxl"]], 1)], 1)
    b = np.stack([S["y"], S["xy"], S["xly"]], 1)
    beta = np.full(b.shape, np.nan)
    ok = np.isfinite(A).all((1, 2)) & np.isfinite(b).all(1)
    idx = np.flatnonzero(ok)
    with np.errstate(all="ignore"):
        det = np.linalg.det(A[idx])
        scale = np.prod(np.diagonal(A[idx], axis1=1, axis2=2), axis=1)
    idx = idx[np.abs(det) > 1e-12 * np.abs(scale)]
    beta[idx] = np.linalg.solve(A[idx], b[idx][..., None])[..., 0]
    out = d.loc[last, ["permno", "month"]].copy()
    out["beta"] = beta[:, 1] + beta[:, 2]
    out["permno"] = out["permno"].astype("int64")
    return out[out["beta"].notna()].reset_index(drop=True)
