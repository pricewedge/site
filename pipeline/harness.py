#!/usr/bin/env python3
"""Score a candidate characteristic against the package's published decile weights.

`validate.py` answers "does the pipeline reproduce the paper". This answers the
narrower question a definitional experiment needs: given one candidate series
for one characteristic, how closely do its decile capitalisation weights track
the package's? No buy-and-hold, no discount factor, so a variant can be tried in
seconds rather than minutes.

The trick that makes it cheap: whether a firm can enter a sort depends on the
ten fixed variables, which never change between candidates. That mask is
computed once and reused, leaving only the candidate's own missingness and the
decile assignment per month.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pwsite.sorts import DECILES, MIN_FIRMS, assign_deciles
from pwsite.wrds_source import CACHE

FORMATION_MONTHS = 462


class Harness:
    def __init__(self) -> None:
        from validate import _package_root, panel, published

        root = _package_root()
        _, self.order, self.alpha, self.weights = published(root)
        (self.universe, self.months, self.grid, self.rf,
         self.fixed, self.first) = panel()
        self.index = {v: i for i, v in enumerate(self.months)}
        permnos = np.array(sorted(self.universe.permno.unique()))
        self.column = {v: i for i, v in enumerate(permnos)}
        self.shape = (len(self.months), len(permnos))

        # The part of admissibility that no candidate can change.
        f = self.fixed
        base = (np.isfinite(f["Returns"]) & np.isfinite(f["PORT_WEGHT"])
                & np.isfinite(f["RetX_mb"]))
        lagged = [k for k in f if k not in {"Returns", "PORT_WEGHT", "RetX_mb"}]
        prior = np.ones(self.shape, dtype=bool)
        for name in lagged:
            prior &= np.isfinite(f[name])
        self.base = base
        self.prior = prior
        self.nyse = f["exchcd"] == 1
        self.weight = f["PORT_WEGHT"]

    def to_grid(self, frame: pd.DataFrame, values) -> np.ndarray:
        """Lay a (permno, month)-keyed series onto the firm-by-month grid."""
        out = np.full(self.shape, np.nan)
        rows = frame["month"].map(self.index)
        cols = frame["permno"].astype("int64").map(self.column)
        ok = (rows.notna() & cols.notna()).to_numpy()
        out[rows[ok].astype(int), cols[ok].astype(int)] = np.asarray(
            values, dtype=float)[ok]
        return out

    def shares(self, x: np.ndarray) -> np.ndarray:
        out = np.full((len(self.months), DECILES), np.nan)
        for t in range(self.first - 1, len(self.months)):
            present = self.base[t] & self.prior[t - 1] & np.isfinite(x[t - 1])
            if present.sum() <= MIN_FIRMS:
                continue
            members = np.flatnonzero(present)
            deciles = assign_deciles(x[t - 1][members], self.nyse[t - 1][members])
            w0 = self.weight[t][members]
            total = np.nansum(w0)
            for p in range(1, DECILES + 1):
                out[t, p - 1] = np.nansum(w0[deciles == p]) / total
        return out[self.first - 1:]

    def score(self, characteristic: str, x: np.ndarray) -> dict:
        """Mean and per-decile agreement with the package, plus mean weights."""
        k = self.order[characteristic]
        s = self.shares(x)
        if self.alpha[k] < 0:
            s = s[:, ::-1]
        n = min(FORMATION_MONTHS, s.shape[0])
        mine, theirs = s[:n] * 100, self.weights[:n, :, k] * 100
        usable = np.isfinite(mine[:, 0]) & np.isfinite(theirs[:, 0])
        if usable.sum() <= 10:
            return {"mean": np.nan, "per_decile": [], "months": int(usable.sum())}
        per = [np.corrcoef(mine[usable, j], theirs[usable, j])[0, 1]
               for j in range(DECILES)]
        return {"mean": float(np.mean(per)), "per_decile": per,
                "months": int(usable.sum()),
                "mine_1": float(np.nanmean(mine[:, 0])),
                "pub_1": float(np.nanmean(theirs[:, 0])),
                "mine_10": float(np.nanmean(mine[:, 9])),
                "pub_10": float(np.nanmean(theirs[:, 9]))}

    def report(self, label: str, characteristic: str, x: np.ndarray) -> dict:
        r = self.score(characteristic, x)
        if np.isnan(r["mean"]):
            print(f"{label:38}   too few months ({r['months']})", flush=True)
        else:
            print(f"{label:38}{r['mean']:8.3f}{r['per_decile'][0]:7.2f}"
                  f"{r['mine_1']:8.2f}{r['pub_1']:7.2f}"
                  f"{r['mine_10']:8.2f}{r['pub_10']:7.2f}", flush=True)
        r["label"] = label
        r["characteristic"] = characteristic
        return r


HEADER = (f"{'candidate':38}{'mean':>8}{'d1':>7}{'mine1':>8}{'pub1':>7}"
          f"{'mine10':>8}{'pub10':>7}")
