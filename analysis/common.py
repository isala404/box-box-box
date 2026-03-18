from __future__ import annotations

import json
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Sequence


ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_DIR = ROOT / "data" / "historical_races"
TEST_INPUT_DIR = ROOT / "data" / "test_cases" / "inputs"
TEST_EXPECTED_DIR = ROOT / "data" / "test_cases" / "expected_outputs"

COMPOUNDS = ("SOFT", "MEDIUM", "HARD")

DEFAULT_PARAMS = {
    "off": {"SOFT": -1.0, "MEDIUM": 0.0, "HARD": 0.8},
    "rate": {
        "SOFT": 1.2406729384227766,
        "MEDIUM": 0.6290198039097495,
        "HARD": 0.32170928712764346,
    },
    "grace": {"SOFT": 10, "MEDIUM": 20, "HARD": 30},
    "temp_power": 0.8059025951046688,
}


@dataclass(frozen=True)
class DriverSummary:
    race_id: str
    driver_id: str
    true_rank: int
    predicted_rank: int
    total_laps: int
    temp: int
    pit_time: float
    base_lap_time: float
    starting_tire: str
    compounds: tuple[str, ...]
    pit_laps: tuple[int, ...]
    stint_lengths: tuple[int, ...]
    pit_count: int
    transition: str
    total_time_inline: float
    total_time_closed: float


def iter_historical_races(limit_races: int | None = None) -> Iterator[dict]:
    yielded = 0
    for path in sorted(HISTORICAL_DIR.glob("*.json")):
        for race in json.loads(path.read_text()):
            yield race
            yielded += 1
            if limit_races is not None and yielded >= limit_races:
                return


def iter_test_cases(with_expected: bool = False) -> Iterator[dict | tuple[dict, dict]]:
    for path in sorted(TEST_INPUT_DIR.glob("test_*.json")):
        race = json.loads(path.read_text())
        if with_expected:
            expected = json.loads((TEST_EXPECTED_DIR / path.name).read_text())
            yield race, expected
        else:
            yield race


def strategy_components(strategy: dict, total_laps: int) -> tuple[tuple[str, ...], tuple[int, ...], tuple[int, ...]]:
    compounds: List[str] = [strategy["starting_tire"]]
    pit_laps: List[int] = []
    stint_lengths: List[int] = []
    last_lap = 0
    for stop in strategy["pit_stops"]:
        pit_lap = int(stop["lap"])
        pit_laps.append(pit_lap)
        stint_lengths.append(pit_lap - last_lap)
        compounds.append(stop["to_tire"])
        last_lap = pit_lap
    stint_lengths.append(total_laps - last_lap)
    return tuple(compounds), tuple(pit_laps), tuple(stint_lengths)


def temp_factor(temp: int, params: dict = DEFAULT_PARAMS) -> float:
    return (temp / 20.0) ** params["temp_power"]


def lap_time(compound: str, age: int, temp: int, params: dict = DEFAULT_PARAMS) -> float:
    off = params["off"][compound]
    rate = params["rate"][compound]
    grace = params["grace"][compound]
    return off + rate * max(0, age - grace) * temp_factor(temp, params)


def degradation_sum(length: int, grace: int) -> int:
    extra = length - grace
    if extra <= 0:
        return 0
    return extra * (extra + 1) // 2


def simulate_total_time_inline(strategy: dict, race_config: dict, params: dict = DEFAULT_PARAMS) -> float:
    total_time = 0.0
    tire_age = 0
    compound = strategy["starting_tire"]
    pit_laps = {int(stop["lap"]): stop["to_tire"] for stop in strategy["pit_stops"]}
    base = race_config["base_lap_time"]
    total_laps = race_config["total_laps"]
    pit_time = race_config["pit_lane_time"]
    tf = temp_factor(race_config["track_temp"], params)
    for lap in range(1, total_laps + 1):
        tire_age += 1
        total_time += (
            base
            + params["off"][compound]
            + params["rate"][compound] * max(0, tire_age - params["grace"][compound]) * tf
        )
        if lap in pit_laps:
            total_time += pit_time
            compound = pit_laps[lap]
            tire_age = 0
    return total_time


def simulate_total_time_closed_form(strategy: dict, race_config: dict, params: dict = DEFAULT_PARAMS) -> float:
    compounds, _, stint_lengths = strategy_components(strategy, race_config["total_laps"])
    base = race_config["base_lap_time"]
    total = base * race_config["total_laps"] + len(strategy["pit_stops"]) * race_config["pit_lane_time"]
    tf = temp_factor(race_config["track_temp"], params)
    for compound, length in zip(compounds, stint_lengths, strict=True):
        total += length * params["off"][compound]
        total += params["rate"][compound] * tf * degradation_sum(length, params["grace"][compound])
    return total


def simulate_race_inline(race: dict, params: dict = DEFAULT_PARAMS) -> list[str]:
    results = []
    for strategy in race["strategies"].values():
        results.append((simulate_total_time_inline(strategy, race["race_config"], params), strategy["driver_id"]))
    results.sort()
    return [driver_id for _, driver_id in results]


def build_driver_summaries(race: dict, params: dict = DEFAULT_PARAMS) -> list[DriverSummary]:
    config = race["race_config"]
    true_ranks = {driver_id: idx for idx, driver_id in enumerate(race["finishing_positions"])}
    predicted_order = simulate_race_inline(race, params)
    predicted_ranks = {driver_id: idx for idx, driver_id in enumerate(predicted_order)}

    rows: list[DriverSummary] = []
    for strategy in race["strategies"].values():
        driver_id = strategy["driver_id"]
        compounds, pit_laps, stint_lengths = strategy_components(strategy, config["total_laps"])
        rows.append(
            DriverSummary(
                race_id=race["race_id"],
                driver_id=driver_id,
                true_rank=true_ranks[driver_id],
                predicted_rank=predicted_ranks[driver_id],
                total_laps=config["total_laps"],
                temp=config["track_temp"],
                pit_time=config["pit_lane_time"],
                base_lap_time=config["base_lap_time"],
                starting_tire=strategy["starting_tire"],
                compounds=compounds,
                pit_laps=pit_laps,
                stint_lengths=stint_lengths,
                pit_count=len(strategy["pit_stops"]),
                transition="->".join(compounds),
                total_time_inline=simulate_total_time_inline(strategy, config, params),
                total_time_closed=simulate_total_time_closed_form(strategy, config, params),
            )
        )
    return rows


def relative_finish_winner(a: DriverSummary, b: DriverSummary) -> DriverSummary:
    return a if a.true_rank < b.true_rank else b


def predicted_winner(a: DriverSummary, b: DriverSummary) -> DriverSummary:
    return a if a.predicted_rank < b.predicted_rank else b


def is_mirror_pair(a: DriverSummary, b: DriverSummary) -> bool:
    return a.compounds == tuple(reversed(b.compounds)) and a.stint_lengths == tuple(reversed(b.stint_lengths))


def is_grace_edge(summary: DriverSummary, delta: int = 1, params: dict = DEFAULT_PARAMS) -> bool:
    for compound, length in zip(summary.compounds, summary.stint_lengths, strict=True):
        if abs(length - params["grace"][compound]) <= delta:
            return True
    return False


def pairwise_driver_rows(summaries: Sequence[DriverSummary]) -> Iterator[tuple[DriverSummary, DriverSummary]]:
    yield from combinations(summaries, 2)
