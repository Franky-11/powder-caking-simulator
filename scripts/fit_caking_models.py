from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from powder_caking.models import (
    fit_caking_rate_exponential_models,
    fit_caking_time_exponential_models,
    load_kinetics_summary,
)


def main() -> None:
    processed_dir = REPO_ROOT / "data" / "processed"
    kinetics_df = load_kinetics_summary(processed_dir)
    outputs = {
        "caking_time_fit_params.csv": fit_caking_time_exponential_models(
            kinetics_df, time_column="caking_time_20kpa_h"
        ),
        "caking_rate_fit_params.csv": fit_caking_rate_exponential_models(
            kinetics_df, rate_column="dfc_dt_pa_per_h"
        ),
    }

    for filename, frame in outputs.items():
        out_path = processed_dir / filename
        frame.to_csv(out_path, index=False)
        print(f"Wrote {len(frame)} rows to {out_path}")
        print(frame.to_string(index=False))


if __name__ == "__main__":
    main()
