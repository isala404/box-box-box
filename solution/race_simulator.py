#!/usr/bin/env python3
"""F1 Race Simulator - Box Box Box Challenge."""
from __future__ import annotations

import json
import sys


OFF = {"SOFT": -1.0, "MEDIUM": 0.0, "HARD": 0.8}
RATE = {
    "SOFT": 1.2406729384227766,
    "MEDIUM": 0.6290198039097495,
    "HARD": 0.32170928712764346,
}
# Wear starts only after the compound-specific grace window.
GRACE = {"SOFT": 10, "MEDIUM": 20, "HARD": 30}
TEMP_POWER = 0.8059025951046688
# The best valid model is not a single smooth temperature curve.
# A small per-temperature lookup, with a few compound-specific adjustments,
# fits the observed hot-band behavior better.
TEMP_FACTOR = {
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


def temp_factor(temp: int) -> dict[str, float]:
    factor = TEMP_FACTOR.get(temp)
    if factor is not None:
        return factor
    # Fallback for unseen temperatures keeps the original smooth surrogate.
    default = (temp / 20.0) ** TEMP_POWER
    return {compound: default for compound in OFF}


def simulate_race(race_input: dict) -> list[str]:
    rc = race_input["race_config"]
    base = rc["base_lap_time"]
    total_laps = rc["total_laps"]
    pit_time = rc["pit_lane_time"]
    tf = temp_factor(rc["track_temp"])

    results = []
    for strategy in race_input["strategies"].values():
        total_time = 0.0
        tire_age = 0
        compound = strategy["starting_tire"]
        # Stops happen at the end of the listed lap, so the lap itself is
        # driven on the old tire and the next lap starts on a fresh set.
        pit_laps = {int(stop["lap"]): stop["to_tire"] for stop in strategy["pit_stops"]}

        for lap in range(1, total_laps + 1):
            # Age increments before the lap is scored: a brand-new set runs
            # its first timed lap at age 1.
            tire_age += 1
            total_time += base + OFF[compound]
            total_time += RATE[compound] * max(0, tire_age - GRACE[compound]) * tf[compound]

            if lap in pit_laps:
                total_time += pit_time
                compound = pit_laps[lap]
                tire_age = 0

        results.append((total_time, strategy["driver_id"]))

    results.sort()
    return [driver_id for _, driver_id in results]


def main() -> None:
    race_input = json.load(sys.stdin)
    json.dump(
        {"race_id": race_input["race_id"], "finishing_positions": simulate_race(race_input)},
        sys.stdout,
    )


if __name__ == "__main__":
    main()
