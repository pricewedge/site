#!/usr/bin/env python3
"""Build every artefact the pricewedge.com site and its downloads need.

    python build.py                # everything
    python build.py --skip-portfolio
    python build.py --out ../site/public/data

Reads only the JFE replication package; writes only into the output directory.
Validation against the published Table 1 runs before anything is written.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from pwsite import bundles, config as C, firm, portfolio, validate


def _log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def manifest(firm_stats: dict, portfolio_datasets: dict, download_stats: dict) -> dict:
    from pwsite.sources import used_characteristics

    return {
        "dataVersion": C.DATA_VERSION,
        "vintage": C.VINTAGE,
        "citation": C.CITATION,
        "firm": {
            "specs": [
                {
                    "id": s["id"],
                    "label": s["label"],
                    "short": s["short"],
                    "mapping": s["mapping"],
                    "level": s["level"],
                    "sample": s["sample"],
                    "default": s["default"],
                }
                for s in C.FIRM_SPECS
            ],
            "mappingNotes": C.MAPPING_NOTES,
            "levelNotes": C.LEVEL_NOTES,
            "sampleNotes": C.SAMPLE_NOTES,
            "characteristics": C.RANK_CHARS,
            "levels": C.LEVEL_SERIES,
            "timing": (
                "A price wedge dated t is built from firm characteristics dated "
                "t-1. Characteristic percentiles are shown at their own calendar "
                "date, following Fig. 7 of the paper."
            ),
            **firm_stats,
        },
        "portfolio": {
            "horizonMonths": C.HORIZON_MONTHS,
            "eventYears": C.EVENT_YEARS,
            "characteristics": used_characteristics(),
            "treatments": {
                "0": "Buy and hold (benchmark, Table 1)",
                "1": "Repurchases and issuances treated as (negative) dividends",
            },
            "cohorts": {str(k): v["cohorts"] for k, v in portfolio_datasets.items()},
        },
        "downloads": download_stats["files"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=C.OUT)
    parser.add_argument("--skip-portfolio", action="store_true")
    parser.add_argument("--skip-downloads", action="store_true")
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()

    if not C.PW_SHARE.exists():
        _log(f"error: cannot find {C.PW_SHARE}")
        _log("set PRICEWEDGE_SOURCE to the ReplicationPackage directory")
        return 1

    out = args.out
    if args.clean and out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    _log("validating firm-level cell labelling")
    failures = validate.check_firm()
    if failures:
        for line in failures:
            _log(f"  FAIL {line}")
        return 1
    _log("  firm-level checks passed")

    portfolio_datasets: dict[int, dict] = {}
    if not args.skip_portfolio:
        for rep_iss in (0, 1):
            _log(f"rebuilding portfolio wedges (rep_iss={rep_iss})")
            portfolio_datasets[rep_iss] = portfolio.build(rep_iss)
        _log("validating against published Table 1")
        failures = validate.check_portfolio(portfolio_datasets[0])
        if failures:
            for line in failures[:20]:
                _log(f"  FAIL {line}")
            return 1
        _log("  all 114 published PW* estimates reproduced")
        (out / "portfolios.json").write_text(
            json.dumps(
                {str(k): v for k, v in portfolio_datasets.items()}, separators=(",", ":")
            )
        )

    _log("packing firm-level series")
    firm_stats = firm.build(out)
    _log(
        f"  {firm_stats['securities']:,} securities, "
        f"{firm_stats['shards']} shard(s), {firm_stats['bytes'] / 1e6:.1f} MB"
    )
    firm.pack_struct_check(out)

    download_stats = {"files": []}
    if not args.skip_downloads:
        _log("writing download bundles")
        download_stats = bundles.build(out, portfolio_datasets)
        for item in download_stats["files"]:
            flag = "  [too large for Pages]" if item["oversize"] and not item["external"] else ""
            _log(f"  {item['file']}  {item['bytes'] / 1e6:.1f} MB{flag}")

        stranded = [i for i in download_stats["files"] if i["oversize"] and not i["external"]]
        if stranded:
            _log("")
            _log(f"warning: {len(stranded)} file(s) exceed Cloudflare Pages' 25 MiB per-file")
            _log("limit and will 404 if deployed with the site. Host them on a GitHub")
            _log("release or an R2 bucket and re-run with, for example:")
            _log("  PRICEWEDGE_DOWNLOAD_BASE=https://github.com/pricewedge/data/"
                 f"releases/download/v{C.DATA_VERSION} python build.py")

    (out / "manifest.json").write_text(
        json.dumps(manifest(firm_stats, portfolio_datasets, download_stats), indent=2)
    )
    _log(f"done -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
