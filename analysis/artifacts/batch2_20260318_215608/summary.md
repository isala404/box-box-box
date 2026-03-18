# Batch 2 Summary

## Hypothesis

- `base_lap_time` is a missing structural variable, likely interacting with degradation rather than with the whole lap multiplicatively.

## Minimal Tests

1. Inspect exact-state cells that should be deterministic under the current model and see whether they split by base.
2. Inspect the dominant `HARD->SOFT` boundary case where the new soft lap is the first lap beyond grace.
3. Run a very small one-parameter scan where degradation scales with base for all compounds or for SOFT only.

## Best Candidates

- model=all_deg, alpha=0.350, tests=69, adjacent_acc=0.999052, hs_soft11_acc=0.666667
- model=all_deg, alpha=0.400, tests=69, adjacent_acc=0.999041, hs_soft11_acc=0.671875
- model=all_deg, alpha=0.450, tests=68, adjacent_acc=0.999035, hs_soft11_acc=0.677083
- model=all_deg, alpha=0.000, tests=67, adjacent_acc=0.999172, hs_soft11_acc=0.619792
- model=soft_deg, alpha=0.000, tests=67, adjacent_acc=0.999172, hs_soft11_acc=0.619792
- model=all_deg, alpha=0.100, tests=67, adjacent_acc=0.999109, hs_soft11_acc=0.619792

## Interim Conclusion

- If the best base-scaling candidate improves both test score and the `HARD->SOFT` boundary accuracy, base interaction is a real lead.
- If it only improves one narrow cell but hurts global score, base may be a proxy for a more specific missing rule.