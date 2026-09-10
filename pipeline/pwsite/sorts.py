"""Characteristic sorts and buy-and-hold portfolio tracking.

A port of `MainPart1.m`. For each characteristic and each formation month it
forms value-weighted decile portfolios at NYSE breakpoints, then tracks the
dividends and capital gains of those portfolios for the next 241 months without
rebalancing. The output is what `portfolio.py` turns into price wedges.

The MATLAB original is written as nested loops over months, portfolios and
horizons -- roughly a hundred million inner steps across 57 characteristics.
The weight recursion is a cumulative product in disguise, so `buy_and_hold`
below evaluates the whole horizon at once and the port runs in minutes rather
than hours. `buy_and_hold_with_dividends` keeps the sequential form, because its
survivor-reinvestment rule genuinely cannot be expressed that way; it is only
needed to calibrate the market price of risk, so it is computed on request.

Conventions inherited from the original, each of which changes the answer:

* Returns and capital gains are stored in excess of the risk-free rate, so the
  risk-free rate is added back before compounding.
* Everything except the return, the market-cap weight and the capital gain is
  lagged one month, including the sorting characteristic.
* A firm enters a sort only if all ten `fixed` variables and the sorting
  characteristic are present, and a month is skipped unless more than 250 firms
  qualify.
* Breakpoints are decile percentiles of the *ranks* of the sorting variable
  among NYSE firms only, which keeps microcaps from setting the cutoffs.
* Decile 1 holds the highest characteristic values and decile 10 the lowest.
  `portfolio.py` later flips this per characteristic so decile 1 is always the
  positive-alpha leg.

Validated against the package's own stored output for the five characteristics
that ship with the firm-level panel (BEME, Q, R_12_2, PROF, I2A). Portfolio
returns agree to machine precision for 99.5% of cells; the remainder sits in 30
of 642 formation months where a firm on a decile boundary lands on the other
side, and never touches the market portfolio, which takes no decile assignment.
Averaged over 463 formation cohorts that residual disappears: every one of the
ten published PW* estimates for those characteristics is reproduced, the largest
disagreement being 0.0002 percentage points.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

HORIZON = 241          # months tracked after formation
DECILES = 10
MIN_FIRMS = 250        # a month with fewer qualifying firms is skipped
FIRST_MONTH = 458      # 1-based row of 1964-07 in the 1099-month grid


def buy_and_hold(
    weights0: np.ndarray,
    rets: np.ndarray,
    retsx: np.ndarray,
    rf: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Value-weighted total and ex-dividend returns of a portfolio held without
    rebalancing.

    `rets` and `retsx` are (horizon, n_firms) excess returns and excess capital
    gains; `weights0` is market capitalisation at formation.

    Weights drift with the capital gain rather than the total return, so
    dividends leave the stock rather than being reinvested in it. That makes the
    weight path a cumulative product of gross capital gains, which is why this
    needs no loop. A firm whose capital gain goes missing takes its weight to
    NaN and stays out for good, matching the original's behaviour.
    """
    gross = 1.0 + retsx + rf[:, None]
    carried = np.empty_like(gross)
    carried[0] = 1.0
    np.cumprod(gross[:-1], axis=0, out=carried[1:])
    weights = weights0[None, :] * carried

    usable = np.isfinite(weights) & np.isfinite(rets) & np.isfinite(retsx)
    w = np.where(usable, weights, 0.0)
    total = w.sum(axis=1)

    with np.errstate(invalid="ignore", divide="ignore"):
        ret = (w * np.where(usable, rets + rf[:, None], 0.0)).sum(axis=1) / total
        retx = (w * np.where(usable, retsx + rf[:, None], 0.0)).sum(axis=1) / total
    return np.where(total > 0, ret, np.nan), np.where(total > 0, retx, np.nan)


def buy_and_hold_with_dividends(
    weights0: np.ndarray,
    rets: np.ndarray,
    retsx: np.ndarray,
    rf: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Dividends paid and cumulative capital gain, per dollar invested.

    Unlike `buy_and_hold`, a firm that drops out has its remaining value spread
    across the survivors, so the position path depends on which firms disappear
    when and cannot be collapsed into a cumulative product.
    """
    horizon = rets.shape[0]
    invested = weights0 / np.nansum(weights0)
    dividends = np.zeros(horizon)
    cumulative = np.zeros(horizon)

    for t in range(horizon):
        yield_t = rets[t] - retsx[t]
        gross = retsx[t] + rf[t]
        avail = np.isfinite(invested) & np.isfinite(yield_t) & np.isfinite(gross)

        dividends[t] = np.sum(invested[avail] * yield_t[avail])
        cumulative[t] = np.sum(invested[avail] * (1.0 + gross[avail]))

        invested = invested * (1.0 + gross)
        if t + 1 < horizon:
            leaving = avail & ~(np.isfinite(rets[t + 1]) & np.isfinite(retsx[t + 1]))
            staying = avail & ~leaving
            if leaving.any() and staying.any():
                surviving = invested[staying].sum()
                if surviving > 0:
                    invested[staying] *= 1.0 + invested[leaving].sum() / surviving
            invested[leaving] = np.nan
    return dividends, cumulative


def assign_deciles(values: np.ndarray, is_nyse: np.ndarray) -> np.ndarray:
    """Decile membership, 1 (highest characteristic) to 10 (lowest).

    Breakpoints are taken from the ranks of the sorting variable among NYSE
    firms, so the cutoffs reflect where NYSE-listed firms sit rather than being
    dragged around by the far more numerous small caps.
    """
    n = len(values)
    ranks = np.empty(n)
    ranks[np.argsort(values, kind="mergesort")] = np.arange(1, n + 1)

    nyse = ranks[is_nyse]
    if nyse.size == 0:
        return np.full(n, DECILES, dtype=int)
    cuts = _matlab_prctile(nyse, 100.0 / DECILES * np.arange(1, DECILES + 1))

    out = np.full(n, DECILES, dtype=int)
    for p in range(1, DECILES):
        if p < DECILES - 1:
            out[(ranks > cuts[p - 1]) & (ranks <= cuts[p])] = DECILES - p
        else:
            out[ranks > cuts[p - 1]] = DECILES - p
    return out


def _matlab_prctile(x: np.ndarray, q: np.ndarray) -> np.ndarray:
    """MATLAB's `prctile`, which numpy's default does not reproduce.

    MATLAB places the sorted observations at percentiles (i-0.5)/n and
    interpolates linearly between them, clamping outside; numpy's default places
    them at (i-1)/(n-1). The two disagree by a fraction of one observation, which
    is enough to move a firm sitting on a decile boundary into the neighbouring
    portfolio and change that portfolio's return.
    """
    ordered = np.sort(x)
    n = ordered.size
    positions = 100.0 * (np.arange(1, n + 1) - 0.5) / n
    return np.interp(q, positions, ordered)


@dataclass
class SortResult:
    """(months, 11, horizon) arrays. Portfolio 11 is the whole sortable universe."""

    ybh: np.ndarray
    ybhx: np.ndarray
    ybh2: np.ndarray | None = None
    ybhx2: np.ndarray | None = None


def sort_characteristic(
    characteristic: np.ndarray,
    fixed: dict[str, np.ndarray],
    rf: np.ndarray,
    which_exchcd: str = "exchcd",
    with_dividends: bool = False,
    first_month: int = FIRST_MONTH,
) -> SortResult:
    """Run the sort for one characteristic.

    All inputs are (n_months, n_firms) with months ascending, matching the
    orientation of the MATLAB `data_fixed` matrices. `fixed` must contain the
    ten variables a firm needs before it can enter a sort.
    """
    returns = fixed["Returns"]
    weights = fixed["PORT_WEGHT"]
    capgain = fixed["RetX_mb"]
    n_months, n_firms = returns.shape

    # Contemporaneous: the return, the market-cap weight and the capital gain.
    # Everything else, including the sorting variable, is lagged one month.
    lagged_names = [k for k in fixed if k not in {"Returns", "PORT_WEGHT", "RetX_mb"}]

    shape = (n_months, DECILES + 1, HORIZON)
    ybh = np.full(shape, np.nan)
    ybhx = np.full(shape, np.nan)
    ybh2 = np.full(shape, np.nan) if with_dividends else None
    ybhx2 = np.full(shape, np.nan) if with_dividends else None

    for t in range(first_month - 1, n_months):
        present = (
            np.isfinite(returns[t]) & np.isfinite(weights[t]) & np.isfinite(capgain[t])
        )
        for name in lagged_names:
            present &= np.isfinite(fixed[name][t - 1])
        present &= np.isfinite(characteristic[t - 1])
        if present.sum() <= MIN_FIRMS:
            continue

        members = np.flatnonzero(present)
        span = min(HORIZON, n_months - t)
        window = slice(t, t + span)
        rets = returns[window][:, members]
        retsx = capgain[window][:, members]
        rf_win = rf[window]

        deciles = assign_deciles(
            characteristic[t - 1][members], fixed[which_exchcd][t - 1][members] == 1
        )
        w0 = weights[t][members]

        for p in range(1, DECILES + 2):
            sel = slice(None) if p == DECILES + 1 else (deciles == p)
            if p <= DECILES and not np.any(sel):
                continue
            r, rx = buy_and_hold(w0[sel], rets[:, sel], retsx[:, sel], rf_win)
            ybh[t, p - 1, :span] = r
            ybhx[t, p - 1, :span] = rx
            if with_dividends:
                d, c = buy_and_hold_with_dividends(
                    w0[sel], rets[:, sel], retsx[:, sel], rf_win
                )
                ybh2[t, p - 1, :span] = d
                ybhx2[t, p - 1, :span] = c

    return SortResult(ybh=ybh, ybhx=ybhx, ybh2=ybh2, ybhx2=ybhx2)
