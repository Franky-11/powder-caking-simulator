from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from powder_caking.climate import ClimateProfile, ClimateSegment, climate_preset_names, load_climate_preset


class ClimateSegmentProfileTests(unittest.TestCase):
    def test_builds_piecewise_constant_profile_from_segments(self) -> None:
        profile = ClimateProfile.from_segments(
            [
                ClimateSegment(duration_d=1.0, temperature_c=20.0, relative_humidity_pct=60.0, label="warehouse"),
                ClimateSegment(duration_d=0.5, temperature_c=30.0, relative_humidity_pct=80.0, label="sea"),
            ],
            dt_d=0.5,
        )

        df = profile.to_dataframe()

        self.assertEqual(df["time_d"].tolist(), [0.0, 0.5, 1.0, 1.5])
        self.assertEqual(df["temperature_c"].tolist(), [20.0, 20.0, 30.0, 30.0])
        self.assertEqual(df["relative_humidity_pct"].tolist(), [60.0, 60.0, 80.0, 80.0])
        self.assertEqual(df["label"].tolist(), ["warehouse", "warehouse", "sea", "sea"])
        self.assertAlmostEqual(profile.duration_d, 1.5)

    def test_rejects_invalid_segment_humidity(self) -> None:
        with self.assertRaises(ValueError):
            ClimateSegment(duration_d=1.0, temperature_c=20.0, relative_humidity_pct=101.0)


class ClimateCsvProfileTests(unittest.TestCase):
    def test_imports_profile_from_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "profile.csv"
            pd.DataFrame(
                {
                    "time_d": [0.0, 0.5, 1.0],
                    "temperature_c": [21.0, 22.0, 23.0],
                    "relative_humidity_pct": [60.0, 61.0, 62.0],
                }
            ).to_csv(csv_path, index=False)

            profile = ClimateProfile.from_csv(csv_path)

        df = profile.to_dataframe()
        self.assertEqual(list(df.columns), ["time_d", "temperature_c", "relative_humidity_pct"])
        self.assertEqual(df["temperature_c"].tolist(), [21.0, 22.0, 23.0])
        self.assertAlmostEqual(profile.duration_d, 1.0)

    def test_imports_timestamp_csv_as_elapsed_days(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "profile.csv"
            pd.DataFrame(
                {
                    "timestamp": ["2024-03-01 08:00:00", "2024-03-01 20:00:00", "2024-03-02 08:00:00"],
                    "temperature_c": [22.0, 25.0, 21.0],
                    "relative_humidity_pct": [65.0, 55.0, 70.0],
                }
            ).to_csv(csv_path, index=False)

            profile = ClimateProfile.from_csv(csv_path)

        self.assertEqual(profile.to_dataframe()["time_d"].tolist(), [0.0, 0.5, 1.0])

    def test_rejects_non_monotonic_time(self) -> None:
        frame = pd.DataFrame(
            {
                "time_d": [0.0, 1.0, 0.5],
                "temperature_c": [21.0, 22.0, 23.0],
                "relative_humidity_pct": [60.0, 61.0, 62.0],
            }
        )

        with self.assertRaises(ValueError):
            ClimateProfile(frame)

    def test_warns_for_irregular_time_steps(self) -> None:
        frame = pd.DataFrame(
            {
                "time_d": [0.0, 0.5, 1.25, 1.5],
                "temperature_c": [21.0, 22.0, 23.0, 24.0],
                "relative_humidity_pct": [60.0, 61.0, 62.0, 63.0],
            }
        )

        profile = ClimateProfile(frame)

        self.assertIn(
            "time_d step size is irregular; resampling will use linear interpolation",
            profile.validation_warnings,
        )

    def test_warns_for_implausible_temperature_range(self) -> None:
        frame = pd.DataFrame(
            {
                "time_d": [0.0, 1.0],
                "temperature_c": [21.0, 85.0],
                "relative_humidity_pct": [60.0, 61.0],
            }
        )

        profile = ClimateProfile(frame)

        self.assertIn(
            "temperature_c contains values outside the expected range -20..80 degC",
            profile.validation_warnings,
        )


class ClimateProfileProcessingTests(unittest.TestCase):
    def test_resamples_profile_to_requested_step_width(self) -> None:
        profile = ClimateProfile(
            pd.DataFrame(
                {
                    "time_d": [0.0, 1.0, 2.0],
                    "temperature_c": [20.0, 30.0, 50.0],
                    "relative_humidity_pct": [60.0, 80.0, 40.0],
                }
            )
        )

        resampled = profile.resample(dt_d=0.5)
        df = resampled.to_dataframe()

        self.assertEqual(df["time_d"].tolist(), [0.0, 0.5, 1.0, 1.5, 2.0])
        self.assertEqual(df["temperature_c"].tolist(), [20.0, 25.0, 30.0, 40.0, 50.0])
        self.assertEqual(df["relative_humidity_pct"].tolist(), [60.0, 70.0, 80.0, 60.0, 40.0])

    def test_resample_preserves_profile_duration_when_step_does_not_divide_evenly(self) -> None:
        profile = ClimateProfile(
            pd.DataFrame(
                {
                    "time_d": [0.0, 1.0],
                    "temperature_c": [20.0, 22.0],
                    "relative_humidity_pct": [60.0, 62.0],
                }
            )
        )

        resampled = profile.resample(dt_d=0.4)
        df = resampled.to_dataframe()

        self.assertEqual(df["time_d"].tolist(), [0.0, 0.4, 0.8, 1.0])
        self.assertAlmostEqual(resampled.duration_d, 1.0)

    def test_preview_reports_duration_and_summary_statistics(self) -> None:
        profile = ClimateProfile(
            pd.DataFrame(
                {
                    "time_d": [0.0, 1.0, 2.0],
                    "temperature_c": [20.0, 30.0, 40.0],
                    "relative_humidity_pct": [60.0, 70.0, 80.0],
                }
            )
        )

        preview = profile.preview()

        self.assertAlmostEqual(preview.duration_d, 2.0)
        self.assertEqual(preview.n_points, 3)
        self.assertAlmostEqual(preview.temperature_min_c, 20.0)
        self.assertAlmostEqual(preview.temperature_max_c, 40.0)
        self.assertAlmostEqual(preview.temperature_mean_c, 30.0)
        self.assertAlmostEqual(preview.relative_humidity_min_pct, 60.0)
        self.assertAlmostEqual(preview.relative_humidity_max_pct, 80.0)
        self.assertAlmostEqual(preview.relative_humidity_mean_pct, 70.0)


class ClimatePresetTests(unittest.TestCase):
    def test_lists_new_climate_presets(self) -> None:
        self.assertEqual(
            set(climate_preset_names()),
            {
                "neutral_reference_transport",
                "tropical_sea_transport_southeast_asia",
                "hot_humid_worst_case",
                "day_night_container_profile",
                "real_container_logger_profile",
            },
        )

    def test_builds_neutral_reference_transport_preset(self) -> None:
        profile = ClimateProfile.neutral_reference_transport(dt_d=1.0)
        df = profile.to_dataframe()

        self.assertAlmostEqual(profile.duration_d, 65.0)
        self.assertEqual(df.iloc[0]["temperature_c"], 20.0)
        self.assertEqual(df.iloc[-1]["relative_humidity_pct"], 70.0)
        self.assertEqual(profile.source, "neutral_reference_transport")

    def test_builds_tropical_transport_preset(self) -> None:
        profile = ClimateProfile.tropical_sea_transport_southeast_asia(dt_d=1.0)
        df = profile.to_dataframe()

        self.assertAlmostEqual(profile.duration_d, 81.0)
        self.assertEqual(df.iloc[-1]["temperature_c"], 32.0)
        self.assertEqual(df.iloc[-1]["relative_humidity_pct"], 85.0)

    def test_builds_hot_humid_worst_case_preset(self) -> None:
        profile = load_climate_preset("hot_humid_worst_case", dt_d=1.0)
        preview = profile.preview()

        self.assertAlmostEqual(preview.duration_d, 75.0)
        self.assertAlmostEqual(preview.temperature_max_c, 35.0)
        self.assertAlmostEqual(preview.relative_humidity_max_pct, 90.0)

    def test_builds_day_night_container_profile_preset(self) -> None:
        profile = ClimateProfile.day_night_container_profile(days=2, dt_d=0.5)
        df = profile.to_dataframe()

        self.assertEqual(df["time_d"].tolist(), [0.0, 0.5, 1.0, 1.5, 2.0])
        self.assertEqual(df["temperature_c"].tolist(), [35.0, 24.0, 35.0, 24.0, 24.0])
        self.assertEqual(df["relative_humidity_pct"].tolist(), [65.0, 90.0, 65.0, 90.0, 90.0])

    def test_rejects_unknown_preset_name(self) -> None:
        with self.assertRaises(ValueError):
            load_climate_preset("missing")


class RealContainerLoggerProfileTests(unittest.TestCase):
    def test_loads_processed_real_container_logger_profile(self) -> None:
        profile = ClimateProfile.real_container_logger_profile()
        df = profile.to_dataframe()

        self.assertEqual(len(df), 2378)
        self.assertEqual(list(df.columns), ["time_d", "temperature_c", "relative_humidity_pct"])
        self.assertAlmostEqual(df.iloc[0]["temperature_c"], 20.71)
        self.assertAlmostEqual(df.iloc[0]["relative_humidity_pct"], 59.689)
        self.assertAlmostEqual(df.iloc[-1]["time_d"], 99.08754052801804)
        self.assertTrue(df["time_d"].is_monotonic_increasing)
        self.assertEqual(profile.source, "real_container_logger_profile")

    def test_resampled_real_container_logger_profile_does_not_expose_path(self) -> None:
        profile = ClimateProfile.real_container_logger_profile().resample(1.0)

        self.assertEqual(profile.source, "real_container_logger_profile:resampled")
        self.assertNotIn("/", profile.source)
        self.assertNotIn("\\", profile.source)


if __name__ == "__main__":
    unittest.main()
