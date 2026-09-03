"""Supabase PostgreSQL retriever: exact lookups + relationship traversal.

Structured authority data lives ONLY here; Qdrant holds the semantic evidence.
Query understanding is deterministic: regex for IS numbers, keyword match for
products/standards. No LLM, no fuzzy magic.

Each method returns plain dicts so run_phase4.py can serialize them straight
into PHASE4_VALIDATION.json and the smoke-test report.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
from supabase.connect import connect  # noqa: E402

# IS 17631 / IS 2347:2023 / IS 302-2-25 / is 9873-1 ...
IS_RE = re.compile(r"\bIS\s*[:\-]?\s*(\d{2,6})(?:\s*[:\-]\s*(\d{4}))?", re.IGNORECASE)
# Words with no retrieval value in the smoke queries.
STOPWORDS = {"what", "which", "who", "where", "when", "is", "are", "the", "a", "an",
             "of", "for", "to", "applies", "apply", "required", "requires",
             "relevant", "tests", "test", "can", "perform", "certification",
             "scheme", "schemes", "standard", "standards", "product", "products",
             "manual", "manuals", "laboratory", "laboratories", "labs", "work"}


def _rows(cur):
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _q(s):
    """SQL-escape hatch for the two ILIKE patterns built from user text."""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def significant_tokens(text):
    return [t for t in re.findall(r"[a-z0-9]+", text.lower())
            if len(t) >= 3 and t not in STOPWORDS]


class PostgresRetriever:
    def __init__(self):
        self.conn = connect(autocommit=True)

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass

    # ---------------- exact lookups ----------------
    def find_standard(self, is_number, year=None):
        """Exact IS lookup by canonical number (display number as fallback)."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM bis.is_master WHERE canonical_is_number = %s",
                        ("IS %s" % is_number,))
            rows = _rows(cur)
            if not rows and year:
                cur.execute("SELECT * FROM bis.is_master "
                            "WHERE display_is_number ILIKE %s LIMIT 1",
                            (_q("IS %s:%s" % (is_number, year)) + "%",))
                rows = _rows(cur)
            return rows[0] if rows else None

    def search_products(self, term, tokens=None, limit=10):
        """Keyword product search. AND-semantics: every token must appear in
        product_name/alternate_names/keywords, else fall back to OR matches."""
        tokens = tokens or significant_tokens(term)
        if not tokens:
            return []
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT product_id, product_name, product_category,
                       alternate_names, keywords, certification_scheme_to_store
                  FROM bis.product_master
                 WHERE """ + " OR ".join(
                     ["(coalesce(product_name,'') || ' ' || coalesce(alternate_names,'') "
                      "|| ' ' || coalesce(keywords,'')) ILIKE %s"] * len(tokens)) +
                " LIMIT %s",
                tuple("%%%s%%" % _q(t) for t in tokens) + (200,))
            candidates = _rows(cur)
        # score = number of tokens matched; keep rows matching ALL tokens, else top N
        def score(p):
            hay = " ".join([p.get("product_name") or "", p.get("alternate_names") or "",
                            p.get("keywords") or ""]).lower()
            return sum(1 for t in tokens if t in hay)
        full = [p for p in candidates if score(p) == len(tokens)]
        pool = full or sorted(candidates, key=score, reverse=True)[:limit]
        seen, out = set(), []
        for p in pool:
            if p["product_id"] not in seen:
                seen.add(p["product_id"])
                out.append(p)
            if len(out) >= limit:
                break
        return out

    def search_standards(self, term, limit=5):
        tokens = significant_tokens(term)
        if not tokens:
            return []
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT is_id, canonical_is_number, display_is_number, title,
                       standard_status, mandatory_voluntary
                  FROM bis.is_master
                 WHERE """ + " OR ".join(
                     ["(coalesce(title,'') || ' ' || coalesce(standard_scope,'') || ' ' "
                      "|| coalesce(product_category,'')) ILIKE %s"] * len(tokens)) +
                " LIMIT 200",
                tuple("%%%s%%" % _q(t) for t in tokens))
            candidates = _rows(cur)
        def score(s):
            hay = " ".join([s.get("title") or "", s.get("standard_scope") or "",
                            s.get("product_category") or ""]).lower()
            return sum(1 for t in tokens if t in hay)
        return sorted(candidates, key=score, reverse=True)[:limit]

    def standards_for_product(self, product_id):
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT s.is_id, s.canonical_is_number, s.title,
                       m.relationship_type
                  FROM bis.is_product_mapping m
                  JOIN bis.is_master s ON s.is_id = m.is_id
                 WHERE m.product_id = %s
                 ORDER BY s.canonical_is_number""", (product_id,))
            return _rows(cur)

    # ---------------- relationship traversal ----------------
    def products(self, is_id):
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT p.product_id, p.product_name, p.product_category,
                       m.relationship_type
                  FROM bis.is_product_mapping m
                  JOIN bis.product_master p ON p.product_id = m.product_id
                 WHERE m.is_id = %s ORDER BY p.product_name""", (is_id,))
            return _rows(cur)

    def qcos(self, is_id):
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT q.qco_id, q.qco_number, q.qco_name, q.effective_date,
                       q.mandatory_status, q.official_document_url, m.relationship_type
                  FROM bis.is_qco_mapping m
                  JOIN bis.qco_master q ON q.qco_id = m.qco_id
                 WHERE m.is_id = %s ORDER BY q.qco_number""", (is_id,))
            return _rows(cur)

    def schemes(self, is_id):
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT sc.scheme_id, sc.scheme_code, sc.scheme_name,
                       sc.certification_type, m.relationship_type
                  FROM bis.is_scheme_mapping m
                  JOIN bis.scheme_master sc ON sc.scheme_id = m.scheme_id
                 WHERE m.is_id = %s ORDER BY sc.scheme_code""", (is_id,))
            return _rows(cur)

    def tests(self, is_id):
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT t.test_id, t.test_name, t.test_parameter,
                       t.test_method, t.clause, m.clause_reference,
                       m.relationship_type
                  FROM bis.is_test_mapping m
                  JOIN bis.test_master t ON t.test_id = m.test_id
                 WHERE m.is_id = %s ORDER BY t.test_name""", (is_id,))
            return _rows(cur)

    def manuals(self, is_id):
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT pm.pm_id, pm.manual_title, pm.manual_version,
                       pm.document_url, m.relationship_type
                  FROM bis.is_product_manual_mapping m
                  JOIN bis.product_manual_master pm ON pm.pm_id = m.manual_id
                 WHERE m.is_id = %s""", (is_id,))
            return _rows(cur)

    def labs(self, is_id, limit=25):
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT l.lab_id, l.lab_name, l.city, l.state,
                       l.recognition_status, m.test_id, m.test_name, m.capability
                  FROM bis.is_lab_test_mapping m
                  JOIN bis.lab_master l ON l.lab_id = m.lab_id
                 WHERE m.is_id = %s ORDER BY l.lab_name LIMIT %s""",
                        (is_id, limit))
            return _rows(cur)

    # ---------------- entry point used by the hybrid retriever ----------------
    def structured_lookup(self, query_text, context_is_number=None):
        """Deterministic structured lookup for one natural-language query.

        Order: explicit IS number in the query, then the context IS number,
        then product keyword search, then title keyword search.
        Returns {'standards': [bundle-per-standard]}.
        """
        m = IS_RE.search(query_text)
        standards = []
        if m:
            s = self.find_standard(m.group(1), year=m.group(2))
            standards = [s] if s else []
        elif context_is_number:
            s = self.find_standard(*_split_is(context_is_number))
            standards = [s] if s else []
        if not standards:
            products = self.search_products(query_text)
            seen = set()
            for p in products[:3]:
                for s in self.standards_for_product(p["product_id"]):
                    if s["is_id"] not in seen:
                        seen.add(s["is_id"])
                        standards.append(self._std_row(s["is_id"]))
        if not standards:
            standards = self.search_standards(query_text, limit=3)

        bundles = []
        for s in standards[:3]:
            is_id = s["is_id"]
            bundles.append({
                "standard": {"is_id": is_id,
                            "canonical_is_number": s.get("canonical_is_number"),
                            "display_is_number": s.get("display_is_number"),
                            "title": s.get("title"),
                            "status": s.get("standard_status")},
                "products": self.products(is_id),
                "qcos": self.qcos(is_id),
                "schemes": self.schemes(is_id),
                "tests": self.tests(is_id),
                "manuals": self.manuals(is_id),
                "labs": self.labs(is_id),
            })
        return {"bundles": bundles}

    def _std_row(self, is_id):
        with self.conn.cursor() as cur:
            cur.execute("SELECT is_id, canonical_is_number, display_is_number, "
                        "title, standard_status FROM bis.is_master WHERE is_id=%s",
                        (is_id,))
            return _rows(cur)[0]


def _split_is(text):
    m = re.search(r"(\d{2,6})(?:[:\-](\d{4}))?", text or "")
    return (m.group(1), m.group(2)) if m else (None, None)


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "What standard applies to office work chairs?"
    r = PostgresRetriever()
    print("[postgres-retriever] query: %s" % q)
    import json
    print(json.dumps(r.structured_lookup(q), indent=2, ensure_ascii=False)[:4000])
    r.close()
