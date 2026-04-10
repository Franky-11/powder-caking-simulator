from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def fit_caking_time_exponential_models(
    kinetics_df: pd.DataFrame,
    time_column: str = "caking_time_20kpa_h",
    min_points: int = 3,
) -> pd.DataFrame:
    """Fit t_cake = a * exp(k * (T - Tg)) per consolidation stress."""

    records: list[dict[str, float | int | str]] = []
    for sigma1_kpa, group in kinetics_df.groupby("sigma1_kpa", sort=True):
        fit_data = group[["t_minus_tg_c", time_column]].dropna()
        if len(fit_data) < min_points:
            continue

        x = fit_data["t_minus_tg_c"].to_numpy(dtype=float)
        y = fit_data[time_column].to_numpy(dtype=float)
        slope, intercept = np.polyfit(x, np.log(y), deg=1)
        y_hat = np.exp(intercept + slope * x)
        r_squared = _r_squared(y, y_hat)

        records.append(
            {
                "sigma1_kpa": float(sigma1_kpa),
                "n_points": int(len(fit_data)),
                "time_column": time_column,
                "a_param": float(np.exp(intercept)),
                "k_param": float(slope),
                "r_squared": float(r_squared),
            }
        )

    return pd.DataFrame.from_records(records).sort_values("sigma1_kpa").reset_index(drop=True)


def fit_caking_rate_exponential_models(
    kinetics_df: pd.DataFrame,
    rate_column: str = "dfc_dt_pa_per_h",
    min_points: int = 3,
) -> pd.DataFrame:
    """Fit dfc/dt = a * exp(k * (T - Tg)) per consolidation stress.

    The fitted rate is in Pa/h when the input column is `dfc_dt_pa_per_h`.
    """

    records: list[dict[str, float | int | str]] = []
    for sigma1_kpa, group in kinetics_df.groupby("sigma1_kpa", sort=True):
        fit_data = group[["t_minus_tg_c", rate_column]].dropna()
        fit_data = fit_data[fit_data[rate_column] > 0]
        if len(fit_data) < min_points:
            continue

        x = fit_data["t_minus_tg_c"].to_numpy(dtype=float)
        y = fit_data[rate_column].to_numpy(dtype=float)
        slope, intercept = np.polyfit(x, np.log(y), deg=1)
        y_hat = np.exp(intercept + slope * x)
        r_squared = _r_squared(y, y_hat)

        records.append(
            {
                "sigma1_kpa": float(sigma1_kpa),
                "n_points": int(len(fit_data)),
                "rate_column": rate_column,
                "a_param_pa_per_h": float(np.exp(intercept)),
                "k_param_per_c": float(slope),
                "r_squared": float(r_squared),
                "fit_equation": "dfc_dt_pa_per_h = a_param_pa_per_h * exp(k_param_per_c * t_minus_tg_c)",
            }
        )

    return pd.DataFrame.from_records(records).sort_values("sigma1_kpa").reset_index(drop=True)


def predict_caking_time_hours(t_minus_tg_c: float, a_param: float, k_param: float) -> float:
    return float(a_param * np.exp(k_param * t_minus_tg_c))


def predict_caking_rate_pa_per_h(t_minus_tg_c: float, a_param_pa_per_h: float, k_param_per_c: float) -> float:
    return float(a_param_pa_per_h * np.exp(k_param_per_c * t_minus_tg_c))


def load_kinetics_summary(processed_dir: str | Path) -> pd.DataFrame:
    processed_dir = Path(processed_dir)
    return pd.read_csv(processed_dir / "mmp1_kinetics_summary.csv")


def _r_squared(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    if ss_tot == 0:
        return 1.0
    return 1.0 - (ss_res / ss_tot)
