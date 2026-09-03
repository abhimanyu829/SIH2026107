"""Phase-6 agent layer: store + tools (phase5 registry) + pipeline."""
from . import store  # noqa: F401
from .pipeline import run_analysis, run_via_graph  # noqa: F401
from . import tools as _tools  # noqa: F401  (registers on import)


def ensure_registered():
    """Imports the tool module so all 14 phase-6 tools register."""
    return _tools
