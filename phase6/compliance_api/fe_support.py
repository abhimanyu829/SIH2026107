"""Frontend support routes: thin GET wrappers over EXISTING phase-5 tools
plus direct-SQL reads for browse/search pages (hallmarking, labs, standards).

NO new business logic. Same pattern as phase5/api/routes_lookup.py: one thin
wrapper per entity. Served by the phase6 app alongside the compliance router,
so the frontend has ONE backend origin.
"""
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/fe", tags=["frontend-support"])


def _supabase():
    from tools._shared import supabase
    return supabase()


# ---- standards search (wraps existing search_standards tool) ----------------
@router.get("/standards/search")
def standards_search(q: str = Query(..., min_length=2), limit: int = 12):
    from tools import call
    r = call("search_standards", query=q, limit=limit)
    if not r["ok"]:
        raise HTTPException(status_code=502, detail=r.get("error") or "failed")
    return {"data": r["data"], "provenance": r["provenance"]}


# ---- product search (wraps existing find_product tool) ---------------------
@router.get("/products/search")
def products_search(q: str = Query(..., min_length=2), limit: int = 12):
    from tools import call
    r = call("find_product", query=q)
    rows = (r["data"] or [])[:max(1, limit)]
    return {"data": rows,
            "provenance": "Supabase bis.product_master (keyword match)"}


# ---- product by id (same shape as /api/products/{id}) ----------------------
@router.get("/products/{product_id}")
def product_detail(product_id: str):
    from tools import call
    r = call("find_product", query=product_id)
    row = next((p for p in (r["data"] or [])
                if p.get("product_id") == product_id), None)
    if row is None:
        raise HTTPException(status_code=404, detail="product not found")
    stds = _supabase().standards_for_product(product_id)
    return {"data": {"product": row, "standards": stds},
            "provenance": "Supabase bis.product_master + is_product_mapping"}


# ---- labs browse: state/city/text filters over bis.lab_master --------------
@router.get("/labs")
def labs_browse(state: str = "", city: str = "", q: str = "",
                lab_type: str = "", limit: int = 60):
    pg = _supabase().impl
    with pg.conn.cursor() as cur:
        sql = ("SELECT lab_id, lab_name, lab_code, lab_type, address, city, "
               "district, state, pin, contact_person, contact_number, email, "
               "recognition_status, scope_url, source_url FROM bis.lab_master "
               "WHERE 1=1")
        args = []
        if state:
            sql += " AND state = %s"
            args.append(state)
        if city:
            sql += " AND city ILIKE %s"
            args.append("%" + city + "%")
        if q:
            sql += " AND (lab_name ILIKE %s OR lab_code ILIKE %s)"
            args += ["%" + q + "%", "%" + q + "%"]
        if lab_type:
            sql += " AND lab_type = %s"
            args.append(lab_type)
        sql += " ORDER BY lab_name LIMIT %s"
        args.append(min(max(1, limit), 200))
        cur.execute(sql, args)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.execute("SELECT DISTINCT state FROM bis.lab_master "
                    "WHERE state IS NOT NULL AND state <> '' ORDER BY state")
        states = [r[0] for r in cur.fetchall()]
    return {"data": {"labs": rows, "states": states},
            "provenance": "Supabase bis.lab_master (BIS-recognized "
                          "laboratories)"}


# ---- lab detail + scope ----------------------------------------------------
@router.get("/labs/{lab_id}")
def lab_detail(lab_id: str):
    pg = _supabase().impl
    with pg.conn.cursor() as cur:
        cur.execute("SELECT lab_id, lab_name, lab_code, lab_type, address, "
                    "city, district, state, pin, contact_person, "
                    "contact_number, email, recognition_status, validity, "
                    "validity_date, scope_url, source_url FROM bis.lab_master "
                    "WHERE lab_id = %s", (lab_id,))
        cols = [d[0] for d in cur.description]
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="lab not found")
        lab = dict(zip(cols, row))
        cur.execute("SELECT ls.test_name, ls.canonical_is_number, "
                    "ls.product_name, ls.test_method_standard, ls.clause_reference, "
                    "ls.scope_status, ls.scope_validity, ls.testing_charge "
                    "FROM bis.lab_scope ls WHERE ls.lab_id = %s LIMIT 40",
                    (lab_id,))
        cols2 = [d[0] for d in cur.description]
        scope = [dict(zip(cols2, r)) for r in cur.fetchall()]
    return {"data": {"lab": lab, "scope": scope},
            "provenance": "Supabase bis.lab_master + bis.lab_scope"}


# ---- hallmarking centres (BIS gold hallmarking network) --------------------
@router.get("/hallmarking/centres")
def hallmarking_centres(state: str = "", city: str = "", q: str = "",
                        status: str = "", limit: int = 60):
    pg = _supabase().impl
    with pg.conn.cursor() as cur:
        sql = ("SELECT hm_id, centre_name, centre_code, "
               "hallmarking_entity_type, address, city, district, state, pin, "
               "recognition_status, validity, validity_date, centre_type, "
               "region, hallmarking_scope, services, source_url "
               "FROM bis.hallmarking_master WHERE 1=1")
        args = []
        if state:
            sql += " AND state = %s"
            args.append(state)
        if city:
            sql += " AND city ILIKE %s"
            args.append("%" + city + "%")
        if q:
            sql += " AND (centre_name ILIKE %s OR centre_code ILIKE %s)"
            args += ["%" + q + "%", "%" + q + "%"]
        if status:
            sql += " AND recognition_status = %s"
            args.append(status)
        sql += " ORDER BY centre_name LIMIT %s"
        args.append(min(max(1, limit), 200))
        cur.execute(sql, args)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.execute("SELECT DISTINCT state FROM bis.hallmarking_master "
                    "WHERE state IS NOT NULL AND state <> '' ORDER BY state")
        states = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT recognition_status, COUNT(*) FROM "
                    "bis.hallmarking_master GROUP BY recognition_status "
                    "ORDER BY 2 DESC")
        statuses = [{"status": r[0], "count": r[1]} for r in cur.fetchall()]
    return {"data": {"centres": rows, "states": states, "statuses": statuses},
            "provenance": "Supabase bis.hallmarking_master (BIS Assaying "
                          "& Hallmarking centres)"}


# ---- QCO browse -------------------------------------------------------------
@router.get("/qcos")
def qcos_browse(q: str = "", limit: int = 60):
    pg = _supabase().impl
    with pg.conn.cursor() as cur:
        sql = ("SELECT qco_id, qco_number, qco_name, ministry, gazette_date, "
               "effective_date, source_url FROM bis.qco_master WHERE 1=1")
        args = []
        if q:
            sql += " AND (qco_name ILIKE %s OR qco_number ILIKE %s)"
            args += ["%" + q + "%", "%" + q + "%"]
        sql += " ORDER BY qco_name LIMIT %s"
        args.append(min(max(1, limit), 200))
        cur.execute(sql, args)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    return {"data": rows,
            "provenance": "Supabase bis.qco_master"}


# ---- schemes browse ---------------------------------------------------------
@router.get("/schemes")
def schemes_browse():
    pg = _supabase().impl
    with pg.conn.cursor() as cur:
        cur.execute("SELECT scheme_id, scheme_code, scheme_name, description "
                    "FROM bis.scheme_master ORDER BY scheme_code")
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    return {"data": rows,
            "provenance": "Supabase bis.scheme_master"}


# ---- product manual browse --------------------------------------------------
@router.get("/manuals")
def manuals_browse(q: str = "", limit: int = 60):
    pg = _supabase().impl
    with pg.conn.cursor() as cur:
        sql = ("SELECT manual_id, manual_title, is_number, manual_version, "
               "effective_date, source_url FROM bis.product_manual_master "
               "WHERE 1=1")
        args = []
        if q:
            sql += " AND (manual_title ILIKE %s OR is_number ILIKE %s)"
            args += ["%" + q + "%", "%" + q + "%"]
        sql += " ORDER BY manual_title LIMIT %s"
        args.append(min(max(1, limit), 200))
        cur.execute(sql, args)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    return {"data": rows,
            "provenance": "Supabase bis.product_manual_master"}
