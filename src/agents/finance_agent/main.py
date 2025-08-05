from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import os
app = FastAPI()


MODEL = SentenceTransformer('all-MiniLM-L6-v2')
DOC_PATH = os.path.join(os.path.dirname(__file__), "finance_docs.txt")
with open(DOC_PATH, "r") as f:
    FINANCE_DOCS = [line.strip() for line in f if line.strip()]
FIN_EMB = np.array(MODEL.encode(FINANCE_DOCS))
INDEX = faiss.IndexFlatL2(FIN_EMB.shape[1])
INDEX.add(FIN_EMB)

def search_docs(query, top_k=1):
    q_emb = MODEL.encode([query])
    D, I = INDEX.search(np.array(q_emb), top_k)
    return [FINANCE_DOCS[i] for i in I[0]]

class TaskRequest(BaseModel):
    task: str

@app.get('/health')
def health_check():
    return {'status': 'ok'}

@app.post('/task')
def execute_task(request: TaskRequest):
    q = request.task.lower()
    if "policy" in q or "info" in q or "invoice" in q or "budget" in q:
        results = search_docs(request.task)
        return {"result": f"Semantic search answer: {results[0]}"}
    else:
        return {"result": f"Finance agent received unclassified task: '{request.task}'"}

