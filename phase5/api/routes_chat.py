"""POST /api/chat - conversational BIS assistance (SIMPLE path)."""
from fastapi import APIRouter, HTTPException

from agent.orchestrator import chat
from schemas.responses import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    try:
        out = chat(req.message, conversation_id=req.conversation_id,
                   language=req.language)
        return ChatResponse(**out)
    except SystemExit as e:
        raise HTTPException(status_code=503,
                            detail="database credentials missing (exit %s)"
                                   % e.code)
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail="%s: %s" % (type(e).__name__,
                                               str(e)[:200]))
