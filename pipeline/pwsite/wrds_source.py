"""Pulling raw data from WRDS.

WRDS exposes a Postgres endpoint, so nothing here needs a browser or a manual
download. Credentials live in `~/.pgpass` once and the pipeline is then
non-interactive forever:

    echo "wrds-pgdata.wharton.upenn.edu:9737:wrds:USERNAME:PASSWORD" >> ~/.pgpass
    chmod 600 ~/.pgpass

Two things shape the design.

**Aggregate on their server, not ours.** CRSP's daily file is tens of gigabytes
across the full history, but the nine daily-based characteristics only need
per-firm-month summaries. Pushing the aggregation into SQL turns a download
measured in gigabytes into one measured in megabytes, which is the difference
between a refresh that takes minutes and one that runs overnight.

**Cache by year.** Every pull is written to Parquet under `raw/`, keyed by table
and year. The first run is expensive; afterwards only new or reopened years are
fetched, which is what makes a monthly refresh cheap.

Where the licence puts the boundary: CRSP's agreement defines Internal Use as
one site and forbids making the data available to third parties, so this module
must run on a university machine. Only its *outputs* -- the estimates -- are
published.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

CACHE = Path(os.environ.get("PRICEWEDGE_RAW", Path(__file__).resolve().parents[2] / "raw"))
PGHOST = "wrds-pgdata.wharton.upenn.edu"
PGPORT = 9737


class MissingCredentials(RuntimeError):
    pass


def connect(username: str | None = None):
    """Open a WRDS connection, explaining the fix if credentials are absent."""
    import wrds

    username = username or os.environ.get("WRDS_USERNAME")
    if not username:
        raise MissingCredentials(
            "Set WRDS_USERNAME (or pass username=). One-time setup:\n"
            f'  echo "{PGHOST}:{PGPORT}:wrds:USERNAME:PASSWORD" >> ~/.pgpass\n'
            "  chmod 600 ~/.pgpass\n"
            "  export WRDS_USERNAME=USERNAME"
        )
    return wrds.Connection(wrds_username=username)


# ---------------------------------------------------------------------------
# Schema, as confirmed against the live subscription
# ---------------------------------------------------------------------------
# CRSP's newer CIZ tables rename nearly everything and, usefully, precompute
# several things the older schema made you derive:
#
#   mthret      already includes delisting returns. Checked against
#               crsp.msedelist over 28,913 delisting events: 22,308 match dlret
#               exactly and none is missing a monthly row, the remainder being
#               months that also had partial-period trading. So no delisting
#               merge is needed -- a step that is easy to get wrong and biases
#               the tails when omitted.
#   mthcap      market capitalisation, and mthprevcap its one-month lag, which
#               is exactly the weight a sort needs at formation.
#   mthprcvol   dollar volume.
#
# Exchange and share class move to letter codes: primaryexch N = NYSE (the
# breakpoint universe), A = NYSE American, Q/R = Nasdaq; sharetype NS = ordinary
# common shares and securitytype EQTY excludes funds.

CIZ_MONTHLY = {
    "date": "mthcaldt", "ret": "mthret", "retx": "mthretx", "prc": "mthprc",
    "cap": "mthcap", "prevcap": "mthprevcap", "vol": "mthvol",
    "dollar_volume": "mthprcvol", "shrout": "shrout", "exchange": "primaryexch",
    "sharetype": "sharetype", "securitytype": "securitytype", "siccd": "siccd",
}
CIZ_DAILY = {
    "date": "dlycaldt", "ret": "dlyret", "retx": "dlyretx", "prc": "dlyprc",
    "cap": "dlycap", "vol": "dlyvol", "dollar_volume": "dlyprcvol",
    "bid": "dlybid", "ask": "dlyask", "high": "dlyhigh", "low": "dlylow",
    "shrout": "shrout",
}
NYSE = "N"
COMMON_SHARES = ("NS",)
EQUITY = ("EQTY",)

# Quoted bid and ask are sparse before 2000 -- roughly 9% of daily rows in the
# 1960s, 30% in the 1970s, 53% in the 1980s, 64% in the 1990s, then 96%+ from
# 2000. SPREAD is the one characteristic of the 57 whose early history cannot be
# built from quotes alone; dlyhigh/dlylow are better populated in the 1960s
# (91%) and worse in the 1980s (45%), so neither source covers the sample on its
# own. Flagged rather than silently patched.
SPREAD_QUOTE_COVERAGE_WARNING = True


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------
# CRSP has two schemas in circulation: the legacy one (msf, msenames, dsf) and
# the newer CIZ one (msf_v2, stksecurityinfohist, dsf_v2). Which a subscription
# exposes varies, and the column names differ, so the pulls are written against
# whatever this finds rather than against an assumption.

CANDIDATES: dict[str, list[str]] = {
    "crsp_monthly": ["crsp.msf_v2", "crsp.msf"],
    "crsp_daily": ["crsp.dsf_v2", "crsp.dsf"],
    "crsp_names": ["crsp.stksecurityinfohist", "crsp.stocknames", "crsp.msenames"],
    "crsp_delist": ["crsp.msedelist_v2", "crsp.msedelist"],
    "compustat_annual": ["comp.funda"],
    "compustat_quarterly": ["comp.fundq"],
    "ccm_link": ["crsp.ccmxpf_lnkhist", "crsp.ccmxpf_linktable"],
    "ff_daily": ["ff.factors_daily"],
    "ff_monthly": ["ff.factors_monthly"],
}

# Fields the 57 characteristic definitions name, from Appendix Table A.1.
NEEDED_COMPUSTAT = [
    "act", "ajex", "at", "ceq", "che", "cogs", "csho", "dlc", "dltt", "dp",
    "ebit", "gp", "ib", "invt", "ivao", "lct", "lt", "mib", "nopi", "oiadp",
    "pi", "ppegt", "ppent", "pstk", "pstkl", "pstkrv", "rect", "sale", "seq",
    "txdb", "txditc", "txp", "xsga",
]
NEEDED_CRSP_MONTHLY = ["permno", "permco", "siccd", "shrout"] + [
    v for k, v in {
        "date": "mthcaldt", "ret": "mthret", "retx": "mthretx", "prc": "mthprc",
        "cap": "mthcap", "prevcap": "mthprevcap", "vol": "mthvol",
        "dollar_volume": "mthprcvol", "exchange": "primaryexch",
        "sharetype": "sharetype", "securitytype": "securitytype",
    }.items()
]
NEEDED_CRSP_DAILY = ["permno", "shrout"] + [
    v for k, v in {
        "date": "dlycaldt", "ret": "dlyret", "retx": "dlyretx", "prc": "dlyprc",
        "vol": "dlyvol", "dollar_volume": "dlyprcvol", "bid": "dlybid",
        "ask": "dlyask", "high": "dlyhigh", "low": "dlylow",
    }.items()
]


@dataclass
class TableReport:
    role: str
    name: str | None
    columns: list[str]
    missing: list[str]


def discover(db, verbose: bool = True) -> dict[str, TableReport]:
    """Find which candidate tables exist and which needed columns they carry.

    Run this once against a real subscription; the result tells us exactly how
    to write the pulls, instead of guessing at a schema.
    """
    wanted = {
        "crsp_monthly": NEEDED_CRSP_MONTHLY,
        "crsp_daily": NEEDED_CRSP_DAILY,
        "compustat_annual": NEEDED_COMPUSTAT,
    }
    found: dict[str, TableReport] = {}

    for role, options in CANDIDATES.items():
        report = TableReport(role, None, [], [])
        for full in options:
            schema, table = full.split(".")
            try:
                cols = [c.lower() for c in db.describe_table(schema, table).name.tolist()]
            except Exception:
                continue
            report.name = full
            report.columns = cols
            report.missing = [c for c in wanted.get(role, []) if c not in cols]
            break
        found[role] = report
        if verbose:
            if report.name is None:
                print(f"  {role:20} NOT FOUND (tried {', '.join(options)})")
            else:
                note = f"missing {report.missing}" if report.missing else "all needed columns present"
                print(f"  {role:20} {report.name:32} {len(report.columns):>4} cols  {note}")
    return found


# ---------------------------------------------------------------------------
# Cached pulls
# ---------------------------------------------------------------------------

def _cache_path(table: str, year: int) -> Path:
    return CACHE / table.replace(".", "_") / f"{year}.parquet"


def cached_years(table: str) -> set[int]:
    folder = CACHE / table.replace(".", "_")
    return {int(p.stem) for p in folder.glob("*.parquet")} if folder.exists() else set()


def pull_years(
    db,
    table: str,
    columns: list[str],
    years: list[int],
    date_column: str = "date",
    where: str = "",
    refresh: bool = False,
) -> pd.DataFrame:
    """Fetch a table year by year, reusing anything already cached.

    The most recent cached year is always refetched by default: filings and
    delisting information arrive late, so the newest year on disk is the one
    most likely to be incomplete.
    """
    have = cached_years(table)
    newest_cached = max(have) if have else None
    frames = []
    for year in sorted(years):
        path = _cache_path(table, year)
        stale = refresh or year == newest_cached
        if path.exists() and not stale:
            frames.append(pd.read_parquet(path))
            continue
        clause = f"and {where}" if where else ""
        sql = (
            f"select {', '.join(columns)} from {table} "
            f"where {date_column} >= '{year}-01-01' and {date_column} <= '{year}-12-31' {clause}"
        )
        frame = db.raw_sql(sql, date_cols=[date_column])
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(path, index=False)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def daily_month_moments(db, table: str, years: list[int]) -> pd.DataFrame:
    """Per-firm-month summaries of the daily file, computed on WRDS's server.

    Nine characteristics are built from daily data. Rather than download the
    daily file, this returns the sufficient statistics each of them needs --
    counts, sums, sums of squares and cross-products with the market -- from
    which the volatilities, maxima and regression coefficients can be recovered
    exactly. The result is per firm-month, so it is megabytes rather than
    gigabytes.

    Kept separate from `pull_years` because the aggregation is the point: this
    is the query whose shape decides whether a refresh is fast.
    """
    frames = []
    for year in sorted(years):
        path = _cache_path(f"{table}__moments", year)
        if path.exists():
            frames.append(pd.read_parquet(path))
            continue
        sql = f"""
            select permno,
                   date_trunc('month', dlycaldt)::date              as month,
                   count(*)                                          as n,
                   sum(dlyret)                                       as sum_ret,
                   sum(dlyret * dlyret)                              as sum_ret2,
                   max(dlyret)                                       as max_ret,
                   sum(dlyprcvol)                                    as sum_dvol,
                   sum(dlyprcvol * dlyprcvol)                        as sum_dvol2,
                   sum(dlyvol / nullif(shrout * 1000.0, 0))          as sum_turn,
                   sum((dlyvol / nullif(shrout * 1000.0, 0)) ^ 2)    as sum_turn2,
                   count(dlybid)                                     as n_quote,
                   sum(case when dlyask > 0 and dlybid > 0
                            then 2 * (dlyask - dlybid) / (dlyask + dlybid) end) as sum_spread
            from {table}
            where dlycaldt >= '{year}-01-01' and dlycaldt <= '{year}-12-31'
              and dlyret is not null
            group by permno, date_trunc('month', dlycaldt)
        """
        frame = db.raw_sql(sql, date_cols=["month"])
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(path, index=False)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
