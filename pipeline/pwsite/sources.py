"""Readers for the MATLAB replication package.

The package mixes MAT v5 and v7.3 (HDF5) files, and stores characteristic
panels transposed. This module hides both details and hands back plain numpy.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import h5py
import numpy as np
import scipy.io as sio

from . import config as C


def yyyymm_to_index(dates: np.ndarray) -> np.ndarray:
    """Months since 0 AD, so date arithmetic is subtraction."""
    return (dates // 100) * 12 + (dates % 100) - 1


@dataclass
class FirmWedges:
    """The 4x2 cell array of firm-level price wedges."""

    dates: np.ndarray          # (T,) int, yyyymm
    permnos: np.ndarray        # (N,) int
    cells: dict                # (row, col) -> (T, N) float64

    @property
    def n_months(self) -> int:
        return len(self.dates)

    @property
    def n_permnos(self) -> int:
        return len(self.permnos)


@lru_cache(maxsize=1)
def load_firm_wedges() -> FirmWedges:
    mat = sio.loadmat(C.PW_SHARE)
    cell = mat["PWshare"]
    return FirmWedges(
        dates=mat["rowdates"].ravel().astype(np.int32),
        permnos=mat["columnPERMNOS"].ravel().astype(np.int32),
        cells={(i, j): cell[i, j] for i in range(cell.shape[0]) for j in range(cell.shape[1])},
    )


@dataclass
class CrspAggregates:
    alpha1: np.ndarray          # (57,) one-month alpha of decile 1, sets sort direction
    rm: np.ndarray              # (642,) excess market return
    rf: np.ndarray              # (642,) risk-free rate
    l_point: float
    portfolio_mktshare: np.ndarray  # (642, 240, 57)


@lru_cache(maxsize=1)
def load_crsp() -> CrspAggregates:
    mat = sio.loadmat(C.CRSP)
    temps = mat["temps"][0, 0]
    return CrspAggregates(
        alpha1=mat["alpha1"].ravel(),
        rm=temps["Rm"].ravel(),
        rf=temps["RF"].ravel(),
        l_point=float(temps["L_point"].ravel()[0]),
        portfolio_mktshare=mat["datas_all_charP"],
    )


@lru_cache(maxsize=1)
def load_characteristic_names() -> tuple[list[str], np.ndarray]:
    """Return (all variable names, the 57 characteristic indices used in the paper).

    Mirrors the index gymnastics at the top of MainPart2.m: `Duration` is
    appended as entry 89, three extra characteristics are pushed onto `use_`,
    and then beta_monthly, LEV, SGNA and Duration are dropped again.
    """
    mat = sio.loadmat(C.VARNAMES)
    names = [str(x[0]) for x in mat["varnames"].ravel()] + ["Duration"]
    use = np.concatenate([mat["use_"].ravel().astype(int), [12, 42, 89]])
    keep = np.concatenate(
        [np.arange(0, 5), np.arange(6, 22), np.arange(23, 51), np.arange(52, len(use) - 1)]
    )
    return names, use[keep]


def used_characteristics() -> list[str]:
    names, use_chars = load_characteristic_names()
    return [names[k - 1] for k in use_chars]


def load_buy_and_hold(characteristic: str, rep_iss: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Post-formation total returns and capital gains for one characteristic sort.

    Returns `(ybh, ybhX)`, each (1099 formation months, 11 portfolios, 241 months
    after formation). Portfolio 11 (index 10) is the aggregate market.
    """
    mat = sio.loadmat(C.REP_ISS_DIRS[rep_iss] / f"{characteristic}.mat", variable_names=["ybh", "ybhX"])
    return mat["ybh"], mat["ybhX"]


class FirmPanel:
    """Lazy accessor for the (24742 x 1099) firm characteristic panels.

    dataforsort.mat is MAT v7.3, which stores MATLAB's (1099, 24742) matrices
    transposed as (24742, 1099). Each panel is ~217 MB in memory, so they are
    read on demand and released by the caller.
    """

    def __init__(self) -> None:
        self._f = h5py.File(C.DATA_FOR_SORT, "r")
        self._refs = self._f["data_fixed"]
        self.dates = self._f["dates"][0].astype(np.int32)   # 192606 .. 201712

    def panel(self, name: str) -> np.ndarray:
        """(N_permno, T) float64 for one of DATA_FIXED_ORDER."""
        i = C.DATA_FIXED_ORDER.index(name)
        return self._f[self._refs[i, 0]][:]

    def close(self) -> None:
        self._f.close()

    def __enter__(self) -> "FirmPanel":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
