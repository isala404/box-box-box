from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.common import build_driver_summaries, iter_historical_races


def artifact_dir() -> Path:
    stamp = datetime.now().strftime("batch2_%Y%m%d_%H%M%S")
    root = Path(__file__).resolve().parent / "artifacts" / stamp
    root.mkdir(parents=True, exist_ok=True)
    return root


def extract_hm_vs_sm() -> pd.DataFrame:
    rows = []
    for race in iter_historical_races():
        summaries = [row for row in build_driver_summaries(race) if row.pit_count == 1]
        hm = [row for row in summaries if row.transition == "HARD->MEDIUM"]
        sm = [row for row in summaries if row.transition == "SOFT->MEDIUM"]
        for left in hm:
            for right in sm:
                rows.append(
                    {
                        "race_id": left.race_id,
                        "temp": left.temp,
                        "total_laps": left.total_laps,
                        "hm_pit": left.stint_lengths[0],
                        "sm_pit": right.stint_lengths[0],
                        "hm_medium_len": left.stint_lengths[1],
                        "sm_medium_len": right.stint_lengths[1],
                        "actual_hm_wins": int(left.true_rank < right.true_rank),
                        "baseline_hm_wins": int(left.predicted_rank < right.predicted_rank),
                        "baseline_margin": left.total_time_inline - right.total_time_inline,
                    }
                )
    return pd.DataFrame(rows)


def extract_adjacent_boundary_errors() -> pd.DataFrame:
    path = ROOT / "analysis" / "artifacts" / "batch1_20260318_214119" / "adjacent_one_stop_pairs.csv.gz"
    df = pd.read_csv(path)
    focus = df[df["transition"].isin(["SOFT->HARD", "HARD->SOFT", "HARD->MEDIUM", "SOFT->MEDIUM"])].copy()
    focus["model_error"] = (focus["late_wins"] != focus["baseline_late_wins"]).astype(int)
    return focus


def _heatmap(ax, table: pd.DataFrame, title: str, vmin: float, vmax: float, cmap: str) -> None:
    im = ax.imshow(table.to_numpy(), aspect="auto", origin="lower", interpolation="nearest", cmap=cmap, vmin=vmin, vmax=vmax)
    ax.set_title(title)
    ax.set_xlabel(table.columns.name or "x")
    ax.set_ylabel(table.index.name or "y")
    x_ticks = np.arange(len(table.columns))
    y_ticks = np.arange(0, len(table.index), max(1, len(table.index) // 8))
    ax.set_xticks(x_ticks[:: max(1, len(x_ticks) // 8)])
    ax.set_xticklabels(table.columns[:: max(1, len(x_ticks) // 8)], rotation=45)
    ax.set_yticks(y_ticks)
    ax.set_yticklabels(table.index[y_ticks])
    return im


def plot_hm_vs_sm(df: pd.DataFrame, out_path: Path) -> dict[str, float]:
    focus = df[df["temp"].between(27, 31)].copy()
    focus["model_error"] = (focus["actual_hm_wins"] != focus["baseline_hm_wins"]).astype(int)

    fig, axes = plt.subplots(2, 2, figsize=(14, 12), constrained_layout=True)
    actual_by_pit = focus.pivot_table(index="hm_pit", columns="sm_pit", values="actual_hm_wins", aggfunc="mean").sort_index().sort_index(axis=1)
    error_by_pit = focus.pivot_table(index="hm_pit", columns="sm_pit", values="model_error", aggfunc="mean").sort_index().sort_index(axis=1)
    actual_by_medium = focus.pivot_table(index="hm_medium_len", columns="sm_medium_len", values="actual_hm_wins", aggfunc="mean").sort_index().sort_index(axis=1)
    error_by_medium = focus.pivot_table(index="hm_medium_len", columns="sm_medium_len", values="model_error", aggfunc="mean").sort_index().sort_index(axis=1)

    im0 = _heatmap(axes[0, 0], actual_by_pit, "Experiment 6A: Actual HARD->MEDIUM win rate by pit geometry (T 27-31)", 0.0, 1.0, "coolwarm")
    im1 = _heatmap(axes[0, 1], error_by_pit, "Experiment 6B: Model error rate by pit geometry (T 27-31)", 0.0, max(0.05, np.nanmax(error_by_pit.to_numpy())), "magma")
    im2 = _heatmap(axes[1, 0], actual_by_medium, "Experiment 6C: Actual win rate by final MEDIUM stint lengths", 0.0, 1.0, "coolwarm")
    im3 = _heatmap(axes[1, 1], error_by_medium, "Experiment 6D: Model error rate by final MEDIUM stint lengths", 0.0, max(0.05, np.nanmax(error_by_medium.to_numpy())), "magma")
    fig.colorbar(im0, ax=axes[0, 0], shrink=0.8)
    fig.colorbar(im1, ax=axes[0, 1], shrink=0.8)
    fig.colorbar(im2, ax=axes[1, 0], shrink=0.8)
    fig.colorbar(im3, ax=axes[1, 1], shrink=0.8)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)

    return {
        "overall_acc": float((df["actual_hm_wins"] == df["baseline_hm_wins"]).mean()),
        "focused_acc": float((focus["actual_hm_wins"] == focus["baseline_hm_wins"]).mean()),
        "focused_mean_abs_margin": float(focus["baseline_margin"].abs().mean()),
    }


def plot_boundary_errors(df: pd.DataFrame, out_path: Path) -> dict[str, float]:
    focus = df[df["model_error"] == 1].copy()
    fig, axes = plt.subplots(1, 3, figsize=(18, 5), constrained_layout=True)

    for transition, group in focus.groupby("transition"):
        axes[0].scatter(group["temp"], group["age_old"], s=24, alpha=0.65, label=transition)
    axes[0].set_title("Experiment 7A: Adjacent-pair error cells")
    axes[0].set_xlabel("Temperature")
    axes[0].set_ylabel("Old tire age")
    axes[0].legend(fontsize=8)

    for transition, group in df.groupby("transition"):
        sample = group.sample(min(len(group), 3000), random_state=0)
        axes[1].scatter(sample["baseline_single_lap_margin"], sample["late_wins"], s=6, alpha=0.08, label=transition)
    axes[1].scatter(focus["baseline_single_lap_margin"], focus["late_wins"], s=30, color="black", label="errors")
    axes[1].axvline(0.0, color="black", linewidth=1.0)
    axes[1].set_title("Experiment 7B: Error cells sit near the margin boundary")
    axes[1].set_xlabel("Baseline single-lap margin")
    axes[1].set_ylabel("Late-pit win")

    top_cells = (
        focus.assign(cell=focus["transition"] + f" @ T=" + focus["temp"].astype(str) + ", ages " + focus["age_old"].astype(str) + "/" + focus["age_new"].astype(str))
        .groupby("cell")
        .size()
        .sort_values(ascending=False)
        .head(12)
    )
    axes[2].barh(top_cells.index[::-1], top_cells.values[::-1], color="slateblue")
    axes[2].set_title("Experiment 7C: Dominant exact error cells")
    axes[2].set_xlabel("Count")

    fig.savefig(out_path, dpi=180)
    plt.close(fig)

    counts = Counter(focus["transition"])
    return {
        "error_rows": float(len(focus)),
        "soft_hard_share": float((counts["SOFT->HARD"] + counts["HARD->SOFT"]) / max(1, len(focus))),
        "median_abs_margin_error": float(focus["baseline_single_lap_margin"].abs().median()),
    }


def write_summary(out_dir: Path, hm_sm: pd.DataFrame, boundary: pd.DataFrame, metrics: dict[str, dict[str, float]]) -> None:
    lines = [
        "# Batch 2 Summary",
        "",
        "## Hypotheses",
        "",
        "1. `HARD->MEDIUM` vs `SOFT->MEDIUM` errors are a stint-geometry issue, not a mirror/tie issue.",
        "2. Remaining adjacent-pair mistakes are concentrated on a few exact `SOFT<->HARD` and related boundary cells.",
        "",
        "## Dataset Sizes",
        "",
        f"- HARD->MEDIUM vs SOFT->MEDIUM pairs: `{len(hm_sm):,}`",
        f"- Focused adjacent-pair rows: `{len(boundary):,}`",
        "",
        "## Conclusions",
        "",
        f"- Experiment 6: {metrics['exp6']}",
        f"- Experiment 7: {metrics['exp7']}",
        "",
        "## Updated Belief",
        "",
        "- The current miss pattern looks more like exact balance/threshold recovery than a missing broad nonlinear term.",
        "- The most suspicious structural corner remains the `SOFT<->HARD` boundary neighborhood, where small changes can flip exact cells repeatedly.",
    ]
    (out_dir / "summary.md").write_text("\n".join(lines))


def main() -> None:
    out_dir = artifact_dir()
    hm_sm = extract_hm_vs_sm()
    boundary = extract_adjacent_boundary_errors()

    hm_sm.to_csv(out_dir / "hm_vs_sm_pairs.csv.gz", index=False, compression="gzip")
    boundary.to_csv(out_dir / "boundary_focus_pairs.csv.gz", index=False, compression="gzip")

    metrics = {
        "exp6": plot_hm_vs_sm(hm_sm, out_dir / "exp6_hm_vs_sm_geometry.png"),
        "exp7": plot_boundary_errors(boundary, out_dir / "exp7_boundary_errors.png"),
    }
    write_summary(out_dir, hm_sm, boundary, metrics)
    print(out_dir)


if __name__ == "__main__":
    main()
