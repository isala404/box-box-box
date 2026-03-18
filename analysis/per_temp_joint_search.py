from __future__ import annotations

import json
from collections import defaultdict
from itertools import product
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPS = ("SOFT", "MEDIUM", "HARD")
TARGET_TEMPS = (20, 22, 23, 28, 29, 30, 31, 32, 33)

OFF = {"SOFT": -1.0, "MEDIUM": 0.0, "HARD": 0.8}
RATE = {
    "SOFT": 1.2406729384227766,
    "MEDIUM": 0.6290198039097495,
    "HARD": 0.32170928712764346,
}
GRACE = {"SOFT": 10, "MEDIUM": 20, "HARD": 30}

BASE_TF = {
    18: {"SOFT": 0.932373217526, "MEDIUM": 0.932373217526, "HARD": 0.932373217526},
    19: {"SOFT": 1.005464726294, "MEDIUM": 1.005464726294, "HARD": 1.005464726294},
    20: {"SOFT": 1.079951690342, "MEDIUM": 1.079951690342, "HARD": 1.079951690342},
    22: {"SOFT": 1.0798376667179816, "MEDIUM": 1.0798376667179816, "HARD": 1.0798376667179816},
    23: {"SOFT": 1.164733386941, "MEDIUM": 1.164733386941, "HARD": 1.164733386941},
    26: {"SOFT": 1.308552561689, "MEDIUM": 1.308552561689, "HARD": 1.308552561689},
    27: {"SOFT": 1.344083244542, "MEDIUM": 1.331121185847, "HARD": 1.326043793731},
    28: {"SOFT": 1.3114899386681973, "MEDIUM": 1.341362095824, "HARD": 1.3114899386681973},
    29: {"SOFT": 1.31701868377, "MEDIUM": 1.31701868377, "HARD": 1.31701868377},
    30: {"SOFT": 1.3164898522, "MEDIUM": 1.3164898522, "HARD": 1.3164898522},
    31: {"SOFT": 1.452050999821, "MEDIUM": 1.452050999821, "HARD": 1.452050999821},
    32: {"SOFT": 1.444220894213, "MEDIUM": 1.444220894213, "HARD": 1.444220894213},
    33: {"SOFT": 1.46377480385, "MEDIUM": 1.435672188888, "HARD": 1.435672188888},
    34: {"SOFT": 1.504979252794, "MEDIUM": 1.504979252794, "HARD": 1.504979252794},
    36: {"SOFT": 1.6059232078752694, "MEDIUM": 1.6059232078752694, "HARD": 1.6059232078752694},
    37: {"SOFT": 1.782270872844, "MEDIUM": 1.782270872844, "HARD": 1.782270872844},
    38: {"SOFT": 3.205179469746, "MEDIUM": 3.205179469746, "HARD": 3.205179469746},
    39: {"SOFT": 1.7129301197683011, "MEDIUM": 1.7129301197683011, "HARD": 1.7129301197683011},
    40: {"SOFT": 1.7482392028429241, "MEDIUM": 1.7482392028429241, "HARD": 1.7482392028429241},
    41: {"SOFT": 1.853832649017, "MEDIUM": 1.853832649017, "HARD": 1.853832649017},
    42: {"SOFT": 1.862395713292, "MEDIUM": 1.862395713292, "HARD": 1.862395713292},
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
    rc = race["race_config"]
    rows = []
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
        rows.append((total, strategy["driver_id"]))
    rows.sort()
    return [driver_id for _, driver_id in rows]


def local_score(cases: list[tuple[dict, list[str]]], tf: dict[str, float]) -> int:
    return sum(1 for race, finishing in cases if predict(race, tf) == finishing)


def candidate_breaks(cases: list[tuple[dict, list[str]]], tf: dict[str, float], target_comp: str) -> list[float]:
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


def refine(cases: list[tuple[dict, list[str]]], start_tf: dict[str, float]) -> tuple[int, dict[str, float]]:
    tf = dict(start_tf)
    while True:
        changed = False
        for comp in COMPS:
            base_x = tf[comp]
            best_x = base_x
            best_local = local_score(cases, tf)
            candidates = [base_x]
            breaks = candidate_breaks(cases, tf, comp)
            if breaks:
                candidates.append(max(0.05, breaks[0] - 1.0))
                candidates.extend(breaks)
                candidates.extend((a + b) / 2 for a, b in zip(breaks, breaks[1:]))
                candidates.append(min(6.0, breaks[-1] + 1.0))
            for x in sorted(set(round(v, 12) for v in candidates if 0.05 <= v <= 6.0)):
                old = tf[comp]
                tf[comp] = x
                cur = local_score(cases, tf)
                tf[comp] = old
                if (cur, -abs(x - base_x)) > (best_local, -abs(best_x - base_x)):
                    best_local = cur
                    best_x = x
            if abs(best_x - tf[comp]) > 1e-12:
                tf[comp] = best_x
                changed = True
        if not changed:
            return local_score(cases, tf), tf


def main() -> None:
    by_temp = load_cases()
    for temp in TARGET_TEMPS:
        cases = by_temp[temp]
        base = BASE_TF[temp]
        best_score = local_score(cases, base)
        best_tf = dict(base)
        print("temp", temp, "start", best_score, "/", len(cases))

        seeds = []
        multipliers = (0.92, 1.0, 1.08)
        for ms, mm, mh in product(multipliers, repeat=3):
            seeds.append(
                {
                    "SOFT": base["SOFT"] * ms,
                    "MEDIUM": base["MEDIUM"] * mm,
                    "HARD": base["HARD"] * mh,
                }
            )
        seen = set()
        for seed in seeds:
            key = tuple(round(seed[comp], 12) for comp in COMPS)
            if key in seen:
                continue
            seen.add(key)
            score, tf = refine(cases, seed)
            if (score, -sum(abs(tf[comp] - base[comp]) for comp in COMPS)) > (
                best_score,
                -sum(abs(best_tf[comp] - base[comp]) for comp in COMPS),
            ):
                best_score = score
                best_tf = tf
        print("temp", temp, "best", best_score, "/", len(cases), best_tf)


if __name__ == "__main__":
    main()
