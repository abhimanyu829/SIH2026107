"""Bulk-loads the frozen Phase-3 CSVs into Supabase with COPY. Re-runnable, no duplicates.

Order matters and is deliberate:
  1. TRUNCATE all 50 tables in a single statement - one statement handles the FK graph
     without CASCADE surprises, and makes a re-run land on exactly the same row counts
     instead of doubling anything.
  2. COPY every table from its CSV, streamed from the client with copy_expert, so no
     server-side file access is needed (Supabase does not give you the server filesystem).
     The column list is read from each CSV's own header, so column order can never drift.
  3. Apply sql/indexes.sql - foreign keys and indexes AFTER the data. Validating each
     constraint once against a finished table is far cheaper than per-row checks during
     the load, and it is the reason this finishes in one pass.

Empty CSV field -> NULL (WITH NULL ''), which is what Phase 3 documented: a NULL means
'not established by the uploaded data'. FORCE_NULL is applied to the FK columns so a
quoted empty string can never be mistaken for a real key.
"""
import csv
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
from connect import connect  # noqa: E402

csv.field_size_limit(50_000_000)


def manifest():
    """[(table, csv_abs_path, [columns], [fk_columns], [int_columns])] in manifest order."""
    with open(config.MANIFEST, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        path = os.path.join(config.DATA_DIR, r["csv_path"])
        if not os.path.exists(path):
            sys.exit("[LOAD] missing Phase-3 CSV: %s" % r["csv_path"])
        with open(path, encoding="utf-8-sig", newline="") as fh:
            cols = next(csv.reader(fh))
        fks = [s.split("->")[0].strip()
               for s in r["foreign_keys"].split(";") if s.strip()]
        # integer + numeric cols that may carry literal "NULL" text in Phase-3 CSVs
        int_cols = [s.strip() for s in r.get("integer_columns", "").split(";")
                    if s.strip()]
        int_cols += [s.strip() for s in r.get("numeric_columns", "").split(";")
                     if s.strip()]
        out.append((r["table_name"], path, cols, fks, int_cols))
    return out


def csv_rows(path):
    """Data rows in a CSV, counted the same way COPY will read them."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        return max(0, sum(1 for _ in csv.reader(f)) - 1)


def _sanitize_csv(path, cols, int_col_set):
    """Returns a bytes object with literal 'NULL' text AND any non-numeric text in
    int/numeric columns replaced by empty string, so COPY WITH NULL '' handles them
    correctly.

    Phase-3 provenance data contains categorical confidence labels ('HIGH','MEDIUM',
    'LOW') in a column declared NUMERIC.  Any value that cannot be parsed as a Python
    float is silently mapped to NULL rather than aborting the load.
    """
    import io
    int_idxs = {i for i, c in enumerate(cols) if c in int_col_set}
    if not int_idxs:
        return None   # no sanitisation needed; caller uses file directly
    buf = io.StringIO()
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        writer = csv.writer(buf)
        for row in reader:
            for i in int_idxs:
                if i < len(row):
                    v = row[i].strip()
                    if v == "NULL":
                        row[i] = ""          # literal NULL → PostgreSQL NULL
                    elif v:
                        try:
                            float(v)         # parseable numeric → leave as-is
                        except ValueError:
                            row[i] = ""      # text label ('HIGH' etc.) → NULL
            writer.writerow(row)
    return buf.getvalue().encode("utf-8")


def copy_table(cur, table, path, cols, fks, int_cols=None):
    """COPY one CSV into one table. Returns rows loaded."""
    collist = ", ".join('"' + c + '"' for c in cols)
    force = ""
    if fks:
        force = ", FORCE_NULL (%s)" % ", ".join('"' + c + '"' for c in fks)
    sql = ("COPY %s.%s (%s) FROM STDIN WITH (FORMAT csv, HEADER true, NULL ''%s, "
           "ENCODING 'UTF8')" % (config.PG_SCHEMA, table, collist, force))
    int_col_set = set(int_cols or [])
    sanitized = _sanitize_csv(path, cols, int_col_set)
    if sanitized is not None:
        import io
        cur.copy_expert(sql, io.BytesIO(sanitized), size=1 << 20)
    else:
        with open(path, "rb") as fh:
            cur.copy_expert(sql, fh, size=1 << 20)
    return cur.rowcount


def main(apply_constraints=True):
    tables = manifest()
    print("[load] %d tables from %s" % (len(tables), os.path.relpath(config.DATA_DIR)))
    conn = connect(autocommit=False)
    result, t0 = {}, time.time()
    try:
        with conn.cursor() as cur:
            # Constraints from a previous run would make TRUNCATE order-sensitive and
            # slow the COPY down, so they are dropped and rebuilt in step 3.
            # String concatenation, not %-formatting: pg format()'s %I must reach
            # PostgreSQL intact, and psycopg2 only interpolates % when args are
            # passed. config.PG_SCHEMA is the trusted constant "bis", not user input.
            cur.execute(
                "SELECT format('ALTER TABLE %I.%I DROP CONSTRAINT %I', n.nspname, "
                "t.relname, c.conname) FROM pg_constraint c "
                "JOIN pg_class t ON t.oid = c.conrelid "
                "JOIN pg_namespace n ON n.oid = t.relnamespace "
                "WHERE c.contype = 'f' AND n.nspname = '" + config.PG_SCHEMA + "';")
            drops = [r[0] for r in cur.fetchall()]
            for d in drops:
                cur.execute(d)
            if drops:
                print("[load] dropped %d existing FK constraints for the bulk load"
                      % len(drops))
            names = ", ".join("%s.%s" % (config.PG_SCHEMA, t[0]) for t in tables)
            cur.execute("TRUNCATE %s;" % names)
            print("[load] truncated %d tables (re-run safe)" % len(tables))
            for i, (table, path, cols, fks, int_cols) in enumerate(tables, 1):
                n = copy_table(cur, table, path, cols, fks, int_cols)
                result[table] = n
                print("  %2d/%d  %-38s %8d rows" % (i, len(tables), table, n),
                      flush=True)
        conn.commit()
        if apply_constraints:
            idx = open(os.path.join(config.SQL_DIR, "indexes.sql"), encoding="utf-8").read()
            print("[load] applying foreign keys and indexes ...")
            with conn.cursor() as cur:
                cur.execute(idx)
            conn.commit()
            print("[load] constraints and indexes applied")
    except Exception as e:
        conn.rollback()
        sys.stderr.write("\n[LOAD FAILED] %s: %s\n"
                         "  Nothing was committed for the failing step; Phase-3 files on "
                         "disk are untouched.\n" % (type(e).__name__, str(e).strip()))
        sys.exit(5)
    finally:
        conn.close()
    total = sum(result.values())
    print("[load] %d rows across %d tables in %.1fs" % (total, len(result), time.time() - t0))
    return result


if __name__ == "__main__":
    main()
