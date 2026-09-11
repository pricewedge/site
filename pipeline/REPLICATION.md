# Rebuilding the paper's estimates from raw CRSP and Compustat

This records how far the from-scratch pipeline gets against *Dynamic Asset
(Mis)Pricing: Build-up versus Resolution Anomalies*, and where it does not get
there. Re-run it with `./.venv/bin/python validate.py`.

## What is being checked

The replication package could not ship CRSP or Compustat data, so it ships its
outputs instead. Two of those outputs make a from-scratch rebuild checkable.

**Table 1** gives the long-leg and short-leg price wedge for each of the 57
characteristics. That is the number that matters, but it is one number per leg,
arrived at through a sort, a 241-month buy-and-hold, and a discount factor — so
when it disagrees, it does not say which step is wrong.

**`DataIN/crsp.mat`** carries `datas_all_charP`, whose slots 41–51 hold each
decile's share of market capitalisation for every formation month and every
characteristic. That series depends only on how a characteristic is built and
how it is sorted. It is 462 observations per characteristic instead of one, and
it isolates exactly the step a rebuild is most likely to get wrong.

The second check is what made the first one tractable. Agreement on decile
weights predicts agreement on wedges: of the 43 characteristics whose weights
agree above 0.85, the wedges land within 2 percentage points on average; of the
14 below it, none do.

## Where it stands

All 57 characteristics build from raw CRSP and Compustat. Against Table 1's
published wedges:

| | characteristics | mean abs. difference, long leg | short leg | correlation, long | short |
|---|---|---|---|---|---|
| decile weights agree above 0.85 | 43 | 1.96 pp | 1.10 pp | 0.981 | 0.992 |
| all | 57 | 3.57 pp | 1.58 pp | 0.888 | 0.964 |

For scale: the published long-leg wedges run from &minus;38.6 to +14.8
percentage points and the short legs from &minus;20.5 to +19.5, so a mean error
of about two points on the verified 43 is a small fraction of the spread being
measured. Of those 43, 32 land within one point on at least one leg and 16 on
both; I2A, R_2_1 and R_36_13 land within a tenth of a point.

The fourteen that fall below 0.85 are listed at the end of `validate.py`'s
output and discussed under *What is still wrong* below. Two of them, OA and
AOA, are wrong enough that they should not be published.

## What the decile weights caught

Eight constructions were wrong, and in every case Appendix Table A.1's wording
was either silent or actively misleading. The weights settled each one.

| Characteristic | The wording suggests | What the data says | Agreement |
|---|---|---|---|
| R_12_2 and the other four momentum sorts | return from 12 months to 2 months ago | stored one month earlier; the sort's own lag then produces the stated window | 0.65 → 0.97 |
| R_2_1 | lagged one-month return | the current month's return, for the same reason | 0.11 → 0.97 |
| SPREAD | average daily bid-ask spread | the daily high-low range; CRSP quotes cover 9% of daily rows in the 1960s | 0.02 → 0.94 |
| BETA_d | sum of coefficients on the market and its lag | estimated over twelve months of daily data, not one | 0.35 → 0.94 |
| sdDVOL | standard deviation of daily volume | of *log* dollar volume | 0.06 → 0.73 |
| dSOUT | annual % change in shares outstanding (shrout) | split-adjusted; CRSP's share counts are not | 0.51 → 0.88 |
| TAN | a weighted sum of receivables, inventory, plant and cash | every component required, not filled with zero | 0.48 → 0.96 |
| ROIC | earnings to the *sum* of equity, liabilities and cash | cash subtracted, which is what invested capital means | 0.64 → 0.93 |

Two further conventions came from the same check rather than from the text: the
industry mean behind aBEME, aPM, aSAT and aSIZE is equal-weighted over ordinary
common shares only, and DP sums twelve monthly dividends per share without
restating them for splits — the more coherent calculation agrees *worse*.

## What is still wrong

**OA and AOA (0.07, 0.09).** Operating accruals. Roughly twenty definitions
were tried — the literal reading of Appendix Table A.1, Sloan's grouping of the
current-liability terms, the change in net operating assets, with and without
depreciation, scaled by lagged, current and average total assets, by sales and
by absolute earnings — and none reaches 0.6. The published series is genuine
(it is distinct from every other slot and correlates most with the investment
characteristics, as accruals should), so something specific about its
construction is still missing. The resulting wedge is wrong by 40 percentage
points on the long leg, so these two should not be published until resolved.

**SUV (0.08).** Standardised unexplained volume. Estimating the
volume-on-returns regression on the previous month and applying it to the
current one is the natural reading, and the level of the decile weights comes
out right while the month-to-month variation does not.

**DTO (0.37).** Detrended turnover. Its 180-trading-day median is not a moment
of any month, so it cannot be recovered from the server-side aggregation the
rest of the daily characteristics use; it is approximated from a rolling window
of monthly means, and the approximation is the likely cause.

**aPM, aSAT, aBEME, aSIZE (0.30–0.84).** The industry adjustment. Neither
Compustat's historical SIC, nor two-digit SIC, nor a median in place of a mean,
nor capitalisation weighting does better than the plain equal-weighted
Fama-French 48 demeaning that ships.

**TNOVR, RNA, dPIA, ATO, DP, PM (0.71–0.82).** No alternative definition
tried beats what is here. These are ratios whose denominators Compustat
restatements move most, and the package was built from a 2018 vintage, so the
residual is more likely drift in Compustat's own history than an error.
