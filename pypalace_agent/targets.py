"""Score simulated Hamiltonian parameters against user targets."""

from __future__ import annotations

from typing import Any

from .schema import StudySpec


def evaluate_targets(
    spec: StudySpec,
    metrics: dict[str, float],
) -> dict[str, Any]:
    """
    Compare LOM metrics to ``spec.targets``.

    Parameters
    ----------
    spec : StudySpec
        Study specification with targets, tolerances, and weights.
    metrics : dict
        Must include ``frequency_GHz`` and ``anharmonicity_MHz`` (LOM output keys)
        or aliases ``f_q_GHz`` / ``alpha_MHz``.

    Returns
    -------
    dict
        score, satisfied, breakdown, metrics (normalized keys)
    """
    f_q = metrics.get("f_q_GHz", metrics.get("frequency_GHz"))
    alpha = metrics.get("alpha_MHz", metrics.get("anharmonicity_MHz"))
    if f_q is None or alpha is None:
        raise ValueError("metrics must include qubit frequency and anharmonicity")

    normalized = {"f_q_GHz": float(f_q), "alpha_MHz": float(alpha)}
    breakdown: dict[str, dict[str, float]] = {}
    score = 0.0
    satisfied = True

    for key, target in spec.targets.items():
        if key not in normalized:
            raise ValueError(f"Unknown target key {key!r}")
        achieved = normalized[key]
        tol = spec.tolerances.get(key, 1.0)
        weight = spec.weights.get(key, 1.0)
        err = achieved - target
        norm_err = err / tol if tol else err
        within = abs(err) <= tol
        if not within:
            satisfied = False
        breakdown[key] = {
            "target": target,
            "achieved": achieved,
            "error": err,
            "normalized_error": norm_err,
            "tolerance": tol,
            "within_tolerance": within,
        }
        score += weight * (norm_err**2)

    return {
        "score": score,
        "satisfied": satisfied,
        "breakdown": breakdown,
        "metrics": normalized,
    }
