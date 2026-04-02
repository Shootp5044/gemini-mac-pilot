"""Cloud Run API — exposes the brain as a REST endpoint.

This is a lightweight wrapper that only runs the Gemini brain loop.
Tools that require macOS (accessibility, keyboard, apps) return stubs.
Browser and workspace tools are available in cloud mode.
"""

import os
import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Set GCP project from environment
os.environ.setdefault("GCP_PROJECT", os.environ.get("GOOGLE_CLOUD_PROJECT", ""))

app = FastAPI(title="Mac Pilot Brain API", version="1.0.0")


class TaskRequest(BaseModel):
    task: str
    keep_context: bool = True


class TaskResponse(BaseModel):
    result: str
    status: str = "ok"


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "mac-pilot-brain"}


@app.post("/task", response_model=TaskResponse)
async def execute_task(req: TaskRequest):
    if not req.task or not req.task.strip():
        raise HTTPException(status_code=400, detail="Empty task")

    try:
        from mac_pilot.brain import run_brain_loop
        result = await run_brain_loop(req.task, keep_context=req.keep_context)
        return TaskResponse(result=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
