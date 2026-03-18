from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.common import DEFAULT_PARAMS, iter_test_cases


BASE_REF = 87.5
MODELS = ("all_deg", "soft_deg")


def artifact_dir() -> Path:
    stamp = datetime.now().strftime("batch2_%Y%m%d_%H%M%S")
    root = Path(__file__).resolve().parent / "artifacts" / stamp
    root.mkdir(parents=True, exist_ok=True)
    return root


def load_adjacent_with_meta() -> pd.DataFrame:
    adj = pd.read_csv(ROOT / "analysis" / "artifacts" / "batch1_20260318_214119" / "adjacent_one_stop_pairs.csv.gz")
    meta = []
    for path in sorted((ROOT / "data" / "historical_races").glob("*.json")):
        for race in json.loads(path.read_text()):
            rc = race["race_config"]
            meta.append(
                {
                    "race_id": race["race_id"],
                    "track": rc["track"],
                    "base": rc["base_lap_time"],
                    "pit": rc["pit_lane_time"],
                    "total_laps": rc["total_laps"],
                    "temp": rc["track_temp"],
                }
            )
    meta_df = pd.DataFrame(meta)
    return adj.merge(meta_df, on=["race_id", "total_laps", "temp"], how="left")


def base_scale(compound: str, base: float, alpha: float, model: str) -> float:
    scale = (base / BASE_REF) ** alpha
    if model == "all_deg":
        return scale
    if model == "soft_deg":
        return scale if compound == "SOFT" else 1.0
    return 1.0


def lap_delta_for_row(row: pd.Series, alpha: float, model: str) -> float:
    tf = (row["temp"] / 20.0) ** DEFAULT_PARAMS["temp_power"]
    start = row["start"]
    end = row["end"]
    old = DEFAULT_PARAMS["off"][start] + DEFAULT_PARAMS["rate"][start] * row["old_age_eff"] * tf * base_scale(start, row["base"], alpha, model)
    new = DEFAULT_PARAMS["off"][end] + DEFAULT_PARAMS["rate"][end] * row["new_age_eff"] * tf * base_scale(end, row["base"], alpha, model)
    return old - new


def simulate_race_base_model(race: dict, alpha: float, model: str) -> list[str]:
    rc = race["race_config"]
    base = rc["base_lap_time"]
    total_laps = rc["total_laps"]
    pit_time = rc["pit_lane_time"]
    temp = rc["track_temp"]
    tf = (temp / 20.0) ** DEFAULT_PARAMS["temp_power"]

    results = []
    for strategy in race["strategies"].values():
        total_time = 0.0
        tire_age = 0
        compound = strategy["starting_tire"]
        pit_laps = {int(stop["lap"]): stop["to_tire"] for stop in strategy["pit_stops"]}

        for lap in range(1, total_laps + 1):
            tire_age += 1
            age_eff = max(0, tire_age - DEFAULT_PARAMS["grace"][compound])
            deg = DEFAULT_PARAMS["rate"][compound] * age_eff * tf * base_scale(compound, base, alpha, model)
            total_time += base + DEFAULT_PARAMS["off"][compound] + deg
            if lap in pit_laps:
                total_time += pit_time
                compound = pit_laps[lap]
                tire_age = 0
        results.append((total_time, strategy["driver_id"]))

    results.sort()
    return [driver_id for _, driver_id in results]


def evaluate_models(adj: pd.DataFrame) -> pd.DataFrame:
    rows = []
    alpha_grid = np.linspace(-0.8, 0.8, 33)
    tests = list(iter_test_cases(with_expected=True))

    for model in MODELS:
        for alpha in alpha_grid:
            pred = adj.apply(lambda row: int(lap_delta_for_row(row, alpha, model) < 0), axis=1)
            adjacent_acc = float((pred == adj["late_wins"]).mean())
            hs = adj[(adj["transition"] == "HARD->SOFT") & (adj["old_age_eff"] == 0) & (adj["new_age_eff"] == 1)]
            hs_pred = hs.apply(lambda row: int(lap_delta_for_row(row, alpha, model) < 0), axis=1)
            hs_acc = float((hs_pred == hs["late_wins"]).mean())

            passed = 0
            for race, expected in tests:
                predicted = simulate_race_base_model(race, alpha, model)
                passed += int(predicted == expected["finishing_positions"])

            rows.append(
                {
                    "model": model,
                    "alpha": float(alpha),
                    "adjacent_accuracy": adjacent_acc,
                    "hs_soft11_accuracy": hs_acc,
                    "test_passes": passed,
                }
            )
    return pd.DataFrame(rows)


def plot_mixed_cells(adj: pd.DataFrame, out_path: Path) -> None:
    mixed = (
        adj.groupby(["transition", "temp", "age_old", "age_new"])
        .agg(total=("late_wins", "size"), actual_mean=("late_wins", "mean"))
        .reset_index()
    )
    mixed = mixed[(mixed["total"] >= 6) & (mixed["actual_mean"] > 0) & (mixed["actual_mean"] < 1)].sort_values("total", ascending=False).head(6)

    fig, axes = plt.subplots(2, 3, figsize=(18, 9), constrained_layout=True)
    rng = np.random.default_rng(0)
    for ax, row in zip(axes.flat, mixed.itertuples(index=False), strict=True):
        sub = adj[
            (adj["transition"] == row.transition)
            & (adj["temp"] == row.temp)
            & (adj["age_old"] == row.age_old)
            & (adj["age_new"] == row.age_new)
        ].copy()
        ax.scatter(sub["base"], sub["late_wins"] + rng.normal(0.0, 0.03, size=len(sub)), c=sub["late_wins"], cmap="coolwarm", s=45)
        ax.set_title(f"{row.transition} @ T={row.temp}, ages=({row.age_old},{row.age_new})")
        ax.set_xlabel("Base lap time")
        ax.set_ylabel("Late-pit win")
        ax.grid(alpha=0.2)
    fig.suptitle("Batch 2A: Mixed exact-state cells split by base_lap_time", fontsize=16)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_hs_soft11_heatmap(adj: pd.DataFrame, out_path: Path) -> None:
    sub = adj[(adj["transition"] == "HARD->SOFT") & (adj["old_age_eff"] == 0) & (adj["new_age_eff"] == 1)].copy()
    sub["base_bin"] = sub["base"].round(0)
    heat = sub.groupby(["base_bin", "temp"])["late_wins"].mean().unstack(fill_value=np.nan).sort_index()

    fig, ax = plt.subplots(figsize=(12, 7), constrained_layout=True)
    im = ax.imshow(heat.to_numpy(), aspect="auto", origin="lower", cmap="coolwarm", vmin=0.0, vmax=1.0)
    ax.set_title("Batch 2B: HARD->SOFT with clean hard vs first aged soft lap")
    ax.set_xlabel("Temperature")
    ax.set_ylabel("Base lap time (rounded)")
    x_ticks = np.arange(len(heat.columns))
    y_ticks = np.arange(len(heat.index))
    ax.set_xticks(x_ticks)
    ax.set_xticklabels(heat.columns, rotation=45)
    ax.set_yticks(y_ticks[:: max(1, len(y_ticks) // 10)])
    ax.set_yticklabels(heat.index[:: max(1, len(y_ticks) // 10)])
    fig.colorbar(im, ax=ax, label="Late-pit win rate")
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_scan(scan_df: pd.DataFrame, out_path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(15, 5), constrained_layout=True)
    for model, group in scan_df.groupby("model"):
        axes[0].plot(group["alpha"], group["test_passes"], marker="o", linewidth=1.5, label=model)
        axes[1].plot(group["alpha"], group["adjacent_accuracy"], marker="o", linewidth=1.5, label=f"{model} adjacent")
        axes[1].plot(group["alpha"], group["hs_soft11_accuracy"], linestyle="--", linewidth=1.2, label=f"{model} H->S soft11")

    axes[0].axhline(67, color="black", linewidth=1.0, linestyle=":")
    axes[0].set_title("Batch 2C: Test score under base-scaling candidates")
    axes[0].set_xlabel("alpha")
    axes[0].set_ylabel("Exact test passes")
    axes[0].grid(alpha=0.2)
    axes[0].legend()

    axes[1].set_title("Batch 2D: Adjacent-pair accuracy under base-scaling candidates")
    axes[1].set_xlabel("alpha")
    axes[1].set_ylabel("Accuracy")
    axes[1].set_ylim(0.95, 1.001)
    axes[1].grid(alpha=0.2)
    axes[1].legend(ncol=2, fontsize=8)

    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def write_summary(out_dir: Path, scan_df: pd.DataFrame) -> None:
    best_tests = scan_df.sort_values(["test_passes", "adjacent_accuracy"], ascending=False).head(6)
    lines = [
        "# Batch 2 Summary",
        "",
        "## Hypothesis",
        "",
        "- `base_lap_time` is a missing structural variable, likely interacting with degradation rather than with the whole lap multiplicatively.",
        "",
        "## Minimal Tests",
        "",
        "1. Inspect exact-state cells that should be deterministic under the current model and see whether they split by base.",
        "2. Inspect the dominant `HARD->SOFT` boundary case where the new soft lap is the first lap beyond grace.",
        "3. Run a very small one-parameter scan where degradation scales with base for all compounds or for SOFT only.",
        "",
        "## Best Candidates",
        "",
    ]
    for row in best_tests.itertuples(index=False):
        lines.append(
            f"- model={row.model}, alpha={row.alpha:.3f}, tests={row.test_passes}, adjacent_acc={row.adjacent_accuracy:.6f}, hs_soft11_acc={row.hs_soft11_accuracy:.6f}"
        )
    lines.extend(
        [
            "",
            "## Interim Conclusion",
            "",
            "- If the best base-scaling candidate improves both test score and the `HARD->SOFT` boundary accuracy, base interaction is a real lead.",
            "- If it only improves one narrow cell but hurts global score, base may be a proxy for a more specific missing rule.",
        ]
    )
    (out_dir / "summary.md").write_text("\n".join(lines))


def main() -> None:
    out_dir = artifact_dir()
    adj = load_adjacent_with_meta()
    scan_df = evaluate_models(adj)
    scan_df.to_csv(out_dir / "scan.csv", index=False)
    plot_mixed_cells(adj, out_dir / "exp1_mixed_cells_base.png")
    plot_hs_soft11_heatmap(adj, out_dir / "exp2_hs_soft11_heatmap.png")
    plot_scan(scan_df, out_dir / "exp3_base_scaling_scan.png")
    write_summary(out_dir, scan_df)
    print(out_dir)


if __name__ == "__main__":
    main()
