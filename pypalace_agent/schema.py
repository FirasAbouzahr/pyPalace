"""JSON study specification models."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator


class RangeSpec(BaseModel):
    min: float
    max: float

    @model_validator(mode="after")
    def max_gt_min(self) -> "RangeSpec":
        if self.max <= self.min:
            raise ValueError("max must be greater than min")
        return self


class OptunaSpec(BaseModel):
    n_trials: int = 50
    n_jobs: int = 1
    seed: int | None = None


class StudySpec(BaseModel):
    """User-facing study contract for transmon-cross electrostatic + LOM optimization."""

    targets: dict[str, float] = Field(
        ...,
        description="Target Hamiltonian parameters, e.g. f_q_GHz and alpha_MHz.",
    )
    tolerances: dict[str, float] = Field(
        default_factory=dict,
        description="Absolute tolerances per target key (same keys as targets).",
    )
    weights: dict[str, float] = Field(
        default_factory=dict,
        description="Relative weights per target key for the scalar score.",
    )
    template: str = "transmon_cross_grounded"
    search: dict[str, RangeSpec] = Field(
        ...,
        description=(
            "Search bounds. Expected keys: cross_length_um, claw_length_um, "
            "ground_spacing_um, L_J_nH."
        ),
    )
    optuna: OptunaSpec = Field(default_factory=OptunaSpec)
    L_J_nH: float | None = Field(
        default=None,
        description="Deprecated fixed L_J; use search.L_J_nH instead.",
    )
    palace_bin: str | None = Field(
        default=None,
        description="Path to Palace executable; defaults to PALACE_BIN env var.",
    )
    mpi_processes: int = 1
    mesh_surface_size_um: float = 0.5
    mesh_scale: float = 1000.0
    topology: str = "grounded"

    @model_validator(mode="after")
    def validate_template_and_topology(self) -> "StudySpec":
        if self.template != "transmon_cross_grounded":
            raise ValueError('Only template "transmon_cross_grounded" is implemented.')
        if self.topology.lower() not in ("grounded",):
            raise ValueError('Only topology "grounded" is implemented for v0.')
        return self

    @model_validator(mode="after")
    def fill_defaults(self) -> "StudySpec":
        required = ("f_q_GHz", "alpha_MHz")
        for key in required:
            if key not in self.targets:
                raise ValueError(f"targets must include {key!r}")
        for key in required:
            self.tolerances.setdefault(key, 0.05 if key == "f_q_GHz" else 15.0)
            self.weights.setdefault(key, 1.0)
        return self

    @classmethod
    def from_json_file(cls, path: str | Path) -> "StudySpec":
        import json

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls.model_validate(data)
