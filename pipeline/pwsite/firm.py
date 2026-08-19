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


def _load_names_overlay() -> dict[int, dict]:
    """Optional PERMNO -> company name/ticker map.

    CRSP identifiers are licensed, so none ship with the replication package.
    Drop a CSV at `pipeline/overlays/permno_names.csv` with columns
    `permno,name,ticker` and it is merged into the search index; without it the
    site searches by PERMNO alone.
    """
    path = Path(__file__).resolve().parents[1] / "overlays" / "permno_names.csv"
    if not path.exists():
        return {}
    import csv

    out: dict[int, dict] = {}
    with path.open(newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            try:
                permno = int(row["permno"])
            except (KeyError, TypeError, ValueError):
                continue
            entry = {}
            if row.get("name"):
                entry["name"] = row["name"].strip()
            if row.get("ticker"):
                entry["ticker"] = row["ticker"].strip().upper()
            if entry:
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

    names_overlay = _load_names_overlay()

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

    # Names are optional and sparse, so they ride alongside the records rather
    # than inflating every row with two nulls.
    labels = {
        str(permno): names_overlay[permno]
        for permno, *_ in index
        if permno in names_overlay
    }

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
        "namesAttached": bool(names_overlay),
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
