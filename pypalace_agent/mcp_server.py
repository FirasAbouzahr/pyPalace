"""MCP server exposing pypalace-agent study tools (stdio transport)."""

from __future__ import annotations

import json
from pathlib import Path

from .schema import StudySpec
from .study import load_study_result, run_study
from .targets import evaluate_targets


def run_mcp_server() -> None:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as e:
        raise ImportError(
            "MCP support requires: pip install 'pypalace[agentic]'"
        ) from e

    mcp = FastMCP("pypalace-agent")

    @mcp.tool()
    def run_study_from_spec(
        spec_path: str,
        workspace: str | None = None,
        study_id: str | None = None,
    ) -> str:
        """Run an Optuna design study from a JSON specification file."""
        spec = StudySpec.from_json_file(spec_path)
        result = run_study(
            spec,
            workspace=Path(workspace) if workspace else None,
            study_id=study_id,
        )
        return json.dumps(result, indent=2)

    @mcp.tool()
    def get_study_result(study_path: str) -> str:
        """Load result.json from a completed study directory."""
        return json.dumps(load_study_result(study_path), indent=2)

    @mcp.tool()
    def evaluate_targets_tool(
        spec_json: str,
        metrics_json: str,
    ) -> str:
        """
        Score LOM metrics against targets.

        metrics_json should include frequency_GHz and anharmonicity_MHz (or f_q_GHz / alpha_MHz).
        """
        spec = StudySpec.model_validate(json.loads(spec_json))
        metrics = json.loads(metrics_json)
        return json.dumps(evaluate_targets(spec, metrics), indent=2)

    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_mcp_server()
