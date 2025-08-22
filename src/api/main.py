from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev - allows all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

class WorkflowRequest(BaseModel):
    domain: str  # 'hr', 'finance', or 'procurement'
    task: str

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/workflow")
async def handle_workflow(request: WorkflowRequest):
    domain_urls = {
        "hr": "https://hr-agent-fearless-gorilla-qc.cfapps.us10-001.hana.ondemand.com",
        "finance": "https://finance-agent-unexpected-camel-xm.cfapps.us10-001.hana.ondemand.com",
        "procurement": "https://procurement-agent-bold-pangolin-za.cfapps.us10-001.hana.ondemand.com",
    }
    agent_url = domain_urls.get(request.domain)
    if not agent_url:
        raise HTTPException(status_code=400, detail=f"Agent URL for domain {request.domain} is not set")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{agent_url}/task", json={"task": request.task})
        response.raise_for_status()
        return response.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Could not reach agent: {e}")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Agent error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Orchestrator error: {str(e)}")

