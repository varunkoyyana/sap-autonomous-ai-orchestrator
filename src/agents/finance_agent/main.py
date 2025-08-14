import requests
import os
import logging
from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

# -------------------------------------------------
# Logging Config
# -------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

app = FastAPI()

# -------------------------------------------------
# Load Finance reference docs & embeddings
# -------------------------------------------------
try:
    MODEL = SentenceTransformer('all-MiniLM-L6-v2')
    DOC_PATH = os.path.join(os.path.dirname(__file__), "finance_docs.txt")
    with open(DOC_PATH, "r") as f:
        FINANCE_DOCS = [line.strip() for line in f if line.strip()]
    FIN_EMB = np.array(MODEL.encode(FINANCE_DOCS))
    INDEX = faiss.IndexFlatL2(FIN_EMB.shape[1])
    INDEX.add(FIN_EMB)
    logging.info(f"Loaded {len(FINANCE_DOCS)} finance documents.")
except Exception as e:
    logging.error("Failed to load finance docs or embeddings: %s", e)
    FINANCE_DOCS = []
    INDEX = None

def search_docs(query, top_k=1):
    if INDEX is None or not FINANCE_DOCS:
        logging.warning("Finance document index is empty.")
        return []
    try:
        q_emb = MODEL.encode([query])
        D, I = INDEX.search(np.array(q_emb), top_k)
        return [FINANCE_DOCS[i] for i in I[0]]
    except Exception as e:
        logging.error("Error searching finance docs: %s", e)
        return []

# -------------------------------------------------
# Environment/LLM
# -------------------------------------------------
load_dotenv()
llm = ChatOpenAI(
    model="gpt-3.5-turbo",
    openai_api_key=os.getenv("OPENAI_API_KEY")
)
SAP_API_URL_INVOICE = os.getenv("SAP_API_URL_INVOICE", "")

def get_sap_token():
    token_url = os.getenv("SAP_TOKEN_URL")
    client_id = os.getenv("SAP_CLIENT_ID")
    client_secret = os.getenv("SAP_CLIENT_SECRET")

    if not all([token_url, client_id, client_secret]):
        msg = "Missing SAP OAuth2 credentials in .env"
        logging.error(msg)
        raise RuntimeError(msg)

    try:
        resp = requests.post(
            token_url,
            data={'grant_type': 'client_credentials'},
            auth=(client_id, client_secret)
        )
        resp.raise_for_status()
        token = resp.json().get("access_token")
        logging.info("SAP token retrieved successfully.")
        return token
    except Exception as e:
        logging.error("Error fetching SAP token: %s", e)
        raise

def generate_answer(query, context):
    try:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert finance assistant. Use the provided company finance documents to answer clearly and concisely."),
            ("human", "Question: {question}\nContext: {context}")
        ])
        return llm.invoke(prompt.format_messages(question=query, context=context)).content
    except Exception as e:
        logging.error("Error generating LLM answer: %s", e)
        return "Error generating answer."

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
# Main endpoint for finance tasks
# -------------------------------------------------
@app.post("/task")
def execute_task(request: TaskRequest):
    logging.info("Received task: %s", request.task)
    q = request.task.lower()

    try:
        # Finance domain keywords
        if any(k in q for k in ["invoice", "payment", "budget", "expense", "statement"]):

            results = search_docs(request.task)
            context_doc = results[0] if results else ""
            answer = generate_answer(request.task, context_doc)

            # ----------------------------
            # Invoice Process Section
            # ----------------------------
            if "invoice" in q:
                if not SAP_API_URL_INVOICE:
                    logging.error("Missing SAP_API_URL_INVOICE in environment.")
                    return {
                        "result": answer,
                        "source_document": context_doc,
                        "sap_api_status": "ERROR",
                        "sap_api_result": "Missing SAP_API_URL_INVOICE in environment variables."
                    }

                payload = {
                    "invoiceNumber": "INV-20230815-001",  # TODO: make dynamic
                    "vendorName": "ACME Supplies",
                    "amount": 1250.0,
                    "currency": "USD",
                    "dueDate": "2025-09-30"
                }
                try:
                    token = get_sap_token()
                    headers = {
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    }
                    logging.info("Sending invoice process request to SAP: %s", SAP_API_URL_INVOICE)
                    sap_resp = requests.post(SAP_API_URL_INVOICE, json=payload, headers=headers, timeout=15)
                    sap_status = sap_resp.status_code
                    if sap_resp.headers.get("Content-Type", "").startswith("application/json"):
                        sap_result = sap_resp.json()
                    else:
                        sap_result = sap_resp.text
                    logging.info("SAP Invoice API Response Status: %s", sap_status)
                except Exception as e:
                    sap_status = "ERROR"
                    sap_result = str(e)
                    logging.error("SAP invoice API call failed: %s", e)

                return {
                    "result": answer,
                    "source_document": context_doc,
                    "sap_api_status": sap_status,
                    "sap_api_result": sap_result
                }

            # Non-invoice finance tasks
            return {
                "result": answer,
                "source_document": context_doc
            }

        # Fallback for unrelated tasks
        return {
            "result": f"Finance agent received unclassified task: '{request.task}'"
        }

    except Exception as e:
        logging.error("Unexpected error in execute_task: %s", e)
        return {
            "error": str(e),
            "message": "Internal server error during finance task processing."
        }
