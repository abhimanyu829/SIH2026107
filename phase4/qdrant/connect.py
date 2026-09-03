"""One Qdrant Cloud client, from QDRANT_URL + QDRANT_API_KEY. Nothing else.

Credentials come only from the environment; the URL and key are never printed.
Run this file directly to test the connection:  python qdrant/connect.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

HINT = ("Qdrant Cloud console -> Cluster -> API keys: QDRANT_URL is the cluster\n"
        "  REST endpoint (https://xxxx.cloud.qdrant.io:6333), QDRANT_API_KEY its key.")


def get_client():
    """Returns a QdrantClient pointed at QDRANT_URL, or exits with a clear,
    secret-free message. Never starts a local server."""
    try:
        from qdrant_client import QdrantClient
    except ImportError:
        sys.stderr.write("[DEPENDENCY] qdrant-client is missing. "
                         "pip install -r phase4/requirements.txt\n")
        sys.exit(2)
    url = config.require("QDRANT_URL", HINT)
    api_key = config.require("QDRANT_API_KEY", "Set it to the cluster's API key.")
    try:
        client = QdrantClient(url=url, api_key=api_key,
                              timeout=config.QDRANT_TIMEOUT,
                              prefer_grpc=config.QDRANT_PREFER_GRPC)
    except Exception as e:
        sys.stderr.write(
            "\n[QDRANT CONNECTION FAILED]\n"
            "  target : %s\n"
            "  error  : %s: %s\n"
            "  checks : URL includes https:// and :6333? API key current? cluster not deleted?\n"
            "  Phase-3 data is untouched by this failure - nothing needs rebuilding.\n"
            % (config.redact(url), type(e).__name__, str(e).strip()))
        sys.exit(3)
    return client


def describe(client=None):
    """Prints cluster identity for the log. Contains no secret."""
    client = client or get_client()
    info = client.get_collections()
    names = [c.name for c in info.collections]
    print("  target     : %s" % config.redact(os.environ.get("QDRANT_URL", "")))
    print("  collections: %d %s" % (len(names), names))
    return names


if __name__ == "__main__":
    print("[qdrant] connecting ...")
    describe()
    print("[qdrant] connection OK")
