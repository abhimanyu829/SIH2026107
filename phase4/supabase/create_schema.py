"""Creates the Supabase schema from the FROZEN Phase-3 DDL. Re-runnable.

sql/schema.sql inlines POSTGRES_READY/DDL.sql byte for byte; before executing anything
this script re-hashes the frozen file and confirms the inlined copy still matches, so a
drifted or hand-edited schema cannot be loaded silently. Phase 4 does not redesign the
model - it only adds the alias views and, later, the constraints Phase 3 declared in
TABLE_MANIFEST.csv but did not enforce.

The DDL drops and recreates its tables, so running this again gives a clean, empty
schema; load_data.py then refills it.
"""
import hashlib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
from connect import connect  # noqa: E402

SCHEMA_SQL = os.path.join(config.SQL_DIR, "schema.sql")


def verify_frozen_ddl():
    """Proves sql/schema.sql still contains the frozen Phase-3 DDL, unmodified."""
    text = open(SCHEMA_SQL, encoding="utf-8").read()
    m = re.search(r"--   sha256 : ([0-9a-f]{64})", text)
    if not m:
        sys.exit("[SCHEMA] schema.sql has no recorded Phase-3 DDL sha256 - refusing to run.")
    recorded = m.group(1)
    actual = hashlib.sha256(
        open(config.FROZEN_DDL, encoding="utf-8").read().encode("utf-8")).hexdigest()
    if recorded != actual:
        sys.exit("[SCHEMA] POSTGRES_READY/DDL.sql has changed since schema.sql was built\n"
                 "  recorded %s\n  on disk  %s\n"
                 "  Regenerate schema.sql; do not edit it by hand." % (recorded, actual))
    body = text.split("SECTION 1: FROZEN PHASE-3 DDL", 1)[1]
    frozen = open(config.FROZEN_DDL, encoding="utf-8").read()
    if frozen not in body:
        sys.exit("[SCHEMA] the inlined DDL in schema.sql is not byte-identical to the "
                 "frozen Phase-3 DDL - refusing to run.")
    print("  frozen Phase-3 DDL verified: sha256 %s..." % actual[:16])
    return text


def main():
    print("[schema] verifying the frozen Phase-3 DDL ...")
    sql = verify_frozen_ddl()
    conn = connect(autocommit=False)
    try:
        with conn.cursor() as cur:
            print("[schema] executing schema.sql (%d KB) ..." % (len(sql) // 1024))
            cur.execute(sql)
            cur.execute("SELECT count(*) FROM information_schema.tables "
                        "WHERE table_schema=%s AND table_type='BASE TABLE';",
                        (config.PG_SCHEMA,))
            tables = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM information_schema.views "
                        "WHERE table_schema=%s;", (config.PG_SCHEMA,))
            views = cur.fetchone()[0]
        conn.commit()
    except Exception as e:
        conn.rollback()
        sys.stderr.write("[SCHEMA FAILED] %s: %s\n" % (type(e).__name__, str(e).strip()))
        sys.exit(4)
    finally:
        conn.close()
    print("[schema] %d tables + %d views in schema '%s'" % (tables, views, config.PG_SCHEMA))
    if tables != config.EXPECTED_TABLES:
        sys.exit("[SCHEMA] expected %d tables, found %d" % (config.EXPECTED_TABLES, tables))
    print("[schema] OK")
    return {"tables": tables, "views": views}


if __name__ == "__main__":
    main()
