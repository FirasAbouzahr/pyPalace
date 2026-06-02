"""Unit tests for pypalace_agent (no Palace / Metal required)."""

import json
from pathlib import Path

from pypalace_agent.schema import StudySpec
from pypalace_agent.targets import evaluate_targets


def test_study_spec_from_example_json():
    path = Path(__file__).resolve().parents[1] / "examples/agentic/transmon_cross_study.json"
    spec = StudySpec.from_json_file(path)
    assert spec.targets["f_q_GHz"] == 4.5
    assert spec.search["L_J_nH"].max == 30


def test_evaluate_targets_satisfied():
    spec = StudySpec.model_validate(
        {
            "targets": {"f_q_GHz": 4.5, "alpha_MHz": -250},
            "tolerances": {"f_q_GHz": 0.05, "alpha_MHz": 15},
            "weights": {"f_q_GHz": 1.0, "alpha_MHz": 1.0},
            "search": {
                "cross_length_um": {"min": 200, "max": 400},
                "claw_length_um": {"min": 50, "max": 200},
                "ground_spacing_um": {"min": 5, "max": 30},
                "L_J_nH": {"min": 5, "max": 30},
            },
        }
    )
    out = evaluate_targets(
        spec,
        {"frequency_GHz": 4.48, "anharmonicity_MHz": -248},
    )
    assert out["satisfied"] is True
    assert out["score"] < 1.0


def test_evaluate_targets_miss():
    spec = StudySpec.model_validate(
        {
            "targets": {"f_q_GHz": 4.5, "alpha_MHz": -250},
            "search": {
                "cross_length_um": {"min": 200, "max": 400},
                "claw_length_um": {"min": 50, "max": 200},
                "ground_spacing_um": {"min": 5, "max": 30},
                "L_J_nH": {"min": 5, "max": 30},
            },
        }
    )
    out = evaluate_targets(
        spec,
        {"f_q_GHz": 5.5, "alpha_MHz": -100},
    )
    assert out["satisfied"] is False
    assert out["score"] > 1.0
