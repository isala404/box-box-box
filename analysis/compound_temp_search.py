from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPS = ("SOFT", "MEDIUM", "HARD")

OFF = {"SOFT": -1.0, "MEDIUM": 0.0, "HARD": 0.8}
RATE = {
    "SOFT": 1.2406729384227766,
    "MEDIUM": 0.6290198039097495,
    "HARD": 0.32170928712764346,
}
GRACE = {"SOFT": 10, "MEDIUM": 20, "HARD": 30}

BASE_TABLE = {
    18: 0.932373217526,
    19: 1.005464726294,
    20: 1.079951690342,
    22: 1.0798376667179816,
    23: 1.164733386941,
    26: 1.308552561689,
    27: 1.326043793731,
    28: 1.3114899386681973,
    29: 1.31701868377,
    30: 1.3164898522,
    31: 1.452050999821,
    32: 1.444220894213,
    33: 1.435672188888,
    34: 1.504979252794,
    36: 1.6059232078752694,
    37: 1.782270872844,
    38: 3.205179469746,
    39: 1.7129301197683011,
    40: 1.7482392028429241,
    41: 1.853832649017,
    42: 1.862395713292,
}


def load_cases() -> dict[int, list[tuple[dict, list[str]]]]:
    by_temp: dict[int, list[tuple[dict, list[str]]]] = defaultdict(list)
    inputs = ROOT / "data" / "test_cases" / "inputs"
    expected = ROOT / "data" / "test_cases" / "expected_outputs"

    for path in sorted(inputs.glob("test_*.json")):
        race = json.loads(path.read_text())
        finishing = json.loads((expected / path.name).read_text())["finishing_positions"]
        by_temp[race["race_config"]["track_temp"]].append((race, finishing))
    return by_temp


def predict(race: dict, tf: dict[str, float]) -> list[str]:
    totals = []
    rc = race["race_config"]
    for strategy in race["strategies"].values():
        total = 0.0
        age = 0
        compound = strategy["starting_tire"]
        pit_laps = {int(stop["lap"]): stop["to_tire"] for stop in strategy["pit_stops"]}
        for lap in range(1, rc["total_laps"] + 1):
            age += 1
            total += rc["base_lap_time"] + OFF[compound]
            total += RATE[compound] * max(0, age - GRACE[compound]) * tf[compound]
            if lap in pit_laps:
                total += rc["pit_lane_time"]
                compound = pit_laps[lap]
                age = 0
        totals.append((total, strategy["driver_id"]))
    totals.sort()
    return [driver_id for _, driver_id in totals]


def local_score(cases: list[tuple[dict, list[str]]], tf: dict[str, float]) -> int:
    return sum(1 for race, finishing in cases if predict(race, tf) == finishing)


def candidate_breaks(
    cases: list[tuple[dict, list[str]]],
    tf: dict[str, float],
    target_comp: str,
) -> list[float]:
    vals = []
    others = [comp for comp in COMPS if comp != target_comp]
    for race, _ in cases:
        rc = race["race_config"]
        reduced = []
        for strategy in race["strategies"].values():
            const = 0.0
            coeff = {comp: 0.0 for comp in COMPS}
            age = 0
            compound = strategy["starting_tire"]
            pit_laps = {int(stop["lap"]): stop["to_tire"] for stop in strategy["pit_stops"]}
            for lap in range(1, rc["total_laps"] + 1):
                age += 1
                const += rc["base_lap_time"] + OFF[compound]
                coeff[compound] += RATE[compound] * max(0, age - GRACE[compound])
                if lap in pit_laps:
                    const += rc["pit_lane_time"]
                    compound = pit_laps[lap]
                    age = 0
            base = const + sum(coeff[comp] * tf[comp] for comp in others)
            reduced.append((base, coeff[target_comp]))
        for idx, (c1, k1) in enumerate(reduced):
            for c2, k2 in reduced[idx + 1 :]:
                delta_k = k1 - k2
                if abs(delta_k) < 1e-12:
                    continue
                x = (c2 - c1) / delta_k
                if 0.05 <= x <= 6.0:
                    vals.append(round(x, 12))
    return sorted(set(vals))


def main() -> None:
    by_temp = load_cases()
    tf = {temp: {comp: BASE_TABLE[temp] for comp in COMPS} for temp in by_temp}

    def total_score() -> int:
        return sum(local_score(by_temp[temp], tf[temp]) for temp in by_temp)

    print("start", total_score())
    for iteration in range(8):
        changed = False
        for temp in sorted(by_temp):
            cases = by_temp[temp]
            for comp in COMPS:
                base_x = tf[temp][comp]
                best_x = base_x
                best_local = local_score(cases, tf[temp])
                candidates = [base_x]
                breaks = candidate_breaks(cases, tf[temp], comp)
                if breaks:
                    candidates.append(max(0.05, breaks[0] - 1.0))
                    candidates.extend(breaks)
                    candidates.extend((a + b) / 2 for a, b in zip(breaks, breaks[1:]))
                    candidates.append(min(6.0, breaks[-1] + 1.0))
                for x in sorted(set(round(v, 12) for v in candidates if 0.05 <= v <= 6.0)):
                    old = tf[temp][comp]
                    tf[temp][comp] = x
                    score = local_score(cases, tf[temp])
                    tf[temp][comp] = old
                    if (score, -abs(x - base_x)) > (best_local, -abs(best_x - base_x)):
                        best_local = score
                        best_x = x
                if abs(best_x - tf[temp][comp]) > 1e-12:
                    tf[temp][comp] = best_x
                    changed = True
                    print(
                        "iter",
                        iteration + 1,
                        "temp",
                        temp,
                        "comp",
                        comp,
                        "local",
                        best_local,
                        "x",
                        best_x,
                        "total",
                        total_score(),
                    )
        if not changed:
            break

    print("final", total_score())
    for temp in sorted(tf):
        print(temp, tf[temp])


if __name__ == "__main__":
    main()
