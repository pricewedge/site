#!/usr/bin/env python3
"""Build the firm-by-month characteristic panel the sorts run on.

Every pull is cached under `raw/`, so the first run is the slow one and a
refresh only fetches what has changed. Nothing here needs a browser or a manual
download; see `setup_wrds.py` for the one-time credential setup.

    ./.venv/bin/python build_panel.py            # incremental
    ./.venv/bin/python build_panel.py --refresh  # refetch everything

The panel it writes, `raw/full_panel.parquet`, is the input to the sorts, which
turn it into decile portfolios, which `portfolio.py` turns into price wedges.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pwsite import characteristics as ch
from pwsite.daily import daily_characteristics
from pwsite.industry import ff48
from pwsite.wrds_source import (CACHE, connect, daily_moments, range_moments,
                                suv_moments)

START, END = "1960-01-01", "2017-12-31"
COMPUSTAT_START = "1955-01-01"          # annual characteristics need a prior year

# Industry-adjusted characteristics: the value less the mean among firms in the
# same industry that month, equal-weighted over the ordinary common shares
# that have it. The industry is the paper's own 27-group scheme, recovered
# from its panels (pwsite.industry.learned_industry); Fama-French 48, which
# its sources use, agrees with the published decile weights at 0.51 for aBEME
# against 0.92 for the recovered scheme. Equal weighting is what agrees best;
# capitalisation weighting lets a few large firms set the benchmark.
INDUSTRY_ADJUSTED = {"aBEME": "BEME", "aPM": "PM", "aSAT": "SAT", "aSIZE": "SIZE"}


def _username() -> str:
    if os.environ.get("WRDS_USERNAME"):
        return os.environ["WRDS_USERNAME"]
    profile = Path.home() / ".zshrc"
    if profile.exists():
        found = re.search(r'export WRDS_USERNAME="([^"]+)"', profile.read_text())
        if found:
            return found.group(1)
    raise SystemExit("Set WRDS_USERNAME, or run setup_wrds.py once.")


def _cached(name: str, build, refresh: bool) -> pd.DataFrame:
    path = CACHE / f"{name}.parquet"
    if path.exists() and not refresh:
        print(f"  {name:22} cached")
        return pd.read_parquet(path)
    started = time.time()
    frame = build()
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    print(f"  {name:22} {len(frame):>10,} rows  {time.time() - started:5.0f}s")
    return frame


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true",
                        help="refetch every table instead of reusing the cache")
    args = parser.parse_args()

    os.environ["WRDS_USERNAME"] = _username()
    print("pulling from WRDS")
    db = connect()
    monthly = _cached("crsp_monthly", lambda: ch.crsp_monthly(db, START, END), args.refresh)
    annual = _cached("compustat_annual",
                     lambda: ch.compustat_annual(db, COMPUSTAT_START, END), args.refresh)
    link = _cached("ccm_link", lambda: ch.ccm_link(db), args.refresh)
    years = list(range(int(START[:4]), int(END[:4]) + 1))
    print("  daily moments (aggregated on WRDS's server, one row per firm-month)")
    moments = daily_moments(db, years)
    moments = moments.merge(range_moments(db, years).drop(columns=["n"]),
                            on=["permno", "month"], how="left")
    moments = moments.merge(suv_moments(db, years), on=["permno", "month"], how="left")
    print(f"  {'daily_moments':22} {len(moments):>10,} rows")
    db.close()

    monthly["permno"] = monthly["permno"].astype("int64")

    print("\nbuilding characteristics")
    panel = ch.monthly_all(
        ch.merge_annual_to_monthly(monthly, ch.annual_all(annual), link)
    )
    panel = panel.merge(ch.crsp_characteristics(monthly), on=["permno", "month"],
                        how="left", suffixes=("_drop", ""))
    panel = panel.drop(columns=[c for c in panel.columns if c.endswith("_drop")])
    panel = panel.merge(daily_characteristics(moments, monthly), on=["permno", "month"],
                        how="left")

    # DTO and SUV are the last trading day's value of a daily series, not a
    # moment of the month (pwsite.lastday). They come from the daily file
    # itself; months past the end of that file are left missing rather than
    # filled with a differently defined stand-in.
    from pwsite.lastday import build as lastday_build, daily_years
    years_on_disk = daily_years()
    if years_on_disk:
        print(f"  month-end DTO/SUV from the daily file, {years_on_disk[0]}-{years_on_disk[-1]}")
        ends = lastday_build(years_on_disk).rename(columns={"dto": "DTO", "suv": "SUV"})
        panel = panel.drop(columns=["DTO", "SUV"]).merge(ends, on=["permno", "month"],
                                                          how="left")
    else:
        print("  note: raw/daily_raw missing; DTO and SUV are left missing")
        panel[["DTO", "SUV"]] = np.nan

    # BETA_d likewise: a window of the firm's own trading days, not calendar
    # months (pwsite.beta_daily). Months past the daily file stay missing.
    if years_on_disk and (CACHE / "ff_daily.parquet").exists():
        from pwsite.beta_daily import build as beta_build
        print("  BETA_d over the firm's last 249 trading days, from the daily file")
        betas = beta_build(years_on_disk).rename(columns={"beta": "BETA_d"})
        panel = panel.drop(columns=["BETA_d"]).merge(betas, on=["permno", "month"], how="left")
    else:
        print("  note: daily file or raw/ff_daily.parquet missing; BETA_d keeps the monthly-moment version")

    # A ratio whose denominator is zero is missing, not infinite: the paper's
    # panels carry no infinities, and an infinity inside an industry mean
    # would wipe out every firm in that industry-month.
    from pwsite.spec_ids import ALL_CHARACTERISTICS as _chars
    present = [c for c in _chars if c in panel.columns]
    panel[present] = panel[present].replace([np.inf, -np.inf], np.nan)

    # The industry mean is taken over ordinary common shares only. Averaging
    # over everything CRSP carries -- funds, ADRs, share classes that never
    # enter a sort -- moves the benchmark and agrees with the published decile
    # weights markedly worse (0.10 against 0.51 for aBEME).
    # Industry from CRSP's name-history SIC, which is what the paper used;
    # the monthly table's own siccd is a header code and is only the fallback.
    spells_path = CACHE / "sic_msenames.parquet"
    if spells_path.exists():
        from pwsite.industry import historical_sic
        hist = historical_sic(panel, pd.read_parquet(spells_path))
        panel["siccd_hist"] = np.where(np.isfinite(hist), hist,
                                       pd.to_numeric(panel["siccd"], errors="coerce"))
    else:
        print("  note: raw/sic_msenames.parquet missing; industry uses the header SIC")
        panel["siccd_hist"] = pd.to_numeric(panel["siccd"], errors="coerce")
    panel["ff48"] = ff48(panel["siccd_hist"])
    from pwsite.panel import ordinary_common
    ordinary = ordinary_common(panel)
    # The adjustment uses the paper's own 27-industry scheme, learned from its
    # panels (see pwsite.industry.learned_industry), not Fama-French 48.
    from pwsite.industry import adjust_learned
    adjust_learned(panel, INDUSTRY_ADJUSTED, ordinary)

    CACHE.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(CACHE / "full_panel.parquet", index=False)

    from pwsite.spec_ids import ALL_CHARACTERISTICS
    built = [c for c in ALL_CHARACTERISTICS if c in panel.columns]
    missing = [c for c in ALL_CHARACTERISTICS if c not in panel.columns]
    print(f"\n{len(built)} of {len(ALL_CHARACTERISTICS)} characteristics, "
          f"{len(panel):,} firm-months")
    for i in range(0, len(built), 5):
        print("  " + "  ".join(f"{c}:{100 * panel[c].notna().mean():4.1f}%"
                               for c in built[i:i + 5]))
    if missing:
        print(f"\nnot built: {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
