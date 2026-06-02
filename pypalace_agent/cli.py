"""Command-line interface for pypalace-agent."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .schema import StudySpec
from .study import load_study_result, run_study


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pypalace-agent",
        description="Optimize TransmonCross designs with Palace electrostatics + LOM.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Start an Optuna study from a JSON spec file.")
    run_p.add_argument("spec", type=Path, help="Path to study.json")
    run_p.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="Directory for study artifacts (default: ./pypalace_studies).",
    )
    run_p.add_argument("--study-id", type=str, default=None, help="Optional study folder name.")

    status_p = sub.add_parser("result", help="Print result.json for a completed study.")
    status_p.add_argument("study_path", type=Path, help="Path to study directory.")

    args = parser.parse_args(argv)

    if args.command == "run":
        spec = StudySpec.from_json_file(args.spec)
        out = run_study(spec, workspace=args.workspace, study_id=args.study_id)
        print(json.dumps(out, indent=2))
        return 0 if out.get("satisfied") else 0

    if args.command == "result":
        out = load_study_result(args.study_path)
        print(json.dumps(out, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
