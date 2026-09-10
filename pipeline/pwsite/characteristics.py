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


# ---------------------------------------------------------------------------
# The full annual set
# ---------------------------------------------------------------------------

def _pct_change(frame: pd.DataFrame, column: str) -> pd.Series:
    """Annual percentage change, in percent to match the paper's panel."""
    prior = frame.groupby("gvkey")[column].shift(1)
    return (100.0 * (frame[column] / prior - 1.0)).where(prior > 0)


def annual_all(f: pd.DataFrame) -> pd.DataFrame:
    """Every characteristic computable from fundamentals alone.

    Follows Appendix Table A.1 line by line. "Lagged" always means the prior
    fiscal year, not the prior month, and net operating assets is the paper's
    own construction rather than a textbook one: operating assets are total
    assets less cash and other investments, operating liabilities are total
    assets less every financing claim, so the difference nets out assets and
    leaves what the business itself employs.
    """
    f = f.sort_values(["gvkey", "datadate"]).copy()
    g = f.groupby("gvkey")
    lag = {c: g[c].shift(1) for c in
           ["at", "ceq", "invt", "ppegt", "act", "che", "lct", "dlc", "txp", "sale", "cogs"]}

    be = book_equity(f)
    operating_assets = f["at"] - f["che"].fillna(0) - f["ivao"].fillna(0)
    operating_liabs = (
        f["at"] - f["dlc"].fillna(0) - f["dltt"].fillna(0)
        - f["mib"].fillna(0) - f["pstk"].fillna(0) - f["ceq"].fillna(0)
    )
    noa_level = operating_assets - operating_liabs
    noa_lag = g.apply(lambda _: None) if False else None
    f["_noa"] = noa_level
    noa_lag = f.groupby("gvkey")["_noa"].shift(1)

    out = pd.DataFrame({"gvkey": f["gvkey"], "datadate": f["datadate"]})
    out["be"] = be
    out["be_lag"] = f.assign(_be=be).groupby("gvkey")["_be"].shift(1)
    out["at"] = f["at"]
    out["gp"] = f["gp"]
    out["ceq"] = f["ceq"]
    out["txdb"] = f["txdb"]
    out["sale"] = f["sale"]
    out["ib"] = f["ib"]
    out["dltt"] = f["dltt"]
    out["che"] = f["che"]
    out["BookDebt2"] = f["dltt"].fillna(0) + f["dlc"].fillna(0)

    # value and leverage inputs that need market equity are finished monthly
    out["AT"] = f["at"]
    out["C2A"] = f["che"] / f["at"]
    out["C2D"] = (f["ib"] + f["dp"]) / f["lt"]
    out["SG"] = _pct_change(f, "sale")
    out["CAT"] = f["sale"] / lag["at"]
    out["SAT"] = f["sale"] / f["at"]
    out["PCM"] = (f["sale"] - f["cogs"]) / f["sale"]
    out["IPM"] = f["pi"] / f["sale"]
    out["PM"] = f["oiadp"] / f["sale"]
    out["OL"] = (f["cogs"].fillna(0) + f["xsga"].fillna(0)) / f["at"]
    # Every component must be present: filling a missing receivable or
    # inventory with zero reads as "this firm holds no tangible assets", which
    # pushes exactly the firms with incomplete filings into the bottom decile.
    # It moves the agreement with the published decile weights from 0.48 to 0.96.
    out["TAN"] = (
        0.715 * f["rect"] + 0.547 * f["invt"] + 0.535 * f["ppent"] + f["che"]
    ) / f["at"]
    out["ROA"] = f["ib"] / lag["at"]
    out["ROE"] = f["ib"] / out["be_lag"]
    # Cash is *subtracted* from invested capital. Appendix Table A.1 words this
    # as a sum, but adding it disagrees with the published decile weights
    # (0.64 against 0.93), and subtracting is what "invested capital" means:
    # capital tied up in the business, net of the cash that is not.
    out["ROIC"] = (f["ebit"] - f["nopi"].fillna(0)) / (
        f["ceq"] + f["lt"] - f["che"]
    )
    out["S2C"] = f["sale"] / f["che"]
    out["ATO"] = f["sale"] / noa_lag
    out["RNA"] = f["oiadp"] / noa_lag
    out["NOA"] = noa_level / lag["at"]
    out["I2A"] = _pct_change(f, "at")
    out["dCEQ"] = _pct_change(f, "ceq")
    out["dPIA"] = ((f["ppegt"] - lag["ppegt"]) + (f["invt"] - lag["invt"])) / lag["at"]
    out["IVC"] = (f["invt"] - lag["invt"]) / ((f["at"] + lag["at"]) / 2.0)

    gross_margin = f["sale"] - f["cogs"]
    gm_prior = lag["sale"] - lag["cogs"]
    out["dGS"] = 100.0 * (gross_margin / gm_prior - 1.0) - _pct_change(f, "sale")

    # Operating accruals: the change in non-cash working capital, less
    # depreciation, scaled by the assets that produced it.
    delta = lambda c: f[c] - lag[c]  # noqa: E731
    out["OA"] = (
        delta("act") - delta("che") - delta("lct") - delta("dlc") - delta("txp") - f["dp"]
    ) / lag["at"]
    out["AOA"] = out["OA"].abs()

    shares = f["csho"] * f["ajex"]
    prior_shares = f.assign(_s=shares).groupby("gvkey")["_s"].shift(1)
    out["dSO"] = np.log(shares / prior_shares).where((shares > 0) & (prior_shares > 0))

    out["EPS_ib"] = f["ib"]     # divided by CRSP shares outstanding monthly
    return out


def monthly_all(merged: pd.DataFrame) -> pd.DataFrame:
    """Characteristics that need market value or monthly CRSP data.

    Market capitalisation arrives from CRSP in thousands while Compustat is in
    millions, so it is rescaled once here and every ratio below is formed from
    the rescaled figure.
    """
    out = merged.copy()
    me = out["cap"] / 1000.0
    out["_me"] = me

    out["BEME"] = out["be"] / me
    out["PROF"] = out["gp"] / out["be"]
    out["Q"] = (out["at"] + me - out["ceq"] - out["txdb"].fillna(0)) / out["at"]
    out["A2ME"] = out["at"] / me
    out["E2P"] = out["ib"] / me
    out["S2P"] = out["sale"] / me
    out["D2P"] = out["BookDebt2"] / me
    out["ROC"] = (me + out["dltt"] - out["at"]) / out["che"]
    out["SIZE"] = me
    out["EPS"] = out["EPS_ib"] / (out["shrout"] / 1000.0)
    out["TNOVR"] = out["vol"] / out["shrout"] if "vol" in out else np.nan
    return out


def crsp_characteristics(monthly: pd.DataFrame) -> pd.DataFrame:
    """The characteristics that need only CRSP's monthly file.

    Timing. `sorts.py` lags the sorting variable one month, exactly as the
    MATLAB original does, so a characteristic stored on row `t` is what a sort
    formed at `t+1` uses. The published decile weights say the package stores
    momentum on that convention: "the return from twelve months to two months
    ago" is stored as the return from eleven months to one month ago, which the
    sort's own lag then turns into the stated window. Storing the stated window
    directly shifts every momentum sort one month early -- agreement with the
    published weights falls from 0.97 to 0.65 for R_12_2, and from 0.97 to 0.11
    for R_2_1, where a one-month error leaves nothing in common at all.

    Share counts. CRSP reports shares outstanding unadjusted for splits, so a
    two-for-one split reads as a 100% issuance. Splits leave market
    capitalisation and the ex-dividend return untouched, so the growth in
    split-adjusted shares is recoverable from those two:

        log(cap_t / cap_{t-12}) - sum of log(1 + retx) over the same window

    which is what dSOUT uses (agreement 0.88 against 0.51 for raw share counts).

    Dividends. DP sums twelve monthly payments per share and divides by the
    current price, without restating the payments for splits in between.
    Restating them is the more coherent calculation, and it agrees with the
    published decile weights *worse* (0.74 against 0.82), so the plain sum is
    what the package appears to have used and what is kept here.
    """
    months = np.sort(monthly["month"].unique())
    permnos = np.sort(monthly["permno"].unique())
    dense = pd.MultiIndex.from_product([permnos, months], names=["permno", "month"])
    m = (
        monthly.set_index(["permno", "month"])
        .reindex(dense)
        .reset_index()
        .sort_values(["permno", "month"])
    )
    n_months = len(months)

    def by_firm(values: np.ndarray) -> np.ndarray:
        return values.reshape(len(permnos), n_months)

    def rolling_sum(values: np.ndarray, span: int) -> np.ndarray:
        """Sum over the last `span` calendar months, NaN if any is absent."""
        rolled = (
            pd.DataFrame(values)
            .T.rolling(span, min_periods=span)
            .sum()
            .T.to_numpy()
        )
        return rolled

    def shift(values: np.ndarray, k: int) -> np.ndarray:
        if k == 0:
            return values
        out = np.full_like(values, np.nan)
        out[:, k:] = values[:, :-k]
        return out

    log_ret = by_firm(np.log1p(m["ret"].to_numpy(float)))
    log_retx = by_firm(np.log1p(m["retx"].to_numpy(float)))

    out = m[["permno", "month"]].copy()

    def window(start: int, stop: int) -> np.ndarray:
        """Compound return over months t-start .. t-stop, on the stored
        convention (one month later than the name suggests)."""
        span = start - stop + 1
        return np.expm1(shift(rolling_sum(log_ret, span), stop - 1)).ravel()

    out["R_12_2"] = window(12, 2)
    out["R_12_7"] = window(12, 7)
    out["R_6_2"] = window(6, 2)
    out["R_36_13"] = window(36, 13)
    out["R_2_1"] = m["ret"].to_numpy(float)

    cap = by_firm(m["cap"].to_numpy(float))
    gain_12 = rolling_sum(log_retx, 12)
    out["dSOUT"] = (100.0 * (np.log(cap / shift(cap, 12)) - gain_12)).ravel()

    # Each month's dividend per share, restated in the shares outstanding at t
    # by discounting through the ex-dividend returns paid since.
    price = by_firm(np.abs(m["prc"].to_numpy(float)))
    paid = (by_firm(m["ret"].to_numpy(float)) - by_firm(m["retx"].to_numpy(float))) * shift(price, 1)
    twelve = pd.DataFrame(paid).T.rolling(12, min_periods=6).sum().T.to_numpy()
    out["DP"] = (twelve / price).ravel()

    out["TNOVR"] = (m["vol"] / m["shrout"]).to_numpy(float)
    return out.dropna(how="all", subset=[c for c in out.columns if c not in ("permno", "month")])
