from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from powder_caking.climate import ClimateProfile, ClimateSegment
from powder_caking.simulation import (
    CakingRateParameters,
    caking_rate_pa_per_h,
    consolidation_stress_from_stack_height_kpa,
    dry_mass_from_total_mass,
    integrate_cake_strength_increment_kpa,
    load_default_simulation_parameters,
    permeability_k_over_delta,
    saturation_vapor_pressure_pa,
    simulate_transport,
    tg_linear_c,
    tg_vuataz_c,
    water_activity_from_moisture_db_pct,
    water_mass_from_moisture_db,
)


class SimulationEquationTests(unittest.TestCase):
    def test_reproduces_excel_first_row_equations(self) -> None:
        aw = water_activity_from_moisture_db_pct(3.794304598918056)

        self.assertAlmostEqual(aw, 0.193248147061919)
        self.assertAlmostEqual(saturation_vapor_pressure_pa(20.71), 2445.8520442109107)
        self.assertAlmostEqual(tg_vuataz_c(aw), 49.68269954770015)
        self.assertAlmostEqual(tg_linear_c(aw), 54.65503222446587)

    def test_loads_default_parameters_from_processed_files(self) -> None:
        params = load_default_simulation_parameters(REPO_ROOT / "data" / "processed")

        self.assertEqual(params.integration_method, "euler")
        self.assertAlmostEqual(params.permeability.k0, 0.033901364997275675)
        self.assertAlmostEqual(params.permeability.activation_energy_j_per_kmol, 27566729.799999997)
        self.assertAlmostEqual(params.caking_rate.sigma1_kpa, 20.0)
        self.assertAlmostEqual(params.caking_rate.a_param_pa_per_h, 60.96614981220336)

    def test_can_load_11_kpa_caking_fit(self) -> None:
        params = load_default_simulation_parameters(
            REPO_ROOT / "data" / "processed",
            consolidation_stress_kpa=11.0,
        )

        self.assertAlmostEqual(params.caking_rate.sigma1_kpa, 11.0)
        self.assertAlmostEqual(params.caking_rate.a_param_pa_per_h, 21.951828464474367)

    def test_calculates_water_masses_from_dry_basis_moisture(self) -> None:
        dry_mass = dry_mass_from_total_mass(25.0, 3.794304598918056)
        water_mass = water_mass_from_moisture_db(dry_mass, 3.794304598918056)

        self.assertAlmostEqual(dry_mass, 24.0861, places=4)
        self.assertAlmostEqual(water_mass, 0.9139, places=4)

    def test_integrates_pa_per_h_rate_with_hours(self) -> None:
        increment = integrate_cake_strength_increment_kpa(dfc_dt_pa_per_h=1000.0, dt_h=24.0)

        self.assertAlmostEqual(increment, 24.0)

    def test_calculates_consolidation_stress_from_stack_height(self) -> None:
        stress = consolidation_stress_from_stack_height_kpa(
            stack_height_m=2.0,
            bulk_density_kg_per_m3=650.0,
        )

        self.assertAlmostEqual(stress, 12.748645)

    def test_caking_rate_is_zero_below_tg(self) -> None:
        rate = caking_rate_pa_per_h(
            t_minus_tg_c=-1.0,
            caking_rate=CakingRateParameters(sigma1_kpa=20.0, a_param_pa_per_h=60.0, k_param_per_c=0.5),
        )

        self.assertEqual(rate, 0.0)

    def test_permeability_matches_arrhenius_parameters(self) -> None:
        self.assertAlmostEqual(permeability_k_over_delta(15.0), 3.529010745612398e-07)
        self.assertAlmostEqual(permeability_k_over_delta(35.0), 7.166013289028259e-07)


class TransportSimulationTests(unittest.TestCase):
    def test_simulates_real_logger_profile_against_excel_trace(self) -> None:
        profile = ClimateProfile.real_container_logger_profile()
        params = load_default_simulation_parameters(REPO_ROOT / "data" / "processed")

        result = simulate_transport(
            climate_profile=profile,
            initial_moisture_db_pct=3.794304598918056,
            parameters=params,
        )

        actual = result.time_series

        self.assertEqual(len(actual), 2378)
        self.assertAlmostEqual(actual.iloc[0]["moisture_db_pct"], 3.794304598918056)
        self.assertAlmostEqual(actual.iloc[0]["water_activity"], 0.193248147061919)
        self.assertAlmostEqual(actual.iloc[0]["tg_vuataz_c"], 49.68269954770015)

        self.assertAlmostEqual(result.summary["final_sigma_c_kpa"], 7.151695528261428)
        self.assertFalse(result.summary["is_caked"])
        self.assertIsNone(result.summary["time_to_critical_d"])
        self.assertEqual(result.summary["integration_method"], "euler")
        self.assertEqual(result.summary["consolidation_stress_kpa"], 20.0)

    def test_heun_integration_is_available_for_real_logger_profile(self) -> None:
        profile = ClimateProfile.real_container_logger_profile()
        params = load_default_simulation_parameters(
            REPO_ROOT / "data" / "processed",
            integration_method="heun",
        )

        result = simulate_transport(
            climate_profile=profile,
            initial_moisture_db_pct=3.794304598918056,
            parameters=params,
        )

        self.assertEqual(result.summary["integration_method"], "heun")
        self.assertAlmostEqual(result.summary["final_sigma_c_kpa"], 7.1710995566004065)
        self.assertFalse(result.summary["is_caked"])

    def test_reports_time_to_critical_threshold(self) -> None:
        profile = ClimateProfile.from_segments(
            [
                ClimateSegment(duration_d=2.0, temperature_c=55.0, relative_humidity_pct=90.0),
            ],
            dt_d=0.5,
        )

        result = simulate_transport(
            climate_profile=profile,
            initial_moisture_db_pct=4.0,
            parameters=load_default_simulation_parameters(REPO_ROOT / "data" / "processed"),
        )

        self.assertTrue(result.summary["is_caked"])
        self.assertIsNotNone(result.summary["time_to_critical_d"])
        self.assertGreaterEqual(result.summary["final_sigma_c_kpa"], 20.0)

    def test_can_resample_climate_profile_to_requested_simulation_step(self) -> None:
        profile = ClimateProfile(
            pd.DataFrame(
                {
                    "time_d": [0.0, 1.0],
                    "temperature_c": [20.0, 30.0],
                    "relative_humidity_pct": [60.0, 80.0],
                }
            )
        )

        result = simulate_transport(
            climate_profile=profile,
            initial_moisture_db_pct=3.8,
            parameters=load_default_simulation_parameters(REPO_ROOT / "data" / "processed"),
            dt_d=0.25,
        )

        self.assertEqual(result.time_series["time_d"].tolist(), [0.0, 0.25, 0.5, 0.75, 1.0])


if __name__ == "__main__":
    unittest.main()
