"""Paths, spec definitions and metadata for the pricewedge.com data build.

Everything the site knows about the estimates is declared here, so the site and
the download bundles can never drift apart: `manifest.json` is generated from
these constants.
"""

from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------
# Source data
# --------------------------------------------------------------------------
# The MATLAB replication package for Binsbergen, Boons, Opp and Tamoni,
# "Dynamic Asset (Mis)Pricing: Build-up versus Resolution Anomalies" (JFE).
# Override with PRICEWEDGE_SOURCE if the tree lives somewhere else.

_DEFAULT_SOURCE = (
    Path(__file__).resolve().parents[3]
    / "Project Folders"
    / "JFE"
    / "JFE_final"
    / "ReplicationPackage"
)

# The replication package is licensed CRSP-derived data and lives outside this
# repository — typically in Dropbox alongside the paper, while the repository
# itself lives wherever you keep code. Resolution order:
#   1. PRICEWEDGE_SOURCE in the environment
#   2. pipeline/.source-path, a one-line gitignored file holding the path
#   3. the historical layout, three directories up from the package
_SOURCE_POINTER = Path(__file__).resolve().parents[1] / ".source-path"


def _resolve_source() -> Path:
    from_env = os.environ.get("PRICEWEDGE_SOURCE")
    if from_env:
        return Path(from_env).expanduser()
    if _SOURCE_POINTER.exists():
        recorded = _SOURCE_POINTER.read_text().strip()
        if recorded:
            return Path(recorded).expanduser()
    return _DEFAULT_SOURCE


SOURCE = _resolve_source()

PW_SHARE = SOURCE / "PWshare.mat"          # firm-level price wedges (Dec 2023 vintage)
CRSP = SOURCE / "DataIN" / "crsp.mat"      # market/rf series, alpha signs, portfolio mkt caps
VARNAMES = SOURCE / "DataIN" / "varnames.mat"
DATA_FOR_SORT = SOURCE / "DataIN" / "dataforsort.mat"   # firm characteristic panel (v7.3)
REP_ISS_DIRS = {0: SOURCE / "DataRepIss0", 1: SOURCE / "DataRepIss1"}

# Published Table 1, used as a regression test on the portfolio rebuild.
TABLE1_XLSX = SOURCE.parents[1] / "Table 1.xlsx"

# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------
OUT = Path(os.environ.get("PRICEWEDGE_OUT", Path(__file__).resolve().parents[2] / "data"))

# Shard size is set by the *worst* case, not the best. Hosts that honour HTTP
# range requests fetch only the ~8 KB record a security needs and the shard size
# is irrelevant. Hosts that ignore the header -- Cloudflare Pages returns 200
# with the whole file, despite advertising `accept-ranges: bytes` -- make the
# client download an entire shard per security instead, so keeping shards near
# 1 MiB bounds that fallback at roughly one megabyte rather than eighteen.
# Immutable caching means repeat securities in the same shard are then free.
SHARD_MAX_BYTES = 1 * 1024 * 1024
PAGES_FILE_LIMIT = 25 * 1024 * 1024

# The full firm panel does not fit under that cap, so the download bundles can
# live somewhere else — a GitHub release, an R2 bucket — while the site itself
# stays on Pages. Set PRICEWEDGE_DOWNLOAD_BASE to that location (no trailing
# slash) and the data page links there instead of at /data/downloads.
DOWNLOAD_BASE = os.environ.get("PRICEWEDGE_DOWNLOAD_BASE", "").rstrip("/")

# --------------------------------------------------------------------------
# Vintage
# --------------------------------------------------------------------------
VINTAGE = "2017-12"
DATA_VERSION = "1.0.0"

CITATION = {
    "title": "Dynamic Asset (Mis)Pricing: Build-up versus Resolution Anomalies",
    "authors": [
        "Jules H. van Binsbergen",
        "Martijn Boons",
        "Christian C. Opp",
        "Andrea Tamoni",
    ],
    "journal": "Journal of Financial Economics",
    "url": "https://pricewedge.com",
}

# --------------------------------------------------------------------------
# Firm-level specifications == the 4x2 cell array in PWshare.mat
# --------------------------------------------------------------------------
# Second index: characteristics-to-price-wedge mapping
#   1 -> first three principal components of portfolio-level characteristics
#   2 -> Fama-French 5-factor characteristics plus momentum
# First index:
#   1 -> equity-level price wedge, full sample
#   2 -> equity-level price wedge, out of sample (mapping estimated pre-Oct 1998)
#   3 -> firm-level price wedge (Eq. 9, leverage adjusted), full sample
#   4 -> firm-level price wedge (Eq. 9), out of sample
#
# `cell` is (row, col) zero-based into PWshare.

FIRM_SPECS = [
    {
        "id": "pc3-equity-full",
        "cell": (0, 0),
        "mapping": "pc3",
        "level": "equity",
        "sample": "full",
        "label": "Equity price wedge — 3 PCs",
        "short": "3 PC · equity",
        "default": True,
    },
    {
        "id": "ff5-equity-full",
        "cell": (0, 1),
        "mapping": "ff5",
        "level": "equity",
        "sample": "full",
        "label": "Equity price wedge — FF5 + momentum",
        "short": "FF5 · equity",
        "default": False,
    },
    {
        "id": "pc3-equity-oos",
        "cell": (1, 0),
        "mapping": "pc3",
        "level": "equity",
        "sample": "oos",
        "label": "Equity price wedge — 3 PCs, out of sample",
        "short": "3 PC · equity · OOS",
        "default": False,
    },
    {
        "id": "ff5-equity-oos",
        "cell": (1, 1),
        "mapping": "ff5",
        "level": "equity",
        "sample": "oos",
        "label": "Equity price wedge — FF5 + momentum, out of sample",
        "short": "FF5 · equity · OOS",
        "default": False,
    },
    {
        "id": "pc3-firm-full",
        "cell": (2, 0),
        "mapping": "pc3",
        "level": "firm",
        "sample": "full",
        "label": "Firm-value price wedge — 3 PCs",
        "short": "3 PC · firm",
        "default": False,
    },
    {
        "id": "ff5-firm-full",
        "cell": (2, 1),
        "mapping": "ff5",
        "level": "firm",
        "sample": "full",
        "label": "Firm-value price wedge — FF5 + momentum",
        "short": "FF5 · firm",
        "default": False,
    },
    {
        "id": "pc3-firm-oos",
        "cell": (3, 0),
        "mapping": "pc3",
        "level": "firm",
        "sample": "oos",
        "label": "Firm-value price wedge — 3 PCs, out of sample",
        "short": "3 PC · firm · OOS",
        "default": False,
    },
    {
        "id": "ff5-firm-oos",
        "cell": (3, 1),
        "mapping": "ff5",
        "level": "firm",
        "sample": "oos",
        "label": "Firm-value price wedge — FF5 + momentum, out of sample",
        "short": "FF5 · firm · OOS",
        "default": False,
    },
]

MAPPING_NOTES = {
    "pc3": (
        "Portfolio-level price wedges are projected on the first three principal "
        "components of rank-normalised portfolio characteristics; a firm's price "
        "wedge is that mapping evaluated at its own characteristic percentiles. "
        "Requires all 57 characteristics to be observed, so it covers about 20% "
        "fewer firm-months than the FF5 mapping."
    ),
    "ff5": (
        "Portfolio-level price wedges are projected on the five Fama-French "
        "characteristics plus momentum (size, book-to-market, profitability, "
        "investment, momentum)."
    ),
}

LEVEL_NOTES = {
    "equity": (
        "The estimate is the log deviation of the firm's market equity from its "
        "informationally efficient value; positive means overpriced."
    ),
    "firm": (
        "The estimate carries the equity price wedge over to total firm value "
        "under the assumption that debt is correctly priced (Eq. 9): "
        "log[E/(E+D)·exp(-PW) + D/(E+D)], sign-aligned with the equity wedge. "
        "Leverage damps the wedge, so magnitudes are smaller."
    ),
}

SAMPLE_NOTES = {
    "full": "Characteristics-to-price-wedge mapping estimated on the full sample.",
    "oos": (
        "Mapping estimated using portfolio sorts through September 1983, so that "
        "post-formation returns through September 1998 are used. Estimates begin "
        "in October 1998 and use no data the market did not have."
    ),
}

# --------------------------------------------------------------------------
# Firm characteristics shown in the optional characteristic panel
# --------------------------------------------------------------------------
# Keys are positions in `data_fixed` inside dataforsort.mat, in the order
# declared by MainPart2.m:
#   {'Returns','PORT_WEGHT','BEME','Q','R_12_2','PROF','I2A','RetX_mb','exchcd','BookDebt2'}

DATA_FIXED_ORDER = [
    "Returns",
    "PORT_WEGHT",
    "BEME",
    "Q",
    "R_12_2",
    "PROF",
    "I2A",
    "RetX_mb",
    "exchcd",
    "BookDebt2",
]

# Characteristics we rank-normalise cross-sectionally each month. SIZE is
# market capitalisation, so it is derived from PORT_WEGHT rather than stored
# separately.
RANK_CHARS = [
    {"id": "BEME", "source": "BEME", "label": "Book-to-market", "group": "Value"},
    {"id": "R_12_2", "source": "R_12_2", "label": "Momentum (12-2)", "group": "Momentum"},
    {"id": "SIZE", "source": "PORT_WEGHT", "label": "Size (market cap)", "group": "Size"},
    {"id": "PROF", "source": "PROF", "label": "Profitability", "group": "Profitability"},
    {"id": "I2A", "source": "I2A", "label": "Investment", "group": "Investment"},
    {"id": "Q", "source": "Q", "label": "Tobin's q", "group": "Value"},
]

# Extra per-firm series carried alongside the wedges.
LEVEL_SERIES = [
    {"id": "mktcap", "label": "Market capitalisation ($m)", "decimals": 2},
    {"id": "pindex", "label": "Cumulative capital-gain index", "decimals": 5},
]

# --------------------------------------------------------------------------
# Portfolio-level rebuild (MainPart2.m)
# --------------------------------------------------------------------------
HORIZON_MONTHS = 180          # J = 15 years of post-formation cash flows
FIRST_FORMATION_ROW = 458     # 1-based row of 1964-06 in the 1099-month grid
L_POINT = {                   # market price-of-risk that zeroes the market wedge
    0: 3.324377969076594,
    1: 3.223507723315755,
}

# Price wedge remaining h years after portfolio formation (Figs. 5 and 6).
EVENT_YEARS = list(range(0, 16))
