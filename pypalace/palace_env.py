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


def get_palace_schema():
    """
    Locate Palace ``config-schema.json`` for optional config validation.

    Search order:
    1. ``PALACE_SCHEMA`` or ``PATH_TO_PALACE_SCHEMA`` environment variable
    2. Walk upward from the Palace executable (and ``PATH_TO_PALACE``) looking for
       ``scripts/schema/config-schema.json`` (Palace source-tree layout)

    Returns
    -------
    str or None
        Absolute path to the schema file, or ``None`` if it could not be found.
    """

    for env_name in ("PALACE_SCHEMA", "PATH_TO_PALACE_SCHEMA"):
        if env_path := os.environ.get(env_name):
            path = Path(env_path).expanduser()
            if path.is_file():
                return str(path.resolve())
            print(
                "USER WARNING: {} does not point to a schema file ({}), "
                "trying auto-detect instead.".format(env_name, path)
            )

    search_roots = []

    if env_palace := os.environ.get("PATH_TO_PALACE"):
        search_roots.append(Path(env_palace).expanduser().resolve())

    try:
        search_roots.append(Path(get_palace_executable()).resolve())
    except (RuntimeError, FileNotFoundError):
        pass

    seen = set()
    for root in search_roots:
        for parent in [root.parent, *root.parent.parents]:
            key = str(parent)
            if key in seen:
                continue
            seen.add(key)
            candidate = parent / "scripts" / "schema" / "config-schema.json"
            if candidate.is_file():
                return str(candidate.resolve())

    return None
