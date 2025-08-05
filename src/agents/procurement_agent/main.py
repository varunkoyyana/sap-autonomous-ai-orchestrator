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
    if "order" in request.task.lower():
        return {"result": "Procurement is placing an order."}
    elif "supplier" in request.task.lower():
        return {"result": "Supplier onboarding workflow is triggered by Procurement."}
    else:
        return {"result": f"Procurement agent received unclassified task: '{request.task}'"}
