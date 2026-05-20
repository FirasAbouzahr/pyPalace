from .config import Config

__all__ = ["Config", "Simulation", "mesh"]


def __getattr__(name):
    if name == "Simulation":
        from .simulation import Simulation

        return Simulation
    if name == "mesh":
        from .mesh import mesh

        return mesh
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
