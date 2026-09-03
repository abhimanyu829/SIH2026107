"""Phase-6 API assembly: MOUNTS the existing Phase-5 app, adds /api/compliance.

Phase 5's FastAPI code is imported unchanged - this module only includes the
compliance router on top of it. Run:  uvicorn compliance_api.app:app --port 8002
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "phase5"))

from api.main import app as phase5_app  # noqa: E402  (existing app)

from . import routes  # noqa: E402

phase5_app.include_router(routes.router)

app = phase5_app

