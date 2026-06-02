# pyPalace agentic studies (experimental)

Automated TransmonCross optimization: **Qiskit Metal (scripted)** → **pyPalace mesh** → **Palace electrostatics** → **LOM** → **Optuna**, driven by a JSON study spec.

This lives in the **`pypalace_agent`** package on the agentic branch — not in core `pypalace`.

## Install

```bash
pip install -e ".[agentic]"
# Prerequisites (not installed by pip):
#   - AWS Palace (set PALACE_BIN)
#   - qiskit-metal (scripted layouts)
```

## Study spec

See `examples/agentic/transmon_cross_study.json`:

```json
{
  "targets": { "f_q_GHz": 4.5, "alpha_MHz": -250 },
  "tolerances": { "f_q_GHz": 0.05, "alpha_MHz": 15 },
  "weights": { "f_q_GHz": 1.0, "alpha_MHz": 1.0 },
  "search": {
    "cross_length_um": { "min": 200, "max": 400 },
    "claw_length_um": { "min": 50, "max": 200 },
    "ground_spacing_um": { "min": 5, "max": 30 },
    "L_J_nH": { "min": 5, "max": 30 }
  }
}
```

## CLI

```bash
export PALACE_BIN=/path/to/palace

pypalace-agent run examples/agentic/transmon_cross_study.json

pypalace-agent result pypalace_studies/<study_id>
```

Artifacts: `pypalace_studies/<study_id>/trials/`, `result.json`, `geometry_cache/` (reused when only `L_J_nH` changes).

## MCP (Cursor / other clients)

```json
{
  "mcpServers": {
    "pypalace-agent": {
      "command": "python",
      "args": ["-m", "pypalace_agent.mcp_server"],
      "env": {
        "PALACE_BIN": "/path/to/palace"
      }
    }
  }
}
```

Tools: `run_study_from_spec`, `get_study_result`, `evaluate_targets_tool`.

## Notes

- Template: grounded **TransmonCross** (Example 02 style), 4D search including **L_J**.
- Geometry maps to Metal options: top-level ``cross_length``; ``connection_pads.claw.claw_length`` and ``ground_spacing`` (``claw_gap`` fixed at 6 µm, Metal default).
- Slurm / multi-qubit: not in v0.
