"""Characteristics that are a daily series sampled on the last trading day.

Two of the nine daily characteristics are not moments of a month at all. The
paper's own panels settle what they are:

* DTO is the day's turnover less its own trailing 180-trading-day mean, taken
  on the last trading day of the month. Appendix Table A.1 describes a median,
  a market adjustment and a Nasdaq volume scaling; each of those makes the
  agreement with the paper's panel worse, and none is used. Built this way it
  matches the panel at a Spearman correlation of 0.998.
* SUV is likewise the last trading day's value: the day's volume less what a
  regression of volume on the day's positive and negative return predicts,
  divided by that regression's residual standard deviation, the regression
  estimated on the calendar month's own trading days (the last day included).
  Built this way it matches the panel's ranking exactly (Spearman 1.000).

Neither can come out of the server-side monthly aggregation the other daily
characteristics use, so this reads the daily file itself, year by year, and
carries the trailing window across the year boundary.
"""

from __future__ import annotations

import glob
from pathlib import Path

import numpy as np
import pandas as pd

from .wrds_source import CACHE

DTO_WINDOW = 180          # trading days
DTO_MIN = 90
SUV_MIN_DAYS = 5          # trading days in the month; the panel shows no threshold
SUV_DDOF = 1              # residual variance divides by n - 1 (ratio to the panel 1.0000; n - 3 gives 1.054)


def daily_years() -> list[int]:
    """Calendar years the daily file covers, in order."""
    return sorted(int(Path(f).stem) for f in glob.glob(str(CACHE / "daily_raw" / "*.parquet")))


def _daily(years: list[int] | None = None) -> pd.DataFrame:
    files = sorted(glob.glob(str(CACHE / "daily_raw" / "*.parquet")))
    if years:
        files = [f for f in files if int(Path(f).stem) in years]
    frames = [pd.read_parquet(f, columns=["permno", "d", "r", "v", "s"]) for f in files]
    d = pd.concat(frames, ignore_index=True)
    d = d.sort_values(["permno", "d"]).reset_index(drop=True)
    d["month"] = (d["d"].dt.year * 100 + d["d"].dt.month).astype("int32")
    with np.errstate(invalid="ignore", divide="ignore"):
        d["turn"] = np.where(d["s"] > 0, d["v"] / (d["s"] * 1000.0), np.nan).astype("float32")
    return d


def month_end(d: pd.DataFrame, suv: bool = True) -> pd.DataFrame:
    """Per (permno, month): DTO and SUV on the month's last trading day."""
    g = d.groupby("permno", sort=False)
    mean180 = g["turn"].transform(
        lambda s: s.rolling(DTO_WINDOW, min_periods=DTO_MIN).mean().shift(1))
    d["dto"] = d["turn"] - mean180
    if suv:
        d["suv"] = _within_month_suv(d)
    last = d.groupby(["permno", "month"]).tail(1)
    cols = ["permno", "month", "dto"] + (["suv"] if suv else [])
    return last[cols].reset_index(drop=True)


def _within_month_suv(d: pd.DataFrame) -> np.ndarray:
    """Last day's standardised residual from that month's own regression of
    daily volume on the day's positive and negative return.

    The regression is estimated on the calendar month's trading days only,
    the day being scored included, and the residual is divided by the
    regression's residual standard deviation. Solved from the month's
    cross-moment sums so no per-firm-month loop is needed.
    """
    y = d["v"].to_numpy(float)
    r = d["r"].to_numpy(float)
    rp = np.clip(r, 0, None); rn = np.clip(-r, 0, None)
    P = pd.DataFrame({"one": 1.0, "rp": rp, "rn": rn, "y": y, "rprp": rp * rp,
                      "rnrn": rn * rn, "rprn": rp * rn, "rpy": rp * y, "rny": rn * y,
                      "yy": y * y}, index=d.index)
    S = P.groupby([d["permno"], d["month"]]).transform("sum")
    A = np.stack([np.stack([S["one"], S["rp"], S["rn"]], 1),
                  np.stack([S["rp"], S["rprp"], S["rprn"]], 1),
                  np.stack([S["rn"], S["rprn"], S["rnrn"]], 1)], 1)
    b = np.stack([S["y"], S["rpy"], S["rny"]], 1)
    n = S["one"].to_numpy()
    beta = np.full(b.shape, np.nan)
    ok = np.isfinite(A).all((1, 2)) & np.isfinite(b).all(1) & (n >= SUV_MIN_DAYS)
    idx = np.flatnonzero(ok)
    with np.errstate(all="ignore"):
        det = np.linalg.det(A[idx])
        scale = np.prod(np.diagonal(A[idx], axis1=1, axis2=2), axis=1)
    idx = idx[np.abs(det) > 1e-10 * np.abs(scale)]
    beta[idx] = np.linalg.solve(A[idx], b[idx][..., None])[..., 0]
    rss = S["yy"].to_numpy() - (beta * b).sum(1)
    with np.errstate(all="ignore"):
        sig = np.sqrt(np.where(rss > 0, rss, np.nan) / (n - SUV_DDOF))
        resid = y - (beta[:, 0] + beta[:, 1] * rp + beta[:, 2] * rn)
        return resid / sig


def build(years: list[int] | None = None, suv: bool = True) -> pd.DataFrame:
    out = month_end(_daily(years), suv=suv)
    out["permno"] = out["permno"].astype("int64")
    return out
