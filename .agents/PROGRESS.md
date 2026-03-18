Zero-degradation constraint analysis (analysis/zero_deg_v2.py, zero_deg_v3.py, zero_deg_final.py)
- FINDING: Feasible region for (off_S, off_H) is an unbounded cone; ratio r = off_H/(-off_S) must be in open interval (7/9, 5/6)
- FINDING: Simplest fraction 4/5 = 0.8 sits at the center; at ratio=4/5 the contradictory pair (8,10)/(-8,-10) is exactly on the boundary (8*S+10*H=0), explains irreducible 3,614 violations (0.34%)
- TRADEOFF: Cannot determine absolute scale from ordering alone (pure ratio constraint). Need degradation rate fitting to pin down off_S ≈ -0.5 to -1.5 s/lap
- Plots saved to analysis/plots_v2/: zero_deg_final.png, violations_heatmap.png, feasible_region_v2.png
- Scripts take ~120s to run due to loading all 30k races + O(n^2) pair extraction

Implemented vectorized lap-by-lap analysis script (analysis/analyze_v2.py)
- TRADEOFF: Vectorized dot product for training (~0.35s/paramset) vs reference simulator for test cases (exact FP match needed). Tied drivers cause different ordering between approaches due to floating-point accumulation order.
- Current best params score 42/100 test cases, 0/30000 exact train matches, pairwise ~0.516
- Constraint-optimal offsets (off_S=-1.014, off_H=0.797) score only 7/100 test cases despite slightly higher pairwise accuracy (~0.5166) — not the right direction
- Perturbations around current_best show at most 28/100, suggesting the formula or parameters need rethinking
- ISSUE: 0 exact train matches means the simulator ordering never perfectly matches any race — likely missing something (random noise, per-driver base speed, etc.)
- FINDING: 94.8% of drivers in failed races have pos errors >0, concentrated in races with all 3 compounds (29,587/30k). Failures show no pattern with temperature or race length — errors are spread uniformly.
- FINDING: Training pairwise accuracy ~0.516 is barely above 0.5 (random), which is a major red flag — the model barely outperforms chance on ordering pairs of drivers. This suggests the formula is missing key terms.
