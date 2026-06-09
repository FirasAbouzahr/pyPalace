import os
import platform
import shutil
from pathlib import Path

def get_palace_executable() -> str:
    """Return path to a Palace executable suitable for pyPalace Simulation.run()."""
    if env_path := os.environ.get("PATH_TO_PALACE"):
        path = Path(env_path).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"PATH_TO_PALACE does not exist: {path}")
        return str(path)

    machine = platform.machine().lower()
    if machine in {"arm64", "aarch64"}:
        preferred = ("palace-arm64.bin", "palace-x86_64.bin", "palace")
    else:
        preferred = ("palace-x86_64.bin", "palace-arm64.bin", "palace")

    # Direct hits on PATH (some installs only expose the .bin)
    for name in preferred:
        if found := shutil.which(name):
            return found

    # Wrapper on PATH → look for siblings in the same directory
    if wrapper := shutil.which("palace"):
        bindir = Path(wrapper).parent
        for name in preferred:
            candidate = bindir / name
            if candidate.is_file():
                return str(candidate)

    raise RuntimeError(
        "Palace executable not found. Add Palace to PATH, or set "
        "PATH_TO_PALACE to palace-x86_64.bin (or palace-arm64.bin on Apple Silicon)."
    )
