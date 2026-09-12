"""How precisely each portfolio's price wedge is estimated.

A portfolio's wedge is minus the log of the average, across formation cohorts,
of the discounted cash flows per unit of price. Those cohorts overlap almost
completely -- adjacent ones share 179 of their 180 months -- so the average is
far less precise than 463 observations would suggest, and by very different
amounts across portfolios.

This reproduces the package's own standard error (`LibPWBootstrap/logPWse.m`):
regress the cohort-level ratio on a constant, take a Newey-West variance at the
horizon's lag length, and carry it through the logarithm by the delta method.
Its block bootstrap resamples cohorts in 180-month blocks, which is the same
dependence structure by another route.

The point of having these is that a mapping from characteristics to wedges is
fitting 570 numbers of unequal quality, and should say so.
"""

from __future__ import annotations

import numpy as np

from . import config as C


def newey_west_mean(x: np.ndarray, lag: int) -> tuple[float, float]:
    """Mean of `x` and its Newey-West variance, as `olsnwsdbeta` computes it."""
    x = x[np.isfinite(x)]
    n = len(x)
    if n <= lag + 1:
        return (np.nan, np.nan)
    mean = x.mean()
    e = x - mean
    # X is a column of ones, so (X'X)^-1 = 1/n and the sandwich collapses to a
    # Bartlett-weighted sum of autocovariances divided by n.
    omega = 0.0
    for k in range(lag + 1):
        weight = 1.0 - k / (1.0 + lag)
        cov = float(e[k:] @ e[: n - k]) / n
        omega += (1.0 if k == 0 else 2.0) * weight * cov
    return mean, omega / n


def wedge_standard_error(ratio: np.ndarray, lag: int | None = None) -> tuple[float, float]:
    """Price wedge and its standard error, from the cohort-level ratios.

    `ratio` is the discounted cash flow per unit of price for each formation
    cohort; the wedge is -log of its mean. The delta method turns the variance
    of the mean into the variance of the wedge, dividing by the mean squared.
    """
    lag = C.HORIZON_MONTHS - 1 if lag is None else lag
    mean, var = newey_west_mean(ratio, lag)
    if not np.isfinite(mean) or mean <= 0 or not np.isfinite(var) or var < 0:
        return (np.nan, np.nan)
    return -np.log(mean), np.sqrt(var) / mean


def block_bootstrap_se(ratio: np.ndarray, block: int | None = None,
                       draws: int = 2000, seed: int = 0) -> float:
    """Standard error of the wedge from a moving-block bootstrap over cohorts.

    Blocks are the length of the resolution horizon, which is the span over
    which two cohorts share data, matching the package's choice.
    """
    block = C.HORIZON_MONTHS if block is None else block
    x = ratio[np.isfinite(ratio)]
    n = len(x)
    if n < block + 1:
        return np.nan
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, n - block + 1, size=(draws, int(np.ceil(n / block))))
    out = np.empty(draws)
    index = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(draws, -1)[:, :n]
    means = x[index].mean(axis=1)
    out = -np.log(np.where(means > 0, means, np.nan))
    return float(np.nanstd(out, ddof=1))
