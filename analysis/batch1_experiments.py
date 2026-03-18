from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.common import (
    COMPOUNDS,
    DEFAULT_PARAMS,
    build_driver_summaries,
    is_grace_edge,
    is_mirror_pair,
    iter_historical_races,
    iter_test_cases,
    lap_time,
    pairwise_driver_rows,
    predicted_winner,
    relative_finish_winner,
)


TRANSITIONS = [(a, b) for a in COMPOUNDS for b in COMPOUNDS if a != b]


def artifact_dir() -> Path:
    stamp = datetime.now().strftime("batch1_%Y%m%d_%H%M%S")
    root = Path(__file__).resolve().parent / "artifacts" / stamp
    root.mkdir(parents=True, exist_ok=True)
    return root


def summarize_race_failures() -> tuple[pd.DataFrame, pd.DataFrame]:
    tests = []
    inversions = []
    for race, expected in iter_test_cases(with_expected=True):
        race = {**race, "finishing_positions": expected["finishing_positions"]}
        summaries = build_driver_summaries(race)
        expected_order = expected["finishing_positions"]
        predicted_order = sorted(summaries, key=lambda row: row.predicted_rank)
        predicted_ids = [row.driver_id for row in predicted_order]
        passed = predicted_ids == expected_order
        expected_rank = {driver_id: idx for idx, driver_id in enumerate(expected_order)}
        summary_by_id = {row.driver_id: row for row in summaries}

        inversion_count = 0
        mirror_count = 0
        grace_count = 0
        same_stop_count = 0
        for left, right in pairwise_driver_rows(summaries):
            pred_sign = left.predicted_rank < right.predicted_rank
            true_sign = left.true_rank < right.true_rank
            if pred_sign == true_sign:
                continue
            inversion_count += 1
            mirror_flag = is_mirror_pair(left, right)
            grace_flag = is_grace_edge(left) or is_grace_edge(right)
            same_stop_flag = left.pit_count == right.pit_count
            mirror_count += int(mirror_flag)
            grace_count += int(grace_flag)
            same_stop_count += int(same_stop_flag)
            inversions.append(
                {
                    "race_id": race["race_id"],
                    "temp": race["race_config"]["track_temp"],
                    "total_laps": race["race_config"]["total_laps"],
                    "left_driver": left.driver_id,
                    "right_driver": right.driver_id,
                    "left_transition": left.transition,
                    "right_transition": right.transition,
                    "left_pits": left.pit_count,
                    "right_pits": right.pit_count,
                    "mirror": mirror_flag,
                    "grace_edge": grace_flag,
                    "same_stop_count": same_stop_flag,
                }
            )

        tests.append(
            {
                "race_id": race["race_id"],
                "temp": race["race_config"]["track_temp"],
                "total_laps": race["race_config"]["total_laps"],
                "passed": passed,
                "inversion_count": inversion_count,
                "mirror_inversions": mirror_count,
                "grace_edge_inversions": grace_count,
                "same_stop_inversions": same_stop_count,
            }
        )
    return pd.DataFrame(tests), pd.DataFrame(inversions)


def extract_adjacent_one_stop_pairs(limit_races: int | None = None) -> pd.DataFrame:
    rows = []
    for race in iter_historical_races(limit_races=limit_races):
        summaries = [row for row in build_driver_summaries(race) if row.pit_count == 1]
        buckets = defaultdict(list)
        for row in summaries:
            buckets[row.compounds].append(row)

        for compounds, group in buckets.items():
            for left, right in pairwise_driver_rows(group):
                p_left = left.pit_laps[0]
                p_right = right.pit_laps[0]
                if abs(p_left - p_right) != 1:
                    continue

                early = left if p_left < p_right else right
                late = right if early is left else left
                early_p = early.pit_laps[0]
                late_p = late.pit_laps[0]
                start, end = compounds
                age_old = late_p
                age_new = early.total_laps - early_p
                true_late_wins = int(relative_finish_winner(late, early) is late)
                pred_late_wins = int(predicted_winner(late, early) is late)
                single_lap_margin = lap_time(start, age_old, late.temp) - lap_time(end, age_new, late.temp)

                rows.append(
                    {
                        "race_id": late.race_id,
                        "temp": late.temp,
                        "total_laps": late.total_laps,
                        "start": start,
                        "end": end,
                        "transition": f"{start}->{end}",
                        "early_driver": early.driver_id,
                        "late_driver": late.driver_id,
                        "early_pit": early_p,
                        "late_pit": late_p,
                        "age_old": age_old,
                        "age_new": age_new,
                        "old_age_eff": max(0, age_old - DEFAULT_PARAMS["grace"][start]),
                        "new_age_eff": max(0, age_new - DEFAULT_PARAMS["grace"][end]),
                        "new_lap_clean": age_new <= DEFAULT_PARAMS["grace"][end],
                        "late_wins": true_late_wins,
                        "baseline_late_wins": pred_late_wins,
                        "baseline_single_lap_margin": single_lap_margin,
                        "baseline_margin_sign_correct": int((single_lap_margin < 0) == bool(true_late_wins)),
                    }
                )
    return pd.DataFrame(rows)


def extract_mirror_pairs(limit_races: int | None = None) -> pd.DataFrame:
    rows = []
    for race in iter_historical_races(limit_races=limit_races):
        summaries = [row for row in build_driver_summaries(race) if row.pit_count == 1]
        for left, right in pairwise_driver_rows(summaries):
            if not is_mirror_pair(left, right):
                continue
            winner = relative_finish_winner(left, right)
            predicted = predicted_winner(left, right)
            rows.append(
                {
                    "race_id": left.race_id,
                    "temp": left.temp,
                    "total_laps": left.total_laps,
                    "left_driver": left.driver_id,
                    "right_driver": right.driver_id,
                    "left_transition": left.transition,
                    "right_transition": right.transition,
                    "winner_driver": winner.driver_id,
                    "predicted_driver": predicted.driver_id,
                    "predicted_matches_truth": int(predicted.driver_id == winner.driver_id),
                    "inline_diff": left.total_time_inline - right.total_time_inline,
                    "closed_diff": left.total_time_closed - right.total_time_closed,
                    "inline_abs_diff": abs(left.total_time_inline - right.total_time_inline),
                    "closed_abs_diff": abs(left.total_time_closed - right.total_time_closed),
                    "both_grace_clean": int(
                        left.stint_lengths[0] <= DEFAULT_PARAMS["grace"][left.compounds[0]]
                        and left.stint_lengths[1] <= DEFAULT_PARAMS["grace"][left.compounds[1]]
                        and right.stint_lengths[0] <= DEFAULT_PARAMS["grace"][right.compounds[0]]
                        and right.stint_lengths[1] <= DEFAULT_PARAMS["grace"][right.compounds[1]]
                    ),
                }
            )
    return pd.DataFrame(rows)


def plot_adjacent_heatmaps(df: pd.DataFrame, out_path: Path) -> dict[str, float]:
    clean_df = df[df["new_lap_clean"]].copy()
    boundary_rates = {}
    fig, axes = plt.subplots(2, 3, figsize=(18, 10), constrained_layout=True)
    for ax, (start, end) in zip(axes.flat, TRANSITIONS, strict=True):
        sub = clean_df[(clean_df["start"] == start) & (clean_df["end"] == end)]
        grouped = (
            sub.groupby(["age_old", "temp"])
            .agg(win_rate=("late_wins", "mean"), count=("late_wins", "size"))
            .reset_index()
        )
        if grouped.empty:
            ax.set_axis_off()
            continue
        pivot = grouped.pivot(index="age_old", columns="temp", values="win_rate").sort_index()
        c = ax.imshow(
            pivot.to_numpy(),
            aspect="auto",
            origin="lower",
            interpolation="nearest",
            cmap="coolwarm",
            vmin=0.0,
            vmax=1.0,
        )
        ax.set_title(f"{start} -> {end} (clean new lap)")
        x_ticks = np.arange(len(pivot.columns))
        y_ticks = np.arange(0, len(pivot.index), max(1, len(pivot.index) // 8))
        ax.set_xticks(x_ticks[:: max(1, len(x_ticks) // 8)])
        ax.set_xticklabels(pivot.columns[:: max(1, len(x_ticks) // 8)], rotation=45)
        ax.set_yticks(y_ticks)
        ax.set_yticklabels(pivot.index[y_ticks])
        ax.set_xlabel("Temperature")
        ax.set_ylabel("Old tire age on extra lap")

        boundary = (
            grouped.sort_values(["temp", "age_old"])
            .groupby("temp")
            .apply(
                lambda g: g.loc[g["win_rate"] >= 0.5, "age_old"].max()
                if (g["win_rate"] >= 0.5).any()
                else np.nan
            )
        )
        boundary_rates[f"{start}->{end}"] = float(np.nanmean(boundary.to_numpy()))
    fig.colorbar(c, ax=axes.ravel().tolist(), shrink=0.82, label="Late-pit win rate")
    fig.suptitle("Experiment 1: Adjacent one-lap pit shift boundaries", fontsize=16)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    return boundary_rates


def plot_boundary_and_temp_factor(df: pd.DataFrame, out_path: Path) -> dict[str, float]:
    clean_df = df[df["new_lap_clean"]].copy()
    fig, axes = plt.subplots(2, 1, figsize=(14, 10), constrained_layout=True)
    inferred_rows = []

    for start, end in TRANSITIONS:
        sub = clean_df[(clean_df["start"] == start) & (clean_df["end"] == end)]
        if sub.empty:
            continue
        grouped = (
            sub.groupby(["temp", "age_old"])
            .agg(win_rate=("late_wins", "mean"), count=("late_wins", "size"))
            .reset_index()
        )
        boundary = (
            grouped.sort_values(["temp", "age_old"])
            .groupby("temp")
            .apply(
                lambda g: g.loc[g["win_rate"] >= 0.5, "age_old"].max()
                if (g["win_rate"] >= 0.5).any() and (g["win_rate"] < 0.5).any()
                else np.nan
            )
            .dropna()
        )
        if boundary.empty:
            continue
        label = f"{start}->{end}"
        axes[0].plot(boundary.index, boundary.values, marker="o", linewidth=1.5, label=label)

        age_eff = boundary.values - DEFAULT_PARAMS["grace"][start]
        valid = age_eff > 0
        if valid.any():
            numerator = DEFAULT_PARAMS["off"][end] - DEFAULT_PARAMS["off"][start]
            inferred = numerator / (DEFAULT_PARAMS["rate"][start] * age_eff[valid])
            inferred_rows.extend(
                {"transition": label, "temp": int(temp), "tf_inferred": float(val)}
                for temp, val in zip(boundary.index[valid], inferred, strict=True)
            )

    temps = sorted(df["temp"].unique())
    power_curve = [(temp / 20.0) ** DEFAULT_PARAMS["temp_power"] for temp in temps]
    piecewise_curve = []
    for temp in temps:
        if temp <= 24:
            piecewise_curve.append(0.8 + 0.035 * (temp - 18))
        elif temp <= 34:
            piecewise_curve.append(1.03 + 0.045 * (temp - 24))
        else:
            piecewise_curve.append(1.48 + 0.035 * (temp - 34))

    axes[0].set_title("Experiment 2A: Boundary age vs temperature")
    axes[0].set_xlabel("Temperature")
    axes[0].set_ylabel("Max old-tire age where late pit still wins")
    axes[0].legend(ncol=3, fontsize=8)
    axes[0].grid(alpha=0.2)

    inferred_df = pd.DataFrame(inferred_rows)
    if not inferred_df.empty:
        for transition, group in inferred_df.groupby("transition"):
            axes[1].plot(group["temp"], group["tf_inferred"], marker="o", linewidth=1.2, alpha=0.7, label=transition)
        median = inferred_df.groupby("temp")["tf_inferred"].median().reindex(temps)
        axes[1].plot(temps, power_curve, color="black", linewidth=2.2, label="baseline power law")
        axes[1].plot(temps, piecewise_curve, color="gray", linestyle="--", linewidth=1.4, label="piecewise placeholder")
        axes[1].plot(temps, median.to_numpy(), color="goldenrod", linewidth=2.0, label="median inferred tf")
        axes[1].set_ylim(bottom=0.0)
    axes[1].set_title("Experiment 2B: Inferred per-temperature factor from clean-region boundaries")
    axes[1].set_xlabel("Temperature")
    axes[1].set_ylabel("Inferred temperature factor")
    axes[1].grid(alpha=0.2)
    axes[1].legend(ncol=3, fontsize=8)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)

    return {
        "median_abs_delta_to_power_curve": float(
            np.nanmedian(np.abs(inferred_df["tf_inferred"] - inferred_df["temp"].map(dict(zip(temps, power_curve)))))
        )
        if not inferred_df.empty
        else math.nan
    }


def plot_mirror_pairs(df: pd.DataFrame, out_path: Path) -> dict[str, float]:
    fig, axes = plt.subplots(1, 3, figsize=(18, 5), constrained_layout=True)
    axes[0].hist(df["inline_abs_diff"], bins=50, color="steelblue")
    axes[0].set_title("Experiment 3A: Inline diff magnitude")
    axes[0].set_xlabel("|inline total-time diff|")
    axes[0].set_ylabel("Count")
    axes[0].set_yscale("log")

    axes[1].scatter(df["temp"], df["inline_diff"], s=12, alpha=0.5, c=df["predicted_matches_truth"], cmap="coolwarm")
    axes[1].axhline(0.0, color="black", linewidth=1.0)
    axes[1].set_title("Experiment 3B: Inline diff by temperature")
    axes[1].set_xlabel("Temperature")
    axes[1].set_ylabel("left - right inline time")

    sample = df.copy()
    sample["closed_zero"] = np.isclose(sample["closed_diff"], 0.0, atol=1e-9)
    counts = sample[["predicted_matches_truth", "closed_zero", "both_grace_clean"]].sum()
    axes[2].bar(
        ["pred=truth", "closed≈0", "both clean"],
        [counts["predicted_matches_truth"], counts["closed_zero"], counts["both_grace_clean"]],
        color=["forestgreen", "slateblue", "darkorange"],
    )
    axes[2].set_title("Experiment 3C: Mirror-pair diagnostics")
    axes[2].set_ylabel("Count")
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    return {
        "mirror_pred_accuracy": float(df["predicted_matches_truth"].mean()),
        "mirror_median_inline_abs_diff": float(df["inline_abs_diff"].median()),
        "mirror_share_closed_zero": float(np.isclose(df["closed_diff"], 0.0, atol=1e-9).mean()),
    }


def plot_test_failures(test_df: pd.DataFrame, inv_df: pd.DataFrame, out_path: Path) -> dict[str, float]:
    fig, axes = plt.subplots(1, 3, figsize=(18, 5), constrained_layout=True)

    fail_rate = (
        test_df.assign(failed=~test_df["passed"])
        .groupby(["total_laps", "temp"])["failed"]
        .mean()
        .unstack(fill_value=np.nan)
        .sort_index()
    )
    im = axes[0].imshow(fail_rate.to_numpy(), aspect="auto", origin="lower", cmap="magma", vmin=0.0, vmax=1.0)
    axes[0].set_title("Experiment 4A: Test fail rate by laps x temp")
    axes[0].set_xlabel("Temperature")
    axes[0].set_ylabel("Total laps")
    xticks = np.arange(len(fail_rate.columns))
    yticks = np.arange(0, len(fail_rate.index), max(1, len(fail_rate.index) // 8))
    axes[0].set_xticks(xticks[:: max(1, len(xticks) // 8)])
    axes[0].set_xticklabels(fail_rate.columns[:: max(1, len(xticks) // 8)], rotation=45)
    axes[0].set_yticks(yticks)
    axes[0].set_yticklabels(fail_rate.index[yticks])

    fail_only = inv_df.copy()
    pattern_counts = {
        "mirror": int(fail_only["mirror"].sum()),
        "grace_edge": int(fail_only["grace_edge"].sum()),
        "same_stop": int(fail_only["same_stop_count"].sum()),
        "different_stop": int((~fail_only["same_stop_count"]).sum()),
    }
    axes[1].bar(pattern_counts.keys(), pattern_counts.values(), color=["teal", "firebrick", "goldenrod", "gray"])
    axes[1].set_title("Experiment 4B: Inversion cluster counts")
    axes[1].set_ylabel("Count")
    axes[1].tick_params(axis="x", rotation=30)

    top_pairs = (
        fail_only.assign(pair=fail_only["left_transition"] + " vs " + fail_only["right_transition"])
        .groupby("pair")
        .size()
        .sort_values(ascending=False)
        .head(10)
    )
    axes[2].barh(top_pairs.index[::-1], top_pairs.values[::-1], color="mediumpurple")
    axes[2].set_title("Experiment 4C: Top inversion pattern pairs")
    axes[2].set_xlabel("Count")

    fig.colorbar(im, ax=axes[0], shrink=0.8, label="Fail rate")
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    return {
        "test_pass_rate": float(test_df["passed"].mean()),
        "mean_inversions_failed_test": float(test_df.loc[~test_df["passed"], "inversion_count"].mean()),
        "mirror_share_of_inversions": float(inv_df["mirror"].mean()) if not inv_df.empty else math.nan,
    }


def plot_adjacent_residuals(df: pd.DataFrame, out_path: Path) -> dict[str, float]:
    fig, axes = plt.subplots(2, 2, figsize=(16, 10), constrained_layout=True)

    df = df.copy()
    df["model_correct"] = (df["baseline_late_wins"] == df["late_wins"]).astype(int)
    by_transition = (
        df.groupby(["transition", "old_age_eff"])
        .agg(error_rate=("model_correct", lambda s: 1.0 - s.mean()), count=("model_correct", "size"))
        .reset_index()
    )
    for transition, group in by_transition.groupby("transition"):
        axes[0, 0].plot(group["old_age_eff"], group["error_rate"], marker="o", linewidth=1.2, alpha=0.8, label=transition)
    axes[0, 0].set_title("Experiment 5A: Error rate vs old-age past grace")
    axes[0, 0].set_xlabel("Old-age effective laps past grace")
    axes[0, 0].set_ylabel("Baseline single-lap misclassification rate")
    axes[0, 0].legend(ncol=3, fontsize=8)
    axes[0, 0].grid(alpha=0.2)

    age_temp = (
        df.groupby(["old_age_eff", "temp"])
        .agg(error_rate=("model_correct", lambda s: 1.0 - s.mean()))
        .reset_index()
        .pivot(index="old_age_eff", columns="temp", values="error_rate")
        .sort_index()
    )
    im = axes[0, 1].imshow(age_temp.to_numpy(), aspect="auto", origin="lower", cmap="viridis", vmin=0.0, vmax=max(0.1, np.nanmax(age_temp.to_numpy())))
    axes[0, 1].set_title("Experiment 5B: Error heatmap by age_eff x temp")
    axes[0, 1].set_xlabel("Temperature")
    axes[0, 1].set_ylabel("Old-age effective laps past grace")
    x_ticks = np.arange(len(age_temp.columns))
    y_ticks = np.arange(0, len(age_temp.index), max(1, len(age_temp.index) // 8))
    axes[0, 1].set_xticks(x_ticks[:: max(1, len(x_ticks) // 8)])
    axes[0, 1].set_xticklabels(age_temp.columns[:: max(1, len(x_ticks) // 8)], rotation=45)
    axes[0, 1].set_yticks(y_ticks)
    axes[0, 1].set_yticklabels(age_temp.index[y_ticks])

    axes[1, 0].scatter(
        df["baseline_single_lap_margin"],
        df["late_wins"] + np.random.default_rng(0).normal(0.0, 0.03, size=len(df)),
        s=8,
        alpha=0.2,
        c=df["temp"],
        cmap="coolwarm",
    )
    axes[1, 0].axvline(0.0, color="black", linewidth=1.0)
    axes[1, 0].set_title("Experiment 5C: Outcome vs baseline single-lap margin")
    axes[1, 0].set_xlabel("Baseline margin: old lap - new lap")
    axes[1, 0].set_ylabel("Late-pit win")

    clean_vs_dirty = df.groupby("new_lap_clean")["model_correct"].mean()
    axes[1, 1].bar(["clean new lap", "degraded new lap"], [clean_vs_dirty.get(True, np.nan), clean_vs_dirty.get(False, np.nan)], color=["royalblue", "tomato"])
    axes[1, 1].set_ylim(0.0, 1.0)
    axes[1, 1].set_title("Experiment 5D: Baseline accuracy on controlled adjacent pairs")
    axes[1, 1].set_ylabel("Accuracy")

    fig.colorbar(im, ax=axes[0, 1], shrink=0.8, label="Error rate")
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    return {
        "adjacent_pair_accuracy": float(df["model_correct"].mean()),
        "adjacent_clean_accuracy": float(clean_vs_dirty.get(True, math.nan)),
        "adjacent_dirty_accuracy": float(clean_vs_dirty.get(False, math.nan)),
    }


def write_summary(
    out_dir: Path,
    adjacent_df: pd.DataFrame,
    mirror_df: pd.DataFrame,
    test_df: pd.DataFrame,
    inv_df: pd.DataFrame,
    metrics: dict[str, dict[str, float]],
) -> None:
    lines = [
        "# Batch 1 Summary",
        "",
        "## Current Beliefs vs Uncertainties",
        "",
        "- Likely solid: additive compound offsets, grace windows around 10/20/30, lap-by-lap pit timing, and order sensitivity from floating accumulation at least for some mirror cases.",
        "- Re-opened: smooth temperature power law, globally linear degradation without thresholds, and the claim that mirror mismatches are only precision noise.",
        "- Unresolved: whether per-temperature behavior is discrete/piecewise, whether adjacent pit-shift boundaries expose off-by-one rules, and whether current failures cluster around a small set of strategy motifs.",
        "",
        "## Top 5 Experiments",
        "",
        "1. Adjacent one-stop pit-shift heatmaps on clean new laps to expose crisp boundary shapes.",
        "2. Boundary-age extraction and inferred per-temperature factor to test lookup/piecewise vs smooth temperature behavior.",
        "3. Mirror-pair diagnostics comparing inline accumulation with closed-form ties.",
        "4. Test counterexample clustering by temperature, laps, mirror flag, grace-edge flag, and transition pair.",
        "5. Adjacent-pair residual analysis to see whether errors grow with age, temperature, or only at structural edges.",
        "",
        "## Artifacts",
        "",
        f"- Adjacent pairs: `{len(adjacent_df):,}` rows",
        f"- Mirror pairs: `{len(mirror_df):,}` rows",
        f"- Test cases: `{len(test_df):,}` rows",
        f"- Test inversions: `{len(inv_df):,}` rows",
        "",
        "## Experiment Conclusions",
        "",
        f"- Experiment 1: {metrics['exp1']}",
        f"- Experiment 2: {metrics['exp2']}",
        f"- Experiment 3: {metrics['exp3']}",
        f"- Experiment 4: {metrics['exp4']}",
        f"- Experiment 5: {metrics['exp5']}",
        "",
        "## Keep / Discard / Uncertain",
        "",
        "- Keep: adjacent pit-shift analysis as the main evidence source because it reduces whole races to single-lap inequalities.",
        "- Discard for now: any claim that temperature is definitively smooth based only on aggregate score differences.",
        "- Uncertain: whether baseline linear age_eff is actually correct everywhere or only a good local surrogate.",
        "",
        "## Next Highest-Value Experiment",
        "",
        "- Use only the clean-new adjacent pairs to infer a discrete lap-time table order for each compound across `(temperature, age)` and look for exact threshold tables or missing off-by-one indexing.",
    ]
    (out_dir / "summary.md").write_text("\n".join(lines))


def main() -> None:
    out_dir = artifact_dir()
    adjacent_df = extract_adjacent_one_stop_pairs()
    mirror_df = extract_mirror_pairs()
    test_df, inv_df = summarize_race_failures()

    adjacent_df.to_csv(out_dir / "adjacent_one_stop_pairs.csv.gz", index=False, compression="gzip")
    mirror_df.to_csv(out_dir / "mirror_pairs.csv.gz", index=False, compression="gzip")
    test_df.to_csv(out_dir / "test_case_results.csv", index=False)
    inv_df.to_csv(out_dir / "test_inversions.csv", index=False)

    metrics = {
        "exp1": plot_adjacent_heatmaps(adjacent_df, out_dir / "exp1_adjacent_heatmaps.png"),
        "exp2": plot_boundary_and_temp_factor(adjacent_df, out_dir / "exp2_boundary_temp_factor.png"),
        "exp3": plot_mirror_pairs(mirror_df, out_dir / "exp3_mirror_pairs.png"),
        "exp4": plot_test_failures(test_df, inv_df, out_dir / "exp4_test_failures.png"),
        "exp5": plot_adjacent_residuals(adjacent_df, out_dir / "exp5_adjacent_residuals.png"),
    }
    write_summary(out_dir, adjacent_df, mirror_df, test_df, inv_df, metrics)
    print(out_dir)


if __name__ == "__main__":
    main()
