"""One Supabase PostgreSQL connection, from SUPABASE_DATABASE_URL. Nothing else.

Credentials come only from the environment; the URL is never printed unredacted.
Run this file directly to test the connection:  python supabase/connect.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

HINT = ("Supabase -> Project Settings -> Database -> Connection string -> URI.\n"
        "  Use the connection pooler URI (port 6543) if your network blocks 5432.")


def dsn():
    """The connection string, with sslmode=require added when absent (Supabase needs TLS)."""
    url = config.require("SUPABASE_DATABASE_URL", HINT)
    if "sslmode=" not in url:
        url += ("&" if "?" in url else "?") + "sslmode=require"
    return url


def connect(autocommit=False):
    """Returns a psycopg2 connection with search_path already set to the bis schema.

    Raises SystemExit with a readable message on a connection failure - a Phase-4
    connection problem must never be mistaken for a Phase-3 data problem.
    """
    try:
        import psycopg2
    except ImportError:
        sys.stderr.write("[DEPENDENCY] psycopg2 is missing. "
                         "pip install -r phase4/requirements.txt\n")
        sys.exit(2)
    url = dsn()
    try:
        conn = psycopg2.connect(url, connect_timeout=20,
                                application_name="bis-sih26107-phase4",
                                options="-c statement_timeout=600000")
    except Exception as e:
        sys.stderr.write(
            "\n[SUPABASE CONNECTION FAILED]\n"
            "  target : %s\n"
            "  error  : %s: %s\n"
            "  checks : project not paused? password URL-encoded? pooler port 6543?\n"
            "  Phase-3 data is untouched by this failure - nothing needs rebuilding.\n"
            % (config.redact(url), type(e).__name__, str(e).strip()))
        sys.exit(3)
    conn.autocommit = autocommit
    with conn.cursor() as cur:
        cur.execute("SET search_path TO %s, public;" % config.PG_SCHEMA)
    if not autocommit:
        conn.commit()
    return conn


def describe():
    """Prints server identity for the log. Contains no secret."""
    conn = connect(autocommit=True)
    with conn.cursor() as cur:
        cur.execute("SELECT current_database(), current_user, "
                    "split_part(version(), ' on ', 1), pg_size_pretty("
                    "pg_database_size(current_database()));")
        db, user, ver, size = cur.fetchone()
    conn.close()
    print("  target   : %s" % config.redact(dsn()))
    print("  database : %s   role: %s" % (db, user))
    print("  server   : %s   size: %s" % (ver, size))
    return True


if __name__ == "__main__":
    print("[supabase] connecting ...")
    describe()
    print("[supabase] connection OK")
