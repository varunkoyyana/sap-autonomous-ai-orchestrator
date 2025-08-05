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
    if "onboard" in request.task.lower():
        return {"result": "Employee onboarding for HR started."}
    elif "leave" in request.task.lower():
        return {"result": "Leave request is being processed by HR."}
    else:
        return {"result": f"HR agent received unclassified task: '{request.task}'"}
