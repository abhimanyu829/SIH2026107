"""Validates the Supabase PostgreSQL side. Read-only; safe to re-run.

Compares every canonical table against its Phase-3 CSV, checks PKs, FKs,
uniqueness and NOT NULL sanity, then runs the two end-to-end SQL smoke tests
(IS 17631, IS 2347:2023). Writes the "supabase" section of
validation/PHASE4_VALIDATION.json; exits non-zero on any failure.
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
from connect import connect  # noqa: E402
from load_data import manifest, csv_rows  # noqa: E402

csv.field_size_limit(50_000_000)


def validate():
    print("[pg-validate] connecting ...")
    conn = connect(autocommit=True)
    r = {"tables": {}, "checks": {}}

    def record(name, passed, detail=""):
        r["checks"][name] = {"pass": bool(passed), "detail": str(detail)}
        print("  %-28s %s%s" % (name, "PASS" if passed else "FAIL",
                                ("  " + str(detail)) if detail else ""))
        return passed

    with conn.cursor() as cur:
        # 1. connection
        cur.execute("SELECT current_database(), current_user")
        db, user = cur.fetchone()
        r["connection"] = {"database": db, "role": user}
        print("  connected as %s@%s" % (user, db))

        # 2. every manifest table exists
        tables = manifest()
        missing = []
        for t, path, cols, fks in tables:
            cur.execute("SELECT to_regclass(%s)", ("bis.%s" % t,))
            if cur.fetchone()[0] is None:
                missing.append(t)
        record("tables_exist", not missing,
               "%d expected, %d missing" % (len(tables), len(missing)))

        # 3. row counts vs the Phase-3 CSVs (counted, not assumed)
        bad_counts = []
        total_rows = 0
        for t, path, cols, fks in tables:
            cur.execute('SELECT count(*) FROM bis."%s"' % t)
            n_db = cur.fetchone()[0]
            n_csv = csv_rows(path)
            r["tables"][t] = {"db_rows": n_db, "csv_rows": n_csv}
            total_rows += n_db
            if n_db != n_csv:
                bad_counts.append("%s db=%d csv=%d" % (t, n_db, n_csv))
        r["total_rows"] = total_rows
        record("row_counts_vs_csv", not bad_counts,
               "%d tables, %d rows, %d mismatches"
               % (len(tables), total_rows, len(bad_counts)))
        for b in bad_counts[:5]:
            print("    mismatch: %s" % b)

        # 4. primary keys: blank + duplicate, per table, straight from catalog
        pk_tables = [t for t, _, _, _ in tables if _pk_col(cur, t)]
        blank_pks, dup_pks = [], []
        for t in pk_tables:
            pk = _pk_col(cur, t)
            cur.execute('SELECT count(*) FROM bis."%s" '
                        'WHERE "%s" IS NULL OR btrim("%s") = \'\'' % (t, pk, pk))
            if cur.fetchone()[0]:
                blank_pks.append(t)
            cur.execute('SELECT count(*) FROM (SELECT "%s" FROM bis."%s" '
                        'GROUP BY "%s" HAVING count(*) > 1) q' % (pk, t, pk))
            if cur.fetchone()[0]:
                dup_pks.append(t)
        record("blank_primary_keys", not blank_pks,
               "%d PK tables checked" % len(pk_tables))
        record("duplicate_primary_keys", not dup_pks, str(dup_pks or "none"))

        # 5. FK constraints present (Phase-3 declared set) and zero orphans
        cur.execute("SELECT count(*) FROM pg_constraint c JOIN pg_namespace n "
                    "ON n.oid = c.connamespace WHERE c.contype='f' "
                    "AND n.nspname='bis'")
        n_fk = cur.fetchone()[0]
        expected_fk = sum(len(fks) for _, _, _, fks in tables)
        record("fk_constraints_present", n_fk >= expected_fk,
               "%d declared, %d in catalog" % (expected_fk, n_fk))

        fk_map = _fk_map(cur)   # {child_table: {col: (parent_table, parent_col)}}
        orphans = 0
        orphan_detail = []
        for t, path, cols, fks in tables:
            for col in fks:
                parent = fk_map.get(t, {}).get(col)
                if not parent:
                    continue
                ptab, pcol = parent
                cur.execute('SELECT count(*) FROM bis."%s" c '
                            'LEFT JOIN bis."%s" p ON p."%s" = c."%s" '
                            'WHERE c."%s" IS NOT NULL AND p."%s" IS NULL'
                            % (t, ptab, pcol, col, col, pcol))
                n = cur.fetchone()[0]
                if n:
                    orphans += n
                    orphan_detail.append("%s.%s=%d" % (t, col, n))
        record("fk_orphans", orphans == 0,
               "%d orphan values %s" % (orphans, orphan_detail[:3] or ""))

        # 6. NOT NULL sanity on retrieval-critical columns
        cur.execute("SELECT count(*) FROM bis.is_master "
                    "WHERE canonical_is_number IS NULL OR btrim(canonical_is_number)=''")
        n1 = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM bis.product_master "
                    "WHERE product_name IS NULL OR btrim(product_name)=''")
        n2 = cur.fetchone()[0]
        record("not_null_business_columns", n1 == 0 and n2 == 0,
               "is_master.canonical_is_number=%d, product_master.product_name=%d"
               % (n1, n2))

        # 7. end-to-end smoke: IS 17631 through the relationship tables
        cur.execute("SELECT is_id, canonical_is_number, title FROM bis.is_master "
                    "WHERE canonical_is_number = 'IS 17631'")
        s = cur.fetchone()
        record("smoke_is_17631_lookup", bool(s), str(s) if s else "not found")
        smoke = {}
        if s:
            is_id = s[0]
            cur.execute("SELECT count(*) FROM bis.is_product_mapping WHERE is_id=%s",
                        (is_id,))
            n_prod = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM bis.is_test_mapping WHERE is_id=%s",
                        (is_id,))
            n_tests = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM bis.is_lab_test_mapping "
                        "WHERE is_id=%s AND lab_id IS NOT NULL", (is_id,))
            n_labs = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM bis.is_scheme_mapping WHERE is_id=%s",
                        (is_id,))
            n_schemes = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM bis.is_qco_mapping WHERE is_id=%s",
                        (is_id,))
            n_qcos = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM bis.is_product_manual_mapping "
                        "WHERE is_id=%s", (is_id,))
            n_pms = cur.fetchone()[0]
            smoke = {"products": n_prod, "tests": n_tests, "labs": n_labs,
                     "schemes": n_schemes, "qcos": n_qcos, "manuals": n_pms}
            record("smoke_is_17631_connected",
                   n_prod > 0 and n_tests > 0 and n_labs > 0 and n_schemes > 0
                   and n_qcos > 0 and n_pms > 0,
                   "products=%d tests=%d labs=%d schemes=%d qcos=%d manuals=%d"
                   % (n_prod, n_tests, n_labs, n_schemes, n_qcos, n_pms))
        else:
            record("smoke_is_17631_connected", False, "standard not found")
        r["smoke_is_17631"] = smoke

        # 8. second smoke: IS 2347:2023 (display form)
        cur.execute("SELECT is_id, canonical_is_number, display_is_number, title "
                    "FROM bis.is_master WHERE display_is_number = 'IS 2347:2023'")
        s2 = cur.fetchone()
        record("smoke_is_2347_2023", bool(s2),
               str(s2[2:4]) if s2 else "IS 2347:2023 not found")

    conn.close()
    r["pass"] = all(c["pass"] for c in r["checks"].values())
    path = config.merge_validation("supabase", r)
    print("[pg-validate] %s -> %s" % ("PASS" if r["pass"] else "FAIL", path))
    if not r["pass"]:
        sys.exit(6)
    return r


def _pk_col(cur, table):
    cur.execute("SELECT a.attname FROM pg_index i "
                "JOIN pg_class c ON c.oid = i.indrelid "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY(i.indkey) "
                "WHERE i.indisprimary AND n.nspname='bis' AND c.relname=%s", (table,))
    row = cur.fetchone()
    return row[0] if row else None


def _fk_map(cur):
    """One catalog query: {child_table: {fk_column: (parent_table, parent_column)}}."""
    cur.execute("""
        SELECT t.relname, a.attname, p.relname, pa.attname
          FROM pg_constraint c
          JOIN pg_class t  ON t.oid  = c.conrelid
          JOIN pg_class p  ON p.oid  = c.confrelid
          JOIN pg_namespace n ON n.oid = t.relnamespace
          JOIN pg_attribute a  ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
          JOIN pg_attribute pa ON pa.attrelid = c.confrelid
                              AND pa.attnum = ANY(c.confkey)
         WHERE c.contype = 'f' AND n.nspname = 'bis'""")
    m = {}
    for t, col, ptab, pcol in cur.fetchall():
        m.setdefault(t, {})[col] = (ptab, pcol)
    return m


if __name__ == "__main__":
    validate()
