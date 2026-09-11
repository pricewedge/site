"""Portfolio-level price wedges, rebuilt from the replication package.

This is a direct port of MainPart2.m. It reproduces the PW* column of Table 1
exactly (verified in `validate.py`), and then goes beyond the published table by
computing every decile rather than only the extremes, and the wedge remaining at
each annual horizon after portfolio formation.

The site charts firm-level wedges only; these series exist so researchers can
download the portfolio estimates.
"""

from __future__ import annotations

import numpy as np

from . import config as C
from .sources import load_buy_and_hold, load_crsp, used_characteristics


def _stochastic_discount_factor(rep_iss: int) -> tuple[np.ndarray, int, int]:
    """Cumulative, bias-adjusted SDF by (formation cohort, months after formation)."""
    crsp = load_crsp()
    n_months = len(crsp.rm)                       # 642 months, 1964-07 .. 2017-12
    n_cohorts = n_months - C.HORIZON_MONTHS + 1   # 463 formation months
    lam = C.L_POINT[rep_iss]

    rm_log = np.log(1.0 + crsp.rf + crsp.rm)
    rf_log = np.log(1.0 + crsp.rf)
    f = rm_log - rf_log
    var_f = np.var(f, ddof=1)

    neg_m = rf_log + 0.5 * lam * var_f * lam + (f - f.mean()) * lam
    m = np.exp(-neg_m)

    window = np.arange(C.HORIZON_MONTHS)[None, :] + np.arange(n_cohorts)[:, None]
    m_cum = np.cumprod(m[window], axis=1)

    # Section 3.2 / Appendix D: correct the downward bias in the estimated mean
    # excess return that compounds with the horizon.
    horizons = np.arange(1, C.HORIZON_MONTHS + 1)
    debias = np.exp(lam**2 * horizons**2 / n_months * var_f / 2.0)
    return m_cum * debias[None, :], n_cohorts, n_months


def _cash_flows(ybh: np.ndarray, ybh_x: np.ndarray, portfolio: int, n_cohorts: int,
                j: int, start_row: int | None = None):
    """Dividends and cumulative capital gains per $1 invested at formation.

    `start_row` is the row of the first formation month. It defaults to the
    package's own layout, where the arrays span 1926 onward and formation
    begins at row 458; a sort run on a different window passes its own.
    """
    start = C.FIRST_FORMATION_ROW - 1 if start_row is None else start_row
    total = ybh[start : start + n_cohorts, portfolio, : j + 1]
    capital = ybh_x[start : start + n_cohorts, portfolio, : j + 1]

    gain_lag = np.concatenate(
        [np.ones((total.shape[0], 1)), np.cumprod(1.0 + capital[:, :-1], axis=1)], axis=1
    )                                        # P_{t+j-1} / P_{t-1}
    gain = np.cumprod(1.0 + capital, axis=1)  # P_{t+j}   / P_{t-1}
    dividends = (total - capital) * gain_lag
    return dividends, gain


def _wedge_at_horizon(dividends, gain, mtj, j, start):
    """-log E[ discounted cash flows from month `start+1` on, per unit of price then ].

    Column `s` of `dividends`/`gain` is month `s+1` after formation, so `start=0`
    is the price wedge at formation, Eq. (1)-(3), where the base price is 1 by
    construction and nothing is discounted yet. `start = 12*h` re-bases on the
    price and cumulative SDF at the end of year `h`, which is the "wedge
    remaining after h years" of Figs. 5 and 6: for h=5 the first cash flow is the
    dividend paid in month 61 and the terminal value is still P_180.
    """
    value = np.nansum(dividends[:, start:j] * mtj[:, start:j], axis=1)
    value += (gain[:, j] + dividends[:, j]) * mtj[:, j]
    base = 1.0 if start == 0 else gain[:, start - 1] * mtj[:, start - 1]
    ratio = value / base
    return -np.log(np.nanmean(ratio)), ratio


def build(rep_iss: int = 0) -> dict:
    crsp = load_crsp()
    mtj, n_cohorts, _ = _stochastic_discount_factor(rep_iss)
    j = C.HORIZON_MONTHS - 1
    characteristics = used_characteristics()

    rows = []
    for pos, name in enumerate(characteristics):
        ybh, ybh_x = load_buy_and_hold(name, rep_iss)
        if crsp.alpha1[pos] < 0:
            # Orient every sort so that decile 1 is the positive-alpha ("long") leg.
            ybh, ybh_x = ybh.copy(), ybh_x.copy()
            ybh[:, 0:10, :] = ybh[:, 9::-1, :]
            ybh_x[:, 0:10, :] = ybh_x[:, 9::-1, :]

        for portfolio in range(11):           # 0..9 deciles, 10 = aggregate market
            dividends, gain = _cash_flows(ybh, ybh_x, portfolio, n_cohorts, j)
            wedge, _ = _wedge_at_horizon(dividends, gain, mtj, j, 0)

            horizons = {}
            for years in C.EVENT_YEARS:
                start = 12 * years
                if start >= j:
                    continue
                horizons[years] = float(_wedge_at_horizon(dividends, gain, mtj, j, start)[0])

            share = float(np.mean(crsp.portfolio_mktshare[:n_cohorts, 40 + portfolio, pos]))
            rows.append(
                {
                    "characteristic": name,
                    "portfolio": "MKT" if portfolio == 10 else str(portfolio + 1),
                    "pw": float(wedge),
                    "pwByYearsAfterFormation": horizons,
                    "crspShare": share,
                    "dollarWedge": float((1.0 - np.exp(-wedge)) * share),
                    "alphaSignFlipped": bool(crsp.alpha1[pos] < 0),
                }
            )
        del ybh, ybh_x

    return {
        "repIss": rep_iss,
        "cohorts": n_cohorts,
        "horizonMonths": C.HORIZON_MONTHS,
        "rows": rows,
    }
