# State, and what to do next

Written so this can be picked up cold. Everything below is on disk; nothing
important lives only in a conversation.

## Where the replication stands

51 of 57 characteristics verified against the package's own decile weights
(`raw/validation.json`, threshold 0.85). Table 1 wedges reproduce to 1.20
percentage points on the long leg and 0.77 on the short, correlations 0.985 and
0.996. `pipeline/validation-latest.txt` is the last full run.

Six remain: SUV (0.07), aPM (0.28), DTO (0.36), aSAT (0.45), aBEME (0.51),
TNOVR (0.79).

## Read these first

* `OVERNIGHT.md` -- the running report, all phases, in order.
* `pipeline/doc/signals.yaml` -- per characteristic: the formula in full, every
  convention, and every rejected alternative with the score it got. 74 of them.
* `pipeline/doc/discrepancies.yaml` -- 20 places the paper's documentation and
  its data disagree, graded A to E.
* `pipeline/doc/signals.pdf`, `quality.pdf` -- the same, typeset.

Do not re-try anything listed under `tried:` in signals.yaml. That is what it
is for.

## The immediately available next step

`raw/daily_raw/*.parquet` now holds the full daily CRSP file, 1962-2017, five
columns (permno, date, return, volume, shares). It was pulled specifically for
SUV and DTO, which cannot be built from the monthly moments:

* **DTO** needs a median over 180 trading days. The current version approximates
  it with a rolling median of nine monthly means and scores 0.36. With the daily
  file the true median is computable directly.
* **SUV** needs day-level regression residuals. Every variant expressible in
  monthly sufficient statistics has been tried and none beats 0.09; the daily
  file allows the ones that could not be expressed.

Score any candidate with `pipeline/harness.py`, which takes seconds per variant.

## The other four

aBEME, aSAT and aPM are the industry-adjusted set. Eighteen variants across ten
classification schemes and eight adjustment operations are logged as rejected.
Neither Chen and Zimmermann nor Jensen, Kelly and Pedersen carry any
industry-adjusted signal, so there is no reference implementation to compare
against. The conclusion in the report is that the industry assignment comes
from a file we do not have, and the route forward is Andrea rather than more
searching. TNOVR at 0.79 is close and may yield to a window or screen variant.

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
about 0.895. The current mapping reaches 0.678.

## Scripts

    build_panel.py        pull and build the 57-characteristic panel
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
