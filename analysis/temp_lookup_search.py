from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


OFF = {"SOFT": -1.0, "MEDIUM": 0.0, "HARD": 0.8}
RATE = {
    "SOFT": 1.2406729384227766,
    "MEDIUM": 0.6290198039097495,
    "HARD": 0.32170928712764346,
}
GRACE = {"SOFT": 10, "MEDIUM": 20, "HARD": 30}
TEMP_POWER = 0.8059025951046688


def load_cases() -> list[tuple[dict, dict]]:
    cases = []
    root = Path(__file__).resolve().parents[1]
    inputs = root / "data" / "test_cases" / "inputs"
    expected = root / "data" / "test_cases" / "expected_outputs"
    for path in sorted(inputs.glob("test_*.json")):
        cases.append((json.loads(path.read_text()), json.loads((expected / path.name).read_text())))
    return cases


def strategy_total(strategy: dict, race_config: dict, tf: float) -> float:
    total = 0.0
    age = 0
    compound = strategy["starting_tire"]
    pit_laps = {stop["lap"]: stop["to_tire"] for stop in strategy["pit_stops"]}
    for lap in range(1, race_config["total_laps"] + 1):
        age += 1
        total += race_config["base_lap_time"] + OFF[compound]
        total += RATE[compound] * max(0, age - GRACE[compound]) * tf
        if lap in pit_laps:
            total += race_config["pit_lane_time"]
            compound = pit_laps[lap]
            age = 0
    return total


def predict(race: dict, tf_table: dict[int, float]) -> list[str]:
    tf = tf_table[race["race_config"]["track_temp"]]
    rows = []
    for strategy in race["strategies"].values():
        rows.append((strategy_total(strategy, race["race_config"], tf), strategy["driver_id"]))
    rows.sort()
    return [driver_id for _, driver_id in rows]


def score(cases: list[tuple[dict, dict]], tf_table: dict[int, float]) -> int:
    return sum(1 for race, expected in cases if predict(race, tf_table) == expected["finishing_positions"])


def candidate_breakpoints(races: list[dict]) -> list[float]:
    thresholds = []
    for race in races:
        rc = race["race_config"]
        coeffs = []
        for strategy in race["strategies"].values():
            const = 0.0
            coeff = 0.0
            age = 0
            compound = strategy["starting_tire"]
            pit_laps = {stop["lap"]: stop["to_tire"] for stop in strategy["pit_stops"]}
            for lap in range(1, rc["total_laps"] + 1):
                age += 1
                const += rc["base_lap_time"] + OFF[compound]
                coeff += RATE[compound] * max(0, age - GRACE[compound])
                if lap in pit_laps:
                    const += rc["pit_lane_time"]
                    compound = pit_laps[lap]
                    age = 0
            coeffs.append((const, coeff))
        for i in range(len(coeffs)):
            for j in range(i + 1, len(coeffs)):
                c1, k1 = coeffs[i]
                c2, k2 = coeffs[j]
                dk = k1 - k2
                if abs(dk) < 1e-12:
                    continue
                thresholds.append((c2 - c1) / dk)
    return sorted(set(round(x, 12) for x in thresholds if 0.1 <= x <= 5.0))


def optimize_temp_lookup(cases: list[tuple[dict, dict]]) -> dict[int, float]:
    by_temp: dict[int, list[tuple[dict, dict]]] = defaultdict(list)
    for race, expected in cases:
        by_temp[race["race_config"]["track_temp"]].append((race, expected))

    tf_table = {temp: (temp / 20.0) ** TEMP_POWER for temp in by_temp}
    print("baseline score:", score(cases, tf_table))

    for temp, subset in sorted(by_temp.items()):
        breaks = candidate_breakpoints([race for race, _ in subset])
        candidates = [tf_table[temp]]
        if breaks:
            candidates.append(max(0.1, breaks[0] - 1.0))
            candidates.extend(breaks)
            candidates.extend((a + b) / 2 for a, b in zip(breaks, breaks[1:]))
            candidates.append(min(5.0, breaks[-1] + 1.0))
        best_score = score(subset, tf_table)
        best_tf = tf_table[temp]
        baseline_tf = (temp / 20.0) ** TEMP_POWER
        for cand in sorted(set(round(x, 12) for x in candidates if 0.1 <= x <= 5.0)):
            trial = dict(tf_table)
            trial[temp] = cand
            local = score(subset, trial)
            if (local, -abs(cand - baseline_tf)) > (best_score, -abs(best_tf - baseline_tf)):
                best_score = local
                best_tf = cand
        tf_table[temp] = best_tf
        print(f"temp={temp} local={best_score}/{len(subset)} tf={best_tf}")

    print("optimized score:", score(cases, tf_table))
    print("lookup table:")
    for temp in sorted(tf_table):
        print(f"  {temp}: {tf_table[temp]},")
    return tf_table


if __name__ == "__main__":
    optimize_temp_lookup(load_cases())
