"""Cross-sectional characteristic percentiles for the optional characteristic panel.

Each month, a characteristic is rank-normalised to [0, 1] across the *sortable
universe*: firms for which all ten variables in `fixed` (MainPart2.m) are
observed. That universe reproduces the percentiles behind Fig. 7 Panel C of the
paper to within 0.006 for Apple, against 0.037 if the universe is left
unrestricted, so the restriction is what the paper used.

Timing note: a price wedge dated t is built from characteristics dated t-1. The
paper's Fig. 7 nevertheless plots percentiles at their own calendar date, and we
follow it; the convention is recorded in the manifest.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import rankdata

from . import config as C
from .sources import FirmPanel


def _midrank(values: np.ndarray, universe: np.ndarray) -> np.ndarray:
    """Column-wise percentile of `values` within `universe`, ties at midpoint.

    `values` and `universe` are (N firms, T months). Returns (N, T) in [0, 1]
    with NaN wherever the firm is outside the universe. The estimator is
    (#below + #tied/2) / #universe, which is what reproduces Fig. 7 Panel C.
    """
    out = np.full(values.shape, np.nan, dtype=np.float32)
    n_valid = universe.sum(axis=0)
    for t in range(values.shape[1]):
        n = int(n_valid[t])
        if n < 20:
            continue
        inside = universe[:, t]
        obs = values[inside, t]
        # rankdata 'average' gives (#below + (#tied+1)/2); shifting by 0.5 turns
        # that into (#below + #tied/2).
        out[inside, t] = ((rankdata(obs, method="average") - 0.5) / n).astype(np.float32)
    return out


def compute_percentiles(month_index: np.ndarray) -> dict[str, np.ndarray]:
    """Percentiles plus raw market cap and a capital-gain index.

    `month_index` selects columns of the 1099-month source grid (i.e. the 642
    months covered by the price wedges). Returns (N firms, T months) float32
    arrays keyed by series id.
    """
    with FirmPanel() as fp:
        universe = None
        needed = {}
        for name in C.DATA_FIXED_ORDER:
            panel = fp.panel(name)
            finite = np.isfinite(panel)
            universe = finite if universe is None else (universe & finite)
            if name in {"PORT_WEGHT", "RetX_mb"} or name in {c["source"] for c in C.RANK_CHARS}:
                needed[name] = panel
            del panel

        result: dict[str, np.ndarray] = {}
        for spec in C.RANK_CHARS:
            if spec["id"] not in C.PACKED_CHARS:
                continue          # ranking every month is slow; skip what is unused
            src = needed[spec["source"]]
            result[spec["id"]] = _midrank(src[:, month_index], universe[:, month_index])

        mktcap = needed["PORT_WEGHT"][:, month_index].astype(np.float32)
        result["mktcap"] = mktcap


    return result
