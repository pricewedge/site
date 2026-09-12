#!/usr/bin/env python3
"""Diff every characteristic against the paper's own panel, firm by firm.

    ./.venv/bin/python compare_panels.py /path/to/t_by_n
    ./.venv/bin/python compare_panels.py /path/to/t_by_n --chars SUV,DTO,aBEME

For each `<name>.mat` in the folder that matches one of our 57, reports the
share of overlapping firm-months that agree exactly, the rank correlation, the
median ratio of ours to theirs (a units mismatch shows up here as a clean
1000 or 0.001), and the coverage difference. Exact agreement above ~94% is what
the five panels already shipped achieve; a rank correlation near one with a
low exact share means a units or timing convention; a low rank correlation
means a different definition.
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pwsite.panel import build_grids
from pwsite.spec_ids import ALL_CHARACTERISTICS
from pwsite.tbyn import HEADER, compare, read_panel

# Their file names where they differ from our identifiers.
ALIASES = {"Size": "SIZE", "R122": "R_12_2", "R127": "R_12_7", "R62": "R_6_2",
           "R21": "R_2_1", "R3613": "R_36_13", "BETAd": "BETA_d"}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("folder")
    p.add_argument("--chars", default=None)
    args = p.parse_args()
    folder = Path(args.folder)
    files = {ALIASES.get(f.stem, f.stem): f for f in folder.glob("*.mat")}
    wanted = args.chars.split(",") if args.chars else ALL_CHARACTERISTICS
    g = build_grids()
    print(f"{len(files)} panels in {folder}; our grid {g.months[0]}-{g.months[-1]}, "
          f"{len(g.permnos):,} securities\n")
    print(HEADER)
    rows = []
    for name in wanted:
        if name not in files or name not in g.universe.columns:
            continue
        theirs, dates = read_panel(files[name])
        ours = g.grid(name)
        r = compare(name, theirs, dates, ours, g.months, g.permnos,
                    drop_negative=(name == "BEME"))
        print(r.row(), flush=True)
        rows.append(r)
    missing = [n for n in wanted if n not in files]
    if missing:
        print(f"\nnot in the folder: {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
