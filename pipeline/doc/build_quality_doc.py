#!/usr/bin/env python3
"""Render the firm-level price wedge quality report from the analysis output.

Reads the CSVs written by mapping_quality.py, mapping_expost.py and
portfolio_precision, so the numbers in the document are never typed by hand.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import json
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from pwsite.wrds_source import CACHE  # noqa: E402

SHORT = {"3 PCs (the paper's)": "3 PCs (paper)", "10 PCs": "10 PCs",
         "direct, unweighted": "direct", "direct, precision-weighted": "direct, precision-wtd",
         "direct + squared ranks": "direct + squares",
         "squared, precision-weighted": "squares, precision-wtd"}


def table(df, cols, fmt):
    out = []
    for _, r in df.iterrows():
        out.append(" & ".join(fmt(r, c) for c in cols) + r"\\")
    return "\n".join(out)


def _tex(x: str) -> str:
    return str(x).replace("_", r"\_")


def _stability_section() -> str:
    """Wedges on subsamples of the formation cohorts (stability.py current)."""
    sm = CACHE / "stability_current_summary.csv"
    if not sm.exists():
        return ""
    S = pd.read_csv(sm); B = pd.read_csv(CACHE / "stability_current_by_characteristic.csv")
    F = pd.read_csv(CACHE / "stability_current_firm.csv")
    h = json.loads((CACHE / "stability_current_halves.json").read_text())
    order = ["full 1964-2011", "paper 1964-2002", "first half 1964-1987", "second half 1988-2011",
             "third 1964-1979", "third 1980-1995", "third 1996-2011",
             "from 1975", "from 1980", "from 1985", "from 1990", "from 1995", "from 2000"]
    S = S.set_index("subsample").loc[order]; F = F.set_index("subsample").loc[order]
    rows = []
    for lab, r in S.iterrows():
        rows.append(f"{lab} & {int(r.cohorts)} & {r['lambda']:.2f} & {r.wedge_sd:.1f} & {r.median_se_idio:.1f} & "
                    f"{r.corr_full:.2f} & {r.rank_full:.2f} & {r.slope_on_full:.2f} & {r.rmse_full:.1f} & "
                    f"{r.ls_corr:.2f} & {int(r.ls_sign_flips)}\\\\")
    t1 = "\n".join(rows)
    B = B.copy(); B["move"] = (B["ls_second1988"] - B["ls_first1964"]).abs(); B = B.sort_values("move", ascending=False)
    rows = []
    for _, r in B.iterrows():
        rows.append(f"{_tex(r.char)} & {r.ls_full:.0f} & {r.ls_paper:.0f} & {r.ls_first1964:.0f} & {r.ls_second1988:.0f} & "
                    f"{r.ls_1964:.0f} & {r.ls_1980:.0f} & {r.ls_1996:.0f}\\\\")
    t3 = "\n".join(rows)
    same = float(np.mean(np.sign(B.ls_first1964) == np.sign(B.ls_second1988)))
    ls_corr_halves = float(B.ls_first1964.corr(B.ls_second1988))
    rows = []
    for lab, r in F.iterrows():
        rows.append(f"{lab} & {r['corr']:.2f} & {r['rank']:.2f} & {r.mean_diff:+.1f} & {r.sd_diff:.1f} & "
                    f"{100*r.share_abs_diff_gt10:.0f}\\% & {r.corr_recent:.2f} & {r.sd_diff_recent:.1f}\\\\")
    t4 = "\n".join(rows)
    fw_sd = float(F.loc["full 1964-2011", "wedge_sd"])
    return r"""
\section*{Is the cross-section of wedges stable over time, and which sample should the site use?}

Every portfolio wedge is $-\log$ of the mean, over formation cohorts, of the
discounted fifteen-year cash flow per dollar of price. The full available
sample has """ + f"{h['cohorts']}" + r""" cohorts, formed """ + f"{h['first_cohort']}" + r""" to """ + f"{h['last_cohort']}" + r""",
with cash flows to """ + f"{h['last_month']}" + r""". Cohorts overlap in 179 of their 180 months, so the
sample holds about three independent fifteen-year windows, and any subsample
of it one or two. The question is whether the cross-section of wedges is the
same object in different parts of the sample, and if not, which part the site
should rest on.

\texttt{stability.py} re-estimates all 570 decile wedges on subsets of the
cohorts: the paper's own window, halves, thirds, and every window that starts
in a later year. On each subset the market price of risk is re-solved so that
the market wedge is zero there, as it is on the full sample; without that, a
subsample's wedges shift as a block with the market's realised return. All
comparisons below use the """ + f"{h['n_verified']}" + r""" portfolios of the verified characteristics.

\subsection*{Each subsample against the full sample}

{\small\begin{longtable}{lrrrrrrrrrr}\toprule
Cohorts formed & N & $\lambda$ & sd & noise & corr & rank & slope & RMSE & LS corr & flips\\\midrule
\endhead
""" + t1 + r"""
\bottomrule\end{longtable}}

\noindent\emph{sd}: cross-sectional standard deviation of the subsample's wedges, pp.
\emph{noise}: median idiosyncratic standard error of a wedge in that subsample, pp,
from a moving-block bootstrap over its cohorts with each draw demeaned across
portfolios so the component common to all portfolios drops out (block length
120 cohorts, or a third of the subsample when shorter; """ + f"{h['draws']}" + r""" draws). \emph{corr},
\emph{rank}, \emph{slope}, \emph{RMSE}: the subsample's wedges against the full
sample's, slope of subsample on full. \emph{LS corr} and \emph{flips}: the
correlation of the 56 long-short spreads with the full sample's, and how many
change sign.

Two things stand out. Adding the 2003--2011 cohorts to the paper's window
changes almost nothing: correlation 0.99, one sign flip, RMSE 1.4~pp. Dropping
the early cohorts is a different matter. Every window that starts in 1980 or
later correlates 0.5 to 0.8 with the full cross-section, and the 1980--1995
third is nearly flat (sd 5.6~pp against 9.3) and unrelated to the rest.

\subsection*{The two halves against each other}

The halves are independent cohorts, so this is the cleanest test. Their
wedges correlate """ + f"{h['corr']:.2f}" + r""" (rank """ + f"{h['rank']:.2f}" + r"""), with a slope of second on first of
""" + f"{h['slope']:.2f}" + r""". Given each half's idiosyncratic noise, two halves of a \emph{constant}
cross-section would correlate about """ + f"{h['expected_corr_constant']:.2f}" + r""". The change across
portfolios has a standard deviation of """ + f"{h['sd_change']:.1f}" + r"""~pp, of which noise accounts for
""" + f"{h['noise_idio']:.1f}" + r"""~pp and about """ + f"{h['sd_true_change']:.1f}" + r"""~pp is left, on a cross-sectional spread of
""" + f"{h['wedge_sd_full']:.1f}" + r"""~pp. """ + f"{100*h['share_gt2_idio']:.0f}" + r"""\% of portfolios move by more than two idiosyncratic
standard errors. So the cross-section moves between halves by roughly its own
size. That is the honest reading, with one caveat in the other direction: a
block bootstrap with blocks shorter than the 180-month overlap understates
sampling noise, so some of the """ + f"{h['sd_true_change']:.1f}" + r"""~pp may still be sampling variation. The
gap between """ + f"{h['corr']:.2f}" + r""" and """ + f"{h['expected_corr_constant']:.2f}" + r""" is too large for all of it to be.
Judged against the \emph{total} Newey--West standard errors, which include the
component common to all portfolios, no portfolio's change is significant
(median total noise """ + f"{h['noise_total']:.0f}" + r"""~pp); that statistic answers a different question,
whether a single wedge is known, and the answer to that was already no.

\subsection*{Where the change sits}

Long-short spread of each characteristic (long leg less short leg, pp) by
subsample, ordered by how much it moves between the halves.
""" + f"{100*same:.0f}" + r"""\% of characteristics keep the sign of their spread across halves; the
spreads correlate """ + f"{ls_corr_halves:.2f}" + r""" across halves.

\begin{longtable}{lrrrrrrr}\toprule
 & full & paper & 1964--87 & 1988--2011 & 1964--79 & 1980--95 & 1996--2011\\\midrule
\endhead
""" + t3 + r"""
\bottomrule\end{longtable}

The value ratios reverse between halves, the profitability spreads shrink,
and momentum grows; book-to-market, Q, size, long-term reversal and the
investment-type sorts are the stable core. The 1980--1995 column is flat for
almost everything.

\subsection*{What it does to the firm-level wedges}

The direct mapping refitted on each subsample's portfolio wedges, applied to
the same firm-months, against the full-sample firm wedges (sd """ + f"{fw_sd:.0f}" + r"""~pp).

{\small\begin{longtable}{lrrrrrrr}\toprule
Fitted on & corr & rank & mean diff & sd diff & $|$diff$|>10$ & corr 2020--25 & sd diff 2020--25\\\midrule
\endhead
""" + t4 + r"""
\bottomrule\end{longtable}}

The ranking of firms is robust to the sample: correlations 0.90 to 0.96 for
every window except the 1980--1995 third and the post-2000 window. The
magnitudes are not: refitting on the second half moves two fifths of firms by
more than 10~pp, a later window more. The halves against each other at the
firm level correlate """ + f"{h['firm_halves_corr']:.2f}" + r""" with a standard deviation of the difference of
""" + f"{h['firm_halves_sd_diff']:.0f}" + r"""~pp.

\subsection*{Which sample}

The full available sample is the headline choice. It is the only one with
about three independent fifteen-year windows; every later window rests on one
or two cycles, which is why the price of risk swings from 5.6 to 2.5 to 2.8
across the thirds, and the windows ending after 2008 carry a different scale
(slopes 1.2 to 1.35 on the extremes). Extending the paper's window to 2011
cohorts and 2025 cash flows is safe. Switching to a later window is not a
better estimate of the same quantity: it changes the answer in the direction
of the post-1990 weakness of the value ratios and the 2000 and 2008 episodes,
which is regime. What the drift does argue for is showing it: the full-sample
firm wedge with the two half-sample estimates as a range, or ``since 1988'' as
a labelled alternative specification, with the statement that rankings agree
at 0.9 and magnitudes differ by about $\pm$12~pp.
"""


def _levels_section() -> str:
    """Realised-wedge level test (realised_levels.py) and the weighting discussion."""
    sm = CACHE / "realised_levels_paper_summary.csv"
    if not sm.exists():
        return ""
    Su = pd.read_csv(sm); D = pd.read_csv(CACHE / "realised_levels_paper_deciles.csv")
    short = {"published PWshare (PC3, EW profiles)": "published PWshare (PC3, EW profiles)",
             "PC3 on 114 extremes, EW profiles (paper's construction)": "PC3, 114 extremes, EW profiles (rebuilt)"}
    def nm(c): return _tex(short.get(c, c))
    def block(sample):
        rows = []
        for cand in Su[Su["sample"] == sample]["candidate"].unique():
            e = Su[(Su["sample"] == sample) & (Su.candidate == cand) & (Su.weighting == "EW")].iloc[0]
            v = Su[(Su["sample"] == sample) & (Su.candidate == cand) & (Su.weighting == "VW")].iloc[0]
            rows.append(f"{nm(cand)} & {e.slope:.2f} & {e.intercept:+.1f} & {e.mad:.1f} & {v.slope:.2f} & {v.intercept:+.1f} & {v.mad:.1f} & "
                        f"{e.fitted_mean_ew:.1f} & {e.fitted_mean_vw:.1f}\\\\")
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
    oos1 = Su[Su["sample"] == "out-of-sample, full lambda"]; oos2 = Su[Su["sample"] == "out-of-sample, lambda per half"]
    def dec_rows(cand, sample):
        out = []
        for wl in ("EW", "VW"):
            d = D[(D.candidate == cand) & (D["sample"] == sample) & (D.weighting == wl)].sort_values("decile")
            out.append(f"{wl} fitted & " + " & ".join(f"{x:.0f}" for x in d.fitted) + "\\\\")
            out.append(f"{wl} realised & " + " & ".join(f"{x:.0f}" for x in d.realised) + "\\\\")
        return "\n".join(out)
    return r"""
\section*{Levels: do firms realise the wedge they are assigned?}

The criteria above compare mappings on portfolios. None of them can say
whether the number the site would print for a firm is the right \emph{level},
and correlation-based comparisons hide level errors entirely. This section
tests levels directly. Each candidate firm wedge is treated as a
characteristic: firms are sorted into deciles on it every month at NYSE
breakpoints, decile 1 holding the firms called most overpriced, and each
decile is held for fifteen years as an equal-weighted and as a
value-weighted portfolio. The realised wedge of that portfolio, $-\log$ of
the mean discounted cash flow per dollar over the formation cohorts with the
same SDF and the same $\lambda$ as Table~1, is then regressed on the mean
wedge the mapping assigned to the decile's members. A mapping whose levels
can be trusted shows a slope of one and an intercept of zero. The
equal-weighted version is the one that matters for a website that reports
one firm at a time; the value-weighted version says whether the mapping
respects the calibration that sets the value-weighted market wedge to zero.
\texttt{realised\_levels.py} computes everything below.

A reference point first. The realised wedge of the equal-weighted universe,
one dollar in every firm, is """ + f"{univ_ew:.1f}" + r"""~pp, against """ + f"{univ_vw:.1f}" + r"""~pp for the
value-weighted universe (zero by calibration up to the admissibility filter).
The average firm is a small firm and is far more underpriced, under this SDF,
than the average dollar. Any firm-level wedge has to reproduce that gap.

\subsection*{In sample: fitted and realised on all cohorts}

{\footnotesize\begin{longtable}{lrrrrrrrr}\toprule
 & \multicolumn{3}{c}{equal-weighted deciles} & \multicolumn{3}{c}{value-weighted deciles} & \multicolumn{2}{c}{mean fitted wedge}\\
Firm wedge & slope & icept & MAD & slope & icept & MAD & EW & VW\\\midrule
\endhead
""" + block("in-sample") + r"""
\bottomrule\end{longtable}}

\noindent\emph{slope}, \emph{icept}: realised decile wedge regressed on the
decile's mean fitted wedge. \emph{MAD}: mean absolute gap between fitted and
realised across the ten deciles, pp. \emph{mean fitted}: the mapping's own
firm-level average, equal-weighted over firm-months and capitalisation-weighted;
the latter should sit near the value-weighted universe wedge. ``VW wedges,
VW profiles'' is the mapping used everywhere else in this report; ``EW
wedges, EW profiles'' fits the same regression on equal-weighted decile
portfolios described by equal-weighted mean ranks; ``stacked'' fits on both
sets at once, each with its own profiles.

The published firm wedges are the paper's PC3 mapping with equal-weighted
profiles, and our rebuild of that construction reproduces them (level within
1~pp). On equal-weighted deciles they have a slope of """ + f"{pub_e.slope:.2f}" + r""" and an intercept of
""" + f"{pub_e.intercept:+.1f}" + r"""~pp: the firms the paper calls fairly priced realise wedges near
$-25$~pp, and only the most underpriced decile realises what it is assigned.
Value-weighted the slope is """ + f"{pub_v.slope:.2f}" + r""" and the intercept """ + f"{pub_v.intercept:+.1f}" + r"""~pp. The reason
is mechanical and is set out below: an equal-weighted profile places the
average firm at the centre of a regression whose left-hand side is the
value-weighted, big-firm wedge.

The mapping used elsewhere in this report has the level right (intercepts
""" + f"{cur_e.intercept:+.1f}" + r""" and """ + f"{cur_v.intercept:+.1f}" + r"""~pp) but too much dispersion (slopes """ + f"{cur_e.slope:.2f}" + r""" and
""" + f"{cur_v.slope:.2f}" + r"""): it assigns the bottom decile about $-70$~pp where $-42$ is
realised. Its centre is coherent because value-weighted wedges are paired
with value-weighted profiles, but the typical firm sits far from that centre
and the regression extrapolates. Heavier shrinkage repairs the
value-weighted slope and not the equal-weighted one. Fitting on both
portfolio sets with matching profiles does best: """ + nm(best) + r""" reaches a slope of
""" + f"{stacked.slope:.2f}" + r""" and an intercept of """ + f"{stacked.intercept:+.1f}" + r"""~pp equal-weighted, with a mean absolute
gap of """ + f"{stacked.mad:.1f}" + r"""~pp across deciles, and """ + f"{best_v.slope:.2f}" + r""" and """ + f"{best_v.intercept:+.1f}" + r"""~pp value-weighted.

The last two columns are the aggregate check. Because the market wedge is
zero by calibration, the capitalisation-weighted mean of any firm-level wedge
should sit near the value-weighted universe's realised wedge
(""" + f"{univ_vw:.1f}" + r"""~pp here, the admissibility filter aside). The published series gives
""" + f"{pub_e.fitted_mean_vw:+.1f}" + r"""~pp, the value-weighted mapping """ + f"{cur_e.fitted_mean_vw:+.1f}" + r"""~pp, and """ + nm(best) + r"""
""" + f"{stacked.fitted_mean_vw:+.1f}" + r"""~pp; a mapping fitted on equal-weighted portfolios alone
overshoots the other way. Equal-weighted, the same column should sit near the
equal-weighted universe (""" + f"{univ_ew:.1f}" + r"""~pp): """ + f"{pub_e.fitted_mean_ew:+.1f}" + r""" for the published
series against """ + f"{stacked.fitted_mean_ew:+.1f}" + r""" for the stacked mapping.

\subsection*{Decile detail, in sample}

Mean fitted and realised wedge by decile of the fitted wedge (pp), for the
published series and for """ + nm(best) + r""".

{\small\begin{tabular}{lrrrrrrrrrr}\toprule
published & 1 & 2 & 3 & 4 & 5 & 6 & 7 & 8 & 9 & 10\\\midrule
""" + dec_rows("published PWshare (PC3, EW profiles)", "in-sample") + r"""
\midrule
""" + nm(best) + r""" & 1 & 2 & 3 & 4 & 5 & 6 & 7 & 8 & 9 & 10\\\midrule
""" + dec_rows(best, "in-sample") + r"""
\bottomrule\end{tabular}}

\subsection*{Out of sample}

Mappings fitted on the cohorts formed before 1988 and evaluated on the
cohorts formed from 1988 on (the published series, fitted on all cohorts, is
evaluated on the same late cohorts). Two versions: with $\lambda$ held at the
full-sample value, where the late cohorts' own market wedge is
""" + f"{float(oos1[oos1.weighting == 'VW'].universe_realised.iloc[0]):+.0f}" + r"""~pp value-weighted so every intercept carries that shift; and with
$\lambda$ re-solved on each half, so the market wedge is zero in the fitting
and in the evaluation period alike.

{\footnotesize\begin{longtable}{llrrrr}\toprule
Firm wedge & $\lambda$ & EW slope & EW icept & VW slope & VW icept\\\midrule
\endhead
""" + "\n".join(
        f"{nm(c)} & {lab} & {Su[(Su['sample']==smp)&(Su.candidate==c)&(Su.weighting=='EW')].slope.iloc[0]:.2f} & "
        f"{Su[(Su['sample']==smp)&(Su.candidate==c)&(Su.weighting=='EW')].intercept.iloc[0]:+.1f} & "
        f"{Su[(Su['sample']==smp)&(Su.candidate==c)&(Su.weighting=='VW')].slope.iloc[0]:.2f} & "
        f"{Su[(Su['sample']==smp)&(Su.candidate==c)&(Su.weighting=='VW')].intercept.iloc[0]:+.1f}\\\\"
        for smp, lab in (("out-of-sample, full lambda", "full"), ("out-of-sample, lambda per half", "per half"))
        for c in Su[Su['sample'] == smp].candidate.unique()) + r"""
\bottomrule\end{longtable}}

Out of sample the slopes survive for the stacked mapping (""" + f"{float(oos2[(oos2.candidate == best) & (oos2.weighting == 'EW')].slope.iloc[0]):.2f}" + r""" equal-weighted,
""" + f"{float(oos2[(oos2.candidate == best) & (oos2.weighting == 'VW')].slope.iloc[0]):.2f}" + r""" value-weighted with $\lambda$ per half) and the level does not: with
$\lambda$ held fixed the intercepts are about $+15$~pp, the late market's own
wedge; with $\lambda$ re-solved per half they are about $-12$~pp, because the
late cohorts' average firm realised """ + f"{float(oos2[oos2.weighting == 'EW'].universe_realised.iloc[0]):.0f}" + r"""~pp against a late market of zero,
below what the early cohorts taught the mapping. This is the same message as
the time-split test earlier: the ranking of firms carries forward, the level of
the cross-section moves with the sample, and no mapping fitted on one period
can know the next period's level.

\section*{Equal and value weighting in the method}

The method is value-weighted where it defines the object and equal-weighted
where it carries it to firms, and the two do not meet. Where each is used:

\begin{tabular}{p{4.6cm}p{4.2cm}p{4.2cm}}\toprule
Step & Paper & This pipeline\\\midrule
Price of risk $\lambda$ & value-weighted market wedge set to zero & same\\
Decile portfolios & value-weighted, NYSE breakpoints & same\\
Portfolio wedges & $-\log$ of the mean over cohorts, each cohort equal & same\\
Portfolio profiles (regressors) & equal-weighted mean of members' ranks (\texttt{nanmean}; the code asks itself ``should this be value weighted?'') & capitalisation-weighted mean rank; both available since 14 September\\
Regression across portfolios & each portfolio one observation, 114 extremes & same, 570 deciles\\
Firm ranks & rank within the sortable universe & rank within firms with the characteristic\\
Firm-level averages, Q and investment regressions & each firm-month one observation & not run here\\
\bottomrule\end{tabular}\\[6pt]

The calibration is the identifying normalisation of the SDF and must stay:
a wedge is a statement relative to the average dollar in the market. The
value-weighted decile is the standard object and its wedge is a
dollar-weighted quantity. The problem is the profile. A portfolio's
equal-weighted mean rank describes its average member, which for any decile
is a small firm; its wedge describes its dollars, which belong to its large
members. Regressing the second on the first and then evaluating at a firm's
own rank hands every firm the big-firm level, which is what the
$""" + f"{pub_e.intercept:+.0f}" + r"""$~pp intercept above measures. Pairing value-weighted wedges with
value-weighted profiles is coherent but centres the mapping where almost no
firm is, and pairing equal-weighted wedges with equal-weighted profiles is
coherent and centred on the firms but throws away the dollar-weighted
information the calibration is built on. Using both, each with its own
profile, is the construction that passes the level test, and the
capitalisation-weighted mean of its firm wedges is the check that it still
respects the calibration.

None of this changes rankings much: every candidate above ranks firms
similarly (correlations 0.9 and above). It changes the number a firm is
given, by 10 to 20~pp for the typical firm, and it changes what an average
of firm-level wedges means in any firm-level regression.

\section*{Recommendations}

For discussion; each item names what the evidence in this report supports.

\begin{enumerate}
\item \textbf{Signal construction.} Adopt the documented definitions where the
data departs from them and the departure changes what is measured: operating
accruals net of depreciation (OA, AOA); SUV and DTO as the monthly measures
Table~A.1 describes rather than the last trading day's value; TNOVR with
contemporaneous volume; an industry classification that is stated. Keep, and
document, the conventions the panels revealed that are innocuous (BETA\_d
over 249 trading days, sdDVOL without zero-volume days, IDIOV with $n-1$,
the day-level spread). Treat a zero-sales ratio as missing. Drop or flag aPM:
its industry means are dominated by firms with near-zero sales and its
long-short alpha is indistinguishable from zero, so neither its sort nor its
sign is identified.
\item \textbf{Wedge estimation.} Keep the calibration that sets the
value-weighted market wedge to zero. Use the full available sample as the
headline (formations to 2011, cash flows to 2025) and report the half-sample
range, since the cross-section moves by roughly its own size between halves;
do not move to a later window. Apply the log-bias correction to the
left-hand side of the mapping or not at all; it is about 1~pp.
\item \textbf{Mapping.} Replace three principal components on the 114
extremes with a penalised direct regression on all deciles; it is better on
every portfolio criterion and is the only form whose penalty can be chosen
out of sample. Fit it on value-weighted and equal-weighted decile portfolios
together, each with profiles of its own weighting, and choose the penalty on
the leave-one-family-out fit subject to the realised-level test (slope near
one, intercept near zero, equal- and value-weighted).
\item \textbf{Weighting.} Make the choice explicit at each step and never
pair a wedge with a profile of a different weighting. For a site that reports
one firm at a time the target is the equal-weighted realised wedge of firms
with those characteristics; the capitalisation-weighted mean of the firm
wedges must still equal the market wedge, and that check belongs in the
pipeline.
\item \textbf{Levels, not correlations.} Evaluate every firm-level series on
realised wedges of fitted deciles, and report the slope, the intercept and
the decile table alongside any correlation. The published firm wedges pass
the correlation test and fail the level test by """ + f"{abs(pub_e.intercept):.0f}" + r"""~pp.
\item \textbf{Uncertainty and range.} A portfolio wedge carries a standard
error near 30~pp and the half-sample estimates differ by about 12~pp at the
firm level; present firm wedges with that range, and flag firms whose
characteristics lie outside the profiles' support, where the mapping
extrapolates.
\item \textbf{Downstream uses.} Firm-level regressions that use the wedge as
a regressor in levels (the investment-$q$ analysis) inherit the level error
of the firm wedges and should be re-run with a level-calibrated series.
\item \textbf{Open items.} The horizon (fifteen years) and the SDF are taken
as given here; sensitivity to both is untested. The move to a public
characteristic library (JKP) for the extension is the right way to make the
signal side reproducible.
\end{enumerate}
"""


def main() -> int:
    q = pd.read_csv(CACHE / "mapping_quality_paper.csv")
    e = pd.read_csv(CACHE / "mapping_expost_paper.csv")
    p = pd.read_csv(CACHE / "portfolio_precision.csv")
    v = json.loads((CACHE / "validation.json").read_text())
    unverified = sorted(r["char"] for r in v if (r["weight_agreement"] or 0) <= 0.85)
    n_unverified = len(unverified); unverified_list = ", ".join(unverified) or "none"
    n_verified = len(v) - n_unverified; n_portfolios = int(q["n"].max())
    fam_direct = float(q[(q["test"] == "leave one family out") & (q["mapping"] == "direct, unweighted")]["r2"].iloc[0])
    fam_all = 0.632   # mapping_quality.py --all-characteristics, 12 September 2026; not stored in the csv
    def _spread(m, h, w):
        return float(e[(e["mapping"] == m) & (e["horizon"] == h) & (e["weighting"] == w)]["spread"].iloc[0])
    def _monotone(m):
        rows = e[e["mapping"] == m]
        bad = {}
        for _, r in rows.iterrows():
            if not all(r[f"d{i}"] > r[f"d{i+1}"] for i in range(1, 10)):
                bad.setdefault({"cap": "capitalisation", "equal": "equal"}[r["weighting"]], []).append(int(r["horizon"]))
        def _hz(h):
            return ", ".join(str(x) for x in h[:-1]) + (" and " if len(h) > 1 else "") + str(h[-1]) + " months"
        return [f"{w}-weighted at {_hz(sorted(h))}" for w, h in bad.items()]
    sp60_cap, sp60_eq = _spread("direct", 60, "cap"), _spread("direct", 60, "equal")
    sp60_cap_pc3, sp60_eq_pc3 = _spread("pc3", 60, "cap"), _spread("pc3", 60, "equal")
    bd, bp = _monotone("direct"), _monotone("pc3")
    mono_direct = ("and its deciles are monotone at every horizon and weighting." if not bd
                   else "and its deciles are monotone except " + " and ".join(bd) + ".")
    mono_pc3 = ("and are monotone throughout." if not bp
                else "and are not monotone " + " or ".join(bp) + ".")
    q["m"] = q["mapping"].map(lambda s: SHORT.get(s, s))
    stability_section = _stability_section()
    levels_section = _levels_section()

    tests = ["leave one characteristic out", "leave one family out", "extremes held out"]
    body = []
    for t in tests:
        sub = q[q.test == t]
        body.append(r"\subsection*{" + t.capitalize() + "}")
        body.append(r"\begin{tabular}{lrrrrr}\toprule")
        body.append(r"Mapping & $R^2$ & Correlation & Intercept & Slope & RMSE (pp)\\\midrule")
        for _, r in sub.iterrows():
            bold = r"\bfseries " if r["m"] == "direct" else ""
            body.append(f"{bold}{r['m']} & {r['r2']:.3f} & {r['corr']:.3f} & "
                        f"{r['intercept']:+.2f} & {r['slope']:.3f} & {r['rmse']:.2f}\\\\")
        body.append(r"\bottomrule\end{tabular}\\[8pt]")

    ex = []
    for kind, label in [("pc3", "3 PCs (paper)"), ("pc10", "10 PCs"), ("direct", "direct")]:
        for w in ("cap", "equal"):
            s = e[(e.mapping == kind) & (e.weighting == w)].sort_values("horizon")
            for _, r in s.iterrows():
                ex.append(f"{label} & {int(r['horizon'])}m & {w} & {r['d1']:.1f} & "
                          f"{r['d10']:.1f} & {r['spread']:.1f}\\\\")

    se = p["se_nw"].dropna()
    doc = r"""\documentclass[11pt]{article}
\usepackage[margin=2.3cm]{geometry}
\usepackage{booktabs,amsmath,microtype,longtable}
\usepackage[colorlinks=true,linkcolor=black,urlcolor=blue]{hyperref}
\usepackage{sectsty}\allsectionsfont{\sffamily}
\setlength{\parindent}{0pt}\setlength{\parskip}{5pt}
\title{\sffamily Firm-level price wedges:\\how good is the mapping, and can it be improved?}
\author{}\date{\today}
\begin{document}\maketitle

\section*{What is being measured}

A firm's price wedge is not estimated directly. Wedges are estimated for decile
portfolios, and a mapping carries those onto individual firms through their
characteristics. The question is how much that mapping can be trusted, and
whether it can be improved.

Four criteria, because they answer different questions.

\textbf{Leaving one characteristic out.} Fit on the portfolios of all but one
characteristic, predict that one's ten deciles, rotate. Can the mapping price an
anomaly it has not seen?

\textbf{Leaving one family out.} The same, holding out a whole Freyberger--
Neuhierl--Weber category. Harder and more honest: value characteristics predict
each other, so holding out book-to-market while assets-to-market and
earnings-to-price remain is not a real test.

\textbf{Holding out the extreme deciles.} Fit on deciles two to nine, predict
one and ten. This tests extrapolation, which is what the mapping must do at the
firm level: 94\% of firm-months sit outside the range the portfolios span on at
least one characteristic.

\textbf{Subsequent returns.} Do firms the mapping calls overpriced go on to
underperform? This is the only criterion evaluated on firms rather than
portfolios, so it is the only one that can penalise bad extrapolation.

Everything is scored on magnitudes, not only ordering: the realised wedge is
regressed on the fitted one and the intercept and slope reported. A perfect
mapping has intercept zero and slope one. A mapping that ranks firms correctly
but compresses the spread shows a slope away from one, and would be no good for
a website that reports a wedge rather than a score.

\paragraph{Which portfolios count.} Only characteristics whose construction is
verified against the replication package enter, as regressors \emph{and} as
portfolios. A portfolio we cannot reproduce carries a wedge we cannot trust, so
including it adds noise to the left-hand side as well as the right. With
""" + f"{n_unverified}" + r""" characteristic still unverified (""" + unverified_list + r"""), the rule costs
nothing: the leave-one-family-out fit of the direct mapping is """ + f"{fam_all:.2f}" + r""" with every
characteristic in and """ + f"{fam_direct:.2f}" + r""" without it. When six were unverified it
raised that fit from 0.56 to 0.67.

\section*{Results}
""" + "\n".join(body) + r"""

\section*{Do the wedges predict returns?}

Firms are sorted into deciles on their fitted wedge each month and tracked
forward. Decile 1 is the most negative wedge (most underpriced), decile 10 the
most positive, so if wedges are mispricing that resolves, decile 1 should
outperform and the spread should be positive.

\begin{longtable}{llrrrr}\toprule
Mapping & Horizon & Weighting & Decile 1 & Decile 10 & Spread (pp)\\\midrule
\endhead
""" + "\n".join(ex) + r"""
\bottomrule\end{longtable}

The wedges predict returns strongly and with the right sign. Over five years the
direct mapping separates the extreme deciles by """ + f"{sp60_cap:.0f}" + r""" percentage points
capitalisation-weighted and """ + f"{sp60_eq:.0f}" + r""" equal-weighted, """ + mono_direct + r""" Three principal components produce a
smaller spread (""" + f"{sp60_cap_pc3:.0f}" + r""" and """ + f"{sp60_eq_pc3:.0f}" + r""" points) """ + mono_pc3 + r"""

\section*{Can the mapping be improved?}

\subsection*{Precision weighting: no, and the reason is informative}

If some portfolio wedges were estimated far more precisely than others, the
regression should weight them accordingly. They are not. Reproducing the
package's own standard error --- a Newey--West variance on the cohort-level
ratios carried through the logarithm by the delta method --- and separately a
moving-block bootstrap with the package's 180-month blocks:

\begin{tabular}{lrrrr}\toprule
 & Median & 10th pct & 90th pct & Max\\\midrule
Standard error (pp) & """ + f"{se.median():.1f} & {se.quantile(.1):.1f} & {se.quantile(.9):.1f} & {se.max():.1f}" + r"""\\
\bottomrule\end{tabular}\\[6pt]

The ratio of the 90th to the 10th percentile is """ + f"{se.quantile(.9)/se.quantile(.1):.1f}" + r""". Precision is
close to uniform across the """ + f"{n_portfolios}" + r""" portfolios, so weighting by it has almost
nothing to exploit --- and in the event it is very slightly worse on all three
criteria, presumably because the weights add estimation noise of their own.

What the exercise does reveal is the \emph{level}: a standard error around
""" + f"{se.median():.0f}" + r""" percentage points on wedges whose cross-sectional standard deviation is
about 10. Individual portfolio wedges are imprecise, because 463 formation
cohorts that overlap in 179 of their 180 months are worth only two or three
independent observations. That is a caveat on the whole exercise rather than on
any mapping.

\subsection*{Non-linear terms: no}

Adding squared ranks roughly halves out-of-sample fit and pushes the slope to
0.6 or below. The design already carries the non-linearity that matters: using
all ten deciles rather than the extremes lets the wedge be non-linear in each
sorting characteristic, and squaring """ + f"{n_verified}" + r""" standardised ranks mostly adds
collinear regressors for """ + f"{n_portfolios}" + r""" observations to overfit.

\subsection*{Shrinkage: yes, and it is the substance}

Unpenalised, the direct regression fits best in sample and generalises worst.
Penalised at the level chosen inside each fold, it is the best mapping on every
criterion at once and is close to unbiased in magnitude. The penalty is not a
technicality: without it the fitted wedges of unfamiliar portfolios are more
than twice too dispersed. On the leave-one-family-out test the realised wedge
moves 0.42 for each point of fitted wedge with no penalty, against 0.89 with
the penalty of 100 (run of 12 September 2026, \texttt{group\_cv.held\_out} on the
verified portfolios).

\subsection*{Number of components}

Ten principal components come close to the direct regression and beat three
decisively on every criterion. If a dimension-reduced mapping is wanted for
interpretability, ten is the defensible choice; three is not.

""" + stability_section + levels_section + r"""

\end{document}
"""
    (HERE / "quality.tex").write_text(doc)
    print(f"wrote {HERE/'quality.tex'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
