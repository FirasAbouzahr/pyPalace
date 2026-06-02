"""Single-trial physics: geometry, mesh, electrostatics, LOM."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pypalace.analysis import LOM
from pypalace.simulation import Simulation

from .schema import StudySpec
from .targets import evaluate_targets
from .templates.transmon_cross import (
    build_electrostatic_config,
    build_transmon_cross_design,
    mesh_design,
)


@dataclass
class TrialParams:
    cross_length_um: float
    claw_length_um: float
    ground_spacing_um: float
    L_J_nH: float

    @classmethod
    def from_optuna_params(cls, params: dict[str, float]) -> "TrialParams":
        return cls(
            cross_length_um=float(params["cross_length_um"]),
            claw_length_um=float(params["claw_length_um"]),
            ground_spacing_um=float(params["ground_spacing_um"]),
            L_J_nH=float(params["L_J_nH"]),
        )

    def geometry_key(self) -> tuple[float, float, float]:
        return (self.cross_length_um, self.claw_length_um, self.ground_spacing_um)


@dataclass
class GeometryCache:
    """Reused when only L_J changes between trials."""

    key: tuple[float, float, float]
    mesh_path: Path
    config_path: Path
    output_dir: Path
    capacitance_matrix: Any


def resolve_palace_bin(spec: StudySpec) -> str:
    path = spec.palace_bin or os.environ.get("PALACE_BIN")
    if not path:
        raise EnvironmentError(
            "Set PALACE_BIN to the Palace executable path, or pass palace_bin in the study JSON."
        )
    return path


def run_lom(
    capacitance_matrix: Any,
    L_J_nH: float,
    topology: str = "grounded",
) -> dict[str, float]:
    L_J = L_J_nH * 1e-9
    c_sigma = LOM.calculate_C_Sigma(capacitance_matrix, topology=topology)
    ham = LOM.get_qubit_Hamiltonian_parameters(c_sigma, L_J)
    return {
        "frequency_GHz": ham["frequency_GHz"],
        "anharmonicity_MHz": ham["anharmonicity_MHz"],
        "C_Sigma_F": float(c_sigma),
    }


def run_geometry_pipeline(
    work_dir: Path,
    params: TrialParams,
    spec: StudySpec,
) -> GeometryCache:
    """Build QM design, mesh, run electrostatics, return capacitance matrix."""
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    design = build_transmon_cross_design(
        params.cross_length_um,
        params.claw_length_um,
        params.ground_spacing_um,
    )
    mesh_path = work_dir / "device.msh"
    mesh_design(
        design,
        mesh_path,
        surface_mesh_size_um=spec.mesh_surface_size_um,
        mesh_scale=spec.mesh_scale,
    )

    output_dir = work_dir / "palace_output"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    config_path = work_dir / "config.json"
    cfg = build_electrostatic_config(mesh_path, output_dir, config_path)
    cfg.save_config()

    palace_bin = resolve_palace_bin(spec)
    sim = Simulation(cfg, palace_bin)
    sim.run(n=spec.mpi_processes)

    cap = sim.get_capacitance_matrix()
    return GeometryCache(
        key=params.geometry_key(),
        mesh_path=mesh_path,
        config_path=config_path,
        output_dir=output_dir,
        capacitance_matrix=cap,
    )


def run_trial(
    work_dir: Path,
    params: TrialParams,
    spec: StudySpec,
    cache: GeometryCache | None = None,
) -> dict[str, Any]:
    """
    Execute one trial; reuse ``cache`` when geometry matches and only L_J changed.
    """
    work_dir = Path(work_dir)
    if cache is None or cache.key != params.geometry_key():
        cache = run_geometry_pipeline(work_dir, params, spec)

    lom = run_lom(cache.capacitance_matrix, params.L_J_nH, topology=spec.topology)
    evaluation = evaluate_targets(spec, lom)

    result = {
        "params": {
            "cross_length_um": params.cross_length_um,
            "claw_length_um": params.claw_length_um,
            "ground_spacing_um": params.ground_spacing_um,
            "L_J_nH": params.L_J_nH,
        },
        "lom": lom,
        "evaluation": evaluation,
        "geometry_key": list(cache.key),
    }
    with open(work_dir / "trial_result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    return result


def save_geometry_cache(cache: GeometryCache, path: Path) -> None:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    cache.capacitance_matrix.to_csv(path / "capacitance_matrix.csv")
    meta = {
        "key": list(cache.key),
        "mesh_path": str(cache.mesh_path),
        "config_path": str(cache.config_path),
        "output_dir": str(cache.output_dir),
    }
    with open(path / "cache_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


def load_geometry_cache(path: Path) -> GeometryCache:
    import pandas as pd

    path = Path(path)
    with open(path / "cache_meta.json", encoding="utf-8") as f:
        meta = json.load(f)
    cap = pd.read_csv(path / "capacitance_matrix.csv", index_col=0)
    return GeometryCache(
        key=tuple(meta["key"]),
        mesh_path=Path(meta["mesh_path"]),
        config_path=Path(meta["config_path"]),
        output_dir=Path(meta["output_dir"]),
        capacitance_matrix=cap,
    )
