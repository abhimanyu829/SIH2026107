"""Live connectivity check: Supabase row counts + Qdrant point count."""
import sys

sys.path.insert(0, ".")
import config as cfg  # noqa: E402

cfg.load_env()

from tools._shared import qdrant, supabase  # noqa: E402

pg = supabase()
with pg.impl.conn.cursor() as cur:
    cur.execute("SELECT relname, n_live_tup FROM pg_stat_user_tables "
                "WHERE schemaname='bis' ORDER BY n_live_tup DESC LIMIT 60")
    rows = cur.fetchall()
    print("bis tables with rows (top):")
    for r in rows[:25]:
        print("  %s: %d" % (r[0], r[1]))
    cur.execute("SELECT count(*) FROM bis.is_master")
    print("is_master exact count:", cur.fetchone()[0])
    cur.execute("SELECT canonical_is_number, title, is_id FROM bis.is_master "
                "WHERE canonical_is_number LIKE '%%17631%%'")
    print("17631 rows:", cur.fetchall())

qd = qdrant()
info = qd.impl.client.get_collections()
print("Qdrant collections:", [c.name for c in info.collections])
cnt = qd.impl.client.count(qd.impl.collection, exact=True)
print("Qdrant exact point count:", cnt.count)
