"""Centralized tool registry.

Every tool is a plain function with: typed args, typed dict output, its own
validation + error handling, and provenance (source tables / collection) in the
result. The LLM never sees SQL - it sees these functions only.
"""


class ToolResult(dict):
    """Uniform tool output: {'ok', 'tool', 'data', 'error', 'provenance'}."""


def tool(name, description, provenance=""):
    """Decorator registering a function into the registry with metadata."""
    def wrap(fn):
        fn._tool_name = name
        fn._tool_description = description
        fn._tool_provenance = provenance
        _REGISTRY[name] = fn
        return fn
    return wrap


_REGISTRY = {}


def registry():
    """{name: callable} - the one tool registry the graph uses."""
    _ensure_all_imported()
    return dict(_REGISTRY)


def tool_specs():
    """Name + description pairs for the LLM prompt (cheap, no schemas dumped)."""
    _ensure_all_imported()
    return [{"name": n, "description": f._tool_description}
            for n, f in sorted(_REGISTRY.items())]


def call(name, **kwargs):
    """Invokes a registered tool; never raises - failures become ok=False.

    SystemExit included: a missing-credential exit deep in a Phase-4 connector
    becomes a clean 'credentials missing' tool error, so the graph degrades to
    UNKNOWN answers instead of dying mid-request.
    """
    _ensure_all_imported()
    fn = _REGISTRY.get(name)
    if fn is None:
        return ToolResult(ok=False, tool=name, data=None,
                          error="unknown tool", provenance="")
    try:
        return fn(**kwargs)
    except SystemExit as e:
        return ToolResult(ok=False, tool=name, data=None,
                          error="credentials missing (exit %s)" % e.code,
                          provenance="")
    except TypeError as e:
        return ToolResult(ok=False, tool=name, data=None,
                          error="bad arguments: %s" % e, provenance="")
    except Exception as e:
        return ToolResult(ok=False, tool=name, data=None,
                          error="%s: %s" % (type(e).__name__, str(e)[:200]),
                          provenance="")


_LOADED = False


def _ensure_all_imported():
    """Imports tool modules once so decorators register their functions."""
    global _LOADED
    if _LOADED:
        return
    for m in ("products", "standards", "qco", "schemes", "manuals", "tests",
              "labs", "evidence", "verification", "comparison"):
        __import__("tools." + m)
    _LOADED = True
