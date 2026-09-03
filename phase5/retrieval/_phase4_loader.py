"""Load phase4 retrieval modules BY PATH with phase4's own config bound.

Why: phase5 also has a package named `retrieval` and a `config.py`, so a plain
`import retrieval.postgres_retriever` / `import config` inside those modules
would resolve to phase5's versions in the running process. Phase4's config is
executed once under the distinct key 'phase4_config' (NEVER overwriting the
global 'config' entry), and is swapped in as sys.modules['config'] only while
a phase4 module executes - import statements bind the module object they see
at exec time, so runtime `config.X` lookups keep hitting phase4's config.
"""
import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))       # workspace root
PHASE4 = os.path.join(_ROOT, "phase4")

_CFG4 = None


def phase4_config():
    """Exec phase4/config.py once under 'phase4_config' (alias, no globals touched)."""
    global _CFG4
    if _CFG4 is not None:
        return _CFG4
    if "phase4_config" in sys.modules:
        _CFG4 = sys.modules["phase4_config"]
        return _CFG4
    spec = importlib.util.spec_from_file_location(
        "phase4_config", os.path.join(PHASE4, "config.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["phase4_config"] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop("phase4_config", None)
        raise
    _CFG4 = mod
    return _CFG4


def _load(alias, path):
    spec = importlib.util.spec_from_file_location(alias, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    cfg4 = phase4_config()
    prev = sys.modules.get("config")
    sys.modules["config"] = cfg4
    try:
        spec.loader.exec_module(mod)
    finally:
        if prev is not None and prev is not cfg4:
            sys.modules["config"] = prev
        elif prev is None and "config" in sys.modules and \
                sys.modules["config"] is cfg4:
            sys.modules.pop("config", None)
    return mod


def load_phase4_module(relpath, alias):
    """Exec a phase4 module by path; its 'config' resolves to phase4's config."""
    if alias in sys.modules:
        return sys.modules[alias]
    path = os.path.join(PHASE4, *relpath.split("/"))
    # phase4 modules do sys.path.insert(0, phase4_root) themselves; ensure it
    if PHASE4 not in sys.path:
        sys.path.insert(0, PHASE4)
    # connect helpers: phase4 scripts import 'supabase.connect' / 'qdrant.connect'
    for pkg in ("supabase", "qdrant"):
        if pkg not in sys.modules:
            init = os.path.join(PHASE4, pkg, "__init__.py")
            if os.path.exists(init):
                spec = importlib.util.spec_from_file_location(
                    pkg, init,
                    submodule_search_locations=[os.path.join(PHASE4, pkg)])
                m = importlib.util.module_from_spec(spec)
                sys.modules[pkg] = m
                spec.loader.exec_module(m)
    return _load(alias, path)


def load_phase4_connect(pkg, alias):
    """Load phase4's supabase/connect.py or qdrant/connect.py by path.

    connect modules are imported LAZILY by the retrievers (first client use),
    outside any sys.modules swap - so they must be pre-loaded explicitly with
    phase4's config bound, and cached where their `import connect` / package
    lookups will find them.
    """
    path = os.path.join(PHASE4, pkg, "connect.py")
    if alias in sys.modules:
        return sys.modules[alias]
    if PHASE4 not in sys.path:
        sys.path.insert(0, PHASE4)
    pkg_dir = os.path.join(PHASE4, pkg)
    if pkg not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            pkg, os.path.join(pkg_dir, "__init__.py"),
            submodule_search_locations=[pkg_dir])
        m = importlib.util.module_from_spec(spec)
        sys.modules[pkg] = m
        spec.loader.exec_module(m)
    return _load(alias, path)
