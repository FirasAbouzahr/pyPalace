from .config import Config

__all__ = ["Config", "Simulation", "Mesh", "mesh"]


def __getattr__(name):
    if name == "Simulation":
        from .simulation import Simulation

        return Simulation
    if name in ("Mesh", "mesh"):
        from .meshing import Mesh

        return Mesh
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
