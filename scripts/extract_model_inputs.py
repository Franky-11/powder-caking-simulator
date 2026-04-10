from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from powder_caking.extractors import (
    extract_aw_tg_data,
    extract_critical_cake_strength,
    extract_mmp1_kinetics_summary,
    extract_permeation_time_series,
    extract_real_container_logger_profile,
    extract_relative_change_summary,
    extract_table2_scenario_series,
    extract_wdd_arrhenius_parameters,
    extract_wdd_measurement_timeseries,
    extract_wdd_permeability_summary,
)


def main() -> None:
    processed_dir = REPO_ROOT / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    workbook_mmp = REPO_ROOT / "excel" / "2 MMP Zvf.xlsx"
    workbook_uptake = REPO_ROOT / "excel" / "Wasseraufnahme 25 Sack Milchpulver.xlsx"

    outputs = {
        "mmp1_kinetics_summary.csv": extract_mmp1_kinetics_summary(workbook_mmp),
        "relative_change_summary.csv": extract_relative_change_summary(workbook_mmp),
        "aw_tg_data.csv": extract_aw_tg_data(workbook_mmp),
        "critical_cake_strength.csv": extract_critical_cake_strength(workbook_mmp),
        "permeation_time_series.csv": extract_permeation_time_series(workbook_uptake),
        "real_container_logger_profile.csv": extract_real_container_logger_profile(workbook_uptake),
        "table2_scenario_series.csv": extract_table2_scenario_series(workbook_uptake),
        "wdd_permeability_summary.csv": extract_wdd_permeability_summary(workbook_uptake),
        "wdd_arrhenius_parameters.csv": extract_wdd_arrhenius_parameters(workbook_uptake),
        "wdd_measurement_timeseries.csv": extract_wdd_measurement_timeseries(workbook_uptake),
    }

    for filename, frame in outputs.items():
        out_path = processed_dir / filename
        frame.to_csv(out_path, index=False)
        print(f"Wrote {len(frame)} rows to {out_path}")


if __name__ == "__main__":
    main()
