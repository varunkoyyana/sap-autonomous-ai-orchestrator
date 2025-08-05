from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class TaskRequest(BaseModel):
    task: str

@app.get('/health')
def health_check():
    return {'status': 'ok'}

@app.post('/task')
def execute_task(request: TaskRequest):
    if "invoice" in request.task.lower():
        return {"result": "Finance is processing the invoice."}
    elif "budget" in request.task.lower():
        return {"result": "Budget allocation workflow is triggered by Finance."}
    else:
        return {"result": f"Finance agent received unclassified task: '{request.task}'"}
