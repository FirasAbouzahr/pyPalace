"""Optuna study driver for agentic transmon optimization."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schema import StudySpec
from .trial import (
    GeometryCache,
    TrialParams,
    run_geometry_pipeline,
    run_trial,
    save_geometry_cache,
)

SEARCH_KEYS = (
    "cross_length_um",
    "claw_length_um",
    "ground_spacing_um",
    "L_J_nH",
)


def run_study(
    spec: StudySpec,
    *,
    workspace: Path | None = None,
    study_id: str | None = None,
) -> dict[str, Any]:
    """
    Run an Optuna study from ``spec`` and write ``result.json`` under the study directory.
    """
    try:
        import optuna
    except ImportError as e:
        raise ImportError(
            "Optuna is required for studies. Install with: pip install 'pypalace[agentic]'"
        ) from e

    workspace = Path(workspace or Path.cwd() / "pypalace_studies")
    study_id = study_id or (
        datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    )
    study_path = workspace / study_id
    study_path.mkdir(parents=True, exist_ok=True)

    with open(study_path / "spec.json", "w", encoding="utf-8") as f:
        json.dump(spec.model_dump(), f, indent=2)

    for key in SEARCH_KEYS:
        if key not in spec.search:
            raise ValueError(f"search must include {key!r}")

    cache: GeometryCache | None = None
    cache_dir = study_path / "geometry_cache"

    def objective(trial: optuna.Trial) -> float:
        nonlocal cache
        params_dict = {
            name: trial.suggest_float(name, bounds.min, bounds.max)
            for name, bounds in spec.search.items()
        }
        params = TrialParams.from_optuna_params(params_dict)
        trial_dir = study_path / "trials" / str(trial.number)
        trial_dir.mkdir(parents=True, exist_ok=True)

        if cache is None or cache.key != params.geometry_key():
            cache = run_geometry_pipeline(trial_dir, params, spec)
            save_geometry_cache(cache, cache_dir)

        result = run_trial(trial_dir, params, spec, cache=cache)
        trial.set_user_attr("metrics", result["evaluation"]["metrics"])
        trial.set_user_attr("satisfied", result["evaluation"]["satisfied"])
        trial.set_user_attr("params", result["params"])
        return float(result["evaluation"]["score"])

    sampler = optuna.samplers.TPESampler(seed=spec.optuna.seed)
    study = optuna.create_study(direction="minimize", sampler=sampler)
    study.optimize(
        objective,
        n_trials=spec.optuna.n_trials,
        n_jobs=spec.optuna.n_jobs,
        show_progress_bar=True,
    )

    best = study.best_trial
    metrics = best.user_attrs.get("metrics", {})
    out = {
        "study_id": study_id,
        "study_path": str(study_path),
        "satisfied": bool(best.user_attrs.get("satisfied", False)),
        "best": {
            **best.params,
            "f_q_GHz": metrics.get("f_q_GHz"),
            "alpha_MHz": metrics.get("alpha_MHz"),
        },
        "best_score": best.value,
        "targets": spec.targets,
        "tolerances": spec.tolerances,
        "n_trials": len(study.trials),
    }
    with open(study_path / "result.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    return out


def load_study_result(study_path: Path | str) -> dict[str, Any]:
    with open(Path(study_path) / "result.json", encoding="utf-8") as f:
        return json.load(f)
