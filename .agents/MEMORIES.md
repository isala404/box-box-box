Tooling
- Stack: Python (analysis scripts), .venv/bin/python (3.12)
- Data: 30k historical races in data/historical_races/races_NNNNN-NNNNN.json (30 files x 1000 races), 100 test cases in data/test_cases/
- Key script: analysis/analyze_v2.py

Preferences
- Vectorized scoring uses precomputed feature vectors (dot products) for training pairwise accuracy, ~0.35s per param set vs ~7s naive
- Reference lap-by-lap simulator MUST be used for test case exact match scoring (FP accumulation order matters for ties)

Patterns
- Race structure: race_config + strategies (pos1..pos20, each has driver_id, starting_tire, pit_stops)
- Expected output: finishing_positions list of driver_ids in order
- Feature vector per driver: [base*laps, laps_S, laps_M, laps_H, deg_S, deg_M, deg_H, pit_time]
- Param coef vector: [1, off_S, off_M, off_H, rate_S, rate_M, rate_H, 1]

Domain
- F1 simulator: lap_time = base + off[c] + rate[c] * max(0, age - grace[c]) * T/20
- GRACE = {SOFT:10, MEDIUM:20, HARD:30}, age starts at 1 and resets to 0 after pit
- Pit happens at END of lap, so tire_age resets to 0, next lap starts at age=1
- Many races have tied or near-tied drivers (same strategy, same compounds) — sorting is sensitive to FP order
- 94.8% of drivers in failed races have position errors, suggesting most failures are genuine not FP ties
- HARD+MEDIUM+SOFT compound mix: 29,587/30,000 races; pure HARD+MEDIUM: 413 races

Constraint analysis (zero-degradation races)
- 6,000/30,000 races (20%) have ALL stints within grace period (zero degradation)
- 1,047,887 1-stop distinct-mix pair constraints extracted
- Feasible region is an UNBOUNDED CONE: ratio r = off_H/(-off_S) in OPEN interval (7/9, 5/6)
- Simplest fraction: 4/5 = 0.8. So off_H = 0.8 * (-off_S)
- The 0.34% irreducible violations (3,614 cases) come from near-tie pairs where 8*off_S+10*off_H=0 exactly at ratio 4/5
- These near-tie races appear to be resolved by something other than compound offsets (start position?)
- Absolute scale cannot be determined from ordering alone; need degradation rate fitting
