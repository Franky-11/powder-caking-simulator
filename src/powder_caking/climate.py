from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = ("time_d", "temperature_c", "relative_humidity_pct")
TEMPERATURE_WARNING_RANGE_C = (-20.0, 80.0)
IRREGULAR_STEP_RELATIVE_TOLERANCE = 0.05
IRREGULAR_STEP_ABSOLUTE_TOLERANCE_D = 1e-9


@dataclass(frozen=True)
class ClimateProfilePreview:
    duration_d: float
    n_points: int
    temperature_min_c: float
    temperature_max_c: float
    temperature_mean_c: float
    relative_humidity_min_pct: float
    relative_humidity_max_pct: float
    relative_humidity_mean_pct: float

    def as_dict(self) -> dict[str, float | int]:
        return {
            "duration_d": self.duration_d,
            "n_points": self.n_points,
            "temperature_min_c": self.temperature_min_c,
            "temperature_max_c": self.temperature_max_c,
            "temperature_mean_c": self.temperature_mean_c,
            "relative_humidity_min_pct": self.relative_humidity_min_pct,
            "relative_humidity_max_pct": self.relative_humidity_max_pct,
            "relative_humidity_mean_pct": self.relative_humidity_mean_pct,
        }


@dataclass(frozen=True)
class ClimateSegment:
    duration_d: float
    temperature_c: float
    relative_humidity_pct: float
    label: str | None = None

    def __post_init__(self) -> None:
        if self.duration_d <= 0:
            raise ValueError("duration_d must be greater than 0")
        if not 0 <= self.relative_humidity_pct <= 100:
            raise ValueError("relative_humidity_pct must be between 0 and 100")


@dataclass(frozen=True)
class ClimateProfile:
    data: pd.DataFrame
    source: str | None = None
    validation_warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        frame = self.data.copy()
        _validate_columns(frame)

        for column in REQUIRED_COLUMNS:
            frame[column] = pd.to_numeric(frame[column], errors="raise")

        if frame[list(REQUIRED_COLUMNS)].isna().any().any():
            raise ValueError("climate profile must not contain missing values")
        if not frame["time_d"].is_monotonic_increasing:
            raise ValueError("time_d must be monotonically increasing")
        if frame["time_d"].duplicated().any():
            raise ValueError("time_d values must be unique")
        if ((frame["relative_humidity_pct"] < 0) | (frame["relative_humidity_pct"] > 100)).any():
            raise ValueError("relative_humidity_pct must be between 0 and 100")

        frame = frame.reset_index(drop=True)
        warnings = (*self.validation_warnings, *_build_validation_warnings(frame))

        object.__setattr__(self, "data", frame)
        object.__setattr__(self, "validation_warnings", tuple(dict.fromkeys(warnings)))

    @classmethod
    def from_segments(cls, segments: Iterable[ClimateSegment], dt_d: float = 1 / 24) -> ClimateProfile:
        if dt_d <= 0:
            raise ValueError("dt_d must be greater than 0")

        records: list[dict[str, float | int | str | None]] = []
        time_d = 0.0
        last_segment: ClimateSegment | None = None
        last_index = 0
        for index, segment in enumerate(segments, start=1):
            last_segment = segment
            last_index = index
            segment_end_d = time_d + segment.duration_d
            while time_d < segment_end_d - 1e-12:
                records.append(
                    {
                        "time_d": round(time_d, 12),
                        "temperature_c": float(segment.temperature_c),
                        "relative_humidity_pct": float(segment.relative_humidity_pct),
                        "segment": index,
                        "label": segment.label,
                    }
                )
                time_d += dt_d
            time_d = segment_end_d

        if last_segment is None:
            raise ValueError("at least one climate segment is required")

        records.append(
            {
                "time_d": round(time_d, 12),
                "temperature_c": float(last_segment.temperature_c),
                "relative_humidity_pct": float(last_segment.relative_humidity_pct),
                "segment": last_index,
                "label": last_segment.label,
            }
        )

        return cls(pd.DataFrame.from_records(records), source="segments")

    @classmethod
    def from_csv(
        cls,
        path: str | Path,
        time_column: str = "time_d",
        temperature_column: str = "temperature_c",
        humidity_column: str = "relative_humidity_pct",
        timestamp_column: str = "timestamp",
    ) -> ClimateProfile:
        path = Path(path)
        frame = pd.read_csv(path)

        if time_column in frame.columns:
            time_d = pd.to_numeric(frame[time_column], errors="raise")
        elif timestamp_column in frame.columns:
            timestamps = pd.to_datetime(frame[timestamp_column], errors="raise")
            time_d = (timestamps - timestamps.iloc[0]).dt.total_seconds() / 86400
        else:
            raise ValueError(f"CSV must contain either {time_column!r} or {timestamp_column!r}")

        missing = [column for column in (temperature_column, humidity_column) if column not in frame.columns]
        if missing:
            raise ValueError(f"CSV is missing required columns: {', '.join(missing)}")

        profile_frame = pd.DataFrame(
            {
                "time_d": time_d,
                "temperature_c": frame[temperature_column],
                "relative_humidity_pct": frame[humidity_column],
            }
        )
        return cls(profile_frame, source=str(path))

    @classmethod
    def real_container_logger_profile(cls, path: str | Path | None = None) -> ClimateProfile:
        if path is None:
            path = Path(__file__).resolve().parents[2] / "data" / "processed" / "real_container_logger_profile.csv"
        return cls.from_csv(path).with_source("real_container_logger_profile")

    @classmethod
    def neutral_reference_transport(cls, dt_d: float = 1 / 24) -> ClimateProfile:
        return cls.from_segments(
            [
                ClimateSegment(10.0, 20.0, 60.0, "warehouse_europe"),
                ClimateSegment(45.0, 25.0, 65.0, "moderate_sea_transport"),
                ClimateSegment(10.0, 25.0, 70.0, "destination_storage"),
            ],
            dt_d=dt_d,
        ).with_source("neutral_reference_transport")

    @classmethod
    def tropical_sea_transport_southeast_asia(cls, dt_d: float = 1 / 24) -> ClimateProfile:
        return cls.from_segments(
            [
                ClimateSegment(7.0, 20.0, 60.0, "warehouse_europe"),
                ClimateSegment(60.0, 30.0, 80.0, "sea_tropical"),
                ClimateSegment(14.0, 32.0, 85.0, "port_southeast_asia"),
            ],
            dt_d=dt_d,
        ).with_source("tropical_sea_transport_southeast_asia")

    @classmethod
    def hot_humid_worst_case(cls, dt_d: float = 1 / 24) -> ClimateProfile:
        return cls.from_segments(
            [
                ClimateSegment(5.0, 25.0, 70.0, "warm_start"),
                ClimateSegment(60.0, 35.0, 85.0, "hot_humid_transport"),
                ClimateSegment(10.0, 35.0, 90.0, "hot_humid_storage"),
            ],
            dt_d=dt_d,
        ).with_source("hot_humid_worst_case")

    @classmethod
    def day_night_container_profile(cls, days: int = 60, dt_d: float = 1 / 24) -> ClimateProfile:
        if days <= 0:
            raise ValueError("days must be greater than 0")

        segments: list[ClimateSegment] = []
        for _ in range(days):
            segments.append(ClimateSegment(0.5, 35.0, 65.0, "day_hot"))
            segments.append(ClimateSegment(0.5, 24.0, 90.0, "night_humid"))

        return cls.from_segments(segments, dt_d=dt_d).with_source("day_night_container_profile")

    def with_source(self, source: str | None) -> ClimateProfile:
        return ClimateProfile(self.data, source=source, validation_warnings=self.validation_warnings)

    def resample(self, dt_d: float) -> ClimateProfile:
        if dt_d <= 0:
            raise ValueError("dt_d must be greater than 0")
        if len(self.data) < 2:
            raise ValueError("climate profile must contain at least two rows for resampling")

        duration_d = self.duration_d
        if duration_d <= 0:
            raise ValueError("climate profile duration must be greater than 0 for resampling")

        source_time = self.data["time_d"].to_numpy(dtype=float)
        source_time = source_time - source_time[0]
        target_time = np.arange(0.0, duration_d + (dt_d * 0.5), dt_d, dtype=float)
        if target_time[-1] < duration_d - 1e-12:
            target_time = np.append(target_time, duration_d)
        else:
            target_time[-1] = duration_d

        resampled = pd.DataFrame(
            {
                "time_d": np.round(target_time, 12),
                "temperature_c": np.interp(
                    target_time,
                    source_time,
                    self.data["temperature_c"].to_numpy(dtype=float),
                ),
                "relative_humidity_pct": np.interp(
                    target_time,
                    source_time,
                    self.data["relative_humidity_pct"].to_numpy(dtype=float),
                ),
            }
        )

        source = f"{self.source}:resampled" if self.source else "resampled"
        return ClimateProfile(resampled, source=source, validation_warnings=self.validation_warnings)

    def preview(self) -> ClimateProfilePreview:
        temperature = self.data["temperature_c"]
        humidity = self.data["relative_humidity_pct"]
        return ClimateProfilePreview(
            duration_d=self.duration_d,
            n_points=int(len(self.data)),
            temperature_min_c=float(temperature.min()),
            temperature_max_c=float(temperature.max()),
            temperature_mean_c=float(temperature.mean()),
            relative_humidity_min_pct=float(humidity.min()),
            relative_humidity_max_pct=float(humidity.max()),
            relative_humidity_mean_pct=float(humidity.mean()),
        )

    def to_dataframe(self) -> pd.DataFrame:
        return self.data.copy()

    @property
    def duration_d(self) -> float:
        return float(self.data["time_d"].iloc[-1] - self.data["time_d"].iloc[0])


def real_container_logger_profile(path: str | Path | None = None) -> ClimateProfile:
    return ClimateProfile.real_container_logger_profile(path)


CLIMATE_PRESETS: dict[str, Callable[..., ClimateProfile]] = {
    "neutral_reference_transport": ClimateProfile.neutral_reference_transport,
    "tropical_sea_transport_southeast_asia": ClimateProfile.tropical_sea_transport_southeast_asia,
    "hot_humid_worst_case": ClimateProfile.hot_humid_worst_case,
    "day_night_container_profile": ClimateProfile.day_night_container_profile,
    "real_container_logger_profile": ClimateProfile.real_container_logger_profile,
}


def climate_preset_names() -> tuple[str, ...]:
    return tuple(CLIMATE_PRESETS)


def load_climate_preset(name: str, **kwargs: object) -> ClimateProfile:
    try:
        preset = CLIMATE_PRESETS[name]
    except KeyError as exc:
        available = ", ".join(climate_preset_names())
        raise ValueError(f"Unknown climate preset {name!r}. Available: {available}") from exc
    return preset(**kwargs)


def _validate_columns(frame: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"climate profile is missing required columns: {', '.join(missing)}")


def _build_validation_warnings(frame: pd.DataFrame) -> tuple[str, ...]:
    warnings: list[str] = []

    temperature_min = float(frame["temperature_c"].min())
    temperature_max = float(frame["temperature_c"].max())
    if temperature_min < TEMPERATURE_WARNING_RANGE_C[0] or temperature_max > TEMPERATURE_WARNING_RANGE_C[1]:
        warnings.append(
            "temperature_c contains values outside the expected range "
            f"{TEMPERATURE_WARNING_RANGE_C[0]:g}..{TEMPERATURE_WARNING_RANGE_C[1]:g} degC"
        )

    if len(frame) >= 3:
        diffs = frame["time_d"].diff().dropna().to_numpy(dtype=float)
        median_dt = float(np.median(diffs))
        if median_dt > 0:
            tolerance = max(IRREGULAR_STEP_ABSOLUTE_TOLERANCE_D, abs(median_dt) * IRREGULAR_STEP_RELATIVE_TOLERANCE)
            if np.any(np.abs(diffs - median_dt) > tolerance):
                warnings.append("time_d step size is irregular; resampling will use linear interpolation")
            if np.any(diffs > (2 * median_dt) + tolerance):
                warnings.append("time_d contains gaps larger than twice the median step size")

    return tuple(warnings)
