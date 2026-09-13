#!/usr/bin/env python3
"""Compare decile membership, firm by firm, against the paper's own sorts.

`t_by_n/Allocation/<char>.mat` (from MainPart4PWfirmLevel.m, section 1) holds
`allocation`: for every formation month from July 1964 and every security,
which decile the paper's sort put it in, or NaN if it was not in the sort.
That is the sharpest test of a sort there is -- sharper than decile
capitalisation weights, which can agree while membership differs at the edges.

Three numbers per characteristic: how often we agree on whether a security is
in the sort at all; among securities both sorts include, how often we put it
in the same decile; and how often within one decile of theirs.

    ./.venv/bin/python compare_allocation.py [--chars A,B,C]
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
import scipy.io as sio

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pwsite.panel import build_grids
from pwsite.sorts import MIN_FIRMS, assign_deciles
from pwsite.spec_ids import ALL_CHARACTERISTICS
from pwsite.tbyn import package_permnos

FOLDER = Path("/Users/opp/Dropbox/Papers/Build-up-vs-Resolution/ReplicationPackage/t_by_n/Allocation")
FIRST_ROW_MONTH = 196407          # allocation row 1


def month_add(yyyymm: int, k: int) -> int:
    y, m = divmod(yyyymm, 100)
    m0 = (m - 1) + k
    return (y + m0 // 12) * 100 + (m0 % 12) + 1


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--chars", default=None)
    args = p.parse_args()
    wanted = args.chars.split(",") if args.chars else ALL_CHARACTERISTICS

    g = build_grids()
    permnos = package_permnos()
    shared = np.intersect1d(permnos, g.permnos)
    pi = {q: i for i, q in enumerate(permnos)}
    oi = {q: i for i, q in enumerate(g.permnos)}
    cp = np.array([pi[q] for q in shared]); co = np.array([oi[q] for q in shared])
    w = g.fixed["PORT_WEGHT"]; nyse = g.fixed["exchcd"] == 1
    base = np.isfinite(g.fixed["Returns"]) & np.isfinite(w) & np.isfinite(g.fixed["RetX_mb"])
    prior = np.ones(g.shape, bool)
    for k, v in g.fixed.items():
        if k not in {"Returns", "PORT_WEGHT", "RetX_mb"}:
            prior &= np.isfinite(v)
    month_index = {m: i for i, m in enumerate(g.months)}

    print(f"{'char':9}{'months':>8}{'in-sort agree':>15}{'same decile':>13}{'within 1':>10}"
          f"{'mean |diff|':>13}{'ours in':>10}{'theirs in':>11}")
    for name in wanted:
        f = FOLDER / f"{name}.mat"
        if not f.exists() or f.stat().st_size == 0 or name not in g.universe.columns:
            continue
        try:
            alloc = sio.loadmat(f)["allocation"]
        except Exception as e:
            print(f"{name:9} unreadable: {str(e)[:50]}"); continue
        x = g.grid(name)
        agree_in = same = within = absd = n_both = n_ours = n_theirs = 0
        months = 0
        for r in range(alloc.shape[0]):
            m = month_add(FIRST_ROW_MONTH, r)
            if m not in month_index:
                continue
            t = month_index[m]
            if t < g.first - 1:
                continue
            theirs = alloc[r, cp]                      # decile or NaN, our shared order
            present = base[t] & prior[t - 1] & np.isfinite(x[t - 1])
            ours = np.full(g.shape[1], np.nan)
            if present.sum() > MIN_FIRMS:
                mem = np.flatnonzero(present)
                ours[mem] = assign_deciles(x[t - 1][mem], nyse[t - 1][mem])
            ours = ours[co]
            tin, oin = np.isfinite(theirs), np.isfinite(ours)
            if not tin.any() and not oin.any():
                continue
            months += 1
            agree_in += (tin == oin).sum()
            both = tin & oin
            n_both += both.sum(); n_ours += oin.sum(); n_theirs += tin.sum()
            d = np.abs(theirs[both] - ours[both])
            same += (d == 0).sum(); within += (d <= 1).sum(); absd += d.sum()
        if months == 0:
            print(f"{name:9} no overlapping months"); continue
        tot = months * len(shared)
        print(f"{name:9}{months:>8}{agree_in/tot:15.1%}{same/max(n_both,1):13.1%}"
              f"{within/max(n_both,1):10.1%}{absd/max(n_both,1):13.3f}"
              f"{n_ours/months:10.0f}{n_theirs/months:11.0f}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
