"""Live check #2: Supabase server timeouts + connectivity mode."""
import sys

sys.path.insert(0, ".")
import config as cfg  # noqa: E402

cfg.load_env()

import os  # noqa: E402

import psycopg2  # noqa: E402

conn = psycopg2.connect(os.environ["SUPABASE_DATABASE_URL"])
with conn.cursor() as cur:
    for s in ("statement_timeout", "idle_in_transaction_session_timeout",
              "tcp_user_timeout"):
        cur.execute("SHOW %s" % s)
        print(s, "=", cur.fetchone()[0])
    cur.execute("SELECT usename, useconfig FROM pg_user WHERE usename = 'postgres'")
    print("user config:", cur.fetchall())
    cur.execute("SELECT count(*) FROM bis.is_master")
    print("is_master rows now:", cur.fetchone()[0])
conn.close()
