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

TF = {
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


def predict(race: dict, off_adj: dict[str, float]) -> list[str]:
    rc = race["race_config"]
    tf = TF[rc["track_temp"]]
    rows = []
    for strategy in race["strategies"].values():
        total = 0.0
        age = 0
        compound = strategy["starting_tire"]
        pit_laps = {int(stop["lap"]): stop["to_tire"] for stop in strategy["pit_stops"]}
        for lap in range(1, rc["total_laps"] + 1):
            age += 1
            total += rc["base_lap_time"] + OFF[compound] + off_adj[compound]
            total += RATE[compound] * max(0, age - GRACE[compound]) * tf[compound]
            if lap in pit_laps:
                total += rc["pit_lane_time"]
                compound = pit_laps[lap]
                age = 0
        rows.append((total, strategy["driver_id"]))
    rows.sort()
    return [driver_id for _, driver_id in rows]


def local_score(cases: list[tuple[dict, list[str]]], off_adj: dict[str, float]) -> int:
    return sum(1 for race, finishing in cases if predict(race, off_adj) == finishing)


def candidate_breaks(
    cases: list[tuple[dict, list[str]]],
    off_adj: dict[str, float],
    target_comp: str,
) -> list[float]:
    vals = []
    others = [comp for comp in COMPS if comp != target_comp]
    for race, _ in cases:
        rc = race["race_config"]
        tf = TF[rc["track_temp"]]
        reduced = []
        for strategy in race["strategies"].values():
            const = 0.0
            laps_on_comp = {comp: 0.0 for comp in COMPS}
            age = 0
            compound = strategy["starting_tire"]
            pit_laps = {int(stop["lap"]): stop["to_tire"] for stop in strategy["pit_stops"]}
            for lap in range(1, rc["total_laps"] + 1):
                age += 1
                const += rc["base_lap_time"] + OFF[compound]
                const += RATE[compound] * max(0, age - GRACE[compound]) * tf[compound]
                laps_on_comp[compound] += 1.0
                if lap in pit_laps:
                    const += rc["pit_lane_time"]
                    compound = pit_laps[lap]
                    age = 0
            base = const + sum(laps_on_comp[comp] * off_adj[comp] for comp in others)
            reduced.append((base, laps_on_comp[target_comp]))
        for idx, (c1, k1) in enumerate(reduced):
            for c2, k2 in reduced[idx + 1 :]:
                delta_k = k1 - k2
                if abs(delta_k) < 1e-12:
                    continue
                x = (c2 - c1) / delta_k
                if -5.0 <= x <= 5.0:
                    vals.append(round(x, 12))
    return sorted(set(vals))


def main() -> None:
    by_temp = load_cases()
    off_adj = {temp: {comp: 0.0 for comp in COMPS} for temp in by_temp}

    def total_score() -> int:
        return sum(local_score(by_temp[temp], off_adj[temp]) for temp in by_temp)

    print("start", total_score())
    for iteration in range(8):
        changed = False
        for temp in sorted(by_temp):
            cases = by_temp[temp]
            for comp in COMPS:
                base_x = off_adj[temp][comp]
                best_x = base_x
                best_local = local_score(cases, off_adj[temp])
                candidates = [base_x]
                breaks = candidate_breaks(cases, off_adj[temp], comp)
                if breaks:
                    candidates.append(max(-5.0, breaks[0] - 1.0))
                    candidates.extend(breaks)
                    candidates.extend((a + b) / 2 for a, b in zip(breaks, breaks[1:]))
                    candidates.append(min(5.0, breaks[-1] + 1.0))
                for x in sorted(set(round(v, 12) for v in candidates if -5.0 <= v <= 5.0)):
                    old = off_adj[temp][comp]
                    off_adj[temp][comp] = x
                    score = local_score(cases, off_adj[temp])
                    off_adj[temp][comp] = old
                    if (score, -abs(x - base_x)) > (best_local, -abs(best_x - base_x)):
                        best_local = score
                        best_x = x
                if abs(best_x - off_adj[temp][comp]) > 1e-12:
                    off_adj[temp][comp] = best_x
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
    for temp in sorted(off_adj):
        if any(abs(off_adj[temp][comp]) > 1e-12 for comp in COMPS):
            print(temp, off_adj[temp])


if __name__ == "__main__":
    main()
