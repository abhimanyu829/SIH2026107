"""GET lookup endpoints - direct structured access over Supabase.

One thin wrapper per entity; the LLM never writes SQL, and neither do these.
"""
from fastapi import APIRouter, HTTPException

from tools import call

router = APIRouter(tags=["lookup"])


def _tool(name, **kwargs):
    r = call(name, **kwargs)
    if not r["ok"]:
        raise HTTPException(status_code=404, detail=r.get("error") or "not found")
    return {"data": r["data"], "provenance": r["provenance"]}


@router.get("/standards/{is_number}")
def standard(is_number: str, year: str = ""):
    return _tool("get_standard", is_number=is_number, year=year)


@router.get("/products/{product_id}")
def product(product_id: str):
    """Product by id, with its linked standards."""
    r = call("find_product", query=product_id)
    if not r["ok"] or not r["data"]:
        raise HTTPException(status_code=404, detail="product not found")
    row = next((p for p in r["data"] if p.get("product_id") == product_id),
               None)
    if row is None:
        raise HTTPException(status_code=404, detail="product id not matched")
    from tools._shared import supabase
    stds = supabase().standards_for_product(product_id)
    return {"data": {"product": row, "standards": stds},
            "provenance": "Supabase bis.product_master + is_product_mapping"}


@router.get("/qco/{is_number}")
def qco(is_number: str):
    return _tool("get_qco", is_number=is_number)


@router.get("/schemes/{is_number}")
def scheme(is_number: str):
    return _tool("get_scheme", is_number=is_number)


@router.get("/tests/{is_number}")
def tests(is_number: str):
    return _tool("get_tests", is_number=is_number)


@router.get("/labs/{is_number}")
def labs(is_number: str, limit: int = 25):
    return _tool("find_labs", is_number=is_number, limit=limit)


@router.get("/evidence/{document_id}")
def evidence(document_id: str):
    return _tool("get_document", document_id=document_id)
