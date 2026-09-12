#!/usr/bin/env python3
"""Regenerate the signal log's derived fields and render the LaTeX version.

`doc/signals.yaml` is the source of truth and is edited by hand as findings
land: it records, for each of the 57 characteristics, exactly how it is built
and everything that was tried and rejected. This script fills in the numbers
that should never be typed by hand -- the agreement scores and wedge errors
come from the last validation run -- and writes `doc/signals.tex`.

    ./.venv/bin/python doc/build_signal_log.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from pwsite.wrds_source import CACHE  # noqa: E402

THRESHOLD = 0.85


def latest_numbers() -> dict:
    """Agreement and wedge errors from the most recent validation run."""
    out = {}
    v = json.loads((CACHE / "validation.json").read_text())
    for row in v:
        out[row["char"]] = {
            "agreement": row["weight_agreement"],
            "long": row["long"], "long_paper": row["long_paper"],
            "short": row["short"], "short_paper": row["short_paper"],
        }
    return out


def esc(text: str) -> str:
    """LaTeX-escape running prose, leaving math between $...$ alone."""
    parts = re.split(r"(\$[^$]*\$)", str(text))
    for i, p in enumerate(parts):
        if p.startswith("$"):
            continue
        for a, b in [("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"),
                     ("$", r"\$"), ("#", r"\#"), ("_", r"\_"), ("{", r"\{"),
                     ("}", r"\}"), ("~", r"\textasciitilde{}"),
                     ("^", r"\textasciicircum{}")]:
            p = p.replace(a, b)
        parts[i] = p
    return "".join(parts)


def discrepancy_section() -> str:
    """Where the paper's documentation and its data disagree."""
    path = HERE / "discrepancies.yaml"
    if not path.exists():
        return ""
    data = yaml.safe_load(path.read_text())
    out = [r"\clearpage", r"\section*{Where the paper and its data disagree}",
           esc("Graded deliberately. Only category A claims something is wrong. "
               "B and C are documentation that cannot be built from; D concerns the "
               "reported results rather than the signals; E records things that look "
               "like discrepancies and are not, so they are not re-opened.")]
    for cat in data["categories"]:
        out.append(r"\subsection*{" + esc(f"{cat['key']}. {cat['title']}") + "}")
        out.append(r"\emph{" + esc(cat["blurb"].strip()) + "}\n")
        for it in cat["items"]:
            out.append(r"\paragraph{" + esc(it["signal"]) + "}" + "\\leavevmode" + r"\\[-6pt]")
            out.append(r"\begin{description}[leftmargin=2.1cm,style=nextline]"
                       .replace("[leftmargin=2.1cm,style=nextline]", ""))
            if it.get("documented"):
                out.append(r"\item[Documented:] " + esc(it["documented"].strip()))
            if it.get("implemented"):
                out.append(r"\item[Implemented:] " + esc(it["implemented"].strip()))
            if it.get("evidence"):
                out.append(r"\item[Evidence:] " + esc(it["evidence"].strip()))
            if it.get("consequence"):
                out.append(r"\item[Why it matters:] " + esc(it["consequence"].strip()))
            if it.get("note"):
                out.append(r"\item[Note:] " + esc(it["note"].strip()))
            out.append(r"\end{description}")
    return "\n".join(out)


def render(signals: list[dict], numbers: dict) -> str:
    rows = []
    for s in signals:
        n = numbers.get(s["id"], {})
        s["_agreement"] = n.get("agreement")
        s["_long_err"] = (n["long"] - n["long_paper"]) if "long" in n else None
        s["_short_err"] = (n["short"] - n["short_paper"]) if "short" in n else None
        rows.append(s)
    ok = [s for s in rows if (s["_agreement"] or 0) > THRESHOLD]
    bad = [s for s in rows if (s["_agreement"] or 0) <= THRESHOLD]

    def num(v, d=2):
        return "--" if v is None else f"{v:.{d}f}"

    lines = [r"""\documentclass[11pt]{article}
\usepackage[margin=2.2cm]{geometry}
\usepackage{longtable,booktabs,amsmath,xcolor,microtype,enumitem}
\usepackage[colorlinks=true,linkcolor=black,urlcolor=blue]{hyperref}
\usepackage{sectsty}\allsectionsfont{\sffamily}
\setlength{\parindent}{0pt}\setlength{\parskip}{4pt}
\newcommand{\ok}{\textcolor{black!70}{verified}}
\newcommand{\bad}{\textcolor{red!70!black}{unresolved}}
\title{\sffamily Price wedge anomaly signals:\\construction log}
\author{}\date{\today}
\begin{document}\maketitle

\section*{How to read this}

One entry per characteristic. \emph{Agreement} is the mean correlation, across
the ten deciles and 462 formation months, between our decile capitalisation
weights and the replication package's own (\texttt{datas\_all\_charP}). It tests
the characteristic and the sort alone, independently of the 241-month tracking
and the discount factor. Above """ + f"{THRESHOLD}" + r""" the construction is
treated as verified. \emph{Error} is our price wedge less the paper's Table 1
value, in percentage points.

\emph{Rejected alternatives} records what was tried and did not work, so the
same ground is not covered twice.

\section*{Summary}
\begin{longtable}{llrrrl}
\toprule
Signal & Group & Agreement & Long err. & Short err. & Status\\
\midrule
\endhead"""]
    for s in ok + bad:
        status = r"\ok" if (s["_agreement"] or 0) > THRESHOLD else r"\bad"
        lines.append(f"{esc(s['id'])} & {esc(s.get('group','')) } & "
                     f"{num(s['_agreement'],3)} & {num(s['_long_err'])} & "
                     f"{num(s['_short_err'])} & {status}\\\\")
    lines.append(r"""\bottomrule
\end{longtable}
""")
    lines.append(discrepancy_section())
    lines.append(r"\section*{Construction, signal by signal}")
    for s in ok + bad:
        lines.append(r"\subsection*{" + esc(s["id"]) + " --- " + esc(s.get("name","")) + "}")
        meta = [f"\\textbf{{Group}} {esc(s.get('group',''))}",
                f"\\textbf{{Source}} {esc(s.get('source','--'))}",
                f"\\textbf{{Frequency}} {esc(s.get('frequency','--'))}",
                f"\\textbf{{Agreement}} {num(s['_agreement'],3)}"]
        lines.append(" \\quad ".join(meta) + r"\\[2pt]")
        if s.get("inputs"):
            lines.append(r"\textbf{Inputs.} \texttt{" + esc(", ".join(s["inputs"])) + "}\n")
        lines.append(r"\textbf{Formula.}" + "\n" + r"\begin{quote}" + "\n"
                     + esc(s.get("formula","")).replace("\n", r"\\" + "\n")
                     + "\n" + r"\end{quote}")
        if s.get("notes"):
            lines.append(r"\textbf{Notes.} " + esc(s["notes"]) + "\n")
        if s.get("tried"):
            lines.append(r"\textbf{Rejected alternatives.}")
            lines.append(r"\begin{longtable}{p{10.5cm}rp{3.2cm}}")
            lines.append(r"\toprule Variant & Agreement & Verdict\\\midrule\endhead")
            for t in s["tried"]:
                sc = t.get("score")
                lines.append(f"{esc(t['variant'])} & "
                             f"{'--' if sc is None else f'{sc:.3f}'} & "
                             f"{esc(t.get('verdict',''))}\\\\")
            lines.append(r"\bottomrule\end{longtable}")
    lines.append(r"\end{document}")
    return "\n".join(lines)


def main() -> int:
    signals = yaml.safe_load((HERE / "signals.yaml").read_text())["signals"]
    numbers = latest_numbers()
    missing = [s["id"] for s in signals if s["id"] not in numbers]
    if missing:
        print(f"note: no validation numbers for {', '.join(missing)}")
    (HERE / "signals.tex").write_text(render(signals, numbers))
    n_ok = sum(1 for s in signals if (numbers.get(s['id'],{}).get('agreement') or 0) > THRESHOLD)
    print(f"{len(signals)} signals, {n_ok} verified above {THRESHOLD}")
    print(f"wrote {HERE/'signals.tex'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
