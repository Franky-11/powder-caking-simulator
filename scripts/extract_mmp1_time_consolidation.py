from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from powder_caking.extractors import extract_mmp1_time_consolidation


def main() -> None:
    repo_root = REPO_ROOT
    workbook = repo_root / "excel" / "2 MMP Zvf.xlsx"
    output_dir = repo_root / "data" / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)

    df = extract_mmp1_time_consolidation(workbook)
    output_path = output_dir / "mmp1_time_consolidation.csv"
    df.to_csv(output_path, index=False)

    summary = (
        df.groupby(["sigma1_kpa", "temperature_c"], dropna=False)
        .agg(n_points=("time_h", "size"), time_min_h=("time_h", "min"), time_max_h=("time_h", "max"))
        .reset_index()
    )

    print(f"Wrote {len(df)} rows to {output_path}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
