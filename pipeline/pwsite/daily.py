"""The nine characteristics built from CRSP's daily file.

Nothing here reads daily data. `wrds_source.daily_moments` reduces each
firm-month of daily observations to a row of sums on WRDS's server, and every
characteristic below is recovered from those sums exactly:

* a standard deviation needs the count, the sum and the sum of squares;
* a least-squares fit needs only the cross-product matrix of its regressors,
  and the residual sum of squares follows from the fitted coefficients;
* a maximum and a mean are already there.

The one exception is DTO, whose 180-trading-day median is not a moment of any
month. It is approximated here from a rolling window of monthly means, and
said so.

Sample rule: at least fifteen daily observations in the month, as Appendix
Table A.1 requires. Below that the month is left missing rather than estimated
from a handful of days.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

MIN_DAYS = 15

# CRSP counts both sides of a Nasdaq dealer trade, so Nasdaq volume is roughly
# double a comparable NYSE figure. Appendix Table A.1 scales it down by 50%
# before 1997 and 38% after, which is the convention DTO is defined on.
NASDAQ_SCALE_PRE = 0.50
NASDAQ_SCALE_POST = 0.38
NASDAQ_SPLIT_YEAR = 1997


def _sd(n: np.ndarray, s: np.ndarray, ss: np.ndarray) -> np.ndarray:
    """Sample standard deviation from count, sum and sum of squares."""
    with np.errstate(invalid="ignore", divide="ignore"):
        var = (ss - s * s / n) / (n - 1)
    return np.sqrt(np.where(var > 0, var, np.nan))


def _solve(gram: np.ndarray, moment: np.ndarray) -> np.ndarray:
    """Least-squares coefficients for a stack of normal equations.

    `gram` is (rows, k, k) and `moment` is (rows, k). A singular month -- a
    factor with no variation across the days observed -- yields NaN rather than
    raising, so one bad firm-month does not stop the pass.
    """
    out = np.full(moment.shape, np.nan)
    ok = np.isfinite(gram).all(axis=(1, 2)) & np.isfinite(moment).all(axis=1)
    if ok.any():
        sub = gram[ok]
        good = np.abs(np.linalg.det(sub)) > 1e-30
        idx = np.flatnonzero(ok)[good]
        if idx.size:
            out[idx] = np.linalg.solve(gram[idx], moment[idx])
    return out


def daily_characteristics(moments: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    """Turn per-firm-month daily moments into the nine characteristics.

    `monthly` supplies each firm-month's exchange, which decides the Nasdaq
    volume adjustment.
    """
    d = moments.copy()
    d["month"] = pd.to_datetime(d["month"]).dt.year * 100 + pd.to_datetime(d["month"]).dt.month
    d["permno"] = d["permno"].astype("int64")
    d = d.merge(
        monthly[["permno", "month", "primaryexch"]].drop_duplicates(["permno", "month"]),
        on=["permno", "month"], how="left",
    ).sort_values(["permno", "month"])

    n = d["n"].to_numpy(float)
    enough = n >= MIN_DAYS
    out = d[["permno", "month"]].copy()

    def col(name: str) -> np.ndarray:
        return d[name].to_numpy(float)

    # --- dispersion and extremes -------------------------------------------
    out["RETVOL"] = np.where(enough, _sd(n, col("s_re"), col("s_rere")), np.nan)
    out["MAXRET"] = np.where(enough, col("max_r"), np.nan)
    out["sdDVOL"] = np.where(enough, _sd(n, col("s_dv"), col("s_dvdv")), np.nan)
    nt = col("n_turn")
    out["sdTURN"] = np.where(nt >= MIN_DAYS, _sd(nt, col("s_t"), col("s_tt")), np.nan)
    nq = col("n_spr")
    with np.errstate(invalid="ignore", divide="ignore"):
        out["SPREAD"] = np.where(nq >= MIN_DAYS, col("s_spr") / nq, np.nan)

    # --- BETA_d: the sum of the coefficients on the market and its lag ------
    gram = np.stack([
        np.stack([n,            col("s_m"),   col("s_ml")],   axis=1),
        np.stack([col("s_m"),   col("s_mm"),  col("s_mml")],  axis=1),
        np.stack([col("s_ml"),  col("s_mml"), col("s_mlml")], axis=1),
    ], axis=1)
    rhs = np.stack([col("s_re"), col("s_rem"), col("s_reml")], axis=1)
    beta = _solve(gram, rhs)
    out["BETA_d"] = np.where(enough, beta[:, 1] + beta[:, 2], np.nan)

    # --- IDIOV: residual dispersion around the three-factor model -----------
    z = np.zeros_like(n)
    g4 = np.stack([
        np.stack([n,           col("s_m"),  col("s_s"),  col("s_h")],  axis=1),
        np.stack([col("s_m"),  col("s_mm"), col("s_ms"), col("s_mh")], axis=1),
        np.stack([col("s_s"),  col("s_ms"), col("s_ss"), col("s_sh")], axis=1),
        np.stack([col("s_h"),  col("s_mh"), col("s_sh"), col("s_hh")], axis=1),
    ], axis=1)
    r4 = np.stack([col("s_re"), col("s_rem"), col("s_res"), col("s_reh")], axis=1)
    coef = _solve(g4, r4)
    with np.errstate(invalid="ignore"):
        rss = col("s_rere") - (coef * r4).sum(axis=1)
        idiov = np.sqrt(np.where(rss > 0, rss, np.nan) / (n - 4))
    out["IDIOV"] = np.where(enough, idiov, np.nan)

    # --- SUV: this month's volume against last month's volume-return fit ----
    # The fit is estimated on the previous month and applied to this one, so a
    # month's unexplained volume is genuinely out of sample.
    g3 = np.stack([
        np.stack([n,            col("s_rp"),    col("s_rn")],    axis=1),
        np.stack([col("s_rp"),  col("s_rprp"),  col("s_rprn")],  axis=1),
        np.stack([col("s_rn"),  col("s_rprn"),  col("s_rnrn")],  axis=1),
    ], axis=1)
    r3 = np.stack([col("s_v"), col("s_vrp"), col("s_vrn")], axis=1)
    vcoef = _solve(g3, r3)
    with np.errstate(invalid="ignore"):
        vrss = col("s_vv") - (vcoef * r3).sum(axis=1)
        vsd = np.sqrt(np.where(vrss > 0, vrss, np.nan) / (n - 3))

    prior = pd.DataFrame(vcoef, columns=["a", "b", "c"], index=d.index)
    prior["sd"] = vsd
    prior["permno"] = d["permno"].to_numpy()
    lagged = prior.groupby("permno")[["a", "b", "c", "sd"]].shift(1)
    predicted = (
        lagged["a"].to_numpy() * n
        + lagged["b"].to_numpy() * col("s_rp")
        + lagged["c"].to_numpy() * col("s_rn")
    )
    with np.errstate(invalid="ignore", divide="ignore"):
        suv = (col("s_v") - predicted) / (n * lagged["sd"].to_numpy())
    out["SUV"] = np.where(enough, suv, np.nan)

    # --- DTO: turnover in excess of the market's, detrended -----------------
    year = d["month"].to_numpy() // 100
    scale = np.where(
        d["primaryexch"].isin(["Q", "R"]).to_numpy(),
        np.where(year < NASDAQ_SPLIT_YEAR, NASDAQ_SCALE_PRE, NASDAQ_SCALE_POST),
        1.0,
    )
    with np.errstate(invalid="ignore", divide="ignore"):
        turn = scale * col("s_t") / nt
    frame = pd.DataFrame({"permno": d["permno"].to_numpy(), "month": d["month"].to_numpy(),
                          "turn": turn})
    market = frame.groupby("month")["turn"].transform("mean")
    excess = frame["turn"] - market
    # The 180-trading-day median is about nine months; taken over monthly means
    # rather than over the days themselves, which the moments cannot recover.
    frame["_e"] = excess
    median = (
        frame.groupby("permno")["_e"]
        .rolling(9, min_periods=6).median().reset_index(level=0, drop=True)
    )
    out["DTO"] = np.where(nt >= MIN_DAYS, (excess - median).to_numpy(), np.nan)

    return out
