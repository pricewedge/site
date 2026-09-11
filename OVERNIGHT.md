# Overnight work plan

Christian's instruction, 2026-09-10 night. Worked top to bottom; each section
is updated in place as results land, so this file is the running report.

## Phase 1 — definitional audit against Chen-Zimmermann and JKP
For every characteristic not matching the package's decile weights above 0.85:
read Chen and Zimmermann's Stata implementation, diff it against ours, test
whether their convention closes the gap, and record anything peculiar about
what Binsbergen et al. appear to have done.

## Phase 2 — portfolio-level price wedges
Reproduce the published ones from the rebuilt panel, then extend to the latest
data CRSP and Compustat allow.

## Phase 3 — firm-level price wedges
Reproduce what the website currently serves, per firm, across the specification
toggles; measure how close.

## Phase 4 — firm-level wedges to today
Using current characteristics.

## Phase 5 — mapping portfolio wedges to firms
Compare the existing approach (principal components) against regressing
portfolio price wedges on portfolio characteristic ranks. Judged on intercepts
and slopes, not only rank correlation: magnitudes matter, not just ordering.

---


# Phase 1 — definitional audit

## Where the rebuild now stands

46 of 57 characteristics reproduce the package's own decile capitalisation
weights above 0.85, up from 40 at the start of the night. On those 46 the price
wedges land 1.79 percentage points from Table 1 on the long leg and 1.04 on the
short, correlations 0.985 and 0.992. Across all 57 it is 3.26 and 1.53.

Five more were fixed tonight, all by reading Chen and Zimmermann's Stata and
diffing the convention rather than guessing:

| characteristic | before | after | what was wrong |
|---|---|---|---|
| RNA | 0.76 | 0.95 | common equity filled with zero in operating liabilities |
| ATO | 0.78 | 0.92 | same |
| dSOUT | 0.88 | 0.97 | CRSP's own cumulative share factor, not one backed out of returns |
| dPIA | 0.78 | 0.87 | an unreported component is no change, not a dropped firm |
| TNOVR | 0.71 | 0.80 | turnover averaged over three months, not one |

The common-equity one is worth stating plainly because it is invisible in the
text. Operating liabilities are total assets less debt, minority interest,
preferred stock and common equity. Fill common equity with zero when it is
missing and operating liabilities become nearly all of total assets, so net
operating assets collapse toward zero -- and ATO and RNA, which divide by them,
explode into the end deciles. Nothing in Appendix Table A.1 or in Freyberger,
Neuhierl and Weber says which fields may be zero-filled.

## The catalogue

Sorted by how well the construction is verified. "weights" is the mean
correlation, across the ten deciles, between our decile capitalisation shares
and the package's own, over 462 formation months. It tests the characteristic
and the sort alone -- not the 241-month tracking, not the discount factor.

| char | weights | PW long | paper | diff | PW short | paper | diff | source |
|---|---|---|---|---|---|---|---|---|
| OA | 0.069 | 28.2 | -11.7 | 39.9 | 14.4 | 13.9 | 0.5 | sloan1996 |
| SUV | 0.080 | -1.1 | -4.8 | 3.7 | -3.3 | 0.3 | 3.6 | garfinkel2009 |
| AOA | 0.087 | 14.6 | -8.3 | 22.9 | 32.4 | 12.8 | 19.6 | bandyopadhyay2010 |
| aPM | 0.298 | -13.1 | -14.8 | 1.7 | 13.4 | 10.6 | 2.8 | soliman2008 |
| DTO | 0.367 | -3.9 | -5.6 | 1.7 | -1.2 | 0.7 | 1.9 | garfinkel2009 |
| aSAT | 0.442 | -14.0 | -10.6 | 3.4 | 1.5 | 0.5 | 1.0 | soliman2008 |
| aBEME | 0.509 | -41.4 | -38.0 | 3.4 | 11.4 | 15.8 | 4.4 | asness2000 |
| TNOVR | 0.797 | -13.5 | -3.4 | 10.1 | 8.2 | 6.1 | 2.1 | datar1998 |
| DP | 0.822 | -30.8 | -29.4 | 1.4 | 1.1 | 3.3 | 2.2 | litzenberger1979 |
| PM | 0.824 | 9.7 | 11.7 | 2.0 | -16.4 | -15.6 | 0.8 | soliman2008 |
| aSIZE | 0.843 | -28.4 | -15.3 | 13.1 | 7.3 | 7.2 | 0.1 | asness2000 |
| OL | 0.854 | -11.0 | -11.8 | 0.8 | 6.0 | 7.7 | 1.7 | novy2011 |
| PROF | 0.872 | 0.1 | 1.4 | 1.3 | -14.9 | -12.5 | 2.4 | ball2015 |
| dPIA | 0.873 | -19.6 | -19.1 | 0.5 | 4.9 | 5.3 | 0.4 | lyandres2008 |
| sdDVOL | 0.874 | -32.4 | -23.5 | 8.9 | 5.2 | 5.0 | 0.2 | chordia2001 |
| CAT | 0.884 | -3.1 | -4.7 | 1.6 | 3.2 | 7.7 | 4.5 | haugen1996 |
| IPM | 0.889 | 14.0 | 13.7 | 0.3 | -15.9 | -15.8 | 0.1 | - |
| SAT | 0.898 | -8.8 | -10.2 | 1.4 | 4.9 | 8.7 | 3.8 | soliman2008 |
| S2C | 0.907 | -17.6 | -17.5 | 0.1 | 3.8 | 4.8 | 1.0 | ou1989 |
| NOA | 0.917 | 7.1 | 8.0 | 0.9 | 8.2 | 8.8 | 0.6 | hirshleifer2004 |
| dSO | 0.922 | -26.5 | -26.3 | 0.2 | 7.3 | 8.0 | 0.7 | fama2008 |
| ATO | 0.923 | 6.3 | 9.0 | 2.7 | 4.8 | 4.5 | 0.3 | soliman2008 |
| IVC | 0.923 | -14.5 | -16.2 | 1.7 | -5.7 | -6.1 | 0.4 | thomas2002 |
| C2A | 0.927 | -18.4 | -17.4 | 1.0 | 8.9 | 9.5 | 0.6 | palazzo2012 |
| S2P | 0.927 | -27.1 | -32.8 | 5.7 | 20.5 | 18.9 | 1.6 | lewellen2015 |
| ROIC | 0.930 | 11.1 | 10.6 | 0.5 | -17.8 | -18.0 | 0.2 | brown2007 |
| PCM | 0.931 | 5.7 | 6.2 | 0.5 | -20.5 | -18.8 | 1.7 | gorodnichenko2016 |
| IDIOV | 0.933 | -6.6 | -1.5 | 5.1 | -6.8 | -7.7 | 0.9 | ang2006 |
| dCEQ | 0.935 | -11.8 | -8.8 | 3.0 | 11.6 | 12.6 | 1.0 | richardson2005 |
| SPREAD | 0.935 | -21.9 | -13.4 | 8.5 | 3.2 | -0.3 | 3.5 | chung2014 |
| SG | 0.937 | -14.1 | -14.5 | 0.4 | 4.2 | 4.4 | 0.2 | lakonishok1994 |
| BETA_d | 0.940 | -23.0 | -21.3 | 1.7 | 10.7 | 10.6 | 0.1 | lewellen2006 |
| ROA | 0.940 | 15.4 | 14.8 | 0.6 | -10.1 | -11.6 | 1.5 | balakrishnan2010 |
| D2P | 0.944 | -8.3 | -4.9 | 3.4 | 18.1 | 17.0 | 1.1 | litzenberger1979 |
| RNA | 0.946 | -3.9 | -3.7 | 0.2 | 12.6 | 12.1 | 0.5 | soliman2008 |
| I2A | 0.946 | -13.4 | -13.4 | 0.0 | 5.6 | 6.6 | 1.0 | - |
| dGS | 0.946 | -10.7 | -10.4 | 0.3 | -0.2 | -0.4 | 0.2 | abarbanell1997 |
| C2D | 0.946 | 11.1 | 11.5 | 0.4 | -3.3 | -0.5 | 2.8 | ou1989 |
| EPS | 0.949 | -6.5 | -6.0 | 0.5 | -9.0 | -8.1 | 0.9 | basu1977 |
| ROE | 0.949 | 10.1 | 10.0 | 0.1 | -16.3 | -15.5 | 0.8 | haugen1996 |
| TAN | 0.955 | 12.4 | 13.9 | 1.5 | -6.0 | -4.8 | 1.2 | hahn2009 |
| A2ME | 0.955 | -12.9 | -11.3 | 1.6 | 17.6 | 17.1 | 0.5 | bhandari1988 |
| sdTURN | 0.959 | -1.3 | 1.3 | 2.6 | -1.7 | -2.5 | 0.8 | chordia2001 |
| Q | 0.960 | -35.7 | -31.8 | 3.9 | 17.8 | 17.3 | 0.5 | - |
| RETVOL | 0.963 | -16.0 | -11.0 | 5.0 | -0.9 | -2.6 | 1.7 | ang2006 |
| MAXRET | 0.963 | -13.9 | -10.4 | 3.5 | -4.7 | -5.6 | 0.9 | bali2011 |
| ROC | 0.965 | -32.0 | -28.1 | 3.9 | 16.4 | 15.4 | 1.0 | chandrashekar2009 |
| R_12_7 | 0.968 | 5.2 | 4.9 | 0.3 | -18.4 | -19.0 | 0.6 | novy2012 |
| E2P | 0.968 | -25.1 | -24.2 | 0.9 | 8.0 | 6.1 | 1.9 | basu1983 |
| BEME | 0.968 | -36.4 | -34.1 | 2.3 | 19.2 | 19.5 | 0.3 | - |
| R_6_2 | 0.969 | 0.7 | 1.0 | 0.3 | -13.7 | -13.6 | 0.1 | jegadeesh1993 |
| R_2_1 | 0.970 | -7.6 | -7.7 | 0.1 | -1.3 | -1.1 | 0.2 | jegadeesh1990 |
| dSOUT | 0.970 | -28.9 | -27.9 | 1.0 | 10.1 | 10.7 | 0.6 | pontiff2008 |
| AT | 0.972 | -16.1 | -18.6 | 2.5 | 2.4 | 2.9 | 0.5 | gandhi2015 |
| R_12_2 | 0.973 | 5.0 | 4.8 | 0.2 | -18.9 | -20.5 | 1.6 | fama1996 |
| R_36_13 | 0.975 | -26.8 | -26.8 | 0.0 | 18.1 | 18.9 | 0.8 | de1985 |
| SIZE | 0.992 | -37.9 | -38.6 | 0.7 | 7.0 | 7.3 | 0.3 | fama1992 |

## What is peculiar, characteristic by characteristic

**The five momentum sorts are stored one month early.** R_12_2 holds the return
from eleven months ago to one month ago, and the sort's own lag then produces
the stated twelve-to-two window. Storing the stated window directly drops
agreement from 0.97 to 0.65, and for R_2_1, where a one-month error leaves
nothing in common, from 0.97 to 0.11. This is the single largest departure from
the published wording and it affects five characteristics.

**Market equity is contemporaneous, not December of the prior year.** FNW say
December t-1 explicitly for A2ME, E2P and BEME and "as of December" for S2P.
Every market-value ratio disagrees, and not marginally: A2ME 0.95 against 0.70,
E2P 0.97 against 0.69, Q 0.96 against 0.61, S2P 0.93 against 0.72, D2P 0.94
against 0.71, SIZE 0.99 against 0.97.

**SPREAD is the high-low range, not the quoted spread**, although FNW cite
Chung and Zhang (2014), whose estimator is the quoted bid-ask spread. CRSP
carries quotes for 9% of daily rows in the 1960s and 53% in the 1980s, so the
quoted version cannot be computed over this sample at all: it agrees at 0.02
against 0.94 for the range.

**BETA_d is estimated over twelve months of daily data, not one.** 0.35 at one
month, 0.62 at six, 0.94 at twelve, 0.63 at twenty-four. IDIOV is the opposite
and is emphatically monthly, 0.93 against 0.58 at twelve -- and Jensen, Kelly
and Pedersen corroborate that, carrying `ivol_ff3_21d` at a 21-day window.

**sdDVOL is the dispersion of log dollar volume.** In levels it measures scale
rather than variability: 0.06 against 0.87.

**ROIC subtracts cash from invested capital** though Table A.1 words it as a
sum: 0.64 against 0.93.

**TAN requires every component present.** Zero-filling reads as "this firm holds
no tangible assets" and sends firms with incomplete filings to the bottom
decile: 0.48 against 0.96.

**DP does not restate dividends for splits.** Restating is the more coherent
calculation and agrees worse, 0.74 against 0.82. Nor does it come from CRSP's
distributions file, which is the more principled source and agrees far worse
still, 0.35.

## Where agreement on the sort does not buy agreement on the wedge

Four characteristics reproduce the decile weights well and the wedge badly:
aSIZE (weights 0.84, long leg off by 13.1 points), TNOVR (0.80, 10.1), sdDVOL
(0.87, 8.9) and SPREAD (0.94, 8.5). Decile membership can be almost right while
the wedge is not, because the wedge depends on fifteen years of subsequent cash
flows and is sensitive to exactly which firms sit in the tails. Agreement on
weights is necessary, not sufficient.

## What resisted everything

**OA and AOA (0.07, 0.09).** Around thirty accrual definitions were tried:
Sloan's grouping and the literal reading of Table A.1; changes in net operating
assets; with and without depreciation; scaled by lagged, current and average
total assets, by sales and by absolute earnings; with income taxes payable
required, zero-filled, or dropped; and the cash-flow-statement form, net income
less cash flow from operations. None reaches 0.30. Outliers are not the cause --
winsorising monthly at 1/99, or discarding firms whose accruals exceed their
assets, moves the answer by less than 0.01 -- and neither is a timing offset,
since cross-correlating against shifts of the published series shows no peak
where the same test peaks cleanly at zero for BEME.

What does help is somebody else's implementation. JKP's `oaccruals_at` scores
0.28 overall and 0.68 on the long decile against 0.07 here, and reproduces that
decile's share of market capitalisation almost exactly -- 5.48% against a
published 5.30%, where every definition tried here gives about 10%. Their
measure takes accruals from the cash flow statement; building that directly
recovers their long-decile agreement but not their level, so their screens are
doing work beyond the formula. **Recommendation: take `oaccruals_at` from the
JKP library rather than keep guessing, and do not publish OA or AOA until the
long leg, currently 40 points from the paper, is understood.**

**SUV (0.08).** Garfinkel (2009) estimates the volume-on-returns regression
over a benchmark window and applies it out of sample. No window from one month
to twenty-four improves on the within-month fit, in levels or in logs. Neither
Chen and Zimmermann nor JKP carry a Garfinkel signal, so there is no third
implementation to compare against.

**DTO (0.37).** Its 180-trading-day median is not a moment of any month, so it
cannot come out of the server-side aggregation the other eight daily
characteristics use. It is approximated from a rolling window of monthly means,
and that approximation is the likely cause rather than any definitional
question.

**aBEME (0.51), aSAT (0.44), aPM (0.30), aSIZE (0.84).** The industry
adjustment. Exhaustively tested and not closed: ten classification schemes
(one-digit SIC, Fama-French 5, 10, 12, 17, 30, 38, 48 and 49, and a firm's
modal SIC), Compustat's historical SIC with and without CRSP fallback, eight
adjustment operations (demean, demedian, divide by the industry mean, log
ratio, standardise, percentile rank within industry, cross-sectional rank less
the industry mean rank, leave-one-out), equal against capitalisation weighting,
industry means taken over all of CRSP against ordinary common shares against
NYSE firms only, and Asness, Porter and Stevens's aggregate ratio -- industry
book over industry market rather than the mean of firm ratios. Plain
equal-weighted demeaning within Fama-French 48 is the best of them, and it is
not close enough. Note that aBEME fails at 0.51 while its parent BEME reaches
0.97, so the adjustment itself is the problem, not the input.

**PM (0.82) and DP (0.82)** have no better candidate. Chen and Zimmermann's
profit margin, net income over revenue, is much worse at 0.39.


# Phase 2 — portfolio-level price wedges

## Reproduced

`portfolio_wedges.py` runs the sorts, calibrates the market price of risk, and
reports all ten deciles rather than the two legs Table 1 prints. Two things
make it self-contained rather than borrowed from the package:

**The price of risk is re-solved, not carried over.** It is whatever makes the
market's own price wedge exactly zero. On the paper's sample that is 3.3641
against the package's 3.3244 -- the 1.2% gap is our market portfolio being our
universe rather than theirs. Using the package's value instead moves the mean
long-leg error from +1.27 points to -0.02 and the short leg from +0.34 to
-1.04, so neither choice dominates.

**Signs come from our own one-month alphas.** The paper signs each
characteristic so its long-short earns a positive one-month alpha. Taking that
from our returns rather than the package's stored `alpha1` agrees for 55 of 57.
The two that differ, dGS and aPM, have alphas of 0.0013 and 0.0001 a month --
aPM's is indistinguishable from zero, so which leg is "long" is arbitrary, and
that is worth knowing before publishing a signed wedge for it.

Against Table 1, self-signed: 2.05 points mean absolute error on the long leg
and 1.45 on the short over the 46 verified characteristics, correlations 0.979
and 0.983. The decile profiles are cleanly monotone where they should be --
BEME runs -35.5 to +20.2 across its ten deciles, R_12_2 +5.9 to -17.9.

## Brought forward

CRSP now runs to December 2025 and Compustat to August 2026. The whole panel
rebuilds on that: 57 of 57 characteristics, 4.9 million firm-months.

The binding constraint on *portfolio* wedges is the fifteen-year resolution
horizon, not the data: a cohort formed in month t needs 180 months of
subsequent cash flows, so the last formable cohort is **December 2010**. That
gives **559 formation cohorts against the paper's 463**, a 21% increase, and a
recalibrated price of risk of **3.5474**.

Both tables are written to `raw/portfolio_wedges_paper.csv` and
`raw/portfolio_wedges_current.csv`, with all ten deciles, the one-month alpha,
the sign, and the long-short spread.

# Phase 3 — reproducing the firm-level wedges the site serves

`PWshare.mat` holds the paper's own firm-level wedges: 642 months by 24,742
securities for each of eight specifications. Ours, built from scratch through
the same three-principal-component mapping, line up against them like this:

| mapping | overlap | correlation | median per firm | slope | RMSE |
|---|---|---|---|---|---|
| 3 PCs | 638,601 firm-months, 7,858 firms | **0.940** | **0.906** | 0.895 | 12.1 pp |
| FF5 + momentum | same | 0.816 | 0.869 | 0.508 | 32.3 pp |
| direct rank regression | same | 0.768 | 0.789 | 0.525 | 30.6 pp |

The three-PC reconstruction tracks the published series closely and reproduces
its dispersion almost exactly: standard deviation 22.0 points against 21.0.
55% of firms have a per-firm correlation above 0.8 over their own history.

What differs is the level, and the reason is instructive. Equal-weighted, ours
average -17.7 points against a published -8.3. **Capitalisation-weighted, ours
average -5.2 points, against a 570-portfolio mean of -4.3 and a market wedge of
zero.** The published series, capitalisation-weighted, averages +6.3. So the
rebuilt series aggregates back to the portfolio and market levels it was
derived from, and the published one does not. The equal-weighted gap is small
firms, which the mapping pushes to large negative wedges -- which is Phase 5's
subject.

# Phase 4 — firm-level wedges to today

Firm-level wedges now run to **December 2025** for 8,956 firms, in
`raw/firm_wedges_current_{pc3,direct}.parquet`. The mapping is estimated where
portfolio wedges are observable (cohorts through 2010) and evaluated forward,
which is the only honest way to price a firm today.

Coverage is the practical constraint, and it is fixable. Requiring all 57
characteristics leaves **540 firms in December 2025**. Requiring only the 46
whose construction is verified leaves **3,156** -- six times as many, using only
the characteristics we trust:

| completeness rule | firms, latest month | share of the panel |
|---|---|---|
| all 57 | 540 | 19.3% |
| without OA and AOA | 920 | 24.1% |
| the 46 verified above 0.85 | **3,156** | **50.7%** |

**Recommendation: drop the eleven unverified characteristics from the firm-level
mapping.** It costs nothing in fidelity -- they are the ones we cannot
reproduce -- and multiplies coverage of recent years by six. Separately, aPM is
missing for 76% of firm-months in 2024-25 and should be looked at regardless.

# Phase 5 — which mapping, judged on magnitudes

Christian's proposal was to regress portfolio price wedges directly on the
portfolios' characteristic ranks rather than on three principal components of
them, and to judge the result on intercepts and slopes rather than on rank
correlation alone. Both halves of that turn out to matter.

## At the portfolio level the direct regression wins clearly

Every fit is scored by regressing the realised portfolio wedge on the fitted
one. A mapping that orders firms correctly but compresses the spread shows up
as a slope above one; one that overstates magnitudes shows a slope below one.
Out-of-sample means leaving one whole characteristic out and predicting its ten
portfolios -- the relevant test, since a firm's combination of characteristics
is never one of the 570 portfolios.

| mapping | in-sample R² | out-of-sample R² | correlation | intercept | slope | RMSE |
|---|---|---|---|---|---|---|
| 1 PC | 0.391 | 0.376 | 0.613 | -0.11 | 0.973 | 8.44 pp |
| **3 PCs (the paper's)** | 0.560 | **0.529** | 0.727 | -0.20 | 0.951 | 7.34 pp |
| 5 PCs | 0.631 | 0.578 | 0.760 | -0.33 | 0.919 | 6.98 pp |
| 10 PCs | 0.735 | 0.692 | 0.832 | -0.24 | 0.931 | 5.96 pp |
| FF5 + momentum | 0.644 | 0.623 | 0.789 | -0.11 | 0.976 | 6.56 pp |
| direct, unpenalised | 0.810 | 0.619 | 0.787 | -0.87 | 0.752 | 7.16 pp |
| **direct, penalised** | — | **0.724** | **0.851** | **+0.04** | **0.994** | **5.62 pp** |

Unpenalised, the direct regression fits best in sample and generalises worst:
57 regressors on 570 portfolios overfits, and its out-of-sample slope of 0.752
means it **overstates how mispriced an unfamiliar portfolio is by a third**.
Penalised at the level that maximises out-of-sample fit, the same regression
becomes the best mapping available on every criterion at once: it explains
0.724 of the variation against 0.529 for three principal components, cuts the
error from 7.34 to 5.62 percentage points, and is essentially unbiased in
magnitude -- intercept 0.04, slope 0.994 where perfection is 0 and 1.

On the extreme deciles alone, the ones that matter most, it reaches R² 0.804
with a slope of 0.953.

So: **Christian's approach is right, and the shrinkage is what makes it right.**
Three principal components are not merely less accurate, they discard 20% of
the explainable variation and leave 30% more error.

## At the firm level the picture reverses, and the reason is the real finding

The same direct mapping, evaluated at individual firms, correlates only 0.768
with the published series where three components reach 0.940, and produces
firm wedges averaging -32 points equal-weighted.

This is not a defect of the regression. It is a property of the exercise:

* Across the 570 portfolios, a characteristic's percentile rank has a median
  standard deviation of **0.077**. Portfolios are averages of hundreds of
  firms, so idiosyncratic rank variation averages away and the design points
  barely move.
* Across individual firms the same ranks have a median standard deviation of
  **0.271** -- three and a half times wider, and up to eight times for R_2_1,
  dGS and R_6_2.
* **94.1% of firm-months sit outside the range of the 570 portfolios on at
  least one characteristic.**

Going from portfolio wedges to firm wedges is therefore almost entirely
extrapolation, and the more flexible the mapping the further it extrapolates.
Three principal components behave better at the firm level precisely because
they are restricted to the three directions in which portfolios actually vary.

Two consequences worth taking seriously:

1. **Firm-level magnitudes are extrapolations and should be presented as such.**
   The ordering is well identified; the level for any individual small firm is
   not. Capitalisation-weighted the wedges aggregate correctly, so the
   aggregate and the large-firm numbers are trustworthy in a way the tails are
   not.
2. **The best portfolio-level mapping is not the best firm-level mapping.** If
   the site's purpose is per-firm numbers, three components remain defensible.
   If the purpose is to measure mispricing at the portfolio level -- which is
   what the paper actually estimates -- the penalised direct regression is
   strictly better and should be what the paper reports.

A natural way to have both: fit the penalised direct regression, and state the
firm-level wedge together with the share of the firm's characteristics that lie
inside the portfolio range, so a reader can see when a number is interpolated
and when it is not.


# Cross-check against Jensen, Kelly and Pedersen

Their library on WRDS carries an independently built version of many of the
same quantities, which gives a second opinion that owes nothing to the
replication package. Comparing 39 pairs on Spearman rank correlation over 3.3
million overlapping firm-months:

**Nine agree essentially perfectly** -- SIZE, RETVOL, MAXRET, dSOUT, R_12_2,
R_6_2 (1.000), R_2_1 (0.999), IDIOV (0.997), AT (0.994) -- and a further six
above 0.95: S2P, A2ME, OL, D2P, BEME, TNOVR. These are independent confirmation
that our constructions are right, and they include the two that were *changed*
tonight on the package's evidence: dSOUT matches JKP exactly after the share-
factor fix, and TNOVR reaches 0.94 after the three-month window.

**OA and AOA fail here too** -- 0.22 and -0.05 against their `oaccruals_at`,
the lowest of all 39. Three independent sources now agree that our accruals are
wrong: the package's decile weights, JKP's own series, and the fact that JKP's
series scores four times better against the package than ours does.

**The rest of the low correlations are definitional choices rather than
errors, and should not be read as red flags.** Where our construction is
already verified above 0.85 against the package, a disagreement with JKP means
the two libraries made different choices, not that ours is broken:

* BETA_d (0.35) -- ours is a twelve-month Dimson beta, theirs a 21-day one. The
  twelve-month window is what the package's decile weights require (0.94
  against 0.35 at one month).
* sdTURN (-0.11) and sdDVOL (0.74) -- ours are one month of daily data as
  Appendix A.1 specifies, theirs 126-day. Ours verify at 0.96 and 0.87.
* dSO (0.53) -- ours is Compustat share growth, theirs CRSP's. Ours verifies at
  0.92.
* Q against `at_me` (-0.85) -- these are near-reciprocal by construction, so a
  strong negative correlation is the expected result.
* PM against `ope_be` (0.60) -- not the same quantity; JKP carry no profit
  margin in Soliman's sense.

Median absolute agreement across the 39 is 0.83. Written to
`raw/jkp_comparison.csv`.
