"""Regression tests against numbers published in the paper.

The build refuses to emit data if any of these fail, so a future re-run against
an updated CRSP pull cannot silently change the published estimates.
"""

from __future__ import annotations

import numpy as np
import openpyxl

from . import config as C
from .sources import load_firm_wedges


def published_table1() -> dict[str, dict]:
    """Parse Table 1 out of the paper's own spreadsheet.

    Columns: characteristic, description, sort order, PW^a long (+2 p-values),
    PW^a short (+2 p-values), PW^a long-short, % resolution, then the
    mean-bias-adjusted-only PW* for long, short and long-short.
    """
    book = openpyxl.load_workbook(C.TABLE1_XLSX, read_only=True, data_only=True)
    sheet = book["Tabelle1"]
    out: dict[str, dict] = {}
    for row in sheet.iter_rows(min_row=3, values_only=True):
        if not row or not row[0]:
            continue
        out[str(row[0]).strip()] = {
            "pw_long": float(row[3]),
            "pw_short": float(row[6]),
            "pw_long_short": float(row[9]),
            "p_long": float(str(row[4]).strip("()")),
            "p_short": float(str(row[7]).strip("()")),
            "resolution": float(str(row[10]).strip("[]")),
            "pwstar_long": float(row[11]),
            "pwstar_short": float(row[12]),
            "pwstar_long_short": float(row[13]),
        }
    book.close()
    return out


# Table 1 abbreviates a few characteristic names; map them back to file names.
TABLE1_ALIASES = {
    "BETAd": "BETA_d",
    "R3613": "R_36_13",
    "R122": "R_12_2",
    "R127": "R_12_7",
    "R62": "R_6_2",
    "R21": "R_2_1",
}


def check_portfolio(dataset: dict, tolerance: float = 0.05) -> list[str]:
    """PW* for deciles 1 and 10 must match the published Table 1 to 0.05pp."""
    published = published_table1()
    lookup = {}
    for name, values in published.items():
        lookup[TABLE1_ALIASES.get(name, name)] = values

    rebuilt: dict[str, dict] = {}
    for row in dataset["rows"]:
        rebuilt.setdefault(row["characteristic"], {})[row["portfolio"]] = row["pw"]

    failures = []
    compared = 0
    for name, values in lookup.items():
        if name not in rebuilt:
            failures.append(f"{name}: missing from rebuild")
            continue
        for leg, portfolio in (("pwstar_long", "1"), ("pwstar_short", "10")):
            got = rebuilt[name][portfolio] * 100.0
            want = values[leg]
            compared += 1
            if abs(got - want) > tolerance:
                failures.append(f"{name} {leg}: rebuilt {got:.2f} vs published {want:.2f}")

    if compared != 114:
        failures.append(f"compared {compared} portfolios, expected 114")
    return failures


def check_firm() -> list[str]:
    """Spot-check the PWshare cell labelling against claims made in the paper."""
    fw = load_firm_wedges()
    failures = []

    def corr(a, b):
        mask = np.isfinite(a) & np.isfinite(b)
        return float(np.corrcoef(a[mask], b[mask])[0, 1])

    # Section 4.4: full-sample and out-of-sample equity wedges correlate at 0.98.
    got = corr(fw.cells[(0, 0)], fw.cells[(1, 0)])
    if abs(got - 0.98) > 0.01:
        failures.append(f"corr(3PC equity full, 3PC equity OOS) = {got:.3f}, expected ~0.98")

    # The out-of-sample cells must start in October 1998 and no earlier.
    for cell in ((1, 0), (1, 1), (3, 0), (3, 1)):
        observed = np.isfinite(fw.cells[cell]).any(axis=1)
        start = int(fw.dates[np.argmax(observed)])
        if start != 199810:
            failures.append(f"cell {cell} starts {start}, expected 199810")

    # Eq. (9): the firm-value wedge implies an equity share of firm value in [0,1].
    equity, firm = fw.cells[(0, 0)], fw.cells[(2, 0)]
    mask = np.isfinite(equity) & np.isfinite(firm) & (np.abs(equity) > 0.02)
    weight = (np.exp(-firm[mask]) - 1.0) / (np.exp(-equity[mask]) - 1.0)
    inside = float(np.mean((weight >= 0) & (weight <= 1)))
    if inside < 0.98:
        failures.append(f"only {inside:.1%} of implied equity weights lie in [0,1]")

    return failures
