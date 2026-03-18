# Reverse Engineering Lab Notebook

## Current Beliefs vs Uncertainties

### Likely Proven Invariants
- Race outcome is independent per driver; only total simulated time matters.
- Pit stops happen at the end of the specified lap, and pit time must be added inline.
- Tire age starts at 0, increments before lap timing, so the first lap on a fresh set is age 1.
- The offset model is additive, not multiplicative.
- Grace windows near `SOFT=10`, `MEDIUM=20`, `HARD=30` are very likely real, but still worth attacking with targeted adjacent-pair checks.

### Plausible But Not Yet Safe
- Temperature is well described by a shared smooth power law.
- Degradation is globally linear after grace with no hidden thresholds or table lookups.
- Mirror-strategy mismatches are only floating accumulation and not a missing order-sensitive term.
- The current offset and rate values are close to the true ones rather than being a compensating surrogate.

### Known Dead Ends
- Multiplicative compound effects.
- Fuel terms.
- Blind optimizer-heavy search without structural constraints.
- Treating aggregate score improvements as proof of the underlying algorithm.

## Top 5 Highest-Information Experiments

1. Adjacent one-stop pit-shift heatmaps on clean new laps.
Hypothesis: If the simulator is simple, these comparisons should show crisp temperature-age boundaries rather than diffuse noise.

2. Boundary extraction and inferred per-temperature factor.
Hypothesis: The temperature domain may be discrete or piecewise, and the power-law fit may just be a surrogate.

3. Mirror-pair diagnostics.
Hypothesis: Some reversed-order outcomes are pure floating accumulation, but others may reveal a missing structural term.

4. Test counterexample clustering.
Hypothesis: The current failures come from a few motifs, not from broad global imprecision.

5. Adjacent-pair residual analysis.
Hypothesis: If baseline linear degradation is wrong, residuals should spike at specific ages, compounds, or temperature bands.

## Operating Rules
- Prefer controlled comparisons over global fitting.
- Save plots before drawing conclusions.
- Kill a hypothesis as soon as the plot contradicts it.
- Re-run only the experiments that survive the previous batch.

## Batch 1 Results

- Adjacent one-stop pit-shift comparisons are almost perfectly explained by the current structural model: `175,157` adjacent pairs with `99.917%` agreement, and `99.996%` on the clean-new-lap subset.
- Mirror pairs remain precision-sensitive, but they are not the main remaining error source: `40,428` mirror pairs with `95.97%` agreement and median inline diff around `2.27e-12`.
- The remaining adjacent-pair errors are not diffuse. `145` misclassifications cluster heavily in a few exact cells, dominated by `HARD->SOFT` and `SOFT->HARD`.
- The strongest spike is `new_age_eff = 1`, especially `HARD->SOFT` where the compared soft lap is the first lap beyond soft grace.

## Batch 2 Results

- Exact-state cells that should be deterministic under a `(compound, age, temp)`-only model split by `base_lap_time`.
- The split is strong, not marginal. In mixed `HARD->SOFT` cells like `(temp=32, age_old=26, age_new=11)`, low-base races lose while high-base races win.
- A simple base interaction improves the test score:
  - baseline additive model with temperature only: `67/100`
  - add degradation scale `* (base_lap_time / 87.5)^alpha`: best narrow scan found `69/100` at fixed old power, and `70/100` when combined with `temp_power ~= 0.82`
- A crude low/high base threshold did not improve score, so the base effect appears smoother than a single step.

## Updated Beliefs

- Stronger: grace indexing and linear-in-age degradation are mostly right.
- Stronger: temperature still matters multiplicatively and the useful exponent remains near `0.82`.
- New structural lead: `base_lap_time` affects degradation. This was missed by the earlier temperature-only model.
- Weaker: the claim that compound, age, and temperature alone are sufficient.

## Next Highest-Value Experiments

1. Mine the remaining 30 failing tests under the `base`-aware model and see whether the residual cluster is now mostly mirror/tie noise or another clean structural motif.
2. Test whether the base interaction should apply to all compounds equally or whether compound-specific base scaling explains the remaining failing family.
3. Re-open a tiny fuel / absolute-lap-position probe only in the residual cells, because adjacent-pair derivations compare laps at different race positions.
