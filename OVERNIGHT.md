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

(results below, appended as they land)
