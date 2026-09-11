"""The stochastic discount factor, on any sample.

`portfolio.py` reads the market return, the risk-free rate and the market price
of risk out of the replication package, which pins it to 1964-2017. Everything
here takes those as arguments instead, so the same machinery runs on a sample
that extends past the paper's.

The market price of risk is not a free parameter. The paper fixes it by
requiring the market's own price wedge to be exactly zero -- the market is not
mispriced relative to itself -- and everything else is measured against that.
Extending the sample therefore means re-solving for it, not carrying the
published value forward.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import brentq

from . import config as C


def discount_factor(rm: np.ndarray, rf: np.ndarray, lam: float,
                    horizon: int = C.HORIZON_MONTHS) -> tuple[np.ndarray, int]:
    """Cumulative, bias-adjusted SDF by (formation cohort, months after formation).

    `rm` is the market return in excess of `rf`, both monthly and aligned, over
    the months a portfolio can be formed in and tracked through.
    """
    n_months = len(rm)
    n_cohorts = n_months - horizon + 1
    if n_cohorts < 1:
        raise ValueError(f"{n_months} months is too few for a {horizon}-month horizon")

    rm_log = np.log(1.0 + rf + rm)
    rf_log = np.log(1.0 + rf)
    f = rm_log - rf_log
    var_f = np.var(f, ddof=1)

    neg_m = rf_log + 0.5 * lam * var_f * lam + (f - f.mean()) * lam
    m = np.exp(-neg_m)

    window = np.arange(horizon)[None, :] + np.arange(n_cohorts)[:, None]
    m_cum = np.cumprod(m[window], axis=1)

    # The estimated mean excess return is biased downward, and the bias
    # compounds with the horizon (Section 3.2 and Appendix D).
    horizons = np.arange(1, horizon + 1)
    debias = np.exp(lam**2 * horizons**2 / n_months * var_f / 2.0)
    return m_cum * debias[None, :], n_cohorts


def wedge(ybh: np.ndarray, ybhx: np.ndarray, portfolio: int, mtj: np.ndarray,
          n_cohorts: int, horizon: int, start: int = 0) -> float:
    """Price wedge of one portfolio, in logs, given a discount factor."""
    from .portfolio import _cash_flows, _wedge_at_horizon

    j = horizon - 1
    dividends, gain = _cash_flows(ybh, ybhx, portfolio, n_cohorts, j)
    return float(_wedge_at_horizon(dividends, gain, mtj, j, start)[0])


def solve_lambda(ybh: np.ndarray, ybhx: np.ndarray, rm: np.ndarray, rf: np.ndarray,
                 market: int = 10, horizon: int = C.HORIZON_MONTHS,
                 bracket: tuple[float, float] = (0.1, 12.0)) -> float:
    """The market price of risk that makes the market's price wedge zero.

    `ybh` and `ybhx` come from a sort whose eleventh portfolio is the whole
    sortable universe, which is what the paper treats as the market.
    """
    def residual(lam: float) -> float:
        mtj, n_cohorts = discount_factor(rm, rf, lam, horizon)
        return wedge(ybh, ybhx, market, mtj, n_cohorts, horizon)

    low, high = bracket
    f_low, f_high = residual(low), residual(high)
    if np.sign(f_low) == np.sign(f_high):
        raise ValueError(
            f"market wedge does not change sign on [{low}, {high}]: "
            f"{f_low:.4f} to {f_high:.4f}"
        )
    return float(brentq(residual, low, high, xtol=1e-10, rtol=1e-12))
