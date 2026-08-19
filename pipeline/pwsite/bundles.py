"""Download bundles: the same estimates as flat CSV and Parquet.

Everything a visitor can plot, they can also download. Files are written per
vintage under `data/downloads/` and are meant to be published unchanged, so a
paper citing `pricewedge_firm_2017-12_v1.0.0.parquet` keeps resolving.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C
from .sources import load_firm_wedges


def _stamp() -> str:
    return f"{C.VINTAGE}_v{C.DATA_VERSION}"


def firm_long_frame() -> pd.DataFrame:
    """Long panel: one row per (permno, month) with a column per specification."""
    fw = load_firm_wedges()
    frames = {}
    for spec in C.FIRM_SPECS:
        frames[spec["id"]] = fw.cells[tuple(spec["cell"])]

    stack = np.stack(list(frames.values()))               # (S, T, N)
    keep = np.isfinite(stack).any(axis=0)                 # (T, N)
    t_idx, n_idx = np.nonzero(keep)

    data = {
        "permno": fw.permnos[n_idx].astype(np.int32),
        "month": fw.dates[t_idx].astype(np.int32),
    }
    for k, spec in enumerate(C.FIRM_SPECS):
        data[spec["id"]] = stack[k][t_idx, n_idx].astype(np.float32)

    frame = pd.DataFrame(data).sort_values(["permno", "month"], ignore_index=True)
    return frame


def portfolio_frames(datasets: dict[int, dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(wedge at formation, wedge by years after formation) across both treatments."""
    formation, horizon = [], []
    for rep_iss, dataset in datasets.items():
        treatment = "buy_and_hold" if rep_iss == 0 else "with_issuance_repurchases"
        for row in dataset["rows"]:
            formation.append(
                {
                    "characteristic": row["characteristic"],
                    "portfolio": row["portfolio"],
                    "treatment": treatment,
                    "pw": row["pw"],
                    "crsp_share": row["crspShare"],
                    "dollar_wedge_share": row["dollarWedge"],
                }
            )
            for years, value in row["pwByYearsAfterFormation"].items():
                horizon.append(
                    {
                        "characteristic": row["characteristic"],
                        "portfolio": row["portfolio"],
                        "treatment": treatment,
                        "years_after_formation": int(years),
                        "pw": value,
                    }
                )
    return pd.DataFrame(formation), pd.DataFrame(horizon)


def _describe(path: Path, rows: int) -> dict:
    size = path.stat().st_size
    oversize = size > C.PAGES_FILE_LIMIT
    base = C.DOWNLOAD_BASE or "/data/downloads"
    return {
        "file": path.name,
        "bytes": size,
        "rows": rows,
        "url": f"{base}/{path.name}",
        # True means the file cannot be served from Cloudflare Pages and has to
        # be hosted externally; build.py refuses to finish if that is unresolved.
        "oversize": oversize,
        "external": bool(C.DOWNLOAD_BASE),
    }


def _write(frame: pd.DataFrame, out_dir: Path, name: str) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []

    parquet = out_dir / f"{name}.parquet"
    frame.to_parquet(parquet, index=False, compression="zstd")
    written.append(_describe(parquet, len(frame)))

    csv_gz = out_dir / f"{name}.csv.gz"
    with gzip.open(csv_gz, "wt", newline="", encoding="utf-8") as fh:
        frame.to_csv(fh, index=False, float_format="%.6g")
    written.append(_describe(csv_gz, len(frame)))

    return written


def build(out_dir: Path, portfolio_datasets: dict[int, dict]) -> dict:
    downloads = out_dir / "downloads"
    stamp = _stamp()
    manifest = []

    firm = firm_long_frame()
    manifest += [
        dict(dataset="firm", **item)
        for item in _write(firm, downloads, f"pricewedge_firm_{stamp}")
    ]

    formation, horizon = portfolio_frames(portfolio_datasets)
    manifest += [
        dict(dataset="portfolio", **item)
        for item in _write(formation, downloads, f"pricewedge_portfolio_{stamp}")
    ]
    manifest += [
        dict(dataset="portfolio_horizon", **item)
        for item in _write(horizon, downloads, f"pricewedge_portfolio_horizon_{stamp}")
    ]

    readme = downloads / "README.txt"
    readme.write_text(_readme_text(manifest))
    (downloads / "index.json").write_text(json.dumps(manifest, indent=2))
    return {"files": manifest}


def _readme_text(manifest: list[dict]) -> str:
    files = "\n".join(f"  {item['file']}  ({item['rows']:,} rows)" for item in manifest)
    return f"""Price wedge estimates — vintage {C.VINTAGE}, data version {C.DATA_VERSION}

{C.CITATION['title']}
{', '.join(C.CITATION['authors'])}
{C.CITATION['journal']}

Files
{files}

pricewedge_firm_*
  One row per PERMNO-month. Columns are the eight specifications described at
  {C.CITATION['url']}/methodology. A price wedge is the log deviation of the
  market value from its informationally efficient value: positive means
  overpriced. A wedge dated t is built from characteristics dated t-1.
  Equity-level series run 1964-07..2017-12; firm-level (Eq. 9) series run
  1974-07..2016-12; out-of-sample series begin 1998-10.

pricewedge_portfolio_*
  Price wedge at portfolio formation for all ten deciles plus the aggregate
  market, for each of the 57 characteristic sorts, under both cash-flow
  treatments. `pw` is mean-bias adjusted (the PW* column of Table 1).
  Deciles are oriented so that decile 1 is the positive-alpha leg.

pricewedge_portfolio_horizon_*
  The same wedges re-based at the end of each year after portfolio formation,
  holding the fifteen-year resolution assumption fixed. Year 0 is the wedge at
  formation and equals `pw` above.

Securities are identified by CRSP PERMNO. CRSP name and ticker identifiers are
licensed and are not redistributed here.
"""
