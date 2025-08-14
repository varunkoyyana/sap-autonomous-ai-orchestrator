import requests
import os
from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import faiss
import re

import numpy as np
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

app = FastAPI()

# Load embeddings and index
MODEL = SentenceTransformer('all-MiniLM-L6-v2')
DOC_PATH = os.path.join(os.path.dirname(__file__), "procurement_docs.txt")
with open(DOC_PATH, "r") as f:
    PROCUREMENT_DOCS = [line.strip() for line in f if line.strip()]

PROC_EMB = np.array(MODEL.encode(PROCUREMENT_DOCS))
INDEX = faiss.IndexFlatL2(PROC_EMB.shape[1])
INDEX.add(PROC_EMB)


def search_docs(query, top_k=1):
    q_emb = MODEL.encode([query])
    D, I = INDEX.search(np.array(q_emb), top_k)
    return [PROCUREMENT_DOCS[i] for i in I[0]]


# Load environment variables
load_dotenv()
llm = ChatOpenAI(model="gpt-3.5-turbo", openai_api_key=os.getenv("OPENAI_API_KEY"))

# Get SAP API Proxy URL from environment
SAP_API_URL = os.getenv(
    "SAP_API_URL",  # Comes from .env file
    ""              # Fallback if not set
)




#load token

def get_sap_token():
    """Fetch OAuth2 token from SAP BTP service key credentials."""
    token_url = os.getenv("SAP_TOKEN_URL")
    client_id = os.getenv("SAP_CLIENT_ID")
    client_secret = os.getenv("SAP_CLIENT_SECRET")

    if not all([token_url, client_id, client_secret]):
        raise RuntimeError("Missing SAP OAuth2 credentials in environment variables.")

    resp = requests.post(
        token_url,
        data={'grant_type': 'client_credentials'},
        auth=(client_id, client_secret)
    )
    resp.raise_for_status()
    return resp.json().get("access_token")





def generate_answer(query, context):
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert procurement assistant. Use the provided company documents to answer clearly and concisely."),
        ("human", "Question: {question}\nContext: {context}")
    ])
    return llm.invoke(prompt.format_messages(question=query, context=context)).content


# -------------------------------------------------
# Helper: Dynamic product & quantity parser
# -------------------------------------------------
def parse_order_details(task_text):
    """
    Extract quantity and product from strings like:
    'Place an order for 5 laptops'
    'Order 12 printers'
    """
    pattern = r'order(?: for)? (\d+)\s+([a-zA-Z]+)'
    match = re.search(pattern, task_text.lower())
    if match:
        quantity = int(match.group(1))
        product = match.group(2).capitalize()
        return product, quantity
    else:
        # Default values if nothing matches
        return "Laptop", 10

# -------------------------------------------------
# Request model
# -------------------------------------------------
class TaskRequest(BaseModel):
    task: str

# -------------------------------------------------
# Health check endpoint
# -------------------------------------------------
@app.get("/health")
def health_check():
    return {"status": "ok"}

# -------------------------------------------------
# Main endpoint for procurement tasks
# -------------------------------------------------
@app.post("/task")
def execute_task(request: TaskRequest):
    q = request.task.lower()

    if "policy" in q or "info" in q or "order" in q or "supplier" in q:
        # Search internal docs
        results = search_docs(request.task)
        answer = generate_answer(request.task, results[0])

        # If it's an order task, call SAP API Proxy
        if "order" in q:
            product, quantity = parse_order_details(request.task)
            payload = {
                "product": product,
                "quantity": quantity
            }
            try:
                token = get_sap_token()
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
                sap_url = os.getenv("SAP_API_URL")

                sap_resp = requests.post(sap_url, json=payload, headers=headers)
                sap_status = sap_resp.status_code
                if sap_resp.headers.get("Content-Type", "").startswith("application/json"):
                    sap_result = sap_resp.json()
                else:
                    sap_result = sap_resp.text
            except Exception as e:
                sap_status = "ERROR"
                sap_result = str(e)

            return {
                "result": answer,
                "source_document": results[0],
                "sap_api_status": sap_status,
                "sap_api_result": sap_result
            }

        # Non-order procurement tasks
        return {
            "result": answer,
            "source_document": results[0]
        }

    # Fallback for unrelated tasks
    return {
        "result": f"Procurement agent received unclassified task: '{request.task}'"
    }