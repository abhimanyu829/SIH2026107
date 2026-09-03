"""POST /api/search - direct evidence search over Qdrant (hybrid side)."""
from fastapi import APIRouter, HTTPException

from schemas.responses import SearchRequest
from tools import call

router = APIRouter(tags=["search"])


@router.post("/search")
def search_endpoint(req: SearchRequest):
    r = call("search_evidence", query=req.query,
             canonical_is_number=req.canonical_is_number,
             document_type=req.document_type, is_id=req.is_id,
             top_k=req.top_k)
    if not r["ok"]:
        raise HTTPException(status_code=502, detail=r.get("error") or "failed")
    return {"query": req.query, "count": len(r["data"]),
            "results": r["data"], "provenance": r["provenance"]}
