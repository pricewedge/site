"""Pack the firm-level price wedges into range-requestable binary shards.

Layout
------
`firms/shard-NN.bin`  concatenated per-security records, no header.
   A record is `n_series` contiguous Float32 (little-endian) runs of
   `n_months` values each, series-major, NaN for missing:

       [series_0 over t0..t1][series_1 over t0..t1] ... [series_k over t0..t1]

   `t0`/`t1` are indices into the global month grid, covering the union of
   months in which *any* price wedge specification is observed for that
   security. So a chart never has to reason about which months exist.

`firms/index.json`  one entry per security:
       [permno, t0, t1, shard, byte_offset]
   plus the series order and the month grid, so a client can compute the exact
   `Range` header for a single series without downloading anything else.

Each security costs one HTTP range request of `n_series * n_months * 4` bytes —
about 3 KB for the median security, 40 KB for one observed since 1964.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

import numpy as np

from . import config as C
from .chars import compute_percentiles
from .sources import load_firm_wedges, yyyymm_to_index


def _series_order() -> list[dict]:
    order = [
        {"id": s["id"], "kind": "wedge", "label": s["label"], "decimals": 4}
        for s in C.FIRM_SPECS
    ]
    order += [
        {"id": c["id"], "kind": "percentile", "label": c["label"], "decimals": 3}
        for c in C.RANK_CHARS
    ]
    order += [{"id": s["id"], "kind": "level", "label": s["label"], "decimals": s["decimals"]} for s in C.LEVEL_SERIES]
    return order


ACRONYMS = {
    "IBM", "AT&T", "3M", "USA", "US", "UK", "AMR", "BP", "CBS", "CSX", "CVS",
    "DDR", "EMC", "GE", "GM", "HCA", "HP", "ITT", "JPM", "KLA", "LSI", "MGM",
    "NCR", "NL", "PNC", "PPG", "RJR", "RPM", "SAIC", "SPX", "TRW", "UAL", "UPS",
    "USG", "USX", "VF", "AES", "ADT", "AGCO", "AOL", "BJ", "DSW", "ETF", "REIT",
}
SUFFIXES = {
    "INC", "CORP", "CO", "LTD", "LLC", "PLC", "LP", "TR", "FD", "GRP", "HLDGS",
    "HLDG", "CP", "CL", "SA", "NV", "AG", "COS", "INTL", "MFG", "IND", "SVCS",
    "TECH", "PHARM", "RES", "ENRGY", "COM", "NEW", "OLD", "DEL", "THE",
}


def _titlecase(name: str) -> str:
    """CRSP stores names in upper case, which reads as shouting on a web page.

    Words are title-cased unless they look like an initialism: a known acronym,
    or a short vowel-free token that is not a corporate suffix (so IBM and MMM
    survive, LTD and CORP do not).
    """
    out = []
    for word in name.split():
        core = word.strip(".,")
        upper = core.upper()
        if upper in ACRONYMS:
            out.append(upper)
        elif (
            upper not in SUFFIXES
            and 2 <= len(core) <= 4
            and not any(v in upper for v in "AEIOU")
            and core.isalpha()
        ):
            out.append(upper)
        elif core.isdigit() or (core and core[0].isdigit()):
            out.append(upper)
        else:
            out.append(word.capitalize())
    return " ".join(out)


def _to_yyyymm(text: str) -> int | None:
    text = (text or "").strip()
    if len(text) >= 7 and text[4] == "-":
        return int(text[:4]) * 100 + int(text[5:7])
    if len(text) >= 6 and text[:6].isdigit():
        return int(text[:6])
    return None


def _load_name_spells() -> dict[int, list[dict]]:
    """Read a CRSP names export, if one has been placed in `overlays/`.

    CRSP identifiers are licensed and none ship with this repository. Drop the
    WRDS export in `pipeline/overlays/` under any filename; both the current
    schema (`issuernm`, `secinfostartdt`) and the legacy one (`comnam`,
    `namedt`) are recognised. Without a file the site searches by PERMNO alone.

    Returns permno -> list of name spells, each with a start month.
    """
    folder = Path(__file__).resolve().parents[1] / "overlays"
    files = sorted(
        f for f in folder.glob("*")
        if f.suffix.lower() in {".csv", ".txt"} and f.name != "README.md"
    )
    if not files:
        return {}

    import csv

    spells: dict[int, list[dict]] = {}
    for path in files:
        with path.open(newline="", encoding="utf-8-sig", errors="replace") as fh:
            reader = csv.DictReader(fh)
            cols = {c.lower(): c for c in (reader.fieldnames or [])}
            name_col = cols.get("issuernm") or cols.get("comnam") or cols.get("name")
            start_col = cols.get("secinfostartdt") or cols.get("namedt")
            tick_col = cols.get("ticker") or cols.get("tradingsymbol")
            if "permno" not in cols or not name_col:
                continue
            for row in reader:
                try:
                    permno = int(float(row[cols["permno"]]))
                except (TypeError, ValueError):
                    continue
                raw = (row.get(name_col) or "").strip()
                if not raw:
                    continue
                spells.setdefault(permno, []).append(
                    {
                        "name": _titlecase(raw),
                        "ticker": (row.get(tick_col) or "").strip().upper() if tick_col else "",
                        "start": _to_yyyymm(row.get(start_col, "")) if start_col else None,
                    }
                )
    return spells


def _resolve_names(spells: dict[int, list[dict]], last_month: dict[int, int]) -> dict[int, dict]:
    """Pick the name each security carried in the last month we estimate for it.

    The names file runs past the end of our sample, so taking the most recent
    spell outright would label a 2017 chart with a name the firm only adopted
    later. Preferring the spell in force at the security's final observation
    keeps the label contemporaneous with the data.
    """
    out: dict[int, dict] = {}
    for permno, options in spells.items():
        cutoff = last_month.get(permno)
        dated = [o for o in options if o["start"] is not None]
        pick = None
        if cutoff and dated:
            eligible = [o for o in dated if o["start"] <= cutoff]
            pick = max(eligible, key=lambda o: o["start"]) if eligible else min(
                dated, key=lambda o: o["start"]
            )
        if pick is None:
            pick = max(dated, key=lambda o: o["start"]) if dated else options[-1]
        entry = {"name": pick["name"]}
        if pick["ticker"]:
            entry["ticker"] = pick["ticker"]
        out[permno] = entry
    return out


def build(out_dir: Path) -> dict:
    fw = load_firm_wedges()
    dates = fw.dates
    n_months = fw.n_months

    # Align the 1099-month characteristic grid to the 642-month wedge grid.
    from .sources import FirmPanel

    with FirmPanel() as fp:
        src_dates = fp.dates
    pos = {int(d): i for i, d in enumerate(src_dates)}
    month_index = np.array([pos[int(d)] for d in dates], dtype=int)

    wedge_stack = np.stack(
        [fw.cells[tuple(s["cell"])].astype(np.float32) for s in C.FIRM_SPECS]
    )  # (8, T, N)

    extra = compute_percentiles(month_index)  # each (N, T)

    series = _series_order()
    n_series = len(series)

    # Coverage window per security: union across the wedge specifications only.
    observed = np.isfinite(wedge_stack).any(axis=0)          # (T, N)
    has_any = observed.any(axis=0)                            # (N,)
    first = np.argmax(observed, axis=0)
    last = n_months - 1 - np.argmax(observed[::-1], axis=0)

    spells = _load_name_spells()

    firms_dir = out_dir / "firms"
    firms_dir.mkdir(parents=True, exist_ok=True)
    for stale in firms_dir.glob("shard-*.bin"):
        stale.unlink()

    index: list[list] = []
    shard_no = 0
    offset = 0
    handle = (firms_dir / f"shard-{shard_no:02d}.bin").open("wb")

    order = np.argsort(fw.permnos)
    for col in order:
        if not has_any[col]:
            continue
        t0, t1 = int(first[col]), int(last[col])
        span = t1 - t0 + 1
        block = np.empty((n_series, span), dtype="<f4")
        for k, spec in enumerate(C.FIRM_SPECS):
            block[k] = wedge_stack[k, t0 : t1 + 1, col]
        k = len(C.FIRM_SPECS)
        for meta in C.RANK_CHARS + C.LEVEL_SERIES:
            block[k] = extra[meta["id"]][col, t0 : t1 + 1]
            k += 1

        payload = block.tobytes()
        if offset and offset + len(payload) > C.SHARD_MAX_BYTES:
            handle.close()
            shard_no += 1
            offset = 0
            handle = (firms_dir / f"shard-{shard_no:02d}.bin").open("wb")

        handle.write(payload)
        index.append([int(fw.permnos[col]), t0, t1, shard_no, offset])
        offset += len(payload)

    handle.close()

    # Names are optional, so they ride alongside the records rather than
    # inflating every row with two nulls.
    last_month = {permno: int(dates[t1]) for permno, _t0, t1, _s, _o in index}
    resolved = _resolve_names(spells, last_month) if spells else {}
    labels = {str(permno): resolved[permno] for permno, *_ in index if permno in resolved}

    (firms_dir / "index.json").write_text(
        json.dumps(
            {
                "months": [int(d) for d in dates],
                "series": series,
                "bytesPerValue": 4,
                "dtype": "float32-le",
                "recordFields": ["permno", "t0", "t1", "shard", "offset"],
                "records": index,
                "hasNames": bool(labels),
                "names": labels,
            },
            separators=(",", ":"),
        )
    )

    total_bytes = sum(
        (firms_dir / f"shard-{i:02d}.bin").stat().st_size for i in range(shard_no + 1)
    )
    return {
        "securities": len(index),
        "shards": shard_no + 1,
        "bytes": total_bytes,
        "series": [s["id"] for s in series],
        "namesAttached": bool(labels),
    }


def pack_struct_check(path: Path) -> None:  # pragma: no cover - dev helper
    """Assert the on-disk record for one security round-trips."""
    meta = json.loads((path / "firms" / "index.json").read_text())
    permno, t0, t1, shard, off = meta["records"][0]
    span = t1 - t0 + 1
    n = len(meta["series"])
    with (path / "firms" / f"shard-{shard:02d}.bin").open("rb") as fh:
        fh.seek(off)
        raw = fh.read(n * span * 4)
    assert len(raw) == n * span * 4
    struct.unpack(f"<{n * span}f", raw)
