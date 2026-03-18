# Batch 1 Summary

## Current Beliefs vs Uncertainties

- Likely solid: additive compound offsets, grace windows around 10/20/30, lap-by-lap pit timing, and order sensitivity from floating accumulation at least for some mirror cases.
- Re-opened: smooth temperature power law, globally linear degradation without thresholds, and the claim that mirror mismatches are only precision noise.
- Unresolved: whether per-temperature behavior is discrete/piecewise, whether adjacent pit-shift boundaries expose off-by-one rules, and whether current failures cluster around a small set of strategy motifs.

## Top 5 Experiments

1. Adjacent one-stop pit-shift heatmaps on clean new laps to expose crisp boundary shapes.
2. Boundary-age extraction and inferred per-temperature factor to test lookup/piecewise vs smooth temperature behavior.
3. Mirror-pair diagnostics comparing inline accumulation with closed-form ties.
4. Test counterexample clustering by temperature, laps, mirror flag, grace-edge flag, and transition pair.
5. Adjacent-pair residual analysis to see whether errors grow with age, temperature, or only at structural edges.

## Artifacts

- Adjacent pairs: `175,157` rows
- Mirror pairs: `40,428` rows
- Test cases: `100` rows
- Test inversions: `84` rows

## Experiment Conclusions

- Experiment 1: {'SOFT->MEDIUM': 9.0, 'SOFT->HARD': 9.4, 'MEDIUM->SOFT': nan, 'MEDIUM->HARD': 20.26086956521739, 'HARD->SOFT': nan, 'HARD->MEDIUM': nan}
- Experiment 2: {'median_abs_delta_to_power_curve': 0.27182005244906793}
- Experiment 3: {'mirror_pred_accuracy': 0.9596814089245078, 'mirror_median_inline_abs_diff': 2.2737367544323206e-12, 'mirror_share_closed_zero': 1.0}
- Experiment 4: {'test_pass_rate': 0.67, 'mean_inversions_failed_test': 2.5454545454545454, 'mirror_share_of_inversions': 0.023809523809523808}
- Experiment 5: {'adjacent_pair_accuracy': 0.9991721712520767, 'adjacent_clean_accuracy': 0.9999570881752176, 'adjacent_dirty_accuracy': 0.9976125104452668}

## Keep / Discard / Uncertain

- Keep: adjacent pit-shift analysis as the main evidence source because it reduces whole races to single-lap inequalities.
- Discard for now: any claim that temperature is definitively smooth based only on aggregate score differences.
- Uncertain: whether baseline linear age_eff is actually correct everywhere or only a good local surrogate.

## Next Highest-Value Experiment

- Use only the clean-new adjacent pairs to infer a discrete lap-time table order for each compound across `(temperature, age)` and look for exact threshold tables or missing off-by-one indexing.