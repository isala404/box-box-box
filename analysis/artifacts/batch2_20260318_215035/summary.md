# Batch 2 Summary

## Hypotheses

1. `HARD->MEDIUM` vs `SOFT->MEDIUM` errors are a stint-geometry issue, not a mirror/tie issue.
2. Remaining adjacent-pair mistakes are concentrated on a few exact `SOFT<->HARD` and related boundary cells.

## Dataset Sizes

- HARD->MEDIUM vs SOFT->MEDIUM pairs: `218,968`
- Focused adjacent-pair rows: `112,735`

## Conclusions

- Experiment 6: {'overall_acc': 0.9800929816228855, 'focused_acc': 0.9810140455595461, 'focused_mean_abs_margin': 76.765032654271}
- Experiment 7: {'error_rows': 132.0, 'soft_hard_share': 0.8939393939393939, 'median_abs_margin_error': 0.0807339924126928}

## Updated Belief

- The current miss pattern looks more like exact balance/threshold recovery than a missing broad nonlinear term.
- The most suspicious structural corner remains the `SOFT<->HARD` boundary neighborhood, where small changes can flip exact cells repeatedly.