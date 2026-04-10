from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

MMP_WORKBOOK = REPO_ROOT / "excel" / "2 MMP Zvf.xlsx"
UPTAKE_WORKBOOK = REPO_ROOT / "excel" / "Wasseraufnahme 25 Sack Milchpulver.xlsx"
RAW_WORKBOOKS_AVAILABLE = MMP_WORKBOOK.exists() and UPTAKE_WORKBOOK.exists()

from powder_caking.extractors import extract_mmp1_time_consolidation
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
from powder_caking.models import (
    fit_caking_rate_exponential_models,
    fit_caking_time_exponential_models,
    predict_caking_rate_pa_per_h,
    predict_caking_time_hours,
)


@unittest.skipUnless(MMP_WORKBOOK.exists(), "Lokale Excel-Rohdaten fehlen")
class ExtractMmp1TimeConsolidationTests(unittest.TestCase):
    def test_extracts_expected_shape_and_conditions(self) -> None:
        df = extract_mmp1_time_consolidation(MMP_WORKBOOK)

        self.assertEqual(len(df), 44)
        self.assertEqual(set(df["sigma1_kpa"]), {3.1, 11.0, 20.0})

        combos = {
            (row.sigma1_kpa, row.temperature_c): row.n_points
            for row in df.groupby(["sigma1_kpa", "temperature_c"]).size().reset_index(name="n_points").itertuples(index=False)
        }
        expected = {
            (20.0, 50.0): 5,
            (20.0, 47.5): 5,
            (20.0, 45.0): 6,
            (20.0, 42.5): 4,
            (11.0, 50.0): 6,
            (11.0, 47.5): 5,
            (11.0, 45.0): 5,
            (3.1, 50.0): 4,
            (3.1, 47.5): 4,
        }
        self.assertEqual(combos, expected)

    def test_preserves_traceability_columns(self) -> None:
        df = extract_mmp1_time_consolidation(MMP_WORKBOOK)

        self.assertTrue({"source_workbook", "source_sheet", "source_row", "source_range"}.issubset(df.columns))
        self.assertTrue(df["source_range"].str.contains(":").all())


@unittest.skipUnless(RAW_WORKBOOKS_AVAILABLE, "Lokale Excel-Rohdaten fehlen")
class ExtractDerivedModelInputsTests(unittest.TestCase):
    def test_extracts_mmp1_kinetics_summary(self) -> None:
        df = extract_mmp1_kinetics_summary(MMP_WORKBOOK)

        self.assertEqual(len(df), 9)
        self.assertEqual(set(df["sigma1_kpa"]), {3.1, 11.0, 20.0})
        row = df[(df["sigma1_kpa"] == 20.0) & (df["temperature_c"] == 50.0)].iloc[0]
        self.assertAlmostEqual(row["dfc_dt_pa_per_h"], 1822.1693756984535)
        self.assertAlmostEqual(row["caking_time_20kpa_h"], 2.7314835308557504)

    def test_extracts_relative_change_summary(self) -> None:
        df = extract_relative_change_summary(MMP_WORKBOOK)

        self.assertEqual(len(df), 6)
        self.assertEqual(sorted(df["moisture_db_pct"].unique().tolist()), [3.8, 4.0, 4.2])

    def test_extracts_aw_tg_data(self) -> None:
        df = extract_aw_tg_data(MMP_WORKBOOK)

        self.assertEqual(len(df), 15)
        self.assertIn("MMP1", set(df["material"]))
        self.assertIn("09FD08", set(df["material"]))

    def test_extracts_critical_cake_strength(self) -> None:
        df = extract_critical_cake_strength(MMP_WORKBOOK)

        self.assertEqual(len(df), 6)
        self.assertEqual(df["sigma_c_kpa"].tolist(), [1.39, 9.04, 13.33, 41.46, 56.2, 86.4])
        self.assertEqual(df["sieve_residue_pct"].tolist(), [0.8, 0.9, 1.2, 17.7, 29.9, 39.4])
        self.assertTrue((df["sieving_time_min"] == 1.0).all())
        self.assertTrue((df["sieving_amplitude_mm"] == 1.0).all())
        self.assertTrue({"source_workbook", "source_sheet", "source_row", "source_range"}.issubset(df.columns))

    def test_extracts_permeation_time_series(self) -> None:
        df = extract_permeation_time_series(UPTAKE_WORKBOOK)

        self.assertEqual(len(df), 2378)
        first = df.iloc[0]
        self.assertAlmostEqual(first["temperature_c"], 20.71)
        self.assertAlmostEqual(first["relative_humidity_pct"], 59.689)
        self.assertAlmostEqual(first["moisture_db_pct"], 3.794304598918056)
        self.assertLess(first["water_activity"], 1.0)

    def test_extracts_real_container_logger_profile(self) -> None:
        df = extract_real_container_logger_profile(UPTAKE_WORKBOOK)

        self.assertEqual(list(df.columns), ["time_d", "temperature_c", "relative_humidity_pct"])
        self.assertEqual(len(df), 2378)
        first = df.iloc[0]
        self.assertAlmostEqual(first["time_d"], 0.0)
        self.assertAlmostEqual(first["temperature_c"], 20.71)
        self.assertAlmostEqual(first["relative_humidity_pct"], 59.689)
        self.assertTrue(df["time_d"].is_monotonic_increasing)
        self.assertAlmostEqual(df.iloc[-1]["time_d"], 99.08754052801804)

    def test_extracts_table2_scenario_series(self) -> None:
        df = extract_table2_scenario_series(UPTAKE_WORKBOOK)

        self.assertEqual(len(df), 7134)
        self.assertEqual(set(df["initial_moisture_db_pct"]), {3.8, 4.0, 4.2})
        first = df[(df["initial_moisture_db_pct"] == 3.8) & (df["time_d"] == 0.0)].iloc[0]
        self.assertAlmostEqual(first["cake_strength_kpa"], 0.8)
        self.assertAlmostEqual(first["tg_c"], 49.68269954770015)

    def test_extracts_wdd_permeability_summary(self) -> None:
        df = extract_wdd_permeability_summary(UPTAKE_WORKBOOK)

        self.assertEqual(len(df), 3)
        self.assertEqual(df["temperature_c"].tolist(), [15.0, 23.0, 35.0])
        row_23 = df[df["temperature_c"] == 23.0].iloc[0]
        self.assertAlmostEqual(row_23["k_over_delta_kg_per_m2_d_pa"], 4.38426520968157e-07)

    def test_extracts_wdd_arrhenius_parameters(self) -> None:
        df = extract_wdd_arrhenius_parameters(UPTAKE_WORKBOOK)

        values = dict(zip(df["parameter"], df["value"]))
        self.assertAlmostEqual(values["negative_ea_over_r"], -3315.7)
        self.assertAlmostEqual(values["pre_exponential_factor"], 0.033901364997275675)

    def test_extracts_wdd_measurement_timeseries(self) -> None:
        df = extract_wdd_measurement_timeseries(UPTAKE_WORKBOOK)

        self.assertEqual(set(df["temperature_c"]), {15.0, 23.0, 35.0})
        self.assertGreater(len(df), 5000)
        self.assertAlmostEqual(df[df["temperature_c"] == 35.0]["time_d"].max(), 29.958344907407406)


class FitCakingModelsTests(unittest.TestCase):
    @unittest.skipUnless(MMP_WORKBOOK.exists(), "Lokale Excel-Rohdaten fehlen")
    def test_fits_expected_exponential_parameters(self) -> None:
        kinetics_df = extract_mmp1_kinetics_summary(MMP_WORKBOOK)
        params_df = fit_caking_time_exponential_models(kinetics_df)

        self.assertEqual(set(params_df["sigma1_kpa"]), {11.0, 20.0})

        row_20 = params_df[params_df["sigma1_kpa"] == 20.0].iloc[0]
        self.assertAlmostEqual(row_20["a_param"], 128.51, places=2)
        self.assertAlmostEqual(row_20["k_param"], -0.584, places=3)

        row_11 = params_df[params_df["sigma1_kpa"] == 11.0].iloc[0]
        self.assertAlmostEqual(row_11["a_param"], 588.28, places=2)
        self.assertAlmostEqual(row_11["k_param"], -0.631, places=3)

    @unittest.skipUnless(MMP_WORKBOOK.exists(), "Lokale Excel-Rohdaten fehlen")
    def test_fits_caking_rate_parameters(self) -> None:
        kinetics_df = extract_mmp1_kinetics_summary(MMP_WORKBOOK)
        params_df = fit_caking_rate_exponential_models(kinetics_df)

        self.assertEqual(set(params_df["sigma1_kpa"]), {11.0, 20.0})
        row_20 = params_df[params_df["sigma1_kpa"] == 20.0].iloc[0]
        self.assertAlmostEqual(row_20["a_param_pa_per_h"], 60.96614981220336)
        self.assertAlmostEqual(row_20["k_param_per_c"], 0.5329326968060314)

    def test_predicts_caking_time_from_fit(self) -> None:
        predicted = predict_caking_time_hours(t_minus_tg_c=6.6, a_param=128.51, k_param=-0.584)
        self.assertAlmostEqual(predicted, 2.7314835308557504, delta=0.02)

    def test_predicts_caking_rate_from_fit(self) -> None:
        predicted = predict_caking_rate_pa_per_h(
            t_minus_tg_c=6.6,
            a_param_pa_per_h=60.96614981220336,
            k_param_per_c=0.5329326968060314,
        )
        self.assertAlmostEqual(predicted, 2054.2674430080488)


if __name__ == "__main__":
    unittest.main()
