"""SUV and DTO as monthly characteristics, the way their sources define them.

Garfinkel (2009) defines both as daily quantities. Standardised unexplained
volume on a day is the day's volume minus the value fitted by a regression
of volume on the day's positive and negative return, divided by the residual
standard deviation of that regression, the regression estimated over a
window that precedes the day. Freyberger, Neuhierl and Weber make the
estimation window the previous calendar month. The month's characteristic is
the mean of the daily values over the month's trading days, which is
Garfinkel's own aggregation over his event window.

Detrended turnover starts from daily turnover with Nasdaq volume scaled down
(by 50% before 1997 and 38% from 1997, Anderson and Dyl 2005), subtracts the
market's turnover on the day (aggregate volume over aggregate shares of NYSE
and AMEX stocks, as in Garfinkel), and detrends by the firm's own median of
that market-adjusted series over the previous 180 trading days (FNW). The
month's characteristic is again the mean over the month's trading days.

Both need at least MIN_DAYS trading days in the month, as Table A.1 requires
of every daily characteristic; the SUV regression needs MIN_FIT days.

This module is the site's specification. `pwsite.lastday` builds what the
paper's data actually holds (the last trading day's value of each series).
"""

from __future__ import annotations

import glob
from pathlib import Path

import numpy as np
import pandas as pd

from .wrds_source import CACHE

MIN_DAYS = 15
MIN_FIT = 10
DTO_WINDOW = 180
DTO_MIN = 90
NASDAQ_SCALE_BEFORE_1997 = 0.50
NASDAQ_SCALE_FROM_1997 = 0.62


def _daily(years: list[int] | None = None) -> pd.DataFrame:
    files = sorted(glob.glob(str(CACHE / "daily_raw" / "*.parquet")))
    if years:
        files = [f for f in files if int(Path(f).stem) in years]
    d = pd.concat([pd.read_parquet(f, columns=["permno", "d", "r", "v", "s"]) for f in files],
                  ignore_index=True)
    d = d.sort_values(["permno", "d"]).reset_index(drop=True)
    d["month"] = (d["d"].dt.year * 100 + d["d"].dt.month).astype("int32")
    return d


def suv_monthly(d: pd.DataFrame) -> pd.DataFrame:
    """Mean over month t of the daily standardised residual, the regression
    fitted on month t-1's days."""
    y = d["v"].to_numpy(float)
    r = d["r"].to_numpy(float)
    rp = np.clip(r, 0, None); rn = np.clip(-r, 0, None)
    P = pd.DataFrame({"one": 1.0, "rp": rp, "rn": rn, "y": y, "rprp": rp * rp, "rnrn": rn * rn,
                      "rprn": rp * rn, "rpy": rp * y, "rny": rn * y, "yy": y * y}, index=d.index)
    S = P.groupby([d["permno"], d["month"]]).sum()          # one row per firm-month
    n = S["one"].to_numpy()
    A = np.stack([np.stack([S["one"], S["rp"], S["rn"]], 1),
                  np.stack([S["rp"], S["rprp"], S["rprn"]], 1),
                  np.stack([S["rn"], S["rprn"], S["rnrn"]], 1)], 1)
    b = np.stack([S["y"], S["rpy"], S["rny"]], 1)
    beta = np.full(b.shape, np.nan)
    ok = np.isfinite(A).all((1, 2)) & np.isfinite(b).all(1) & (n >= MIN_FIT)
    idx = np.flatnonzero(ok)
    with np.errstate(all="ignore"):
        det = np.linalg.det(A[idx]); scale = np.prod(np.diagonal(A[idx], axis1=1, axis2=2), axis=1)
    idx = idx[np.abs(det) > 1e-10 * np.abs(scale)]
    beta[idx] = np.linalg.solve(A[idx], b[idx][..., None])[..., 0]
    with np.errstate(all="ignore"):
        rss = S["yy"].to_numpy() - (beta * b).sum(1)
        sig = np.sqrt(np.where(rss > 0, rss, np.nan) / (n - 1))
        # a fit month whose residual dispersion is below 1% of its mean volume is
        # degenerate (a stock that barely traded); its standardised residuals
        # would be arbitrary. Everything else is kept: the measure is in levels
        # and heavy-tailed by construction, and the sorts use ranks.
        ybar = S["y"].to_numpy() / n
        sig = np.where((ybar > 0) & (sig >= 0.01 * ybar), sig, np.nan)
    fit = pd.DataFrame({"b0": beta[:, 0], "b1": beta[:, 1], "b2": beta[:, 2], "sig": sig},
                       index=S.index).reset_index()
    # the fit that applies to month t is the one estimated on the previous calendar month
    prev = fit["month"].to_numpy()
    nxt = np.where(prev % 100 == 12, (prev // 100 + 1) * 100 + 1, prev + 1)
    fit["month"] = nxt
    dd = d[["permno", "month"]].merge(fit, on=["permno", "month"], how="left")
    z = (y - (dd["b0"].to_numpy() + dd["b1"].to_numpy() * rp + dd["b2"].to_numpy() * rn)) / dd["sig"].to_numpy()
    out = pd.DataFrame({"permno": d["permno"], "month": d["month"], "z": z})
    g = out.groupby(["permno", "month"])["z"]
    res = g.mean().rename("SUV").reset_index()
    res["n"] = g.count().to_numpy()
    res.loc[res["n"] < MIN_DAYS, "SUV"] = np.nan
    return res.drop(columns="n")


def dto_monthly(d: pd.DataFrame, exchange: pd.DataFrame) -> pd.DataFrame:
    """Mean over the month of market-adjusted, Nasdaq-scaled daily turnover
    less its own trailing 180-trading-day median.

    `exchange` holds (permno, month, primaryexch) from the monthly file; the
    month's exchange is applied to every day of the month."""
    d = d.merge(exchange, on=["permno", "month"], how="left")
    exch = d["primaryexch"].fillna("").astype(str).to_numpy()
    year = d["d"].dt.year.to_numpy()
    nasdaq = exch == "Q"
    scale = np.where(nasdaq, np.where(year < 1997, NASDAQ_SCALE_BEFORE_1997, NASDAQ_SCALE_FROM_1997), 1.0)
    v = d["v"].to_numpy(float) * scale
    shares = d["s"].to_numpy(float) * 1000.0
    with np.errstate(invalid="ignore", divide="ignore"):
        d["turn"] = np.where(shares > 0, v / shares, np.nan)
    nyam = np.isin(exch, ["N", "A"]) & np.isfinite(v) & (shares > 0)
    mk = pd.DataFrame({"d": d["d"], "v": np.where(nyam, v, 0.0), "s": np.where(nyam, shares, 0.0)}).groupby("d").sum()
    mkt = (mk["v"] / mk["s"]).rename("mkt_turn")
    d = d.merge(mkt, left_on="d", right_index=True, how="left")
    d["mato"] = d["turn"] - d["mkt_turn"]
    med = d.groupby("permno", sort=False)["mato"].transform(
        lambda s: s.rolling(DTO_WINDOW, min_periods=DTO_MIN).median().shift(1))
    d["dt"] = d["mato"] - med
    g = d.groupby(["permno", "month"])["dt"]
    res = g.mean().rename("DTO").reset_index()
    res["n"] = g.count().to_numpy()
    res.loc[res["n"] < MIN_DAYS, "DTO"] = np.nan
    return res.drop(columns="n")


def build(exchange: pd.DataFrame, years: list[int] | None = None) -> pd.DataFrame:
    d = _daily(years)
    out = suv_monthly(d).merge(dto_monthly(d, exchange), on=["permno", "month"], how="outer")
    out["permno"] = out["permno"].astype("int64")
    return out
