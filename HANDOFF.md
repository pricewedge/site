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

    build_panel.py        pull and build the 57-characteristic panel
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
