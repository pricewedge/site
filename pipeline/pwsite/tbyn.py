"""Reading the paper's own characteristic panels, and comparing ours to them.

The characteristics the paper sorted on were built by Fahiz Baba-Yara and
stored one file per characteristic in the format `MainPart1.m` loads from
`t_by_n/`: a matrix `data` whose first column is the month as yyyymm and whose
remaining 24,742 columns are securities in the order `PWshare.mat` lists them.
The replication package shipped the folder empty; Andrea Tamoni supplied it.

With those files a characteristic can be checked firm by firm and month by
month, which is a far sharper test than the decile-weight agreement used until
now -- and the only one that can say *which* firms differ and by how much,
which is what settles a definition.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.io as sio

from . import config as C


def read_panel(path: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """The (months x securities) values and their yyyymm dates from one file.

    Rows whose date is not a number are dropped; the files carry one such row,
    the artefact of a slice that starts one position before July 1926.
    """
    path = Path(path)
    try:
        data = sio.loadmat(path)["data"]
    except (NotImplementedError, ValueError):
        import h5py
        with h5py.File(path) as h:
            data = np.array(h["data"]).T
    dated = np.isfinite(data[:, 0])
    return data[dated, 1:], data[dated, 0].astype(int)


def package_permnos() -> np.ndarray:
    return sio.loadmat(C.PW_SHARE)["columnPERMNOS"].ravel().astype(int)


@dataclass
class Comparison:
    name: str
    overlap: int
    exact: float          # share of overlapping firm-months equal to 1e-6
    within_1pct: float
    rank_corr: float
    median_ratio: float   # ours / theirs, over non-zero theirs
    coverage_theirs: int
    coverage_ours: int

    def row(self) -> str:
        return (f"{self.name:9}{self.overlap:>11,}{self.exact:9.1%}{self.within_1pct:11.1%}"
                f"{self.rank_corr:11.4f}{self.median_ratio:13.4f}"
                f"{100*(self.coverage_ours/self.coverage_theirs-1):+9.1f}%")


HEADER = (f"{'char':9}{'overlap':>11}{'exact':>9}{'within 1%':>11}{'rank corr':>11}"
          f"{'ours/theirs':>13}{'coverage':>10}")


def compare(name: str, theirs: np.ndarray, their_dates: np.ndarray,
            ours: np.ndarray, our_months: np.ndarray, our_permnos: np.ndarray,
            drop_negative: bool = False) -> Comparison:
    """Line one of their panels up with one of our grids and score agreement."""
    permnos = package_permnos()
    shared = np.intersect1d(permnos, our_permnos)
    pi = {p: i for i, p in enumerate(permnos)}
    oi = {p: i for i, p in enumerate(our_permnos)}
    cp = np.array([pi[p] for p in shared]); co = np.array([oi[p] for p in shared])
    drow = {d: i for i, d in enumerate(their_dates)}
    months = [m for m in our_months if m in drow]
    rp = np.array([drow[m] for m in months])
    ro = np.array([int(np.searchsorted(our_months, m)) for m in months])
    a = theirs[np.ix_(rp, cp)]
    b = ours[np.ix_(ro, co)]
    if drop_negative:
        a = np.where(a < 0, np.nan, a); b = np.where(b < 0, np.nan, b)
    ok = np.isfinite(a) & np.isfinite(b)
    x, y = a[ok], b[ok]
    rel = np.abs(x - y) / np.maximum(np.abs(x), 1e-9)
    nz = np.abs(x) > 0
    return Comparison(
        name=name, overlap=int(ok.sum()),
        exact=float((rel < 1e-6).mean()) if ok.any() else np.nan,
        within_1pct=float((rel < 0.01).mean()) if ok.any() else np.nan,
        rank_corr=float(pd.Series(x).corr(pd.Series(y), method="spearman")) if ok.sum() > 2 else np.nan,
        median_ratio=float(np.median(y[nz] / x[nz])) if nz.any() else np.nan,
        coverage_theirs=int(np.isfinite(a).sum()), coverage_ours=int(np.isfinite(b).sum()),
    )
