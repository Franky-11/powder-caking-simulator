from __future__ import annotations

import sys
import unittest
from pathlib import Path

import httpx


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from powder_caking.api import create_app


class PowderCakingApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        transport = httpx.ASGITransport(app=create_app())
        self.client = httpx.AsyncClient(transport=transport, base_url="http://testserver")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def test_gets_model_defaults(self) -> None:
        response = await self.client.get("/model/defaults")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["integration_methods"], ["euler", "heun"])
        self.assertEqual(data["default_consolidation_stress_kpa"], 20.0)
        self.assertEqual(data["available_consolidation_stress_kpa"], [11.0, 20.0])
        self.assertIn("neutral_reference_transport", data["climate_presets"])
        self.assertAlmostEqual(data["parameters"]["caking_rate"]["a_param_pa_per_h"], 60.96614981220336)

    async def test_gets_climate_presets_with_preview(self) -> None:
        response = await self.client.get("/presets/climate")

        self.assertEqual(response.status_code, 200)
        presets = {item["name"]: item for item in response.json()}
        self.assertIn("hot_humid_worst_case", presets)
        self.assertAlmostEqual(presets["hot_humid_worst_case"]["preview"]["duration_d"], 75.0)
        self.assertEqual(presets["real_container_logger_profile"]["preview"]["n_points"], 2378)

    async def test_previews_csv_profile_with_resampling_and_warnings(self) -> None:
        csv_text = "\n".join(
            [
                "time_d,temperature_c,relative_humidity_pct",
                "0.0,20.0,60.0",
                "0.5,22.0,61.0",
                "1.25,24.0,62.0",
            ]
        )

        response = await self.client.post(
            "/profiles/preview",
            json={"csv_text": csv_text, "dt_d": 0.25},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["source"], "api_csv:resampled")
        self.assertAlmostEqual(data["preview"]["duration_d"], 1.25)
        self.assertEqual(data["preview"]["n_points"], 6)
        self.assertIn("time_d step size is irregular; resampling will use linear interpolation", data["warnings"])

    async def test_previews_timestamp_csv_as_elapsed_days(self) -> None:
        csv_text = "\n".join(
            [
                "timestamp,temperature_c,relative_humidity_pct",
                "2024-03-01 08:00:00,20.0,60.0",
                "2024-03-01 20:00:00,24.0,80.0",
            ]
        )

        response = await self.client.post("/profiles/preview", json={"csv_text": csv_text})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertAlmostEqual(data["preview"]["duration_d"], 0.5)
        self.assertAlmostEqual(data["preview"]["temperature_mean_c"], 22.0)

    async def test_preview_real_logger_preset_does_not_expose_path(self) -> None:
        response = await self.client.post(
            "/profiles/preview",
            json={"preset_name": "real_container_logger_profile", "dt_d": 1.0},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["source"], "real_container_logger_profile:resampled")
        self.assertNotIn("/", data["source"])
        self.assertNotIn("\\", data["source"])

    async def test_simulates_inline_profile(self) -> None:
        response = await self.client.post(
            "/simulate",
            json={
                "climate_profile": {
                    "points": [
                        {"time_d": 0.0, "temperature_c": 20.0, "relative_humidity_pct": 60.0},
                        {"time_d": 1.0, "temperature_c": 30.0, "relative_humidity_pct": 80.0},
                    ]
                },
                "initial_moisture_db_pct": 3.8,
                "dt_d": 0.5,
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["summary"]["integration_method"], "euler")
        self.assertEqual(data["parameters"]["caking_rate"]["sigma1_kpa"], 20.0)
        self.assertEqual([row["time_d"] for row in data["time_series"]], [0.0, 0.5, 1.0])
        self.assertFalse(data["summary"]["is_caked"])

    async def test_simulation_defaults_are_unchanged_without_overrides(self) -> None:
        response = await self.client.post("/simulate", json=_simulation_payload())

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["parameters"]["permeability"]["mode"], "temperature_dependent")
        self.assertAlmostEqual(data["parameters"]["permeability"]["k0"], 0.033901364997275675)
        self.assertAlmostEqual(data["parameters"]["gab"]["mo"], 4.63)
        self.assertAlmostEqual(data["parameters"]["critical_sigma_c_kpa"], 20.0)
        self.assertAlmostEqual(data["parameters"]["sack_mass_kg"], 25.0)
        self.assertAlmostEqual(data["parameters"]["sack_area_m2"], 1.26)

    async def test_simulation_applies_gab_override(self) -> None:
        baseline = await self.client.post("/simulate", json=_simulation_payload())
        response = await self.client.post(
            "/simulate",
            json=_simulation_payload(
                parameter_overrides={
                    "gab": {
                        "mo": 5.2,
                    }
                }
            ),
        )

        self.assertEqual(response.status_code, 200)
        baseline_data = baseline.json()
        data = response.json()
        self.assertAlmostEqual(data["parameters"]["gab"]["mo"], 5.2)
        self.assertNotAlmostEqual(
            data["time_series"][0]["water_activity"],
            baseline_data["time_series"][0]["water_activity"],
        )

    async def test_simulation_applies_caking_threshold_override(self) -> None:
        response = await self.client.post(
            "/simulate",
            json=_simulation_payload(
                parameter_overrides={
                    "caking_threshold": {
                        "critical_sigma_c_kpa": 1.0,
                    }
                }
            ),
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertAlmostEqual(data["parameters"]["critical_sigma_c_kpa"], 1.0)
        self.assertAlmostEqual(data["summary"]["critical_sigma_c_kpa"], 1.0)

    async def test_simulation_applies_sack_override(self) -> None:
        response = await self.client.post(
            "/simulate",
            json=_simulation_payload(
                parameter_overrides={
                    "sack": {
                        "sack_mass_kg": 10.0,
                        "sack_area_m2": 2.0,
                    }
                }
            ),
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertAlmostEqual(data["parameters"]["sack_mass_kg"], 10.0)
        self.assertAlmostEqual(data["parameters"]["sack_area_m2"], 2.0)
        self.assertAlmostEqual(data["time_series"][0]["dry_mass_kg"], 10.0 / 1.038)

    async def test_simulation_applies_constant_permeability_mode(self) -> None:
        response = await self.client.post(
            "/simulate",
            json=_simulation_payload(
                parameter_overrides={
                    "permeability": {
                        "mode": "constant",
                        "k_over_delta_kg_per_m2_d_pa": 1.2e-6,
                    }
                }
            ),
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["parameters"]["permeability"]["mode"], "constant")
        self.assertAlmostEqual(data["parameters"]["permeability"]["k_over_delta_kg_per_m2_d_pa"], 1.2e-6)
        self.assertAlmostEqual(data["time_series"][0]["k_over_delta_kg_per_m2_d_pa"], 1.2e-6)
        self.assertAlmostEqual(data["time_series"][1]["k_over_delta_kg_per_m2_d_pa"], 1.2e-6)

    async def test_simulation_rejects_invalid_overrides(self) -> None:
        response = await self.client.post(
            "/simulate",
            json=_simulation_payload(
                parameter_overrides={
                    "sack": {
                        "sack_mass_kg": -1.0,
                    }
                }
            ),
        )

        self.assertEqual(response.status_code, 422)

    async def test_simulation_returns_profile_warnings(self) -> None:
        response = await self.client.post(
            "/simulate",
            json={
                "climate_profile": {
                    "points": [
                        {"time_d": 0.0, "temperature_c": 20.0, "relative_humidity_pct": 60.0},
                        {"time_d": 0.5, "temperature_c": 22.0, "relative_humidity_pct": 61.0},
                        {"time_d": 1.25, "temperature_c": 24.0, "relative_humidity_pct": 62.0},
                    ]
                },
                "initial_moisture_db_pct": 3.8,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "time_d step size is irregular; resampling will use linear interpolation",
            response.json()["warnings"],
        )

    async def test_moisture_limit_reports_safe_current_profile(self) -> None:
        response = await self.client.post(
            "/simulate/moisture-limit",
            json=_moisture_limit_payload(initial_moisture_db_pct=3.8),
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["is_current_profile_safe"])
        self.assertAlmostEqual(data["current_initial_moisture_db_pct"], 3.8)
        self.assertGreater(data["safe_initial_moisture_db_pct"], 4.0)
        self.assertLess(data["safe_initial_moisture_db_pct"], 4.3)
        self.assertGreater(data["moisture_margin_db_pct"], 0)
        self.assertAlmostEqual(data["critical_sigma_c_kpa"], 20.0)
        self.assertLess(data["final_sigma_c_kpa_at_limit"], 20.0)
        self.assertGreater(data["iterations"], 0)
        self.assertEqual(data["warnings"], [])

    async def test_moisture_limit_reports_caking_current_profile(self) -> None:
        response = await self.client.post(
            "/simulate/moisture-limit",
            json=_moisture_limit_payload(initial_moisture_db_pct=4.8),
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["is_current_profile_safe"])
        self.assertLess(data["moisture_margin_db_pct"], 0)
        self.assertGreater(data["safe_initial_moisture_db_pct"], 4.0)
        self.assertLess(data["safe_initial_moisture_db_pct"], 4.3)

    async def test_moisture_limit_applies_expert_overrides(self) -> None:
        baseline = await self.client.post(
            "/simulate/moisture-limit",
            json=_moisture_limit_payload(),
        )
        response = await self.client.post(
            "/simulate/moisture-limit",
            json=_moisture_limit_payload(
                parameter_overrides={
                    "gab": {
                        "mo": 5.2,
                    }
                }
            ),
        )

        self.assertEqual(response.status_code, 200)
        baseline_data = baseline.json()
        data = response.json()
        self.assertGreater(data["safe_initial_moisture_db_pct"], baseline_data["safe_initial_moisture_db_pct"])

    async def test_moisture_limit_reports_lower_bound_caked(self) -> None:
        response = await self.client.post(
            "/simulate/moisture-limit",
            json=_moisture_limit_payload(
                climate_profile={
                    "points": [
                        {"time_d": 0.0, "temperature_c": 60.0, "relative_humidity_pct": 90.0},
                        {"time_d": 5.0, "temperature_c": 60.0, "relative_humidity_pct": 90.0},
                    ]
                }
            ),
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNone(data["safe_initial_moisture_db_pct"])
        self.assertIsNone(data["moisture_margin_db_pct"])
        self.assertIsNone(data["final_sigma_c_kpa_at_limit"])
        self.assertIn("lower search bound already cakes", data["warnings"][0])

    async def test_moisture_limit_reports_upper_bound_safe(self) -> None:
        response = await self.client.post(
            "/simulate/moisture-limit",
            json=_moisture_limit_payload(
                climate_profile={
                    "points": [
                        {"time_d": 0.0, "temperature_c": 35.0, "relative_humidity_pct": 90.0},
                        {"time_d": 5.0, "temperature_c": 35.0, "relative_humidity_pct": 90.0},
                    ]
                }
            ),
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertAlmostEqual(data["safe_initial_moisture_db_pct"], 5.0)
        self.assertEqual(data["iterations"], 0)
        self.assertIn("upper search bound remains safe", data["warnings"][0])

    async def test_moisture_limit_rejects_invalid_search_bounds(self) -> None:
        response = await self.client.post(
            "/simulate/moisture-limit",
            json=_moisture_limit_payload(
                search_bounds={
                    "min_initial_moisture_db_pct": 5.0,
                    "max_initial_moisture_db_pct": 3.0,
                    "tolerance_db_pct": 0.01,
                }
            ),
        )

        self.assertEqual(response.status_code, 422)

    async def test_rejects_unknown_preset_for_preview(self) -> None:
        response = await self.client.post("/profiles/preview", json={"preset_name": "missing"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("Unknown climate preset", response.json()["detail"])

    async def test_rejects_missing_profile_source(self) -> None:
        response = await self.client.post("/profiles/preview", json={})

        self.assertEqual(response.status_code, 422)

    async def test_rejects_unavailable_caking_fit(self) -> None:
        response = await self.client.post(
            "/simulate",
            json={
                "climate_profile": {"preset_name": "neutral_reference_transport", "dt_d": 1.0},
                "initial_moisture_db_pct": 3.8,
                "consolidation_stress_kpa": 15.0,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("No caking-rate fit for 15.0 kPa", response.json()["detail"])


def _simulation_payload(**overrides):
    payload = {
        "climate_profile": {
            "points": [
                {"time_d": 0.0, "temperature_c": 20.0, "relative_humidity_pct": 60.0},
                {"time_d": 1.0, "temperature_c": 30.0, "relative_humidity_pct": 80.0},
            ]
        },
        "initial_moisture_db_pct": 3.8,
    }
    payload.update(overrides)
    return payload


def _moisture_limit_payload(**overrides):
    payload = {
        "climate_profile": {
            "points": [
                {"time_d": 0.0, "temperature_c": 45.0, "relative_humidity_pct": 90.0},
                {"time_d": 5.0, "temperature_c": 45.0, "relative_humidity_pct": 90.0},
            ]
        },
        "initial_moisture_db_pct": 3.8,
        "dt_d": 0.5,
        "search_bounds": {
            "min_initial_moisture_db_pct": 3.0,
            "max_initial_moisture_db_pct": 5.0,
            "tolerance_db_pct": 0.01,
        },
    }
    payload.update(overrides)
    return payload


if __name__ == "__main__":
    unittest.main()
