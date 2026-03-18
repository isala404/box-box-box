from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPS = ("SOFT", "MEDIUM", "HARD")
HOT_TEMPS = (27, 28, 29, 30, 31, 32, 33)

OFF = {"SOFT": -1.0, "MEDIUM": 0.0, "HARD": 0.8}
RATE = {
    "SOFT": 1.2406729384227766,
    "MEDIUM": 0.6290198039097495,
    "HARD": 0.32170928712764346,
}
BASE_GRACE = {"SOFT": 10, "MEDIUM": 20, "HARD": 30}
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


def load_cases() -> list[tuple[dict, list[str]]]:
    cases = []
    inputs = ROOT / "data" / "test_cases" / "inputs"
    expected = ROOT / "data" / "test_cases" / "expected_outputs"
    for path in sorted(inputs.glob("test_*.json")):
        race = json.loads(path.read_text())
        finishing = json.loads((expected / path.name).read_text())["finishing_positions"]
        cases.append((race, finishing))
    return cases


def score(cases: list[tuple[dict, list[str]]], delta: dict[int, dict[str, int]]) -> int:
    passed = 0
    for race, finishing in cases:
        rc = race["race_config"]
        tf = TF[rc["track_temp"]]
        hot_delta = delta.get(rc["track_temp"], {})
        rows = []
        for strategy in race["strategies"].values():
            total = 0.0
            age = 0
            compound = strategy["starting_tire"]
            pit_laps = {int(stop["lap"]): stop["to_tire"] for stop in strategy["pit_stops"]}
            for lap in range(1, rc["total_laps"] + 1):
                age += 1
                grace = BASE_GRACE[compound] + hot_delta.get(compound, 0)
                total += rc["base_lap_time"] + OFF[compound]
                total += RATE[compound] * max(0, age - grace) * tf[compound]
                if lap in pit_laps:
                    total += rc["pit_lane_time"]
                    compound = pit_laps[lap]
                    age = 0
            rows.append((total, strategy["driver_id"]))
        rows.sort()
        passed += [driver_id for _, driver_id in rows] == finishing
    return passed


def main() -> None:
    cases = load_cases()
    delta = {temp: {comp: 0 for comp in COMPS} for temp in HOT_TEMPS}
    print("start", score(cases, delta))
    for iteration in range(5):
        changed = False
        for temp in HOT_TEMPS:
            for comp in COMPS:
                base_x = delta[temp][comp]
                best_x = base_x
                best_score = score(cases, delta)
                for x in range(-3, 4):
                    delta[temp][comp] = x
                    cur = score(cases, delta)
                    if (cur, -abs(x - base_x)) > (best_score, -abs(best_x - base_x)):
                        best_score = cur
                        best_x = x
                delta[temp][comp] = best_x
                if best_x != base_x:
                    changed = True
                    print("iter", iteration + 1, "temp", temp, "comp", comp, "delta", best_x, "score", best_score)
        if not changed:
            break
    print("final", score(cases, delta))
    print(delta)


if __name__ == "__main__":
    main()
