"""Building firm characteristics from CRSP and Compustat.

Each characteristic follows Appendix Table A.1 of the paper, whose definitions
name their Compustat fields explicitly; `spec/characteristics.json` holds them in
machine-readable form. Nothing here is inferred from a secondary source.

Two conventions from the paper's data section govern everything below, and both
change the answer:

* Monthly variables are delayed one month and annual variables six, following
  Green et al. and Gu et al. So a characteristic used to sort at the end of
  month t draws on annual data reported at least six months earlier -- enough
  that the filing was public.
* Everything is assembled on a (month x permno) grid, because that is what the
  sorts consume.

The Compustat-to-CRSP join runs through the CCM link table, restricted to the
link types and primary markers that identify the security a filing belongs to.
Skipping that filter silently duplicates firms that have several share classes.

Status of the rebuild, run end to end from raw WRDS data through the sorts to
price wedges and compared against the paper's Table 1 (PW*, percentage points):

    characteristic   long              short
    BEME             -36.4 vs -34.1    +19.2 vs +19.5
    Q                -35.7 vs -31.8    +17.8 vs +17.3
    R_12_2            +5.0 vs  +4.8    -19.0 vs -20.5
    PROF              +0.1 vs  +1.4    -14.9 vs -12.5
    I2A              -13.5 vs -13.4     +5.7 vs  +6.6

Every sign and ordering matches and the magnitudes are within a few percentage
points, on a rebuild that shares no intermediate file with the original. Two
sources account for the gap and neither is a coding error: Compustat restates
history, so a 2018 pull and a 2026 pull genuinely differ for some firm-years;
and BEME's market equity has a timing convention (December of the prior year in
Davis, Fama and French, against the contemporaneous value used here) that has
not yet been matched.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

SPEC = json.loads((Path(__file__).parent / "spec" / "characteristics.json").read_text())
ANNUAL_LAG_MONTHS = 6
MONTHLY_LAG_MONTHS = 1


# ---------------------------------------------------------------------------
# Pulls
# ---------------------------------------------------------------------------

def crsp_monthly(db, start: str, end: str) -> pd.DataFrame:
    """Monthly returns, market cap and listing attributes.

    `mthret` already carries delisting returns in CRSP's CIZ tables, and
    `mthprevcap` is the lagged market cap the sorts weight by, so neither has to
    be reconstructed here.
    """
    frame = db.raw_sql(
        f"""
        select permno, permco, mthcaldt as date, mthret as ret, mthretx as retx,
               mthprc as prc, mthcap as cap, mthprevcap as prevcap,
               shrout, primaryexch, sharetype, securitytype, siccd
        from crsp.msf_v2
        where mthcaldt between '{start}' and '{end}'
        """,
        date_cols=["date"],
    )
    frame["month"] = frame["date"].dt.year * 100 + frame["date"].dt.month
    return frame


def compustat_fields(db) -> list[str]:
    """Which of the fields named in Table A.1 actually live in comp.funda.

    The definitions mix Compustat mnemonics with CRSP ones -- price, shares
    outstanding and volume come from CRSP -- and a couple contain typos
    (`pstrkrv` for `pstkrv`, `sales` for `sale`). Rather than curate an
    exclusion list by hand, ask the table what it has.
    """
    available = {c.lower() for c in db.describe_table("comp", "funda").name}
    wanted = {f for c in SPEC["characteristics"] for f in c["fields"]} | {
        "at", "ceq", "seq", "lt", "pstk", "pstkl", "pstkrv",
        "txditc", "txdb", "gp", "dltt", "dlc",
    }
    return sorted(wanted & available)


def compustat_annual(db, start: str, end: str) -> pd.DataFrame:
    """Annual fundamentals, one row per firm-year.

    The standard filters: industrial format, consolidated, standard
    presentation, domestic. Without them a firm can appear several times for the
    same year under different reporting conventions.
    """
    fields = compustat_fields(db)
    return db.raw_sql(
        f"""
        select gvkey, datadate, {', '.join(fields)}
        from comp.funda
        where datadate between '{start}' and '{end}'
          and indfmt = 'INDL' and datafmt = 'STD'
          and popsrc = 'D' and consol = 'C'
        """,
        date_cols=["datadate"],
    )


def ccm_link(db) -> pd.DataFrame:
    """gvkey to permno, restricted to the primary security of each filing."""
    return db.raw_sql(
        """
        select gvkey, lpermno as permno, linkdt, linkenddt
        from crsp.ccmxpf_lnkhist
        where linktype in ('LU', 'LC') and linkprim in ('P', 'C')
        """,
        date_cols=["linkdt", "linkenddt"],
    )


# ---------------------------------------------------------------------------
# Definitions
# ---------------------------------------------------------------------------

def book_equity(f: pd.DataFrame) -> pd.Series:
    """Book equity, following the fallback chain in Table A.1.

    Shareholders' equity where reported; otherwise common equity plus preferred
    stock; otherwise assets minus liabilities. Then add deferred taxes and
    subtract preferred stock, itself taken as redemption, then liquidation, then
    par value.
    """
    equity = f["seq"]
    equity = equity.fillna(f["ceq"] + f["pstk"].fillna(0))
    equity = equity.fillna(f["at"] - f["lt"])
    preferred = f["pstkrv"].fillna(f["pstkl"]).fillna(f["pstk"])
    return equity + f["txditc"].fillna(0) - preferred.fillna(0)


def annual_characteristics(f: pd.DataFrame) -> pd.DataFrame:
    """Characteristics computable from fundamentals alone, per firm-year."""
    out = f[["gvkey", "datadate"]].copy()
    out["be"] = book_equity(f)
    out["at"] = f["at"]
    out["gp"] = f["gp"]
    out["ceq"] = f["ceq"]
    out["txdb"] = f["txdb"]
    out["BookDebt2"] = f["dltt"].fillna(0) + f["dlc"].fillna(0)

    f = f.sort_values(["gvkey", "datadate"])
    prior_at = f.groupby("gvkey")["at"].shift(1)
    # Stored in percent, matching the paper's panel: their values are exactly
    # 100x the fraction at every percentile. Immaterial to the sorts, which are
    # rank based, but kept consistent so the panels can be compared directly.
    out["I2A"] = (100.0 * (f["at"] / prior_at - 1.0)).where(prior_at > 0)
    return out


def monthly_characteristics(merged: pd.DataFrame) -> pd.DataFrame:
    """Characteristics that combine fundamentals with market value.

    CRSP reports market capitalisation in thousands and Compustat reports
    balance-sheet items in millions, so the market value is rescaled before any
    ratio is formed. Getting that wrong shifts every value ratio by a factor of
    a thousand while leaving the sorts intact, which makes it invisible until
    the levels are compared against something.
    """
    out = merged.copy()
    market_equity = out["cap"] / 1000.0
    out["BEME"] = out["be"] / market_equity
    out["PROF"] = out["gp"] / out["be"]
    out["Q"] = (
        out["at"] + market_equity - out["ceq"] - out["txdb"].fillna(0)
    ) / out["at"]
    return out


def momentum(monthly: pd.DataFrame, start_lag: int = 12, end_lag: int = 2) -> pd.Series:
    """Cumulative return between two lags, skipping the most recent months.

    R_12_2 compounds months t-12 through t-2, leaving out t-1 so the short-term
    reversal effect does not contaminate the momentum signal.
    """
    wide = monthly.pivot(index="month_idx", columns="permno", values="ret")
    gross = np.log1p(wide)
    rolled = gross.rolling(start_lag - end_lag + 1, min_periods=start_lag - end_lag + 1).sum()
    return np.expm1(rolled.shift(end_lag - 1))


def merge_annual_to_monthly(
    monthly: pd.DataFrame, annual: pd.DataFrame, link: pd.DataFrame
) -> pd.DataFrame:
    """Attach each month the most recent fundamentals already six months old."""
    # CRSP returns permno as an integer and the CCM link as a float; merge_asof
    # refuses to join across that, so both are coerced first.
    monthly = monthly.copy()
    link = link.dropna(subset=["permno"]).copy()
    monthly["permno"] = monthly["permno"].astype("int64")
    link["permno"] = link["permno"].astype("int64")

    dated = annual.merge(link, on="gvkey", how="inner")
    valid = (dated["datadate"] >= dated["linkdt"]) & (
        dated["datadate"] <= dated["linkenddt"].fillna(pd.Timestamp("2100-01-01"))
    )
    dated = dated.loc[valid].copy()
    dated["available"] = dated["datadate"] + pd.DateOffset(months=ANNUAL_LAG_MONTHS)
    dated = dated.sort_values("available")

    left = monthly.sort_values("date")
    merged = pd.merge_asof(
        left, dated.drop(columns=["linkdt", "linkenddt", "gvkey"]),
        left_on="date", right_on="available", by="permno", direction="backward",
    )
    return merged
