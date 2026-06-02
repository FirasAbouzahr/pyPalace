"""TransmonCross (grounded Xmon) template for electrostatic LOM studies."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pypalace import Config, mesh
from pypalace.builder import Boundaries, Domains, Model, Solver

# Matches Example 02 TransmonCross notebook naming.
MESH_ATTRIBUTES = {
    "cross": 1,
    "claw_connector_arm": 2,
}


def build_transmon_cross_design(
    cross_length_um: float,
    claw_length_um: float,
    ground_spacing_um: float,
) -> Any:
    """
    Build a planar Qiskit Metal design with one TransmonCross component (no GUI).

    Parameters are given in micrometers and map to common TransmonCross option keys.
    """
    from qiskit_metal import designs
    from qiskit_metal.qlibrary.qubits.transmon_cross import TransmonCross
    from qiskit_metal.toolbox_python.attr_dict import Dict

    design = designs.DesignPlanar()
    options = Dict(
        cross_length=f"{cross_length_um}um",
        connection_pads=Dict(
            claw=Dict(
                connector_location="90",
                connector_type="0",
                claw_length=f"{claw_length_um}um",
                ground_spacing=f"{ground_spacing_um}um",
                claw_gap="4um",
            )
        ),
    )
    TransmonCross(design, "qubit", options=options)
    design.rebuild()
    return design


def mesh_design(
    design: Any,
    output_mesh: Path,
    *,
    surface_mesh_size_um: float = 0.5,
    mesh_scale: float = 1000.0,
) -> Any:
    """Mesh the design and return the attribute table DataFrame."""
    return mesh.mesh_Quantum_Metal_design(
        design,
        output_mesh=output_mesh,
        Attributes=dict(MESH_ATTRIBUTES),
        surface_mesh_size=surface_mesh_size_um * 1e-3,  # um -> mm (Metal default)
        mesh_scale=mesh_scale,
        verbose=False,
    )


def build_electrostatic_config(
    mesh_path: Path,
    output_dir: Path,
    config_path: Path,
) -> Config:
    """
    Frozen electrostatic Palace config for grounded TransmonCross (Example 02 pattern).

    Attribute IDs follow ``build_and_mesh_transmons.ipynb`` / xmon mesh:
    cross=1, claw=2, substrate=4, air=5, ground_plane=6, far_field=7.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cfg = Config(str(config_path))
    cfg.add_Problem(Type="Electrostatic", Output=str(output_dir), Verbose=1)
    cfg.add_Model(Mesh=str(mesh_path), L0=1.0e-6)

    silicon = Domains.Material(
        Attributes=[4], Permeability=1.0, Permittivity=11.45, LossTan=0.0
    )
    vacuum = Domains.Material(Attributes=[5], Permeability=1.0, Permittivity=1.0, LossTan=0.0)
    cfg.add_Domains(Materials=[silicon, vacuum])

    bcs = [
        Boundaries.Terminal(Index=1, Attributes=[1]),
        Boundaries.Terminal(Index=2, Attributes=[2]),
        Boundaries.Ground(Attributes=[6, 7]),
    ]
    post = [
        Boundaries.Postprocessing_SurfaceFlux(Index=1, Attributes=[1], Type="Electric"),
        Boundaries.Postprocessing_SurfaceFlux(Index=2, Attributes=[2], Type="Electric"),
    ]
    cfg.add_Boundaries(BCs=bcs, Postprocessing=post)

    electro = Solver.Electrostatic(Save=3)
    linear = Solver.Linear(Type="BoomerAMG", KSPType="CG", Tol=1e-6, MaxIts=25)
    cfg.add_Solver(Simulation=electro, Order=2, Linear=linear)
    return cfg

