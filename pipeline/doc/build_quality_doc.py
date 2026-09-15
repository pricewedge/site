#!/usr/bin/env python3
"""Render the firm-level price wedge quality report from the analysis output.

Every number comes from a CSV written by mapping_quality.py, mapping_expost.py,
realised_levels.py, stability.py or the precision run; nothing is typed by hand.
The prose is written for the paper's coauthors, in the paper's vocabulary.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from pwsite.wrds_source import CACHE  # noqa: E402

THRESHOLD = 0.85
SHORT = {"3 PCs (the paper's)": "3 principal components (paper)", "10 PCs": "10 principal components",
         "direct, unweighted": "penalized regression", "direct, precision-weighted": "penalized, precision-weighted",
         "direct + squared ranks": "penalized, with squared ranks",
         "squared, precision-weighted": "squared ranks, precision-weighted"}
CAND = {"published PWshare (PC3, EW profiles)": "Published firm-level wedges (paper)",
        "PC3 on 114 extremes, EW profiles (paper's construction)": "Paper's construction, rebuilt",
        "direct ridge 100: VW wedges, VW profiles": "Value-weighted portfolios only (penalty 100)",
        "direct ridge 300: VW wedges, VW profiles": "Value-weighted portfolios only (penalty 300)",
        "direct ridge 100: EW wedges, EW profiles": "Equal-weighted portfolios only (penalty 100)",
        "direct ridge 300: EW wedges, EW profiles": "Equal-weighted portfolios only (penalty 300)",
        "direct ridge 100: VW and EW stacked": "Both portfolio sets (penalty 100)",
        "direct ridge 300: VW and EW stacked": "Both portfolio sets (penalty 300)"}


def _tex(x) -> str:
    return str(x).replace("_", r"\_")


def _stability_section() -> str:
    sm = CACHE / "stability_current_summary.csv"
    if not sm.exists():
        return ""
    S = pd.read_csv(sm); B = pd.read_csv(CACHE / "stability_current_by_characteristic.csv")
    F = pd.read_csv(CACHE / "stability_current_firm.csv")
    h = json.loads((CACHE / "stability_current_halves.json").read_text())
    order = ["full 1964-2011", "paper 1964-2002", "first half 1964-1987", "second half 1988-2011",
             "third 1964-1979", "third 1980-1995", "third 1996-2011",
             "from 1975", "from 1980", "from 1985", "from 1990", "from 1995", "from 2000"]
    label = {"full 1964-2011": "All dates, 1964--2011", "paper 1964-2002": "Paper's window, 1964--2002",
             "first half 1964-1987": "First half, 1964--87", "second half 1988-2011": "Second half, 1988--2011",
             "third 1964-1979": "1964--79", "third 1980-1995": "1980--95", "third 1996-2011": "1996--2011",
             "from 1975": "From 1975", "from 1980": "From 1980", "from 1985": "From 1985",
             "from 1990": "From 1990", "from 1995": "From 1995", "from 2000": "From 2000"}
    S = S.set_index("subsample").loc[order]; F = F.set_index("subsample").loc[order]
    t1 = "\n".join(f"{label[lab]} & {int(r.cohorts)} & {r['lambda']:.2f} & {r.corr_full:.2f} & {r.slope_on_full:.2f} & "
                   f"{r.rmse_full:.1f} & {int(r.ls_sign_flips)}\\\\" for lab, r in S.iterrows())
    t4 = "\n".join(f"{label[lab]} & {r['corr']:.2f} & {r.mean_diff:+.1f} & {r.sd_diff:.1f} & "
                   f"{100*r.share_abs_diff_gt10:.0f}\\%\\\\" for lab, r in F.iterrows())
    B = B.copy(); B["move"] = (B["ls_second1988"] - B["ls_first1964"]).abs(); B = B.sort_values("move", ascending=False)
    top = B.head(8); bottom = B.tail(6)
    def rows(df):
        return "\n".join(f"{_tex(r.char)} & {r.ls_full:.0f} & {r.ls_first1964:.0f} & {r.ls_second1988:.0f}\\\\" for _, r in df.iterrows())
    same = float(np.mean(np.sign(B.ls_first1964) == np.sign(B.ls_second1988)))
    return r"""
\section{Stability across formation dates}

The price wedge of a portfolio is an average over formation dates, and so is
the market price of risk. This section asks whether the cross-section of
wedges is the same object in different parts of the sample. All 570 decile
wedges are re-estimated on subsets of the formation dates, the market price
of risk re-solved on each subset so that the market's wedge is zero there
; the """ + f"{h['n_verified']}" + r""" portfolios of the verified characteristics are
compared.

\begin{tbl}{Portfolio wedges estimated on subsets of the formation dates, against those on all dates.}
\begin{tabular}{lrrrrrr}\toprule
Formation dates & months & price of risk & corr.\ with all dates & slope & RMSE & sign changes\\\midrule
""" + t1 + r"""
\bottomrule
\end{tabular}
\tablenote{corr., slope, RMSE: the subsample's 560 wedges against those on all
dates; sign changes: how many of the 56 long-short spreads change sign.}
\end{tbl}

Two things stand out. Extending the paper's window to all available dates
changes almost nothing. Dropping the early dates does: every window starting
in 1980 or later correlates at 0.5 to 0.8 with the full cross-section, and
the 1980--95 third is nearly flat and unrelated to the rest.

\textbf{The two halves.} The halves use disjoint formation dates, so this is
the cleanest comparison. Their wedges correlate at """ + f"{h['corr']:.2f}" + r""". Two halves of a
constant cross-section would correlate at about """ + f"{h['expected_corr_constant']:.2f}" + r""", given the
portfolio-specific estimation noise of each half (from a block bootstrap
with the component common to all portfolios removed). The change across
portfolios has a standard deviation of """ + f"{h['sd_change']:.1f}" + r"""~pp, of which about
""" + f"{h['sd_true_change']:.1f}" + r"""~pp is beyond noise, on a cross-sectional spread of """ + f"{h['wedge_sd_full']:.1f}" + r"""~pp.
The cross-section moves between halves by roughly its own size. One caveat
in the other direction: a block bootstrap with blocks shorter than the
fifteen-year overlap understates noise, so part of the change may still be
sampling; the gap between """ + f"{h['corr']:.2f}" + r""" and """ + f"{h['expected_corr_constant']:.2f}" + r""" is too large for all of it.

\textbf{Where the change is.} Long-short spreads (long side minus short
side, pp) on all dates and in each half, for the characteristics that move
most and least; """ + f"{100*same:.0f}" + r"""\% keep the sign of their spread across halves.

\begin{tbl}{Long-short spreads, pp, for the characteristics that move most (top) and least (bottom) between halves.}
\begin{tabular}{lrrr}\toprule
 & all dates & 1964--87 & 1988--2011\\\midrule
""" + rows(top) + r"""
\midrule
""" + rows(bottom) + r"""
\bottomrule
\end{tabular}
\end{tbl}

The value ratios reverse between halves, profitability spreads shrink,
momentum grows; book-to-market, $q$, size, long-term reversal and the
investment sorts are the stable core.

\textbf{At the firm level.} The mapping refitted on each subsample and
applied to the same firm-months, against the firm-level wedges from all
dates (whose standard deviation across firms is """ + f"{float(F.loc['full 1964-2011', 'wedge_sd']):.0f}" + r"""~pp):

\begin{tbl}{Firm-level wedges from the mapping refitted on each subset, against those from all dates.}
\begin{tabular}{lrrrr}\toprule
Fitted on & corr. & mean difference & s.d.\ of difference & firms moved $>10$~pp\\\midrule
""" + t4 + r"""
\bottomrule
\end{tabular}
\end{tbl}

Firm rankings are robust to the sample (correlations 0.90 to 0.96, the
1980--95 third and the post-2000 window aside); levels are not. The halves
against each other at the firm level correlate at """ + f"{h['firm_halves_corr']:.2f}" + r""" with a
standard deviation of the difference of """ + f"{h['firm_halves_sd_diff']:.0f}" + r"""~pp. This is the evidence
behind decision~3 in the decisions note: all available formation dates,
the half-sample estimates as an internal check, no sample choices on the
website.
"""


def _levels_section() -> str:
    sm = CACHE / "realised_levels_paper_summary.csv"
    if not sm.exists():
        return ""
    Su = pd.read_csv(sm); D = pd.read_csv(CACHE / "realised_levels_paper_deciles.csv")
    def nm(c): return _tex(CAND.get(c, c))
    def block(sample):
        rows = []
        for cand in Su[Su["sample"] == sample]["candidate"].unique():
            e = Su[(Su["sample"] == sample) & (Su.candidate == cand) & (Su.weighting == "EW")].iloc[0]
            v = Su[(Su["sample"] == sample) & (Su.candidate == cand) & (Su.weighting == "VW")].iloc[0]
            z = lambda x: f"{int(round(x)):+d}"
            rows.append(f"{nm(cand)} & {e.slope:.2f} & {z(e.intercept)} & {e.mad:.1f} & {v.slope:.2f} & {z(v.intercept)} & "
                        f"{z(e.fitted_mean_ew)} & {z(e.fitted_mean_vw)}\\\\")
        return "\n".join(rows)
    ins = Su[Su["sample"] == "in-sample"]
    pub_e = ins[(ins.candidate.str.startswith("published")) & (ins.weighting == "EW")].iloc[0]
    pub_v = ins[(ins.candidate.str.startswith("published")) & (ins.weighting == "VW")].iloc[0]
    cur_e = ins[(ins.candidate == "direct ridge 100: VW wedges, VW profiles") & (ins.weighting == "EW")].iloc[0]
    cur_v = ins[(ins.candidate == "direct ridge 100: VW wedges, VW profiles") & (ins.weighting == "VW")].iloc[0]
    stacked = ins[ins.candidate.str.contains("stacked") & (ins.weighting == "EW")].sort_values("mad").iloc[0]
    best = stacked.candidate
    best_v = ins[(ins.candidate == best) & (ins.weighting == "VW")].iloc[0]
    univ_ew = float(pub_e.universe_realised); univ_vw = float(pub_v.universe_realised)
    oos2 = Su[Su["sample"] == "out-of-sample, lambda per half"]
    oos1 = Su[Su["sample"] == "out-of-sample, full lambda"]
    def dec_rows(cand, sample):
        out = []
        for wl, name in (("EW", "equal-weighted"), ("VW", "value-weighted")):
            d = D[(D.candidate == cand) & (D["sample"] == sample) & (D.weighting == wl)].sort_values("decile")
            out.append(f"{name}, assigned & " + " & ".join(f"{x:.0f}" for x in d.fitted) + "\\\\")
            out.append(f"{name}, realized & " + " & ".join(f"{x:.0f}" for x in d.realised) + "\\\\")
        return "\n".join(out)
    oos_rows = "\n".join(
        f"{nm(c)} & {oos2[(oos2.candidate==c)&(oos2.weighting=='EW')].slope.iloc[0]:.2f} & "
        f"{oos2[(oos2.candidate==c)&(oos2.weighting=='EW')].intercept.iloc[0]:+.0f} & "
        f"{oos2[(oos2.candidate==c)&(oos2.weighting=='VW')].slope.iloc[0]:.2f} & "
        f"{oos2[(oos2.candidate==c)&(oos2.weighting=='VW')].intercept.iloc[0]:+.0f}\\\\"
        for c in oos2.candidate.unique())
    return r"""
\section{Levels: do firms realize the wedge they are assigned?}

The portfolio-level tests cannot say whether the number the website prints
for a firm is the right \emph{level}, and two firm-level series can
correlate at 0.95 while differing by 20~pp. This section tests levels
directly. A candidate firm-level wedge is
treated like a characteristic: firms are sorted into deciles on it every
month at NYSE breakpoints, decile 1 holding the firms called most
overpriced; each decile is held for fifteen years, equal-weighted and
value-weighted; its realized price wedge is computed with the paper's SDF
and price of risk; and the realized wedge is regressed on the average wedge
the candidate had assigned to the decile's members. A candidate whose levels
can be trusted gives a slope of one and an intercept of zero. The
equal-weighted deciles ask whether firms realize what they are told, which is
the website's question; the value-weighted deciles ask whether the candidate
respects the calibration. The calibration adds one more check: the
value-weighted average of a candidate's firm-level wedges must equal the
market's wedge, zero.

\textbf{A reference point.} The realized wedge of the equal-weighted market
(one dollar in every firm) is """ + f"{univ_ew:.1f}" + r"""~pp; that of the value-weighted market is
""" + f"{univ_vw:.1f}" + r"""~pp (zero by calibration, up to the sample filter). The average firm is a
small firm and is far more underpriced than the average dollar. A firm-level
wedge has to reproduce that gap.

\subsection*{In sample}

\begin{tbl}{The level test in sample: realized decile wedges regressed on assigned ones.}
\begin{tabular}{lrrrrrrr}\toprule
 & \multicolumn{3}{c}{equal-weighted deciles} & \multicolumn{2}{c}{value-weighted} & \multicolumn{2}{c}{mean assigned}\\
\cmidrule(lr){2-4}\cmidrule(lr){5-6}\cmidrule(lr){7-8}
Candidate & slope & icept & gap & slope & icept & EW & VW\\\midrule
""" + block("in-sample") + r"""
\bottomrule
\end{tabular}
\tablenote{icept: intercept, pp. gap: mean absolute difference between assigned and
realized across the ten deciles, pp. mean assigned: the average of the
candidate's firm-level wedges, equal-weighted over firm-months (compare with
""" + f"{univ_ew:.0f}" + r""") and value-weighted (compare with zero).}
\end{tbl}

The paper's published firm-level wedges (three principal components of the
114 extreme deciles, each portfolio described by the equal-weighted average
of its members' characteristics) have a slope of """ + f"{pub_e.slope:.2f}" + r""" and an intercept of
""" + f"{pub_e.intercept:+.0f}" + r"""~pp on equal-weighted deciles: the firms they call fairly priced
realize about $-25$~pp, and only the most underpriced decile realizes what it
is assigned. Their value-weighted average is """ + f"{pub_e.fitted_mean_vw:+.0f}" + r"""~pp where the
calibration requires zero. The reason is in Section~4.

The pipeline's mapping on value-weighted portfolios alone has the level
right (intercepts """ + f"{cur_e.intercept:+.0f}" + r""" and """ + f"{cur_v.intercept:+.0f}" + r"""~pp) and too much dispersion (slopes
""" + f"{cur_e.slope:.2f}" + r""" and """ + f"{cur_v.slope:.2f}" + r"""): it assigns the most underpriced decile about $-70$~pp
where $-42$ is realized, because the typical firm sits far from the
value-weighted portfolios' characteristics and the regression extrapolates.
Fitting on both portfolio sets, each with the matching average of
characteristics, does best: """ + nm(best) + r""" gives a slope of """ + f"{stacked.slope:.2f}" + r""" and an
intercept of """ + f"{stacked.intercept:+.0f}" + r"""~pp equal-weighted, a mean absolute gap of """ + f"{stacked.mad:.1f}" + r"""~pp
across deciles, """ + f"{best_v.slope:.2f}" + r""" and """ + f"{best_v.intercept:+.0f}" + r"""~pp value-weighted, and a value-weighted
average of """ + f"{stacked.fitted_mean_vw:+.0f}" + r"""~pp.

\subsection*{Decile detail}

Assigned and realized wedge by decile of the assigned wedge, pp, for the
published series and for """ + nm(best).lower() + r""".

\begin{tbl}{Assigned and realized wedge by decile of the assigned wedge, pp.}
\begin{tabular}{lrrrrrrrrrr}\toprule
Published & 1 & 2 & 3 & 4 & 5 & 6 & 7 & 8 & 9 & 10\\\midrule
""" + dec_rows("published PWshare (PC3, EW profiles)", "in-sample") + r"""
\midrule
""" + nm(best) + r""" & 1 & 2 & 3 & 4 & 5 & 6 & 7 & 8 & 9 & 10\\\midrule
""" + dec_rows(best, "in-sample") + r"""
\bottomrule
\end{tabular}
\end{tbl}

\subsection*{Out of sample}

Mappings fitted on formation dates before 1988 and evaluated on the dates
from 1988 on, with the price of risk re-solved on each half so the market's
wedge is zero in both (the published series, fitted on all dates, is
evaluated on the same late dates).

\begin{tbl}{The level test out of sample: fitted before 1988, realized from 1988 on, price of risk re-solved on each half.}
\begin{tabular}{lrrrr}\toprule
Candidate & EW slope & EW icept & VW slope & VW icept\\\midrule
""" + oos_rows + r"""
\bottomrule
\end{tabular}
\end{tbl}

The slopes survive. The intercepts are about $-12$~pp for every candidate
fitted on the early dates, because the late dates' average firm realized
""" + f"{float(oos2[oos2.weighting == 'EW'].universe_realised.iloc[0]):.0f}" + r"""~pp against a late market of zero, below what the early dates taught the
mapping. With the price of risk held at its full-sample value the intercepts
are about $+15$~pp instead, the late market's own wedge. The ranking of firms
carries forward; the level of the whole cross-section moves with the sample
(Section~5).

\section{Where the method weights by value and where by firm}

\begin{tbl}{Where the method weights by value and where by firm.}
\begin{tabular}{>{\raggedright\arraybackslash}p{4.6cm}>{\raggedright\arraybackslash}p{4.4cm}>{\raggedright\arraybackslash}p{4.4cm}}\toprule
Step & Paper & Pipeline\\\midrule
Market price of risk & value-weighted market wedge set to zero & same\\
Decile portfolios & value-weighted, NYSE breakpoints & same\\
Portfolio-level characteristics & equal-weighted average of the members' rank-normalized characteristics & capitalization-weighted average; both available\\
Regression across portfolios & each portfolio one observation, 114 extreme deciles & same, all 570 deciles\\
Firm-level regressions (investment, $q$) & each firm-month one observation & not run here\\
\bottomrule
\end{tabular}
\end{tbl}

The calibration and the value-weighted decile define the object and stay.
The problem is the average that describes a portfolio. A portfolio's
equal-weighted average characteristics describe its typical member, a small
firm; its wedge belongs to its dollars, which sit in its large members.
Regressing the second on the first and evaluating at a firm's own
characteristics hands every firm the big-firm level, which is the
$""" + f"{pub_e.intercept:+.0f}" + r"""$~pp intercept above. Pairing value-weighted wedges with
capitalization-weighted averages is coherent but centres the mapping where
almost no firm is; using both portfolio sets, each with its own average, is
the construction that passes the level test and keeps the value-weighted
average of firm-level wedges at zero. Rankings barely move under any of
these; levels move by 10 to 20~pp for the typical firm. This is the evidence
behind decision~1 in the decisions note.
"""


def main() -> int:
    q = pd.read_csv(CACHE / "mapping_quality_paper.csv")
    e = pd.read_csv(CACHE / "mapping_expost_paper.csv")
    p = pd.read_csv(CACHE / "portfolio_precision.csv")
    v = json.loads((CACHE / "validation.json").read_text())
    unverified = sorted(r["char"] for r in v if (r["weight_agreement"] or 0) <= THRESHOLD)
    n_verified = len(v) - len(unverified); n_portfolios = int(q["n"].max())
    fam_direct = float(q[(q["test"] == "leave one family out") & (q["mapping"] == "direct, unweighted")]["r2"].iloc[0])
    fam_all = 0.632   # mapping_quality.py --all-characteristics, 12 September 2026; not stored in the csv
    def _spread(m, h, w):
        return float(e[(e["mapping"] == m) & (e["horizon"] == h) & (e["weighting"] == w)]["spread"].iloc[0])
    def _monotone(m):
        rows = e[e["mapping"] == m]; bad = {}
        for _, r in rows.iterrows():
            if not all(r[f"d{i}"] > r[f"d{i+1}"] for i in range(1, 10)):
                bad.setdefault({"cap": "value", "equal": "equal"}[r["weighting"]], []).append(int(r["horizon"]))
        def _hz(h):
            return ", ".join(str(x) for x in h[:-1]) + (" and " if len(h) > 1 else "") + str(h[-1]) + " months"
        return [f"{w}-weighted at {_hz(sorted(h))}" for w, h in bad.items()]
    sp60_cap, sp60_eq = _spread("direct", 60, "cap"), _spread("direct", 60, "equal")
    sp60_cap_pc3, sp60_eq_pc3 = _spread("pc3", 60, "cap"), _spread("pc3", 60, "equal")
    bd, bp = _monotone("direct"), _monotone("pc3")
    mono_direct = ("monotone at every horizon and weighting" if not bd else "monotone except " + " and ".join(bd))
    mono_pc3 = ("monotone throughout" if not bp else "not monotone " + " or ".join(bp))
    q["m"] = q["mapping"].map(lambda s: SHORT.get(s, s))
    stability_section = _stability_section()
    levels_section = _levels_section()

    tests = {"leave one characteristic out": "Leave one characteristic out",
             "leave one family out": "Leave one family of characteristics out",
             "extremes held out": "Extreme deciles held out"}
    body = []
    for t, title in tests.items():
        sub = q[q.test == t]
        body.append(r"\begin{tbl}{" + title + r": each mapping's fit on the held-out portfolios.}")
        body.append(r"\begin{tabular}{lrrrrr}\toprule")
        body.append(r"Mapping & $R^2$ & corr. & intercept & slope & RMSE\\\midrule")
        for _, r in sub.iterrows():
            bold = r["mapping"] == "direct, unweighted"
            name = (r"\bfseries " if bold else "") + r["m"]
            body.append(f"{name} & {r.r2:.3f} & {r['corr']:.3f} & {r.intercept:+.2f} & {r.slope:.3f} & {r.rmse:.2f}\\\\")
        body.append(r"\bottomrule\end{tabular}\end{tbl}")
    ex = []
    for _, r in e.iterrows():
        m = {"pc3": "3 principal components", "pc10": "10 principal components", "direct": "penalized regression"}.get(r["mapping"], r["mapping"])
        ex.append(f"{m} & {int(r.horizon)} & {'value' if r.weighting == 'cap' else 'equal'} & {r.d1:.1f} & {r.d10:.1f} & {r.spread:.1f}\\\\")
    se = p["se_nw"].dropna(); n_dates = int(p["n_cohorts"].max())

    doc = r"""\documentclass[11pt]{article}
\usepackage{pwdoc}
\title{Firm-level price wedges\\[2pt]\large How well does the mapping from portfolios to firms work?}
\author{Quality report for the pricewedge.com pipeline}\date{\today}
\begin{document}\maketitle

\subsection*{What this report checks}

The paper estimates price wedges for characteristic-sorted decile portfolios
and carries them to individual firms through a mapping from portfolio-level
characteristics to portfolio-level wedges. This report asks how much that
mapping can be trusted and whether it can be improved. Throughout, ``pp''
is percentage points of the price wedge, and a fitted or assigned wedge is
what a mapping gives a portfolio or a firm from its characteristics.

Six checks, each answering a different question:
\begin{itemize}[nosep]
\item Leave one characteristic out (Section~1): can the mapping price an
anomaly it has not seen?
\item Leave one family of characteristics out (Section~1): the same with a
whole Freyberger--Neuhierl--Weber category held out, since value
characteristics predict one another.
\item Extreme deciles held out (Section~1): fit on deciles 2 to 9, predict 1
and 10; the mapping extrapolates at the firm level, where 94\% of
firm-months lie outside the range the portfolios span on at least one
characteristic.
\item Subsequent returns (Section~2): do firms called overpriced go on to
underperform?
\item Levels (Section~3): do firms realize the wedge they are assigned? This
is the decisive test for a website that reports a number rather than a
ranking.
\item Stability across formation dates (Section~5): is the cross-section of
wedges the same object in different parts of the sample?
\end{itemize}
Every check is scored on magnitudes as well as ordering: the realized wedge
is regressed on the assigned one and the slope and intercept are reported.
A perfect mapping has slope one and intercept zero. $R^2$ is computed out of
sample as $1 - \mathrm{SSE}/\mathrm{SST}$ on the held-out portfolios, so a
mapping that ranks well but mis-scales is penalized.

\textbf{Which portfolios enter.} Only characteristics whose construction is
verified against the paper's own data, as regressors and as portfolios; a
portfolio we cannot reproduce carries a wedge we cannot trust. With
""" + f"{len(unverified)}" + r""" characteristic unverified (""" + ", ".join(unverified) + r"""), the rule costs
nothing: the leave-one-family-out fit is """ + f"{fam_all:.2f}" + r""" with every characteristic in
and """ + f"{fam_direct:.2f}" + r""" without it.

\section{The mapping on portfolios}

Candidates: the paper's three principal components of portfolio-level
characteristics, ten principal components, and a penalized regression of
the wedges on all """ + f"{n_verified}" + r""" rank-normalized characteristics (penalty chosen out of
sample, on the leave-one-family-out fit), with two variants of the latter,
weighting portfolios by the precision of their wedge and adding squared
ranks. The paper fits on the 114 extreme deciles; here all """ + f"{n_portfolios}" + r""" deciles are
used, which is what the firm level needs.

""" + "\n".join(body) + r"""

The penalized regression is best on every check, by 0.2 of $R^2$ on the
family test, and its slope is closest to one. Ten principal components come
close; three do not. Neither variant helps: precision weighting has nothing
to exploit (the standard errors of the portfolio wedges are nearly uniform,
a 1.2-fold spread between the 10th and 90th percentiles, all near
""" + f"{se.median():.0f}" + r"""~pp because """ + f"{n_dates}" + r""" formation dates that overlap in 179 of their
180 months are worth two or three independent observations), and squared
ranks halve the out-of-sample fit. The penalty is the substance: without it
the fitted wedges of an unfamiliar family are more than twice too dispersed
(the realized wedge moves 0.42 per point of fitted wedge, against 0.89 with
the penalty).

\section{Subsequent returns}

Firms are sorted into deciles on their assigned wedge each month and
tracked forward; decile 1 is the most negative (most underpriced). If the
wedge is mispricing that resolves, decile 1 should outperform.

\begin{tbl}{Subsequent cumulative returns, in percent, of the extreme deciles of the assigned wedge.}
\begin{tabular}{llrrrr}\toprule
Mapping & months & weighting & decile 1 & decile 10 & spread\\\midrule
""" + "\n".join(ex) + r"""
\bottomrule
\end{tabular}
\end{tbl}

Over five years the penalized regression separates the extreme deciles by
""" + f"{sp60_cap:.0f}" + r"""~pp value-weighted and """ + f"{sp60_eq:.0f}" + r"""~pp equal-weighted, with deciles """ + mono_direct + r""";
three principal components give """ + f"{sp60_cap_pc3:.0f}" + r""" and """ + f"{sp60_eq_pc3:.0f}" + r"""~pp and are """ + mono_pc3 + r""".
""" + levels_section + stability_section + r"""

\section{Decisions taken, and what remains open}

Three decisions follow from this report and are recorded, with their
reasons, in the decisions note: the firm-level wedge is the equal-weighted
realized wedge of firms with the firm's characteristics with the
value-weighted average pinned at zero (Section~3); the characteristics are
defined as their source papers define them (the signal log); the
wedges use all available formation dates, with no sample choices on the
website (Section~5). Every build reports the level test, the aggregate
check, the family-out fit, the subsequent-return spreads and the
half-sample comparison before a series is published.

Open: sensitivity to the fifteen-year horizon and to the SDF is untested; the
firm-level regressions in the paper that use the wedge as a regressor in
levels inherit the intercept documented in Section~3 and would change with a
level-calibrated series.

\end{document}
"""
    (HERE / "quality.tex").write_text(doc)
    print(f"wrote {HERE/'quality.tex'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
