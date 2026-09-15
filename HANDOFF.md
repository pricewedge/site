# State, and what to do next

Written so this can be picked up cold. Everything below is on disk; nothing
important lives only in a conversation.

## Where the replication stands

56 of 57 characteristics verified against the package's own decile weights
(`raw/validation.json`, threshold 0.85). Table 1 wedges reproduce to 0.79
percentage points on the long leg and 0.71 on the short, correlations 0.996 and
0.997. `pipeline/validation-latest.txt` is the last full run.

The one holdout is aPM at 0.78. Its parent PM verifies at 0.97. The adjustment
subtracts an equal-weighted industry mean of PM, and that mean is dominated by
firms with sales near zero, whose PM runs to thousands in absolute value.
Which of those firms carry a PM value differs slightly between our
CRSP/Compustat vintage and the paper's, and each such difference moves a whole
industry-month. The paper's own panel shows the same fragility: recomputing
its cell means from its own PM reproduces its aPM exactly for 16% of
firm-months, against 43% for aSAT and 58% for aSIZE.

## Read these first

* `OVERNIGHT.md` -- the running report, all phases, in order.
* `pipeline/doc/signals.yaml` -- per characteristic: the formula in full, every
  convention, and every rejected alternative with the score it got. 122 of them.
* `pipeline/doc/discrepancies.yaml` -- 24 places the paper's documentation and
  its data disagree, graded A to E.
* `pipeline/doc/signals.pdf`, `quality.pdf` -- the same, typeset.

Do not re-try anything listed under `tried:` in signals.yaml. That is what it
is for.

## What the paper's own panels settled (12 September 2026)

Andrea Tamoni shared the paper's firm-month panels, one `.mat` file per
characteristic plus the raw inputs, in
`Dropbox/Papers/Build-up-vs-Resolution/ReplicationPackage/t_by_n/`.
`pipeline/pwsite/tbyn.py` reads them, `pipeline/compare_panels.py` diffs every
characteristic against ours at the firm-month level, and
`pipeline/compare_allocation.py` diffs decile membership. Comparing against
the panels, rather than against decile weights, pinned down the five
constructions that had resisted everything:

* **DTO** is the last trading day's turnover less the mean of its own previous
  180 trading days. There is no market adjustment, no Nasdaq scaling and no
  median. Spearman 0.998 against the panel.
* **SUV** is the last trading day's standardised residual from a regression of
  daily volume on the day's positive and negative return, estimated on that
  calendar month's trading days, the residual divided by the residual standard
  deviation with n - 1. The ratio of the panel's values to ours is 1.0000.
* **TNOVR** is the previous month's volume over the current month's shares.
  Spearman 1.0000.
* **SPREAD** is built day by day: a trading day contributes its high-low
  range if it has one and its quoted spread otherwise, and the month is the
  mean over those days with no minimum. Every firm-month in the four years
  tested agrees with the panel within 1%, with nothing missing.
* The **industry adjustment** uses 27 groups of SIC codes that are not
  Fama-French 48. They were recovered from the panels: within a month the value
  less its adjusted value is one constant per industry, and grouping SIC codes
  by that constant across months gives 27 groups that never contradict one
  another (`raw/their_industry_table.json`, `pwsite.industry.learned_industry`).
  The SIC code is CRSP's name-history code (`crsp.msenames`), which reproduces
  the panel's own siccd for 99.5% of firm-months.

Both DTO and SUV are the last day's value of a daily series, which is the
signature of a daily file collapsed to monthly by keeping the last
observation. `pipeline/pwsite/lastday.py` builds them from `raw/daily_raw/`,
which now runs 1962-2025.

Four smaller conventions came out of the same comparison. BETA_d is estimated
over the firm's last 249 trading days, not calendar months (84% of
firm-months within 1% of the panel, rank correlation 0.9996; 250 days or
twelve calendar months halve that). sdDVOL leaves
zero-volume days out (a zero-volume day taken as ln(1 + 0) = 0 had inflated
the dispersion for 27% of firm-months). IDIOV divides the residual sum of
squares by n - 1, not n - 4. DP differs from the panel for three quarters of
the non-zero firm-months by a factor spread from 0.87 to 1.10, which no
formula variant narrows; the dividend series itself differs, most plausibly
because the paper takes dividends from CRSP's distribution events rather
than from ret - retx. It is verified at the sort level and is the best
remaining target.

One error was ours: PM, PCM and IPM were infinite where sales were zero, and
one infinity inside an industry mean wiped out every firm in that
industry-month. That alone took aPM from 0.37 to 0.78.

What remains different is data vintage. Against the panels, 2 to 7% of
firm-months differ for a typical characteristic, flat across decades, with our
coverage 1 to 3% higher. `pipeline/panel-agreement-latest.txt` is the full
firm-month comparison and `raw/validation.json` the sort-level agreement.

## The two panels, and a trap

`raw/full_panel.parquet` stops in December 2017 and is what every validation
runs on. The site's current panel is `raw/full_panel_today.parquet`, built by
`build_panel.py --end 2025-12-31 --suffix _today` from the `_today` caches,
and every current-tag script needs `--panel ../raw/full_panel_today.parquet
--factors ../raw/ff_monthly_today.parquet --end 202512`. Without those flags
`--tag current` silently re-runs the 2017 panel (that happened on 12
September; the current outputs were regenerated correctly on 13 September:
559 cohorts, lambda 3.5311, 4,904,234 firm-months).

## Which sample for the wedges (13 September 2026)

`stability.py current` re-estimates all 570 decile wedges on subsamples of
the 559 formation cohorts, re-solving lambda on each. The cross-section is
not stable: the two halves (1964-87 and 1988-2011) correlate 0.45 where two
halves of a constant cross-section would correlate about 0.68 given their
sampling noise; 13 of 56 long-short spreads change sign, the value ratios
(E2P, A2ME, D2P) reverse and momentum triples; the 1980-95 third is nearly
flat and unrelated to the rest (0.17). Adding the 2003-2011 cohorts to the
paper's window changes almost nothing (0.99). Refitting the firm mapping on
either half keeps the firm ranking (correlation 0.92-0.96 with the
full-sample firm wedges) but moves magnitudes by 8-12 pp, a third to two
fifths of firms by more than 10 pp. Recommendation recorded there and in the
chat of 13 September: headline on the full available sample, show the
half-sample sensitivity, do not switch to a later window.

## Levels and weighting (14 September 2026)

Correlation is not the test for firm-level wedges; levels are. `realised_levels.py`
sorts firms on a candidate firm wedge, holds the deciles fifteen years, and
regresses the realised wedge on the fitted one. Findings, all in `doc/quality.pdf`:

* Our portfolio profiles were capitalisation-weighted mean ranks; the paper's
  `chars.mat` uses equal-weighted means (`nanmean`). That one choice moves every
  firm-level wedge by 10-27 pp. With equal-weighted profiles our PC3 reproduces
  `PWshare.mat` to 1.2 pp in level (slope 1.04); the ~1 pp residual is the
  log-bias correction, which enters once, on the portfolio wedges.
* The realised wedge of the equal-weighted universe is -24.6 pp (value-weighted
  0 by calibration). The published firm wedges average -6.9 pp and fail the
  level test (EW slope 0.64, intercept -18 pp): equal-weighted profiles hand
  the average firm the big-firm wedge. Our cap-weighted mapping has the level
  right and 30% too much dispersion. Fitting on value- and equal-weighted
  deciles together, each with its own profiles, passes (slope 0.86-0.88,
  intercept near zero equal-weighted).
* `portfolio_wedges.py --weighting equal` and `portfolio_profiles.py --weighting
  equal` build the equal-weighted objects (tag suffix `_ew`).

The report's Recommendations section lists what to change in the method; the
mapping default in the pipeline is still value-weighted wedges with
value-weighted profiles until that discussion is settled.

## The site specification (15 September 2026)

Three decisions are recorded in `pipeline/doc/decisions.pdf`, with the
evidence: (A) the firm-level number is the equal-weighted realised wedge of
firms with the firm's profile, with the cap-weighted mean pinned to the market
wedge (candidate 3, the stacked mapping); (B) signals as their original papers
define them (Sloan accruals; monthly SUV and DTO per Garfinkel and FNW; FF48
equal-weighted industry means with at least three firms; aPM dropped); (C) the
full available sample, no sample options on the site. Sources are in
`Dropbox/.../Website/Literature/` (indexed in `_index.md`).

Build and evaluate the site series with:

    build_panel.py --end 2025-12-31 --suffix _today --spec site
    A="--panel ../raw/full_panel_today_site.parquet --factors ../raw/ff_monthly_today.parquet --end 202512"
    portfolio_wedges.py --tag site $A --refresh;  portfolio_wedges.py --tag site $A --weighting equal --refresh
    portfolio_profiles.py --tag site $A;          portfolio_profiles.py --tag site $A --weighting equal
    firm_wedges.py --tag site --mapping stacked
    realised_levels.py --tag site $A;  mapping_quality.py --tag site;  mapping_expost.py --tag site $A
    group_cv.py site;  stability.py site

`pwsite/garfinkel.py` holds the monthly SUV and DTO (the site's spec);
`pwsite/lastday.py` holds what the paper's data does (last trading day).
`pwsite/characteristics.ACCRUALS` switches the depreciation sign.

## The firm-level mapping

Settled: regress portfolio wedges on portfolio characteristic ranks, ridge
penalty 100 on standardised regressors, verified characteristics only, all ten
deciles. Beats three principal components on every criterion. See
`pipeline/mapping_quality.py` and `doc/quality.pdf`.

Two things tested and rejected: precision weighting (the standard errors are
nearly uniform, a 1.2-fold spread, so there is nothing to exploit) and squared
ranks (halves out-of-sample fit).

Choose the penalty by the strict out-of-sample R-squared, 1 - SSE/SST, on
leave-one-family-out folds. Not the squared correlation, which is blind to
scaling: plain OLS scores 0.32 on that and -0.06 on the strict measure.

## Known ceiling

Bootstrapping the cohorts in 180-month blocks: 99% of a wedge's standard error
is common to all portfolios and cancels in a cross-sectional regression, which
leaves 3.2 percentage points of usable noise against a cross-sectional
dispersion of 9.8. The best attainable out-of-sample R-squared is therefore
about 0.895. The current mapping reaches 0.62 on the 56 verified
characteristics (0.63 with the penalty chosen inside each fold).

## Scripts

    build_panel.py        pull and build the 57-characteristic panel (to 2017);
                          --end 2025-12-31 --suffix _today builds the site's current panel
    stability.py          wedges on cohort subsamples: is the cross-section stable, which sample to use
    realised_levels.py    the level test: do firms realise the wedge they are assigned
    compare_panels.py     diff every characteristic against the paper's own panels
    compare_allocation.py diff decile membership against the paper's own sorts
    pwsite/lastday.py     DTO and SUV from the daily file (last trading day)
    pwsite/beta_daily.py  BETA_d over the firm's last 249 trading days
    pwsite/tbyn.py        read the paper's t_by_n panels
    validate.py           score everything against the package and Table 1
    harness.py            score one candidate series, fast
    portfolio_wedges.py   sorts, lambda calibration, wedges for all deciles
    portfolio_profiles.py characteristic profiles of the 570 portfolios
    firm_wedges.py        evaluate a mapping at individual firms
    mapping_quality.py    the four criteria
    mapping_expost.py     do the wedges predict returns
    doc/build_*.py        regenerate the two documents

`pipeline/.source-path` points at the replication package. WRDS credentials are
in `~/.pgpass`; `WRDS_USERNAME` is exported from `~/.zshrc`.
