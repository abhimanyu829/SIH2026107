"""POST /api/agent/run - explicit or auto-selected complex workflow."""
from fastapi import APIRouter, HTTPException

from agent.orchestrator import agent_run
from schemas.responses import AgentRunRequest, AgentRunResponse

router = APIRouter(tags=["agent"])


@router.post("/agent/run", response_model=AgentRunResponse)
def agent_endpoint(req: AgentRunRequest):
    try:
        # /agent/run always executes the agentic path; force_agent only
        # documents intent (the endpoint exists for explicit agent runs)
        out = agent_run(req.message, conversation_id=req.conversation_id,
                        language=req.language, force_agent=True)
        return AgentRunResponse(**out)
    except SystemExit as e:
        raise HTTPException(status_code=503,
                            detail="database credentials missing (exit %s)"
                                   % e.code)
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail="%s: %s" % (type(e).__name__,
                                               str(e)[:200]))
