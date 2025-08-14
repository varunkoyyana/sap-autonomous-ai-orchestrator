from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx

app = FastAPI()

class WorkflowRequest(BaseModel):
    domain: str  # 'hr', 'finance', or 'procurement'
    task: str

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/workflow")
async def handle_workflow(request: WorkflowRequest):
    domain_urls = {
        "hr": "http://127.0.0.1:8001",
        "finance": "http://127.0.0.1:8002",
        "procurement": "http://127.0.0.1:8003",
    }
    if request.domain not in domain_urls:
        raise HTTPException(status_code=400, detail="Invalid domain")
    agent_url = domain_urls[request.domain]

    async with httpx.AsyncClient() as client:
        response = await client.post(f"{agent_url}/task", json={"task": request.task})

    return response.json()
